import gc
import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder
from .base_agent import BaseAgent

class DataAgent(BaseAgent):
    """Cleans and preprocesses the uploaded dataset generically."""

    # Columns with more unique values than this get label-encoded, not one-hot
    HIGH_CARD_THRESHOLD = 50
    # Columns where unique ratio exceeds this are treated as IDs and dropped
    ID_RATIO_THRESHOLD = 0.95

    def __init__(self):
        super().__init__("DataAgent")

    def run(self, context):
        # Keep one pristine copy for raw_data, work on a second in-place.
        # Avoid a 3rd copy that would triple peak RAM.
        raw_df = context["data"].copy()
        df = raw_df.copy()
        # Release the original reference so only raw_df + df live in RAM.
        del context["data"]
        gc.collect()
        self.log("Cleaning & preprocessing dataset...")

        # Strip whitespace from column names
        df.columns = [str(c).strip() for c in df.columns]

        # Treat empty strings as NaN
        df.replace({"": np.nan, " ": np.nan}, inplace=True)

        # Drop rows that are 100% NaN (track count for health report)
        all_nan_rows = df.isna().all(axis=1).sum()
        if all_nan_rows > 0:
            df = df.dropna(how="all")
            self.log(f"Dropped {all_nan_rows} completely empty rows")
        context["dropped_empty_rows"] = int(all_nan_rows)

        # Drop columns that are 100% NaN
        all_nan_cols = [c for c in df.columns if df[c].isna().all()]
        if all_nan_cols:
            df.drop(columns=all_nan_cols, inplace=True)
            self.log(f"Dropped {len(all_nan_cols)} completely empty columns: {', '.join(all_nan_cols[:5])}")
        context["dropped_empty_cols"] = len(all_nan_cols)

        # Drop columns that are almost entirely missing (>90% null)
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

        # ── Smart encoding of categorical columns ──────────────────────────
        cat_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
        dropped_ids = []
        label_encoded = []
        one_hot_cols = []

        for col in cat_cols:
            n_unique = df[col].nunique()
            ratio = n_unique / len(df) if len(df) > 0 else 0

            if ratio >= self.ID_RATIO_THRESHOLD:
                # Looks like an ID column (>95% unique) -> drop it
                dropped_ids.append(col)
            elif n_unique > self.HIGH_CARD_THRESHOLD:
                # High cardinality -> label encode instead of one-hot
                le = LabelEncoder()
                df[col] = le.fit_transform(df[col].astype(str))
                label_encoded.append(col)
            else:
                # Low cardinality -> safe for one-hot
                one_hot_cols.append(col)

        if dropped_ids:
            self.log(f"Dropped ID-like columns ({len(dropped_ids)}): {', '.join(dropped_ids[:5])}")
            df.drop(columns=dropped_ids, inplace=True)

        if label_encoded:
            self.log(f"Label-encoded high-cardinality columns ({len(label_encoded)}): {', '.join(label_encoded[:5])}")

        if one_hot_cols:
            df = pd.get_dummies(df, columns=one_hot_cols, drop_first=True)
            self.log(f"One-hot encoded columns ({len(one_hot_cols)}): {', '.join(one_hot_cols[:5])}")

        # ── Downcast numerics to halve RAM footprint ───────────────────────
        for col in df.select_dtypes(include=["float64"]).columns:
            df[col] = df[col].astype("float32")
        for col in df.select_dtypes(include=["int64"]).columns:
            df[col] = df[col].astype("int32")
        gc.collect()

        context["raw_data"] = raw_df
        context["clean_data"] = df
        self.log(f"Data preprocessing complete -> {df.shape[0]} rows x {df.shape[1]} cols")
        return context