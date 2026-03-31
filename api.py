from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import pandas as pd
import sqlite3
import xml.etree.ElementTree as ET
import yaml
import zipfile
import io
import tempfile
import os

from core.coordinator import PipelineCoordinator

app = FastAPI(title="InsightForge API")

# Allow requests from the React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def parse_upload(file: UploadFile) -> pd.DataFrame:
    name = file.filename.lower()
    contents = file.file.read()
    buf = io.BytesIO(contents)

    if name.endswith(".csv"):
        return pd.read_csv(buf, on_bad_lines="skip", engine="c")

    elif name.endswith(".xlsx"):
        return pd.read_excel(buf)

    elif name.endswith(".json"):
        return pd.read_json(buf)

    elif name.endswith(".sqlite") or name.endswith(".sql"):
        # Write to a temp file because sqlite3 needs a path
        with tempfile.NamedTemporaryFile(delete=False, suffix=".sqlite") as tmp:
            tmp.write(contents)
            tmp_path = tmp.name
        conn = sqlite3.connect(tmp_path)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        os.unlink(tmp_path)
        if not tables:
            raise HTTPException(status_code=400, detail="No tables found in SQLite file.")
        return pd.read_sql(f"SELECT * FROM {tables[0][0]}", conn)

    elif name.endswith(".xml"):
        tree = ET.parse(buf)
        root = tree.getroot()
        rows = [{elem.tag: elem.text for elem in child} for child in root]
        return pd.DataFrame(rows)

    elif name.endswith(".yaml") or name.endswith(".yml"):
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
        raise HTTPException(status_code=400, detail="No supported file found inside ZIP.")

    else:
        raise HTTPException(status_code=400, detail=f"Unsupported file format: {name}")


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


@app.get("/health")
def health():
    return {"status": "ok"}