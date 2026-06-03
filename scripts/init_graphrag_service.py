"""
Step 2 of GraphRAG setup.
- Drops the old MyDatabase graph (custom schema)
- Creates a fresh MyDatabase graph
- Initializes the TigerGraph GraphRAG schema (DocumentChunk, Concept, Community, etc.)
- Installs all required GSQL queries (GraphRAG_Hybrid_Vector_Search, etc.)

Prerequisites:
  1. TigerGraph workspace running on tgcloud.io
  2. Docker Desktop running:  cd graphrag && docker compose up -d graphrag graphrag-ecc chat-history
  3. data/raw/graphrag_docs.jsonl exists (run prepare_graphrag_data.py first)
"""
import sys
import time
import requests
from pyTigerGraph import TigerGraphConnection

TG_HOST    = "https://tg-cddb2056-27e0-4388-87a8-8be8de814ed5.tg-2635877100.i.tgcloud.io"
TG_USER    = "yashdharme6@gmail.com"
TG_PASS    = os.getenv("TG_PASSWORD", "")
TG_TOKEN   = os.getenv("TG_PASSWORD", "")
GRAPH_NAME = "MyDatabase"
GRAPHRAG_SERVICE = "http://localhost:8003"


def wait_for_service(url: str, timeout: int = 60):
    print(f"Waiting for GraphRAG service at {url} ...")
    for _ in range(timeout):
        try:
            r = requests.get(f"{url}/", timeout=3)
            if r.status_code < 500:
                print("  Service is up.")
                return True
        except Exception:
            pass
        time.sleep(1)
    print("  ERROR: GraphRAG service did not start within timeout.")
    return False


def main():
    # 1. Check GraphRAG service is running
    if not wait_for_service(GRAPHRAG_SERVICE):
        print("\nStart Docker containers first:")
        print("  cd graphrag && docker compose up -d graphrag graphrag-ecc chat-history")
        sys.exit(1)

    # 2. Call GraphRAG service initialize endpoint directly with Basic auth.
    # Basic auth â†’ GraphRAG service uses get_db_connection_pwd â†’ reads ports from server_config.json (443).
    # Bearer token path hardcodes sslPort=14240 which is blocked on Savanna.
    print(f"\nCalling {GRAPHRAG_SERVICE}/{GRAPH_NAME}/graphrag/initialize ...")
    print("  This installs GraphRAG schema (DocumentChunk, Concept, Community) + GSQL queries.")
    print("  May take 2â€“5 minutes...")
    try:
        r = requests.post(
            f"{GRAPHRAG_SERVICE}/{GRAPH_NAME}/graphrag/initialize",
            auth=(TG_USER, TG_PASS),
            timeout=300,
        )
        if r.status_code in (200, 201):
            print(f"  Success: {r.json()}")
        else:
            print(f"  ERROR {r.status_code}: {r.text[:500]}")
            sys.exit(1)
    except Exception as e:
        print(f"  Init error: {e}")
        sys.exit(1)

    print("\nGraphRAG schema initialized successfully.")
    print("Next: run  python scripts/ingest_via_graphrag.py")


if __name__ == "__main__":
    main()

