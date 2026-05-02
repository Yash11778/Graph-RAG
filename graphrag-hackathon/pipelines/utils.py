import tiktoken

_enc = tiktoken.get_encoding("cl100k_base")

COST_PER_M = 0.075


def count_tokens(text: str) -> int:
    return len(_enc.encode(text))


def calculate_cost(total_tokens: int) -> float:
    return (total_tokens / 1_000_000) * COST_PER_M


def make_result(
    pipeline: str,
    answer: str,
    prompt_tokens: int,
    completion_tokens: int,
    latency_s: float,
) -> dict:
    total = prompt_tokens + completion_tokens
    return {
        "pipeline": pipeline,
        "answer": answer,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total,
        "latency_s": round(latency_s, 3),
        "cost_usd": round(calculate_cost(total), 8),
    }
