"""Step 1: collect answers from all 3 pipelines and save to JSON."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

ROOT  = Path(__file__).parent.parent
OUT   = ROOT / "data" / "qa" / "eval_answers.json"

with open(ROOT / "data" / "qa" / "qa_pairs_graph.json") as f:
    qa_pairs = json.load(f)

SAMPLE    = qa_pairs[:20]
questions = [q["question"] for q in SAMPLE]
refs      = [q["answer"]   for q in SAMPLE]

import pipelines.pipeline1_llm      as p1
import pipelines.pipeline2_rag      as p2
import pipelines.pipeline3_graphrag as p3
p2._load()

def collect(name, fn):
    answers = []
    for i, q in enumerate(questions, 1):
        try:
            r = fn(q)
            a = r.get("answer", "") if isinstance(r, dict) else str(r)
        except Exception as e:
            a = "no answer"
            print(f"  [{i}] ERROR: {e}")
        answers.append(a.strip() or "no answer")
        print(f"  [{i:>2}/{len(questions)}] {name}", flush=True)
    return answers

print("P1..."); p1_ans = collect("P1", p1.pipeline1)
print("P2..."); p2_ans = collect("P2", p2.pipeline2)
print("P3..."); p3_ans = collect("P3", p3.pipeline3)

with open(OUT, "w") as f:
    json.dump({"questions": questions, "references": refs,
               "p1": p1_ans, "p2": p2_ans, "p3": p3_ans}, f, indent=2)
print(f"\nSaved answers to {OUT}")
