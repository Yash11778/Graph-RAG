import { useState } from 'react';
import axios from 'axios';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from 'recharts';

const API_BASE = import.meta.env.VITE_API_BASE || '';
const HYBRID_PARAMS_LABEL = 'num_hops=2';

const PIPELINE_COLORS = { llm_only: '#ef4444', basic_rag: '#f97316', graphrag: '#16a34a' };
const PIPELINE_LABELS = { llm_only: 'LLM-Only', basic_rag: 'Basic RAG', graphrag: 'GraphRAG' };

const THEMES = {
  light: {
    bg: '#f8fafc', surface: '#ffffff', surface2: '#f1f5f9',
    border: '#e2e8f0', text: '#0f172a', textMuted: '#64748b', textSubtle: '#94a3b8',
    inputBg: '#ffffff', metricBg: '#f8fafc',
    graphragBorder: '#16a34a', graphragBg: '#f0fdf4',
    errorBg: '#fef2f2', errorBorder: '#fca5a5', errorText: '#dc2626',
    successBg: '#f0fdf4', successBorder: '#16a34a', successText: '#15803d',
    badgePassBg: '#dcfce7', badgePassText: '#15803d',
    badgeFailBg: '#fee2e2', badgeFailText: '#dc2626',
    chartGrid: '#e2e8f0', tooltipBg: '#ffffff',
    spinnerTrack: '#e2e8f0', spinnerHead: '#16a34a',
    btnBg: '#0f172a', btnText: '#ffffff',
    btnDisabledBg: '#e2e8f0', btnDisabledText: '#94a3b8',
    tableRowBorder: '#f1f5f9', tableHeaderText: '#64748b',
    toggleBg: '#e2e8f0', toggleText: '#0f172a',
    tagBg: '#f1f5f9', tagText: '#475569',
    bertBg: '#eff6ff', bertBorder: '#93c5fd', bertText: '#1e40af',
  },
  dark: {
    bg: '#0f172a', surface: '#1e293b', surface2: '#0f172a',
    border: '#334155', text: '#f1f5f9', textMuted: '#94a3b8', textSubtle: '#64748b',
    inputBg: '#1e293b', metricBg: '#0f172a',
    graphragBorder: '#22c55e', graphragBg: '#052e16',
    errorBg: '#450a0a', errorBorder: '#ef4444', errorText: '#fca5a5',
    successBg: '#052e16', successBorder: '#22c55e', successText: '#4ade80',
    badgePassBg: '#14532d', badgePassText: '#4ade80',
    badgeFailBg: '#450a0a', badgeFailText: '#f87171',
    chartGrid: '#334155', tooltipBg: '#1e293b',
    spinnerTrack: '#334155', spinnerHead: '#22c55e',
    btnBg: '#22c55e', btnText: '#0f172a',
    btnDisabledBg: '#1e293b', btnDisabledText: '#64748b',
    tableRowBorder: '#1e293b', tableHeaderText: '#64748b',
    toggleBg: '#334155', toggleText: '#f1f5f9',
    tagBg: '#1e293b', tagText: '#94a3b8',
    bertBg: '#1e3a5f', bertBorder: '#3b82f6', bertText: '#93c5fd',
  },
};

function Spinner({ t }) {
  return (
    <div style={{ textAlign: 'center', padding: 48 }}>
      <div style={{
        display: 'inline-block', width: 40, height: 40,
        border: `4px solid ${t.spinnerTrack}`, borderTopColor: t.spinnerHead,
        borderRadius: '50%', animation: 'spin 0.8s linear infinite',
      }} />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      <p style={{ color: t.textMuted, marginTop: 16, fontSize: 14 }}>Running all 3 pipelines…</p>
    </div>
  );
}

function JudgeBadge({ judge, t }) {
  if (!judge) return null;
  return (
    <span style={{
      background: judge === 'PASS' ? t.badgePassBg : t.badgeFailBg,
      color: judge === 'PASS' ? t.badgePassText : t.badgeFailText,
      borderRadius: 6, padding: '2px 10px', fontSize: 12, fontWeight: 700,
    }}>{judge}</span>
  );
}

function MetricBadge({ label, value, t }) {
  return (
    <div style={{
      background: t.metricBg, border: `1px solid ${t.border}`,
      borderRadius: 8, padding: '8px 14px', flex: 1, minWidth: 70,
    }}>
      <div style={{ fontSize: 10, color: t.textSubtle, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 2 }}>{label}</div>
      <div style={{ fontSize: 15, fontWeight: 700, color: t.text }}>{value}</div>
    </div>
  );
}

function PipelineCard({ name, data, judge, t }) {
  const color = PIPELINE_COLORS[name];
  const isGraphRAG = name === 'graphrag';
  return (
    <div style={{
      background: t.surface,
      border: `2px solid ${isGraphRAG ? t.graphragBorder : t.border}`,
      borderRadius: 12, padding: 20,
      display: 'flex', flexDirection: 'column', gap: 12,
      boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontWeight: 700, fontSize: 15, color }}>{PIPELINE_LABELS[name]}</span>
        <JudgeBadge judge={judge} t={t} />
      </div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <MetricBadge label="Tokens" value={data.total_tokens.toLocaleString()} t={t} />
        <MetricBadge label="Latency" value={`${data.latency_s}s`} t={t} />
        <MetricBadge label="Cost" value={`$${data.cost_usd.toFixed(6)}`} t={t} />
      </div>
      {isGraphRAG && data.retriever && (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {[
            data.retriever && `Retriever: ${data.retriever}`,
            data.graph_hops && `Hops: ${data.graph_hops}`,
            data.service && data.service,
          ].filter(Boolean).map(tag => (
            <span key={tag} style={{
              background: t.tagBg, color: t.tagText,
              borderRadius: 5, padding: '2px 8px', fontSize: 11,
            }}>{tag}</span>
          ))}
        </div>
      )}
      <div style={{
        background: t.metricBg, border: `1px solid ${t.border}`,
        borderRadius: 8, padding: 12,
        fontSize: 13, color: t.textMuted, lineHeight: 1.65,
        maxHeight: 180, overflowY: 'auto',
      }}>
        {data.answer}
      </div>
    </div>
  );
}

function BERTScorePanel({ bs, t }) {
  if (!bs) return null;
  const hit = bs.bonus_hit;
  return (
    <div style={{
      background: t.bertBg, border: `1px solid ${t.bertBorder}`,
      borderRadius: 12, padding: '16px 24px', marginBottom: 24,
      display: 'flex', alignItems: 'center', gap: 32, flexWrap: 'wrap',
    }}>
      <div>
        <div style={{ fontSize: 11, color: t.bertText, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 2 }}>BERTScore F1</div>
        <div style={{ fontSize: 22, fontWeight: 800, color: t.bertText }}>{bs.raw_f1}</div>
      </div>
      <div>
        <div style={{ fontSize: 11, color: t.bertText, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 2 }}>Rescaled F1</div>
        <div style={{ fontSize: 22, fontWeight: 800, color: t.bertText }}>{bs.rescaled_f1}</div>
      </div>
      <div>
        <div style={{ fontSize: 11, color: t.bertText, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 2 }}>Bonus Status</div>
        <span style={{
          background: hit ? t.badgePassBg : t.badgeFailBg,
          color: hit ? t.badgePassText : t.badgeFailText,
          borderRadius: 6, padding: '3px 12px', fontSize: 13, fontWeight: 700,
        }}>{hit ? 'BONUS HIT' : 'BONUS MISSED'}</span>
      </div>
      <div style={{ fontSize: 12, color: t.bertText, maxWidth: 280 }}>
        Bonus requires rescaled F1 ≥ 0.55 or raw F1 ≥ 0.88
      </div>
    </div>
  );
}

export default function App() {
  const [question, setQuestion]       = useState('');
  const [groundTruth, setGroundTruth] = useState('');
  const [loading, setLoading]         = useState(false);
  const [result, setResult]           = useState(null);
  const [error, setError]             = useState('');
  const [history, setHistory]         = useState([]);
  const [darkMode, setDarkMode]       = useState(false);

  const t = THEMES[darkMode ? 'dark' : 'light'];

  async function handleRun(e) {
    e.preventDefault();
    if (!question.trim()) return;
    setLoading(true); setError(''); setResult(null);
    try {
      const { data } = await axios.post(`${API_BASE}/compare`, {
        question:     question.trim(),
        ground_truth: groundTruth.trim(),
      });
      setResult(data);
      setHistory(prev => [{
        question:       question.trim(),
        graphrag_tokens: data.graphrag.total_tokens,
        reduction_pct:  data.token_reduction_pct,
        judge:          data.judge_graphrag || '—',
        bertscore:      data.bertscore?.raw_f1 ?? '—',
      }, ...prev]);
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setLoading(false);
    }
  }

  const chartData = result
    ? ['llm_only', 'basic_rag', 'graphrag'].map(k => ({
        name: PIPELINE_LABELS[k], tokens: result[k].total_tokens, color: PIPELINE_COLORS[k],
      }))
    : [];

  const inputStyle = {
    background: t.inputBg, border: `1px solid ${t.border}`, borderRadius: 8,
    padding: '12px 16px', fontSize: 15, color: t.text, outline: 'none', width: '100%',
  };

  return (
    <div style={{
      minHeight: '100vh', background: t.bg, color: t.text,
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      padding: '36px 24px', maxWidth: 1100, margin: '0 auto', transition: 'background 0.2s',
    }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 32 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
            <div style={{ width: 10, height: 10, borderRadius: '50%', background: '#16a34a', boxShadow: '0 0 0 3px #bbf7d0' }} />
            <span style={{ fontSize: 12, color: t.textMuted, fontWeight: 500 }}>
              TigerGraph GraphRAG Hackathon
            </span>
          </div>
          <h1 style={{ fontSize: 24, fontWeight: 800, color: t.text, margin: 0 }}>
            Token Comparison Dashboard
          </h1>
          <p style={{ color: t.textMuted, marginTop: 6, fontSize: 14, margin: '6px 0 0' }}>
            LLM-Only · Basic RAG · GraphRAG (TigerGraph Hybrid, {HYBRID_PARAMS_LABEL})
          </p>
        </div>
        <button onClick={() => setDarkMode(d => !d)} style={{
          background: t.toggleBg, color: t.toggleText, border: `1px solid ${t.border}`,
          borderRadius: 8, padding: '8px 16px', fontSize: 13, fontWeight: 500,
          cursor: 'pointer', flexShrink: 0,
        }}>
          {darkMode ? '☀ Light' : '☾ Dark'}
        </button>
      </div>

      {/* Form */}
      <div style={{
        background: t.surface, border: `1px solid ${t.border}`,
        borderRadius: 14, padding: 24, marginBottom: 28,
        boxShadow: '0 1px 4px rgba(0,0,0,0.05)',
      }}>
        <h2 style={{ fontSize: 13, fontWeight: 600, color: t.textMuted, marginBottom: 16, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          Ask a Question
        </h2>
        <form onSubmit={handleRun} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <input value={question} onChange={e => setQuestion(e.target.value)}
            placeholder="e.g. What were the key causes of World War II?" style={inputStyle} />
          <input value={groundTruth} onChange={e => setGroundTruth(e.target.value)}
            placeholder="Ground truth answer (optional — enables LLM judge + BERTScore)"
            style={{ ...inputStyle, fontSize: 14, color: t.textMuted }} />
          <button type="submit" disabled={loading || !question.trim()} style={{
            alignSelf: 'flex-start',
            background: (loading || !question.trim()) ? t.btnDisabledBg : t.btnBg,
            color:      (loading || !question.trim()) ? t.btnDisabledText : t.btnText,
            border: 'none', borderRadius: 8, padding: '11px 28px',
            fontSize: 14, fontWeight: 600,
            cursor: (loading || !question.trim()) ? 'not-allowed' : 'pointer',
          }}>
            {loading ? 'Running…' : 'Run All 3 Pipelines'}
          </button>
        </form>
      </div>

      {error && (
        <div style={{
          background: t.errorBg, border: `1px solid ${t.errorBorder}`,
          borderRadius: 10, padding: 14, marginBottom: 24, color: t.errorText, fontSize: 14,
        }}>{error}</div>
      )}

      {loading && <Spinner t={t} />}

      {result && !loading && (
        <>
          {/* Token reduction banner */}
          <div style={{
            background: t.successBg, border: `2px solid ${t.successBorder}`,
            borderRadius: 12, padding: '18px 28px', marginBottom: 24,
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 16,
          }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 28, fontWeight: 800, color: t.successText }}>
                {result.token_reduction_pct}% fewer tokens
              </div>
              <div style={{ fontSize: 13, color: t.textMuted, marginTop: 2 }}>
                GraphRAG vs Basic RAG · Multi-hop TigerGraph traversal
              </div>
            </div>
          </div>

          {/* BERTScore (only when ground truth provided) */}
          <BERTScorePanel bs={result.bertscore} t={t} />

          {/* Chart */}
          <div style={{
            background: t.surface, border: `1px solid ${t.border}`,
            borderRadius: 14, padding: '20px 24px', marginBottom: 24,
            boxShadow: '0 1px 4px rgba(0,0,0,0.05)',
          }}>
            <h2 style={{ fontSize: 13, fontWeight: 600, color: t.textMuted, marginBottom: 16, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Token Usage by Pipeline
            </h2>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={chartData} margin={{ top: 4, right: 16, bottom: 4, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={t.chartGrid} />
                <XAxis dataKey="name" stroke={t.textSubtle} tick={{ fill: t.textMuted, fontSize: 13 }} />
                <YAxis stroke={t.textSubtle} tick={{ fill: t.textMuted, fontSize: 12 }} />
                <Tooltip
                  contentStyle={{ background: t.tooltipBg, border: `1px solid ${t.border}`, borderRadius: 8 }}
                  labelStyle={{ color: t.text, fontWeight: 600 }}
                  itemStyle={{ color: t.textMuted }}
                />
                <Bar dataKey="tokens" radius={[6, 6, 0, 0]}>
                  {chartData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Pipeline cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 32 }}>
            {['llm_only', 'basic_rag', 'graphrag'].map(key => (
              <PipelineCard
                key={key} name={key} data={result[key]}
                judge={result[`judge_${key}`]}
                t={t}
              />
            ))}
          </div>
        </>
      )}

      {/* History */}
      {history.length > 0 && (
        <div style={{
          background: t.surface, border: `1px solid ${t.border}`,
          borderRadius: 14, padding: '20px 24px',
          boxShadow: '0 1px 4px rgba(0,0,0,0.05)',
        }}>
          <h2 style={{ fontSize: 13, fontWeight: 600, color: t.textMuted, marginBottom: 16, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Query History
          </h2>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr>
                {['Question', 'GraphRAG Tokens', 'Reduction', 'Judge', 'BERTScore'].map(h => (
                  <th key={h} style={{
                    padding: '8px 12px', borderBottom: `1px solid ${t.border}`,
                    color: t.tableHeaderText, textAlign: 'left', fontWeight: 600,
                    fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.04em',
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {history.map((row, i) => (
                <tr key={i} style={{ borderBottom: `1px solid ${t.tableRowBorder}` }}>
                  <td style={{ padding: '10px 12px', color: t.text, maxWidth: 260, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {row.question}
                  </td>
                  <td style={{ padding: '10px 12px', color: PIPELINE_COLORS.graphrag, fontWeight: 600 }}>
                    {row.graphrag_tokens.toLocaleString()}
                  </td>
                  <td style={{ padding: '10px 12px', fontWeight: 700, color: t.successText }}>
                    {row.reduction_pct}%
                  </td>
                  <td style={{ padding: '10px 12px' }}>
                    {row.judge !== '—'
                      ? <JudgeBadge judge={row.judge} t={t} />
                      : <span style={{ color: t.textSubtle }}>—</span>}
                  </td>
                  <td style={{ padding: '10px 12px', color: t.bertText, fontWeight: 600 }}>
                    {row.bertscore}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div style={{ marginTop: 40, textAlign: 'center', color: t.textSubtle, fontSize: 12 }}>
        TigerGraph GraphRAG Hackathon · Hybrid Retriever (DocumentChunk + Community) · {' '}
        <span style={{ color: PIPELINE_COLORS.graphrag }}>num_hops=2</span>
      </div>
    </div>
  );
}
