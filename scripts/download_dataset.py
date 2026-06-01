"""
Download ~100M token Wikipedia dataset for Round 2.
Downloads HuggingFace parquet files directly via pyarrow — avoids
the dill/Python 3.14 incompatibility in the datasets library.

41 parquet files × ~160K articles each = ~6.7M articles total.
We stop after collecting enough to hit the token target.

Usage:
    python scripts/download_dataset.py
    python scripts/download_dataset.py --target-tokens 100000000
"""

import argparse
import io
import json
import time
from pathlib import Path

import pyarrow.parquet as pq
import requests
import tiktoken
from tqdm import tqdm

ROOT = Path(__file__).parent.parent.resolve()
OUT_FILE = ROOT / "data" / "raw" / "dataset_100m.jsonl"
PROGRESS_FILE = ROOT / "data" / "raw" / "download_progress.json"

enc = tiktoken.get_encoding("cl100k_base")

PARQUET_API = "https://huggingface.co/api/datasets/wikimedia/wikipedia/parquet/20231101.en/train"

KEEP_KEYWORDS = {
    "war", "battle", "siege", "invasion", "treaty", "revolution", "rebellion",
    "empire", "kingdom", "republic", "dynasty", "colony", "independence",
    "president", "prime minister", "king", "queen", "emperor", "general",
    "admiral", "senator", "governor", "chancellor", "pope",
    "born", "died", "founded", "established",
    "award", "prize", "championship", "tournament", "olympic", "election",
    "university", "institute", "organization", "corporation", "company",
    "party", "alliance", "coalition", "federation",
    "river", "mountain", "city", "country", "island", "continent", "capital",
    "discovered", "invented", "published", "directed by", "written by",
    "composed by", "designed by", "awarded",
}

MIN_TOKENS = 150
MAX_TOKENS = 4000


def load_progress():
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"files_done": [], "articles_written": 0, "total_tokens": 0, "done": False}


def save_progress(prog: dict):
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(prog, f)


def passes_filter(text: str, min_hits: int) -> bool:
    text_lower = text.lower()
    return sum(1 for kw in KEEP_KEYWORDS if kw in text_lower) >= min_hits


def fetch_parquet_urls() -> list[str]:
    r = requests.get(PARQUET_API, timeout=15)
    r.raise_for_status()
    return r.json()


def download_parquet(url: str) -> pq.ParquetFile:
    for attempt in range(3):
        try:
            r = requests.get(url, timeout=120)
            r.raise_for_status()
            return pq.ParquetFile(io.BytesIO(r.content))
        except Exception as e:
            if attempt == 2:
                raise
            print(f"  Retry {attempt+1} for {url}: {e}")
            time.sleep(5)


def main(target_tokens: int, max_articles: int, min_hits: int):
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    prog = load_progress()
    if prog.get("done"):
        print(f"Already complete: {prog['articles_written']:,} articles, "
              f"{prog['total_tokens']:,} tokens.")
        print(f"Delete {PROGRESS_FILE} to restart.")
        return

    files_done = set(prog["files_done"])
    total_tokens = prog["total_tokens"]
    total_articles = prog["articles_written"]

    print(f"Resuming: {total_articles:,} articles, {total_tokens/1e6:.1f}M tokens")
    print(f"Target: {target_tokens/1e6:.0f}M tokens | max {max_articles:,} articles")

    print("Fetching parquet file list...")
    urls = fetch_parquet_urls()
    print(f"Found {len(urls)} parquet files\n")

    mode = "a" if total_articles > 0 else "w"

    with open(OUT_FILE, mode, encoding="utf-8") as out:
        for file_idx, url in enumerate(urls):
            if url in files_done:
                print(f"  Skipping {file_idx}: already processed")
                continue

            if total_tokens >= target_tokens or total_articles >= max_articles:
                break

            print(f"Downloading file {file_idx+1}/{len(urls)}: {url.split('/')[-1]}")
            try:
                pf = download_parquet(url)
            except Exception as e:
                print(f"  SKIP — download failed: {e}")
                continue

            for batch in pf.iter_batches(batch_size=1000):
                df = batch.to_pydict()
                ids = df.get("id", [])
                titles = df.get("title", [])
                texts = df.get("text", [])

                for article_id, title, text in tqdm(
                    zip(ids, titles, texts),
                    total=len(ids),
                    desc=f"  File {file_idx+1}",
                    leave=False,
                ):
                    text = (text or "").strip()
                    if not text:
                        continue
                    tokens = len(enc.encode(text))
                    if tokens < MIN_TOKENS or tokens > MAX_TOKENS:
                        continue
                    if not passes_filter(text, min_hits):
                        continue

                    record = {
                        "id": str(article_id),
                        "title": title or "",
                        "text": text,
                    }
                    out.write(json.dumps(record, ensure_ascii=False) + "\n")
                    out.flush()
                    total_tokens += tokens
                    total_articles += 1

                    if total_tokens >= target_tokens or total_articles >= max_articles:
                        break

                if total_tokens >= target_tokens or total_articles >= max_articles:
                    break

            files_done.add(url)
            save_progress({
                "files_done": list(files_done),
                "articles_written": total_articles,
                "total_tokens": total_tokens,
                "done": False,
            })
            print(f"  >> {total_articles:,} articles | {total_tokens/1e6:.1f}M tokens")

    prog = {
        "files_done": list(files_done),
        "articles_written": total_articles,
        "total_tokens": total_tokens,
        "done": True,
    }
    save_progress(prog)

    print(f"\nDone!")
    print(f"Articles written : {total_articles:,}")
    print(f"Approx tokens    : {total_tokens:,} ({total_tokens/1e6:.1f}M)")
    print(f"Output           : {OUT_FILE}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-tokens", type=int, default=100_000_000)
    parser.add_argument("--max-articles", type=int, default=70_000)
    parser.add_argument("--min-hits", type=int, default=2)
    args = parser.parse_args()
    main(args.target_tokens, args.max_articles, args.min_hits)
