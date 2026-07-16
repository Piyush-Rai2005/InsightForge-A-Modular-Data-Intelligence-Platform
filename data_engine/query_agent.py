"""
QueryAgent — Robust chat-with-data using DuckDB + optional Groq AI.

Two modes:
  1. LOCAL MODE (no API key): Smart pattern matching → DuckDB SQL → formatted answer
  2. AI MODE (with Groq key): LLM generates SQL + interprets results naturally

The agent NEVER crashes — every question gets an answer.
"""

import os
import re
import logging
import duckdb
import pandas as pd
from dotenv import load_dotenv
from data_engine.rag_retriever import RAGRetriever

logger = logging.getLogger(__name__)

load_dotenv()

# ── Geographic synonym dictionary (US Census Bureau divisions) ────────────────
# Keys: every alias a user might type (all lowercase).
# Values: list of state FULL NAMES — format is resolved at runtime against
#         actual column values (full name / abbreviation / region label).
_GEO_SYNONYMS: dict[str, list[str]] = {
    # ── Pacific division ────────────────────────────────────────────────────
    "pacific coast":      ["California", "Oregon", "Washington", "Alaska", "Hawaii"],
    "pacific division":   ["California", "Oregon", "Washington", "Alaska", "Hawaii"],
    "pacific":            ["California", "Oregon", "Washington", "Alaska", "Hawaii"],
    "west coast":         ["California", "Oregon", "Washington"],
    # ── Mountain division ────────────────────────────────────────────────────
    "mountain division":  ["Arizona", "Colorado", "Idaho", "Montana",
                           "Nevada", "New Mexico", "Utah", "Wyoming"],
    "mountain states":    ["Arizona", "Colorado", "Idaho", "Montana",
                           "Nevada", "New Mexico", "Utah", "Wyoming"],
    # ── West region (Pacific + Mountain) ────────────────────────────────────
    "west region":        ["California", "Oregon", "Washington", "Alaska", "Hawaii",
                           "Arizona", "Colorado", "Idaho", "Montana",
                           "Nevada", "New Mexico", "Utah", "Wyoming"],
    # ── East North Central ───────────────────────────────────────────────────
    "great lakes":        ["Illinois", "Indiana", "Michigan", "Ohio", "Wisconsin"],
    "east north central": ["Illinois", "Indiana", "Michigan", "Ohio", "Wisconsin"],
    # ── West North Central ───────────────────────────────────────────────────
    "west north central": ["Iowa", "Kansas", "Minnesota", "Missouri",
                           "Nebraska", "North Dakota", "South Dakota"],
    "plains states":      ["Iowa", "Kansas", "Minnesota", "Missouri",
                           "Nebraska", "North Dakota", "South Dakota"],
    # ── Midwest (East + West North Central combined) ─────────────────────────
    "midwest":            ["Illinois", "Indiana", "Iowa", "Kansas", "Michigan",
                           "Minnesota", "Missouri", "Nebraska", "North Dakota",
                           "Ohio", "South Dakota", "Wisconsin"],
    "midwestern states":  ["Illinois", "Indiana", "Iowa", "Kansas", "Michigan",
                           "Minnesota", "Missouri", "Nebraska", "North Dakota",
                           "Ohio", "South Dakota", "Wisconsin"],
    # ── New England ──────────────────────────────────────────────────────────
    "new england":        ["Connecticut", "Maine", "Massachusetts",
                           "New Hampshire", "Rhode Island", "Vermont"],
    # ── Mid-Atlantic ─────────────────────────────────────────────────────────
    "mid atlantic":       ["New Jersey", "New York", "Pennsylvania"],
    "mid-atlantic":       ["New Jersey", "New York", "Pennsylvania"],
    # ── Northeast (New England + Mid-Atlantic) ───────────────────────────────
    "northeast":          ["Connecticut", "Maine", "Massachusetts",
                           "New Hampshire", "Rhode Island", "Vermont",
                           "New Jersey", "New York", "Pennsylvania"],
    # ── South Atlantic ───────────────────────────────────────────────────────
    "south atlantic":     ["Delaware", "Florida", "Georgia", "Maryland",
                           "North Carolina", "South Carolina",
                           "Virginia", "West Virginia", "District of Columbia"],
    "east coast":         ["Maine", "New Hampshire", "Massachusetts", "Rhode Island",
                           "Connecticut", "New York", "New Jersey", "Pennsylvania",
                           "Delaware", "Maryland", "Virginia", "North Carolina",
                           "South Carolina", "Georgia", "Florida"],
    # ── East South Central ───────────────────────────────────────────────────
    "east south central": ["Alabama", "Kentucky", "Mississippi", "Tennessee"],
    "deep south":         ["Alabama", "Georgia", "Louisiana",
                           "Mississippi", "South Carolina"],
    # ── West South Central ───────────────────────────────────────────────────
    "west south central": ["Arkansas", "Louisiana", "Oklahoma", "Texas"],
    "southwest":          ["Arizona", "New Mexico", "Oklahoma", "Texas"],
    # ── South region (all three south divisions) ─────────────────────────────
    "south region":       ["Delaware", "Florida", "Georgia", "Maryland",
                           "North Carolina", "South Carolina", "Virginia",
                           "West Virginia", "Alabama", "Kentucky",
                           "Mississippi", "Tennessee", "Arkansas",
                           "Louisiana", "Oklahoma", "Texas"],
    # ── Southeast ────────────────────────────────────────────────────────────
    "southeast":          ["Alabama", "Arkansas", "Florida", "Georgia",
                           "Louisiana", "Mississippi", "North Carolina",
                           "South Carolina", "Tennessee", "Virginia"],
}

# Canonical abbreviation map (full name → 2-letter code)
_STATE_ABBREVS: dict[str, str] = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
    "California": "CA", "Colorado": "CO", "Connecticut": "CT",
    "Delaware": "DE", "District of Columbia": "DC", "Florida": "FL",
    "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL",
    "Indiana": "IN", "Iowa": "IA", "Kansas": "KS", "Kentucky": "KY",
    "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN",
    "Mississippi": "MS", "Missouri": "MO", "Montana": "MT",
    "Nebraska": "NE", "Nevada": "NV", "New Hampshire": "NH",
    "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH",
    "Oklahoma": "OK", "Oregon": "OR", "Pennsylvania": "PA",
    "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD",
    "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT",
    "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
    "Wisconsin": "WI", "Wyoming": "WY",
}


class QueryAgent:
    def __init__(self, parquet_path):
        self.parquet_path = parquet_path

        # DuckDB connection
        self.con = duckdb.connect()
        self.con.execute(
            f"CREATE OR REPLACE VIEW data AS SELECT * FROM read_parquet('{self.parquet_path}')"
        )

        # Read schema
        schema_df = self.con.execute("DESCRIBE data").fetchdf()
        self.columns = schema_df["column_name"].tolist()
        self.col_types = dict(zip(schema_df["column_name"], schema_df["column_type"]))
        self.col_lower_map = {c.lower(): c for c in self.columns}

        # Row count
        self.row_count = self.con.execute("SELECT COUNT(*) FROM data").fetchone()[0]

        # Numeric & categorical columns
        self.numeric_cols = [c for c, t in self.col_types.items()
                            if any(x in t.upper() for x in ["INT", "FLOAT", "DOUBLE", "DECIMAL", "BIGINT", "NUMERIC"])]
        self.cat_cols = [c for c in self.columns if c not in self.numeric_cols]

        # Sample data for AI context
        sample = self.con.execute("SELECT * FROM data LIMIT 3").fetchdf()
        self.sample_text = sample.to_string(index=False, max_cols=20)

        # Try to set up Groq client
        self.client = None
        api_key = os.getenv("GROQ_API_KEY", "")
        if api_key and api_key != "your_groq_api_key_here":
            try:
                from groq import Groq
                self.client = Groq(api_key=api_key)
                print("[OK] Groq AI enabled for chat")
            except Exception:
                print("[WARN] Groq import failed, using local mode")

        # ── RAG Retriever (activated only when dataset has > 20 columns) ───────────
        # Reads a 500-row sample from the Parquet just to embed column sample values;
        # DuckDB continues to query the full file for all SQL operations.
        self._rag: RAGRetriever | None = None
        if len(self.columns) > 20:
            try:
                session_id = os.path.splitext(os.path.basename(parquet_path))[0]
                df_sample = pd.read_parquet(parquet_path).head(500)
                self._rag = RAGRetriever(df_sample, session_id=session_id)
                logger.info("[QueryAgent] RAG retriever initialized (%d cols)", len(self.columns))
            except Exception as exc:
                logger.warning("[QueryAgent] RAG init failed (%s) — will use full schema", exc)
                self._rag = None

        # ── Geographic synonym layer ──────────────────────────────────────────────
        # Detects the geo column + value format once on init (cheap: one DuckDB query).
        # _build_geo_context() is then called per question — returns "" when no alias
        # is present so there is zero overhead for non-geographic questions.
        self._geo_col, self._geo_fmt = self._detect_geo_column()

    # ──────────────────────────────────────────────────────────────────
    # Geographic synonym layer
    # ──────────────────────────────────────────────────────────────────
    def _detect_geo_column(self):
        """
        Scan the dataset to find the geographic column and its value format.

        Returns a tuple (column_name, format) where format is one of:
          'full'   — values like 'California', 'Texas'
          'abbrev' — values like 'CA', 'TX'
          'region' — values like 'West', 'South' (Census region labels)
          None     — no geographic column detected
        """
        # Candidate column names (priority order)
        GEO_COL_KEYWORDS = [
            "state", "province", "region", "territory",
            "st", "geo", "location", "area",
        ]
        geo_col = None
        for keyword in GEO_COL_KEYWORDS:
            for col in self.columns:
                if keyword == col.lower().replace(" ", "_").replace("-", "_"):
                    geo_col = col
                    break
                if keyword in col.lower():
                    geo_col = col
                    break
            if geo_col:
                break

        if not geo_col:
            return None, None

        # Sample unique values from that column
        try:
            sample_df = self.con.execute(
                f'SELECT DISTINCT "{geo_col}" FROM data LIMIT 30'
            ).fetchdf()
            values = (
                sample_df.iloc[:, 0]
                .dropna()
                .astype(str)
                .str.strip()
                .tolist()
            )
        except Exception:
            return geo_col, None

        if not values:
            return geo_col, None

        abbrev_set = set(_STATE_ABBREVS.values())          # 'CA', 'TX', ...
        full_set   = set(_STATE_ABBREVS.keys())            # 'California', ...
        region_labels = {"west", "east", "south", "north", "central",
                         "northeast", "northwest", "southeast", "southwest",
                         "midwest"}  # broad Census region names

        abbrev_hits = sum(1 for v in values if v in abbrev_set)
        full_hits   = sum(1 for v in values if v in full_set)
        region_hits = sum(1 for v in values if v.lower() in region_labels)

        if full_hits >= abbrev_hits and full_hits > 0:
            fmt = "full"
        elif abbrev_hits > 0:
            fmt = "abbrev"
        elif region_hits > 0:
            fmt = "region"
        else:
            fmt = "full"   # safest default

        logger.info(
            "[GEO] Detected geo column=%r  format=%s  "
            "(full_hits=%d, abbrev_hits=%d, region_hits=%d)",
            geo_col, fmt, full_hits, abbrev_hits, region_hits,
        )
        return geo_col, fmt

    def _build_geo_context(self, question: str) -> str:
        """
        Check whether the question contains any known geographic alias.
        If yes, return a ready-to-inject paragraph that tells the LLM
        exactly which column values map to that alias.
        If no alias is detected, return an empty string (zero overhead).

        The paragraph format:
            Geographic synonym mappings for this dataset:
             - 'Pacific coast' / 'Pacific division' → "State" IN ('California', 'Oregon', ...)
            Use these exact column values when writing your SQL WHERE clause.
        """
        if not hasattr(self, "_geo_col") or not self._geo_col:
            return ""

        q_lower = question.lower()
        matched: dict[str, list[str]] = {}   # alias → resolved values

        for alias, full_names in _GEO_SYNONYMS.items():
            if alias in q_lower:
                # Convert full names to the format this dataset actually uses
                if self._geo_fmt == "abbrev":
                    resolved = [_STATE_ABBREVS[s] for s in full_names
                                if s in _STATE_ABBREVS]
                else:
                    # 'full' or 'region' — keep as full names; the LLM will
                    # know the column's actual values from the sample data
                    resolved = full_names
                matched[alias] = resolved

        if not matched:
            return ""

        lines = []
        for alias, vals in matched.items():
            quoted = ", ".join(f"'{v}'" for v in vals)
            lines.append(
                f" - '{alias}' → \"{self._geo_col}\" IN ({quoted})"
            )

        return (
            "Geographic synonym mappings for this dataset:\n"
            + "\n".join(lines)
            + "\nUse these exact column values when writing your SQL WHERE clause.\n"
        )

    # ──────────────────────────────────────────────────────────────────
    # Column matching — find the best column for a user's words
    # ──────────────────────────────────────────────────────────────────
    def _find_column(self, text):
        """Find the best matching column name from user text."""
        text_lower = text.lower()

        # Exact match (case-insensitive)
        for col in self.columns:
            if col.lower() in text_lower:
                return col

        # Fuzzy match — check if any word in column name appears in text
        best_col = None
        best_score = 0
        for col in self.columns:
            col_words = set(re.findall(r'[a-z]+', col.lower().replace("_", " ").replace("-", " ")))
            text_words = set(re.findall(r'[a-z]+', text_lower))
            overlap = len(col_words & text_words)
            if overlap > best_score:
                best_score = overlap
                best_col = col
        return best_col if best_score > 0 else None

    def _find_numeric_column(self, text):
        """Find best matching numeric column."""
        text_lower = text.lower()
        for col in self.numeric_cols:
            if col.lower() in text_lower:
                return col
        # Fuzzy
        for col in self.numeric_cols:
            col_words = set(re.findall(r'[a-z]+', col.lower().replace("_", " ")))
            text_words = set(re.findall(r'[a-z]+', text_lower))
            if col_words & text_words:
                return col
        return self.numeric_cols[0] if self.numeric_cols else None

    # ──────────────────────────────────────────────────────────────────
    # SQL execution helper
    # ──────────────────────────────────────────────────────────────────
    def _run_sql(self, sql):
        """Execute SQL and return dataframe or None."""
        try:
            return self.con.execute(sql).fetchdf()
        except Exception as e:
            print(f"[SQL ERROR] {e}")
            return None

    # ──────────────────────────────────────────────────────────────────
    # Smart local query engine (no AI needed)
    # ──────────────────────────────────────────────────────────────────
    def _local_answer(self, question):
        """Answer questions using pattern matching + DuckDB. No API needed."""
        q = question.lower().strip()

        # ── Row/column count ──
        if any(w in q for w in ["how many rows", "total rows", "row count", "number of rows", "how many records"]):
            return f"The dataset has **{self.row_count:,} rows**."

        if any(w in q for w in ["how many columns", "column count", "number of columns", "what columns", "list columns", "show columns", "what fields"]):
            cols_str = ", ".join([f"`{c}`" for c in self.columns[:40]])
            extra = f" *(and {len(self.columns) - 40} more)*" if len(self.columns) > 40 else ""
            return f"The dataset has **{len(self.columns)} columns:**\n\n{cols_str}{extra}"

        # ── Unique values ──
        if any(w in q for w in ["unique values", "distinct values", "unique in", "distinct in", "categories in"]):
            col = self._find_column(question)
            if col:
                df = self._run_sql(f'SELECT DISTINCT "{col}" FROM data ORDER BY "{col}" LIMIT 30')
                if df is not None and not df.empty:
                    vals = df[col].tolist()
                    val_str = ", ".join([f"`{v}`" for v in vals[:30]])
                    total = self._run_sql(f'SELECT COUNT(DISTINCT "{col}") as cnt FROM data')
                    cnt = total["cnt"].iloc[0] if total is not None else len(vals)
                    extra = f"\n\n*Showing 30 of {cnt} unique values*" if cnt > 30 else ""
                    return f"**Unique values in `{col}`** ({cnt:,} total):\n\n{val_str}{extra}"
            return "Please specify which column you'd like unique values for."

        # ── Top / Best / Most ──
        if any(w in q for w in ["top", "best", "most popular", "highest", "best seller", "best selling", "most sold", "top selling"]):
            # Extract limit number
            limit = 10
            num_match = re.search(r'top\s+(\d+)', q)
            if num_match:
                limit = int(num_match.group(1))

            # Find a good column to rank by
            rank_col = self._find_numeric_column(question)
            group_col = self._find_column(question)

            if group_col and group_col in self.numeric_cols:
                # User mentioned a numeric column — find a categorical one
                for c in self.cat_cols:
                    if c.lower() not in ["row id", "order id", "id"]:
                        group_col = c
                        break

            if group_col and rank_col and group_col != rank_col:
                df = self._run_sql(
                    f'SELECT "{group_col}", SUM("{rank_col}") as total_{rank_col.lower().replace(" ", "_")} '
                    f'FROM data GROUP BY "{group_col}" ORDER BY 2 DESC LIMIT {limit}'
                )
                if df is not None and not df.empty:
                    return f"**Top {limit} by `{rank_col}`:**\n\n{self._format_table(df)}"
            elif group_col:
                df = self._run_sql(
                    f'SELECT "{group_col}", COUNT(*) as count '
                    f'FROM data GROUP BY "{group_col}" ORDER BY count DESC LIMIT {limit}'
                )
                if df is not None and not df.empty:
                    return f"**Top {limit} `{group_col}` by count:**\n\n{self._format_table(df)}"

        # ── Average / Mean ──
        if any(w in q for w in ["average", "mean", "avg"]):
            col = self._find_numeric_column(question)
            if col:
                df = self._run_sql(f'SELECT ROUND(AVG("{col}"), 2) as average_{col.lower().replace(" ", "_")} FROM data')
                if df is not None and not df.empty:
                    val = df.iloc[0, 0]
                    return f"**Average `{col}`:** {val:,.2f}"

        # ── Sum / Total ──
        if any(w in q for w in ["total", "sum"]) and not any(w in q for w in ["rows", "columns"]):
            col = self._find_numeric_column(question)
            if col:
                df = self._run_sql(f'SELECT ROUND(SUM("{col}"), 2) as total_{col.lower().replace(" ", "_")} FROM data')
                if df is not None and not df.empty:
                    val = df.iloc[0, 0]
                    return f"**Total `{col}`:** {val:,.2f}"

        # ── Min / Max ──
        if any(w in q for w in ["minimum", "lowest", "smallest", "min"]):
            col = self._find_numeric_column(question)
            if col:
                df = self._run_sql(f'SELECT MIN("{col}") as min_{col.lower().replace(" ", "_")} FROM data')
                if df is not None and not df.empty:
                    return f"**Minimum `{col}`:** {df.iloc[0, 0]:,}"

        if any(w in q for w in ["maximum", "largest", "biggest", "max"]):
            col = self._find_numeric_column(question)
            if col:
                df = self._run_sql(f'SELECT MAX("{col}") as max_{col.lower().replace(" ", "_")} FROM data')
                if df is not None and not df.empty:
                    return f"**Maximum `{col}`:** {df.iloc[0, 0]:,}"

        # ── Distribution / Breakdown / Group by ──
        if any(w in q for w in ["distribution", "breakdown", "group by", "by category", "per", "each"]):
            group_col = None
            for c in self.cat_cols:
                if c.lower() in q:
                    group_col = c
                    break
            if not group_col:
                group_col = self._find_column(question)

            num_col = self._find_numeric_column(question)
            if group_col and num_col and group_col != num_col:
                df = self._run_sql(
                    f'SELECT "{group_col}", ROUND(SUM("{num_col}"), 2) as total, '
                    f'ROUND(AVG("{num_col}"), 2) as average, COUNT(*) as count '
                    f'FROM data GROUP BY "{group_col}" ORDER BY total DESC LIMIT 15'
                )
                if df is not None and not df.empty:
                    return f"**`{num_col}` by `{group_col}`:**\n\n{self._format_table(df)}"

        # ── Summary / Overview / Describe ──
        if any(w in q for w in ["summary", "describe", "statistics", "overview", "stats"]):
            stats = []
            for col in self.numeric_cols[:8]:
                row = self._run_sql(
                    f'SELECT ROUND(AVG("{col}"), 2) as avg, ROUND(MIN("{col}"), 2) as min, '
                    f'ROUND(MAX("{col}"), 2) as max FROM data'
                )
                if row is not None and not row.empty:
                    stats.append(f"- **{col}**: avg={row['avg'].iloc[0]:,}, min={row['min'].iloc[0]:,}, max={row['max'].iloc[0]:,}")
            if stats:
                return f"**Dataset Summary** ({self.row_count:,} rows, {len(self.columns)} columns):\n\n" + "\n".join(stats)

        # ── What-if / Hypothetical ──
        if any(w in q for w in ["what if", "what happens", "what would", "if we", "increase by", "decrease by", "jump by"]):
            # Extract percentage
            pct_match = re.search(r'(\d+)\s*%', q)
            pct = int(pct_match.group(1)) / 100 if pct_match else 0.20
            
            col = self._find_numeric_column(question)
            if col:
                stats = self._run_sql(
                    f'SELECT ROUND(SUM("{col}"), 2) as current_total, '
                    f'ROUND(AVG("{col}"), 2) as current_avg, '
                    f'ROUND(MIN("{col}"), 2) as current_min, '
                    f'ROUND(MAX("{col}"), 2) as current_max FROM data'
                )
                if stats is not None and not stats.empty:
                    curr_total = stats["current_total"].iloc[0]
                    curr_avg = stats["current_avg"].iloc[0]
                    new_total = curr_total * (1 + pct)
                    new_avg = curr_avg * (1 + pct)
                    direction = "increase" if pct > 0 else "decrease"
                    pct_display = abs(pct) * 100

                    return (
                        f"### 📊 What-If Analysis: `{col}` {direction}s by {pct_display:.0f}%\n\n"
                        f"| Metric | Current | Projected |\n"
                        f"|--------|--------:|----------:|\n"
                        f"| **Total** | {curr_total:,.2f} | {new_total:,.2f} |\n"
                        f"| **Average** | {curr_avg:,.2f} | {new_avg:,.2f} |\n"
                        f"| **Change** | — | {'+' if pct > 0 else ''}{curr_total * pct:,.2f} |\n\n"
                        f"*A {pct_display:.0f}% {direction} in `{col}` would move the total from "
                        f"**{curr_total:,.2f}** to **{new_total:,.2f}***"
                    )

        # ── Show / List data ──
        if any(w in q for w in ["show me", "show", "list", "display", "sample", "examples"]):
            limit = 10
            num_match = re.search(r'(\d+)', q)
            if num_match:
                limit = min(int(num_match.group(1)), 50)
            col = self._find_column(question)
            if col:
                df = self._run_sql(f'SELECT "{col}" FROM data LIMIT {limit}')
                if df is not None and not df.empty:
                    return f"**Sample `{col}` ({limit} rows):**\n\n{self._format_table(df)}"
            else:
                df = self._run_sql(f'SELECT * FROM data LIMIT {limit}')
                if df is not None and not df.empty:
                    return f"**Sample data ({limit} rows):**\n\n{self._format_table(df)}"

        # ── Correlation / Relationship ──
        if any(w in q for w in ["correlation", "relationship", "related", "correlate"]):
            if len(self.numeric_cols) >= 2:
                pairs = []
                for i, c1 in enumerate(self.numeric_cols[:5]):
                    for c2 in self.numeric_cols[i+1:5]:
                        corr = self._run_sql(f'SELECT ROUND(CORR("{c1}", "{c2}"), 3) as correlation FROM data')
                        if corr is not None and not corr.empty:
                            val = corr["correlation"].iloc[0]
                            if val is not None:
                                pairs.append(f"- `{c1}` ↔ `{c2}`: **{val}**")
                if pairs:
                    return f"**Correlations between numeric columns:**\n\n" + "\n".join(pairs)

        return None  # No local answer found

    # ──────────────────────────────────────────────────────────────────
    # AI-powered query (uses Groq when available)
    # ──────────────────────────────────────────────────────────────────
    def _ai_answer(self, question):
        """Use Groq to generate SQL, run it, then interpret results."""
        if not self.client:
            return None

        # Build schema for the LLM prompt.
        # RAG ON  (> 20 cols): embed question → retrieve only the relevant subset
        #   └─ Smaller prompt = faster Groq call + fewer hallucinated column names
        # RAG OFF (≤ 20 cols): dump full schema directly (same as before)
        if self._rag and self._rag.rag_active:
            schema = self._rag.get_schema(question, k=12)
            logger.debug("[QueryAgent] RAG schema selected for prompt")
        else:
            schema_lines = []
            for col in self.columns[:60]:
                schema_lines.append(f"  - {col} ({self.col_types[col]})")
            schema = "\n".join(schema_lines)

        # Geographic synonym injection — resolves aliases like 'Pacific coast',
        # 'Midwest', 'New England' into exact column values BEFORE the LLM writes SQL.
        # Returns "" when the question contains no recognized geographic alias.
        geo_context = self._build_geo_context(question)
        if geo_context:
            logger.info("[GEO] Injecting synonym mapping into prompt: %s", geo_context[:120])

        # Step 1: Generate SQL
        prompt = f"""You are a DuckDB SQL expert and data analyst. The user is asking about their dataset.

Table: data ({self.row_count:,} rows)
Columns:
{schema}

Sample data:
{self.sample_text}
{(chr(10) + geo_context) if geo_context else ""}
User question: {question}

Instructions:
1. If this is a factual data question, write a DuckDB SQL query to answer it.
2. If this is a hypothetical/what-if question, write SQL to get the CURRENT values, then I'll compute the projection.
3. Return ONLY the SQL query — no explanation, no markdown fences.
4. Table name is "data" — use exact column names (case-sensitive, wrap in double quotes).
5. LIMIT results to 20 rows.
6. Keep it simple — prefer COUNT, AVG, SUM, GROUP BY.
7. If geographic synonyms are provided above, always use the exact IN clause values given."""

        try:
            resp = self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                timeout=30,  # never hang longer than 30 s
            )
            sql = resp.choices[0].message.content.strip()
            # Strip markdown fences the LLM sometimes wraps the query in
            sql = sql.replace("```sql", "").replace("```", "").strip()
            # DuckDB uses double-quote identifiers ("Column"), NOT MySQL backticks (`Column`).
            # Llama occasionally outputs backtick quoting — convert it before execution.
            sql = re.sub(r'`([^`]+)`', r'"\1"', sql)
            if sql.startswith('"') and sql.endswith('"'):
                sql = sql[1:-1]

            print(f"[AI SQL] {sql}")
            df = self._run_sql(sql)
            
            if df is not None:
                # Step 2: Have AI interpret the result
                if df.empty:
                    result_text = "The query ran successfully, but returned 0 rows (no data found)."
                else:
                    result_text = df.head(20).to_string(index=False)
                    
                interpret_prompt = f"""The user asked: "{question}"

I ran this SQL: {sql}

Result:
{result_text}

Write a clear, helpful answer in markdown. Use bold for key numbers. Be conversational. Keep it under 200 words.
IMPORTANT: NEVER show the SQL query you ran to the user. Do NOT include any SQL blocks or SQL code in your response."""

                resp2 = self.client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "user", "content": interpret_prompt}],
                    temperature=0.3,
                    timeout=30,  # never hang longer than 30 s
                )
                return resp2.choices[0].message.content.strip()
        except Exception as e:
            print(f"[AI FAILED] {e}")
            return None

        return None

    # ──────────────────────────────────────────────────────────────────
    # Format helpers
    # ──────────────────────────────────────────────────────────────────
    def _format_table(self, df):
        """Format a dataframe as a markdown table."""
        try:
            return df.to_markdown(index=False)
        except Exception:
            return f"```text\n{df.to_string(index=False)}\n```"

    # ──────────────────────────────────────────────────────────────────
    # Main entry point
    # ──────────────────────────────────────────────────────────────────
    def run(self, question):
        """
        Answer any user question about their data.
        Returns a formatted markdown string — never crashes.
        """
        # Phase 1: Try AI first (Groq) — best quality answers
        if self.client:
            try:
                ai = self._ai_answer(question)
                if ai:
                    return ai
            except Exception as e:
                print(f"[AI ERROR] {e}")

        # Phase 2: Fall back to smart local engine (no API needed)
        try:
            local = self._local_answer(question)
            if local:
                return local
        except Exception as e:
            print(f"[LOCAL ERROR] {e}")

        # Phase 3: Smart fallback — give useful info about the dataset
        col = self._find_column(question)
        if col and col in self.numeric_cols:
            df = self._run_sql(
                f'SELECT ROUND(AVG("{col}"), 2) as average, ROUND(SUM("{col}"), 2) as total, '
                f'ROUND(MIN("{col}"), 2) as min, ROUND(MAX("{col}"), 2) as max, '
                f'COUNT(*) as rows FROM data'
            )
            if df is not None and not df.empty:
                return (
                    f"Here's what I found about **`{col}`**:\n\n"
                    f"| Metric | Value |\n|--------|------:|\n"
                    f"| Average | {df['average'].iloc[0]:,} |\n"
                    f"| Total | {df['total'].iloc[0]:,} |\n"
                    f"| Min | {df['min'].iloc[0]:,} |\n"
                    f"| Max | {df['max'].iloc[0]:,} |\n"
                    f"| Rows | {df['rows'].iloc[0]:,} |"
                )
        elif col:
            df = self._run_sql(
                f'SELECT "{col}", COUNT(*) as count FROM data '
                f'GROUP BY "{col}" ORDER BY count DESC LIMIT 10'
            )
            if df is not None and not df.empty:
                return f"**Top values in `{col}`:**\n\n{self._format_table(df)}"

        # Final fallback
        col_preview = ", ".join([f"`{c}`" for c in self.columns[:15]])
        return (
            f"I have your dataset with **{self.row_count:,} rows** and **{len(self.columns)} columns**.\n\n"
            f"**Columns:** {col_preview}\n\n"
            f"Try questions like:\n"
            f"- \"What are the top 10 products by sales?\"\n"
            f"- \"What is the average profit?\"\n"
            f"- \"What if sales jump by 20%?\"\n"
            f"- \"Show me the distribution of category\"\n"
            f"- \"What are the unique values in region?\""
        )