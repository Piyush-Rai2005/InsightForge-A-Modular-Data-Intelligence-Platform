"""
SessionVectorStore — ephemeral, per-session column index using ChromaDB + MiniLM.

ACTIVATION THRESHOLD:
  ≤ COLUMN_RAG_THRESHOLD columns → callers must skip this class entirely
                                   (full schema is already small enough for LLM)
  >  COLUMN_RAG_THRESHOLD columns → index columns, retrieve only the relevant
                                   subset per question (focused LLM prompts)

Design:
  - EphemeralClient() = pure in-memory, zero disk writes, GC'd when object drops
  - all-MiniLM-L6-v2 is ~80MB; loaded ONCE as a process-level singleton (_MODEL)
    via _get_model() — subsequent SessionVectorStore instances reuse the same object
    so "Loading weights 103/103" only appears once per server process, not per request.
  - Each column document: "Column: {name} | Type: {dtype} | Samples: {top3_values}"
    The sample values give the encoder semantic signal beyond just the column name.
"""
import logging
from typing import List

import pandas as pd

logger = logging.getLogger(__name__)

# Datasets with more than this many columns activate RAG.
COLUMN_RAG_THRESHOLD = 20

# ── Singleton model ────────────────────────────────────────────────────────────
# Loaded once per server process on first use.  Reused by every SessionVectorStore
# instance, across all chat sessions and server reloads within the same process.
_MODEL = None  # type: ignore[assignment]


def _get_model():
    """Return the shared SentenceTransformer, initialising it on first call."""
    global _MODEL
    if _MODEL is None:
        try:
            from sentence_transformers import SentenceTransformer
            import os
            # Suppress the unauthenticated HF-hub warning when no token is set.
            # The model is already cached locally after first download, so this
            # is purely cosmetic noise.
            os.environ.setdefault("HF_HUB_DISABLE_IMPLICIT_TOKEN", "1")
            _MODEL = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("[RAG] SentenceTransformer loaded (process singleton)")
        except Exception as exc:
            logger.warning("[RAG] SentenceTransformer unavailable (%s)", exc)
            _MODEL = None  # type: ignore[assignment]
    return _MODEL




class SessionVectorStore:
    """
    Lightweight, in-memory vector store scoped to one analysis session.

    Usage:
        store = SessionVectorStore("abc123")
        store.index_dataframe(df)                        # run once
        cols = store.get_relevant_columns("revenue?", k=10)  # per question
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self._ready = False
        self._all_columns: List[str] = []

        try:
            import chromadb

            # EphemeralClient = in-memory only, no persistence, no port needed
            self._client = chromadb.EphemeralClient()

            # ChromaDB collection names: alphanumeric + hyphens/underscores, max 63 chars
            safe_id = "".join(
                c if c.isalnum() or c in "-_" else "_" for c in session_id
            )[:55]
            self._collection = self._client.get_or_create_collection(
                name=f"cols_{safe_id}",
                metadata={"hnsw:space": "cosine"},
            )

            # Reuse the process-level singleton — avoids reloading 103 weight
            # shards on every chat request.
            self._model = _get_model()
            if self._model is None:
                raise RuntimeError("SentenceTransformer not available")

            self._ready = True
            logger.info("[RAG] SessionVectorStore ready (session=%s)", session_id)

        except Exception as exc:
            logger.warning(
                "[RAG] VectorStore init failed (%s) — RAG will be skipped", exc
            )

    @property
    def is_ready(self) -> bool:
        return self._ready

    # Hard cap: beyond this many columns we sample representatively.
    # Prevents OOM and multi-minute encode loops on very wide datasets.
    MAX_INDEX_COLS = 500

    def index_dataframe(self, df: pd.DataFrame):
        """
        Index columns in df for semantic retrieval.

        Document format per column:
            "Column: <name> | Type: <dtype> | Samples: <val1>, <val2>, <val3>"

        Key optimisation — batch encode:
            All column documents are encoded in ONE model.encode() call.
            On 9 000 columns this cuts encode time from ~5 min to ~10 s.

        Wide-dataset guard:
            If df has > MAX_INDEX_COLS columns we sample representatively
            (all non-numeric cols first, then top numeric by variance) so
            ChromaDB stays well within memory on free-tier deployments.
        """
        if not self._ready:
            return

        cols_to_index = list(df.columns)
        total_cols = len(cols_to_index)

        if total_cols > self.MAX_INDEX_COLS:
            import pandas as _pd
            obj_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
            num_cols = df.select_dtypes(include="number").columns.tolist()
            # Fill remaining slots with highest-variance numeric columns
            remaining = self.MAX_INDEX_COLS - len(obj_cols)
            if remaining > 0 and num_cols:
                top_num = df[num_cols].var().nlargest(remaining).index.tolist()
            else:
                top_num = []
            cols_to_index = (obj_cols + top_num)[:self.MAX_INDEX_COLS]
            logger.warning(
                "[RAG] Wide dataset (%d cols) — indexing representative %d cols "
                "(%d categorical + %d numeric by variance)",
                total_cols, len(cols_to_index), len(obj_cols), len(top_num),
            )

        documents, ids = [], []
        for col in cols_to_index:
            dtype = str(df[col].dtype)
            try:
                top_vals = df[col].dropna().value_counts().head(3).index.tolist()
                sample_str = ", ".join(str(v) for v in top_vals)
            except Exception:
                sample_str = ""
            text = (
                f"Column: {col} | Type: {dtype} | Samples: {sample_str}"
                if sample_str
                else f"Column: {col} | Type: {dtype}"
            )
            documents.append(text)
            ids.append(col)

        if not documents:
            return

        # ── Batch encode: ONE call instead of N calls — critical for wide data ──
        logger.info("[RAG] Batch-encoding %d column docs…", len(documents))
        embeddings = self._model.encode(
            documents,
            batch_size=128,          # process 128 texts at a time
            show_progress_bar=False,
            convert_to_numpy=True,
        ).tolist()

        self._collection.add(
            documents=documents, embeddings=embeddings, ids=ids
        )
        self._all_columns = cols_to_index
        logger.info(
            "[RAG] Indexed %d/%d columns (session=%s)",
            len(ids), total_cols, self.session_id,
        )

    def get_relevant_columns(self, question: str, k: int = 12) -> List[str]:
        """
        Return the names of the k columns most semantically relevant to question.
        Guaranteed to return something — falls back to all columns on any error.
        """
        if not self._ready or not self._all_columns:
            return self._all_columns

        k = min(k, len(self._all_columns))
        try:
            emb = self._model.encode(question).tolist()
            results = self._collection.query(
                query_embeddings=[emb], n_results=k
            )
            retrieved = results["ids"][0] if results["ids"] else self._all_columns
            logger.debug(
                "[RAG] Retrieved %d/%d cols for question=%r",
                len(retrieved), len(self._all_columns), question[:60],
            )
            return retrieved
        except Exception as exc:
            logger.warning("[RAG] Query failed (%s) — returning all columns", exc)
            return self._all_columns