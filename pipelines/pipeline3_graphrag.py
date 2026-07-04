"""
Pipeline 3 — GraphRAG: keyword -> TigerGraph GSQL traversal (single REST call)

Retrieval path:
  Question -> extract keyword/phrase candidates -> installed `graphrag_retrieve` GSQL query
    -> matches Entity.name (case-insensitive) -> 1-hop ENTITY_COREF expansion
    -> Merge (name, fact) pairs capped at ~180 tokens
    -> Gemini generates answer

Schema this queries against (see scripts/add_entity_schema.py):
  Article --HAS_CHUNK--> Chunk --HAS_ENTITY--> Entity(id, name, fact, chunk_id)
                                                  Entity <--ENTITY_COREF--> Entity

No offline snapshot fallback: if the live graph has nothing for a question, that is
reported honestly as a miss (status="no_context") rather than silently substituted
with pre-baked data. A previous version of this file queried a nonexistent
`description` attribute and `RELATIONSHIP` edge type, and guessed primary IDs from
slugified keywords instead of the real `{chunk_id}_e{idx}` IDs -- it could never
return real data and was masked by a fabricated `data/graph_snapshot.json` fallback.
That fallback and the QA set curated to match it (`qa_pairs_graph.json`) have been
removed; benchmark against the real `data/qa/qa_pairs.json` only.
"""
import os
import re
import time
import logging
import threading
from concurrent.futures import ThreadPoolExecutor

import requests
from requests.adapters import HTTPAdapter

from pipelines.utils import count_tokens, gemini_generate, make_result, setup_gemini

logger = logging.getLogger(__name__)

TG_HOST    = os.environ.get("TG_HOST", "")
TG_SECRET  = os.environ.get("TG_PASSWORD", "")
GRAPH_NAME = os.environ.get("TG_GRAPH", "MyDatabase")

# ── Connection-pooled HTTP session ───────────────────────────────────────────────
_session = requests.Session()
_adapter = HTTPAdapter(pool_connections=4, pool_maxsize=16, max_retries=0)
_session.mount("https://", _adapter)
_session.mount("http://", _adapter)

# ── Token cache ────────────────────────────────────────────────────────────────
_token_lock   = threading.Lock()
_cached_token = None
_token_expiry = 0.0


def _get_token() -> str:
    global _cached_token, _token_expiry
    with _token_lock:
        if _cached_token and time.time() < _token_expiry - 60:
            return _cached_token
        host   = os.environ.get("TG_HOST", TG_HOST)
        secret = os.environ.get("TG_PASSWORD", TG_SECRET)
        resp   = _session.post(
            f"{host}/gsql/v1/tokens",
            json={"secret": secret, "graph": GRAPH_NAME},
            timeout=10,
        )
        resp.raise_for_status()
        _cached_token = resp.json()["token"]
        _token_expiry = time.time() + 6 * 24 * 3600
        return _cached_token


def _ensure_entity_cache():
    """Warm the GraphRAG path at startup (auth token, TLS connection, Gemini client)
    so the first *user* query is fast. Runs in the app's background preload thread."""
    try:
        if _tg_reachable():
            _get_token()
            _load()
            _tg_retrieve("What was the Cold War?")
            logger.info("TigerGraph warm-up complete")
    except Exception as e:
        logger.warning("TigerGraph warm-up skipped: %s", e)


# ── TigerGraph reachability (cached) ─────────────────────────────────────────────
_health_lock  = threading.Lock()
_tg_healthy   = None
_tg_health_at = 0.0
_HEALTH_TTL   = 30.0


def _tg_reachable() -> bool:
    global _tg_healthy, _tg_health_at
    with _health_lock:
        now = time.time()
        if _tg_healthy is not None and now - _tg_health_at < _HEALTH_TTL:
            return _tg_healthy
        host = os.environ.get("TG_HOST", TG_HOST)
        try:
            resp = _session.get(f"{host}/api/ping", timeout=(3, 4))
            _tg_healthy = resp.status_code < 500
        except Exception:
            _tg_healthy = False
        _tg_health_at = now
        return _tg_healthy


# ── Keyword extraction ─────────────────────────────────────────────────────────
_STOPWORDS = {
    "what", "who", "how", "why", "when", "where", "which", "were", "was",
    "did", "does", "the", "and", "for", "are", "his", "her", "its", "our",
    "their", "that", "this", "with", "from", "into", "have", "has", "had",
    "been", "they", "them", "than", "about", "during", "between", "major",
    "main", "key", "most", "some", "any", "all", "also", "make", "made",
    "give", "gave", "role", "part", "led", "lead", "played", "known", "called",
    "contribute", "contributed", "develop", "developed", "describe", "caused",
}


def _extract_candidates(question: str) -> list[str]:
    """Candidate entity-name phrases (unigrams, bigrams, trigrams) to match against
    Entity.name in the live graph. Matching is case-insensitive on the graph side
    (see graphrag_retrieve's lower(e.name) comparison), so no case handling needed here."""
    text  = re.sub(r"[^\w\s]", " ", question.lower())
    words = [w for w in text.split() if w not in _STOPWORDS and len(w) >= 2]
    cands = list(words)
    cands += [f"{words[i]} {words[i+1]}" for i in range(len(words) - 1)]
    cands += [f"{words[i]} {words[i+1]} {words[i+2]}" for i in range(len(words) - 2)]
    return cands


# Fan-out pool for the deadline wrapper.
_deadline_executor = ThreadPoolExecutor(max_workers=4)


def _tg_query_retrieve(candidates: list[str], max_seeds: int = 4, max_neighbors: int = 5) -> list[dict]:
    """Single REST call to the installed graphrag_retrieve GSQL query. Returns a list of
    {id, name, fact, chunk_id, is_seed} dicts, or [] on any failure/miss."""
    host  = os.environ.get("TG_HOST", TG_HOST)
    token = _get_token()
    resp = _session.get(
        f"{host}/restpp/query/{GRAPH_NAME}/graphrag_retrieve",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "candidateNames": candidates,
            "maxSeeds":       max_seeds,
            "maxNeighbors":   max_neighbors,
        },
        timeout=(4, 10),
    )
    if resp.status_code != 200:
        logger.warning("graphrag_retrieve HTTP %s: %s", resp.status_code, resp.text[:300])
        return []
    data = resp.json()
    results = (data.get("results") or [{}])[0].get("Result", [])
    out = []
    for r in results:
        attrs = r.get("attributes", r)
        out.append({
            "id":       r.get("v_id") or attrs.get("id"),
            "name":     attrs.get("name", ""),
            "fact":     attrs.get("fact", ""),
            "chunk_id": attrs.get("chunk_id", ""),
            "is_seed":  bool(attrs.get("is_seed")),
        })
    return out


def _tg_retrieve(question: str, deadline: float = 14.0) -> list[str]:
    """True GraphRAG retrieval against the real schema:
      1. Extract keyword/phrase candidates from the question.
      2. Single GSQL call: match Entity.name (case-insensitive) -> seeds,
         expand 1 hop along ENTITY_COREF -> same real-world entity in other chunks/docs.
      3. Format each match as "<name>: <fact>", seeds first so they win the token budget.
    """
    def _run():
        candidates = list(dict.fromkeys(_extract_candidates(question)))
        if not candidates:
            return []
        entities = _tg_query_retrieve(candidates)
        if not entities:
            logger.info("No entity matches for: %s", question[:60])
            return []

        seed_facts, nbr_facts = [], []
        for e in entities:
            if not e["fact"]:
                continue
            text = f"{e['name']}: {e['fact']}"
            (seed_facts if e["is_seed"] else nbr_facts).append(text)

        logger.info("Retrieved %d seed facts + %d neighbour facts",
                    len(seed_facts), len(nbr_facts))
        return seed_facts + nbr_facts

    future = _deadline_executor.submit(_run)
    try:
        return future.result(timeout=deadline)
    except TimeoutError:
        logger.warning("TG retrieval timed out (%.1fs)", deadline)
        return []
    except Exception as e:
        logger.warning("TG retrieval error: %s", e)
        return []


# ── Module-level state ─────────────────────────────────────────────────────────
_gemini_client = None


def _load():
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = setup_gemini()


def _truncate_to_tokens(text: str, max_tok: int) -> str:
    if count_tokens(text) <= max_tok:
        return text
    words  = text.split()
    lo, hi = 0, len(words)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if count_tokens(" ".join(words[:mid])) <= max_tok:
            lo = mid
        else:
            hi = mid - 1
    return " ".join(words[:lo])


def pipeline3(question: str) -> dict:
    t_start = time.time()

    tg_texts = _tg_retrieve(question) if _tg_reachable() else []

    context_parts: list[str] = []
    seen:          set[str]  = set()
    token_budget              = 180

    for text in tg_texts:
        chunk = _truncate_to_tokens(text, 50)
        if chunk in seen:
            continue
        tok = count_tokens(chunk)
        if tok <= token_budget:
            context_parts.append(chunk)
            seen.add(chunk)
            token_budget -= tok
        if token_budget <= 0:
            break

    context = "\n".join(context_parts) if context_parts else ""

    if not context:
        # Retrieval genuinely found nothing in the knowledge graph for this question.
        # This is a FAILURE, not a token "win" -- flagged explicitly so it is never
        # reported as a reduction.
        answer  = "No relevant graph context found for this question."
        latency = round(time.time() - t_start, 3)
        result  = make_result("graphrag", answer, 0, count_tokens(answer), latency)
        result.update({
            "sources":             [],
            "context_tokens":      0,
            "retriever":           "tigergraph_gsql",
            "graph_context_found": False,
            "status":              "no_context",
        })
        return result

    _load()
    # Same instruction shape as pipeline1/pipeline2 -- only the context source differs,
    # so token-reduction comparisons reflect retrieval, not prompt-engineering tricks.
    prompt = (
        "Answer the question in clear prose using only the context below. "
        "Include all relevant facts, names, and dates.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {question}\n\nAnswer:"
    )
    # Same completion cap as pipeline1/pipeline2 (300) -- previously capped at 120,
    # which manufactured part of the reported token reduction rather than earning it
    # through better retrieval.
    answer  = gemini_generate(_gemini_client, prompt, max_tokens=300)
    latency = round(time.time() - t_start, 3)

    result = make_result("graphrag", answer, count_tokens(prompt), count_tokens(answer), latency)
    result.update({
        "sources":             list(seen)[:5],
        "context_tokens":      count_tokens(context),
        "retriever":           "tigergraph_gsql",
        "graph_context_found": True,
        "status":              "ok",
    })
    return result
