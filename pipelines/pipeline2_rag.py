import pickle
import time
from pathlib import Path

from pipelines.utils import count_tokens, groq_generate, make_result, setup_groq

_ROOT = Path(__file__).parent.parent.resolve()
_embedder = None
_index = None
_chunks = None
_client = None


def _load():
    global _embedder, _index, _chunks, _client
    if _embedder is None:
        import faiss
        from fastembed import TextEmbedding
        _embedder = TextEmbedding("sentence-transformers/all-MiniLM-L6-v2")
        _index = faiss.read_index(str(_ROOT / 'data/chunks/rag_index.faiss'))
        _chunks = pickle.load(open(str(_ROOT / 'data/chunks/chunks.pkl'), 'rb'))
        _client = setup_groq()


def _embed(text: str):
    import numpy as np
    emb = list(_embedder.embed([text]))[0]
    emb = np.array(emb, dtype=np.float32).reshape(1, -1)
    norm = (emb ** 2).sum(axis=1, keepdims=True) ** 0.5
    return emb / (norm + 1e-10)


def pipeline2(question: str, top_k: int = 5) -> dict:
    _load()
    emb = _embed(question)
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
