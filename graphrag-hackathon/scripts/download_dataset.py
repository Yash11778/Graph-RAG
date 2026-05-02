import json
import os

from datasets import load_dataset
from dotenv import load_dotenv

load_dotenv()

OUTPUT_PATH = "data/raw/wikipedia.jsonl"
NUM_ARTICLES = 1000

os.makedirs("data/raw", exist_ok=True)

dataset = load_dataset(
    "wikipedia",
    "20220301.en",
    split="train",
    streaming=True,
    trust_remote_code=True,
)

count = 0
with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    for article in dataset:
        if count >= NUM_ARTICLES:
            break
        record = {
            "id": article["id"],
            "title": article["title"],
            "text": article["text"],
        }
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
        count += 1
        if count % 100 == 0:
            print(f"Downloaded {count}/{NUM_ARTICLES} articles")

print(f"Saved {count} articles to {OUTPUT_PATH}")
