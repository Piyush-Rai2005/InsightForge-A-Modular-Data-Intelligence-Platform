"""
InsightForge — Unified API (v2.0)
═════════════════════════════════
All routes consolidated into a single FastAPI app.

Routes:
  POST /auth/register
  POST /auth/login
  GET  /auth/me
  POST /analyze
  GET  /jobs/{job_id}/status
  GET  /jobs/{job_id}/result
  POST /chat
  GET  /sessions
  GET  /sessions/{session_id}
  DELETE /sessions/{session_id}
  GET  /sessions/{session_id}/export
  POST /sessions/{session_id}/schedule
  DELETE /sessions/{session_id}/schedule
  GET  /health
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
import pandas as pd
import sqlite3
import xml.etree.ElementTree as ET
import yaml
import zipfile
import io
import tempfile
import os
import base64
import json
import uuid
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import charset_normalizer

load_dotenv()

# ── Local imports ───────────────────────────────────────────────────────────
from auth.database import engine, Base, get_db
from auth.models import User, AnalysisSession
from auth.security import get_current_user, get_current_user_optional
from auth.routes import auth_router
from cache.redis_cache import cache
from jobs.task_runner import dispatch_pipeline, get_result, cancel_job
from exports.pptx_exporter import generate_pptx
from exports.excel_exporter import generate_excel
from scheduler.report_scheduler import schedule_report, cancel_schedule

logger = logging.getLogger(__name__)


# ── Lifespan ────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created")
    yield


app = FastAPI(title="InsightForge API", version="2.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)


# ═══════════════════════════════════════════════════════════════════════════
# File parsing
# ═══════════════════════════════════════════════════════════════════════════
def parse_upload(file: UploadFile) -> pd.DataFrame:
    name = file.filename.lower()
    contents = file.file.read()
    buf = io.BytesIO(contents)

    def get_encoding(data: bytes) -> str:
        sample = data[:100000]
        enc = charset_normalizer.detect(sample).get("encoding")
        return enc if enc else "utf-8"

    if name.endswith(".csv"):
        enc = get_encoding(contents)
        return pd.read_csv(buf, encoding=enc, on_bad_lines="skip")
    elif name.endswith(".xlsx"):
        return pd.read_excel(buf)
    elif name.endswith(".json"):
        enc = get_encoding(contents)
        return pd.read_json(buf, encoding=enc)
    elif name.endswith((".sqlite", ".sql")):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".sqlite") as tmp:
            tmp.write(contents)
            tmp_path = tmp.name
        conn = sqlite3.connect(tmp_path)
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        if not tables:
            conn.close()
            os.unlink(tmp_path)
            raise HTTPException(400, "No tables found in SQLite DB")
        table_name = tables[0][0]
        df = pd.read_sql_query(f"SELECT * FROM [{table_name}]", conn)
        conn.close()
        os.unlink(tmp_path)
        return df
    elif name.endswith(".xml"):
        enc = get_encoding(contents)
        text_content = contents.decode(enc, errors="replace")
        root = ET.fromstring(text_content)
        rows = [{child.tag: child.text for child in elem} for elem in root]
        return pd.DataFrame(rows)
    elif name.endswith((".yaml", ".yml")):
        enc = get_encoding(contents)
        text_content = contents.decode(enc, errors="replace")
        data = yaml.safe_load(io.StringIO(text_content))
        return pd.DataFrame(data)
    elif name.endswith((".txt", ".log", ".tsv", ".dat")):
        enc = get_encoding(contents)
        return pd.read_csv(buf, sep=None, engine="python", encoding=enc)
    elif name.endswith(".parquet"):
        return pd.read_parquet(buf)
    elif name.endswith(".zip"):
        with zipfile.ZipFile(buf) as z:
            for f in z.namelist():
                if f.endswith(".csv"):
                    with z.open(f) as zf:
                        file_bytes = zf.read()
                    enc = get_encoding(file_bytes)
                    return pd.read_csv(io.BytesIO(file_bytes), encoding=enc, on_bad_lines="skip")
                elif f.endswith(".xlsx"):
                    return pd.read_excel(z.open(f))
        raise HTTPException(400, "No supported file inside ZIP")
    raise HTTPException(400, f"Unsupported file format: {name}")


# ── Helpers ─────────────────────────────────────────────────────────────────
def _encode_image(path: str | None):
    if not path or not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    return f"data:image/png;base64,{data}"


def _build_report_payload(result: dict):
    df = result.get("raw_data")

    dataset_overview = None
    missing_values = []

    if df is not None:
        rows, cols = df.shape
        num_df = df.select_dtypes(include=["number"])
        desc = num_df.describe().transpose().iloc[:8] if not num_df.empty else pd.DataFrame()
        desc_cols = list(desc.columns) if not desc.empty else []
        desc_rows = [
            {"feature": feat, **{c: round(float(row[c]), 3) for c in desc_cols}}
            for feat, row in desc.iterrows()
        ] if not desc.empty else []
        missing_series = df.isna().sum()
        missing_values = [
            {"column": col, "missing": int(cnt)}
            for col, cnt in missing_series[missing_series > 0].items()
        ]
        dataset_overview = {
            "rows": rows, "columns": cols,
            "desc_cols": desc_cols, "desc_rows": desc_rows,
        }

    skip_ml = result.get("skip_ml", False)
    scores = result.get("model_scores", {}) or {}
    model_comparison = [
        {"model": k, "accuracy": round(float(v), 4)} for k, v in scores.items()
    ]

    # ── Auto-generated charts (schema-driven) come first ─────────────────
    visuals = []
    for chart in result.get("auto_charts", []):
        visuals.append({
            "title": chart.get("title", ""),
            "image": None,
            "plotly_spec": chart.get("plotly_spec"),
            "insight": chart.get("insight", ""),
        })

    # ── ML charts (only if ML ran) ───────────────────────────────────────
    if not skip_ml:
        mapping = {
            "corr_plot": ("Correlation Heatmap", "corr_plotly"),
            "target_plot": ("Target Distribution", "target_plotly"),
            "conf_matrix": ("Confusion Matrix", "conf_matrix_plotly"),
            "roc_curve": ("ROC Curve", "roc_plotly"),
            "model_bar": ("Model Comparison Chart", "model_bar_plotly"),
        }
        insight_map = {
            "corr_plot": "corr_insight",
            "target_plot": "target_insight",
            "conf_matrix": "cm_insight",
            "roc_curve": "roc_insight",
        }

        for key, (label, plotly_key) in mapping.items():
            img = _encode_image(result.get(key))
            plotly_spec = result.get(plotly_key)
            if img or plotly_spec:
                visuals.append({
                    "title": label,
                    "image": img,
                    "plotly_spec": plotly_spec,
                    "insight": result.get(insight_map.get(key, ""), ""),
                })

    best_acc = result.get("best_model_accuracy")
    best_acc = round(float(best_acc), 4) if best_acc is not None else 0

    return {
        "exec_summary": result.get("exec_summary", ""),
        "recommendations": [
            x.strip() for x in (result.get("recommendations_text") or "").split("\n")
            if x.strip() and x.strip() not in ("**", "***", "---", "___")
        ],
        "best_model_name": result.get("best_model_name", "N/A") if not skip_ml else None,
        "best_model_accuracy": best_acc if not skip_ml else None,
        "dataset_overview": dataset_overview,
        "missing_values": missing_values,
        "model_comparison": model_comparison if not skip_ml else [],
        "visuals": visuals,
        "business_questions": result.get("business_questions", ""),
        "visual_narrative": result.get("visual_narrative", ""),
        "key_statistics": result.get("key_statistics", []),
        "leakage_warnings": result.get("leakage_warnings", []),
        "skip_ml": skip_ml,
        "skip_ml_reason": result.get("skip_ml_reason", ""),
    }


def _build_dashboard_payload(result: dict):
    df = result.get("raw_data")
    if df is None:
        return {"kpis": {}, "charts": []}

    best_acc = result.get("best_model_accuracy")
    best_acc = round(float(best_acc), 4) if best_acc is not None else None

    kpis = {
        "rows": int(df.shape[0]),
        "columns": int(df.shape[1]),
        "best_model": result.get("best_model_name", "N/A"),
        "best_model_accuracy": best_acc,
        "trust_score": result.get("trust_score"),
    }

    charts = []
    missing = df.isna().sum().sort_values(ascending=False)
    missing = missing[missing > 0].head(10)
    if not missing.empty:
        charts.append({
            "id": "missing_values", "type": "bar",
            "x": list(missing.index), "y": [int(v) for v in missing.values],
        })

    return {"kpis": kpis, "charts": charts}


# ═══════════════════════════════════════════════════════════════════════════
# POST /analyze — async pipeline dispatch
# ═══════════════════════════════════════════════════════════════════════════
@app.post("/analyze")
async def analyze(
    file: UploadFile = File(...),
    user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    try:
        df = parse_upload(file)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"Could not parse file: {e}")

    analysis_id = str(uuid.uuid4())

    # Save parquet for chat engine
    os.makedirs("cache/data", exist_ok=True)
    parquet_path = f"cache/data/{analysis_id}.parquet"
    df.to_parquet(parquet_path, index=False)

    # Create session if authenticated
    if user:
        session = AnalysisSession(
            id=analysis_id,
            user_id=user.id,
            filename=file.filename,
        )
        db.add(session)
        db.commit()

    try:
        job_id = dispatch_pipeline(df, analysis_id)
    except RuntimeError as e:
        raise HTTPException(429, str(e))
    return {"job_id": job_id, "analysis_id": analysis_id}


# ═══════════════════════════════════════════════════════════════════════════
# GET /jobs/{job_id}/status — poll for progress
# ═══════════════════════════════════════════════════════════════════════════
@app.get("/jobs/{job_id}/status")
async def job_status(job_id: str):
    status = cache.get_job_status(job_id)
    if not status:
        return {"status": "unknown", "step": "", "progress": 0}
    return status


# ═══════════════════════════════════════════════════════════════════════════
# DELETE /jobs/{job_id} — cancel a running job
# ═══════════════════════════════════════════════════════════════════════════
@app.delete("/jobs/{job_id}")
async def cancel_job_route(job_id: str):
    cancelled = cancel_job(job_id)
    if not cancelled:
        raise HTTPException(404, "Job not found or already finished")
    return {"status": "cancelled", "job_id": job_id}



@app.get("/jobs/{job_id}/result")
async def job_result(
    job_id: str,
    user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    result = get_result(job_id)
    if not result:
        raise HTTPException(404, "Result not ready or already fetched")

    report = _build_report_payload(result)
    dashboard = _build_dashboard_payload(result)

    # Persist to session if authenticated
    if user:
        session = db.query(AnalysisSession).filter(AnalysisSession.id == job_id).first()
        if session:
            session.report_json = json.dumps(report, default=str)
            session.dashboard_json = json.dumps(dashboard, default=str)
            session.health_report_json = json.dumps(result.get("health_report"), default=str)
            session.trust_score_json = json.dumps(result.get("trust_score"), default=str)
            session.advanced_insights_json = json.dumps(result.get("advanced_insights"), default=str)
            db.commit()

    return {
        "report": report,
        "dashboard": dashboard,
        "health_report": result.get("health_report"),
        "trust_score": result.get("trust_score"),
        "advanced_insights": result.get("advanced_insights"),
    }


# ═══════════════════════════════════════════════════════════════════════════
# POST /chat — natural language queries against the dataset
# ═══════════════════════════════════════════════════════════════════════════
class ChatRequest(BaseModel):
    analysis_id: str
    question: str

@app.post("/chat")
async def chat(body: ChatRequest):
    # Check cache first
    cache_key = f"chat:{body.analysis_id}:{body.question}"
    cached = cache.get_json(cache_key)
    if cached:
        return cached

    parquet_path = f"cache/data/{body.analysis_id}.parquet"
    if not os.path.exists(parquet_path):
        raise HTTPException(404, "Dataset not found. Please re-upload your file.")

    try:
        from data_engine.query_agent import QueryAgent
        qa = QueryAgent(parquet_path=parquet_path)
        answer = qa.run(body.question)

        result = {"answer": answer}
        cache.set_json(cache_key, result, ttl=3600)
        return result
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"Chat query failed: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# Session history routes
# ═══════════════════════════════════════════════════════════════════════════
@app.get("/sessions")
async def list_sessions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sessions = db.query(AnalysisSession).filter(
        AnalysisSession.user_id == user.id
    ).order_by(AnalysisSession.created_at.desc()).all()

    return [
        {
            "id": s.id,
            "filename": s.filename,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "schedule_frequency": s.schedule_frequency,
        }
        for s in sessions
    ]


@app.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = db.query(AnalysisSession).filter(
        AnalysisSession.id == session_id,
        AnalysisSession.user_id == user.id,
    ).first()
    if not session:
        raise HTTPException(404, "Session not found")

    return {
        "id": session.id,
        "filename": session.filename,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "report": json.loads(session.report_json) if session.report_json else None,
        "dashboard": json.loads(session.dashboard_json) if session.dashboard_json else None,
        "health_report": json.loads(session.health_report_json) if getattr(session, 'health_report_json', None) else None,
        "trust_score": json.loads(session.trust_score_json) if getattr(session, 'trust_score_json', None) else None,
        "advanced_insights": json.loads(session.advanced_insights_json) if getattr(session, 'advanced_insights_json', None) else None,
        "chat_history": json.loads(session.chat_history) if session.chat_history else [],
    }


@app.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = db.query(AnalysisSession).filter(
        AnalysisSession.id == session_id,
        AnalysisSession.user_id == user.id,
    ).first()
    if not session:
        raise HTTPException(404, "Session not found")
    db.delete(session)
    db.commit()
    return {"message": "Session deleted"}


class RenameSessionRequest(BaseModel):
    name: str

@app.patch("/sessions/{session_id}")
async def rename_session(
    session_id: str,
    body: RenameSessionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = db.query(AnalysisSession).filter(
        AnalysisSession.id == session_id,
        AnalysisSession.user_id == user.id
    ).first()
    if not session:
        raise HTTPException(404, "Session not found")

    session.filename = body.name
    db.commit()
    return {"message": "Session renamed", "new_name": body.name}


# ═══════════════════════════════════════════════════════════════════════════
# Export routes
# ═══════════════════════════════════════════════════════════════════════════
@app.get("/sessions/{session_id}/export")
async def export_session(
    session_id: str,
    format: str = "pdf",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = db.query(AnalysisSession).filter(
        AnalysisSession.id == session_id,
        AnalysisSession.user_id == user.id,
    ).first()
    if not session:
        raise HTTPException(404, "Session not found")

    report = json.loads(session.report_json) if session.report_json else {}

    if format == "pdf":
        pdf_path = f"outputs/report_{session_id}.pdf"
        if os.path.exists(pdf_path):
            return FileResponse(pdf_path, media_type="application/pdf", filename=f"report_{session.filename}.pdf")
        raise HTTPException(404, "PDF not generated yet")

    elif format == "pptx":
        pptx_bytes = generate_pptx(report)
        return Response(
            content=pptx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            headers={"Content-Disposition": f"attachment; filename=report_{session.filename}.pptx"},
        )

    elif format == "xlsx":
        xlsx_bytes = generate_excel(report)
        return Response(
            content=xlsx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=report_{session.filename}.xlsx"},
        )

    raise HTTPException(400, f"Unsupported export format: {format}")


# ═══════════════════════════════════════════════════════════════════════════
# Schedule routes
# ═══════════════════════════════════════════════════════════════════════════
class ScheduleRequest(BaseModel):
    frequency: str  # daily, weekly, monthly


@app.post("/sessions/{session_id}/schedule")
def create_schedule(
    session_id: str,
    body: ScheduleRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.frequency not in ("daily", "weekly", "monthly"):
        raise HTTPException(400, "Frequency must be daily, weekly, or monthly")

    session = db.query(AnalysisSession).filter(
        AnalysisSession.id == session_id,
        AnalysisSession.user_id == user.id,
    ).first()
    if not session:
        raise HTTPException(404, "Session not found")

    schedule_report(session_id, body.frequency)
    session.schedule_frequency = body.frequency
    db.commit()

    return {"status": "scheduled", "frequency": body.frequency}


@app.delete("/sessions/{session_id}/schedule")
def delete_schedule(
    session_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = db.query(AnalysisSession).filter(
        AnalysisSession.id == session_id,
        AnalysisSession.user_id == user.id,
    ).first()
    if not session:
        raise HTTPException(404, "Session not found")

    cancel_schedule(session_id)
    session.schedule_frequency = None
    db.commit()

    return {"status": "unscheduled"}


# ═══════════════════════════════════════════════════════════════════════════
# Health check
# ═══════════════════════════════════════════════════════════════════════════
@app.get("/health")
def health():
    return {"status": "ok", "version": "2.0.0"}