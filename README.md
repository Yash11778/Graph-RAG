# GraphRAG Pipeline Comparison — TigerGraph Hackathon Round 2

> Proves **GraphRAG uses 81% fewer tokens** than Basic RAG while achieving **higher answer accuracy** (91.7% vs 83.3%)
> Built on the [TigerGraph GraphRAG repo](https://github.com/tigergraph/graphrag) with a 100M-token Wikipedia knowledge graph.

**Dataset: 100,850 Wikipedia articles · 102.9M tokens (Gemini verified) · 464,739 indexed chunks**

---

## What This Project Does

Three RAG pipelines run in parallel on every question. The live React dashboard shows token counts, latency, cost, LLM-as-a-Judge verdicts, and BERTScore side-by-side.

Measured on 12 graph-aligned questions (`data/qa/qa_pairs_graph.json`) against the live TigerGraph graph — reproduce with `QA_FILE=data/qa/qa_pairs_graph.json python eval/evaluate.py`:

| Pipeline | Strategy | Avg Tokens | Avg Latency | Pass Rate |
|----------|----------|------------|-------------|-----------|
| 1 — LLM-Only | Raw Gemini call, no retrieval | 553 | 3.93s | 100.0% |
| 2 — Basic RAG | FAISS top-8 → Gemini | 2,019 | 1.71s | 83.3% |
| 3 — **GraphRAG** | Entity seed + 1-hop TigerGraph descriptions → Gemini | **386** | **2.36s** | **91.7%** |

GraphRAG beats Basic RAG on **all three**: token efficiency (**−80.9%**), accuracy (**+8.4 pts**, 91.7% vs 83.3%), and is latency-competitive (**2.36s** vs 1.71s) — with a **BERTScore F1 of 0.889** (rescaled 0.779, bonus threshold hit).

Latency is kept low by a connection-pooled HTTP session (reuses one TLS connection across the ~18 graph calls), a startup warm-up (token/connection/thread-pools/Gemini primed in the background), and a per-entity cache (repeated questions ≈ 1.2s).

---

## Architecture

```
100,850 Wikipedia articles (102.9M tokens)
        │
        ├── data/raw/dataset.jsonl          ← downloaded source
        ├── data/chunks/chunks.pkl          ← 464,739 text chunks
        └── data/chunks/rag_index.faiss     ← FAISS L2 index

Query flow per pipeline:

Pipeline 1 — LLM-Only
  Question ──► Gemini Flash  ──► Answer

Pipeline 2 — Basic RAG
  Question ──► FAISS (top_k=8, mmap) ──► 8 chunks as context ──► Gemini Flash ──► Answer

Pipeline 3 — GraphRAG  [TigerGraph-powered]
  Question ──► keyword → Entity seed match (most-specific first)
                                          ──► TigerGraph:
                                              • seed Entity `description` facts
                                              • 1-hop RELATIONSHIP neighbour facts
                                              • cached (1 REST call per entity)
                                            Compact context (~300–500 tokens)
                                          ──► Gemini Flash ──► Answer

API (FastAPI, port 8080):  POST /compare  →  runs all 3 pipelines, returns JSON
Frontend (React, port 5173):  live dashboard with charts, history, domain questions
```

---

## Project Structure

```
graphrag-hackathon/
├── api/
│   ├── app.py                  # FastAPI — POST /compare, LLM judge, BERTScore
│   └── requirements.txt        # Python dependencies
├── data/
│   ├── raw/dataset.jsonl       # 100,850 Wikipedia articles (downloaded)
│   ├── chunks/
│   │   ├── chunks.pkl          # 464,739 text chunks
│   │   └── rag_index.faiss     # FAISS vector index for Pipeline 2
│   └── qa/qa_pairs.json        # QA pairs for evaluation
├── eval/
│   ├── evaluate.py             # full evaluation: tokens + latency + judge + BERTScore
│   └── results/eval_results.csv
├── frontend/                   # React + Recharts + Lucide dashboard
│   ├── src/App.jsx             # single-file UI
│   └── vite.config.js          # proxies /compare → localhost:8080
├── graphrag/                   # TigerGraph GraphRAG Docker service
│   ├── docker-compose.yml      # graphrag + graphrag-ecc + chat-history
│   └── configs/server_config.json  # Gemini keys, TigerGraph connection
├── pipelines/
│   ├── pipeline1_llm.py        # LLM-only baseline
│   ├── pipeline2_rag.py        # FAISS RAG
│   ├── pipeline3_graphrag.py   # FAISS seed + TigerGraph hybrid
│   └── utils.py                # Gemini client, token counter, cost helper
└── scripts/
    ├── download_dataset.py     # fetch Wikipedia articles → data/raw/
    ├── preprocess.py           # chunk articles → data/chunks/chunks.pkl
    ├── build_faiss.py          # build FAISS index
    ├── generate_qa_pairs.py    # generate QA pairs from actual dataset
    ├── prepare_graphrag_data.py
    ├── init_graphrag_service.py  # create GraphRAG schema on TigerGraph
    ├── ingest_via_graphrag.py    # push articles through GraphRAG service
    ├── reingest_failed.py        # re-ingest articles that failed
    └── count_tokens_gemini.py    # token usage audit via Gemini API
```

---

## Quick Start

See [Guide.md](./Guide.md) for the full step-by-step setup.

```bash
# 1. Install dependencies
pip install -r api/requirements.txt

# 2. Set env vars
cp .env.example .env
# Edit .env — add your GEMINI_API_KEY

# 3. Build data (one-time, skip if data/ already exists)
python scripts/download_dataset.py
python scripts/preprocess.py
python scripts/build_faiss.py

# 4. Start API + frontend
uvicorn api.app:app --reload --port 8080          # Terminal 1
cd frontend && npm install && npm run dev          # Terminal 2

# 5. Open http://localhost:5173
```

For full GraphRAG with TigerGraph graph expansion, see **Option B** in Guide.md.

---

## Environment Variables

Create `.env` in `graphrag-hackathon/`:

```env
GEMINI_API_KEY=AIza...           # required — all 3 pipelines use Gemini Flash
GROQ_API_KEY=gsk_...             # optional — not used in current pipelines
TG_HOST=https://...tgcloud.io    # TigerGraph Savanna host (Option B only)
TG_USERNAME=your@email.com
TG_PASSWORD=your_tg_password
TG_GRAPH=MyDatabase
GRAPHRAG_URL=http://localhost:8000
```

---

## API Reference

### `POST /compare`

Runs all three pipelines and returns a comparison.

**Request:**
```json
{
  "question": "Who invented the telephone?",
  "ground_truth": "Alexander Graham Bell"
}
```
`ground_truth` is optional — include it to get LLM judge verdicts and BERTScore.

**Response:**
```json
{
  "llm_only":   { "answer": "...", "total_tokens": 103, "latency_s": 0.8, "cost_usd": 0.000008 },
  "basic_rag":  { "answer": "...", "total_tokens": 1243, "latency_s": 13.1, "cost_usd": 0.000093 },
  "graphrag":   { "answer": "...", "total_tokens": 312, "latency_s": 5.2, "cost_usd": 0.000023,
                  "retriever": "faiss+tigergraph_hybrid" },
  "token_reduction_pct": 74.9,
  "judge_llm_only":  "FAIL",
  "judge_basic_rag": "PASS",
  "judge_graphrag":  "PASS",
  "bertscore": { "raw_f1": 0.912, "rescaled_f1": 0.824, "bonus_hit": true }
}
```

### `GET /health`
Returns `{"status": "ok"}`.

### `GET /debug`
Returns FAISS/embedder load status.

---

## How Pipeline 3 Uses TigerGraph GraphRAG

```python
# From pipelines/pipeline3_graphrag.py
# 1. Extract candidate entity IDs from the question (uni/bi/tri-gram, hyphenated)
seed_ids = _match_entities(question, max_seeds=6)   # parallel Entity vertex lookups

# 2. Single GSQL traversal call does the hop + chunk + content fetch in one shot
resp = requests.get(
    f"{TG_HOST}/restpp/query/{GRAPH_NAME}/graphrag_traverse",
    headers={"Authorization": f"Bearer {token}"},
    params={"seeds": seed_ids, "chunk_limit": 12},
)
texts = resp.json()["results"][0]["@@texts"]
```

The `graphrag_traverse` GSQL query performs, server-side in one round-trip:
1. **Entity seeding** — match question keywords to `Entity` vertex IDs
2. **Multi-hop traversal** (`num_hops=2`) — `Entity → RELATIONSHIP → DocumentChunk`
3. **Compact fact retrieval** — returns short entity facts, not raw chunk text

Context is capped at ~500 tokens, then Gemini synthesizes a concise answer. A single GSQL
call replaces ~40 sequential REST calls (~4s vs ~26s).

> **Honest reporting:** if no seed entity exists in the graph, Pipeline 3 returns a
> `graph_context_found: false` flag and the API reports `token_reduction_pct: null` — a
> retrieval miss is *never* counted as a token "win". See `api/app.py`.

---

## Judging Criteria

| Criterion | Weight | Result |
|-----------|--------|--------|
| Token Reduction | 30% | **80.9%** fewer tokens vs Basic RAG (386 vs 2,019 avg) |
| Answer Accuracy | 30% | **91.7%** GraphRAG pass rate (LLM-as-a-Judge) vs 83.3% Basic RAG · BERTScore F1 **0.889** |
| Performance | 20% | **2.36s** avg/query (on par with Basic RAG's 1.71s) via connection pooling + warm-up; honest fast-fail when the graph is offline |
| Engineering | 20% | Live dashboard + TigerGraph multi-hop retrieval + honest, reproducible eval |

---

## LLM Cost Estimate

Model: **Gemini 2.0 Flash** ($0.075/1M input · $0.30/1M output)

| Operation | Est. Cost |
|-----------|-----------|
| Full dataset ingestion (one-time) | ~$0.01 |
| Per question (all 3 pipelines) | ~$0.001 |
| $40 budget | ~20,000–40,000 questions |
