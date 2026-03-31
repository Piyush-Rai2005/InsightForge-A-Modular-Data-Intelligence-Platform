import json
import os
from dotenv import load_dotenv
from google import genai

from data_engine.vector_store import VectorStore
from data_engine.query_engine import QueryEngine

# ✅ Load .env
load_dotenv()

class QueryAgent:
    def __init__(self, parquet_path, schema_path="schema.json"):
        self.engine = QueryEngine(parquet_path)
        self.vector_store = VectorStore()

        # ✅ Get API key from .env
        api_key = os.getenv("GOOGLE_API_KEY")

        if not api_key:
            raise ValueError("❌ GOOGLE_API_KEY not found in .env")

        self.client = genai.Client(api_key=api_key)

        # Load schema
        with open(schema_path, "r") as f:
            self.schema = json.load(f)

    def get_relevant_columns(self, user_query):
        return self.vector_store.search(user_query)

    def generate_sql(self, user_query, context):
        prompt = f"""
You are an expert data analyst.

Dataset Schema:
{self.schema}

Relevant Columns:
{context}

Convert the user question into a valid DuckDB SQL query.

Rules:
- Table name is 'data.parquet'
- Use exact column names
- Only return SQL
- No explanation
- No markdown

Question: {user_query}
"""

        response = self.client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )

        sql = response.text.strip()

        # Clean formatting issues
        sql = sql.replace("```sql", "").replace("```", "").strip()

        return sql

    def run(self, user_query):
        context = self.get_relevant_columns(user_query)

        sql = self.generate_sql(user_query, context)

        print("🧠 Generated SQL:")
        print(sql)

        try:
            result = self.engine.run_query(sql)
            return result

        except Exception as e:
            print("❌ SQL Failed. Attempting Fix...")

            fix_prompt = f"""
    The following SQL query failed:

    {sql}

    Error:
    {str(e)}

    Fix the SQL. Return only corrected SQL.
    """

            response = self.client.models.generate_content(
                model="gemini-1.5-flash",
                contents=fix_prompt
            )

            fixed_sql = response.text.strip()
            fixed_sql = fixed_sql.replace("```sql", "").replace("```", "").strip()

            print("🔧 Fixed SQL:")
            print(fixed_sql)

            return self.engine.run_query(fixed_sql)