import os
import time

import tiktoken
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

enc = tiktoken.get_encoding('cl100k_base')

GROQ_MODEL = 'llama-3.1-8b-instant'
_client: Groq | None = None


def setup_groq() -> Groq:
    global _client
    if _client is None:
        api_key = os.getenv('GROQ_API_KEY', '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')
        _client = Groq(api_key=api_key)
    return _client


def count_tokens(text: str) -> int:
    return len(enc.encode(text))


def make_result(pipeline, answer, prompt_tok, comp_tok, latency) -> dict:
    total = prompt_tok + comp_tok
    return {
        'pipeline':          pipeline,
        'answer':            answer,
        'prompt_tokens':     prompt_tok,
        'completion_tokens': comp_tok,
        'total_tokens':      total,
        'latency_s':         latency,
        'cost_usd':          0.0,
    }


def groq_generate(client: Groq, prompt: str, max_tokens: int = 200) -> str:
    for attempt in range(5):
        try:
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{'role': 'user', 'content': prompt}],
                temperature=0.0,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            err = str(e)
            # Retry only on per-minute rate limits, not daily token limits
            is_tpm_limit = '429' in err and 'per_day' not in err and 'tokens per day' not in err.lower()
            if is_tpm_limit and attempt < 4:
                wait = 5 * (attempt + 1)
                print(f'  [rate limit] waiting {wait}s...', flush=True)
                time.sleep(wait)
            else:
                raise
