from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import pandas as pd
import sqlite3
import xml.etree.ElementTree as ET
import yaml
import zipfile
import io
import tempfile
import os
import base64
import uuid
from pathlib import Path

from core.coordinator import PipelineCoordinator
from data_engine.query_agent import QueryAgent
from data_engine.schema import generate_schema

app = FastAPI(title="InsightForge API")

_last_result = {}
_analysis_sessions = {}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "https://insightforge-data.vercel.app"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)


class ChatRequest(BaseModel):
    analysis_id: str
    question: str


# ---------------- FILE PARSER ----------------
def parse_upload(file: UploadFile) -> pd.DataFrame:
    name = file.filename.lower()
    contents = file.file.read()
    buf = io.BytesIO(contents)

    if name.endswith(".csv"):
        return pd.read_csv(buf, on_bad_lines="skip")

    elif name.endswith(".xlsx"):
        return pd.read_excel(buf)

    elif name.endswith(".json"):
        return pd.read_json(buf)

    elif name.endswith((".sqlite", ".sql")):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".sqlite") as tmp:
            tmp.write(contents)
            tmp_path = tmp.name

        conn = sqlite3.connect(tmp_path)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()

        if not tables:
            raise HTTPException(400, "No tables found in SQLite DB")

        table_name = tables[0][0]
        df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)

        conn.close()
        os.unlink(tmp_path)
        return df

    elif name.endswith(".xml"):
        root = ET.parse(buf).getroot()
        rows = [{child.tag: child.text for child in elem} for elem in root]
        return pd.DataFrame(rows)

    elif name.endswith((".yaml", ".yml")):
        data = yaml.safe_load(buf)
        return pd.DataFrame(data)

    elif name.endswith((".txt", ".log", ".tsv", ".dat")):
        return pd.read_csv(buf, sep=None, engine="python")

    elif name.endswith(".parquet"):
        return pd.read_parquet(buf)

    elif name.endswith(".zip"):
        with zipfile.ZipFile(buf) as z:
            for f in z.namelist():
                if f.endswith(".csv"):
                    return pd.read_csv(z.open(f))
                elif f.endswith(".xlsx"):
                    return pd.read_excel(z.open(f))
        raise HTTPException(400, "No supported file inside ZIP")

    raise HTTPException(400, f"Unsupported file format: {name}")


# ---------------- HELPERS ----------------
def _encode_image(path: str | None):
    if not path or not os.path.exists(path):
        return None

    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode()

    return f"data:image/png;base64,{data}"


# ---------------- REPORT PAYLOAD ----------------
def _build_report_payload(result: dict):
    df = result.get("raw_data")

    dataset_overview = None
    missing_values = []

    if df is not None:
        rows, cols = df.shape

        desc = df.describe().transpose().iloc[:8]
        desc_cols = list(desc.columns)

        desc_rows = [
            {"feature": feat, **{c: round(float(row[c]), 3) for c in desc_cols}}
            for feat, row in desc.iterrows()
        ]

        missing_series = df.isna().sum()
        missing_values = [
            {"column": col, "missing": int(cnt)}
            for col, cnt in missing_series[missing_series > 0].items()
        ]

        dataset_overview = {
            "rows": rows,
            "columns": cols,
            "desc_cols": desc_cols,
            "desc_rows": desc_rows,
        }

    scores = result.get("model_scores", {})
    model_comparison = [
        {"model": k, "accuracy": round(float(v), 4)}
        for k, v in scores.items()
    ]

    visuals = []
    mapping = {
        "corr_plot": "Correlation Heatmap",
        "target_plot": "Target Distribution",
        "conf_matrix": "Confusion Matrix",
        "roc_curve": "ROC Curve",
        "model_bar": "Model Comparison Chart",
    }

    insight_map = {
        "corr_plot": "corr_insight",
        "target_plot": "target_insight",
        "conf_matrix": "cm_insight",
        "roc_curve": "roc_insight",
    }

    for key, label in mapping.items():
        img = _encode_image(result.get(key))
        if img:
            visuals.append({
                "title": label,
                "image": img,
                "insight": result.get(insight_map.get(key, ""), "")
            })

    return {
        "exec_summary": result.get("exec_summary", ""),
        "recommendations": [
            x.strip() for x in (result.get("recommendations_text") or "").split("\n") if x.strip()
        ],
        "best_model_name": result.get("best_model_name", "N/A"),
        "best_model_accuracy": round(float(result.get("best_model_accuracy", 0)), 4),
        "dataset_overview": dataset_overview,
        "missing_values": missing_values,
        "model_comparison": model_comparison,
        "visuals": visuals,
    }


# ---------------- DASHBOARD ----------------
def _build_dashboard_payload(result: dict):
    df = result.get("raw_data")
    if df is None:
        return {"kpis": {}, "charts": []}

    kpis = {
        "rows": int(df.shape[0]),
        "columns": int(df.shape[1]),
        "best_model": result.get("best_model_name", "N/A"),
        "best_model_accuracy": round(float(result.get("best_model_accuracy", 0)), 4),
    }

    charts = []

    missing = df.isna().sum().sort_values(ascending=False)
    missing = missing[missing > 0].head(10)

    if not missing.empty:
        charts.append({
            "id": "missing_values",
            "type": "bar",
            "x": list(missing.index),
            "y": list(missing.values),
        })

    return {"kpis": kpis, "charts": charts}


# ---------------- SESSION STORAGE ----------------
def _persist_session_artifacts(analysis_id, result):
    base_dir = Path("outputs") / "sessions" / analysis_id
    base_dir.mkdir(parents=True, exist_ok=True)

    raw_df = result.get("raw_data")
    if raw_df is None:
        raise HTTPException(500, "No raw_data")

    raw_path = base_dir / "raw.parquet"
    data_path = base_dir / "data.parquet"
    schema_path = base_dir / "schema.json"

    raw_df.to_parquet(raw_path, index=False)
    raw_df.to_parquet(data_path, index=False)

    generate_schema(str(data_path), output_path=str(schema_path))

    return {
        "data_parquet_path": str(data_path),
        "schema_path": str(schema_path),
    }


# ---------------- ROUTES ----------------
@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    df = parse_upload(file)

    result = PipelineCoordinator().run(df)

    analysis_id = str(uuid.uuid4())

    artifacts = _persist_session_artifacts(analysis_id, result)

    report = _build_report_payload(result)
    dashboard = _build_dashboard_payload(result)

    _analysis_sessions[analysis_id] = {
        **artifacts
    }

    return {
        "analysis_id": analysis_id,
        "report": report,
        "dashboard": dashboard,
    }


@app.post("/chat")
def chat(request: ChatRequest):
    session = _analysis_sessions.get(request.analysis_id)

    if not session:
        raise HTTPException(404, "Invalid analysis_id")

    agent = QueryAgent(
        parquet_path=session["data_parquet_path"],
        schema_path=session["schema_path"],
    )

    sql = agent.generate_sql(
        request.question,
        agent.get_relevant_columns(request.question),
    )

    result_df = agent.engine.run_query(sql)

    return {
        "sql": sql,
        "columns": list(result_df.columns),
        "rows": result_df.head(200).to_dict(orient="records"),
    }


@app.get("/health")
def health():
    return {"status": "ok"}