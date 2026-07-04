import os
import time

import tiktoken
from dotenv import load_dotenv

load_dotenv()

enc = tiktoken.get_encoding('cl100k_base')

# Model is env-configurable so a retired model never breaks the pipelines (gemini-2.0-flash
# was retired by Google in 2026). Default to the current stable flash tier; override with
# GEMINI_MODEL in .env (e.g. gemini-2.5-flash, gemini-3.5-flash, or gemini-flash-latest).
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')
_GEMINI_KEY  = os.getenv('GEMINI_API_KEY')

_client = None


def setup_gemini():
    global _client
    if _client is None:
        if not _GEMINI_KEY:
            raise RuntimeError("GEMINI_API_KEY environment variable is not set")
        from google import genai
        _client = genai.Client(api_key=_GEMINI_KEY)
    return _client


def count_tokens(text: str) -> int:
    return len(enc.encode(text))


def make_result(pipeline: str, answer: str, prompt_tok: int, comp_tok: int, latency: float) -> dict:
    total = prompt_tok + comp_tok
    # gemini-2.5-flash pricing (non-thinking, ≤200K context): $0.15/1M input, $0.60/1M output
    # Override with GEMINI_INPUT_PRICE / GEMINI_OUTPUT_PRICE env vars if using a different model.
    input_price  = float(os.getenv('GEMINI_INPUT_PRICE',  '0.15'))   # per 1M tokens
    output_price = float(os.getenv('GEMINI_OUTPUT_PRICE', '0.60'))   # per 1M tokens
    cost = (prompt_tok * input_price + comp_tok * output_price) / 1_000_000
    return {
        'pipeline':          pipeline,
        'answer':            answer,
        'prompt_tokens':     prompt_tok,
        'completion_tokens': comp_tok,
        'total_tokens':      total,
        'latency_s':         latency,
        'cost_usd':          round(cost, 6),
    }


def _extract_text(response) -> str:
    """Extract text from a Gemini response, handling thinking-token responses where
    response.text raises ValueError instead of returning None."""
    # Fast path: works for standard (non-thinking) responses
    try:
        text = response.text
        if text:
            return text.strip()
    except (ValueError, AttributeError):
        pass

    # Slow path: iterate parts, collect only text parts (skip thought parts)
    try:
        parts = response.candidates[0].content.parts
        texts = [p.text for p in parts if hasattr(p, 'text') and p.text and not getattr(p, 'thought', False)]
        return " ".join(texts).strip()
    except Exception:
        pass

    return ""


def gemini_generate(client, prompt: str, max_tokens: int = 400) -> str:
    from google.genai import types
    # Gemini 2.5+ models "think" by default, which adds latency and can consume the
    # output budget. Disable it so generation stays fast and non-thinking. Older models
    # that don't support thinking simply ignore this config.
    cfg_kwargs = dict(temperature=0.0, max_output_tokens=max_tokens)
    try:
        cfg_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
    except Exception:
        pass
    for attempt in range(5):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(**cfg_kwargs),
            )
            return _extract_text(response)
        except Exception as e:
            err = str(e)
            if ('429' in err or 'quota' in err.lower() or 'rate' in err.lower()) and attempt < 4:
                wait = 3 * (2 ** attempt)    # exponential back-off: 3s, 6s, 12s, 24s
                print(f'  [rate limit] waiting {wait}s (attempt {attempt + 1}/5)…', flush=True)
                time.sleep(wait)
            else:
                raise
