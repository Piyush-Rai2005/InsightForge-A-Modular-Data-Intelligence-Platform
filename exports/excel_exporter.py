"""
Generate a multi-sheet Excel workbook from analysis results.
"""
import io
import pandas as pd


def generate_excel(report: dict) -> bytes:
    buf = io.BytesIO()

    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        # ── Overview sheet ──────────────────────────────────────────────────
        overview = report.get("dataset_overview", {})
        if overview:
            desc_rows = overview.get("desc_rows", [])
            if desc_rows:
                pd.DataFrame(desc_rows).to_excel(writer, sheet_name="Overview", index=False)

        # ── Model Comparison sheet ──────────────────────────────────────────
        models = report.get("model_comparison", [])
        if models:
            pd.DataFrame(models).to_excel(writer, sheet_name="Models", index=False)

        # ── Missing Values sheet ────────────────────────────────────────────
        missing = report.get("missing_values", [])
        if missing:
            pd.DataFrame(missing).to_excel(writer, sheet_name="Missing Values", index=False)

        # ── Recommendations sheet ───────────────────────────────────────────
        recs = report.get("recommendations", [])
        if recs:
            pd.DataFrame({"Recommendation": recs}).to_excel(writer, sheet_name="Recommendations", index=False)

        # ── Key Statistics sheet ────────────────────────────────────────────
        stats = report.get("key_statistics", [])
        if stats:
            pd.DataFrame({"Statistic": stats}).to_excel(writer, sheet_name="Key Statistics", index=False)

        # ── Executive Summary sheet ─────────────────────────────────────────
        exec_sum = report.get("exec_summary", "")
        if exec_sum:
            pd.DataFrame({"Executive Summary": [exec_sum]}).to_excel(writer, sheet_name="Summary", index=False)

    return buf.getvalue()
