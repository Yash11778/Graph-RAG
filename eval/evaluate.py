import json
import os
import sys
import warnings
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
from pipelines.utils import groq_generate, setup_groq

_judge_client = setup_groq()

PIPELINES = [
    ('llm_only',  pipeline1),
    ('basic_rag', pipeline2),
    ('graphrag',  pipeline3),
]


def llm_judge(question: str, ground_truth: str, prediction: str) -> str:
    prompt = (
        "You are a strict evaluator. Respond with exactly one word.\n"
        "PASS if the prediction is factually correct and addresses the question.\n"
        "FAIL if it is incorrect, incomplete, or irrelevant.\n\n"
        f"Question: {question}\n"
        f"Ground Truth: {ground_truth}\n"
        f"Prediction: {prediction}\n\n"
        "Answer (PASS or FAIL):"
    )
    response = groq_generate(_judge_client, prompt, max_tokens=5)
    return 'PASS' if 'PASS' in response.upper() else 'FAIL'


def compute_bertscore(predictions: list, references: list) -> dict:
    try:
        from bert_score import score
    except ImportError:
        return {'raw_f1': 0.0, 'rescaled_f1': 0.0, 'bonus_hit': False, 'error': 'bert_score not installed'}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _, _, F1 = score(predictions, references, lang='en',
                         model_type='distilbert-base-uncased', verbose=False)
    raw_f1   = F1.mean().item()
    rescaled = (raw_f1 - 0.5) / 0.5
    return {
        'raw_f1':       round(raw_f1, 4),
        'rescaled_f1':  round(rescaled, 4),
        'bonus_hit':    rescaled >= 0.55 or raw_f1 >= 0.88,
    }


def main():
    qa_path = ROOT / 'data/qa/qa_pairs.json'
    with open(qa_path) as f:
        qa_pairs = json.load(f)

    rows = []
    for i, qa in enumerate(tqdm(qa_pairs, desc='Evaluating')):
        question     = qa['question']
        ground_truth = qa['answer']

        for name, fn in PIPELINES:
            try:
                result = fn(question)
                judge  = llm_judge(question, ground_truth, result['answer'])
            except Exception as e:
                print(f'  [{name}] ERROR: {e}', flush=True)
                result = {'answer': '', 'total_tokens': 0, 'latency_s': 0}
                judge  = 'FAIL'

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

    rag_avg     = df[df['pipeline'] == 'basic_rag']['total_tokens'].mean()
    graphrag_avg = df[df['pipeline'] == 'graphrag']['total_tokens'].mean()
    reduction   = (1 - graphrag_avg / rag_avg) * 100
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
