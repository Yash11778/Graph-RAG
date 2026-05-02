import os

import google.generativeai as genai
import tiktoken
from dotenv import load_dotenv

load_dotenv()

enc = tiktoken.get_encoding('cl100k_base')


def setup_gemini() -> genai.GenerativeModel:
    genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
    return genai.GenerativeModel('gemini-1.5-flash')


def count_tokens(text: str) -> int:
    return len(enc.encode(text))


def calc_cost(tokens: int) -> float:
    return (tokens / 1_000_000) * 0.075


def make_result(pipeline, answer, prompt_tok, comp_tok, latency) -> dict:
    total = prompt_tok + comp_tok
    return {
        'pipeline': pipeline,
        'answer': answer,
        'prompt_tokens': prompt_tok,
        'completion_tokens': comp_tok,
        'total_tokens': total,
        'latency_s': latency,
        'cost_usd': round(calc_cost(total), 8),
    }


def gemini_generate(model: genai.GenerativeModel, prompt: str) -> str:
    cfg = genai.types.GenerationConfig(temperature=0.0, max_output_tokens=400)
    response = model.generate_content(prompt, generation_config=cfg)
    return response.text.strip()
