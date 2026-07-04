import json
import os
import sys
from pathlib import Path

# Suppress HuggingFace / transformers noise before any imports
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")
os.environ.setdefault("HF_HUB_VERBOSITY", "error")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import pandas as pd
from tqdm import tqdm

ROOT = Path(__file__).parent.parent.resolve()
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from pipelines.pipeline1_llm import pipeline1
from pipelines.pipeline2_rag import pipeline2
from pipelines.pipeline3_graphrag import pipeline3
from eval.judge import llm_judge, compute_bertscore

PIPELINES = [
    ('llm_only',  pipeline1),
    ('basic_rag', pipeline2),
    ('graphrag',  pipeline3),
]


def main():
    # Always the real benchmark set -- a smaller "graph-aligned" set used to exist
    # (qa_pairs_graph.json) that was curated to match a fabricated offline snapshot
    # rather than the live graph. It's been removed; this is the only QA file now.
    qa_path = ROOT / 'data/qa/qa_pairs.json'
    print(f'Using QA file: {qa_path}')
    with open(qa_path, encoding='utf-8') as f:
        qa_pairs = json.load(f)

    rows = []
    for i, qa in enumerate(tqdm(qa_pairs, desc='Evaluating')):
        question     = qa['question']
        ground_truth = qa['answer']

        for name, fn in PIPELINES:
            try:
                result = fn(question)
            except Exception as e:
                print(f'  [{name}] pipeline ERROR: {e}', flush=True)
                result = {'answer': '', 'total_tokens': 0, 'latency_s': 0}
            try:
                judge = llm_judge(question, ground_truth, result['answer'])
            except Exception as e:
                print(f'  [{name}] judge ERROR: {e}', flush=True)
                judge = 'FAIL'

            rows.append({
                'qid':          i,
                'pipeline':     name,
                'total_tokens': result['total_tokens'],
                'latency_s':    result['latency_s'],
                'judge':        judge,
                'answer':       result['answer'],
                'ground_truth': ground_truth,
                'question':     question,
            })
            print(
                f'  [{name}] judge={judge} '
                f'tokens={result["total_tokens"]} '
                f'latency={result["latency_s"]}s',
                flush=True,
            )

    out_dir = ROOT / 'eval/results'
    out_dir.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_csv(out_dir / 'eval_results.csv', index=False)
    print(f'\nSaved {out_dir / "eval_results.csv"}')
    print_summary(df)


def print_summary(df: pd.DataFrame):
    print('\n=== EVALUATION SUMMARY ===')
    for name, _ in PIPELINES:
        sub      = df[df['pipeline'] == name]
        pass_pct = (sub['judge'] == 'PASS').mean() * 100
        print(f'\n[{name}]')
        print(f'  pass_rate:   {pass_pct:.1f}%')
        print(f'  avg_tokens:  {sub["total_tokens"].mean():.1f}')
        print(f'  avg_latency: {sub["latency_s"].mean():.3f}s')

    rag_avg      = df[df['pipeline'] == 'basic_rag']['total_tokens'].mean()
    graphrag_avg = df[df['pipeline'] == 'graphrag']['total_tokens'].mean()
    reduction    = (1 - graphrag_avg / rag_avg) * 100 if rag_avg > 0 else 0.0
    print(f'\nToken reduction (graphrag vs basic_rag): {reduction:.1f}%')

    gr_rows      = df[df['pipeline'] == 'graphrag']
    predictions  = gr_rows['answer'].tolist()
    references   = gr_rows['ground_truth'].tolist()

    print('\nComputing BERTScore...')
    bs = compute_bertscore(predictions, references)
    print(f'BERTScore raw_f1:      {bs["raw_f1"]}')
    print(f'BERTScore rescaled_f1: {bs["rescaled_f1"]}')
    print(f'BERTScore bonus_hit:   {bs["bonus_hit"]}')

    gr_pass   = (gr_rows['judge'] == 'PASS').mean() * 100
    judge_hit = gr_pass >= 90

    print(f'\nFINAL: token_reduction={reduction:.1f}%, judge_pass_rate={gr_pass:.1f}%, bertscore_rescaled={bs["rescaled_f1"]}')
    print(f'BONUS STATUS: {"HIT" if judge_hit else "MISSED"} judge | {"HIT" if bs["bonus_hit"] else "MISSED"} bertscore')


if __name__ == '__main__':
    main()
