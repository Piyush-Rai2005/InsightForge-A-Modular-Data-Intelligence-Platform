import duckdb

class QueryEngine:
    def __init__(self, parquet_path):
        self.parquet_path = parquet_path
        self.con = duckdb.connect()
        self.con.execute(
            "CREATE OR REPLACE VIEW data AS SELECT * FROM read_parquet(?)",
            [self.parquet_path],
        )

    def run_query(self, query):
        result = self.con.execute(query).fetchdf()
        return result