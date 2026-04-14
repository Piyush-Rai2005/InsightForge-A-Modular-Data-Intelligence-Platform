from .base_agent import BaseAgent
import os
import pandas as pd
from groq import Groq

class InsightAgent(BaseAgent):
    """Generates narrative business intelligence, actionable visual explanations, and discovers hidden insights."""

    def __init__(self):
        super().__init__("InsightAgent")
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    def ask_ai(self, prompt):
        try:
            resp = self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            self.log(f"AI generation failed: {e}")
            return "Insight unavailable."

    def run(self, context):
        df = context["raw_data"]
        target = context.get("target_column", "(unknown)")

        scores = context.get("model_scores") or {}
        best_name = context.get("best_model_name", "N/A")
        best_acc = context.get("best_model_accuracy", 0)

        n_rows, n_cols = df.shape
        schema = "\n".join([f"- {c}: {str(df[c].dtype)}" for c in df.columns[:15]])

        # -------------------------------------------------------------------
        # 1. EXECUTIVE SUMMARIES (3-Bullet TL;DR) & RECOMMENDATIONS
        # -------------------------------------------------------------------
        if scores:
            scores_text = ", ".join([f"{m}: {round(a, 3)}" for m, a in scores.items()])

            prompt = f"""
You are an expert Data Strategist analyzing a dataset to present to executives.
Dataset: {n_rows} rows, {n_cols} columns. Target variable: '{target}'.
Schema:
{schema}
Models: {scores_text} | Best: {best_name} ({best_acc:.3f})

Write EXACTLY 3 sections with these exact markers. Do NOT add markdown outside the markers:

<EXEC_SUM>
(Write exactly 3 high-impact bullet points summarizing the overarching data story and model success.)

<MODEL_STORY>
(Write a short 2-sentence narrative explaining how well we can predict '{target}' and what that means for the business.)

<RECO>
(Provide 3 actionable business steps based on these predictive capabilities.)
"""
            text = self.ask_ai(prompt)

            def extract(tag, blob):
                if f"<{tag}>" not in blob:
                    # Fallback extraction if LLM formatting is slightly off
                    if tag in blob:
                         return blob.split(tag)[1].split("<")[0].replace(">", "").strip()
                    return ""
                return blob.split(f"<{tag}>")[1].split("<")[0].strip()

            exec_sum = extract("EXEC_SUM", text)
            model_story = extract("MODEL_STORY", text)
            reco = extract("RECO", text)

        else:
            exec_sum = "• Dataset lacks target diversity.\n• Predictive modeling suspended.\n• Focus on data collection."
            model_story = "Not enough label diversity for model training."
            reco = "• Collect samples representing additional target classes.\n• Improve dataset balance."

        context["exec_summary"] = exec_sum
        context["model_story"] = model_story
        context["recommendations_text"] = reco

        # -------------------------------------------------------------------
        # 2. NATURAL LANGUAGE EXPLANATIONS (Actionable Visual Insights)
        # -------------------------------------------------------------------
        # Instead of just reading numbers, the LLM translates charts into business action.

        corr_info = context.get("corr_info", {})
        corr_prompt = f"""
Act as a business analyst. Explain these top feature correlations in natural language.
Correlations: {corr_info}
Do not just list the numbers. Write 2 sentences explaining WHAT this means for the business and ONE action they should take based on this link.
"""
        context["corr_insight"] = self.ask_ai(corr_prompt)

        target_info = context.get("target_info", {})
        tgt_prompt = f"""
Act as a business analyst. Look at this target class distribution: {target_info}.
Write 2 sentences explaining if the data is skewed or balanced, and how this impacts the company's real-world strategy regarding this target.
"""
        context["target_insight"] = self.ask_ai(tgt_prompt)

        # -------------------------------------------------------------------
        # 3. INSIGHT DISCOVERY (Unexpected Patterns & "Browsing")
        # -------------------------------------------------------------------
        self.log("Discovering hidden insights...")
        
        # To let the LLM "browse", we give it summary stats and correlations
        # We sample a few rows to give it a feel for actual values without blowing up context size
        numeric_df = df.select_dtypes(include=['number'])
        if not numeric_df.empty:
            summary_stats = numeric_df.describe().loc[['mean', 'min', 'max']].to_dict()
            sample_data = df.sample(min(3, len(df))).to_dict(orient="records")
            
            discovery_prompt = f"""
You are an AI Data Detective looking for unexpected or highly valuable business insights.
Target Variable: {target}
Summary Statistics (Mean, Min, Max): {summary_stats}
Sample Data Rows: {sample_data}

Browse this statistical summary. Identify 2 specific, potentially surprising, or highly actionable insights. 
Write them as compelling statements (e.g., "Interestingly, while average X is [val], the maximum spikes to [val], suggesting an opportunity to..."). 
Keep it under 4 sentences total. Be creative but grounded in the provided numbers.
"""
            context["discovery_insight"] = self.ask_ai(discovery_prompt)
        else:
            context["discovery_insight"] = "No numeric data available for deep statistical discovery."


        # Keep standard one-liners for technical metrics
        cm_info = context.get("conf_matrix_info", {})
        context["cm_insight"] = self.ask_ai(f"Explain this confusion matrix in one simple sentence for a non-technical manager: {cm_info}")

        auc_val = context.get("auc_score", "N/A")
        context["roc_insight"] = self.ask_ai(f"Explain in one sentence what an AUC of {auc_val} means for our ability to trust this model.")

        return context