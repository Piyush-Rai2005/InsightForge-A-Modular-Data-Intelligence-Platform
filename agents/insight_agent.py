from .base_agent import BaseAgent
import os
from groq import Groq



class InsightAgent(BaseAgent):
    """Generates all narrative insights using Groq AI, including visual explanations."""

    def __init__(self):
        super().__init__("InsightAgent")
        self.client =Groq(api_key=os.getenv("GROQ_API_KEY"))

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
        # EXECUTIVE SUMMARY + MODEL STORY + RECOMMENDATIONS
        # -------------------------------------------------------------------
        if scores:
            scores_text = ", ".join([f"{m}: {round(a, 3)}" for m, a in scores.items()])

            prompt = f"""
You are a consulting-grade narrative engine. Tone: confident data storyteller (Tone B).

Dataset: {n_rows} rows, {n_cols} columns
Target: {target}

Schema sample:
{schema}

Model accuracies:
{scores_text}

Best model: {best_name} ({best_acc:.3f})

Write EXACTLY 3 sections with these markers:

<EXEC_SUM>
(4–6 lines)

<MODEL_STORY>
(3–4 bullets, one sentence each)

<RECO>
(3–5 business recommendations)

DO NOT add anything outside markers.
"""

            text = self.ask_ai(prompt)

            def extract(tag, blob):
                if tag not in blob:
                    return ""
                return blob.split(tag)[1].split("<")[0].strip()

            exec_sum = extract("EXEC_SUM>", text)
            model_story = extract("MODEL_STORY>", text)
            reco = extract("RECO>", text)

        else:
            exec_sum = (
                "The dataset contains only one target class, so modeling was skipped. "
                "However, structural patterns, quality diagnostics, and feature behavior "
                "still provide useful ground for future predictive work."
            )
            model_story = "• Not enough label diversity for model training."
            reco = (
                "• Collect samples representing additional target classes.\n"
                "• Improve dataset balance before training models.\n"
                "• Re-run the system once diversity is adequate."
            )

        context["exec_summary"] = exec_sum
        context["model_story"] = model_story
        context["recommendations_text"] = reco

        # -------------------------------------------------------------------
        # VISUAL INSIGHT ONE-LINERS
        # -------------------------------------------------------------------

        # 1️⃣ Correlation Heatmap Insight
        corr_info = context.get("corr_info", {})
        corr_prompt = f"""
Generate a one-line insight for a correlation heatmap.

Top correlated pairs:
{corr_info}

Tone: Clean consulting tone.
"""
        context["corr_insight"] = self.ask_ai(corr_prompt)

        # 2️⃣ Target Distribution Insight
        target_info = context.get("target_info", {})
        tgt_prompt = f"""
Generate a one-line insight describing target distribution:

Class counts:
{target_info}

Tone: Concise, business-friendly.
"""
        context["target_insight"] = self.ask_ai(tgt_prompt)

        # 3️⃣ Confusion Matrix Insight
        cm_info = context.get("conf_matrix_info", {})
        cm_prompt = f"""
Explain confusion matrix in one sentence.

Values:
{cm_info}

Tone: Clear and non-technical.
"""
        context["cm_insight"] = self.ask_ai(cm_prompt)

        # 4️⃣ ROC Curve Insight
        auc_val = context.get("auc_score", None)
        roc_prompt = f"""
Write one line explaining the ROC curve significance.

AUC value: {auc_val}

Tone: simple, insightful.
"""
        context["roc_insight"] = self.ask_ai(roc_prompt)

        # 5️⃣ Model Comparison Chart Insight
        comp_prompt = f"""
Models and accuracies:
{scores}

Write one sentence summarizing which model performs best and what that implies.
"""
        context["model_compare_insight"] = self.ask_ai(comp_prompt)

        return context