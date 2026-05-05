import json
import os
import sys
import time
from pathlib import Path

import pandas as pd
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipelines.pipeline1_llm import pipeline1
from pipelines.pipeline2_rag import pipeline2
from pipelines.pipeline3_graphrag import pipeline3
from pipelines.utils import groq_generate, setup_groq

_judge_client = setup_groq()


def llm_judge(question: str, ground_truth: str, prediction: str) -> str:
    prompt = (
        "You are a strict evaluator. Given a question, a ground truth answer, and a predicted answer, "
        "respond with exactly one word: PASS if the prediction is factually correct and addresses the question, "
        "or FAIL if it is incorrect, incomplete, or irrelevant.\n\n"
        f"Question: {question}\n"
        f"Ground Truth: {ground_truth}\n"
        f"Prediction: {prediction}\n\n"
        "Respond with only PASS or FAIL."
    )
    response = groq_generate(_judge_client, prompt)
    return 'PASS' if 'PASS' in response.upper() else 'FAIL'


def compute_bertscore(predictions: list, references: list) -> dict:
    from bert_score import score
    _, _, F1 = score(predictions, references, lang='en',
                     model_type='roberta-large', verbose=False)
    raw_f1 = F1.mean().item()
    rescaled = (raw_f1 - 0.5) / 0.5
    return {
        'raw_f1': round(raw_f1, 4),
        'rescaled_f1': round(rescaled, 4),
        'bonus_hit': rescaled >= 0.55 or raw_f1 >= 0.88,
    }


def main():
    with open('data/qa/qa_pairs.json') as f:
        qa_pairs = json.load(f)

    rows = []
    for i, qa in enumerate(tqdm(qa_pairs, desc='Evaluating')):
        question = qa['question']
        ground_truth = qa['answer']

        for name, fn in [('llm_only', pipeline1), ('basic_rag', pipeline2), ('graphrag', pipeline3)]:
            result = fn(question)
            judge = llm_judge(question, ground_truth, result['answer'])
            rows.append({
                'qid': i,
                'pipeline': name,
                'total_tokens': result['total_tokens'],
                'latency_s': result['latency_s'],
                'judge': judge,
                'answer': result['answer'],
                'ground_truth': ground_truth,
                'question': question,
            })

    os.makedirs('eval/results', exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_csv('eval/results/eval_results.csv', index=False)
    print('\nSaved eval/results/eval_results.csv')
    print_summary(df)


def print_summary(df: pd.DataFrame):
    print('\n=== EVALUATION SUMMARY ===')
    for pipeline in ['llm_only', 'basic_rag', 'graphrag']:
        sub = df[df['pipeline'] == pipeline]
        pass_rate = (sub['judge'] == 'PASS').mean() * 100
        avg_tokens = sub['total_tokens'].mean()
        avg_latency = sub['latency_s'].mean()
        print(f'\n[{pipeline}]')
        print(f'  pass_rate:   {pass_rate:.1f}%')
        print(f'  avg_tokens:  {avg_tokens:.1f}')
        print(f'  avg_latency: {avg_latency:.3f}s')

    rag_avg = df[df['pipeline'] == 'basic_rag']['total_tokens'].mean()
    graphrag_avg = df[df['pipeline'] == 'graphrag']['total_tokens'].mean()
    token_reduction = (1 - graphrag_avg / rag_avg) * 100

    print(f'\nToken reduction (graphrag vs basic_rag): {token_reduction:.1f}%')

    graphrag_rows = df[df['pipeline'] == 'graphrag']
    predictions = graphrag_rows['answer'].tolist()
    references = graphrag_rows['ground_truth'].tolist()

    print('\nComputing BERTScore (this may take a minute)...')
    bs = compute_bertscore(predictions, references)
    print(f'BERTScore raw_f1:      {bs["raw_f1"]}')
    print(f'BERTScore rescaled_f1: {bs["rescaled_f1"]}')
    print(f'BERTScore bonus_hit:   {bs["bonus_hit"]}')

    graphrag_pass_rate = (df[df['pipeline'] == 'graphrag']['judge'] == 'PASS').mean() * 100
    judge_hit = graphrag_pass_rate >= 90
    bertscore_hit = bs['bonus_hit']

    print(f'\nFINAL: token_reduction={token_reduction:.1f}%, judge_pass_rate={graphrag_pass_rate:.1f}%, bertscore_rescaled={bs["rescaled_f1"]}')
    print(f'BONUS STATUS: {"HIT" if judge_hit else "MISSED"} judge | {"HIT" if bertscore_hit else "MISSED"} bertscore')


if __name__ == '__main__':
    main()
