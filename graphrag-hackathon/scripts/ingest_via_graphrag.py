"""
Step 3 of GraphRAG setup.
Ingests Wikipedia articles into TigerGraph using the GraphRAG schema,
then triggers ECC (Eventual Consistency Checker) to:
  - Chunk each Document (characters chunker via GraphRAG service config)
  - Generate Gemini embeddings for each DocumentChunk
  - Extract Entity / RelationshipType vertices
  - Build Community summaries (multi-hop graph reasoning)

Why direct REST upsert (not GSQL loading job):
  TigerGraph Savanna (cloud) loading jobs require the data file to be
  accessible on the TigerGraph server itself. Our data is local. Direct
  REST upsert works correctly with Savanna from any network location.

Graph structure written here:
  Document --HAS_CONTENT--> Content   (ECC reads text from here)
  ECC then creates: Document --HAS_CHILD--> DocumentChunk --HAS_CONTENT--> Content
                    DocumentChunk has embedding (Gemini)
                    DocumentChunk --CONTAINS_ENTITY--> Entity
                    Entity --IN_COMMUNITY--> Community
"""
import json
import sys
import time
from pathlib import Path

import requests
from tqdm import tqdm

TG_HOST    = "https://tg-cddb2056-27e0-4388-87a8-8be8de814ed5.tg-2635877100.i.tgcloud.io"
TG_TOKEN   = "YOUR_TG_JWT_TOKEN_HERE"
TG_GRAPH   = "MyDatabase"
TG_HEADERS = {"Authorization": f"Bearer {TG_TOKEN}"}
UPSERT_URL = f"{TG_HOST}/restpp/graph/{TG_GRAPH}"

GRAPHRAG_SERVICE = "http://localhost:8003"
GRAPHRAG_AUTH    = ("yashdharme6@gmail.com", "YOUR_TG_SECRET_HERE")

INPUT_FILE  = Path("data/raw/dataset.jsonl")
BATCH_SIZE  = 50
PROGRESS_FILE = Path("data/ingest_progress.json")


def upsert(payload: dict) -> bool:
    for attempt in range(3):
        try:
            r = requests.post(UPSERT_URL, headers=TG_HEADERS, json=payload, timeout=30)
            if r.status_code in (200, 201):
                return True
            print(f"  [tg] upsert failed {r.status_code}: {r.text[:200]}")
        except Exception as e:
            print(f"  [tg] error: {e}")
        time.sleep(2 ** attempt)
    return False


def ingest_batch(docs: list[dict]) -> bool:
    now = int(time.time())
    vertices_doc = {}
    vertices_content = {}
    edges_doc_to_content = {}

    for doc in docs:
        doc_id     = str(doc["id"])
        content_id = f"content_{doc_id}"

        vertices_doc[doc_id] = {
            "epoch_added":      {"value": now},
            "epoch_processing": {"value": 0},
            "epoch_processed":  {"value": 0},
        }
        vertices_content[content_id] = {
            "text":        {"value": doc["text"]},
            "ctype":       {"value": "character"},
            "epoch_added": {"value": now},
        }
        edges_doc_to_content.setdefault(doc_id, {}) \
            .setdefault("HAS_CONTENT", {}) \
            .setdefault("Content", {})[content_id] = {}

    payload = {
        "vertices": {
            "Document": vertices_doc,
            "Content":  vertices_content,
        },
        "edges": {
            "Document": edges_doc_to_content,
        },
    }
    return upsert(payload)


def trigger_ecc() -> None:
    print("\nTriggering ECC (Eventual Consistency Checker)...")
    print("  ECC will: chunk documents -> embed with Gemini -> extract entities -> build community graph")
    print("  This runs in the background. Monitor: docker logs graphrag-ecc -f")
    try:
        r = requests.get(
            f"{GRAPHRAG_SERVICE}/{TG_GRAPH}/graphrag/forceupdate",
            auth=GRAPHRAG_AUTH,
            timeout=30,
        )
        print(f"  ECC status: {r.json()}")
    except Exception as e:
        print(f"  ECC warning: {e}")


def main():
    print("Loading articles...")
    with open(INPUT_FILE, encoding="utf-8") as f:
        articles = [json.loads(l) for l in f]
    print(f"  {len(articles)} articles loaded")

    # Load progress
    done_ids: set[str] = set()
    if PROGRESS_FILE.exists():
        done_ids = set(json.loads(PROGRESS_FILE.read_text()))
        print(f"  Resuming - {len(done_ids)} already ingested")

    remaining = [a for a in articles if str(a["id"]) not in done_ids]
    print(f"  {len(remaining)} articles to ingest\n")

    if not remaining:
        print("All articles already ingested. Triggering ECC...")
        trigger_ecc()
        return

    done_list = list(done_ids)
    failed = 0

    for i in tqdm(range(0, len(remaining), BATCH_SIZE), desc="Ingesting", unit="batch"):
        batch = remaining[i:i + BATCH_SIZE]
        ok = ingest_batch(batch)
        if ok:
            done_list.extend(str(a["id"]) for a in batch)
            PROGRESS_FILE.write_text(json.dumps(done_list))
        else:
            failed += len(batch)

    total_ingested = len(done_list) - len(done_ids)
    print(f"\nIngested {total_ingested} articles. Failed: {failed}")

    if failed == 0:
        trigger_ecc()
        print("\nDone! ECC is now processing documents in the background.")
        print("ECC builds: DocumentChunk vertices + embeddings + Entity graph + Community graph")
        print("Monitor progress: docker logs graphrag-ecc -f")
        print("Next: wait ~20-40 min for ECC, then run  uvicorn api.app:app --reload --port 8080")
    else:
        print(f"WARNING: {failed} articles failed. Re-run to retry.")


if __name__ == "__main__":
    import os
    os.chdir(Path(__file__).parent.parent)
    main()
