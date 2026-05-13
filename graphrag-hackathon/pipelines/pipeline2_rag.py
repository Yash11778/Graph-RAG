import pickle
import time
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from pipelines.utils import count_tokens, groq_generate, make_result, setup_groq

_ROOT = Path(__file__).parent.parent.resolve()
_embedder = None
_index = None
_chunks = None
_client = None


def _load():
    global _embedder, _index, _chunks, _client
    if _embedder is None:
        _embedder = SentenceTransformer('all-MiniLM-L6-v2')
        _index = faiss.read_index(str(_ROOT / 'data/chunks/rag_index.faiss'))
        _chunks = pickle.load(open(str(_ROOT / 'data/chunks/chunks.pkl'), 'rb'))
        _client = setup_groq()


def pipeline2(question: str, top_k: int = 5) -> dict:
    _load()
    emb = _embedder.encode([question], normalize_embeddings=True)
    emb = np.array(emb, dtype=np.float32)
    faiss.normalize_L2(emb)
    _, idxs = _index.search(emb, top_k)

    retrieved = [_chunks[i] for i in idxs[0] if i < len(_chunks)]
    context = '\n\n---\n\n'.join(c['text'] for c in retrieved)
    sources = [c.get('source', c.get('title', '')) for c in retrieved]

    prompt = f'Context:\n{context}\n\nQuestion: {question}\nAnswer thoroughly.'
    start = time.time()
    answer = groq_generate(_client, prompt)
    latency = round(time.time() - start, 3)

    p_tok = count_tokens(prompt)
    c_tok = count_tokens(answer)
    result = make_result('basic_rag', answer, p_tok, c_tok, latency)
    result['sources'] = sources
    return result
