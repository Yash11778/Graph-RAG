# GraphRAG Hackathon — TigerGraph

Proves GraphRAG (Pipeline 3) uses **≥85% fewer tokens** than Basic RAG (Pipeline 2)
while maintaining high answer accuracy. Built on the [TigerGraph GraphRAG repo](https://github.com/tigergraph/graphrag).

## Architecture

```
Dataset (2.3M tokens, 371 Wikipedia articles)
    │
    ├─ Pipeline 1: LLM-Only (Groq llama-3.3-70b)
    │   └─ No retrieval. Raw baseline.
    │
    ├─ Pipeline 2: Basic RAG
    │   └─ FAISS vector search (top_k=5) → Groq LLM
    │
    └─ Pipeline 3: GraphRAG  ← TigerGraph GraphRAG repo
        └─ pyTigerGraph SDK → GraphRAG Docker service (port 8003)
            └─ Hybrid retriever: DocumentChunk + Community vector search
                └─ Multi-hop graph traversal (num_hops=2, Concept/Relationship edges)
                    └─ Gemini LLM synthesis

Dashboard: React + Recharts · LLM-as-a-Judge · BERTScore
```

## Setup Order

### Prerequisites
- Python 3.10+
- Docker Desktop (for GraphRAG service)
- TigerGraph Savanna workspace running at tgcloud.io

### Step 1 — Install & prepare data
```bash
pip install -r api/requirements.txt
python scripts/download_dataset.py       # Wikipedia articles → data/raw/dataset.jsonl
python scripts/preprocess.py             # FAISS chunks → data/chunks/
python scripts/build_faiss.py            # FAISS index for Pipeline 2
python scripts/prepare_graphrag_data.py  # Convert to GraphRAG JSONL format
python scripts/generate_qa_pairs.py      # Generate QA pairs from actual dataset
```

### Step 2 — Start TigerGraph GraphRAG Docker service
```bash
cd graphrag
docker compose up -d graphrag graphrag-ecc chat-history
cd ..
```

### Step 3 — Initialize and ingest through GraphRAG service
```bash
python scripts/init_graphrag_service.py  # Creates GraphRAG schema on TigerGraph
python scripts/ingest_via_graphrag.py    # Ingest 371 articles through GraphRAG service
                                          # (chunking + Gemini embedding + entity extraction)
```

### Step 4 — Run
```bash
# API (port 8080)
uvicorn api.app:app --reload --port 8080

# Frontend (port 5173)
cd frontend && npm install && npm run dev

# Full evaluation (tokens + latency + LLM-judge + BERTScore)
python eval/evaluate.py
```

## Pipelines

| # | Strategy | Tokens (avg) | Reduction |
|---|----------|-------------|-----------|
| 1 | LLM-Only | ~30 | baseline |
| 2 | Basic RAG (FAISS top_k=5) | ~1,400 | — |
| 3 | **GraphRAG** (TigerGraph Hybrid, num_hops=2) | **~150–200** | **~85%** |

## Pipeline 3 — How it uses TigerGraph GraphRAG

Pipeline 3 calls the official TigerGraph GraphRAG service via `pyTigerGraph`:

```python
conn.ai.configureGraphRAGHost("http://localhost:8003")
resp = conn.ai.answerQuestion(question, method="hybrid", method_parameters={
    "indices":      ["DocumentChunk", "Community"],
    "top_k":        2,
    "num_hops":     2,
    "num_seen_min": 1,
})
```

The service performs:
1. **Vector search** on `DocumentChunk` + `Community` vertices
2. **Multi-hop graph traversal** via `Concept` and `Relationship` edges
3. **Graph co-occurrence re-ranking** — chunks linked by shared entities score higher
4. **Community summaries** — cluster-level knowledge reduces context further
5. **Gemini LLM synthesis** of the compact, graph-focused context

This is genuine GraphRAG — not FAISS with a smaller `top_k`.

## API Endpoints
```
POST /compare   { "question": "...", "ground_truth": "..." }
GET  /health
GET  /
```

## Judging Criteria Met

| Criterion | Weight | Our Result |
|-----------|--------|------------|
| Token Reduction | 30% | ~85% (GraphRAG vs Basic RAG) |
| Answer Accuracy | 30% | LLM-judge + BERTScore evaluated |
| Performance | 20% | Latency tracked per pipeline |
| Engineering | 20% | Dashboard + GraphRAG repo integration |
