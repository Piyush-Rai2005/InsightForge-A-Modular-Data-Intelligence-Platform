from .base_agent import BaseAgent
import os
from groq import Groq




class TargetAgent(BaseAgent):
    """Uses Groq LLM to infer the most likely target column, with fallbacks."""

    def __init__(self):
        super().__init__("TargetAgent")
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    def _ask_ai_for_target(self, df):
        schema_lines = [f"{c}: {str(df[c].dtype)}" for c in df.columns]
        schema = "\n".join(schema_lines)

        prompt = (
            "You are configuring an AutoML pipeline.\\n"
            "Here are the dataset columns with dtypes:\\n"
            f"{schema}\\n\\n"
            "Which single column is most likely the prediction target/label?\\n"
            "Reply with only the exact column name."
        )

        resp = self.client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
        )
        answer = resp.choices[0].message.content.strip()
        return answer.replace('"', "").replace("'", "").strip()

    def run(self, context):
        df = context["clean_data"]
        self.log("🤖 AI inferring target column...")

        target_col = None
        try:
            ai_guess = self._ask_ai_for_target(df)
            if ai_guess in df.columns:
                target_col = ai_guess
                self.log(f"AI selected target = {ai_guess}")
        except Exception as e:
            self.log(f"AI target inference failed: {e}")

        if target_col is None:
            priority_keywords = ["target", "label", "class", "readmitted", "outcome", "churn", "default", "y"]
            for col in df.columns:
                low = col.lower()
                if any(k in low for k in priority_keywords):
                    target_col = col
                    self.log(f"Fallback target detected = {col}")
                    break

        if target_col is None:
            target_col = df.columns[-1]
            self.log(f"Using last column as target = {target_col}")

        context["target_column"] = target_col
        return context