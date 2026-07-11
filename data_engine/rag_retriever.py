"""
RAGRetriever — threshold-aware schema retrieval for LLM prompts.

Single decision rule:
  len(df.columns) ≤ COLUMN_RAG_THRESHOLD  →  return full schema, zero overhead
  len(df.columns) >  COLUMN_RAG_THRESHOLD  →  embed question, return top-k cols only

This means:
  • Small / demo datasets   → same behaviour as before, instant
  • Wide datasets (50-200+) → focused prompts → faster Groq calls, better accuracy

Used by:
  • agents/schema_insight_agent.py  (step 3 in pipeline — creates + stores retriever)
  • agents/target_agent.py          (step 4 — reuses retriever from context)
  • agents/insight_agent.py         (step 8 — reuses retriever from context)
  • data_engine/query_agent.py      (chat endpoint — creates its own retriever)
"""

import uuid
import logging
from typing import List, Optional

import pandas as pd

from .vector_store import COLUMN_RAG_THRESHOLD, SessionVectorStore

logger = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _schema_text(df: pd.DataFrame, columns: List[str]) -> str:
    """Format a column list as the schema block used in LLM prompts."""
    lines = []
    for col in columns:
        if col not in df.columns:
            continue
        dtype = str(df[col].dtype)
        nunique = int(df[col].nunique())
        lines.append(f"- {col}: {dtype} ({nunique} unique values)")
    return "\n".join(lines)


# ── Main class ─────────────────────────────────────────────────────────────────

class RAGRetriever:
    """
    Create one instance per analysis and reuse it across agents.

    Args:
        df          : The original (pre-cleaning) DataFrame.
        session_id  : Optional stable ID — used as the ChromaDB collection
                      name prefix. Falls back to a random short UUID.

    Attributes:
        rag_active  : True only when df has > COLUMN_RAG_THRESHOLD columns
                      AND ChromaDB + sentence-transformers are available.
    """

    def __init__(self, df: pd.DataFrame, session_id: Optional[str] = None):
        self.df = df
        self.session_id = session_id or str(uuid.uuid4())[:12]
        self.rag_active = False
        self._store: Optional[SessionVectorStore] = None

        n_cols = len(df.columns)

        if n_cols > COLUMN_RAG_THRESHOLD:
            logger.info(
                "[RAGRetriever] %d columns > threshold %d — activating RAG (session=%s)",
                n_cols, COLUMN_RAG_THRESHOLD, self.session_id,
            )
            store = SessionVectorStore(self.session_id)
            if store.is_ready:
                store.index_dataframe(df)
                self._store = store
                self.rag_active = True
            else:
                # ChromaDB / sentence-transformers unavailable — degrade gracefully
                logger.warning(
                    "[RAGRetriever] Store unavailable — falling back to full schema for all queries"
                )
        else:
            logger.info(
                "[RAGRetriever] %d columns ≤ threshold %d — RAG OFF, full schema used directly",
                n_cols, COLUMN_RAG_THRESHOLD,
            )

    # ── Public API ─────────────────────────────────────────────────────────────

    def get_schema(self, question: str, k: int = 12) -> str:
        """
        Return a formatted schema string ready for LLM prompt injection.

        When RAG is ON:  embeds the question → retrieves top-k relevant columns
        When RAG is OFF: returns all columns (dataset is small enough)
        """
        cols = self.get_column_names(question, k=k)
        return _schema_text(self.df, cols)

    def get_column_names(self, question: str, k: int = 12) -> List[str]:
        """
        Return column names for the given question.
        Safe to call always — never raises.
        """
        if self.rag_active and self._store:
            return self._store.get_relevant_columns(question, k=k)
        return list(self.df.columns)
