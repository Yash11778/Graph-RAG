import pickle
import sys
from collections import defaultdict

import requests
from tqdm import tqdm

TG_HOST = 'https://tg-cddb2056-27e0-4388-87a8-8be8de814ed5.tg-2635877100.i.tgcloud.io'
TG_TOKEN = 'YOUR_TG_JWT_TOKEN_HERE'
TG_GRAPH = 'MyDatabase'
HEADERS = {'Authorization': f'Bearer {TG_TOKEN}', 'Content-Type': 'application/json'}
UPSERT_URL = f'{TG_HOST}/restpp/graph/{TG_GRAPH}'
BATCH_SIZE = 100


def upsert(payload: dict) -> bool:
    r = requests.post(UPSERT_URL, headers=HEADERS, json=payload, timeout=30)
    if r.status_code not in (200, 201):
        print(f'  upsert failed {r.status_code}: {r.text[:200]}')
        return False
    return True


def ingest_batch(articles: dict, chunks: list):
    vertices_article = {}
    vertices_chunk = {}
    edges_has_chunk = {}
    edges_next_chunk = {}

    for doc_id, title in articles.items():
        vertices_article[doc_id] = {'title': {'value': title}}

    for c in chunks:
        vertices_chunk[c['id']] = {
            'text': {'value': c['text']},
            'chunk_index': {'value': c['chunk_index']},
        }
        edges_has_chunk.setdefault(c['doc_id'], {}).setdefault('HAS_CHUNK', {}).setdefault('Chunk', {})[c['id']] = {}

    for c in chunks:
        if c.get('next_id'):
            edges_next_chunk.setdefault(c['id'], {}).setdefault('NEXT_CHUNK', {}).setdefault('Chunk', {})[c['next_id']] = {}

    payload = {
        'vertices': {
            'Article': vertices_article,
            'Chunk': vertices_chunk,
        },
        'edges': {
            'Article': edges_has_chunk,
            'Chunk': edges_next_chunk,
        },
    }
    return upsert(payload)


def main():
    print('Loading chunks...')
    chunks_raw = pickle.load(open('data/chunks/chunks.pkl', 'rb'))
    print(f'Loaded {len(chunks_raw)} chunks from {len(set(c["doc_id"] for c in chunks_raw))} articles')

    by_doc = defaultdict(list)
    for c in chunks_raw:
        by_doc[c['doc_id']].append(c)

    enriched = []
    articles = {}

    for doc_id, doc_chunks in by_doc.items():
        doc_chunks_sorted = sorted(doc_chunks, key=lambda c: int(c['id'].split('_c')[-1]))
        articles[doc_id] = doc_chunks_sorted[0]['source']
        for i, c in enumerate(doc_chunks_sorted):
            entry = {
                'id': c['id'],
                'text': c['text'],
                'doc_id': doc_id,
                'chunk_index': i,
                'next_id': doc_chunks_sorted[i + 1]['id'] if i + 1 < len(doc_chunks_sorted) else None,
            }
            enriched.append(entry)

    print(f'Ingesting {len(enriched)} chunks into TigerGraph...')
    total_ok = 0
    total_fail = 0

    for i in tqdm(range(0, len(enriched), BATCH_SIZE), desc='Batches'):
        batch = enriched[i:i + BATCH_SIZE]
        batch_articles = {c['doc_id']: articles[c['doc_id']] for c in batch}
        ok = ingest_batch(batch_articles, batch)
        if ok:
            total_ok += len(batch)
        else:
            total_fail += len(batch)

    print(f'\nDone. ingested={total_ok}  failed={total_fail}')
    if total_fail > 0:
        print('WARNING: some batches failed — re-run to retry')
        sys.exit(1)


if __name__ == '__main__':
    main()
