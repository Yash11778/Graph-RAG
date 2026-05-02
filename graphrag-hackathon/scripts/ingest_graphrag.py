import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()

CHUNKS_PATH = "data/chunks/chunks.jsonl"
GRAPHRAG_URL = os.getenv("GRAPHRAG_URL", "http://localhost:8000")
BATCH_SIZE = 50

chunks = []
with open(CHUNKS_PATH, encoding="utf-8") as f:
    for line in f:
        chunks.append(json.loads(line))

print(f"Loaded {len(chunks)} chunks → ingesting to {GRAPHRAG_URL}")

for i in range(0, len(chunks), BATCH_SIZE):
    batch = chunks[i : i + BATCH_SIZE]
    documents = [
        {
            "id": str(c["id"]),
            "text": c["text"],
            "metadata": {"title": c["title"], "article_id": c["article_id"]},
        }
        for c in batch
    ]
    resp = requests.post(
        f"{GRAPHRAG_URL}/ingest",
        json={"documents": documents},
        timeout=120,
    )
    resp.raise_for_status()
    print(f"Ingested {min(i + BATCH_SIZE, len(chunks))}/{len(chunks)}")

print("Ingestion complete")
