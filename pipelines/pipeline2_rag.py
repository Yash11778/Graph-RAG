import pickle
import time
from pathlib import Path

from pipelines.utils import count_tokens, gemini_generate, make_result, setup_gemini

_ROOT     = Path(__file__).parent.parent.resolve()
_embedder = None
_index    = None
_chunks   = None
_client   = None


def _load():
    global _embedder, _index, _chunks, _client
    if _embedder is not None and _index is not None and _chunks is not None:
        return
    try:
        import faiss
        from fastembed import TextEmbedding
        _embedder = TextEmbedding("sentence-transformers/all-MiniLM-L6-v2")
        # Memory-map the index instead of loading all 681 MB into RAM — keeps the
        # footprint small enough to run alongside the embedder + BERTScore on modest machines.
        _index    = faiss.read_index(str(_ROOT / 'data/chunks/rag_index.faiss'), faiss.IO_FLAG_MMAP)
        with open(str(_ROOT / 'data/chunks/chunks.pkl'), 'rb') as f:
            _chunks = pickle.load(f)
        _client = setup_gemini()
    except Exception as e:
        _embedder = _index = _chunks = _client = None
        raise RuntimeError(f"pipeline2 load failed: {e}") from e


def _embed(text: str):
    import numpy as np
    emb  = list(_embedder.embed([text]))[0]
    emb  = np.array(emb, dtype=np.float32).reshape(1, -1)
    norm = (emb ** 2).sum(axis=1, keepdims=True) ** 0.5
    return emb / (norm + 1e-10)


def pipeline2(question: str, top_k: int = 8) -> dict:
    _load()
    emb = _embed(question)
    _, idxs = _index.search(emb, top_k)

    retrieved = [_chunks[i] for i in idxs[0] if i < len(_chunks)]
    context   = '\n\n---\n\n'.join(c['text'] for c in retrieved)
    sources   = [c.get('source', c.get('title', '')) for c in retrieved]

    prompt = (
        "You are an expert assistant. Use ONLY the context below to answer the question. "
        "Be thorough — extract every relevant fact, name, date, and detail present in the context. "
        "If the context covers multiple aspects of the question, address all of them. "
        "Do not say 'the context does not state' — if the answer is in the context, state it clearly.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {question}\n\n"
        "Answer:"
    )
    start   = time.time()
    answer  = gemini_generate(_client, prompt, max_tokens=500)
    latency = round(time.time() - start, 3)

    p_tok  = count_tokens(prompt)
    c_tok  = count_tokens(answer)
    result = make_result('basic_rag', answer, p_tok, c_tok, latency)
    result['sources'] = sources
    return result
