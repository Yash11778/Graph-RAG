import json
import os
import tiktoken
from datasets import load_dataset
from tqdm import tqdm

KEYWORDS = ['war','battle','military','invasion','campaign','general','army','navy','soldier']
OUTPUT_PATH = "data/raw/dataset.jsonl"
TOKEN_LIMIT = 2_300_000 

os.makedirs("data/raw", exist_ok=True)
    
enc = tiktoken.get_encoding("cl100k_base")

dataset = load_dataset(
    "wikimedia/wikipedia",
    "20231101.en",
    split="train",
    streaming=True,
)

total_docs = 0
total_tokens = 0

with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    pbar = tqdm(desc="Downloading", unit="docs")
    for article in dataset:
        if total_tokens >= TOKEN_LIMIT:
            break
        title_lower = article["title"].lower()
        if not any(kw in title_lower for kw in KEYWORDS):
            continue
        if len(article["text"]) < 500:
            continue
        tokens = enc.encode(article["text"])
        record = {
            "id": article["id"],
            "title": article["title"],
            "text": article["text"],
        }
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
        total_docs += 1
        total_tokens += len(tokens)
        pbar.update(1)
        pbar.set_postfix(tokens=f"{total_tokens:,}")
    pbar.close()

print(f"Total docs: {total_docs}")
print(f"Total tokens: {total_tokens:,}")
