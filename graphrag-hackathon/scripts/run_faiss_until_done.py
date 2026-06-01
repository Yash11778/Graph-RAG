"""
Auto-restarts build_faiss.py until it exits 0 (success).
Each restart picks up from the last checkpoint.
"""
import subprocess
import sys
import time

PYTHON = r"C:\Users\yashd\AppData\Local\Programs\Python\Python314\python.exe"
SCRIPT = r"d:\HACKATHONS\Graph RAG\graphrag-hackathon\graphrag-hackathon\scripts\build_faiss.py"
CHUNKS = r"d:\HACKATHONS\Graph RAG\graphrag-hackathon\graphrag-hackathon\data\chunks\chunks.jsonl"
INDEX  = r"d:\HACKATHONS\Graph RAG\graphrag-hackathon\graphrag-hackathon\data\chunks\rag_index.faiss"
PKL    = r"d:\HACKATHONS\Graph RAG\graphrag-hackathon\graphrag-hackathon\data\chunks\chunks.pkl"

CMD = [
    PYTHON, SCRIPT,
    "--chunks", CHUNKS,
    "--index", INDEX,
    "--pkl", PKL,
    "--batch-size", "512",
    "--embed-batch-size", "8",
    "--checkpoint-every", "50",
]

attempt = 0
while True:
    attempt += 1
    print(f"\n{'='*60}", flush=True)
    print(f"Attempt {attempt} — starting build_faiss.py", flush=True)
    print(f"{'='*60}", flush=True)
    result = subprocess.run(CMD)
    if result.returncode == 0:
        print(f"\nSUCCESS on attempt {attempt}!", flush=True)
        sys.exit(0)
    else:
        print(f"\nFailed (exit {result.returncode}). Sleeping 10s then retrying...", flush=True)
        time.sleep(10)
