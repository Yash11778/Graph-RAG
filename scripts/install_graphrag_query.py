"""
Installs scripts/graphrag_queries.gsql on the live Savanna graph.
Run once (and again any time the query is edited):
    python scripts/install_graphrag_query.py

Then verify with:
    python scripts/verify_graphrag_retrieval.py "napoleon"
"""
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

TG_HOST    = os.environ["TG_HOST"]
TG_SECRET  = os.environ["TG_PASSWORD"]
GRAPH_NAME = os.environ.get("TG_GRAPH", "MyDatabase")

GSQL_FILE = Path(__file__).parent / "graphrag_queries.gsql"


def get_token() -> str:
    resp = requests.post(
        f"{TG_HOST}/gsql/v1/tokens",
        json={"secret": TG_SECRET, "graph": GRAPH_NAME},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["token"]


def main():
    gsql = GSQL_FILE.read_text(encoding="utf-8")
    token = get_token()
    print("Installing graphrag_retrieve query on", GRAPH_NAME, "...")
    resp = requests.post(
        f"{TG_HOST}/gsql/v1/statements",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "text/plain"},
        data=gsql.encode("utf-8"),
        timeout=180,
    )
    print("Status:", resp.status_code)
    print(resp.text[:2000])
    if resp.status_code not in (200, 201):
        print("ERROR: query install failed")
        sys.exit(1)
    print("\ngraphrag_retrieve installed successfully.")


if __name__ == "__main__":
    main()
