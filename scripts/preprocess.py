import json
import os
import re
import tiktoken
from tqdm import tqdm

INPUT_PATH = "data/raw/dataset.jsonl"
OUTPUT_PATH = "data/chunks/chunks.jsonl"

os.makedirs("data/chunks", exist_ok=True)

enc = tiktoken.get_encoding("cl100k_base")


def clean_text(text):
    text = re.sub(r'==+[^=]+=+', '', text)
    text = re.sub(r'\[\[([^\]|]*\|)?([^\]]*)\]\]', r'\2', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def chunk_text(text, max_tok=256, overlap=32):
    tokens = enc.encode(text)
    step = max_tok - overlap
    chunks = []
    for start in range(0, len(tokens), step):
        end = min(start + max_tok, len(tokens))
        chunks.append(enc.decode(tokens[start:end]))
        if end == len(tokens):
            break
    return chunks


total_chunks = 0

with open(INPUT_PATH, encoding="utf-8") as fin, open(OUTPUT_PATH, "w", encoding="utf-8") as fout:
    lines = fin.readlines()
    for line in tqdm(lines, desc="Preprocessing", unit="docs"):
        doc = json.loads(line)
        cleaned = clean_text(doc["text"])
        chunks = chunk_text(cleaned)
        for j, chunk in enumerate(chunks):
            record = {
                "id": f"{doc['id']}_c{j}",
                "text": chunk,
                "source": doc["title"],
                "doc_id": doc["id"],
            }
            fout.write(json.dumps(record, ensure_ascii=False) + "\n")
            total_chunks += 1

print(f"Total chunks saved: {total_chunks}")
