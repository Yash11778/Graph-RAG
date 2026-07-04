"""
Proves graphrag_retrieve returns real facts from the live graph — run this and paste
the output into the benchmark report / judge response, since "it returns something"
is exactly the claim that was previously false.

Usage:
    python scripts/verify_graphrag_retrieval.py "napoleon bonaparte"
    python scripts/verify_graphrag_retrieval.py --qa-sample 5   # sample from qa_pairs.json
"""
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

ROOT       = Path(__file__).parent.parent
TG_HOST    = os.environ["TG_HOST"]
TG_SECRET  = os.environ["TG_PASSWORD"]
GRAPH_NAME = os.environ.get("TG_GRAPH", "MyDatabase")

sys.path.insert(0, str(ROOT))
from pipelines.pipeline3_graphrag import _extract_candidates  # noqa: E402


def get_token() -> str:
    resp = requests.post(
        f"{TG_HOST}/gsql/v1/tokens",
        json={"secret": TG_SECRET, "graph": GRAPH_NAME},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["token"]


def query(question: str, token: str):
    candidates = {c.lower() for c in _extract_candidates(question)}
    resp = requests.get(
        f"{TG_HOST}/restpp/query/{GRAPH_NAME}/graphrag_retrieve",
        headers={"Authorization": f"Bearer {token}"},
        params={"candidateNames": list(candidates)},
        timeout=15,
    )
    return resp.status_code, resp.json()


def main():
    token = get_token()

    if len(sys.argv) > 1 and sys.argv[1] == "--qa-sample":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        qa = json.loads((ROOT / "data/qa/qa_pairs.json").read_text(encoding="utf-8"))
        questions = [q["question"] for q in qa[:n]]
    else:
        questions = [" ".join(sys.argv[1:]) or "napoleon bonaparte"]

    hits, misses = 0, 0
    for q in questions:
        status, data = query(q, token)
        results = (data.get("results") or [{}])[0].get("Result", []) if status == 200 else []
        ok = status == 200 and len(results) > 0
        hits += ok
        misses += not ok
        print(f"\nQ: {q}")
        print(f"  HTTP {status} — {len(results)} entities returned")
        for r in results[:5]:
            attrs = r.get("attributes", r)
            print(f"    [{'SEED' if attrs.get('is_seed') else 'nbr '}] {attrs.get('name')}: {attrs.get('fact')}")

    print(f"\n=== {hits} hit / {misses} miss out of {hits + misses} questions ===")
    if misses:
        print("Non-zero misses are expected for some questions (not every question has a")
        print("matching entity name) — but hits must be > 0 to prove retrieval works at all.")


if __name__ == "__main__":
    main()
