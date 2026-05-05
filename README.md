# GraphRAG Hackathon

## Project goal
Prove GraphRAG (Pipeline 3) uses 60-80% fewer tokens than Basic RAG (Pipeline 2) while
maintaining >90% LLM-judge pass rate. Ship an interactive comparison dashboard.

## Setup order
```
pip install -r api/requirements.txt
python scripts/download_dataset.py    # Wikipedia articles -> data/raw/
python scripts/preprocess.py          # 256-token chunks -> data/chunks/
python scripts/build_faiss.py         # FAISS index -> data/chunks/rag_index.faiss

# Start TigerGraph workspace on tgcloud.io, then:
python scripts/setup_tg_schema.py     # Create Article + Chunk schema with NEXT_CHUNK edges
python scripts/ingest_tg.py           # Ingest 10,283 chunks with graph edges into TigerGraph
```

> TigerGraph is required for Pipeline 3. Start the workspace on tgcloud.io before running
> setup_tg_schema.py and ingest_tg.py. Once ingested, the graph persists — no need to
> re-ingest on subsequent runs.

## Run
```
# API (port 8080)
uvicorn api.app:app --reload --port 8080

# Frontend (port 5173)
cd frontend && npm install && npm run dev

# Full eval
python eval/evaluate.py
```

## Pipelines
| # | File | Strategy |
|---|------|----------|
| 1 | pipelines/pipeline1_llm.py | Pure LLM, no retrieval |
| 2 | pipelines/pipeline2_rag.py | FAISS vector search, top_k=5 |
| 3 | pipelines/pipeline3_graphrag.py | FAISS top_k=2 entry points → TigerGraph NEXT_CHUNK graph traversal → coherent article context |

## Key numbers
- LLM: Groq llama-3.3-70b-versatile, temperature=0.0
- Embeddings: all-MiniLM-L6-v2 (dim=384)
- Token counter: tiktoken cl100k_base
- Avg token reduction (GraphRAG vs Basic RAG): ~66%

## API endpoints
```
POST /compare   { "question": "...", "ground_truth": "..." }  -> all three pipelines + reduction %
GET  /health    -> {"status":"ok"}
GET  /          -> API info
```
