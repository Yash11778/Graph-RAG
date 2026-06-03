"""
Ingest chunks into TigerGraph GraphRAG service.
Resumable — tracks progress in data/chunks/ingest_progress_tg.json.
Rate-limited to avoid overwhelming the GraphRAG service.

The GraphRAG service must be running (GRAPHRAG_SERVICE in .env or localhost:8003).

Usage:
    python scripts/ingest_graphrag.py
    python scripts/ingest_graphrag.py --chunks data/chunks/chunks.jsonl --workers 4
"""

import argparse
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

ROOT = Path(__file__).parent.parent.resolve()
PROGRESS_FILE = ROOT / "data" / "chunks" / "ingest_progress_tg.json"
FAILED_FILE = ROOT / "data" / "chunks" / "failed_ingestion.json"


def load_progress() -> set:
    if PROGRESS_FILE.exists():
        try:
            with open(PROGRESS_FILE, encoding="utf-8") as f:
                data = json.load(f)
                return set(data) if data else set()
        except (json.JSONDecodeError, ValueError):
            return set()
    return set()


def save_progress(done_ids: set):
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(list(done_ids), f)


def ingest_one(base: str, chunk: dict, timeout: int = 30) -> tuple[str, bool, str]:
    chunk_id = chunk["id"]
    try:
        payload = {
            "text": chunk["text"],
            "doc_id": chunk_id,
            "metadata": {"source": chunk.get("source", "")},
        }
        r = requests.post(f"{base}/ingest", json=payload, timeout=timeout)
        r.raise_for_status()
        return chunk_id, True, ""
    except Exception as e:
        return chunk_id, False, str(e)


def main(chunks_path: str, base: str, workers: int, save_every: int):
    # Health check
    try:
        resp = requests.get(f"{base}/health", timeout=10)
        assert resp.status_code == 200
        print(f"GraphRAG service OK at {base}")
    except Exception as e:
        print(f"ERROR: GraphRAG service not reachable at {base}: {e}")
        print("Make sure TigerGraph GraphRAG service is running.")
        return

    done_ids = load_progress()
    print(f"Already ingested: {len(done_ids):,} — resuming from there")

    # Count total without loading all into RAM
    print(f"Counting chunks in {chunks_path}...")
    total = sum(1 for _ in open(chunks_path, encoding="utf-8"))
    remaining = total - len(done_ids)
    print(f"Total: {total:,} | Remaining: {remaining:,}\n")

    failed = []
    ingested = len(done_ids)
    i = 0

    with ThreadPoolExecutor(max_workers=workers) as pool, \
         tqdm(total=remaining, desc="Ingesting", unit="chunks") as pbar:

        futures = {}

        def submit_batch(batch):
            for chunk in batch:
                futures[pool.submit(ingest_one, base, chunk)] = chunk

        # Stream chunks and submit in small batches to keep memory low
        batch = []
        batch_size = workers * 8
        with open(chunks_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                chunk = json.loads(line)
                if chunk["id"] in done_ids:
                    continue
                batch.append(chunk)
                if len(batch) >= batch_size:
                    submit_batch(batch)
                    batch = []

        if batch:
            submit_batch(batch)

        for future in as_completed(futures):
            chunk_id, ok, err = future.result()
            if ok:
                done_ids.add(chunk_id)
                ingested += 1
            else:
                failed.append({"id": chunk_id, "error": err})
            pbar.update(1)
            pbar.set_postfix(ok=ingested, fail=len(failed))
            i += 1

            if i % save_every == 0:
                save_progress(done_ids)
                with open(FAILED_FILE, "w") as f:
                    json.dump(failed, f)

    save_progress(done_ids)
    with open(FAILED_FILE, "w") as f:
        json.dump(failed, f)

    print(f"\nIngestion complete")
    print(f"  Ingested : {ingested:,}")
    print(f"  Failed   : {len(failed):,}")
    print(f"  Progress : {PROGRESS_FILE}")
    print(f"  Failures : {FAILED_FILE}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunks", default="data/chunks/chunks.jsonl")
    parser.add_argument("--base",
                        default=os.getenv("GRAPHRAG_SERVICE", "http://localhost:8003"))
    parser.add_argument("--workers", type=int, default=4,
                        help="Parallel ingest threads (reduce if hitting rate limits)")
    parser.add_argument("--save-every", type=int, default=500,
                        help="Save progress every N chunks")
    args = parser.parse_args()
    main(args.chunks, args.base, args.workers, args.save_every)
