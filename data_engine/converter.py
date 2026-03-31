import polars as pl
import os

def convert_csv_to_parquet(input_path, output_path):
    df = pl.read_csv(input_path)
    df.write_parquet(output_path)
    print("✅ Converted to Parquet")