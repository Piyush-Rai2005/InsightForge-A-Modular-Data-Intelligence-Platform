import streamlit as st
import pandas as pd
import json
import sqlite3
import xml.etree.ElementTree as ET
import yaml
import zipfile
import io
import time

from core.coordinator import PipelineCoordinator


# ----------------------------------------------------
# PAGE CONFIG
# ----------------------------------------------------
st.set_page_config(page_title="InsightForge", layout="wide")


# ----------------------------------------------------
# CUSTOM STYLING
# ----------------------------------------------------
st.markdown(
    """
    <style>
        .title-font {
            font-size: 38px;
            font-weight: 800;
            font-family: 'Poppins', sans-serif;
            letter-spacing: 0.8px;
        }
        .tagline {
            font-size: 16px;
            opacity: 0.75;
            margin-top: -8px;
            font-family: 'Poppins', sans-serif;
        }
        .spinner-box {
            background: rgba(0,122,255,0.15);
            padding: 18px;
            border-radius: 10px;
            width: 100%;
            font-weight: 600;
            color: white;
            text-align:center;
            font-family:'Poppins', sans-serif;
        }
        .preview-title {
            font-size: 24px;
            font-weight: 700;
            color: #ffffff;
            margin-top: 20px;
            margin-bottom: 12px;
            letter-spacing: 0.6px;
            font-family: 'Poppins', sans-serif;
        }
        div[data-testid="dataframe"] table tbody tr td {
            padding-top: 10px !important;
            padding-bottom: 10px !important;
        }
        div[data-testid="dataframe"] table thead th {
            font-weight: 700 !important;
            font-size: 14px !important;
            font-family: 'Poppins', sans-serif;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------
# HEADER
# ----------------------------------------------------
st.markdown(
    """
    <h1 class="title-font" style="text-align:center; color:white;">
        🤖 InsightForge
    </h1>
    <p class="tagline" style="text-align:center; color:white;">
        Let your data tell it's story ✨
    </p>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------
# FILE UPLOADER
# ----------------------------------------------------
uploaded = st.file_uploader(
    "Upload dataset",
    type=[
        "csv", "xlsx", "json", "sql", "sqlite",
        "xml", "txt", "tsv", "log", "dat", "yaml", "yml",
        "parquet", "zip"
    ],
)

# ----------------------------------------------------
# SMART UNIVERSAL FILE READER
# ----------------------------------------------------
def load_file(uploaded):
    name = uploaded.name.lower()

    if name.endswith(".csv"):
        return pd.read_csv(uploaded)

    elif name.endswith(".xlsx"):
        return pd.read_excel(uploaded)

    elif name.endswith(".json"):
        return pd.read_json(uploaded)

    elif name.endswith(".sqlite") or name.endswith(".sql"):
        conn = sqlite3.connect(uploaded)
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        if tables:
            tname = tables[0][0]
            return pd.read_sql(f"SELECT * FROM {tname}", conn)

    elif name.endswith(".xml"):
        tree = ET.parse(uploaded)
        root = tree.getroot()
        rows = [{elem.tag: elem.text for elem in child} for child in root]
        return pd.DataFrame(rows)

    elif name.endswith(".yaml") or name.endswith(".yml"):
        data = yaml.safe_load(uploaded)
        return pd.DataFrame(data)

    elif name.endswith(".txt") or name.endswith(".log") or name.endswith(".tsv") or name.endswith(".dat"):
        return pd.read_csv(uploaded, sep=None, engine="python")

    elif name.endswith(".parquet"):
        return pd.read_parquet(uploaded)

    elif name.endswith(".zip"):
        with zipfile.ZipFile(uploaded) as z:
            for f in z.namelist():
                if f.endswith(".csv"):
                    return pd.read_csv(z.open(f))
                elif f.endswith(".xlsx"):
                    return pd.read_excel(z.open(f))
        st.warning("⚠ ZIP detected but no supported file inside.")
        return None

    else:
        st.error("❌ Unsupported format.")
        return None

# ---------------------------------------------------
# PIPELINE EXECUTION
# ---------------------------------------------------
if uploaded:
    df = load_file(uploaded)

    if df is not None:

        st.markdown("<span class='preview-title'>🔍 Data Preview</span>", unsafe_allow_html=True)
        st.dataframe(df.head())

        if st.button("🚀 Activate InsightForge"):

            status_placeholder = st.empty()

           
            spinner_html = """
            <div style="
                background: rgba(0, 122, 255, 0.25); 
                padding: 20px;
                border-radius: 10px;
                width: 100%;
                text-align: left;
                font-family: 'Poppins', sans-serif;
                font-size: 14px;
                color: white;
                backdrop-filter: blur(3px); 
                border: 1px solid rgba(0,122,255,0.25); 
}
            ">
             🧠 Turning your data into insights........hang tight!
            </div>
            """
            status_placeholder.markdown(spinner_html, unsafe_allow_html=True)

            #  Run your pipeline normally (NO Streamlit spinner)
            result = PipelineCoordinator().run(df)

            # Remove the loading bar and show success message
            status_placeholder.empty()

            st.success("✨ Your insights are ready!")

            report_path = result.get("report_path")
            if report_path:
                with open(report_path, "rb") as f:
                    st.download_button(
                        "📥 Download Your Insight Report",
                        data=f,
                        file_name="InsightForge_Report.pdf",
                        mime="application/pdf",
                        help="Your AI-generated report 🤍",
                        width="stretch"
                    )
            else:
                st.error("⚠ Report was not generated.")