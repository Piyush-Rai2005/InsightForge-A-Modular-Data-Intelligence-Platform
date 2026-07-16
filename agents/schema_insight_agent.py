"""
SchemaInsightAgent — Analyzes dataset schema to generate business-relevant
questions, runs SQL queries via DuckDB, and creates data-specific Plotly charts.

This replaces the old "run 3 template ML charts on everything" approach with
genuine exploratory data analysis tailored to the actual dataset.
"""

import os
import json
import logging
import pandas as pd
import numpy as np
from .base_agent import BaseAgent
from data_engine.rag_retriever import RAGRetriever

logger = logging.getLogger(__name__)


def _fmt(val, d=2):
    """Safely format a value as float. Returns 'N/A' for non-numeric."""
    try:
        return f"{float(val):.{d}f}"
    except (ValueError, TypeError):
        return str(val)

try:
    from groq import Groq
    _groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
except Exception:
    _groq_client = None


class SchemaInsightAgent(BaseAgent):
    """Generates business-relevant insights by analyzing the schema and data patterns."""

    def __init__(self):
        super().__init__("SchemaInsightAgent")

    def _ask_ai(self, prompt):
        if not _groq_client:
            return ""
        try:
            resp = _groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            self.log(f"AI call failed: {e}")
            return ""

    def _detect_column_semantics(self, df):
        """Classify each column by its semantic meaning."""
        semantics = {
            "date_cols": [],
            "monetary_cols": [],
            "rating_cols": [],
            "category_cols": [],
            "geo_cols": [],
            "id_cols": [],
            "numeric_cols": [],
            "text_cols": [],
        }

        money_keywords = ["price", "cost", "revenue", "amount", "payment", "freight", "value", "salary", "income", "profit", "fee", "total"]
        date_keywords = ["date", "time", "timestamp", "created", "updated", "delivered", "shipped", "approved", "purchased", "order_date"]
        rating_keywords = ["score", "rating", "review", "satisfaction", "stars", "grade"]
        geo_keywords = ["state", "city", "country", "region", "zip", "lat", "lng", "longitude", "latitude", "location", "address"]
        id_keywords = ["_id", "id_", "uuid", "key", "code", "identifier"]

        # ── Compute all nunique values in ONE vectorized pass ──────────────
        # Previously: df[col].nunique() called N times = N full column scans.
        # Now: one df.nunique() call scans the whole frame once.
        nuniques = df.nunique()
        n_rows = len(df)

        for col in df.columns:
            low = col.lower().strip()
            dtype = str(df[col].dtype)
            n_unique = int(nuniques[col])
            ratio = n_unique / n_rows if n_rows > 0 else 0

            # IDs: very high cardinality
            if ratio > 0.9 and n_unique > 100:
                semantics["id_cols"].append(col)
                continue
            if any(k in low for k in id_keywords) and n_unique > n_rows * 0.5:
                semantics["id_cols"].append(col)
                continue

            # Dates
            if any(k in low for k in date_keywords):
                semantics["date_cols"].append(col)
                continue
            if dtype == "object":
                try:
                    sample = df[col].dropna().head(20)
                    pd.to_datetime(sample, errors="raise")
                    semantics["date_cols"].append(col)
                    continue
                except Exception:
                    pass

            # Money
            if any(k in low for k in money_keywords) and pd.api.types.is_numeric_dtype(df[col]):
                semantics["monetary_cols"].append(col)
                continue

            # Ratings
            if any(k in low for k in rating_keywords) and pd.api.types.is_numeric_dtype(df[col]):
                semantics["rating_cols"].append(col)
                continue

            # Geo
            if any(k in low for k in geo_keywords):
                semantics["geo_cols"].append(col)
                continue

            # Categoricals (low-medium cardinality strings)
            if dtype == "object" and n_unique <= 50:
                semantics["category_cols"].append(col)
                continue

            # Numerics
            if pd.api.types.is_numeric_dtype(df[col]):
                semantics["numeric_cols"].append(col)
                continue

            # Remaining text
            if dtype == "object":
                semantics["text_cols"].append(col)

        return semantics

    def _generate_auto_charts(self, df, semantics):
        """Generate data-specific Plotly charts based on detected column semantics."""
        charts = []
        dark_layout = {
            "paper_bgcolor": "#0f1117",
            "plot_bgcolor": "#0f1117",
            "font": {"color": "#a0a0a0", "size": 11},
        }
        accent_colors = ["#63d396", "#4a9ed6", "#f59e0b", "#a78bfa", "#ff5f6d", "#06b6d4", "#ec4899", "#84cc16"]

        # ── 1. Time series: Date x Monetary/Numeric -> trend line ──────────
        for date_col in semantics["date_cols"][:2]:
            try:
                dates = pd.to_datetime(df[date_col], errors="coerce")
                if dates.notna().sum() < 10:
                    continue

                trend_col = None
                for mc in semantics["monetary_cols"][:1]:
                    trend_col = mc
                if not trend_col:
                    for nc in semantics["numeric_cols"][:1]:
                        trend_col = nc
                if not trend_col:
                    monthly = dates.dt.to_period("M").value_counts().sort_index()
                    charts.append({
                        "title": f"Volume Over Time ({date_col})",
                        "insight": f"Shows the count of records by month based on {date_col}.",
                        "plotly_spec": {
                            "data": [{
                                "type": "scatter",
                                "x": [str(p) for p in monthly.index],
                                "y": monthly.values.tolist(),
                                "mode": "lines+markers",
                                "line": {"color": "#63d396", "width": 2.5},
                                "marker": {"size": 5},
                                "hovertemplate": "%{x}: %{y:,.0f}<extra></extra>",
                            }],
                            "layout": {
                                **dark_layout,
                                "title": {"text": f"Volume Over Time", "font": {"color": "#f0f2f5", "size": 16}},
                                "xaxis": {"title": "Month", "gridcolor": "rgba(255,255,255,0.05)"},
                                "yaxis": {"title": "Count", "gridcolor": "rgba(255,255,255,0.05)"},
                                "margin": {"l": 60, "r": 30, "t": 50, "b": 60},
                            }
                        }
                    })
                    continue

                temp = df[[date_col, trend_col]].copy()
                temp[date_col] = dates
                temp = temp.dropna()
                temp["month"] = temp[date_col].dt.to_period("M")
                monthly = temp.groupby("month")[trend_col].agg(["sum", "mean", "count"])

                charts.append({
                    "title": f"{trend_col} Trend Over Time",
                    "insight": f"Monthly trend of {trend_col} by {date_col}. Sum and average shown.",
                    "plotly_spec": {
                        "data": [
                            {
                                "type": "bar",
                                "x": [str(p) for p in monthly.index],
                                "y": monthly["sum"].tolist(),
                                "name": "Total",
                                "marker": {"color": "rgba(99,211,150,0.4)"},
                                "hovertemplate": "%{x}<br>Total: %{y:,.2f}<extra></extra>",
                            },
                            {
                                "type": "scatter",
                                "x": [str(p) for p in monthly.index],
                                "y": monthly["mean"].tolist(),
                                "name": "Average",
                                "mode": "lines+markers",
                                "yaxis": "y2",
                                "line": {"color": "#63d396", "width": 2.5},
                                "marker": {"size": 5},
                                "hovertemplate": "%{x}<br>Avg: %{y:,.2f}<extra></extra>",
                            }
                        ],
                        "layout": {
                            **dark_layout,
                            "title": {"text": f"{trend_col} Trend Over Time", "font": {"color": "#f0f2f5", "size": 16}},
                            "xaxis": {"title": "Month", "gridcolor": "rgba(255,255,255,0.05)"},
                            "yaxis": {"title": "Total", "gridcolor": "rgba(255,255,255,0.05)"},
                            "yaxis2": {"title": "Average", "overlaying": "y", "side": "right", "gridcolor": "rgba(255,255,255,0.03)"},
                            "legend": {"font": {"color": "#a0a0a0"}, "x": 0, "y": 1.15, "orientation": "h"},
                            "margin": {"l": 60, "r": 60, "t": 50, "b": 60},
                        }
                    }
                })
            except Exception as e:
                self.log(f"Time series chart failed for {date_col}: {e}")

        # ── 2. Category breakdown ──────────────────────────────────────────
        for cat_col in semantics["category_cols"][:3]:
            try:
                counts = df[cat_col].value_counts().head(15)
                if len(counts) < 2:
                    continue

                charts.append({
                    "title": f"Distribution by {cat_col}",
                    "insight": f"Top {len(counts)} categories in {cat_col}. Most common: '{counts.index[0]}' ({counts.iloc[0]:,} records).",
                    "plotly_spec": {
                        "data": [{
                            "type": "bar",
                            "x": counts.values.tolist(),
                            "y": [str(v) for v in counts.index],
                            "orientation": "h",
                            "marker": {"color": accent_colors[:len(counts)] * 3},
                            "hovertemplate": "%{y}: %{x:,.0f}<extra></extra>",
                        }],
                        "layout": {
                            **dark_layout,
                            "title": {"text": f"Distribution by {cat_col}", "font": {"color": "#f0f2f5", "size": 16}},
                            "xaxis": {"title": "Count", "gridcolor": "rgba(255,255,255,0.05)"},
                            "yaxis": {"autorange": "reversed"},
                            "margin": {"l": 140, "r": 30, "t": 50, "b": 50},
                        }
                    }
                })

                value_col = None
                for mc in semantics["monetary_cols"][:1]:
                    value_col = mc
                if not value_col:
                    for rc in semantics["rating_cols"][:1]:
                        value_col = rc

                if value_col and value_col in df.columns:
                    avg_by_cat = df.groupby(cat_col)[value_col].mean().sort_values(ascending=False).head(15)
                    if len(avg_by_cat) >= 2:
                        charts.append({
                            "title": f"Average {value_col} by {cat_col}",
                            "insight": f"Highest average {value_col}: '{avg_by_cat.index[0]}' ({_fmt(avg_by_cat.iloc[0])}), lowest: '{avg_by_cat.index[-1]}' ({_fmt(avg_by_cat.iloc[-1])}).",
                            "plotly_spec": {
                                "data": [{
                                    "type": "bar",
                                    "x": [str(v) for v in avg_by_cat.index],
                                    "y": [round(v, 2) for v in avg_by_cat.values],
                                    "marker": {"color": "#4a9ed6", "line": {"color": "rgba(255,255,255,0.1)", "width": 1}},
                                    "text": [_fmt(v) for v in avg_by_cat.values],
                                    "textposition": "outside",
                                    "textfont": {"color": "#a0a0a0", "size": 10},
                                    "hovertemplate": "%{x}: %{y:.2f}<extra></extra>",
                                }],
                                "layout": {
                                    **dark_layout,
                                    "title": {"text": f"Avg {value_col} by {cat_col}", "font": {"color": "#f0f2f5", "size": 16}},
                                    "xaxis": {"tickangle": -45, "gridcolor": "rgba(255,255,255,0.05)"},
                                    "yaxis": {"title": f"Avg {value_col}", "gridcolor": "rgba(255,255,255,0.05)"},
                                    "margin": {"l": 60, "r": 30, "t": 50, "b": 80},
                                }
                            }
                        })
            except Exception as e:
                self.log(f"Category chart failed for {cat_col}: {e}")

        # ── 3. Rating/Score distribution ───────────────────────────────────
        for rat_col in semantics["rating_cols"][:2]:
            try:
                counts = df[rat_col].value_counts().sort_index()
                charts.append({
                    "title": f"{rat_col} Distribution",
                    "insight": f"Average {rat_col}: {_fmt(df[rat_col].mean())}. Most common: {counts.idxmax()} ({counts.max():,} records).",
                    "plotly_spec": {
                        "data": [{
                            "type": "bar",
                            "x": [str(v) for v in counts.index],
                            "y": counts.values.tolist(),
                            "marker": {
                                "color": [
                                    "#ff5f6d" if v <= 2 else "#f59e0b" if v == 3 else "#63d396"
                                    for v in counts.index
                                ] if all(isinstance(v, (int, float)) for v in counts.index) else accent_colors[:len(counts)]
                            },
                            "hovertemplate": "Score %{x}: %{y:,.0f}<extra></extra>",
                        }],
                        "layout": {
                            **dark_layout,
                            "title": {"text": f"{rat_col} Distribution", "font": {"color": "#f0f2f5", "size": 16}},
                            "xaxis": {"title": rat_col, "gridcolor": "rgba(255,255,255,0.05)"},
                            "yaxis": {"title": "Count", "gridcolor": "rgba(255,255,255,0.05)"},
                            "margin": {"l": 60, "r": 30, "t": 50, "b": 50},
                        }
                    }
                })
            except Exception as e:
                self.log(f"Rating chart failed for {rat_col}: {e}")

        # ── 4. Geographic breakdown ────────────────────────────────────────
        for geo_col in semantics["geo_cols"][:1]:
            try:
                if df[geo_col].nunique() > 50:
                    continue
                counts = df[geo_col].value_counts().head(20)
                if len(counts) < 2:
                    continue
                charts.append({
                    "title": f"Records by {geo_col}",
                    "insight": f"Top region: '{counts.index[0]}' with {counts.iloc[0]:,} records ({counts.iloc[0]/len(df)*100:.1f}% of total).",
                    "plotly_spec": {
                        "data": [{
                            "type": "bar",
                            "x": [str(v) for v in counts.index],
                            "y": counts.values.tolist(),
                            "marker": {"color": "#a78bfa", "line": {"color": "rgba(255,255,255,0.1)", "width": 1}},
                            "hovertemplate": "%{x}: %{y:,.0f}<extra></extra>",
                        }],
                        "layout": {
                            **dark_layout,
                            "title": {"text": f"Records by {geo_col}", "font": {"color": "#f0f2f5", "size": 16}},
                            "xaxis": {"tickangle": -45, "gridcolor": "rgba(255,255,255,0.05)"},
                            "yaxis": {"title": "Count", "gridcolor": "rgba(255,255,255,0.05)"},
                            "margin": {"l": 60, "r": 30, "t": 50, "b": 80},
                        }
                    }
                })
            except Exception as e:
                self.log(f"Geo chart failed for {geo_col}: {e}")

        # ── 5. Numeric distributions ──────────────────────────────────────
        for num_col in semantics["numeric_cols"][:2]:
            try:
                vals = df[num_col].dropna()
                if len(vals) < 10:
                    continue
                charts.append({
                    "title": f"{num_col} Distribution",
                    "insight": f"Range: {_fmt(vals.min())} to {_fmt(vals.max())}. Mean: {_fmt(vals.mean())}, Median: {_fmt(vals.median())}.",
                    "plotly_spec": {
                        "data": [{
                            "type": "histogram",
                            "x": vals.tolist(),
                            "nbinsx": 30,
                            "marker": {"color": "rgba(99,211,150,0.5)", "line": {"color": "#63d396", "width": 1}},
                            "hovertemplate": "Range: %{x}<br>Count: %{y}<extra></extra>",
                        }],
                        "layout": {
                            **dark_layout,
                            "title": {"text": f"{num_col} Distribution", "font": {"color": "#f0f2f5", "size": 16}},
                            "xaxis": {"title": num_col, "gridcolor": "rgba(255,255,255,0.05)"},
                            "yaxis": {"title": "Count", "gridcolor": "rgba(255,255,255,0.05)"},
                            "margin": {"l": 60, "r": 30, "t": 50, "b": 50},
                        }
                    }
                })
            except Exception as e:
                self.log(f"Histogram failed for {num_col}: {e}")

        # ── 6. Scatter: two numerics ───────────────────────────────────────
        num_pair = semantics["monetary_cols"] + semantics["numeric_cols"]
        if len(num_pair) >= 2:
            try:
                col_a, col_b = num_pair[0], num_pair[1]
                sample = df[[col_a, col_b]].dropna().sample(min(2000, len(df)), random_state=42)
                corr = sample[col_a].corr(sample[col_b])
                charts.append({
                    "title": f"{col_a} vs {col_b}",
                    "insight": f"Correlation: {corr:.3f}. {'Strong' if abs(corr) > 0.5 else 'Moderate' if abs(corr) > 0.3 else 'Weak'} relationship.",
                    "plotly_spec": {
                        "data": [{
                            "type": "scattergl",
                            "x": sample[col_a].tolist(),
                            "y": sample[col_b].tolist(),
                            "mode": "markers",
                            "marker": {"color": "#63d396", "size": 4, "opacity": 0.5},
                            "hovertemplate": f"{col_a}: %{{x:.2f}}<br>{col_b}: %{{y:.2f}}<extra></extra>",
                        }],
                        "layout": {
                            **dark_layout,
                            "title": {"text": f"{col_a} vs {col_b} (r={corr:.3f})", "font": {"color": "#f0f2f5", "size": 16}},
                            "xaxis": {"title": col_a, "gridcolor": "rgba(255,255,255,0.05)"},
                            "yaxis": {"title": col_b, "gridcolor": "rgba(255,255,255,0.05)"},
                            "margin": {"l": 60, "r": 30, "t": 50, "b": 50},
                        }
                    }
                })
            except Exception as e:
                self.log(f"Scatter chart failed: {e}")

        return charts

    # Max columns to analyse — beyond this we sample representatively
    # to keep Groq prompts under token limits and chart gen fast.
    MAX_ANALYSIS_COLS = 300

    def run(self, context):
        df = context.get("raw_data", context.get("data"))
        if df is None:
            return context

        self.log("Analyzing schema for business-relevant insights...")

        # ── Wide-dataset guard ───────────────────────────────────────────────
        total_cols = len(df.columns)
        if total_cols > self.MAX_ANALYSIS_COLS:
            obj_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
            num_cols = df.select_dtypes(include="number").columns.tolist()
            remaining = self.MAX_ANALYSIS_COLS - len(obj_cols)
            top_num = (
                df[num_cols].var().nlargest(max(remaining, 0)).index.tolist()
                if num_cols and remaining > 0 else []
            )
            keep = (obj_cols + top_num)[:self.MAX_ANALYSIS_COLS]
            df = df[keep]
            self.log(
                f"Wide dataset ({total_cols} cols) — capped analysis to "
                f"{len(keep)} most informative cols "
                f"({len(obj_cols)} categorical + {len(top_num)} numeric by variance)"
            )

        # ── Build RAGRetriever (threshold-aware: RAG only when > 20 columns) ────
        retriever = RAGRetriever(df)
        context["rag_retriever"] = retriever  # reused by TargetAgent + InsightAgent
        if retriever.rag_active:
            self.log(f"RAG activated — {len(df.columns)} columns indexed for focused LLM prompts")
        else:
            self.log(f"RAG skipped — {len(df.columns)} columns (≤ 20), using full schema directly")

        semantics = self._detect_column_semantics(df)
        context["column_semantics"] = semantics

        self.log(f"Detected: {len(semantics['date_cols'])} dates, {len(semantics['monetary_cols'])} monetary, "
                 f"{len(semantics['rating_cols'])} ratings, {len(semantics['category_cols'])} categories, "
                 f"{len(semantics['geo_cols'])} geographic, {len(semantics['id_cols'])} IDs")

        auto_charts = self._generate_auto_charts(df, semantics)
        context["auto_charts"] = auto_charts
        self.log(f"Generated {len(auto_charts)} data-specific visualizations")

        # schema_text for Groq: RAG retrieves the most semantically rich columns;
        # for narrow datasets the retriever returns all columns anyway.
        schema_text = retriever.get_schema(
            "business analysis overview key metrics important columns schema", k=20
        )
        sample_text = df.head(3).to_string(max_cols=15)

        prompt = f"""You are a senior business analyst. Given this dataset schema:
{schema_text}

Sample rows:
{sample_text}

Column semantic analysis:
- Date columns: {semantics['date_cols']}
- Monetary columns: {semantics['monetary_cols']}
- Rating/Score columns: {semantics['rating_cols']}
- Category columns: {semantics['category_cols']}
- Geographic columns: {semantics['geo_cols']}
- ID columns (not useful for analysis): {semantics['id_cols']}

Generate EXACTLY 5 high-value business questions that a company would actually want answered from this data.
Each question should be actionable and specific to THIS dataset (not generic ML questions).
Format each on its own line, numbered 1-5. No extra text."""

        questions = self._ask_ai(prompt)
        context["business_questions"] = questions

        stats = []
        for mc in semantics["monetary_cols"][:3]:
            vals_mc = pd.to_numeric(df[mc], errors='coerce')
            stats.append(f"{mc}: total={_fmt(vals_mc.sum())}, avg={_fmt(vals_mc.mean())}, median={_fmt(vals_mc.median())}")
        for rc in semantics["rating_cols"][:2]:
            vals_rc = pd.to_numeric(df[rc], errors='coerce')
            stats.append(f"{rc}: avg={_fmt(vals_rc.mean())}, min={_fmt(vals_rc.min())}, max={_fmt(vals_rc.max())}")
        for dc in semantics["date_cols"][:2]:
            try:
                dates = pd.to_datetime(df[dc], errors="coerce").dropna()
                stats.append(f"{dc}: from {dates.min().date()} to {dates.max().date()} ({(dates.max()-dates.min()).days} days span)")
            except Exception:
                pass

        context["key_statistics"] = stats

        return context
