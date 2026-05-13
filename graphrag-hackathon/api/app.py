import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from pipelines.pipeline1_llm import pipeline1
from pipelines.pipeline2_rag import pipeline2
from pipelines.pipeline3_graphrag import pipeline3
from eval.evaluate import llm_judge, compute_bertscore

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class QueryRequest(BaseModel):
    question: str
    ground_truth: str = ""


@app.post("/compare")
def compare(req: QueryRequest):
    p1 = pipeline1(req.question)
    p2 = pipeline2(req.question)
    p3 = pipeline3(req.question)

    token_reduction = round((1 - p3["total_tokens"] / max(p2["total_tokens"], 1)) * 100, 1)

    result = {
        "llm_only":          p1,
        "basic_rag":         p2,
        "graphrag":          p3,
        "token_reduction_pct": token_reduction,
        "cost_reduction_pct":  token_reduction,
    }

    if req.ground_truth:
        result["judge_llm_only"]  = llm_judge(req.question, req.ground_truth, p1["answer"])
        result["judge_basic_rag"] = llm_judge(req.question, req.ground_truth, p2["answer"])
        result["judge_graphrag"]  = llm_judge(req.question, req.ground_truth, p3["answer"])

        bs = compute_bertscore(
            predictions=[p3["answer"]],
            references=[req.ground_truth],
        )
        result["bertscore"] = bs

    return result


@app.get("/")
def root():
    return {"status": "ok", "message": "GraphRAG API — POST /compare"}


@app.get("/health")
def health():
    return {"status": "ok"}
