from .base_agent import BaseAgent
import os
import pandas as pd
from groq import Groq

class InsightAgent(BaseAgent):
    """Generates narrative business intelligence -- now schema-aware.
    When ML is skipped, generates pure EDA insights instead of model-centric narratives."""

    def __init__(self):
        super().__init__("InsightAgent")
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    def ask_ai(self, prompt):
        try:
            resp = self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                timeout=30,  # never hang longer than 30 s
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            self.log(f"AI generation failed: {e}")
            return "Insight unavailable."

    def run(self, context):
        df = context.get("raw_data", context.get("data"))
        if df is None:
            return context

        n_rows, n_cols = df.shape
        # Reuse the RAGRetriever created by SchemaInsightAgent (step 3).
        # RAG ON  → retrieves columns most relevant to "key metrics / business outcome"
        # RAG OFF → returns all columns (dataset ≤ 20 cols, no overhead)
        retriever = context.get("rag_retriever")
        if retriever and retriever.rag_active:
            schema = retriever.get_schema(
                "key metrics business outcome important factors performance indicators", k=20
            )
        else:
            schema = "\n".join([f"- {c}: {str(df[c].dtype)}" for c in df.columns])
        semantics = context.get("column_semantics", {})
        key_stats = context.get("key_statistics", [])
        business_questions = context.get("business_questions", "")
        skip_ml = context.get("skip_ml", False)
        leakage_warnings = context.get("leakage_warnings", [])

        stats_text = "\n".join(key_stats) if key_stats else "No key statistics available."

        if skip_ml:
            # ── EDA-ONLY MODE: Pure business intelligence ─────────────────
            prompt = f"""You are a senior business analyst presenting findings to executives.
Dataset: {n_rows:,} rows, {n_cols} columns.
Schema:
{schema}

Key Statistics:
{stats_text}

Business Questions Identified:
{business_questions}

Column Types Detected:
- Date columns: {semantics.get('date_cols', [])}
- Monetary columns: {semantics.get('monetary_cols', [])}
- Rating columns: {semantics.get('rating_cols', [])}
- Category columns: {semantics.get('category_cols', [])}
- Geographic columns: {semantics.get('geo_cols', [])}

Write EXACTLY 3 sections. Do NOT wrap text in ** or any markdown bold formatting. Use plain text only.

<EXEC_SUM>
(Write 3 high-impact bullet points summarizing the most important business insights from this data.
Focus on PATTERNS, TRENDS, and ACTIONABLE FINDINGS -- not ML model results. Do NOT use ** bold markers.)

<RECO>
(Provide 5 specific, actionable business recommendations based on the data patterns.
Each recommendation should be something a business team can actually do. Do NOT use ** bold markers.)

<DISCOVERY>
(Identify 2 surprising or hidden insights from the data statistics that could represent
business opportunities or risks. Be specific with numbers. Do NOT use ** bold markers.)
"""
        else:
            # ── ML MODE: Include model results ────────────────────────────
            scores = context.get("model_scores", {})
            best_name = context.get("best_model_name", "N/A")
            best_acc = context.get("best_model_accuracy", 0)
            target = context.get("target_column", "(unknown)")
            scores_text = ", ".join([f"{m}: {round(a, 3)}" for m, a in scores.items()]) if scores else "N/A"

            leakage_note = ""
            if leakage_warnings:
                leakage_note = f"\n\nDATA LEAKAGE WARNING: {' '.join(leakage_warnings)}\nInclude a warning about this in the summary."

            prompt = f"""You are a senior data scientist presenting findings to executives.
Dataset: {n_rows:,} rows, {n_cols} columns. Target: '{target}'.
Models: {scores_text} | Best: {best_name} ({best_acc:.3f})
{leakage_note}

Key Statistics:
{stats_text}

Write EXACTLY 3 sections. Do NOT wrap text in ** or any markdown bold formatting. Use plain text only.

<EXEC_SUM>
(Write 3 bullet points: data story, model performance, and key business implication. Do NOT use ** bold markers.
{'If accuracy is above 97%, WARN about possible data leakage -- do NOT celebrate perfect scores.' if best_acc > 0.97 else ''})

<RECO>
(Provide 5 actionable business recommendations. Do NOT use ** bold markers.)

<DISCOVERY>
(2 surprising insights from the data statistics. Do NOT use ** bold markers.)
"""

        text = self.ask_ai(prompt)

        def extract(tag, blob):
            if f"<{tag}>" not in blob:
                if tag in blob:
                    raw = blob.split(tag)[1].split("<")[0].replace(">", "").strip()
                else:
                    return ""
            else:
                raw = blob.split(f"<{tag}>")[1].split("<")[0].strip()
            # Clean up orphaned ** bold markers that the AI sometimes wraps around output
            import re
            raw = re.sub(r'^\s*\*\*\s*$', '', raw, flags=re.MULTILINE)  # remove lines that are just **
            raw = raw.strip()
            return raw

        context["exec_summary"] = extract("EXEC_SUM", text)
        context["recommendations_text"] = extract("RECO", text)
        context["discovery_insight"] = extract("DISCOVERY", text)

        # ── Natural language insights for auto-charts ──────────────────────
        auto_charts = context.get("auto_charts", [])
        if auto_charts:
            chart_summaries = "\n".join([f"- {c['title']}: {c.get('insight', '')}" for c in auto_charts[:6]])
            vis_prompt = f"""As a business analyst, provide a 2-sentence narrative summary
connecting these visualization findings into a coherent business story:
{chart_summaries}
"""
            context["visual_narrative"] = self.ask_ai(vis_prompt)

        # ── ML-specific insights (only if ML ran) ─────────────────────────
        if not skip_ml:
            corr_info = context.get("corr_info", {})
            if corr_info:
                context["corr_insight"] = self.ask_ai(
                    f"Explain these feature correlations in 2 business-friendly sentences: {corr_info}"
                )

            target_info = context.get("target_info", {})
            if target_info:
                context["target_insight"] = self.ask_ai(
                    f"Explain this target distribution in 2 sentences for a non-technical manager: {target_info}"
                )

            cm_info = context.get("conf_matrix_info", {})
            if cm_info:
                context["cm_insight"] = self.ask_ai(
                    f"Explain this confusion matrix in one simple sentence: {cm_info}"
                )

            auc_val = context.get("auc_score", "N/A")
            if auc_val != "N/A":
                context["roc_insight"] = self.ask_ai(
                    f"Explain what an AUC of {auc_val} means for model trustworthiness in one sentence."
                )

        return context