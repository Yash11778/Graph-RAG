import json
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

from pipelines.pipeline1_llm import run as run_p1
from pipelines.pipeline2_rag import run as run_p2
from pipelines.pipeline3_graphrag import run as run_p3

app = FastAPI(title="GraphRAG Comparison API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    question: str


class PipelineToggle(BaseModel):
    question: str
    run_p1: bool = True
    run_p2: bool = True
    run_p3: bool = True


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/compare")
def compare(req: QueryRequest):
    try:
        r1 = run_p1(req.question)
        r2 = run_p2(req.question)
        r3 = run_p3(req.question)
        reduction = (
            round((1 - r3["total_tokens"] / r2["total_tokens"]) * 100, 1)
            if r2["total_tokens"] > 0
            else 0
        )
        return {
            "question": req.question,
            "pipeline1_llm": r1,
            "pipeline2_rag": r2,
            "pipeline3_graphrag": r3,
            "token_reduction_pct": reduction,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query/p1")
def query_p1(req: QueryRequest):
    try:
        return run_p1(req.question)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query/p2")
def query_p2(req: QueryRequest):
    try:
        return run_p2(req.question)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query/p3")
def query_p3(req: QueryRequest):
    try:
        return run_p3(req.question)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/results/summary")
def results_summary():
    summary_path = Path(__file__).parent.parent / "eval" / "results" / "summary.json"
    if not summary_path.exists():
        raise HTTPException(status_code=404, detail="Run eval/evaluate.py first")
    with open(summary_path) as f:
        return json.load(f)
