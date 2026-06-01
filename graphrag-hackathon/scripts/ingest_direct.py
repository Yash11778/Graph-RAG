"""
Fast direct ingestion into TigerGraph — bypasses the Docker service's slow LLM
entity extraction pipeline. Embeds chunks in batches via Gemini, then upserts
DocumentChunk + Content + Document vertices directly via pyTigerGraph REST API.

At 100 texts/batch and 20 workers this hits ~1500 RPM (Gemini limit) and
finishes all 464K chunks in ~1 hour.

Usage:
    python scripts/ingest_direct.py
    python scripts/ingest_direct.py --workers 20 --embed-batch 100
"""

import argparse
import json
import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

ROOT = Path(__file__).parent.parent.resolve()
PROGRESS_FILE = ROOT / "data" / "chunks" / "ingest_direct_progress.json"
FAILED_FILE   = ROOT / "data" / "chunks" / "ingest_direct_failed.json"

TG_HOST     = os.getenv("TG_HOST",     "")
TG_USER     = os.getenv("TG_USERNAME", "")
TG_PASS     = os.getenv("TG_PASSWORD", "")
TG_GRAPH    = os.getenv("TG_GRAPH",    "MyDatabase")
TG_TOKEN    = os.getenv("TG_PASSWORD", "")
GEMINI_KEY  = os.getenv("GEMINI_API_KEY", "")
EMBED_MODEL = "models/gemini-embedding-001"

_lock = threading.Lock()


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


def get_conn():
    import pyTigerGraph as tg
    conn = tg.TigerGraphConnection(
        host=TG_HOST,
        username=TG_USER,
        password=TG_PASS,
        graphname=TG_GRAPH,
        apiToken=TG_TOKEN,
    )
    return conn


def embed_batch(texts: list[str], client) -> list[list[float]]:
    """Embed a batch of texts via Gemini. Returns list of embedding vectors."""
    from google.genai import types
    resp = client.models.embed_content(
        model=EMBED_MODEL,
        contents=texts,
        config=types.EmbedContentConfig(output_dimensionality=1536),
    )
    return [e.values for e in resp.embeddings]


def upsert_batch(conn, chunks: list[dict], embeddings: list[list[float]]) -> tuple[int, list]:
    """Upsert DocumentChunk + Content + Document vertices for a batch."""
    epoch_now = int(time.time())
    failed = []

    # Build bulk upsert payload using TigerGraph's upsertData format
    # Vector attributes require {"value": [...]} format
    vertices: dict = {
        "DocumentChunk": {},
        "Content": {},
        "Document": {},
    }
    edges: dict = {
        "DocumentChunk": {"HAS_CONTENT": {"Content": {}},
                          "IS_AFTER":    {"DocumentChunk": {}},
                          "HAS_CHILD":   {"Document": {}}},
        "Document":      {"HAS_CHILD":   {"DocumentChunk": {}}},
    }

    for chunk, emb in zip(chunks, embeddings):
        cid = chunk["id"]
        parts = cid.rsplit("_c", 1)
        doc_id = parts[0] if len(parts) == 2 else cid
        try:
            idx = int(parts[1]) if len(parts) == 2 else 0
        except ValueError:
            idx = 0

        vertices["DocumentChunk"][cid] = {
            "embedding":         {"value": list(emb)},
            "idx":               {"value": idx},
            "epoch_added":       {"value": epoch_now},
        }
        vertices["Content"][cid] = {
            "text":        {"value": chunk["text"]},
            "epoch_added": {"value": epoch_now},
        }
        vertices["Document"][doc_id] = {"epoch_added": {"value": epoch_now}}

        # edges
        edges["DocumentChunk"]["HAS_CONTENT"]["Content"][cid] = \
            edges["DocumentChunk"]["HAS_CONTENT"]["Content"].get(cid, {})
        edges["Document"]["HAS_CHILD"]["DocumentChunk"] = \
            edges["Document"]["HAS_CHILD"].get("DocumentChunk", {})
        edges["Document"]["HAS_CHILD"]["DocumentChunk"][cid] = {}
        if idx > 0:
            prev_id = f"{doc_id}_c{idx - 1}"
            edges["DocumentChunk"]["IS_AFTER"]["DocumentChunk"][cid] = \
                {prev_id: {}}

    try:
        payload = json.dumps({"vertices": vertices})
        conn.upsertData(payload)
        ok = len(chunks)
    except Exception as e:
        failed = [{"ids": [c["id"] for c in chunks], "error": str(e)}]
        ok = 0

    return ok, failed


def process_batch(args):
    """Worker function: embed + upsert one batch. Returns (ok_count, failed_list, chunk_ids)."""
    batch, worker_conn, gemini_client = args
    chunk_ids = [c["id"] for c in batch]
    texts = [c["text"] for c in batch]

    # Retry embed up to 3 times
    embeddings = None
    for attempt in range(3):
        try:
            embeddings = embed_batch(texts, gemini_client)
            break
        except Exception as e:
            if attempt == 2:
                return 0, [{"ids": chunk_ids, "error": f"embed failed: {e}"}], chunk_ids
            time.sleep(2 ** attempt)

    ok, failed = upsert_batch(worker_conn, batch, embeddings)
    return ok, failed, chunk_ids


def main(chunks_path: str, workers: int, embed_batch_size: int, save_every: int):
    from google import genai

    print(f"Connecting to TigerGraph at {TG_HOST}...")
    # Create one connection per worker to avoid threading issues
    conns = []
    for i in range(workers):
        try:
            c = get_conn()
            conns.append(c)
            if i == 0:
                print("TigerGraph connected OK")
        except Exception as e:
            print(f"  Worker {i} conn failed: {e}")
            if i == 0:
                raise

    gemini_clients = [genai.Client(api_key=GEMINI_KEY) for _ in range(workers)]

    done_ids = load_progress()
    print(f"Already ingested: {len(done_ids):,} — resuming")

    print(f"Counting chunks...")
    total = sum(1 for _ in open(chunks_path, encoding="utf-8"))
    remaining = total - len(done_ids)
    print(f"Total: {total:,} | Remaining: {remaining:,}")
    print(f"Workers: {workers} | Embed batch: {embed_batch_size}\n")

    all_failed = []
    ingested = len(done_ids)
    batches_done = 0

    # Pre-load all remaining chunks into batches (streaming)
    batches = []
    current_batch = []
    with open(chunks_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            chunk = json.loads(line)
            if chunk["id"] in done_ids:
                continue
            current_batch.append(chunk)
            if len(current_batch) >= embed_batch_size:
                batches.append(current_batch)
                current_batch = []
    if current_batch:
        batches.append(current_batch)

    print(f"Prepared {len(batches):,} batches of {embed_batch_size}")

    worker_idx = 0
    with ThreadPoolExecutor(max_workers=workers) as pool, \
         tqdm(total=remaining, desc="Ingesting", unit="chunks") as pbar:

        futures = {}
        for batch in batches:
            conn = conns[worker_idx % len(conns)]
            client = gemini_clients[worker_idx % len(gemini_clients)]
            worker_idx += 1
            f = pool.submit(process_batch, (batch, conn, client))
            futures[f] = batch

        for future in as_completed(futures):
            ok, failed, chunk_ids = future.result()
            ingested += ok
            all_failed.extend(failed)
            if ok > 0:
                with _lock:
                    done_ids.update(chunk_ids[:ok])
            pbar.update(len(futures[future]))
            pbar.set_postfix(ok=ingested, fail=len(all_failed))
            batches_done += 1

            if batches_done % save_every == 0:
                with _lock:
                    save_progress(done_ids)
                with open(FAILED_FILE, "w") as ff:
                    json.dump(all_failed, ff)

    save_progress(done_ids)
    with open(FAILED_FILE, "w") as f:
        json.dump(all_failed, f)

    print(f"\n{'='*50}")
    print(f"Ingestion complete")
    print(f"  Ingested : {ingested:,}")
    print(f"  Failed   : {len(all_failed):,}")
    print(f"  Progress : {PROGRESS_FILE}")
    print(f"{'='*50}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunks",       default="data/chunks/chunks.jsonl")
    parser.add_argument("--workers",      type=int, default=20)
    parser.add_argument("--embed-batch",  type=int, default=100,
                        help="Texts per Gemini embed call (max 100)")
    parser.add_argument("--save-every",   type=int, default=50,
                        help="Save progress every N batches")
    args = parser.parse_args()
    main(args.chunks, args.workers, args.embed_batch, args.save_every)
