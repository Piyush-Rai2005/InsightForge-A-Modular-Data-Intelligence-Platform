import polars as pl
import json

def generate_schema(parquet_path, output_path="schema.json"):
    df = pl.read_parquet(parquet_path)

    schema = []

    for col, dtype in df.schema.items():
        schema.append({
            "name": col,
            "type": str(dtype)
        })

    sample_data = df.head(5).to_dicts()

    result = {
        "columns": schema,
        "sample_data": sample_data
    }

    with open(output_path, "w") as f:
        json.dump(result, f, indent=4)

    print("✅ Schema generated!")