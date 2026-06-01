"""
Re-ingest only the articles whose Content vertices had empty text in TigerGraph.
Uploads one article at a time (not batched) to avoid payload size limits.
Then triggers ECC forceupdate to re-embed all pending content.
"""
import json
import time
from pathlib import Path

import requests
from tqdm import tqdm

TG_HOST    = "https://tg-cddb2056-27e0-4388-87a8-8be8de814ed5.tg-2635877100.i.tgcloud.io"
TG_TOKEN   = os.getenv("TG_PASSWORD", "")
TG_GRAPH   = "MyDatabase"
TG_HEADERS = {"Authorization": f"Bearer {TG_TOKEN}"}
UPSERT_URL = f"{TG_HOST}/restpp/graph/{TG_GRAPH}"

GRAPHRAG_SERVICE = "http://localhost:8003"
GRAPHRAG_AUTH    = ("yashdharme6@gmail.com", os.getenv("TG_PASSWORD", ""))

# IDs extracted from ECC error logs
FAILED_IDS_FILE = Path("data/failed_content_ids.txt")
DATASET_FILE    = Path("data/raw/dataset.jsonl")


def get_failed_ids() -> set[str]:
    """Parse ECC docker logs to get failing content IDs."""
    import subprocess
    result = subprocess.run(
        ["docker", "logs", "graphrag-ecc"],
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    logs = result.stderr + result.stdout
    failed = set()
    for line in logs.splitlines():
        if "Error retrieving doc: content_" in line:
            part = line.split("content_")[1].split(" -->")[0].strip()
            failed.add(part)
    print(f"Found {len(failed)} failing content IDs in ECC logs")
    return failed


def upsert_single(doc_id: str, text: str) -> bool:
    """Upload a single Document + Content vertex."""
    now = int(time.time())
    content_id = f"content_{doc_id}"

    # Truncate text to 100k chars to avoid payload limits
    if len(text) > 100000:
        text = text[:100000]

    payload = {
        "vertices": {
            "Document": {
                doc_id: {
                    "epoch_added":      {"value": now},
                    "epoch_processing": {"value": 0},
                    "epoch_processed":  {"value": 0},
                }
            },
            "Content": {
                content_id: {
                    "text":        {"value": text},
                    "ctype":       {"value": "character"},
                    "epoch_added": {"value": now},
                }
            },
        },
        "edges": {
            "Document": {
                doc_id: {
                    "HAS_CONTENT": {
                        "Content": {
                            content_id: {}
                        }
                    }
                }
            }
        },
    }

    for attempt in range(3):
        try:
            r = requests.post(UPSERT_URL, headers=TG_HEADERS, json=payload, timeout=30)
            if r.status_code in (200, 201):
                return True
            print(f"  [tg] {doc_id} failed {r.status_code}: {r.text[:150]}")
        except Exception as e:
            print(f"  [tg] error on {doc_id}: {e}")
        time.sleep(2 ** attempt)
    return False


def trigger_ecc() -> None:
    print("\nTriggering ECC forceupdate...")
    try:
        r = requests.get(
            f"{GRAPHRAG_SERVICE}/{TG_GRAPH}/graphrag/forceupdate",
            auth=GRAPHRAG_AUTH,
            timeout=30,
        )
        print(f"  ECC response: {r.json()}")
    except Exception as e:
        print(f"  ECC trigger error: {e}")


def main():
    # Load all articles
    print("Loading articles...")
    with open(DATASET_FILE, encoding="utf-8") as f:
        articles = {str(a["id"]): a for a in (json.loads(l) for l in f)}
    print(f"  {len(articles)} articles loaded")

    # Get failing IDs
    failed_ids = get_failed_ids()
    to_fix = [aid for aid in failed_ids if aid in articles]
    missing = [aid for aid in failed_ids if aid not in articles]

    print(f"  {len(to_fix)} can be re-uploaded, {len(missing)} not found in dataset")

    if not to_fix:
        print("Nothing to fix.")
        trigger_ecc()
        return

    ok = 0
    fail = 0
    for doc_id in tqdm(to_fix, desc="Re-uploading"):
        text = articles[doc_id]["text"]
        if upsert_single(doc_id, text):
            ok += 1
        else:
            fail += 1
        time.sleep(0.1)  # small delay to avoid hammering TG

    print(f"\nDone: {ok} succeeded, {fail} failed")
    if ok > 0:
        trigger_ecc()
        print("\nECC triggered. Monitor with: docker logs graphrag-ecc -f")
        print("ECC will now chunk + embed the re-uploaded articles.")


if __name__ == "__main__":
    import os
    os.chdir(Path(__file__).parent.parent)
    main()

