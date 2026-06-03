"""
Step 1 of GraphRAG setup.
Converts data/raw/dataset.jsonl → data/raw/graphrag_docs.jsonl
in the format the TigerGraph GraphRAG service expects:
    {"document_id": "...", "text": "..."}
"""
import json
from pathlib import Path

INPUT  = Path("data/raw/dataset.jsonl")
OUTPUT = Path("data/raw/graphrag_docs.jsonl")

total = 0
with open(INPUT, encoding="utf-8") as fin, open(OUTPUT, "w", encoding="utf-8") as fout:
    for line in fin:
        doc = json.loads(line)
        fout.write(json.dumps({
            "document_id": str(doc["id"]),
            "text": doc["text"],
            "attributes": {"title": doc.get("title", "")},
        }, ensure_ascii=False) + "\n")
        total += 1

print(f"Wrote {total} documents to {OUTPUT}")
print("Next: start Docker Desktop, then run  python scripts/init_graphrag_service.py")
