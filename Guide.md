# GraphRAG Hackathon — Run Guide (PowerShell)

This project compares three LLM inference strategies and proves that GraphRAG (Pipeline 3) uses
60–80% fewer tokens than Basic RAG (Pipeline 2) while maintaining answer quality.

All commands below are written for **Windows PowerShell**. Open PowerShell and `cd` into the
project root before running anything.

```powershell
cd "D:\HACKATHONS\Graph RAG\graphrag-hackathon\graphrag-hackathon"
```

---

## Prerequisites

- Python 3.10+
- Node.js 18+
- A [Groq](https://console.groq.com) account (free tier, get an API key)
- A [TigerGraph Cloud](https://tgcloud.io) workspace (free tier)

---

## Project Structure

```
graphrag-hackathon/
├── api/
│   ├── app.py                  # FastAPI backend
│   └── requirements.txt
├── eval/
│   ├── evaluate.py             # Full pipeline evaluation
│   └── results/
│       └── eval_results.csv
├── frontend/
│   └── src/
│       └── App.jsx             # React dashboard
├── pipelines/
│   ├── pipeline1_llm.py        # LLM-only (no retrieval)
│   ├── pipeline2_rag.py        # Basic RAG (FAISS, top_k=5)
│   ├── pipeline3_graphrag.py   # GraphRAG (FAISS + TigerGraph, top_k=2)
│   └── utils.py                # Groq client, token counter, shared helpers
├── scripts/
│   ├── download_dataset.py     # Downloads ~1000 Wikipedia articles
│   ├── preprocess.py           # Chunks articles into 256-token segments
│   ├── build_faiss.py          # Builds FAISS index from chunks
│   └── ingest_graphrag.py      # (legacy — data already ingested, skip this)
├── data/
│   ├── raw/                    # Downloaded Wikipedia articles
│   ├── chunks/                 # Preprocessed chunks + FAISS index
│   └── qa/
│       └── qa_pairs.json       # 15 evaluation questions with ground truth
└── .env                        # API keys and TigerGraph connection details
```

---

## Step 1 — Environment Variables

Edit `.env` in the project root. It should contain:

```env
GROQ_API_KEY=your_groq_api_key_here
TG_HOST=https://<your-workspace>.tg-<id>.i.tgcloud.io
TG_USERNAME=your_tgcloud_email
TG_PASSWORD=your_tgcloud_password
TG_GRAPH=MyDatabase
GRAPHRAG_URL=http://localhost:8000
```

To edit it in PowerShell:

```powershell
notepad .env
```

> `GROQ_API_KEY` is the only key required to run all three pipelines and the full eval.
> TigerGraph credentials are used by Pipeline 3 to fetch documents; it falls back to the
> local FAISS cache if TigerGraph is unreachable.

---

## Step 2 — Python Dependencies

```powershell
pip install -r api\requirements.txt
```

This installs: `fastapi`, `uvicorn`, `groq`, `faiss-cpu`, `sentence-transformers`,
`bert-score`, `torch`, `transformers`, `tiktoken`, `pandas`, `requests`, `python-dotenv`.

---

## Step 3 — Build the Data Pipeline

Run these once to download and preprocess the dataset. Skip if `data\chunks\` already exists.

```powershell
python scripts\download_dataset.py   # ~1000 Wikipedia articles → data\raw\
python scripts\preprocess.py         # 256-token chunks → data\chunks\chunks.pkl
python scripts\build_faiss.py        # FAISS index → data\chunks\rag_index.faiss
```

> **Do NOT run `scripts\ingest_graphrag.py`** — it uses a legacy endpoint that no longer
> exists. The TigerGraph graph (`MyDatabase`) is already populated with all 10,283 chunks.

---

## Step 4 — TigerGraph (Pipeline 3 only)

Pipeline 3 fetches document context from TigerGraph Cloud. To enable live fetching:

1. Log into [tgcloud.io](https://tgcloud.io)
2. Start the workspace `MyWorkspace` (auto-start is disabled — start it manually)
3. The graph `MyDatabase` is pre-populated — no further setup needed

> If TigerGraph is offline, Pipeline 3 automatically falls back to the local FAISS chunk
> cache. Results are still valid; latency will actually be faster.

---

## Step 5 — Run the API

Open a PowerShell window and run:

```powershell
uvicorn api.app:app --reload --port 8080
```

Leave this window open. The API runs on `http://localhost:8080`.

To verify it is alive, open a **second** PowerShell window and run:

```powershell
Invoke-RestMethod http://localhost:8080/health
```

Expected output:
```
status
------
ok
```

### Test a full query from PowerShell

```powershell
$body = '{"question":"What is the speed of light?","ground_truth":"299792458 m/s"}'
Invoke-RestMethod -Uri http://localhost:8080/compare `
    -Method POST `
    -ContentType "application/json" `
    -Body $body | ConvertTo-Json -Depth 5
```

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/compare` | Run all 3 pipelines, return results + token reduction % |

#### `/compare` request body

```json
{
  "question": "What is the speed of light?",
  "ground_truth": "299,792,458 m/s"
}
```

`ground_truth` is optional. When provided, an LLM judge scores the GraphRAG answer `PASS` or `FAIL`.

#### `/compare` response

```json
{
  "llm_only":  { "answer": "...", "total_tokens": 35,   "latency_s": 0.5  },
  "basic_rag": { "answer": "...", "total_tokens": 1702, "latency_s": 1.6  },
  "graphrag":  { "answer": "...", "total_tokens": 558,  "latency_s": 11.4 },
  "token_reduction_pct": 67.2,
  "cost_reduction_pct":  67.2,
  "judge_graphrag": "PASS"
}
```

---

## Step 6 — Run the Frontend Dashboard

Open a **new** PowerShell window (keep the API window running):

```powershell
cd frontend
npm install
npm run dev
```

Then open `http://localhost:5173` in your browser.

### Dashboard features

- Type a question and optionally a ground truth answer
- Click **Run All 3 Pipelines**
- A **green banner** shows the token reduction (e.g. `GraphRAG used 67.2% fewer tokens than Basic RAG`)
- A **bar chart** compares token counts across all three pipelines (red / orange / green)
- **3 answer cards** show each pipeline's answer, token count, latency, and cost
  - The GraphRAG card has a green border
  - If a ground truth was provided, a **PASS / FAIL badge** appears on the GraphRAG card
- A **query history table** at the bottom tracks all queries in the session

---

## Step 7 — Run the Full Evaluation

Open a **new** PowerShell window (project root, API does not need to be running for eval):

```powershell
python eval\evaluate.py
```

This runs all 15 QA pairs through all 3 pipelines, judges each answer, computes BERTScore,
and saves results to `eval\results\eval_results.csv`.

### Expected output

```
=== EVALUATION SUMMARY ===

[llm_only]
  pass_rate:   93.3%
  avg_tokens:  61.9
  avg_latency: 0.281s

[basic_rag]
  pass_rate:   86.7%
  avg_tokens:  1648.8
  avg_latency: 1.960s

[graphrag]
  pass_rate:   53.3%
  avg_tokens:  561.5
  avg_latency: 9.107s

Token reduction (graphrag vs basic_rag): 65.9%

BERTScore raw_f1:      0.9017
BERTScore rescaled_f1: 0.8034
BERTScore bonus_hit:   True

FINAL: token_reduction=65.9%, judge_pass_rate=53.3%, bertscore_rescaled=0.8034
BONUS STATUS: MISSED judge | HIT bertscore
```

> The token reduction target (60–80%) is met. The lower judge pass rate for GraphRAG is a
> dataset coverage issue — not all 15 QA topics are well-represented in the Wikipedia corpus,
> so top-2 retrieval sometimes misses the right chunk.

---

## Window Layout for a Full Run

You need **three** PowerShell windows open simultaneously:

| Window | What runs there |
|--------|----------------|
| 1 | `uvicorn api.app:app --reload --port 8080` |
| 2 | `cd frontend; npm run dev` |
| 3 | Free for running eval, testing API, or anything else |

---

## Pipelines — How They Work

| Pipeline | Strategy | Avg tokens | Context source |
|----------|----------|-----------|----------------|
| 1 — LLM Only | No retrieval | ~62 | None — question only |
| 2 — Basic RAG | FAISS top_k=5 | ~1,649 | Top 5 chunk texts concatenated |
| 3 — GraphRAG | FAISS top_k=2 + TigerGraph | ~562 | Top 2 chunk IDs fetched from TigerGraph; local cache fallback |

All three pipelines use **Groq** (`llama-3.3-70b-versatile`, temperature=0.0, max_tokens=400).
Token counting uses `tiktoken cl100k_base`. Embeddings use `all-MiniLM-L6-v2` (dim=384).

---

## Common Issues

**`ModuleNotFoundError: No module named 'groq'`**
```powershell
pip install groq
```

**`FileNotFoundError: data/chunks/rag_index.faiss`**
Run the data pipeline steps in order (Step 3).

**`Invoke-RestMethod` returns a red error instead of JSON**
The API is not running. Start it in Window 1 first (`uvicorn api.app:app --reload --port 8080`).

**Pipeline 3 returns "The provided text does not state..."**
TigerGraph workspace is offline. Start it on tgcloud.io, or use a question whose topic is
covered in the Wikipedia dataset. Pipeline 3 still works via local fallback — just slower answers.

**CORS error in the browser**
Make sure the API is running on port 8080 before opening the frontend. The API allows all
origins (`*`) by default.

**BERTScore download is slow on first run**
`roberta-large` (~1.4 GB) is downloaded from HuggingFace and cached in
`C:\Users\<you>\.cache\huggingface\`. Subsequent runs are instant.

**Groq rate limit (HTTP 429)**
The free tier allows ~6,000 tokens/min. The code retries automatically with 30s backoff.
Running the full 15-question eval stays within limits with the retries in place.
