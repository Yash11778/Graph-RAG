"""
Compute BERTScore F1 for one pipeline at a time to avoid segfault.
Usage:
    python scripts/eval_bertscore.py p1
    python scripts/eval_bertscore.py p2
    python scripts/eval_bertscore.py p3
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

ROOT    = Path(__file__).parent.parent
CACHE   = ROOT / "data" / "qa" / "eval_answers.json"

which = sys.argv[1] if len(sys.argv) > 1 else "p3"

with open(ROOT / "data" / "qa" / "qa_pairs_graph.json") as f:
    qa_pairs = json.load(f)

SAMPLE     = qa_pairs[:30]
questions  = [q["question"] for q in SAMPLE]
references = [q["answer"]   for q in SAMPLE]

print(f"Running {which.upper()} on {len(questions)} questions...")

if which == "p1":
    import pipelines.pipeline1_llm as p
    fn = p.pipeline1
elif which == "p2":
    import pipelines.pipeline2_rag as p
    p._load()
    fn = p.pipeline2
else:
    import pipelines.pipeline2_rag as p2_mod
    p2_mod._load()
    import pipelines.pipeline3_graphrag as p
    fn = p.pipeline3

answers = []
for i, q in enumerate(questions, 1):
    try:
        result = fn(q)
        ans = result.get("answer", "") if isinstance(result, dict) else str(result)
    except Exception as e:
        ans = "no answer"
        print(f"  [{i:>2}] ERROR: {e}")
    answers.append(ans.strip() if ans.strip() else "no answer")
    print(f"  [{i:>2}/{len(questions)}] done", flush=True)

# Save answers
cache = {}
if CACHE.exists():
    with open(CACHE) as f:
        cache = json.load(f)
cache[which] = answers
with open(CACHE, "w") as f:
    json.dump(cache, f, indent=2)
print(f"Saved {which} answers to {CACHE.name}")

# Compute BERTScore
from bert_score import score as bscore

print("\nComputing BERTScore...")
_, _, F1 = bscore(
    answers,
    references,
    model_type="distilbert-base-uncased",
    lang="en",
    rescale_with_baseline=True,
    verbose=False,
)
result_f1 = round(F1.mean().item(), 4)
print(f"\n{'='*35}")
print(f"{which.upper()} BERTScore F1: {result_f1}")
print(f"{'='*35}")
