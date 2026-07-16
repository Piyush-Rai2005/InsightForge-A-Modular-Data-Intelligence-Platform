from .base_agent import BaseAgent
import os
import pandas as pd
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

class TargetAgent(BaseAgent):
    """
    Smart target selection — only picks a target if it's genuinely meaningful
    for classification. Skips ML entirely for datasets that don't have a
    natural prediction target (e.g., customer lists, transaction logs).
    """

    # Columns that are good ML targets
    TARGET_KEYWORDS = ["target", "label", "class", "churn", "default", "outcome",
                       "fraud", "spam", "sentiment", "survived", "approved",
                       "cancelled", "returned", "delayed", "late", "converted"]

    # Columns that are NEVER good ML targets
    ANTI_KEYWORDS = ["_id", "uuid", "key", "name", "address", "phone",
                     "email", "description", "comment", "url", "path"]

    def __init__(self):
        super().__init__("TargetAgent")
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    def _is_meaningful_target(self, df, col):
        """Check if a column is a meaningful ML target (classification or regression)."""
        nunique = df[col].nunique()
        ratio = nunique / len(df) if len(df) > 0 else 1

        # Too many unique values relative to rows → likely an ID column
        if ratio > 0.8:
            return False
        if nunique < 2:
            return False

        col_lower = col.lower()
        if any(k in col_lower for k in self.ANTI_KEYWORDS):
            return False

        return True

    def _detect_leakage_risk(self, df, target_col):
        """Check if any feature trivially encodes the target (data leakage)."""
        warnings = []
        target_vals = df[target_col]

        for col in df.columns:
            if col == target_col:
                continue
            try:
                if pd.api.types.is_numeric_dtype(df[col]):
                    corr = abs(df[col].corr(target_vals.astype(float)))
                    if corr > 0.95:
                        warnings.append(f"'{col}' has {corr:.3f} correlation with target -- likely data leakage")
            except Exception:
                pass

        return warnings

    def run(self, context):
        df = context["clean_data"]
        self.log("Evaluating whether ML classification is appropriate...")

        target_col = None

        # First check for keyword matches
        for col in df.columns:
            low = col.lower()
            if any(k in low for k in self.TARGET_KEYWORDS) and self._is_meaningful_target(df, col):
                target_col = col
                self.log(f"Found keyword-matched target: {col}")
                break

        # Ask AI only if no keyword match
        if target_col is None:
            try:
                # Use the RAGRetriever built by SchemaInsightAgent if available.
                # For narrow datasets (≤ 20 cols) it returns all columns;
                # for wide datasets it surfaces the most "target-like" columns,
                # preventing the old [:15] hard cut from missing churn/fraud cols at index 20+.
                retriever = context.get("rag_retriever")
                if retriever and retriever.rag_active:
                    schema_info = retriever.get_schema(
                        "prediction target outcome binary classification label churn fraud", k=20
                    )
                else:
                    schema_info = "\n".join([f"{c}: {str(df[c].dtype)}, {df[c].nunique()} unique" for c in df.columns])
                sample_data = df.head(3).to_string(max_cols=12)

                prompt = f"""You are evaluating a dataset for machine learning.
Columns:
{schema_info}

Sample:
{sample_data}

Is there a meaningful prediction target in this data? A good target should be:
- A business outcome (churn, fraud, success, delay, rating, etc.)
- NOT an ID, name, location, or categorical attribute
- Binary or low-cardinality (2-10 classes)

If YES, reply with ONLY the exact column name.
If NO meaningful target exists, reply with exactly: SKIP_ML"""

                resp = self.client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    timeout=30,  # never hang longer than 30 s
                )
                answer = resp.choices[0].message.content.strip().replace('"', '').replace("'", '').strip()

                if answer == "SKIP_ML" or answer not in df.columns:
                    self.log("AI determined: no meaningful ML target in this dataset")
                    context["target_column"] = None
                    context["skip_ml"] = True
                    context["skip_ml_reason"] = "No meaningful prediction target detected. This dataset is better suited for exploratory analysis and business intelligence queries."
                    return context

                if self._is_meaningful_target(df, answer):
                    target_col = answer
                    self.log(f"AI selected target: {answer}")
                else:
                    self.log(f"AI suggested '{answer}' but it doesn't meet quality checks -- skipping ML")
                    context["target_column"] = None
                    context["skip_ml"] = True
                    context["skip_ml_reason"] = f"AI suggested '{answer}' as target but it has too many unique values or is an identifier."
                    return context

            except Exception as e:
                self.log(f"AI target inference failed: {e}")

        # Final fallback -- don't force ML
        if target_col is None:
            self.log("No suitable ML target found -- running in EDA-only mode")
            context["target_column"] = None
            context["skip_ml"] = True
            context["skip_ml_reason"] = "No suitable classification target found. Showing exploratory data analysis instead."
            return context

        # Check for data leakage
        leakage_warnings = self._detect_leakage_risk(df, target_col)
        if leakage_warnings:
            context["leakage_warnings"] = leakage_warnings
            self.log(f"Data leakage detected: {leakage_warnings}")

        # ── Determine task type: classification vs regression ──────────────
        target_dtype = df[target_col].dtype
        nunique = df[target_col].nunique()

        if pd.api.types.is_float_dtype(target_dtype) and nunique > 20:
            task_type = "regression"
        elif pd.api.types.is_integer_dtype(target_dtype) and nunique > 20:
            task_type = "regression"
        elif nunique <= 20:
            task_type = "classification"
        else:
            task_type = "regression"

        self.log(f"Task type: {task_type} (target='{target_col}', dtype={target_dtype}, nunique={nunique})")

        context["target_column"] = target_col
        context["task_type"] = task_type
        context["skip_ml"] = False
        return context