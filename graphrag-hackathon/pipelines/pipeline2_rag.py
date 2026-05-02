import json
import os
import time
from pathlib import Path

import faiss
import google.generativeai as genai
import numpy as np
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

from pipelines.utils import count_tokens, make_result

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
_model = genai.GenerativeModel("gemini-1.5-flash")
_cfg = genai.types.GenerationConfig(temperature=0.0)
_embedder = SentenceTransformer("all-MiniLM-L6-v2")

_FAISS_DIR = Path(__file__).parent.parent / "data" / "faiss"
_index = None
_chunks = None

_PROMPT_TMPL = (
    "Using the following context, answer the question concisely and accurately.\n\n"
    "Context:\n{context}\n\n"
    "Question: {question}"
)


def _load_index():
    global _index, _chunks
    if _index is None:
        _index = faiss.read_index(str(_FAISS_DIR / "index.bin"))
        with open(_FAISS_DIR / "chunks.json") as f:
            _chunks = json.load(f)


def retrieve(question: str, top_k: int = 5) -> list:
    _load_index()
    emb = _embedder.encode([question], normalize_embeddings=True)
    _, idxs = _index.search(np.array(emb, dtype=np.float32), top_k)
    return [_chunks[i]["text"] for i in idxs[0] if i < len(_chunks)]


def run(question: str, top_k: int = 5) -> dict:
    chunks = retrieve(question, top_k)
    context = "\n\n".join(chunks)
    prompt = _PROMPT_TMPL.format(context=context, question=question)
    prompt_tokens = count_tokens(prompt)
    start = time.time()
    response = _model.generate_content(prompt, generation_config=_cfg)
    latency_s = time.time() - start
    answer = response.text.strip()
    return make_result("pipeline2_rag", answer, prompt_tokens, count_tokens(answer), latency_s)
