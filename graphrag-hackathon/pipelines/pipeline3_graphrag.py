"""
Pipeline 3 — GraphRAG: FAISS seed retrieval + TigerGraph entity-graph expansion

Retrieval path:
  Question → FAISS (top-1 most relevant chunk)
    → TigerGraph GraphRAG hybrid search (top-3, num_hops=2)
    → Merge contexts capped at ~380 tokens
    → Groq/Llama generates concise 1-sentence answer (max 80 tokens)
"""
import os
import pickle
import threading
import time
import logging
from pathlib import Path

import requests

from pipelines.utils import count_tokens, groq_generate, make_result, setup_groq

logger = logging.getLogger(__name__)

TG_USER          = "yashdharme6@gmail.com"
TG_PASS          = "YOUR_TG_SECRET_HERE"
GRAPH_NAME       = "MyDatabase"
GRAPHRAG_SERVICE = os.environ.get("GRAPHRAG_SERVICE", "http://localhost:8003")
GRAPHRAG_AUTH    = (TG_USER, TG_PASS)

HYBRID_PARAMS = {
    "indices":      ["DocumentChunk", "Community"],
    "top_k":        3,
    "num_hops":     2,
    "num_seen_min": 1,
    "combine":      "concat",
    "expand":       False,
    "verbose":      False,
}

_ROOT = Path(__file__).parent.parent.resolve()
_embedder    = None
_faiss_index = None
_chunks      = None
_groq_client = None


def _load():
    global _embedder, _faiss_index, _chunks, _groq_client
    if _embedder is None:
        import faiss
        from sentence_transformers import SentenceTransformer
        _embedder    = SentenceTransformer('all-MiniLM-L6-v2')
        _faiss_index = faiss.read_index(str(_ROOT / 'data/chunks/rag_index.faiss'))
        _chunks      = pickle.load(open(str(_ROOT / 'data/chunks/chunks.pkl'), 'rb'))
        _groq_client = setup_groq()


def _faiss_retrieve(question: str, top_k: int = 1) -> list[dict]:
    import faiss
    import numpy as np
    emb = _embedder.encode([question], normalize_embeddings=True)
    emb = np.array(emb, dtype=np.float32)
    faiss.normalize_L2(emb)
    _, idxs = _faiss_index.search(emb, top_k)
    return [_chunks[i] for i in idxs[0] if i < len(_chunks)]


def _tg_retrieve(question: str, deadline: float = 8.0) -> list[str]:
    """
    Call TigerGraph in a daemon thread with a hard wall-clock deadline.
    Uses a fresh thread per call so a hung socket never blocks future calls.
    """
    result: list = []
    exc: list    = []

    def _call():
        try:
            resp = requests.post(
                f"{GRAPHRAG_SERVICE}/{GRAPH_NAME}/graphrag/answerquestion",
                auth=GRAPHRAG_AUTH,
                json={"question": question, "method": "hybrid", "method_params": HYBRID_PARAMS},
                timeout=(3, 5),
            )
            if resp.status_code != 200:
                return
            data      = resp.json()
            retrieved = data.get("retrieved", [])
            texts     = []
            items     = retrieved.items() if isinstance(retrieved, dict) else enumerate(retrieved)
            for _, chunk in items:
                if isinstance(chunk, str) and chunk.strip():
                    texts.append(chunk.strip())
                elif isinstance(chunk, dict):
                    t = chunk.get("text", "") or chunk.get("content", "")
                    if t.strip():
                        texts.append(t.strip())
                elif isinstance(chunk, list):
                    for c in chunk:
                        if isinstance(c, str) and c.strip():
                            texts.append(c.strip())
                        elif isinstance(c, dict):
                            t = c.get("text", "") or c.get("content", "")
                            if t.strip():
                                texts.append(t.strip())
            result.extend(texts)
        except Exception as e:
            exc.append(e)

    t = threading.Thread(target=_call, daemon=True)
    t.start()
    t.join(timeout=deadline)
    if t.is_alive():
        logger.warning("TG retrieval timed out (%.1fs) — skipping", deadline)
    elif exc:
        logger.warning("TG retrieval error: %s", exc[0])
    return result


def pipeline3(question: str) -> dict:
    _load()
    t_start = time.time()

    faiss_chunks  = _faiss_retrieve(question, top_k=1)
    faiss_texts   = [c['text'] for c in faiss_chunks]
    faiss_sources = [c.get('source', '') for c in faiss_chunks]

    tg_texts = _tg_retrieve(question)

    context_parts = list(faiss_texts)
    token_budget  = 380 - sum(count_tokens(t) for t in faiss_texts)
    for tg_text in tg_texts:
        if token_budget <= 0:
            break
        tok = count_tokens(tg_text)
        if tg_text not in context_parts and tok <= token_budget:
            context_parts.append(tg_text)
            token_budget -= tok

    context = "\n\n---\n\n".join(context_parts)
    prompt  = (
        f"Context:\n{context}\n\n"
        f"Q: {question}\n"
        f"A (1 sentence, facts only):"
    )
    answer  = groq_generate(_groq_client, prompt, max_tokens=80)
    latency = round(time.time() - t_start, 3)

    result                   = make_result("graphrag", answer, count_tokens(prompt), count_tokens(answer), latency)
    result["sources"]        = faiss_sources
    result["context_tokens"] = count_tokens(context)
    result["retriever"]      = "faiss+tigergraph_hybrid"
    return result
