import time

import requests

from pipelines.utils import count_tokens, make_result

BASE = 'http://localhost:8010'
PARAMS = {
    'top_k': 3,
    'num_hops': 2,
    'community_level': 2,
    'retriever': 'community',
}


def pipeline3(question: str) -> dict:
    payload = {'query': question, **PARAMS}
    start = time.time()
    resp = requests.post(f'{BASE}/query', json=payload, timeout=60)
    latency = round(time.time() - start, 3)
    resp.raise_for_status()
    data = resp.json()

    answer = data['answer']
    context = data.get('context', '')

    p_tok = count_tokens(context + question)
    c_tok = count_tokens(answer)
    result = make_result('graphrag', answer, p_tok, c_tok, latency)
    result['context_used'] = context
    result['entities'] = data.get('entities', [])
    return result
