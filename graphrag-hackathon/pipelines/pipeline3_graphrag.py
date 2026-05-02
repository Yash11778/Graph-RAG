import os
import time

import google.generativeai as genai
import requests
from dotenv import load_dotenv

from pipelines.utils import count_tokens, make_result

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
_model = genai.GenerativeModel("gemini-1.5-flash")
_cfg = genai.types.GenerationConfig(temperature=0.0)

GRAPHRAG_URL = os.getenv("GRAPHRAG_URL", "http://localhost:8000")

_PROMPT_TMPL = (
    "Using the following context retrieved from a knowledge graph, "
    "answer the question concisely and accurately.\n\n"
    "Context:\n{context}\n\n"
    "Question: {question}"
)


def retrieve_context(
    question: str,
    top_k: int = 3,
    num_hops: int = 2,
    community_level: int = 2,
    retriever: str = "community",
) -> str:
    payload = {
        "query": question,
        "top_k": top_k,
        "num_hops": num_hops,
        "community_level": community_level,
        "retriever_type": retriever,
    }
    resp = requests.post(f"{GRAPHRAG_URL}/retrieve", json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("context", data.get("result", ""))


def run(
    question: str,
    top_k: int = 3,
    num_hops: int = 2,
    community_level: int = 2,
    retriever: str = "community",
) -> dict:
    context = retrieve_context(question, top_k, num_hops, community_level, retriever)
    prompt = _PROMPT_TMPL.format(context=context, question=question)
    prompt_tokens = count_tokens(prompt)
    start = time.time()
    response = _model.generate_content(prompt, generation_config=_cfg)
    latency_s = time.time() - start
    answer = response.text.strip()
    return make_result("pipeline3_graphrag", answer, prompt_tokens, count_tokens(answer), latency_s)
