import os
import time

import tiktoken
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

enc = tiktoken.get_encoding('cl100k_base')

GROQ_MODEL = 'llama-3.3-70b-versatile'
_client: Groq | None = None


def setup_groq() -> Groq:
    global _client
    if _client is None:
        api_key = os.getenv('GROQ_API_KEY', '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')
        _client = Groq(api_key=api_key)
    return _client


def count_tokens(text: str) -> int:
    return len(enc.encode(text))


def calc_cost(tokens: int) -> float:
    return (tokens / 1_000_000) * 0.059  # llama-3.3-70b pricing


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


def groq_generate(client: Groq, prompt: str) -> str:
    for attempt in range(5):
        try:
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{'role': 'user', 'content': prompt}],
                temperature=0.0,
                max_tokens=400,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            if ('429' in str(e) or 'rate' in str(e).lower()) and attempt < 4:
                wait = 30 * (attempt + 1)
                print(f'  [rate limit] waiting {wait}s...', flush=True)
                time.sleep(wait)
            else:
                raise
