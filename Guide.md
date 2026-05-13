# How to Run the GraphRAG Hackathon Project

## What's in this project

Three retrieval pipelines compared side-by-side:

| Pipeline | Strategy | Notes |
|----------|----------|-------|
| Pipeline 1 — LLM-Only | Raw Groq call, no retrieval | Baseline |
| Pipeline 2 — Basic RAG | FAISS top-5 → Groq | ~1,400 tokens/query |
| Pipeline 3 — GraphRAG | FAISS seed + TigerGraph hybrid graph expansion → Groq | ~150–300 tokens/query |

A React dashboard (port 5173) lets you query all three at once and see token/accuracy comparisons.

---

## Prerequisites

- Python 3.10+
- Docker Desktop (running)
- Node.js 18+ (for frontend)
- A `.env` file in `graphrag-hackathon/` with at least:
  ```
  GROQ_API_KEY=gsk_...
  ```

---

## One-time data setup (only needed once)

Run these from `graphrag-hackathon/`:

```bash
pip install -r api/requirements.txt

python scripts/download_dataset.py      # downloads Wikipedia articles → data/raw/
python scripts/preprocess.py            # chunks articles → data/chunks/chunks.pkl
python scripts/build_faiss.py           # builds FAISS index → data/chunks/rag_index.faiss
python scripts/generate_qa_pairs.py     # creates data/qa/qa_pairs.json
```

If `data/chunks/chunks.pkl` and `data/chunks/rag_index.faiss` already exist, skip those steps.

---

## Running the project

### Option A — Without TigerGraph (Pipeline 3 falls back to FAISS-only)

This is the current working state. Pipeline 3 will still return answers using FAISS context but skips the graph expansion step.

**Terminal 1 — API server** (from `graphrag-hackathon/`)
```bash
uvicorn api.app:app --reload --port 8080
```

**Terminal 2 — Frontend** (from `graphrag-hackathon/frontend/`)
```bash
npm install
npm run dev
```

Open http://localhost:5173

---

### Option B — With TigerGraph GraphRAG (full Pipeline 3)

#### Step 1 — Start the Docker stack

From `graphrag-hackathon/graphrag/`:
```bash
docker compose up -d graphrag graphrag-ecc chat-history
```

Wait ~30 seconds for services to be healthy. The GraphRAG service listens on **port 8003**.

Verify it's up:
```bash
curl http://localhost:8003/
```

#### Step 2 — Initialize the schema (only once after fresh Docker start)

From `graphrag-hackathon/`:
```bash
python scripts/init_graphrag_service.py
```

#### Step 3 — Ingest data (only once, or after wiping the database)

```bash
python scripts/ingest_via_graphrag.py
```

This pushes Wikipedia articles through the GraphRAG service (chunking + embedding + entity extraction). Takes 30–60 minutes for the full dataset.

To re-ingest only articles that failed previously:
```bash
python scripts/reingest_failed.py
```

#### Step 4 — Start API + frontend (same as Option A)

```bash
# Terminal 1 — from graphrag-hackathon/
uvicorn api.app:app --reload --port 8080

# Terminal 2 — from graphrag-hackathon/frontend/
npm run dev
```

---

## Running the evaluation

From `graphrag-hackathon/`:
```bash
python eval/evaluate.py
```

Runs all 20 QA pairs through all three pipelines, judges each answer (PASS/FAIL), computes BERTScore, and writes results to `eval/results/eval_results.csv`.

---

## Why you see `TG retrieval error` during evaluation

```
TG retrieval error: HTTPConnectionPool(host='localhost', port=8003):
  Max retries exceeded ... No connection could be made because the
  target machine actively refused it
```

**Cause:** The TigerGraph GraphRAG Docker service (port 8003) is not running.

**Effect:** Pipeline 3 falls back gracefully to FAISS-only context and still produces answers. The `[graphrag] judge=PASS` lines you see are real — answers come from FAISS retrieval without graph expansion.

**Fix:** Start the Docker stack as in Option B, Step 1.

---

## Project structure

```
graphrag-hackathon/
├── api/
│   ├── app.py                  # FastAPI — POST /compare
│   └── requirements.txt
├── data/
│   ├── raw/                    # downloaded Wikipedia articles
│   ├── chunks/                 # FAISS index + pickled chunks
│   └── qa/qa_pairs.json        # 20 QA pairs for evaluation
├── eval/
│   ├── evaluate.py             # full evaluation script
│   └── results/eval_results.csv
├── frontend/                   # React + Recharts dashboard
├── graphrag/                   # TigerGraph GraphRAG repo (Docker)
│   ├── docker-compose.yml
│   └── configs/server_config.json
├── pipelines/
│   ├── pipeline1_llm.py        # LLM-only
│   ├── pipeline2_rag.py        # FAISS RAG
│   ├── pipeline3_graphrag.py   # FAISS seed + TigerGraph hybrid
│   └── utils.py                # Groq client, token counting
└── scripts/
    ├── download_dataset.py
    ├── preprocess.py
    ├── build_faiss.py
    ├── generate_qa_pairs.py
    ├── init_graphrag_service.py
    └── ingest_via_graphrag.py
```

---

## API

```
POST http://localhost:8080/compare
Content-Type: application/json

{
  "question": "Who invented the telephone?",
  "ground_truth": "Alexander Graham Bell"
}
```

`ground_truth` is optional — include it to get LLM judge verdicts and BERTScore in the response.
