import pickle
import time

import faiss
import numpy as np
import requests
from sentence_transformers import SentenceTransformer

from pipelines.utils import count_tokens, groq_generate, make_result, setup_groq

TG_HOST = 'https://tg-cddb2056-27e0-4388-87a8-8be8de814ed5.tg-2635877100.i.tgcloud.io'
TG_TOKEN = 'YOUR_TG_JWT_TOKEN_HERE'
TG_GRAPH = 'MyDatabase'
TG_HEADERS = {'Authorization': f'Bearer {TG_TOKEN}'}

PARAMS = {
    'top_k': 2,
}

embedder = SentenceTransformer('all-MiniLM-L6-v2')
index = faiss.read_index('data/chunks/rag_index.faiss')
chunks = pickle.load(open('data/chunks/chunks.pkl', 'rb'))
chunk_id_map = {c['id']: c for c in chunks}
client = setup_groq()


def _fetch_from_tg(doc_ids: list[str]) -> dict[str, str]:
    """Fetch document content from TigerGraph by ID."""
    results = {}
    for doc_id in doc_ids:
        try:
            r = requests.get(
                f'{TG_HOST}/restpp/graph/{TG_GRAPH}/vertices/Document/{doc_id}',
                headers=TG_HEADERS, timeout=10,
            )
            if r.status_code == 200:
                data = r.json().get('results', [])
                if data:
                    attrs = data[0].get('attributes', {})
                    results[doc_id] = attrs.get('content', '')
        except Exception:
            pass
    return results


def pipeline3(question: str, top_k: int = PARAMS['top_k']) -> dict:
    emb = embedder.encode([question], normalize_embeddings=True)
    emb = np.array(emb, dtype=np.float32)
    faiss.normalize_L2(emb)
    _, idxs = index.search(emb, top_k)

    chunk_ids = [chunks[i]['id'] for i in idxs[0] if i < len(chunks)]

    start = time.time()
    tg_docs = _fetch_from_tg(chunk_ids)
    latency = round(time.time() - start, 3)

    # Fall back to local cache if TigerGraph fetch fails
    context_parts = []
    sources = []
    for cid in chunk_ids:
        text = tg_docs.get(cid) or chunk_id_map.get(cid, {}).get('text', '')
        if text:
            context_parts.append(text)
            sources.append(chunk_id_map.get(cid, {}).get('title', ''))

    context = '\n\n---\n\n'.join(context_parts)
    prompt = f'Context:\n{context}\n\nQuestion: {question}\nAnswer concisely.'

    t_gen = time.time()
    answer = groq_generate(client, prompt)
    latency += round(time.time() - t_gen, 3)

    p_tok = count_tokens(prompt)
    c_tok = count_tokens(answer)
    result = make_result('graphrag', answer, p_tok, c_tok, latency)
    result['sources'] = sources
    return result
