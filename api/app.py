import os
import sys
import time
import threading
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import asynccontextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from pipelines.pipeline1_llm import pipeline1
from pipelines.pipeline2_rag import pipeline2
from pipelines.pipeline3_graphrag import pipeline3
from pipelines.utils import gemini_generate, setup_gemini


# ── LLM judge ─────────────────────────────────────────────────────────────────
_judge_client = setup_gemini()


def llm_judge(question: str, ground_truth: str, prediction: str) -> str:
    prompt = (
        "You are an evaluator. Respond with exactly one word: PASS or FAIL.\n"
        "PASS if the prediction contains the key facts from the ground truth and addresses the question, "
        "even if worded differently or with additional context.\n"
        "FAIL only if the prediction is clearly wrong, contradicts the ground truth, or is completely irrelevant.\n"
        "Be generous — partial but correct answers should PASS.\n\n"
        f"Question: {question}\n"
        f"Ground Truth: {ground_truth}\n"
        f"Prediction: {prediction}\n\n"
        "Answer (PASS or FAIL):"
    )
    try:
        response = gemini_generate(_judge_client, prompt, max_tokens=5)
        return 'PASS' if 'PASS' in response.upper() else 'FAIL'
    except Exception:
        return 'FAIL'


def compute_bertscore(predictions: list, references: list) -> dict:
    # BERTScore loads torch + distilbert (~350 MB). On a 512 MB free-tier host that
    # tips the process into OOM, so the deployed server sets DISABLE_BERTSCORE=1 and
    # relies on the live LLM-as-a-Judge metric instead. The official BERTScore numbers
    # come from the local benchmark run (eval/evaluate.py), which has no memory limit.
    if os.getenv('DISABLE_BERTSCORE', '').lower() in ('1', 'true', 'yes'):
        return {'raw_f1': 0.0, 'rescaled_f1': 0.0, 'bonus_hit': False}
    try:
        from bert_score import score
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _, _, F1 = score(predictions, references, lang='en',
                             model_type='distilbert-base-uncased', verbose=False)
        raw_f1   = F1.mean().item()
        rescaled = (raw_f1 - 0.5) / 0.5
        return {
            'raw_f1':      round(raw_f1, 4),
            'rescaled_f1': round(rescaled, 4),
            'bonus_hit':   rescaled >= 0.55 or raw_f1 >= 0.88,
        }
    except Exception:
        return {'raw_f1': 0.0, 'rescaled_f1': 0.0, 'bonus_hit': False}


# ── Startup: preload models in background so first request is fast ─────────────
_preload_done  = False
_preload_error = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _preload_done, _preload_error
    def _preload():
        global _preload_done, _preload_error
        try:
            from pipelines.pipeline2_rag import _load as load2
            from pipelines.pipeline3_graphrag import _load as load3, _ensure_entity_cache
            load2()
            load3()
            _ensure_entity_cache()   # pre-warm TigerGraph entity ID cache
            # BERTScore (distilbert + torch) is NOT preloaded — it costs ~300MB RAM
            # which exceeds the free-tier 512MB limit. It loads lazily on first eval request.
            _preload_done = True
            print("INFO:     Models preloaded successfully", flush=True)
        except Exception as e:
            _preload_error = str(e)
            print(f"WARNING:  Preload failed: {e}", flush=True)
    threading.Thread(target=_preload, daemon=True).start()
    yield


# ── Thread pools ──────────────────────────────────────────────────────────────
# Pipeline pool: one worker per pipeline (3 concurrent).
# Eval pool: judge × 3 + BERTScore × 1 all run in parallel after pipelines finish.
_pipeline_executor = ThreadPoolExecutor(max_workers=3)
_eval_executor     = ThreadPoolExecutor(max_workers=4)

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    question:     str
    ground_truth: str = ""


@app.post("/compare")
def compare(req: QueryRequest):
    """Run all three pipelines in parallel and return a combined comparison result."""
    futures = {
        'llm_only':  _pipeline_executor.submit(pipeline1, req.question),
        'basic_rag': _pipeline_executor.submit(pipeline2, req.question),
        'graphrag':  _pipeline_executor.submit(pipeline3, req.question),
    }

    results: dict = {}
    for name, future in futures.items():
        try:
            results[name] = future.result(timeout=90)
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"detail": f"{name} pipeline failed: {e}"},
            )

    p1, p2, p3 = results['llm_only'], results['basic_rag'], results['graphrag']

    basic_rag_ok = p2.get('status') != 'faiss_unavailable'

    # GraphRAG only counts as a genuine result when it actually retrieved graph context
    # and produced an answer from it. A retrieval miss returns a ~9-token sentinel — counting
    # that as a "reduction" would fabricate a 99%+ win, so we report it honestly instead.
    graphrag_ok = bool(p3.get('graph_context_found')) and p3.get('context_tokens', 0) > 0
    graphrag_status = p3.get('status', 'ok' if graphrag_ok else 'no_context')

    if graphrag_ok and basic_rag_ok:
        # Token reduction: GraphRAG vs Basic RAG
        token_reduction = round(
            (1 - p3['total_tokens'] / max(p2['total_tokens'], 1)) * 100, 1
        )
        # Cost reduction: derived from actual cost_usd values (not a token proxy)
        cost_reduction = round(
            (1 - p3['cost_usd'] / max(p2['cost_usd'], 1e-9)) * 100, 1
        )
    else:
        # No graph context, or FAISS unavailable → no genuine comparison to report.
        token_reduction = None
        cost_reduction = None

    result = {
        'llm_only':            p1,
        'basic_rag':           p2,
        'graphrag':            p3,
        'graphrag_status':     graphrag_status,
        'token_reduction_pct': token_reduction,
        'cost_reduction_pct':  cost_reduction,
    }

    if req.ground_truth:
        # Run all 4 eval tasks in parallel — previously sequential, adding ~8s total.
        eval_futures = {
            'judge_llm_only':  _eval_executor.submit(llm_judge, req.question, req.ground_truth, p1['answer']),
            'judge_basic_rag': _eval_executor.submit(llm_judge, req.question, req.ground_truth, p2['answer']),
            'judge_graphrag':  _eval_executor.submit(llm_judge, req.question, req.ground_truth, p3['answer']),
            'bertscore':       _eval_executor.submit(compute_bertscore, [p3['answer']], [req.ground_truth]),
        }
        for key, fut in eval_futures.items():
            try:
                result[key] = fut.result(timeout=60)
            except Exception:
                pass

    return result


@app.get("/")
def root():
    return {"status": "ok", "message": "GraphRAG API — POST /compare"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    """Returns whether the model preload has finished. Poll this before the first query."""
    return {
        "ready": _preload_done,
        "error": _preload_error,
    }


@app.get("/debug")
def debug():
    """Returns which components are loaded — useful for diagnosing startup issues."""
    from pipelines.pipeline2_rag import _embedder, _index
    return {
        "embedder_loaded": _embedder is not None,
        "faiss_loaded":    _index is not None,
        "preload_done":    _preload_done,
        "preload_error":   _preload_error,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080, reload=False)
