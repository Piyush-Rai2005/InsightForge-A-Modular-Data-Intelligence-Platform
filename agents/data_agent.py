import numpy as np
import pandas as pd
from .base_agent import BaseAgent

class DataAgent(BaseAgent):
    """Cleans and preprocesses the uploaded dataset generically."""

    def __init__(self):
        super().__init__("DataAgent")

    def run(self, context):
        raw_df = context["data"].copy()
        df = raw_df.copy()
        self.log("Cleaning & preprocessing dataset...")

        # Strip whitespace from column names
        df.columns = [str(c).strip() for c in df.columns]

        # Treat empty strings as NaN
        df.replace({"": np.nan, " ": np.nan}, inplace=True)

        # Drop columns that are almost entirely missing
        thresh = int(0.9 * len(df))
        df.dropna(axis=1, thresh=len(df) - thresh, inplace=True)

        # Try to coerce object columns to numeric when reasonable
        for col in df.columns:
            if df[col].dtype == "object":
                num = pd.to_numeric(df[col], errors="coerce")
                if num.notna().sum() >= 0.7 * len(df):
                    df[col] = num

        # Impute missing values
        for col in df.columns:
            if pd.api.types.is_numeric_dtype(df[col]):
                mean_val = df[col].mean()
                df[col] = df[col].fillna(mean_val)
            else:
                if df[col].isna().any():
                    try:
                        mode = df[col].mode().iloc[0]
                    except IndexError:
                        mode = "Unknown"
                    df[col] = df[col].fillna(mode)

        # One-hot encode categoricals
        cat_cols = df.select_dtypes(include=["object", "category"]).columns
        df = pd.get_dummies(df, columns=cat_cols, drop_first=True)

        context["raw_data"] = raw_df
        context["clean_data"] = df
        self.log("Data preprocessing complete")
        return context