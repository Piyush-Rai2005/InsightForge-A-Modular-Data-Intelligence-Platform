import streamlit as st
import pandas as pd
import json
import sqlite3
import xml.etree.ElementTree as ET
import yaml
import zipfile
import io
import time




# ----------------------------------------------------
# PAGE CONFIG
# ----------------------------------------------------
st.set_page_config(page_title="InsightSphere", layout="wide")


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
        🤖 InsightSphere
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
