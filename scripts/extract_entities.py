"""
Extract named-entity facts from every Chunk and store them in TigerGraph.

Graph structure built here:
  Article --HAS_CHUNK--> Chunk --HAS_ENTITY--> Entity
                                                  |
                         Entity <--ENTITY_COREF-->Entity  (same real-world entity, different chunks)

This is the core of true GraphRAG: entities act as cross-document connective tissue.
At query time, Pipeline 3 traverses Chunk → Entity and returns compact facts (~15 tokens each)
instead of raw chunk text (~256 tokens), achieving genuine ~85% token reduction.

Progress is saved to data/entity_progress.json so the script is safely resumable.
Batches 5 chunks per Groq call to stay within free-tier rate limits.
"""
import json
import os
import pickle
import re
import time
from collections import defaultdict
from pathlib import Path

import requests
from tqdm import tqdm

from pipelines.utils import setup_groq

# ── TigerGraph config ────────────────────────────────────────────────────────
TG_HOST  = 'https://tg-cddb2056-27e0-4388-87a8-8be8de814ed5.tg-2635877100.i.tgcloud.io'
TG_TOKEN = 'YOUR_TG_JWT_TOKEN_HERE'
TG_GRAPH = 'MyDatabase'
TG_HEADERS = {'Authorization': f'Bearer {TG_TOKEN}', 'Content-Type': 'application/json'}
UPSERT_URL = f'{TG_HOST}/restpp/graph/{TG_GRAPH}'

# ── Extraction config ─────────────────────────────────────────────────────────
CHUNKS_PER_BATCH  = 5    # chunks per Groq call
FACTS_PER_CHUNK   = 3    # entity facts to extract per chunk
TG_BATCH_SIZE     = 200  # vertices+edges per TigerGraph upsert
PROGRESS_FILE     = Path('data/entity_progress.json')
GROQ_RETRY_WAIT   = 35   # seconds to wait on 429

EXTRACT_PROMPT = """\
For each chunk below, extract exactly {n} key entity facts.
Rules:
- Each fact must name a specific entity (person, place, event, concept, organization).
- Each fact must be a single sentence, max 20 words.
- Facts must be self-contained (reader needs no other context to understand them).
- Output ONLY valid JSON — no markdown, no explanation.

Output format:
{{"results": [{{"chunk_id": "<id>", "facts": [{{"name": "<entity>", "fact": "<sentence>"}}]}}]}}

Chunks:
{chunks}"""


# ── Groq extraction ───────────────────────────────────────────────────────────

def extract_batch(client, batch: list[dict]) -> dict[str, list[dict]]:
    """Call Groq for a batch of chunks. Returns {chunk_id: [{name, fact}, ...]}."""
    chunks_text = '\n'.join(
        f'[{c["id"]}] {c["text"][:400]}'
        for c in batch
    )
    prompt = EXTRACT_PROMPT.format(n=FACTS_PER_CHUNK, chunks=chunks_text)

    for attempt in range(5):
        try:
            response = client.chat.completions.create(
                model='llama-3.3-70b-versatile',
                messages=[{'role': 'user', 'content': prompt}],
                temperature=0.0,
                max_tokens=800,
            )
            raw = response.choices[0].message.content.strip()
            # strip markdown code fences if present
            raw = re.sub(r'^```(?:json)?\s*', '', raw)
            raw = re.sub(r'\s*```$', '', raw)
            parsed = json.loads(raw)
            result = {}
            for item in parsed.get('results', []):
                cid = item.get('chunk_id', '')
                result[cid] = item.get('facts', [])
            return result
        except json.JSONDecodeError:
            # LLM returned malformed JSON — skip batch gracefully
            print(f'  [warn] JSON parse failed on attempt {attempt + 1}')
            if attempt == 4:
                return {}
        except Exception as e:
            if ('429' in str(e) or 'rate' in str(e).lower()) and attempt < 4:
                wait = GROQ_RETRY_WAIT * (attempt + 1)
                print(f'  [rate limit] waiting {wait}s...')
                time.sleep(wait)
            else:
                print(f'  [error] {e}')
                return {}
    return {}


# ── TigerGraph upsert ─────────────────────────────────────────────────────────

def upsert_tg(payload: dict) -> bool:
    for attempt in range(3):
        try:
            r = requests.post(UPSERT_URL, headers=TG_HEADERS, json=payload, timeout=30)
            if r.status_code in (200, 201):
                return True
            print(f'  [tg] upsert failed {r.status_code}: {r.text[:200]}')
        except Exception as e:
            print(f'  [tg] request error: {e}')
        time.sleep(2 ** attempt)
    return False


def flush_to_tg(entity_vertices: dict, has_entity_edges: dict, coref_edges: list) -> bool:
    """Send a batch of Entity vertices + HAS_ENTITY + ENTITY_COREF edges to TigerGraph."""
    payload: dict = {'vertices': {'Entity': entity_vertices}, 'edges': {}}

    if has_entity_edges:
        payload['edges']['Chunk'] = has_entity_edges

    if coref_edges:
        coref_payload: dict = {}
        for src, dst in coref_edges:
            coref_payload.setdefault(src, {}).setdefault('ENTITY_COREF', {}).setdefault('Entity', {})[dst] = {}
        payload['edges'].setdefault('Entity', {}).update(coref_payload)

    return upsert_tg(payload)


# ── Co-reference linking ───────────────────────────────────────────────────────

def normalize_name(name: str) -> str:
    return re.sub(r'\s+', '_', name.strip().lower())


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    # Load chunks
    print('Loading chunks...')
    chunks: list[dict] = pickle.load(open('data/chunks/chunks.pkl', 'rb'))
    print(f'  {len(chunks)} chunks loaded')

    # Load progress
    done_ids: set[str] = set()
    if PROGRESS_FILE.exists():
        done_ids = set(json.loads(PROGRESS_FILE.read_text()))
        print(f'  Resuming — {len(done_ids)} chunks already processed')

    remaining = [c for c in chunks if c['id'] not in done_ids]
    print(f'  {len(remaining)} chunks to process')

    if not remaining:
        print('All chunks already processed.')
        return

    client = setup_groq()

    # name → list of entity IDs (for ENTITY_COREF linking)
    name_to_entity_ids: dict[str, list[str]] = defaultdict(list)

    entity_buf: dict  = {}
    edge_buf: dict    = {}
    coref_buf: list   = []
    processed_ids     = list(done_ids)
    total_entities    = 0

    batches = [remaining[i:i + CHUNKS_PER_BATCH] for i in range(0, len(remaining), CHUNKS_PER_BATCH)]

    for batch in tqdm(batches, desc='Extracting entities', unit='batch'):
        extracted = extract_batch(client, batch)

        for chunk in batch:
            cid   = chunk['id']
            facts = extracted.get(cid, [])

            for idx, item in enumerate(facts[:FACTS_PER_CHUNK]):
                name = item.get('name', '').strip()
                fact = item.get('fact', '').strip()
                if not name or not fact:
                    continue

                entity_id = f'{cid}_e{idx}'

                entity_buf[entity_id] = {
                    'name':     {'value': name},
                    'fact':     {'value': fact},
                    'chunk_id': {'value': cid},
                }

                # HAS_ENTITY edge: Chunk → Entity
                edge_buf.setdefault(cid, {}) \
                        .setdefault('HAS_ENTITY', {}) \
                        .setdefault('Entity', {})[entity_id] = {}

                # Track for ENTITY_COREF (same entity name, different chunks)
                norm = normalize_name(name)
                for prev_id in name_to_entity_ids[norm]:
                    coref_buf.append((entity_id, prev_id))
                name_to_entity_ids[norm].append(entity_id)
                total_entities += 1

            processed_ids.append(cid)

        # Flush to TigerGraph every TG_BATCH_SIZE entities
        if len(entity_buf) >= TG_BATCH_SIZE:
            flush_to_tg(entity_buf, edge_buf, coref_buf)
            entity_buf.clear()
            edge_buf.clear()
            coref_buf.clear()
            # Save progress
            PROGRESS_FILE.write_text(json.dumps(processed_ids))

    # Final flush
    if entity_buf:
        flush_to_tg(entity_buf, edge_buf, coref_buf)

    PROGRESS_FILE.write_text(json.dumps(processed_ids))
    print(f'\nDone. {total_entities} entity facts stored in TigerGraph.')
    print('Next step: python scripts/verify_entities.py  (optional check)')
    print('           then restart the API server — pipeline3 will use entities automatically.')


if __name__ == '__main__':
    os.chdir(Path(__file__).parent.parent)
    main()
