import { useState } from "react";

const API = "";

const PIPELINE_LABELS = {
  pipeline1_llm: "Pipeline 1 — LLM Only",
  pipeline2_rag: "Pipeline 2 — Basic RAG",
  pipeline3_graphrag: "Pipeline 3 — GraphRAG",
};

const PIPELINE_COLORS = {
  pipeline1_llm: "#6366f1",
  pipeline2_rag: "#f59e0b",
  pipeline3_graphrag: "#10b981",
};

function StatBadge({ label, value, highlight }) {
  return (
    <div style={{
      background: highlight ? "#064e3b" : "#1e293b",
      border: `1px solid ${highlight ? "#10b981" : "#334155"}`,
      borderRadius: 8,
      padding: "8px 14px",
      display: "inline-block",
      marginRight: 8,
      marginBottom: 8,
    }}>
      <div style={{ fontSize: 11, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.05em" }}>{label}</div>
      <div style={{ fontSize: 18, fontWeight: 700, color: highlight ? "#34d399" : "#f1f5f9" }}>{value}</div>
    </div>
  );
}

function PipelineCard({ pipelineKey, data }) {
  const color = PIPELINE_COLORS[pipelineKey];
  const label = PIPELINE_LABELS[pipelineKey];
  const isGraphRAG = pipelineKey === "pipeline3_graphrag";

  return (
    <div style={{
      background: "#1e293b",
      border: `1px solid ${color}`,
      borderRadius: 12,
      padding: 20,
      flex: 1,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
        <div style={{ width: 10, height: 10, borderRadius: "50%", background: color }} />
        <span style={{ fontWeight: 600, fontSize: 14 }}>{label}</span>
      </div>

      <div style={{ marginBottom: 16 }}>
        <StatBadge label="Total tokens" value={data.total_tokens.toLocaleString()} highlight={isGraphRAG} />
        <StatBadge label="Prompt tokens" value={data.prompt_tokens.toLocaleString()} />
        <StatBadge label="Latency" value={`${data.latency_s}s`} />
        <StatBadge label="Cost" value={`$${data.cost_usd.toFixed(6)}`} />
      </div>

      <div style={{
        background: "#0f172a",
        borderRadius: 8,
        padding: 14,
        fontSize: 14,
        lineHeight: 1.6,
        color: "#cbd5e1",
        maxHeight: 200,
        overflowY: "auto",
      }}>
        {data.answer}
      </div>
    </div>
  );
}

function TokenBar({ p2Tokens, p3Tokens }) {
  const reduction = p2Tokens > 0 ? ((1 - p3Tokens / p2Tokens) * 100).toFixed(1) : 0;
  const p3Width = p2Tokens > 0 ? (p3Tokens / p2Tokens) * 100 : 100;

  return (
    <div style={{ background: "#1e293b", borderRadius: 12, padding: 20, marginBottom: 24 }}>
      <div style={{ fontWeight: 600, marginBottom: 12, fontSize: 14 }}>
        Token Reduction: GraphRAG vs Basic RAG
        <span style={{
          marginLeft: 12,
          color: "#34d399",
          fontSize: 22,
          fontWeight: 800,
        }}>
          -{reduction}%
        </span>
      </div>
      <div style={{ marginBottom: 8 }}>
        <div style={{ fontSize: 12, color: "#94a3b8", marginBottom: 4 }}>
          Basic RAG — {p2Tokens.toLocaleString()} tokens
        </div>
        <div style={{ height: 20, background: "#f59e0b", borderRadius: 4 }} />
      </div>
      <div>
        <div style={{ fontSize: 12, color: "#94a3b8", marginBottom: 4 }}>
          GraphRAG — {p3Tokens.toLocaleString()} tokens
        </div>
        <div style={{ height: 20, background: "#10b981", borderRadius: 4, width: `${p3Width}%` }} />
      </div>
    </div>
  );
}

export default function App() {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!question.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const resp = await fetch(`${API}/compare`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.detail || resp.statusText);
      }
      setResult(await resp.json());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <div style={{ marginBottom: 32 }}>
        <h1 style={{ fontSize: 28, fontWeight: 800, color: "#f1f5f9", marginBottom: 6 }}>
          GraphRAG vs RAG
        </h1>
        <p style={{ color: "#64748b", fontSize: 14 }}>
          Compare token usage across three inference pipelines.
          GraphRAG targets 60–80% fewer tokens than Basic RAG.
        </p>
      </div>

      <form onSubmit={handleSubmit} style={{ marginBottom: 32 }}>
        <div style={{ display: "flex", gap: 12 }}>
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask a question…"
            style={{
              flex: 1,
              background: "#1e293b",
              border: "1px solid #334155",
              borderRadius: 8,
              padding: "12px 16px",
              fontSize: 15,
              color: "#f1f5f9",
              outline: "none",
            }}
          />
          <button
            type="submit"
            disabled={loading || !question.trim()}
            style={{
              background: loading ? "#374151" : "#6366f1",
              color: "#fff",
              border: "none",
              borderRadius: 8,
              padding: "12px 28px",
              fontSize: 15,
              fontWeight: 600,
              cursor: loading ? "not-allowed" : "pointer",
            }}
          >
            {loading ? "Running…" : "Compare"}
          </button>
        </div>
      </form>

      {error && (
        <div style={{
          background: "#450a0a",
          border: "1px solid #b91c1c",
          borderRadius: 8,
          padding: 16,
          marginBottom: 24,
          color: "#fca5a5",
        }}>
          {error}
        </div>
      )}

      {result && (
        <>
          <TokenBar
            p2Tokens={result.pipeline2_rag.total_tokens}
            p3Tokens={result.pipeline3_graphrag.total_tokens}
          />
          <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
            <PipelineCard pipelineKey="pipeline1_llm" data={result.pipeline1_llm} />
            <PipelineCard pipelineKey="pipeline2_rag" data={result.pipeline2_rag} />
            <PipelineCard pipelineKey="pipeline3_graphrag" data={result.pipeline3_graphrag} />
          </div>
        </>
      )}

      {!result && !loading && (
        <div style={{ textAlign: "center", color: "#475569", marginTop: 80, fontSize: 14 }}>
          Enter a question above to run all three pipelines and compare results.
        </div>
      )}
    </div>
  );
}
