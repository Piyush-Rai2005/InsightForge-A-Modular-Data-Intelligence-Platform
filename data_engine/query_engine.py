import duckdb

class QueryEngine:
    def __init__(self, parquet_path):
        self.parquet_path = parquet_path
        self.con = duckdb.connect()

    def run_query(self, query):
        result = self.con.execute(query).fetchdf()
        return result