# GraphRAG Hackathon

## Project goal
Prove GraphRAG (Pipeline 3) uses 60-80% fewer tokens than Basic RAG (Pipeline 2) while
maintaining >90% LLM-judge pass rate. Ship an interactive comparison dashboard.

## Setup order
```
pip install -r api/requirements.txt
python scripts/download_dataset.py    # ~1000 Wikipedia articles -> data/raw/
python scripts/preprocess.py          # 256-token chunks -> data/chunks/
python scripts/build_faiss.py         # FAISS index -> data/faiss/
# Start TigerGraph GraphRAG service at localhost:8000, then:
python scripts/ingest_graphrag.py     # Push chunks into the graph
```

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
| 3 | pipelines/pipeline3_graphrag.py | TigerGraph community retrieval, top_k=3, num_hops=2 |

## Key numbers
- Token cost: $0.075 / 1M tokens (Gemini 1.5 Flash)
- Embeddings: all-MiniLM-L6-v2 (dim=384)
- Token counter: tiktoken cl100k_base
- temperature=0.0 everywhere

## API endpoints
```
POST /compare          { "question": "..." }  -> all three pipelines + reduction %
POST /query/p1|p2|p3   { "question": "..." }  -> single pipeline result
GET  /results/summary  -> eval summary JSON
GET  /health
```

## GraphRAG service contract
Expected at GRAPHRAG_URL (default http://localhost:8000).
- POST /ingest   { "documents": [{id, text, metadata}] }
- POST /retrieve { "query", "top_k", "num_hops", "community_level", "retriever_type" }
                 -> { "context": "..." }
