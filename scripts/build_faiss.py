import json
import pickle

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

CHUNKS_PATH = 'data/chunks/chunks.jsonl'
INDEX_PATH = 'data/chunks/rag_index.faiss'
CHUNKS_PKL = 'data/chunks/chunks.pkl'
DIM = 384

chunks = []
with open(CHUNKS_PATH, encoding='utf-8') as f:
    for line in f:
        chunks.append(json.loads(line))

print(f'Loaded {len(chunks)} chunks')

embedder = SentenceTransformer('all-MiniLM-L6-v2')

texts = [c['text'] for c in chunks]
embs = embedder.encode(texts, batch_size=64, show_progress_bar=True)
embs = np.array(embs, dtype=np.float32)
faiss.normalize_L2(embs)

index = faiss.IndexFlatIP(DIM)
index.add(embs)

faiss.write_index(index, INDEX_PATH)
with open(CHUNKS_PKL, 'wb') as f:
    pickle.dump(chunks, f)

print(f'Total vectors: {index.ntotal}')
