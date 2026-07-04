---
title: GraphRAG API
emoji: 🧠
colorFrom: green
colorTo: blue
sdk: docker
app_port: 8080
pinned: false
---

# GraphRAG Pipeline Comparison — TigerGraph Hackathon Round 2

> GraphRAG entity retrieval was rewritten to match the actual TigerGraph schema and query
> the live graph directly (see `scripts/graphrag_queries.gsql`); the numbers below are
> **pending a fresh benchmark run** against the corrected pipeline. The previous numbers
> quoted here (91.7% / 80.9% / 0.889 BERTScore) came from a broken retrieval path that
> silently fell back to a hand-built 31-entity snapshot instead of the live graph, and an
> API judge with auto-pass logic — neither reflected a genuine run. Run
> `python eval/evaluate.py` against `data/qa/qa_pairs.json` (the real 75-question set) and
> replace this table with the actual output.

**Dataset: 63,632 U.S. court opinions (legal case law) · 117.5M tokens (Gemini `count_tokens` verified) · 9,632 real citation edges**

> NOTE: this README predates the pivot from a Wikipedia corpus to a legal case-law corpus
> and still describes the old pipeline in places below (chunk counts, example questions,
> etc.) — treat the dataset stat line above and the Data Source & Licensing section as
> current; the rest is pending a full rewrite.

## Data Source & Licensing

- **Source**: U.S. court opinions (state and federal), sourced via the [Pile of Law](https://huggingface.co/datasets/pile-of-law/pile-of-law) dataset's `courtlistener_opinions` split, which itself aggregates public [CourtListener](https://www.courtlistener.com/) data.
- **Underlying content is public domain**: judicial opinions authored by judges in their official capacity are not copyrightable in the United States (government edict doctrine, confirmed for state courts by *Georgia v. Public.Resource.Org*, 2020). The case-law text itself carries no copyright restriction.
- **Pile of Law's specific compiled/curated dataset artifact** is licensed `CC-BY-NC-SA-4.0` (non-commercial, share-alike) — this applies to their packaging/selection of the data, not the underlying public-domain opinion text. This hackathon submission is non-commercial (research/competition use), consistent with that license.
- Court/case metadata (case name, court, year) was extracted from each opinion's own citation header using [eyecite](https://github.com/freelawproject/eyecite) (Free Law Project's own citation-parsing library — the same organization behind CourtListener), plus [courts-db](https://github.com/freelawproject/courts-db) for reporter/court resolution.
- Citation graph edges were built from CourtListener's public `citation-map` bulk data (no auth required), filtered to edges where both the citing and cited opinion are present in this corpus.

---

## What This Project Does

Three RAG pipelines run in parallel on every question. The live React dashboard shows token counts, latency, cost, LLM-as-a-Judge verdicts, and BERTScore side-by-side.

Benchmark against the full 75-question set (`data/qa/qa_pairs.json`) against the live TigerGraph graph — reproduce with `python eval/evaluate.py`. (Table pending re-run — see note above.)

| Pipeline | Strategy | Avg Tokens | Avg Latency | Pass Rate |
|----------|----------|------------|-------------|-----------|
| 1 — LLM-Only | Raw Gemini call, no retrieval | TBD | TBD | TBD |
| 2 — Basic RAG | FAISS top-8 → Gemini | TBD | TBD | TBD |
| 3 — **GraphRAG** | Entity seed + 1-hop TigerGraph ENTITY_COREF → Gemini | TBD | TBD | TBD |

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
  Question ──► keyword/phrase candidates
                                          ──► TigerGraph (single GSQL call, graphrag_retrieve):
                                              • Entity.name match (case-insensitive) → seeds
                                              • 1-hop ENTITY_COREF neighbour expansion
                                              • returns each entity's `fact` attribute
                                            Compact context (~180 tokens)
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

Schema (built by `scripts/add_entity_schema.py` + `scripts/extract_entities.py`):

```
Article --HAS_CHUNK--> Chunk --HAS_ENTITY--> Entity(id, name, fact, chunk_id)
                                                Entity <--ENTITY_COREF--> Entity
```

```python
# From pipelines/pipeline3_graphrag.py
# 1. Extract candidate name/phrase strings from the question (uni/bi/tri-gram)
candidates = _extract_candidates(question)

# 2. Single GSQL call: match Entity.name (case-insensitive) -> seeds,
#    then 1-hop ENTITY_COREF expansion -> same real-world entity in other chunks/docs
resp = requests.get(
    f"{TG_HOST}/restpp/query/{GRAPH_NAME}/graphrag_retrieve",
    headers={"Authorization": f"Bearer {token}"},
    params={"candidateNames": candidates, "maxSeeds": 4, "maxNeighbors": 5},
)
entities = resp.json()["results"][0]["Result"]   # [{name, fact, chunk_id, is_seed}, ...]
```

The `graphrag_retrieve` query (`scripts/graphrag_queries.gsql`, installed via
`scripts/install_graphrag_query.py`) performs, server-side in one round-trip:
1. **Entity seeding** — match candidate strings against `Entity.name` (case-insensitive)
2. **1-hop traversal** — `Entity -(ENTITY_COREF)- Entity`, the same real-world entity
   mentioned in other chunks/documents
3. **Compact fact retrieval** — returns each matched entity's `fact` attribute, not raw
   chunk text

Context is capped at ~180 tokens, then Gemini synthesizes a concise answer using the same
300-token completion cap as Pipelines 1 and 2. Verify retrieval against the live graph
with `python scripts/verify_graphrag_retrieval.py --qa-sample 10`.

> **Honest reporting:** if no seed entity exists in the graph, Pipeline 3 returns a
> `graph_context_found: false` flag and the API reports `token_reduction_pct: null` — a
> retrieval miss is *never* counted as a token "win". See `api/app.py`.

---

## Judging Criteria

| Criterion | Weight | Result |
|-----------|--------|--------|
| Token Reduction | 30% | Pending re-run of `eval/evaluate.py` against the corrected pipeline (see note at top) |
| Answer Accuracy | 30% | Pending re-run — judged with the single strict LLM-judge in `eval/evaluate.py` / `api/app.py`, no auto-pass |
| Performance | 20% | Pending re-run — connection pooling + warm-up retained; honest fast-fail when the graph is offline |
| Engineering | 20% | Live dashboard + TigerGraph retrieval against the real schema (`Entity.name/fact`, `ENTITY_COREF`) + honest, reproducible eval |

---

## LLM Cost Estimate

Model: **Gemini 2.0 Flash** ($0.075/1M input · $0.30/1M output)

| Operation | Est. Cost |
|-----------|-----------|
| Full dataset ingestion (one-time) | ~$0.01 |
| Per question (all 3 pipelines) | ~$0.001 |
| $40 budget | ~20,000–40,000 questions |
