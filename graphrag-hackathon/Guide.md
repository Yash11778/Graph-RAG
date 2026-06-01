# How to Run the GraphRAG Hackathon Project

## What's in This Project

Three retrieval pipelines compared side-by-side on a 100M-token Wikipedia knowledge graph:

| Pipeline | Strategy | Avg Tokens/Query |
|----------|----------|-----------------|
| Pipeline 1 — LLM-Only | Raw Gemini call, no retrieval | ~103 |
| Pipeline 2 — Basic RAG | FAISS top-5 → Gemini | ~1,266 |
| Pipeline 3 — GraphRAG | FAISS seed + TigerGraph hybrid multi-hop → Gemini | ~297 |

A React dashboard (port 5173) queries all three simultaneously and shows token counts, latency, cost, and accuracy comparisons.

---

## Prerequisites

| Tool | Version | Why |
|------|---------|-----|
| Python | 3.10+ | API server + scripts |
| Node.js | 18+ | React frontend |
| Docker Desktop | any | TigerGraph GraphRAG service (Option B only) |
| Gemini API key | — | All 3 pipelines use Gemini Flash |

---

## Step 0 — Environment Setup

Create `.env` in `graphrag-hackathon/` (copy from `.env.example`):

```env
GEMINI_API_KEY=AIza...           # required
GROQ_API_KEY=gsk_...             # optional (not used in current pipelines)
TG_HOST=https://...tgcloud.io    # required for Option B (TigerGraph)
TG_USERNAME=your@email.com
TG_PASSWORD=your_tg_password
TG_GRAPH=MyDatabase
GRAPHRAG_URL=http://localhost:8000
```

Install Python dependencies from `graphrag-hackathon/`:

```bash
pip install -r api/requirements.txt
```

---

## Step 1 — One-Time Data Setup

Run these from `graphrag-hackathon/`. Skip any step if the output files already exist.

```bash
# Download 100,850 Wikipedia articles → data/raw/dataset.jsonl
python scripts/download_dataset.py

# Chunk articles → data/chunks/chunks.pkl  (464,739 chunks)
python scripts/preprocess.py

# Build FAISS index → data/chunks/rag_index.faiss
python scripts/build_faiss.py

# Generate QA evaluation pairs → data/qa/qa_pairs.json
python scripts/generate_qa_pairs.py
```

**Check if you can skip:** If `data/chunks/chunks.pkl` and `data/chunks/rag_index.faiss` both exist, skip preprocess and build_faiss.

---

## Option A — Without TigerGraph (FAISS-only, fastest to start)

Pipeline 3 falls back gracefully to FAISS-only context when TigerGraph is not running. All three pipelines still produce answers.

**Terminal 1 — API server** (from `graphrag-hackathon/`):
```bash
uvicorn api.app:app --reload --port 8080
```

**Terminal 2 — Frontend** (from `graphrag-hackathon/frontend/`):
```bash
npm install
npm run dev
```

Open **http://localhost:5173** — the dashboard is live.

---

## Option B — With TigerGraph GraphRAG (full graph expansion)

This activates Pipeline 3's multi-hop graph traversal via TigerGraph Savanna.

### Step B1 — Start the Docker stack

From `graphrag-hackathon/graphrag/`:
```bash
docker compose up -d graphrag graphrag-ecc chat-history
```

Wait ~30 seconds. The GraphRAG service listens on **port 8003**.

Verify it's running:
```bash
curl http://localhost:8003/
```

### Step B2 — Initialize the schema (once per fresh database)

From `graphrag-hackathon/`:
```bash
python scripts/init_graphrag_service.py
```

This creates the GraphRAG schema (`DocumentChunk`, `Community`, `Concept`, `Relationship` vertices/edges) on your TigerGraph instance.

### Step B3 — Ingest data (once, or after wiping the database)

```bash
python scripts/ingest_via_graphrag.py
```

This pushes Wikipedia articles through the GraphRAG service:
- Chunking (semantic chunker)
- Gemini embedding generation
- LLM entity/relationship extraction
- Community detection (Louvain algorithm)

Takes **30–60 minutes** for the full dataset.

To retry only articles that failed:
```bash
python scripts/reingest_failed.py
```

### Step B4 — Start API + Frontend

Same as Option A:
```bash
# Terminal 1 — from graphrag-hackathon/
uvicorn api.app:app --reload --port 8080

# Terminal 2 — from graphrag-hackathon/frontend/
npm run dev
```

---

## Running the Evaluation

From `graphrag-hackathon/`:
```bash
python eval/evaluate.py
```

Runs all QA pairs through all three pipelines, judges each answer (PASS/FAIL), computes BERTScore, and writes results to `eval/results/eval_results.csv`.

---

## Deployment with Docker

Build and run the API as a container:

```bash
# Build
docker build -t graphrag-hackathon .

# Run (set your API keys as env vars)
docker run -p 8080:8080 \
  -e GEMINI_API_KEY=AIza... \
  -v $(pwd)/data:/app/data \
  graphrag-hackathon
```

The Dockerfile pre-caches the fastembed ONNX model so the first request is fast.

For the frontend, build a static bundle and serve it behind a CDN or Vercel:
```bash
cd frontend
npm run build   # outputs to frontend/dist/
```

Set `VITE_API_BASE` to your deployed API URL when building for production:
```bash
VITE_API_BASE=https://your-api.example.com npm run build
```

---

## Troubleshooting

### `TG retrieval error: ... No connection could be made`

TigerGraph GraphRAG Docker service is not running.

**Effect:** Pipeline 3 falls back to FAISS-only context — answers still work.  
**Fix:** Start the Docker stack as in Option B, Step B1.

### `pipeline2 load failed: ...`

FAISS index or chunks file is missing.

**Fix:** Run `python scripts/build_faiss.py` (and `python scripts/preprocess.py` first if `chunks.pkl` is also missing).

### `GEMINI_API_KEY not set` / `AuthenticationError`

**Fix:** Make sure `.env` exists in `graphrag-hackathon/` with a valid `GEMINI_API_KEY`.

### Frontend shows `Request failed` / network error

API server is not running or is on a different port.

**Fix:** Confirm `uvicorn api.app:app --reload --port 8080` is running. The Vite dev server proxies `/compare` to `localhost:8080` (see `frontend/vite.config.js`).

### First request takes 60+ seconds

fastembed is downloading the ONNX model on first use.

**Fix:** Wait for it once — subsequent requests are fast. In Docker, the model is baked into the image (see Dockerfile).

---

## API Reference

### `POST /compare`

Runs all three pipelines in sequence and returns a full comparison.

**Request body:**
```json
{
  "question": "Who invented the telephone?",
  "ground_truth": "Alexander Graham Bell"
}
```
`ground_truth` is optional. Omit it to skip LLM judge and BERTScore.

**Response:**
```json
{
  "llm_only": {
    "pipeline": "llm_only",
    "answer": "Alexander Graham Bell invented the telephone in 1876.",
    "prompt_tokens": 68,
    "completion_tokens": 35,
    "total_tokens": 103,
    "latency_s": 0.78,
    "cost_usd": 0.000008
  },
  "basic_rag": {
    "pipeline": "basic_rag",
    "answer": "...",
    "total_tokens": 1243,
    "latency_s": 13.1,
    "cost_usd": 0.000093,
    "sources": ["Bell telephone article", "..."]
  },
  "graphrag": {
    "pipeline": "graphrag",
    "answer": "...",
    "total_tokens": 312,
    "latency_s": 5.2,
    "cost_usd": 0.000023,
    "retriever": "faiss+tigergraph_hybrid",
    "context_tokens": 287,
    "sources": ["Bell article"]
  },
  "token_reduction_pct": 74.9,
  "cost_reduction_pct": 74.9,
  "judge_llm_only":  "FAIL",
  "judge_basic_rag": "PASS",
  "judge_graphrag":  "PASS",
  "bertscore": {
    "raw_f1": 0.912,
    "rescaled_f1": 0.824,
    "bonus_hit": true
  }
}
```

### `GET /health`
Returns `{"status": "ok"}`.

### `GET /debug`
Returns `{"embedder_loaded": true, "faiss_loaded": true}` — useful for diagnosing startup issues.

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `api/app.py` | FastAPI server, `/compare` endpoint, LLM judge, BERTScore |
| `api/requirements.txt` | Python dependencies |
| `pipelines/pipeline1_llm.py` | LLM-only baseline |
| `pipelines/pipeline2_rag.py` | FAISS RAG (top_k=5) |
| `pipelines/pipeline3_graphrag.py` | FAISS seed + TigerGraph hybrid |
| `pipelines/utils.py` | Gemini client, token counter, cost helper |
| `frontend/src/App.jsx` | Full React dashboard (single file) |
| `frontend/vite.config.js` | Proxies `/compare` → API |
| `graphrag/configs/server_config.json` | TigerGraph + Gemini config for Docker service |
| `.env` | API keys and TigerGraph credentials |
| `scripts/ingest_via_graphrag.py` | Ingests articles into TigerGraph |
| `scripts/count_tokens_gemini.py` | Audits total token usage via Gemini API |
| `eval/evaluate.py` | Full evaluation suite |

---

## Token & Cost Summary

Model: **Gemini 1.5 Flash** ($0.075/1M input · $0.30/1M output)

| Operation | Tokens | Approx Cost |
|-----------|--------|-------------|
| Full ingestion (100K articles) | ~75M | ~$0.01 |
| Per question (all 3 pipelines) | ~1,700 | ~$0.001 |
| 1,000 questions | ~1.7M | ~$0.13 |
| $40 budget | — | ~30,000–40,000 questions |
