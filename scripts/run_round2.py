"""
Round 2 orchestration script — runs the full pipeline in order:
  1. Preprocess (chunk dataset_100m.jsonl)
  2. Build FAISS index
  3. Generate QA pairs
  4. Ingest into TigerGraph GraphRAG
  5. Count tokens with Gemini
  6. Run evaluation

Run after download_dataset.py has finished.

Usage:
    python scripts/run_round2.py
    python scripts/run_round2.py --skip-ingest   # if TG already ingested
    python scripts/run_round2.py --skip-gemini   # if token count already done
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.resolve()
os.chdir(ROOT)


def run(cmd: list[str], desc: str):
    print(f"\n{'='*60}")
    print(f"STEP: {desc}")
    print(f"CMD : {' '.join(cmd)}")
    print(f"{'='*60}")
    result = subprocess.run(cmd, cwd=str(ROOT))
    if result.returncode != 0:
        print(f"\nERROR: '{desc}' exited with code {result.returncode}")
        sys.exit(result.returncode)
    print(f"OK: {desc}")


def main(skip_ingest: bool, skip_gemini: bool):
    dataset = ROOT / "data" / "raw" / "dataset_100m.jsonl"
    if not dataset.exists():
        print(f"ERROR: {dataset} not found. Run download_dataset.py first.")
        sys.exit(1)

    # 1. Preprocess
    run([sys.executable, "scripts/preprocess.py",
         "--input", "data/raw/dataset_100m.jsonl",
         "--output", "data/chunks/chunks.jsonl"],
        "Preprocess: chunk dataset into 256-token chunks")

    # 2. Build FAISS index
    run([sys.executable, "scripts/build_faiss.py",
         "--chunks", "data/chunks/chunks.jsonl"],
        "Build FAISS index for Basic RAG")

    # 3. Generate QA pairs
    run([sys.executable, "scripts/generate_qa_pairs.py",
         "--input", "data/raw/dataset_100m.jsonl",
         "--output", "data/qa/qa_pairs.json",
         "--target", "75"],
        "Generate 75 QA pairs from dataset")

    # 4. TigerGraph ingest
    if not skip_ingest:
        run([sys.executable, "scripts/ingest_graphrag.py",
             "--chunks", "data/chunks/chunks.jsonl",
             "--workers", "4"],
            "Ingest chunks into TigerGraph GraphRAG")
    else:
        print("\nSKIPPING TigerGraph ingest (--skip-ingest)")

    # 5. Gemini token count
    if not skip_gemini:
        run([sys.executable, "scripts/count_tokens_gemini.py",
             "--input", "data/raw/dataset_100m.jsonl"],
            "Official Gemini token count")
    else:
        print("\nSKIPPING Gemini token count (--skip-gemini)")

    # 6. Evaluation
    run([sys.executable, "eval/evaluate.py"],
        "Run full benchmark evaluation")

    print("\n" + "="*60)
    print("ROUND 2 PIPELINE COMPLETE")
    print("Results: eval/results/eval_results.csv")
    print("Token count: data/token_count_official.json")
    print("="*60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-ingest", action="store_true",
                        help="Skip TigerGraph ingestion (if already done)")
    parser.add_argument("--skip-gemini", action="store_true",
                        help="Skip Gemini token count (if already done)")
    args = parser.parse_args()
    main(args.skip_ingest, args.skip_gemini)
