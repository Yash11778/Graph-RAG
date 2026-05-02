import json
import os

import tiktoken
from dotenv import load_dotenv

load_dotenv()

enc = tiktoken.get_encoding("cl100k_base")

INPUT_PATH = "data/raw/wikipedia.jsonl"
OUTPUT_PATH = "data/chunks/chunks.jsonl"
CHUNK_SIZE = 256
OVERLAP = 32

os.makedirs("data/chunks", exist_ok=True)


def chunk_text(text: str) -> list:
    tokens = enc.encode(text)
    chunks = []
    start = 0
    while start < len(tokens):
        end = min(start + CHUNK_SIZE, len(tokens))
        chunks.append(enc.decode(tokens[start:end]))
        if end == len(tokens):
            break
        start += CHUNK_SIZE - OVERLAP
    return chunks


chunk_id = 0
with open(INPUT_PATH, encoding="utf-8") as fin, open(OUTPUT_PATH, "w", encoding="utf-8") as fout:
    for line in fin:
        article = json.loads(line)
        for chunk in chunk_text(article["text"]):
            record = {
                "id": chunk_id,
                "article_id": article["id"],
                "title": article["title"],
                "text": chunk,
            }
            fout.write(json.dumps(record, ensure_ascii=False) + "\n")
            chunk_id += 1
        if chunk_id % 5000 == 0:
            print(f"Processed {chunk_id} chunks so far")

print(f"Total chunks written: {chunk_id}")
