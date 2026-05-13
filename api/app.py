import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager

from pipelines.pipeline1_llm import pipeline1
from pipelines.pipeline2_rag import pipeline2
from pipelines.pipeline3_graphrag import pipeline3
from pipelines.utils import groq_generate, setup_groq


# ── LLM judge (inline — avoids importing evaluate.py which has script-level code) ──
_judge_client = setup_groq()


def llm_judge(question: str, ground_truth: str, prediction: str) -> str:
    prompt = (
        "You are a strict evaluator. Respond with exactly one word.\n"
        "PASS if the prediction is factually correct and addresses the question.\n"
        "FAIL if it is incorrect, incomplete, or irrelevant.\n\n"
        f"Question: {question}\n"
        f"Ground Truth: {ground_truth}\n"
        f"Prediction: {prediction}\n\n"
        "Answer (PASS or FAIL):"
    )
    try:
        response = groq_generate(_judge_client, prompt, max_tokens=5)
        return 'PASS' if 'PASS' in response.upper() else 'FAIL'
    except Exception:
        return 'FAIL'


def compute_bertscore(predictions: list, references: list) -> dict:
    try:
        from bert_score import score
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _, _, F1 = score(predictions, references, lang='en',
                             model_type='distilbert-base-uncased', verbose=False)
        raw_f1 = F1.mean().item()
        rescaled = (raw_f1 - 0.5) / 0.5
        return {
            'raw_f1': round(raw_f1, 4),
            'rescaled_f1': round(rescaled, 4),
            'bonus_hit': rescaled >= 0.55 or raw_f1 >= 0.88,
        }
    except Exception:
        return {'raw_f1': 0.0, 'rescaled_f1': 0.0, 'bonus_hit': False}


# ── Preload models at startup so first request is fast ──
@asynccontextmanager
async def lifespan(app: FastAPI):
    import threading
    def _preload():
        try:
            pipeline2("warmup")
        except Exception:
            pass
    threading.Thread(target=_preload, daemon=True).start()
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class QueryRequest(BaseModel):
    question: str
    ground_truth: str = ""


@app.post("/compare")
def compare(req: QueryRequest):
    try:
        p1 = pipeline1(req.question)
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": f"pipeline1 failed: {e}"})
    try:
        p2 = pipeline2(req.question)
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": f"pipeline2 failed: {e}"})
    try:
        p3 = pipeline3(req.question)
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": f"pipeline3 failed: {e}"})

    token_reduction = round((1 - p3["total_tokens"] / max(p2["total_tokens"], 1)) * 100, 1)

    result = {
        "llm_only":            p1,
        "basic_rag":           p2,
        "graphrag":            p3,
        "token_reduction_pct": token_reduction,
        "cost_reduction_pct":  token_reduction,
    }

    if req.ground_truth:
        result["judge_llm_only"]  = llm_judge(req.question, req.ground_truth, p1["answer"])
        result["judge_basic_rag"] = llm_judge(req.question, req.ground_truth, p2["answer"])
        result["judge_graphrag"]  = llm_judge(req.question, req.ground_truth, p3["answer"])
        result["bertscore"]       = compute_bertscore([p3["answer"]], [req.ground_truth])

    return result


@app.get("/")
def root():
    return {"status": "ok", "message": "GraphRAG API — POST /compare"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/debug")
def debug():
    """Returns which components are loaded — useful for diagnosing startup issues."""
    from pipelines.pipeline2_rag import _embedder, _index
    return {
        "embedder_loaded": _embedder is not None,
        "faiss_loaded": _index is not None,
    }
