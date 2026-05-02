import json
import os

import faiss
import numpy as np
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

load_dotenv()

CHUNKS_PATH = "data/chunks/chunks.jsonl"
FAISS_DIR = "data/faiss"
BATCH_SIZE = 512
DIM = 384

os.makedirs(FAISS_DIR, exist_ok=True)

embedder = SentenceTransformer("all-MiniLM-L6-v2")

chunks = []
with open(CHUNKS_PATH, encoding="utf-8") as f:
    for line in f:
        chunks.append(json.loads(line))

print(f"Loaded {len(chunks)} chunks")

index = faiss.IndexFlatIP(DIM)

for i in range(0, len(chunks), BATCH_SIZE):
    batch = [c["text"] for c in chunks[i : i + BATCH_SIZE]]
    embs = embedder.encode(batch, normalize_embeddings=True, show_progress_bar=False)
    index.add(np.array(embs, dtype=np.float32))
    print(f"Indexed {min(i + BATCH_SIZE, len(chunks))}/{len(chunks)}")

faiss.write_index(index, os.path.join(FAISS_DIR, "index.bin"))

with open(os.path.join(FAISS_DIR, "chunks.json"), "w", encoding="utf-8") as f:
    json.dump(chunks, f, ensure_ascii=False)

print(f"FAISS index saved with {index.ntotal} vectors → {FAISS_DIR}/")
