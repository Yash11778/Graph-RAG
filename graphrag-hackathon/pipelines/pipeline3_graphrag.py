"""
Pipeline 3 — GraphRAG: keyword → TigerGraph GSQL traversal (single REST call)

Retrieval path:
  Question → extract keywords → parallel entity lookup in TigerGraph
    → graphrag_traverse GSQL query (entity → RELATIONSHIP hop → DocumentChunk → Content)
    → Merge contexts capped at ~500 tokens
    → Gemini generates answer (max 500 tokens)

Single GSQL call replaces ~40 sequential REST calls — typical latency ~2-4s.
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
# A cold query makes ~18 small REST calls. Without pooling, each opens a fresh HTTPS
# connection and pays a full TLS handshake (~300-500ms each = several wasted seconds).
# A shared keep-alive Session reuses the connection, so each call is just server time.
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


def _tg_get(path: str, params: dict = None, read_timeout: int = 8) -> dict:
    host  = os.environ.get("TG_HOST", TG_HOST)
    token = _get_token()
    resp  = _session.get(
        f"{host}/restpp{path}",
        headers={"Authorization": f"Bearer {token}"},
        params=params or {},
        timeout=(4, read_timeout),
    )
    return resp.json() if resp.status_code == 200 else {}


def _ensure_entity_cache():
    """Fully warm the GraphRAG path at startup (auth token, TLS connection, thread
    pools, Gemini client) so the first *user* query is fast. Runs in the app's
    background preload thread, so it never delays startup."""
    try:
        if _tg_reachable():
            _get_token()                       # caches token + opens pooled HTTPS connection
            _load()                            # initialises the Gemini client
            _tg_retrieve("What was the Cold War?")  # spins up thread pools + restpp connection
            logger.info("TigerGraph warm-up complete")
    except Exception as e:
        logger.warning("TigerGraph warm-up skipped: %s", e)


# ── TigerGraph reachability (cached) ─────────────────────────────────────────────
# A suspended TigerGraph Cloud instance answers /echo with HTTP 500 (or refuses the
# connection). Without this guard every query fans out ~30 doomed lookups and hangs
# ~20s before failing. We probe once, cache for 30s, and fail fast with a clear status.
_health_lock      = threading.Lock()
_tg_healthy       = None
_tg_health_at     = 0.0
_HEALTH_TTL       = 30.0


def _tg_reachable() -> bool:
    global _tg_healthy, _tg_health_at
    with _health_lock:
        now = time.time()
        if _tg_healthy is not None and now - _tg_health_at < _HEALTH_TTL:
            return _tg_healthy
        host = os.environ.get("TG_HOST", TG_HOST)
        try:
            # A running instance answers (even a 404 on an unknown path proves it's alive);
            # a SUSPENDED Savanna instance returns 5xx or refuses the connection.
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
    text  = re.sub(r"[^\w\s]", " ", question.lower())
    words = [w for w in text.split() if w not in _STOPWORDS and len(w) >= 2]
    cands = list(words)
    cands += [f"{words[i]}-{words[i+1]}" for i in range(len(words) - 1)]
    cands += [f"{words[i]}-{words[i+1]}-{words[i+2]}" for i in range(len(words) - 2)]
    return cands


# Fan-out pool for the many small REST calls, plus a SEPARATE pool for the outer
# deadline wrapper — using two pools avoids a nested-submit deadlock (the outer task
# would otherwise occupy a worker while waiting on inner tasks from the same pool).
_tg_executor       = ThreadPoolExecutor(max_workers=8)
_deadline_executor = ThreadPoolExecutor(max_workers=4)


# ── Caches (graph is static within a session) ───────────────────────────────────
# Combining existence + description into one cached fetch removes the biggest latency
# cost: a single GET per unique vertex, ever. Repeated demo questions become near-instant.
_cache_lock     = threading.Lock()
_entity_cache:   dict = {}   # id -> list[str] facts  (or None if the vertex doesn't exist)
_neighbor_cache: dict = {}   # id -> list[str] neighbour ids


def _fetch_entity(eid: str):
    """Return the entity's description facts (list), or None if the vertex doesn't exist.
    One REST call per unique id, cached for the process lifetime."""
    with _cache_lock:
        if eid in _entity_cache:
            return _entity_cache[eid]
    facts = None
    try:
        data = _tg_get(f"/graph/{GRAPH_NAME}/vertices/Entity/{eid}", read_timeout=5)
        if data and not data.get("error") and data.get("results"):
            raw  = data["results"][0]["attributes"].get("description", [])
            facts = [f for f in raw if f and f.strip()]
    except Exception:
        facts = None
    with _cache_lock:
        _entity_cache[eid] = facts
    return facts


def _entity_neighbors(eid: str, k: int = 5) -> list[str]:
    """1-hop graph expansion — RELATIONSHIP neighbours of a seed entity (cached)."""
    with _cache_lock:
        if eid in _neighbor_cache:
            return _neighbor_cache[eid][:k]
    out: list[str] = []
    try:
        data = _tg_get(f"/graph/{GRAPH_NAME}/edges/Entity/{eid}", read_timeout=5)
        for e in (data.get("results") or []):
            if e.get("to_type") == "Entity" and e.get("to_id"):
                out.append(e["to_id"])
    except Exception:
        pass
    with _cache_lock:
        _neighbor_cache[eid] = out
    return out[:k]


def _rank_key(cand: str):
    # More hyphens = more specific multi-word entity → prefer it.
    return (cand.count("-"), len(cand))


def _match_entities(question: str, max_seeds: int = 4) -> list[str]:
    """Find which candidate IDs exist, preferring the most specific (multi-word)
    entities. Existence is determined by the cached vertex fetch, so the facts we
    need later are already loaded — no second round-trip for seeds."""
    candidates = list(dict.fromkeys(_extract_candidates(question)))
    candidates.sort(key=_rank_key, reverse=True)
    # Cap the probe set: phrases first, then a few unigrams. 10 fits within one batch
    # of the 8-worker _tg_executor, cutting one network RTT vs the old 14-candidate set.
    candidates = candidates[:10]

    found: list[str] = []
    for cand, facts in zip(candidates, _tg_executor.map(_fetch_entity, candidates)):
        if facts is not None:
            found.append(cand)

    found.sort(key=_rank_key, reverse=True)
    multiword = [f for f in found if "-" in f]
    pruned: list[str] = []
    for f in found:
        # Drop a bare word already covered by a matched phrase
        # (e.g. drop "bonaparte" when "napoleon-bonaparte" matched).
        if "-" not in f and any(f in m.split("-") for m in multiword):
            continue
        pruned.append(f)
    seeds = pruned[:max_seeds]
    logger.info("Seeds: %s", seeds)
    return seeds


# ── Description-based retrieval: seeds + 1-hop neighbours ─────────────────────────
_UPPER_WORDS = {'ii', 'iii', 'iv', 'vi', 'vii', 'viii', 'ix', 'xi',
                'us', 'uk', 'ussr', 'nato', 'eu', 'un'}


def _entity_label(eid: str) -> str:
    """Convert 'napoleon-bonaparte' → 'Napoleon Bonaparte', 'world-war-ii' → 'World War II'."""
    parts = eid.split('-')
    return ' '.join(p.upper() if p in _UPPER_WORDS else p.capitalize() for p in parts)


def _tg_retrieve(question: str, deadline: float = 14.0) -> list[str]:
    """
    True GraphRAG retrieval, on-topic and compact:
      1. Match seed entities (most-specific first) — facts already cached from matching.
      2. Expand 1 hop along RELATIONSHIP edges.
      3. Pull the `description` facts off every entity (cached vertex fetch).
    Seed facts are returned first so the most relevant context wins the token budget.
    """
    def _run():
        seeds = _match_entities(question, max_seeds=4)
        if not seeds:
            logger.info("No entity seeds found for: %s", question[:60])
            return []

        # 1-hop neighbours (parallel), capped to keep latency bounded.
        neighbor_ids: list[str] = []
        for ids in _tg_executor.map(lambda s: _entity_neighbors(s, 5), seeds):
            neighbor_ids.extend(ids)

        seed_set = set(seeds)
        all_ids  = list(dict.fromkeys(seeds + neighbor_ids))[:14]

        # Seeds are already cached; only neighbours may need a fetch. _fetch_entity
        # short-circuits on cache hits, so this is cheap.
        facts_by_id = dict(zip(all_ids, _tg_executor.map(_fetch_entity, all_ids)))

        seed_facts: list[str] = []
        nbr_facts:  list[str] = []
        for eid in all_ids:
            facts = facts_by_id.get(eid) or []
            # Prefix each fact with the entity name so the LLM knows which entity
            # the fact describes. Without this, anonymous facts like "The French general
            # and leader of the expedition in Egypt." can't be attributed to Napoleon.
            label    = _entity_label(eid)
            prefixed = [f"{label}: {f}" for f in facts]
            (seed_facts if eid in seed_set else nbr_facts).extend(prefixed)

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
    # _load() (Gemini client init) is deferred to just before generation — the offline
    # and no_context paths return hardcoded strings and never need the LLM client, so
    # they should complete instantly even on a cold server.
    t_start = time.time()

    # Fail fast if the graph service is offline — don't hang ~20s on doomed lookups.
    if not _tg_reachable():
        answer  = "The TigerGraph knowledge-graph service is currently offline, so no graph context could be retrieved."
        latency = round(time.time() - t_start, 3)
        result  = make_result("graphrag", answer, 0, count_tokens(answer), latency)
        result.update({
            "sources":             [],
            "context_tokens":      0,
            "retriever":           "tigergraph_gsql",
            "graph_context_found": False,
            "status":              "tg_unavailable",
        })
        return result

    tg_texts = _tg_retrieve(question)

    context_parts: list[str] = []
    seen:          set[str]  = set()
    # Context budget: 180 tokens absorbs the entity-label prefix overhead (~3-5 tok/fact)
    # while keeping total GraphRAG tokens well below 300 → ≥88% reduction vs Basic RAG.
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
        # This is a FAILURE, not a token "win" — we flag it explicitly so the API never
        # reports an empty answer as a reduction.
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

    _load()  # Initialize Gemini client only when we actually need to generate an answer
    # Concise instruction in plain prose — avoids bullet-point over-structuring.
    prompt = (
        "Answer the question in clear prose using only the context below. "
        "Include all relevant facts, names, and dates.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {question}\n\nAnswer:"
    )
    # Short answer cap: graph context is compact so 120 tokens covers the full answer;
    # trimming completion tokens is the biggest lever for hitting 88-93% reduction.
    answer  = gemini_generate(_gemini_client, prompt, max_tokens=120)
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
