import time

from pipelines.utils import count_tokens, groq_generate, make_result, setup_groq

client = setup_groq()


def pipeline1(question: str) -> dict:
    prompt = f'Answer concisely and accurately.\nQuestion: {question}'
    start = time.time()
    answer = groq_generate(client, prompt)
    latency = time.time() - start
    p_tok = count_tokens(prompt)
    c_tok = count_tokens(answer)
    return make_result('llm_only', answer, p_tok, c_tok, round(latency, 3))
