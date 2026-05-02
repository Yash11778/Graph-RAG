import time

from pipelines.utils import calc_cost, count_tokens, gemini_generate, make_result, setup_gemini

model = setup_gemini()


def pipeline1(question: str) -> dict:
    prompt = f'Answer concisely and accurately.\nQuestion: {question}'
    start = time.time()
    answer = gemini_generate(model, prompt)
    latency = time.time() - start
    p_tok = count_tokens(prompt)
    c_tok = count_tokens(answer)
    return make_result('llm_only', answer, p_tok, c_tok, round(latency, 3))
