"""
Step 4 of GraphRAG setup.
Generates QA pairs grounded in the actual dataset (war/military Wikipedia articles).
Uses Groq to extract question + ground-truth answer from real article content,
so all 3 pipelines are evaluated on questions their data actually contains.

Saves to data/qa/qa_pairs.json (overwrites existing generic pairs).
"""
import json
import os
import pickle
import random
import time
from pathlib import Path

from pipelines.utils import setup_groq, groq_generate

TARGET_PAIRS = 20
CHUNKS_PER_PROMPT = 3  # feed 3 chunks per call, ask for 1 Q&A per chunk
OUTPUT = Path("data/qa/qa_pairs.json")

PROMPT_TEMPLATE = """\
Read the following text passages and generate one clear factual question and its precise answer FOR EACH passage.

Rules:
- The question must be answerable ONLY from the passage text.
- The answer must be a complete sentence, not just a word.
- Questions should cover specific facts: dates, people, events, outcomes, causes.
- Output ONLY valid JSON — no markdown, no explanation.

Format:
[{{"question": "...", "answer": "...", "source": "<passage title>"}}, ...]

Passages:
{passages}"""


def main():
    os.makedirs("data/qa", exist_ok=True)
    client = setup_groq()

    # Load raw dataset to get full article titles
    print("Loading dataset...")
    with open("data/raw/dataset.jsonl", encoding="utf-8") as f:
        articles = [json.loads(l) for l in f]

    # Sample diverse articles
    random.seed(42)
    sampled = random.sample(articles, min(30, len(articles)))

    qa_pairs = []
    seen_questions = set()

    for i in range(0, len(sampled), CHUNKS_PER_PROMPT):
        if len(qa_pairs) >= TARGET_PAIRS:
            break

        batch = sampled[i:i + CHUNKS_PER_PROMPT]
        passages_text = "\n\n---\n\n".join(
            f"[{a['title']}]\n{a['text'][:800]}"
            for a in batch
        )
        prompt = PROMPT_TEMPLATE.format(passages=passages_text)

        for attempt in range(4):
            try:
                raw = groq_generate(client, prompt, max_tokens=600)
                # strip markdown fences
                raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
                parsed = json.loads(raw)
                for item in parsed:
                    q = item.get("question", "").strip()
                    a = item.get("answer", "").strip()
                    if q and a and q not in seen_questions:
                        seen_questions.add(q)
                        qa_pairs.append({"question": q, "answer": a, "source": item.get("source", "")})
                break
            except json.JSONDecodeError:
                if attempt == 3:
                    print(f"  [warn] JSON parse failed for batch {i//CHUNKS_PER_PROMPT + 1}")
            except Exception as e:
                if "429" in str(e) or "rate" in str(e).lower():
                    wait = 35 * (attempt + 1)
                    print(f"  [rate limit] waiting {wait}s...")
                    time.sleep(wait)
                else:
                    print(f"  [error] {e}")
                    break

        print(f"  Collected {len(qa_pairs)} pairs so far...")

    qa_pairs = qa_pairs[:TARGET_PAIRS]
    OUTPUT.write_text(json.dumps(qa_pairs, indent=2, ensure_ascii=False))
    print(f"\nSaved {len(qa_pairs)} QA pairs to {OUTPUT}")

    # Print sample
    print("\nSample QA pairs:")
    for qa in qa_pairs[:3]:
        print(f"  Q: {qa['question']}")
        print(f"  A: {qa['answer'][:100]}")
        print(f"  Source: {qa.get('source', '')}\n")


if __name__ == "__main__":
    os.chdir(Path(__file__).parent.parent)
    main()
