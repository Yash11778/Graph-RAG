import os
import time

import google.generativeai as genai
from dotenv import load_dotenv

from pipelines.utils import count_tokens, make_result

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
_model = genai.GenerativeModel("gemini-1.5-flash")
_cfg = genai.types.GenerationConfig(temperature=0.0)

_PROMPT_TMPL = "Answer the following question concisely and accurately:\n\n{question}"


def run(question: str) -> dict:
    prompt = _PROMPT_TMPL.format(question=question)
    prompt_tokens = count_tokens(prompt)
    start = time.time()
    response = _model.generate_content(prompt, generation_config=_cfg)
    latency_s = time.time() - start
    answer = response.text.strip()
    return make_result("pipeline1_llm", answer, prompt_tokens, count_tokens(answer), latency_s)
