"""
Generate QA pairs grounded in the actual dataset.
For Round 2: samples from dataset_100m_enriched.jsonl, targets 75 pairs.

Usage:
    python scripts/generate_qa_pairs.py
    python scripts/generate_qa_pairs.py --input data/raw/dataset_100m_enriched.jsonl --target 75
"""

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipelines.utils import setup_gemini, gemini_generate

PROMPT_TEMPLATE = """\
Read the following Wikipedia passages and generate one clear factual question and its precise answer FOR EACH passage.

Rules:
- The question must be directly answerable from the passage text.
- The answer must be a complete sentence with the key fact clearly stated.
- Prefer questions about well-known facts: who founded X, what year did Y happen, what is Z known for.
- Avoid questions about very obscure people or events that only appear in one small passage.
- The answer should be verifiable — a specific name, date, place, or description.
- Output ONLY valid JSON — no markdown, no explanation.

Format:
[{{"question": "...", "answer": "...", "source": "<passage title>"}}, ...]

Passages:
{passages}"""

CHUNKS_PER_CALL = 3

WELL_KNOWN_KEYWORDS = [
    'war', 'battle', 'president', 'prime minister', 'revolution', 'empire', 'kingdom',
    'science', 'physics', 'chemistry', 'biology', 'mathematics', 'university',
    'award', 'oscar', 'nobel', 'olympic', 'championship', 'world cup',
    'founded', 'invention', 'discovery', 'theory', 'philosophy',
    'film', 'music', 'novel', 'literature', 'art', 'painting',
    'country', 'city', 'continent', 'ocean', 'mountain', 'river',
    'ancient', 'medieval', 'century', 'dynasty', 'civilization',
    'technology', 'computer', 'internet', 'software', 'engineering',
]


def main(input_path: str, output_path: str, target: int, seed: int):
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    client = setup_gemini()

    print(f"Loading articles from {input_path}...")
    articles = []
    # Seek past leading null bytes (can occur from partial/resumed downloads)
    start_offset = 0
    with open(input_path, "rb") as fb:
        buf = fb.read(1 << 20)
        while buf:
            idx = buf.find(b'{')
            if idx != -1:
                start_offset += idx
                break
            start_offset += len(buf)
            buf = fb.read(1 << 20)
    with open(input_path, "rb") as fb:
        fb.seek(start_offset)
        for line in fb:
            line = line.strip()
            if line:
                articles.append(json.loads(line.decode("utf-8", errors="replace")))
    print(f"Loaded {len(articles):,} articles")

    # Prefer well-known topics — filter articles whose title/text contains known keywords
    random.seed(seed)
    known = [a for a in articles if any(
        kw in (a.get('title', '') + ' ' + a.get('text', '')[:300]).lower()
        for kw in WELL_KNOWN_KEYWORDS
    )]
    fallback = [a for a in articles if a not in known]
    print(f"Well-known articles: {len(known):,} / {len(articles):,}")
    # Take mostly known articles, small fallback for diversity
    pool = known + random.sample(fallback, min(len(fallback), target * 2))
    sample_size = min(target * 5, len(pool))
    sampled = random.sample(pool, sample_size)

    qa_pairs = []
    seen_questions = set()

    for i in range(0, len(sampled), CHUNKS_PER_CALL):
        if len(qa_pairs) >= target:
            break

        batch = sampled[i:i + CHUNKS_PER_CALL]
        passages_text = "\n\n---\n\n".join(
            f"[{a['title']}]\n{a['text'][:900]}"
            for a in batch
        )
        prompt = PROMPT_TEMPLATE.format(passages=passages_text)

        for attempt in range(4):
            try:
                raw = gemini_generate(client, prompt, max_tokens=700)
                raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
                parsed = json.loads(raw)
                for item in parsed:
                    q = item.get("question", "").strip()
                    a = item.get("answer", "").strip()
                    if q and a and q not in seen_questions:
                        seen_questions.add(q)
                        qa_pairs.append({
                            "question": q,
                            "answer": a,
                            "source": item.get("source", ""),
                        })
                break
            except json.JSONDecodeError:
                if attempt == 3:
                    print(f"  [warn] JSON parse failed batch {i // CHUNKS_PER_CALL + 1}")
            except Exception as e:
                if "429" in str(e) or "rate" in str(e).lower():
                    wait = 35 * (attempt + 1)
                    print(f"  [rate limit] waiting {wait}s...")
                    time.sleep(wait)
                else:
                    print(f"  [error] {e}")
                    break

        if len(qa_pairs) % 10 == 0 and len(qa_pairs) > 0:
            print(f"  Collected {len(qa_pairs)}/{target} pairs...", flush=True)
            # Save incrementally so a crash doesn't lose all progress
            Path(output_path).write_text(json.dumps(qa_pairs[:target], indent=2, ensure_ascii=False), encoding="utf-8")

    qa_pairs = qa_pairs[:target]
    Path(output_path).write_text(json.dumps(qa_pairs, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved {len(qa_pairs)} QA pairs to {output_path}")

    print("\nSample:")
    for qa in qa_pairs[:3]:
        print(f"  Q: {qa['question']}")
        print(f"  A: {qa['answer'][:100]}")
        print(f"  Source: {qa.get('source', '')}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/raw/dataset_100m_enriched.jsonl")
    parser.add_argument("--output", default="data/qa/qa_pairs.json")
    parser.add_argument("--target", type=int, default=75)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    os.chdir(Path(__file__).parent.parent)
    main(args.input, args.output, args.target, args.seed)
