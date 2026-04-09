from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import pandas as pd
import polars as pl
import sqlite3
import xml.etree.ElementTree as ET
import yaml
import zipfile
import io
import tempfile
import os
import base64

from core.coordinator import PipelineCoordinator

app = FastAPI(title="InsightForge API")

_last_result : dict= {}

# Allow requests from the React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173","https://insightforge-data.vercel.app"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)

def parse_upload(file: UploadFile) -> pl.DataFrame:
    name = file.filename.lower()
    contents = file.file.read()
    buf = io.BytesIO(contents)

    # ---------------- CSV ----------------
    if name.endswith(".csv"):
        return pl.read_csv(buf)

    # ---------------- Excel ----------------
    elif name.endswith(".xlsx"):
        return pl.from_pandas(pd.read_excel(buf))

    # ---------------- JSON ----------------
    elif name.endswith(".json"):
        return pl.read_json(buf)

    # ---------------- SQLite ----------------
    elif name.endswith((".sqlite", ".sql")):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".sqlite") as tmp:
            tmp.write(contents)
            tmp_path = tmp.name

        conn = sqlite3.connect(tmp_path)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()

        if not tables:
            os.unlink(tmp_path)
            raise HTTPException(status_code=400, detail="No tables found in SQLite file.")

        pdf = pd.read_sql(f"SELECT * FROM {tables[0][0]}", conn)

        conn.close()
        os.unlink(tmp_path)
        return pl.from_pandas(pdf)

    # ---------------- XML ----------------
    elif name.endswith(".xml"):
        tree = ET.parse(buf)
        root = tree.getroot()
        rows = [{elem.tag: elem.text for elem in child} for child in root]
        return pl.from_pandas(pd.DataFrame(rows))

    # ---------------- YAML ----------------
    elif name.endswith((".yaml", ".yml")):
        data = yaml.safe_load(buf)
        return pl.from_pandas(pd.DataFrame(data))

    # ---------------- TXT / TSV ----------------
    elif name.endswith((".txt", ".log", ".tsv", ".dat")):
        return pl.read_csv(buf, separator=None)

    # ---------------- Parquet ----------------
    elif name.endswith(".parquet"):
        return pl.read_parquet(buf)

    # ---------------- ZIP ----------------
    elif name.endswith(".zip"):
        with zipfile.ZipFile(buf) as z:
            for f in z.namelist():
                with z.open(f) as inner:
                    inner_buf = io.BytesIO(inner.read())

                    if f.endswith(".csv"):
                        return pl.read_csv(inner_buf)
                    elif f.endswith(".xlsx"):
                        return pl.from_pandas(pd.read_excel(inner_buf))

        raise HTTPException(status_code=400, detail="No supported file found inside ZIP.")

    else:
        raise HTTPException(status_code=400, detail=f"Unsupported file format: {name}")
    
def _encode_image(path: str | None) -> str | None:
    """Read a chart image from disk and return a base64 data-URI."""
    if not path or not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    ext = path.rsplit(".", 1)[-1].lower()
    mime = "image/png" if ext == "png" else f"image/{ext}"
    return f"data:{mime};base64,{data}"

def _build_report_payload(result: dict) -> dict:
    """
    Convert the raw pipeline context dict into a JSON-serialisable
    payload the frontend can render directly.
    """
    df: pd.DataFrame | None = result.get("raw_data")
 
    # ── Dataset overview ──────────────────────────────────────────────────
    dataset_overview = None
    missing_values   = []
 
    if df is not None:
        rows, cols = df.shape
 
        # describe — up to first 8 numeric columns so the table stays readable
        desc       = df.describe().transpose().iloc[:8]
        desc_cols  = list(desc.columns)          # e.g. count, mean, std …
        desc_rows  = []
        for feat, row in desc.iterrows():
            desc_rows.append({"feature": feat, **{c: round(float(row[c]), 3) for c in desc_cols}})
 
        # missing
        missing_series = df.isna().sum()
        missing_values = [
            {"column": col, "missing": int(cnt)}
            for col, cnt in missing_series[missing_series > 0].items()
        ]
 
        dataset_overview = {
            "rows":       rows,
            "columns":    cols,
            "desc_cols":  desc_cols,
            "desc_rows":  desc_rows,
        }
 
    # ── Model scores ──────────────────────────────────────────────────────
    scores    = result.get("model_scores") or {}
    model_comparison = [
        {"model": name, "accuracy": round(float(acc), 4)}
        for name, acc in scores.items()
    ]
 
    # ── Visuals (base64) ─────────────────────────────────────────────────
    visuals = []
    for key, label in [
        ("corr_plot",   "Correlation Heatmap"),
        ("target_plot", "Target Distribution"),
        ("conf_matrix", "Confusion Matrix"),
        ("roc_curve",   "ROC Curve"),
        ("model_bar",   "Model Comparison Chart"),
    ]:
        img_b64 = _encode_image(result.get(key))
        if img_b64:
            visuals.append({
                "title":   label,
                "image":   img_b64,
                "insight": result.get(
                    {"corr_plot": "corr_insight", "target_plot": "target_insight",
                     "conf_matrix": "cm_insight", "roc_curve": "roc_insight"}.get(key, ""),
                    ""
                ),
            })
 
    return {
        "exec_summary":       result.get("exec_summary", ""),
        "recommendations":    [
            line.strip()
            for line in (result.get("recommendations_text") or "").split("\n")
            if line.strip()
        ],
        "best_model_name":    result.get("best_model_name", "N/A"),
        "best_model_accuracy": round(float(result.get("best_model_accuracy", 0)), 4),
        "dataset_overview":   dataset_overview,
        "missing_values":     missing_values,
        "model_comparison":   model_comparison,
        "visuals":            visuals,
    }
    

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    """
    Receives the uploaded dataset, runs the PipelineCoordinator,
    and returns the generated PDF report.
    """
    try:
        df = parse_upload(file)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not parse file: {str(e)}")

    try:
        result = PipelineCoordinator().run(df)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {str(e)}")

    report_path = result.get("report_path")
    if not report_path or not os.path.exists(report_path):
        raise HTTPException(status_code=500, detail="Report was not generated.")

    return FileResponse(
        path=report_path,
        media_type="application/pdf",
        filename="InsightForge_Report.pdf",
    )

@app.get("/report/pdf")
def download_pdf():
    """Serve the last generated PDF for download."""
    report_path = _last_result.get("report_path")
    if not report_path or not os.path.exists(report_path):
        raise HTTPException(status_code=404, detail="No report available. Run /analyze first.")
    return FileResponse(
        path=report_path,
        media_type="application/pdf",
        filename="InsightForge_Report.pdf",
    )

@app.get("/health")
def health():
    return {"status": "ok"}