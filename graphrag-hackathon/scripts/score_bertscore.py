"""Step 2: compute BERTScore from saved answers — no pipeline code loaded."""
import json, gc
from pathlib import Path
from bert_score import score as bscore

ROOT = Path(__file__).parent.parent
with open(ROOT / "data" / "qa" / "eval_answers.json") as f:
    data = json.load(f)

refs = data["references"]

def f1(cands, refs, label):
    gc.collect()
    _, _, F1 = bscore(cands, refs,
                      model_type="distilbert-base-uncased",
                      lang="en",
                      rescale_with_baseline=True,
                      batch_size=4,
                      verbose=False)
    val = round(F1.mean().item(), 4)
    print(f"{label} BERTScore F1: {val}")
    del F1; gc.collect()
    return val

print("="*40)
f1(data["p1"], refs, "LLM Only ")
f1(data["p2"], refs, "Basic RAG")
f1(data["p3"], refs, "GraphRAG ")
print("="*40)
