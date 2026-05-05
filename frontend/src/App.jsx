import { useState } from 'react';
import axios from 'axios';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from 'recharts';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8080';

const PIPELINE_COLORS = { llm_only: '#ef4444', basic_rag: '#f97316', graphrag: '#22c55e' };
const PIPELINE_LABELS = { llm_only: 'LLM-Only', basic_rag: 'Basic RAG', graphrag: 'GraphRAG' };

function Spinner() {
  return (
    <div style={{ textAlign: 'center', padding: 48 }}>
      <div style={{
        display: 'inline-block', width: 40, height: 40,
        border: '4px solid #334155', borderTopColor: '#22c55e',
        borderRadius: '50%', animation: 'spin 0.8s linear infinite',
      }} />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      <p style={{ color: '#94a3b8', marginTop: 16 }}>Running all 3 pipelines…</p>
    </div>
  );
}

function PipelineCard({ name, data, judge }) {
  const color = PIPELINE_COLORS[name];
  const isGraphRAG = name === 'graphrag';
  return (
    <div style={{
      background: '#1e293b',
      border: `2px solid ${isGraphRAG ? '#22c55e' : '#334155'}`,
      borderRadius: 12,
      padding: 20,
      display: 'flex',
      flexDirection: 'column',
      gap: 10,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontWeight: 700, fontSize: 15, color }}>
          {PIPELINE_LABELS[name]}
        </span>
        {isGraphRAG && judge && (
          <span style={{
            background: judge === 'PASS' ? '#14532d' : '#450a0a',
            color: judge === 'PASS' ? '#4ade80' : '#f87171',
            border: `1px solid ${judge === 'PASS' ? '#22c55e' : '#ef4444'}`,
            borderRadius: 6,
            padding: '2px 10px',
            fontSize: 12,
            fontWeight: 700,
          }}>{judge}</span>
        )}
      </div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {[
          ['Tokens', data.total_tokens.toLocaleString()],
          ['Latency', `${data.latency_s}s`],
          ['Cost', `$${data.cost_usd.toFixed(6)}`],
        ].map(([label, val]) => (
          <div key={label} style={{
            background: '#0f172a', borderRadius: 8, padding: '6px 12px', flex: 1, minWidth: 80,
          }}>
            <div style={{ fontSize: 10, color: '#64748b', textTransform: 'uppercase' }}>{label}</div>
            <div style={{ fontSize: 15, fontWeight: 700, color: '#f1f5f9' }}>{val}</div>
          </div>
        ))}
      </div>
      <div style={{
        background: '#0f172a', borderRadius: 8, padding: 12,
        fontSize: 13, color: '#cbd5e1', lineHeight: 1.6,
        maxHeight: 180, overflowY: 'auto',
      }}>
        {data.answer}
      </div>
    </div>
  );
}

export default function App() {
  const [question, setQuestion] = useState('');
  const [groundTruth, setGroundTruth] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [history, setHistory] = useState([]);

  async function handleRun(e) {
    e.preventDefault();
    if (!question.trim()) return;
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const { data } = await axios.post(`${API_BASE}/compare`, {
        question: question.trim(),
        ground_truth: groundTruth.trim(),
      });
      setResult(data);
      setHistory(prev => [{
        question: question.trim(),
        graphrag_tokens: data.graphrag.total_tokens,
        reduction_pct: data.token_reduction_pct,
        judge: data.judge_graphrag || '—',
      }, ...prev]);
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setLoading(false);
    }
  }

  const chartData = result
    ? ['llm_only', 'basic_rag', 'graphrag'].map(k => ({
        name: PIPELINE_LABELS[k],
        tokens: result[k].total_tokens,
        color: PIPELINE_COLORS[k],
      }))
    : [];

  return (
    <div style={{
      minHeight: '100vh', background: '#0f172a', color: '#f1f5f9',
      fontFamily: 'system-ui, sans-serif', padding: '32px 24px', maxWidth: 1100, margin: '0 auto',
    }}>
      <h1 style={{ fontSize: 26, fontWeight: 800, marginBottom: 4 }}>
        GraphRAG Token Comparison Dashboard
      </h1>
      <p style={{ color: '#64748b', marginBottom: 28, fontSize: 14 }}>
        Proves GraphRAG uses 60–80% fewer tokens than Basic RAG.
      </p>

      <form onSubmit={handleRun} style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 28 }}>
        <input
          value={question}
          onChange={e => setQuestion(e.target.value)}
          placeholder="Ask a question…"
          style={{
            background: '#1e293b', border: '1px solid #334155', borderRadius: 8,
            padding: '12px 16px', fontSize: 15, color: '#f1f5f9', outline: 'none', width: '100%',
          }}
        />
        <input
          value={groundTruth}
          onChange={e => setGroundTruth(e.target.value)}
          placeholder="Ground truth answer (optional — enables LLM judge)"
          style={{
            background: '#1e293b', border: '1px solid #334155', borderRadius: 8,
            padding: '12px 16px', fontSize: 14, color: '#94a3b8', outline: 'none', width: '100%',
          }}
        />
        <button
          type="submit"
          disabled={loading || !question.trim()}
          style={{
            alignSelf: 'flex-start',
            background: loading ? '#1e293b' : '#22c55e',
            color: loading ? '#64748b' : '#0f172a',
            border: 'none', borderRadius: 8,
            padding: '12px 28px', fontSize: 15, fontWeight: 700,
            cursor: loading ? 'not-allowed' : 'pointer',
          }}
        >
          {loading ? 'Running…' : 'Run All 3 Pipelines'}
        </button>
      </form>

      {error && (
        <div style={{
          background: '#450a0a', border: '1px solid #ef4444', borderRadius: 8,
          padding: 14, marginBottom: 24, color: '#fca5a5',
        }}>{error}</div>
      )}

      {loading && <Spinner />}

      {result && !loading && (
        <>
          <div style={{
            background: '#14532d', border: '2px solid #22c55e', borderRadius: 12,
            padding: '20px 28px', marginBottom: 28, textAlign: 'center',
            fontSize: 28, fontWeight: 700, color: '#4ade80',
          }}>
            GraphRAG used {result.token_reduction_pct}% fewer tokens than Basic RAG
          </div>

          <div style={{ background: '#1e293b', borderRadius: 12, padding: 20, marginBottom: 28 }}>
            <h2 style={{ fontSize: 14, fontWeight: 600, color: '#94a3b8', marginBottom: 16 }}>
              TOKEN USAGE BY PIPELINE
            </h2>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={chartData} margin={{ top: 4, right: 16, bottom: 4, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="name" stroke="#64748b" tick={{ fill: '#94a3b8', fontSize: 13 }} />
                <YAxis stroke="#64748b" tick={{ fill: '#94a3b8', fontSize: 12 }} />
                <Tooltip
                  contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }}
                  labelStyle={{ color: '#f1f5f9' }}
                  itemStyle={{ color: '#94a3b8' }}
                />
                <Bar dataKey="tokens" radius={[4, 4, 0, 0]}>
                  {chartData.map((entry, i) => (
                    <Cell key={i} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16, marginBottom: 32 }}>
            {['llm_only', 'basic_rag', 'graphrag'].map(key => (
              <PipelineCard
                key={key}
                name={key}
                data={result[key]}
                judge={result.judge_graphrag}
              />
            ))}
          </div>
        </>
      )}

      {history.length > 0 && (
        <div style={{ background: '#1e293b', borderRadius: 12, padding: 20 }}>
          <h2 style={{ fontSize: 14, fontWeight: 600, color: '#94a3b8', marginBottom: 14 }}>
            QUERY HISTORY
          </h2>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ color: '#64748b', textAlign: 'left' }}>
                {['Question', 'GraphRAG Tokens', 'Reduction %', 'Judge'].map(h => (
                  <th key={h} style={{ padding: '6px 12px', borderBottom: '1px solid #334155' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {history.map((row, i) => (
                <tr key={i} style={{ borderBottom: '1px solid #1e293b' }}>
                  <td style={{ padding: '8px 12px', color: '#cbd5e1', maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {row.question}
                  </td>
                  <td style={{ padding: '8px 12px', color: '#22c55e', fontWeight: 600 }}>
                    {row.graphrag_tokens.toLocaleString()}
                  </td>
                  <td style={{ padding: '8px 12px', color: '#4ade80', fontWeight: 700 }}>
                    {row.reduction_pct}%
                  </td>
                  <td style={{ padding: '8px 12px' }}>
                    {row.judge !== '—' ? (
                      <span style={{
                        color: row.judge === 'PASS' ? '#4ade80' : '#f87171',
                        fontWeight: 700,
                      }}>{row.judge}</span>
                    ) : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
