import os
import pickle
import time
from pathlib import Path

from pipelines.utils import count_tokens, gemini_generate, make_result, setup_gemini

_ROOT     = Path(__file__).parent.parent.resolve()
_embedder = None
_index    = None
_chunks   = None
_client   = None


_load_error: str = ""   # set once if FAISS files are missing; cleared on success


def _try_download_faiss():
    """Download FAISS index + chunks from FAISS_DOWNLOAD_URL if env var is set and files are missing."""
    base_url = os.getenv('FAISS_DOWNLOAD_URL', '').rstrip('/')
    if not base_url:
        return
    faiss_path  = _ROOT / 'data/chunks/rag_index.faiss'
    chunks_path = _ROOT / 'data/chunks/chunks.pkl'
    if faiss_path.exists() and chunks_path.exists():
        return
    faiss_path.parent.mkdir(parents=True, exist_ok=True)
    import urllib.request
    for fname, dest in [('rag_index.faiss', faiss_path), ('chunks.pkl', chunks_path)]:
        if not dest.exists():
            url = f"{base_url}/{fname}"
            print(f"INFO:     Downloading {fname} from {url} …", flush=True)
            try:
                urllib.request.urlretrieve(url, dest)
                print(f"INFO:     Downloaded {fname} ({dest.stat().st_size // 1_048_576} MB)", flush=True)
            except Exception as e:
                print(f"WARNING:  Failed to download {fname}: {e}", flush=True)


def _load():
    global _embedder, _index, _chunks, _client, _load_error
    if _embedder is not None and _index is not None and _chunks is not None:
        return
    _try_download_faiss()
    faiss_path  = _ROOT / 'data/chunks/rag_index.faiss'
    chunks_path = _ROOT / 'data/chunks/chunks.pkl'
    if not faiss_path.exists() or not chunks_path.exists():
        _load_error = (
            "FAISS index not found on this server. "
            "Run scripts/build_faiss.py locally to regenerate data/chunks/rag_index.faiss "
            "and data/chunks/chunks.pkl, then upload them to the server."
        )
        return
    try:
        import faiss
        from fastembed import TextEmbedding
        _embedder = TextEmbedding("sentence-transformers/all-MiniLM-L6-v2")
        # Memory-map the index instead of loading all 681 MB into RAM — keeps the
        # footprint small enough to run alongside the embedder + BERTScore on modest machines.
        _index    = faiss.read_index(str(faiss_path), faiss.IO_FLAG_MMAP)
        with open(str(chunks_path), 'rb') as f:
            _chunks = pickle.load(f)
        _client   = setup_gemini()
        _load_error = ""
    except Exception as e:
        _embedder = _index = _chunks = _client = None
        _load_error = str(e)


def _embed(text: str):
    import numpy as np
    emb  = list(_embedder.embed([text]))[0]
    emb  = np.array(emb, dtype=np.float32).reshape(1, -1)
    norm = (emb ** 2).sum(axis=1, keepdims=True) ** 0.5
    return emb / (norm + 1e-10)


def pipeline2(question: str, top_k: int = 8) -> dict:
    _load()
    if _load_error:
        import time
        answer  = f"Basic RAG unavailable: {_load_error}"
        result  = make_result('basic_rag', answer, 0, count_tokens(answer), 0.0)
        result['sources'] = []
        result['status']  = 'faiss_unavailable'
        return result
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
    answer  = gemini_generate(_client, prompt, max_tokens=300)
    latency = round(time.time() - start, 3)

    p_tok  = count_tokens(prompt)
    c_tok  = count_tokens(answer)
    result = make_result('basic_rag', answer, p_tok, c_tok, latency)
    result['sources'] = sources
    return result
