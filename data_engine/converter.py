import polars as pl
import os

def convert_to_parquet(df: pl.DataFrame, output_path: str):
    df.write_parquet(output_path)
    print("✅ Converted to Parquet")