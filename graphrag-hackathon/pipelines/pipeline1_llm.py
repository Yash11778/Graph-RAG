import time

from pipelines.utils import count_tokens, groq_generate, make_result, setup_groq

client = setup_groq()


def pipeline1(question: str) -> dict:
    prompt = (
        "You are a precise factual assistant. Answer the question directly and accurately "
        "using your knowledge. Be specific — include names, dates, and facts.\n\n"
        f"Question: {question}\nAnswer:"
    )
    start = time.time()
    answer = groq_generate(client, prompt, max_tokens=120)
    latency = time.time() - start
    p_tok = count_tokens(prompt)
    c_tok = count_tokens(answer)
    return make_result('llm_only', answer, p_tok, c_tok, round(latency, 3))
