import csv
import json
import os
import sys
from pathlib import Path

import google.generativeai as genai
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

from pipelines.pipeline1_llm import pipeline1 as run_p1
from pipelines.pipeline2_rag import pipeline2 as run_p2
from pipelines.pipeline3_graphrag import pipeline3 as run_p3

_judge = genai.GenerativeModel("gemini-1.5-flash")
_judge_cfg = genai.types.GenerationConfig(temperature=0.0)

RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

_JUDGE_PROMPT = (
    "You are an impartial judge evaluating answer quality.\n\n"
    "Question: {question}\n"
    "Reference answer: {reference}\n"
    "Candidate answer: {answer}\n\n"
    "Does the candidate answer correctly address the question based on the reference? "
    "Respond with exactly one word: PASS or FAIL."
)


def llm_judge(question: str, reference: str, answer: str) -> bool:
    prompt = _JUDGE_PROMPT.format(question=question, reference=reference, answer=answer)
    resp = _judge.generate_content(prompt, generation_config=_judge_cfg)
    return resp.text.strip().upper().startswith("PASS")


def evaluate():
    with open(Path(__file__).parent.parent / "data" / "qa" / "qa_pairs.json") as f:
        qa_pairs = json.load(f)

    rows = []
    for i, qa in enumerate(qa_pairs):
        q, ref = qa["question"], qa["answer"]
        print(f"[{i+1}/{len(qa_pairs)}] {q[:60]}...")

        r1 = run_p1(q)
        r2 = run_p2(q)
        r3 = run_p3(q)

        r1["pass"] = llm_judge(q, ref, r1["answer"])
        r2["pass"] = llm_judge(q, ref, r2["answer"])
        r3["pass"] = llm_judge(q, ref, r3["answer"])

        print(
            f"  tokens → P1:{r1['total_tokens']} P2:{r2['total_tokens']} P3:{r3['total_tokens']}"
            f" | pass P1:{r1['pass']} P2:{r2['pass']} P3:{r3['pass']}"
        )

        for r in (r1, r2, r3):
            rows.append(
                {
                    "question": q,
                    "pipeline": r["pipeline"],
                    "answer": r["answer"],
                    "prompt_tokens": r["prompt_tokens"],
                    "completion_tokens": r["completion_tokens"],
                    "total_tokens": r["total_tokens"],
                    "latency_s": r["latency_s"],
                    "cost_usd": r["cost_usd"],
                    "pass": r["pass"],
                }
            )

    csv_path = RESULTS_DIR / "results.csv"
    fields = ["question", "pipeline", "answer", "prompt_tokens", "completion_tokens",
              "total_tokens", "latency_s", "cost_usd", "pass"]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    p1_rows = [r for r in rows if r["pipeline"] == "pipeline1_llm"]
    p2_rows = [r for r in rows if r["pipeline"] == "pipeline2_rag"]
    p3_rows = [r for r in rows if r["pipeline"] == "pipeline3_graphrag"]

    p1_tokens = sum(r["total_tokens"] for r in p1_rows)
    p2_tokens = sum(r["total_tokens"] for r in p2_rows)
    p3_tokens = sum(r["total_tokens"] for r in p3_rows)

    reduction = (1 - p3_tokens / p2_tokens) * 100 if p2_tokens else 0
    p1_pass = sum(r["pass"] for r in p1_rows) / len(p1_rows) * 100
    p2_pass = sum(r["pass"] for r in p2_rows) / len(p2_rows) * 100
    p3_pass = sum(r["pass"] for r in p3_rows) / len(p3_rows) * 100

    print(f"\n=== Results ===")
    print(f"Total tokens  — P1: {p1_tokens}  P2: {p2_tokens}  P3: {p3_tokens}")
    print(f"Token reduction P3 vs P2: {reduction:.1f}%")
    print(f"Pass rates    — P1: {p1_pass:.1f}%  P2: {p2_pass:.1f}%  P3: {p3_pass:.1f}%")
    print(f"Results saved to {csv_path}")

    summary = {
        "total_questions": len(qa_pairs),
        "p1_total_tokens": p1_tokens,
        "p2_total_tokens": p2_tokens,
        "p3_total_tokens": p3_tokens,
        "token_reduction_pct": round(reduction, 2),
        "p1_pass_rate": round(p1_pass, 2),
        "p2_pass_rate": round(p2_pass, 2),
        "p3_pass_rate": round(p3_pass, 2),
    }
    with open(RESULTS_DIR / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    return summary


if __name__ == "__main__":
    evaluate()
