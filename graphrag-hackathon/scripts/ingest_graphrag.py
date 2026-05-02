import json
import time

import requests
from tqdm import tqdm

BASE = 'http://localhost:8010'

resp = requests.get(f'{BASE}/health', timeout=10)
assert resp.status_code == 200, f'Health check failed: {resp.status_code}'
print('Health check OK')

chunks = []
with open('data/chunks/chunks.jsonl', encoding='utf-8') as f:
    for line in f:
        chunks.append(json.loads(line))

print(f'Loaded {len(chunks)} chunks')

failed_ids = []
ingested = 0

for i, chunk in enumerate(tqdm(chunks, desc='Ingesting')):
    try:
        payload = {
            'text': chunk['text'],
            'doc_id': chunk['id'],
            'metadata': {'source': chunk.get('source', '')},
        }
        r = requests.post(f'{BASE}/ingest', json=payload, timeout=30)
        r.raise_for_status()
        ingested += 1
    except Exception as e:
        failed_ids.append(chunk.get('id', i))

    if (i + 1) % 500 == 0:
        time.sleep(2)

    if (i + 1) % 1000 == 0:
        print(f'Progress: {i + 1}/{len(chunks)} — ingested={ingested} failed={len(failed_ids)}')

with open('data/chunks/failed_ingestion.json', 'w') as f:
    json.dump(failed_ids, f)

print(f'Done. ingested={ingested} failed={len(failed_ids)}')
