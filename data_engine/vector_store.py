import chromadb
from sentence_transformers import SentenceTransformer
import json

class VectorStore:
    def __init__(self):
        self.client = chromadb.Client()
        self.collection = self.client.create_collection(name="schema")

        self.model = SentenceTransformer("all-MiniLM-L6-v2")

    def embed(self, text):
        return self.model.encode(text).tolist()

    def index_schema(self, schema_path="schema.json"):
        with open(schema_path, "r") as f:
            schema = json.load(f)

        for col in schema["columns"]:
            text = f"Column {col['name']} of type {col['type']}"

            embedding = self.embed(text)

            self.collection.add(
                documents=[text],
                embeddings=[embedding],
                ids=[col["name"]]
            )

        print("✅ Schema indexed in vector DB")

    def search(self, query, k=3):
        embedding = self.embed(query)

        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=k
        )

        return results["documents"]