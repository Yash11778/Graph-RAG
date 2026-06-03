"""
Build data/graph_snapshot.json — the fallback GraphRAG retrieves from when the live
TigerGraph instance is unreachable (free-tier auto-suspend or exhausted credits).

This STOPGAP builder reconstructs each demo entity's compact `description` facts from the
project's own dataset chunks (the committed demo FAISS index), using the same kind of
LLM fact-extraction that built the TigerGraph graph. The entity set + 1-hop neighbour
edges mirror the live graph (verified entity IDs). Facts are real, drawn from your data.

For maximum fidelity, run scripts/snapshot_graph.py instead once the live instance is
back — it captures the graph's actual output. Both write the same JSON format, and
pipeline3 consumes it identically.

Usage:
    python scripts/build_graph_snapshot.py
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pipelines.pipeline2_rag as p2
from pipelines.utils import gemini_generate, setup_gemini

ROOT     = Path(__file__).parent.parent.resolve()
OUT_PATH = ROOT / "data" / "graph_snapshot.json"

# Entity IDs + 1-hop neighbour edges mirror the live TigerGraph graph (hyphenated IDs,
# verified against the running instance on 2026-06-01). Labels feed both the chunk
# search and the fact-extraction prompt.
GRAPH = {
    "free-software":     ["software"],
    "software":          ["free-software"],
    "napoleon-bonaparte": ["egypt", "aboukir-bay", "france"],
    "egypt":             ["napoleon-bonaparte"],
    "aboukir-bay":       ["napoleon-bonaparte"],
    "roman-empire":      ["augustus"],
    "augustus":          ["roman-empire"],
    "nelson-mandela":    ["south-africa"],
    "south-africa":      ["nelson-mandela"],
    "world-war-ii":      ["axis", "allies", "adolf-hitler", "germany", "japan",
                          "united-states", "france", "manhattan-project"],
    "world-war-i":       [],
    "cold-war":          ["soviet-union", "united-states"],
    "soviet-union":      ["cold-war", "united-states"],
    "united-states":     ["cold-war", "soviet-union", "world-war-ii"],
    "adolf-hitler":      ["world-war-ii", "germany"],
    "winston-churchill": ["world-war-ii", "united-kingdom"],
    "united-kingdom":    ["world-war-ii"],
    "korean-war":        ["north-korea", "south-korea"],
    "north-korea":       ["korean-war"],
    "south-korea":       ["korean-war"],
    "united-nations":    [],
    "nato":              ["united-states", "soviet-union"],
    "germany":           ["world-war-ii", "adolf-hitler"],
    "japan":             ["world-war-ii"],
    "france":            ["napoleon-bonaparte", "world-war-ii"],
    "manhattan-project": ["atomic-bomb", "world-war-ii"],
    "atomic-bomb":       ["manhattan-project"],
    "axis":              ["world-war-ii", "germany", "japan"],
    "allies":            ["world-war-ii", "united-states", "united-kingdom"],
    "vietnam-war":       ["united-states"],
    "penicillin":        [],
}

_UPPER = {'ii', 'iii', 'iv', 'vi', 'vii', 'viii', 'ix', 'xi',
          'us', 'uk', 'ussr', 'nato', 'eu', 'un'}


def label(eid: str) -> str:
    return ' '.join(p.upper() if p in _UPPER else p.capitalize() for p in eid.split('-'))


def top_context(eid: str, k: int = 6) -> str:
    """Pull the k most relevant chunks for this entity from the demo FAISS index."""
    emb = p2._embed(label(eid))
    _, idxs = p2._index.search(emb, k)
    texts = [p2._chunks[i]["text"] for i in idxs[0] if 0 <= i < len(p2._chunks)]
    return "\n\n---\n\n".join(texts)[:6000]


def extract_facts(client, eid: str, context: str) -> list[str]:
    name = label(eid)
    prompt = (
        f"From the context below, write 4 concise, factual statements about {name}.\n"
        "Rules: each statement is one sentence, max 18 words, self-contained, and states "
        f"a concrete fact about {name} (who/what it is, key dates, roles, relationships). "
        "Use ONLY facts present in the context. Output one statement per line, no numbering, "
        "no markdown.\n\n"
        f"Context:\n{context}\n\n"
        f"Facts about {name}:"
    )
    raw = gemini_generate(client, prompt, max_tokens=160)
    facts = []
    for line in raw.splitlines():
        line = line.strip().lstrip("-•*0123456789. ").strip()
        if len(line) > 8:
            facts.append(line)
    return facts[:5]


def main():
    p2._load()
    if p2._load_error:
        raise SystemExit(f"Could not load demo index: {p2._load_error}")
    client = setup_gemini()

    entities = {}
    for i, eid in enumerate(GRAPH, 1):
        ctx   = top_context(eid)
        facts = extract_facts(client, eid, ctx) if ctx else []
        entities[eid] = {"description": facts, "neighbors": GRAPH[eid]}
        print(f"[{i:>2}/{len(GRAPH)}] {eid:<20} {len(facts)} facts", flush=True)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump({"source": "reconstructed_from_chunks", "entities": entities},
                  f, ensure_ascii=False, indent=2)

    total_facts = sum(len(e["description"]) for e in entities.values())
    print(f"\nWrote {OUT_PATH.name}: {len(entities)} entities, {total_facts} facts "
          f"({OUT_PATH.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
