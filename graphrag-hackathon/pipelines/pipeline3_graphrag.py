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

MAX_CONTEXT_TOKENS = 300
MAX_ANSWER_TOKENS = 150
FAISS_TOP_K = 2

embedder = SentenceTransformer('all-MiniLM-L6-v2')
index = faiss.read_index('data/chunks/rag_index.faiss')
chunks = pickle.load(open('data/chunks/chunks.pkl', 'rb'))
chunk_id_map = {c['id']: c for c in chunks}
client = setup_groq()


def _tg_get(path: str) -> dict | None:
    try:
        r = requests.get(f'{TG_HOST}{path}', headers=TG_HEADERS, timeout=8)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def _fetch_chunk(chunk_id: str) -> dict | None:
    data = _tg_get(f'/restpp/graph/{TG_GRAPH}/vertices/Chunk/{chunk_id}')
    if data:
        results = data.get('results', [])
        if results:
            attrs = results[0].get('attributes', {})
            return {'id': chunk_id, 'text': attrs.get('text', ''), 'chunk_index': attrs.get('chunk_index', 0)}
    local = chunk_id_map.get(chunk_id)
    if local:
        try:
            idx = int(chunk_id.split('_c')[-1])
        except ValueError:
            idx = 0
        return {'id': chunk_id, 'text': local['text'], 'chunk_index': idx}
    return None


def _fetch_neighbor_ids(chunk_id: str) -> list[str]:
    data = _tg_get(f'/restpp/graph/{TG_GRAPH}/edges/Chunk/{chunk_id}/NEXT_CHUNK')
    if data:
        return [e['to_id'] for e in data.get('results', [])]
    return []


def _expand_via_graph(seed_ids: list[str]) -> list[dict]:
    seen: set[str] = set()
    collected: list[dict] = []

    for seed_id in seed_ids:
        if seed_id in seen:
            continue
        seed_chunk = _fetch_chunk(seed_id)
        if not seed_chunk:
            continue
        seen.add(seed_id)
        collected.append(seed_chunk)

        neighbor_ids = _fetch_neighbor_ids(seed_id)
        for nid in neighbor_ids:
            if nid in seen:
                continue
            seen.add(nid)
            nc = _fetch_chunk(nid)
            if nc:
                collected.append(nc)

    collected.sort(key=lambda x: (chunk_id_map.get(x['id'], {}).get('source', ''), x['chunk_index']))
    return collected


def pipeline3(question: str, top_k: int = FAISS_TOP_K) -> dict:
    emb = embedder.encode([question], normalize_embeddings=True)
    emb = np.array(emb, dtype=np.float32)
    faiss.normalize_L2(emb)
    _, idxs = index.search(emb, top_k)
    seed_ids = [chunks[i]['id'] for i in idxs[0] if i < len(chunks)]

    t_start = time.time()
    expanded = _expand_via_graph(seed_ids)
    tg_latency = round(time.time() - t_start, 3)

    context_parts: list[str] = []
    sources: list[str] = []
    budget = MAX_CONTEXT_TOKENS
    for item in expanded:
        tok = count_tokens(item['text'])
        if tok > budget:
            words = item['text'].split()
            approx_chars = int(len(item['text']) * budget / tok)
            trimmed = item['text'][:approx_chars].rsplit(' ', 1)[0]
            if trimmed:
                context_parts.append(trimmed)
                sources.append(chunk_id_map.get(item['id'], {}).get('source', ''))
            break
        context_parts.append(item['text'])
        sources.append(chunk_id_map.get(item['id'], {}).get('source', ''))
        budget -= tok
        if budget <= 0:
            break

    context = '\n\n---\n\n'.join(context_parts)
    prompt = f'Context:\n{context}\n\nQuestion: {question}\nAnswer in 1-2 sentences.'

    t_gen = time.time()
    answer = groq_generate(client, prompt, max_tokens=MAX_ANSWER_TOKENS)
    gen_latency = round(time.time() - t_gen, 3)

    p_tok = count_tokens(prompt)
    c_tok = count_tokens(answer)
    result = make_result('graphrag', answer, p_tok, c_tok, round(tg_latency + gen_latency, 3))
    result['sources'] = list(dict.fromkeys(sources))
    result['graph_expanded_chunks'] = len(expanded)
    result['seed_chunks'] = len(seed_ids)
    return result
