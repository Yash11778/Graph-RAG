"""
Generate a clean architecture diagram for the GraphRAG Pipeline Comparison project.
Output: architecture_diagram.png in the project root.

Run from graphrag-hackathon/:
    python scripts/generate_architecture_diagram.py
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

fig, ax = plt.subplots(figsize=(20, 13))
ax.set_xlim(0, 20)
ax.set_ylim(0, 13)
ax.axis('off')
fig.patch.set_facecolor('#0f172a')

# ── Color palette ──
C = {
    'bg':        '#0f172a',
    'surface':   '#1e293b',
    'surface2':  '#0f172a',
    'border':    '#334155',
    'p1':        '#ef4444',
    'p2':        '#f97316',
    'p3':        '#16a34a',
    'text':      '#f1f5f9',
    'muted':     '#94a3b8',
    'subtle':    '#475569',
    'blue':      '#3b82f6',
    'purple':    '#a855f7',
    'teal':      '#14b8a6',
    'arrow':     '#475569',
}


def box(ax, x, y, w, h, color, alpha=0.15, radius=0.3, border=None, lw=1.5):
    border = border or color
    rect = FancyBboxPatch(
        (x, y), w, h,
        boxstyle=f"round,pad=0,rounding_size={radius}",
        facecolor=color, alpha=alpha,
        edgecolor=border, linewidth=lw,
        zorder=3,
    )
    ax.add_patch(rect)


def label(ax, x, y, text, size=9, color='#f1f5f9', weight='normal', ha='center', va='center', zorder=5):
    ax.text(x, y, text, fontsize=size, color=color, fontweight=weight,
            ha=ha, va=va, zorder=zorder,
            fontfamily='DejaVu Sans')


def arrow(ax, x1, y1, x2, y2, color='#475569', lw=1.5, style='->', head=12):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle=f'->', color=color, lw=lw,
                                mutation_scale=head),
                zorder=4)


# ════════════════════════════════════════════════
# TITLE
# ════════════════════════════════════════════════
label(ax, 10, 12.4, 'GraphRAG Pipeline Comparison — Architecture', size=16, weight='bold', color=C['text'])
label(ax, 10, 12.05, '100,850 Wikipedia Articles  ·  102.9M Tokens  ·  464,739 Indexed Chunks', size=9, color=C['muted'])


# ════════════════════════════════════════════════
# SECTION 1 — DATA LAYER  (top-left)
# ════════════════════════════════════════════════
box(ax, 0.3, 9.5, 4.4, 2.0, C['blue'], alpha=0.08, border=C['blue'], lw=1)
label(ax, 0.9, 11.25, 'DATA LAYER', size=7.5, color=C['blue'], weight='bold', ha='left')

data_items = [
    ('📄  100,850 Wikipedia Articles', 10.9),
    ('✂️   Semantic Chunker  →  464,739 chunks', 10.5),
    ('🔢  fastembed  (MiniLM-L6-v2)  →  vectors', 10.1),
    ('🗂️   FAISS L2 Index  (rag_index.faiss)', 9.7),
]
for txt, yy in data_items:
    label(ax, 0.65, yy, txt, size=8.2, color=C['text'], ha='left')


# ════════════════════════════════════════════════
# SECTION 2 — INGESTION  (top-right)
# ════════════════════════════════════════════════
box(ax, 5.2, 9.5, 5.2, 2.0, C['purple'], alpha=0.08, border=C['purple'], lw=1)
label(ax, 5.6, 11.25, 'INGESTION (one-time)', size=7.5, color=C['purple'], weight='bold', ha='left')

ingest_items = [
    ('🔑  Entity & Relationship Extraction (Gemini)', 10.9),
    ('🏘️   Community Detection  (Louvain algorithm)', 10.5),
    ('📦  DocumentChunk + Community vertices', 10.1),
    ('🐯  TigerGraph Savanna  (tgcloud.io)', 9.7),
]
for txt, yy in ingest_items:
    label(ax, 5.45, yy, txt, size=8.2, color=C['text'], ha='left')

arrow(ax, 4.7, 10.5, 5.2, 10.5, color=C['purple'], lw=1.5)


# ════════════════════════════════════════════════
# SECTION 3 — QUERY  (user input box)
# ════════════════════════════════════════════════
box(ax, 11.0, 10.2, 3.0, 1.0, C['teal'], alpha=0.12, border=C['teal'], lw=1.5)
label(ax, 12.5, 10.85, '🙋  User Question', size=9.5, weight='bold', color=C['teal'])
label(ax, 12.5, 10.45, '"Who invented the telephone?"', size=8, color=C['muted'])

# arrow from user to 3 pipelines
arrow(ax, 12.5, 10.2, 3.0, 8.45, color=C['arrow'], lw=1.2)   # P1
arrow(ax, 12.5, 10.2, 8.5, 8.45, color=C['arrow'], lw=1.2)   # P2
arrow(ax, 12.5, 10.2, 14.5, 8.45, color=C['arrow'], lw=1.2)  # P3


# ════════════════════════════════════════════════
# PIPELINE CARDS  (row)
# ════════════════════════════════════════════════
pipe_cfg = [
    # (x, color, tag, title, lines)
    (0.3, C['p1'], 'P1', 'LLM-Only  (Baseline)', [
        'Question  →  Gemini Flash',
        'No retrieval — pure memory',
        '─────────────────',
        '~103 tokens / query',
        '0.78s avg latency',
        '48% pass rate',
    ]),
    (5.8, C['p2'], 'P2', 'Basic RAG', [
        'Question  →  FAISS top-5',
        '5 chunks  →  Gemini Flash',
        '─────────────────',
        '~1,266 tokens / query',
        '13.4s avg latency',
        '77.3% pass rate',
    ]),
    (11.3, C['p3'], 'P3', 'GraphRAG  ★ Best', [
        'Question  →  FAISS seed (top-1)',
        'TigerGraph Hybrid Retriever',
        '  • DocumentChunk + Community',
        '  • num_hops=2 traversal',
        '  • Graph co-occurrence re-rank',
        '~300 tokens  →  Gemini Flash',
        '─────────────────',
        '~297 tokens / query',
        '5.6s avg latency',
        '81.3% pass rate  ✓',
    ]),
]

for px, pc, tag, title, lines in pipe_cfg:
    h = 4.6 if tag == 'P3' else 4.0
    box(ax, px, 3.8, 5.1, h, pc, alpha=0.10, border=pc, lw=2.0)
    # top accent bar
    bar = FancyBboxPatch((px, 3.8 + h - 0.25), 5.1, 0.25,
                          boxstyle="round,pad=0,rounding_size=0.1",
                          facecolor=pc, alpha=0.6, edgecolor='none', zorder=4)
    ax.add_patch(bar)
    label(ax, px + 0.25, 3.8 + h - 0.125, f'{tag}  {title}', size=9.5, weight='bold', color='white', ha='left')

    for i, line in enumerate(lines):
        yy = 3.8 + h - 0.55 - i * 0.36
        c = C['muted'] if line.startswith('─') else C['text']
        sz = 7.8
        if line.strip().startswith('~') or line.strip().startswith('0.') or 'pass rate' in line or 'latency' in line:
            c = pc
            sz = 8.5
        label(ax, px + 0.25, yy, line, size=sz, color=c, ha='left')


# ════════════════════════════════════════════════
# TIGERGRAPH BOX  (linked from P3)
# ════════════════════════════════════════════════
box(ax, 11.3, 1.6, 5.1, 1.9, C['p3'], alpha=0.08, border=C['p3'], lw=1.5)
label(ax, 13.85, 3.25, '🐯  TigerGraph Savanna', size=9, weight='bold', color=C['p3'])
tg_lines = [
    'POST /graphrag/answerquestion',
    'Hybrid: DocumentChunk + Community',
    'top_k=3  ·  num_hops=2  ·  num_seen_min=1',
]
for i, ln in enumerate(tg_lines):
    label(ax, 11.55, 2.95 - i * 0.38, ln, size=7.8, color=C['text'], ha='left')

arrow(ax, 13.85, 3.8, 13.85, 3.5, color=C['p3'], lw=1.8)


# ════════════════════════════════════════════════
# API LAYER
# ════════════════════════════════════════════════
box(ax, 0.3, 1.0, 10.6, 1.5, C['blue'], alpha=0.08, border=C['blue'], lw=1)
label(ax, 0.65, 2.3, 'FastAPI  (port 8080)  —  POST /compare', size=9, weight='bold', color=C['blue'], ha='left')
api_items = [
    '→  Runs all 3 pipelines in parallel',
    '→  LLM-as-a-Judge (Gemini PASS/FAIL)',
    '→  BERTScore (distilbert-base-uncased)',
    '→  Token reduction %  ·  Cost per query',
]
for i, item in enumerate(api_items):
    label(ax, 0.65, 2.0 - i * 0.3, item, size=7.8, color=C['text'], ha='left')

# arrows from pipelines to API
for px in [2.85, 8.35, 13.85]:
    arrow(ax, px, 3.8, px, 2.5, color=C['arrow'], lw=1.2)


# ════════════════════════════════════════════════
# FRONTEND
# ════════════════════════════════════════════════
box(ax, 11.3, 0.1, 8.4, 1.2, C['teal'], alpha=0.08, border=C['teal'], lw=1)
label(ax, 11.55, 1.05, 'React Dashboard  (port 5173)  —  Vite + Recharts + Lucide', size=8.5, weight='bold', color=C['teal'], ha='left')
fe_items = [
    '• Side-by-side pipeline cards  ·  Token reduction hero',
    '• Bar chart comparison  ·  BERTScore  ·  LLM Judge badges',
    '• Query history  ·  Featured questions  ·  Domain browser',
]
for i, item in enumerate(fe_items):
    label(ax, 11.55, 0.75 - i * 0.27, item, size=7.5, color=C['text'], ha='left')

arrow(ax, 5.6, 1.0, 11.3, 0.7, color=C['teal'], lw=1.5)


# ════════════════════════════════════════════════
# RESULTS CALLOUT
# ════════════════════════════════════════════════
box(ax, 0.3, 0.1, 10.6, 0.85, C['p3'], alpha=0.08, border=C['p3'], lw=1.5)
label(ax, 5.6, 0.7, '📊  GraphRAG vs Basic RAG', size=9, weight='bold', color=C['p3'])
label(ax, 5.6, 0.38, '76.5% fewer tokens   ·   81.3% vs 77.3% pass rate   ·   5.6s vs 13.4s latency', size=8.5, color='#4ade80')


# ════════════════════════════════════════════════
# LEGEND
# ════════════════════════════════════════════════
legend_items = [
    (C['p1'], 'Pipeline 1 — LLM-Only'),
    (C['p2'], 'Pipeline 2 — Basic RAG'),
    (C['p3'], 'Pipeline 3 — GraphRAG'),
    (C['blue'], 'Data / API Layer'),
    (C['teal'], 'Frontend / User'),
    (C['purple'], 'Ingestion'),
]
for i, (lc, lt) in enumerate(legend_items):
    lx = 16.2 + (i % 2) * 1.9
    ly = 12.5 - (i // 2) * 0.4
    ax.add_patch(mpatches.Rectangle((lx - 0.25, ly - 0.1), 0.18, 0.18,
                                     color=lc, alpha=0.8, zorder=5))
    label(ax, lx + 0.05, ly + 0.02, lt, size=7.5, color=C['muted'], ha='left')


plt.tight_layout(pad=0)
out = 'architecture_diagram.png'
plt.savefig(out, dpi=180, bbox_inches='tight',
            facecolor=fig.get_facecolor(), edgecolor='none')
print(f"Saved → {out}")
plt.close()
