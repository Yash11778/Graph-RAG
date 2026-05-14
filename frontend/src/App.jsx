import { useState } from 'react';
import axios from 'axios';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from 'recharts';
import {
  Zap, Brain, GitMerge, ChevronRight, Sparkles, Database, BookOpen,
  Clock, DollarSign, Hash, CheckCircle2, XCircle, History, BarChart2,
  Moon, Sun, Network, ArrowRight, TrendingDown, Award,
} from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_BASE || '';

const PIPELINE_COLORS = { llm_only: '#ef4444', basic_rag: '#f97316', graphrag: '#16a34a' };
const PIPELINE_LABELS = { llm_only: 'LLM-Only', basic_rag: 'Basic RAG', graphrag: 'GraphRAG' };
const PIPELINE_ICONS = { llm_only: Brain, basic_rag: Database, graphrag: Network };
const PIPELINE_DESC  = {
  llm_only: 'Pure language model, no retrieval',
  basic_rag: 'FAISS vector similarity search',
  graphrag:  'TigerGraph multi-hop traversal · num_hops=2',
};

const SUGGESTED_QUESTIONS = [
  {
    label: 'Multi-hop Battles',
    icon: '⚔️',
    question: 'Which battles were fought during the Napoleonic Wars and what were their key outcomes?',
    hint: 'Spans multiple battle articles — highest hop count',
  },
  {
    label: 'War Comparison',
    icon: '🏛️',
    question: 'How did the causes of the American Civil War differ from those of the English Civil War?',
    hint: 'Cross-article reasoning across two war documents',
  },
  {
    label: 'Award History',
    icon: '🏆',
    question: 'What films have won the Academy Award for Best Production Design and what distinguished them?',
    hint: 'Traverses award + film nodes across decades',
  },
  {
    label: 'Tech + Movement',
    icon: '💻',
    question: 'What is the relationship between free software, the Free Software Foundation, and Richard Stallman?',
    hint: 'Entity graph with org, person, and concept nodes',
  },
  {
    label: 'Cold War',
    icon: '🌐',
    question: 'What were the major military conflicts and proxy wars during the Cold War period 1947–1953?',
    hint: 'Dense entity network — best GraphRAG advantage',
  },
  {
    label: 'Science + Impact',
    icon: '🔬',
    question: 'What contributions did Edward Jenner make to medicine and how did they influence biological warfare?',
    hint: 'Person → concept → military article traversal',
  },
];

const THEMES = {
  light: {
    pageBg: 'linear-gradient(135deg, #f0fdf4 0%, #f8fafc 40%, #eff6ff 100%)',
    bg: '#f8fafc',
    surface: '#ffffff',
    surface2: '#f8fafc',
    surfaceHover: '#f1f5f9',
    border: '#e2e8f0',
    borderStrong: '#cbd5e1',
    text: '#0f172a',
    textMuted: '#475569',
    textSubtle: '#94a3b8',
    inputBg: '#ffffff',
    metricBg: '#f8fafc',
    graphragBorder: '#16a34a',
    graphragBg: 'linear-gradient(135deg, #f0fdf4, #dcfce7)',
    graphragGlow: '0 0 0 1px #16a34a, 0 4px 24px rgba(22,163,74,0.15)',
    errorBg: '#fef2f2', errorBorder: '#fca5a5', errorText: '#dc2626',
    successBg: 'linear-gradient(135deg, #f0fdf4, #dcfce7)',
    successBorder: '#16a34a', successText: '#15803d',
    badgePassBg: '#dcfce7', badgePassText: '#15803d',
    badgeFailBg: '#fee2e2', badgeFailText: '#dc2626',
    chartGrid: '#e2e8f0', tooltipBg: '#ffffff',
    spinnerTrack: '#e2e8f0', spinnerHead: '#16a34a',
    btnGradient: 'linear-gradient(135deg, #16a34a, #15803d)',
    btnText: '#ffffff',
    btnDisabledBg: '#e2e8f0', btnDisabledText: '#94a3b8',
    tableRowBorder: '#f1f5f9', tableHeaderText: '#64748b',
    toggleBg: '#f1f5f9', toggleText: '#0f172a',
    tagBg: '#f1f5f9', tagText: '#475569',
    bertBg: 'linear-gradient(135deg, #eff6ff, #dbeafe)', bertBorder: '#93c5fd', bertText: '#1e40af',
    headerGradient: 'linear-gradient(135deg, #15803d, #16a34a)',
    accentGlow: 'rgba(22, 163, 74, 0.1)',
    cardShadow: '0 1px 3px rgba(0,0,0,0.06), 0 4px 16px rgba(0,0,0,0.04)',
    cardShadowHover: '0 4px 12px rgba(0,0,0,0.1), 0 8px 32px rgba(0,0,0,0.06)',
    reductionStat: '#15803d',
  },
  dark: {
    pageBg: 'linear-gradient(135deg, #020617 0%, #0f172a 50%, #030712 100%)',
    bg: '#0f172a',
    surface: '#1e293b',
    surface2: '#0f172a',
    surfaceHover: '#243147',
    border: '#334155',
    borderStrong: '#475569',
    text: '#f1f5f9',
    textMuted: '#94a3b8',
    textSubtle: '#64748b',
    inputBg: '#1e293b',
    metricBg: '#0f172a',
    graphragBorder: '#22c55e',
    graphragBg: 'linear-gradient(135deg, #052e16, #14532d)',
    graphragGlow: '0 0 0 1px #22c55e, 0 4px 24px rgba(34,197,94,0.2)',
    errorBg: '#450a0a', errorBorder: '#ef4444', errorText: '#fca5a5',
    successBg: 'linear-gradient(135deg, #052e16, #14532d)',
    successBorder: '#22c55e', successText: '#4ade80',
    badgePassBg: '#14532d', badgePassText: '#4ade80',
    badgeFailBg: '#450a0a', badgeFailText: '#f87171',
    chartGrid: '#334155', tooltipBg: '#1e293b',
    spinnerTrack: '#334155', spinnerHead: '#22c55e',
    btnGradient: 'linear-gradient(135deg, #22c55e, #16a34a)',
    btnText: '#0f172a',
    btnDisabledBg: '#1e293b', btnDisabledText: '#64748b',
    tableRowBorder: '#1e293b', tableHeaderText: '#64748b',
    toggleBg: '#334155', toggleText: '#f1f5f9',
    tagBg: '#1e293b', tagText: '#94a3b8',
    bertBg: 'linear-gradient(135deg, #1e3a5f, #1e3a8a)', bertBorder: '#3b82f6', bertText: '#93c5fd',
    headerGradient: 'linear-gradient(135deg, #22c55e, #16a34a)',
    accentGlow: 'rgba(34, 197, 94, 0.08)',
    cardShadow: '0 1px 3px rgba(0,0,0,0.3), 0 4px 16px rgba(0,0,0,0.2)',
    cardShadowHover: '0 4px 12px rgba(0,0,0,0.4), 0 8px 32px rgba(0,0,0,0.3)',
    reductionStat: '#4ade80',
  },
};

/* ─── Small helpers ─── */

function Tag({ children, color, bg }) {
  return (
    <span style={{
      background: bg || 'rgba(22,163,74,0.1)',
      color: color || '#16a34a',
      borderRadius: 6, padding: '2px 10px',
      fontSize: 11, fontWeight: 700,
      letterSpacing: '0.04em',
      textTransform: 'uppercase',
    }}>{children}</span>
  );
}

function SectionLabel({ children, t }) {
  return (
    <div style={{
      fontSize: 11, fontWeight: 700, color: t.textSubtle,
      textTransform: 'uppercase', letterSpacing: '0.08em',
      marginBottom: 16,
    }}>{children}</div>
  );
}

function JudgeBadge({ judge, t }) {
  if (!judge) return null;
  const pass = judge === 'PASS';
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4,
      background: pass ? t.badgePassBg : t.badgeFailBg,
      color: pass ? t.badgePassText : t.badgeFailText,
      borderRadius: 20, padding: '3px 10px', fontSize: 11, fontWeight: 700,
    }}>
      {pass
        ? <CheckCircle2 size={11} />
        : <XCircle size={11} />}
      {judge}
    </span>
  );
}

function MetricPill({ icon: Icon, label, value, color, t }) {
  return (
    <div style={{
      background: t.metricBg,
      border: `1px solid ${t.border}`,
      borderRadius: 10, padding: '10px 14px',
      display: 'flex', flexDirection: 'column', gap: 3, flex: 1, minWidth: 80,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
        {Icon && <Icon size={11} color={t.textSubtle} />}
        <span style={{ fontSize: 10, color: t.textSubtle, textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600 }}>
          {label}
        </span>
      </div>
      <div style={{ fontSize: 16, fontWeight: 800, color: color || t.text }}>{value}</div>
    </div>
  );
}

/* ─── Spinner ─── */

function Spinner({ t }) {
  const steps = ['Querying LLM-Only…', 'Running Basic RAG…', 'Traversing TigerGraph…'];
  const [step] = useState(0);
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      padding: '56px 24px', gap: 20,
    }}>
      <div style={{ position: 'relative', width: 60, height: 60 }}>
        <div style={{
          width: 60, height: 60,
          border: `3px solid ${t.spinnerTrack}`,
          borderTopColor: t.spinnerHead,
          borderRadius: '50%',
          animation: 'spin 0.9s linear infinite',
        }} />
        <Network size={22} color={t.spinnerHead}
          style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%,-50%)' }} />
      </div>
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontSize: 15, fontWeight: 600, color: t.text, marginBottom: 4 }}>
          Running all 3 pipelines
        </div>
        <div style={{ fontSize: 13, color: t.textMuted }}>{steps[step]}</div>
      </div>
      <div style={{ display: 'flex', gap: 6 }}>
        {steps.map((s, i) => (
          <div key={s} style={{
            width: 6, height: 6, borderRadius: '50%',
            background: i <= step ? t.spinnerHead : t.spinnerTrack,
            transition: 'background 0.3s',
          }} />
        ))}
      </div>
    </div>
  );
}

/* ─── Suggested Questions ─── */

function SuggestedQuestions({ t, onSelect }) {
  return (
    <div style={{
      background: t.surface,
      border: `1px solid ${t.border}`,
      borderRadius: 16, padding: '22px 24px',
      marginBottom: 20,
      boxShadow: t.cardShadow,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Sparkles size={16} color="#16a34a" />
          <span style={{ fontSize: 14, fontWeight: 700, color: t.text }}>Questions to try</span>
        </div>
        <Tag>Best token reduction</Tag>
      </div>
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
        gap: 10,
      }}>
        {SUGGESTED_QUESTIONS.map((sq) => (
          <button
            key={sq.question}
            className="suggest-card"
            onClick={() => onSelect(sq.question)}
            style={{
              background: t.surface2,
              border: `1px solid ${t.border}`,
              borderRadius: 12, padding: '14px 16px',
              textAlign: 'left', cursor: 'pointer',
              display: 'flex', flexDirection: 'column', gap: 6,
              boxShadow: 'none',
            }}
            onMouseEnter={e => {
              e.currentTarget.style.borderColor = '#16a34a';
              e.currentTarget.style.boxShadow = `0 0 0 1px #16a34a, 0 4px 16px ${t.accentGlow}`;
            }}
            onMouseLeave={e => {
              e.currentTarget.style.borderColor = t.border;
              e.currentTarget.style.boxShadow = 'none';
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ fontSize: 15 }}>{sq.icon}</span>
                <span style={{ fontSize: 10, fontWeight: 700, color: '#16a34a', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                  {sq.label}
                </span>
              </div>
              <ArrowRight size={13} color={t.textSubtle} />
            </div>
            <span style={{ fontSize: 13, color: t.text, lineHeight: 1.55, fontWeight: 500 }}>
              {sq.question}
            </span>
            <span style={{ fontSize: 11, color: t.textSubtle, display: 'flex', alignItems: 'center', gap: 4 }}>
              <TrendingDown size={10} /> {sq.hint}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

/* ─── Dataset Banner ─── */

function DatasetBanner({ t }) {
  const stats = [
    { icon: BookOpen, label: '371 Wikipedia articles' },
    { icon: Database, label: 'FAISS + TigerGraph indexed' },
    { icon: Network, label: 'Multi-hop graph traversal' },
    { icon: GitMerge, label: 'Community summarisation' },
  ];
  return (
    <div style={{
      background: t.surface,
      border: `1px solid ${t.border}`,
      borderRadius: 16, padding: '20px 24px',
      marginBottom: 20,
      boxShadow: t.cardShadow,
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 20, flexWrap: 'wrap' }}>
        <div style={{ flex: 1, minWidth: 220 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <div style={{
              background: t.headerGradient,
              borderRadius: 6, padding: '3px 10px',
              fontSize: 10, fontWeight: 800, color: '#fff',
              textTransform: 'uppercase', letterSpacing: '0.06em',
            }}>Knowledge Base</div>
          </div>
          <div style={{ fontSize: 15, fontWeight: 700, color: t.text, marginBottom: 4 }}>
            Wikipedia · GraphRAG Docs
          </div>
          <div style={{ fontSize: 13, color: t.textMuted, lineHeight: 1.6 }}>
            Broad topics — battles, awards, science, software — chunked, embedded, and stored
            in both <strong style={{ color: t.text }}>FAISS</strong> and a{' '}
            <strong style={{ color: t.text }}>TigerGraph knowledge graph</strong> for fair comparison.
          </div>
        </div>
        <div style={{
          display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, flexShrink: 0,
        }}>
          {stats.map(({ icon: Icon, label }) => (
            <div key={label} style={{
              display: 'flex', alignItems: 'center', gap: 8,
              background: t.surface2, borderRadius: 8, padding: '8px 12px',
              border: `1px solid ${t.border}`,
            }}>
              <Icon size={13} color="#16a34a" />
              <span style={{ fontSize: 12, color: t.textMuted, fontWeight: 500 }}>{label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ─── Pipeline Card ─── */

function PipelineCard({ name, data, judge, t }) {
  const [expanded, setExpanded] = useState(true);
  const color   = PIPELINE_COLORS[name];
  const Icon    = PIPELINE_ICONS[name];
  const isGrag  = name === 'graphrag';

  return (
    <div
      className="pipeline-card"
      style={{
        background: isGrag ? t.graphragBg : t.surface,
        border: `1px solid ${t.border}`,
        boxShadow: isGrag ? t.graphragGlow : t.cardShadow,
        borderRadius: 16,
        display: 'flex', flexDirection: 'column', gap: 0,
        overflow: 'hidden',
      }}
    >
      {/* Accent bar */}
      <div style={{ height: 3, background: color, borderRadius: '16px 16px 0 0' }} />

      <div style={{ padding: '16px 18px', display: 'flex', flexDirection: 'column', gap: 12 }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{
              background: `${color}18`, borderRadius: 8,
              width: 32, height: 32, display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <Icon size={16} color={color} />
            </div>
            <div>
              <div style={{ fontWeight: 800, fontSize: 14, color }}>{PIPELINE_LABELS[name]}</div>
              <div style={{ fontSize: 10, color: t.textSubtle, marginTop: 1 }}>{PIPELINE_DESC[name]}</div>
            </div>
          </div>
          <JudgeBadge judge={judge} t={t} />
        </div>

        {/* Metrics */}
        <div style={{ display: 'flex', gap: 6 }}>
          <MetricPill icon={Hash}       label="Tokens"  value={data.total_tokens.toLocaleString()} color={color} t={t} />
          <MetricPill icon={Clock}      label="Latency" value={`${data.latency_s}s`} t={t} />
          <MetricPill icon={DollarSign} label="Cost"    value={`$${data.cost_usd.toFixed(5)}`} t={t} />
        </div>

        {/* GraphRAG tags */}
        {isGrag && data.retriever && (
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {[
              data.retriever && `Retriever: ${data.retriever}`,
              data.graph_hops && `Hops: ${data.graph_hops}`,
              data.service,
            ].filter(Boolean).map(tag => (
              <span key={tag} style={{
                background: t.tagBg, color: t.tagText,
                borderRadius: 6, padding: '2px 8px', fontSize: 11, fontWeight: 500,
              }}>{tag}</span>
            ))}
          </div>
        )}

        {/* Answer */}
        <div>
          <button
            onClick={() => setExpanded(x => !x)}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              display: 'flex', alignItems: 'center', gap: 4,
              fontSize: 11, fontWeight: 600, color: t.textMuted,
              textTransform: 'uppercase', letterSpacing: '0.05em',
              marginBottom: 6, padding: 0,
            }}
          >
            <ChevronRight size={12} style={{ transform: expanded ? 'rotate(90deg)' : 'none', transition: 'transform 0.2s' }} />
            Answer
          </button>
          {expanded && (
            <div
              className="scrollbar-thin"
              style={{
                background: t.metricBg,
                border: `1px solid ${t.border}`,
                borderRadius: 10, padding: '12px 14px',
                fontSize: 13, color: t.textMuted, lineHeight: 1.7,
                maxHeight: 160, overflowY: 'auto',
              }}
            >
              {data.answer}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ─── BERTScore ─── */

function BERTScorePanel({ bs, t }) {
  if (!bs) return null;
  const hit = bs.bonus_hit;
  return (
    <div className="animate-fade-up" style={{
      background: t.bertBg,
      border: `1px solid ${t.bertBorder}`,
      borderRadius: 16, padding: '18px 24px', marginBottom: 20,
      display: 'flex', alignItems: 'center', gap: 28, flexWrap: 'wrap',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Award size={18} color={t.bertText} />
        <span style={{ fontWeight: 700, fontSize: 14, color: t.bertText }}>BERTScore</span>
      </div>
      {[
        { label: 'Raw F1', value: bs.raw_f1 },
        { label: 'Rescaled F1', value: bs.rescaled_f1 },
      ].map(({ label, value }) => (
        <div key={label}>
          <div style={{ fontSize: 10, color: t.bertText, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 2, fontWeight: 600 }}>{label}</div>
          <div style={{ fontSize: 24, fontWeight: 800, color: t.bertText }}>{value}</div>
        </div>
      ))}
      <div style={{ marginLeft: 'auto' }}>
        <span style={{
          display: 'inline-flex', alignItems: 'center', gap: 6,
          background: hit ? t.badgePassBg : t.badgeFailBg,
          color: hit ? t.badgePassText : t.badgeFailText,
          borderRadius: 20, padding: '5px 14px', fontSize: 12, fontWeight: 700,
        }}>
          {hit ? <CheckCircle2 size={13} /> : <XCircle size={13} />}
          {hit ? 'BONUS HIT' : 'BONUS MISSED'}
        </span>
        <div style={{ fontSize: 11, color: t.bertText, marginTop: 4, textAlign: 'right' }}>
          rescaled ≥ 0.55 or raw ≥ 0.88
        </div>
      </div>
    </div>
  );
}

/* ─── Token Reduction Hero ─── */

function ReductionHero({ result, t }) {
  const pct = result.token_reduction_pct;
  const isPositive = pct > 0;
  return (
    <div className="animate-fade-up" style={{
      background: t.successBg,
      border: `2px solid ${t.successBorder}`,
      borderRadius: 20, padding: '28px 32px', marginBottom: 20,
      display: 'flex', alignItems: 'center', gap: 32, flexWrap: 'wrap',
    }}>
      {/* Big number */}
      <div className="animate-count" style={{ textAlign: 'center' }}>
        <div style={{
          fontSize: 52, fontWeight: 900, lineHeight: 1,
          color: t.reductionStat,
          letterSpacing: '-2px',
        }}>
          {isPositive ? '-' : '+'}{Math.abs(pct)}%
        </div>
        <div style={{ fontSize: 13, color: t.successText, marginTop: 4, fontWeight: 600 }}>
          token reduction
        </div>
      </div>

      <div style={{ width: 1, height: 56, background: t.successBorder, opacity: 0.4 }} />

      {/* Mini stats */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, flex: 1, minWidth: 200 }}>
        <div style={{ fontSize: 13, color: t.successText, fontWeight: 600 }}>
          GraphRAG vs Basic RAG
        </div>
        <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
          {['llm_only', 'basic_rag', 'graphrag'].map(k => (
            <div key={k}>
              <div style={{ fontSize: 10, color: t.successText, textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600 }}>
                {PIPELINE_LABELS[k]}
              </div>
              <div style={{ fontSize: 17, fontWeight: 800, color: PIPELINE_COLORS[k] }}>
                {result[k].total_tokens.toLocaleString()}
              </div>
            </div>
          ))}
        </div>
        <div style={{ fontSize: 12, color: t.successText, opacity: 0.8 }}>
          Multi-hop TigerGraph traversal · num_hops=2
        </div>
      </div>
    </div>
  );
}

/* ─── Main App ─── */

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
        question:        question.trim(),
        graphrag_tokens: data.graphrag.total_tokens,
        reduction_pct:   data.token_reduction_pct,
        judge:           data.judge_graphrag || '—',
        bertscore:       data.bertscore?.raw_f1 ?? '—',
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
    background: t.inputBg,
    border: `1px solid ${t.border}`,
    borderRadius: 10,
    padding: '13px 16px',
    fontSize: 14,
    color: t.text,
    outline: 'none',
    width: '100%',
    transition: 'border-color 0.15s, box-shadow 0.15s',
  };

  return (
    <div style={{
      minHeight: '100vh',
      background: t.pageBg,
      color: t.text,
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      transition: 'background 0.3s',
    }}>
      <div style={{ maxWidth: 1120, margin: '0 auto', padding: '36px 24px 60px' }}>

        {/* ── Header ── */}
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 28 }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
              <div style={{
                width: 8, height: 8, borderRadius: '50%',
                background: '#16a34a',
                animation: 'pulse-ring 2s ease infinite',
              }} />
              <span style={{ fontSize: 12, color: t.textMuted, fontWeight: 600, letterSpacing: '0.04em' }}>
                TigerGraph GraphRAG Hackathon
              </span>
            </div>
            <h1 style={{
              fontSize: 30, fontWeight: 900, color: t.text,
              margin: 0, letterSpacing: '-0.5px', lineHeight: 1.2,
            }}>
              Pipeline Comparison{' '}
              <span style={{
                background: t.headerGradient,
                WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
              }}>Dashboard</span>
            </h1>
            <p style={{ color: t.textMuted, marginTop: 6, fontSize: 14 }}>
              Compare <strong style={{ color: PIPELINE_COLORS.llm_only }}>LLM-Only</strong>
              {' · '}
              <strong style={{ color: PIPELINE_COLORS.basic_rag }}>Basic RAG</strong>
              {' · '}
              <strong style={{ color: PIPELINE_COLORS.graphrag }}>GraphRAG</strong>
              {' '}on token usage, latency, cost & answer quality
            </p>
          </div>

          <button
            className="dark-toggle"
            onClick={() => setDarkMode(d => !d)}
            style={{
              background: t.toggleBg, color: t.toggleText,
              border: `1px solid ${t.border}`,
              borderRadius: 10, padding: '9px 16px',
              fontSize: 13, fontWeight: 600, cursor: 'pointer',
              display: 'flex', alignItems: 'center', gap: 6,
              flexShrink: 0,
            }}
          >
            {darkMode ? <Sun size={14} /> : <Moon size={14} />}
            {darkMode ? 'Light' : 'Dark'}
          </button>
        </div>

        {/* ── Dataset Banner ── */}
        <DatasetBanner t={t} />

        {/* ── Suggested Questions ── */}
        <SuggestedQuestions t={t} onSelect={q => { setQuestion(q); setResult(null); }} />

        {/* ── Query Form ── */}
        <div style={{
          background: t.surface,
          border: `1px solid ${t.border}`,
          borderRadius: 16, padding: '22px 24px',
          marginBottom: 24,
          boxShadow: t.cardShadow,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
            <Zap size={15} color="#16a34a" />
            <span style={{ fontSize: 14, fontWeight: 700, color: t.text }}>Ask a question</span>
          </div>
          <form onSubmit={handleRun} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <input
              value={question}
              onChange={e => setQuestion(e.target.value)}
              placeholder="e.g. Who won the Academy Award for Best Production Design in 2010?"
              style={inputStyle}
            />
            <input
              value={groundTruth}
              onChange={e => setGroundTruth(e.target.value)}
              placeholder="Ground truth (optional — enables LLM judge + BERTScore evaluation)"
              style={{ ...inputStyle, color: t.textMuted }}
            />
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <button
                type="submit"
                disabled={loading || !question.trim()}
                className="btn-primary"
                style={{
                  background: (loading || !question.trim()) ? t.btnDisabledBg : t.btnGradient,
                  color: (loading || !question.trim()) ? t.btnDisabledText : t.btnText,
                  border: 'none', borderRadius: 10,
                  padding: '12px 28px',
                  fontSize: 14, fontWeight: 700,
                  cursor: (loading || !question.trim()) ? 'not-allowed' : 'pointer',
                  display: 'flex', alignItems: 'center', gap: 8,
                  boxShadow: (loading || !question.trim()) ? 'none' : '0 2px 8px rgba(22,163,74,0.3)',
                }}
              >
                <BarChart2 size={15} />
                {loading ? 'Running…' : 'Run All 3 Pipelines'}
              </button>
              {question && !loading && (
                <button
                  type="button"
                  onClick={() => { setQuestion(''); setGroundTruth(''); setResult(null); setError(''); }}
                  style={{
                    background: 'none', border: `1px solid ${t.border}`,
                    borderRadius: 10, padding: '12px 16px',
                    fontSize: 13, color: t.textMuted, cursor: 'pointer',
                    fontWeight: 500,
                  }}
                >
                  Clear
                </button>
              )}
            </div>
          </form>
        </div>

        {/* ── Error ── */}
        {error && (
          <div style={{
            background: t.errorBg, border: `1px solid ${t.errorBorder}`,
            borderRadius: 12, padding: '14px 18px', marginBottom: 20,
            color: t.errorText, fontSize: 14,
            display: 'flex', alignItems: 'center', gap: 8,
          }}>
            <XCircle size={16} /> {error}
          </div>
        )}

        {/* ── Loading ── */}
        {loading && (
          <div style={{
            background: t.surface, border: `1px solid ${t.border}`,
            borderRadius: 16, marginBottom: 20,
            boxShadow: t.cardShadow,
          }}>
            <Spinner t={t} />
          </div>
        )}

        {/* ── Results ── */}
        {result && !loading && (
          <>
            <ReductionHero result={result} t={t} />

            <BERTScorePanel bs={result.bertscore} t={t} />

            {/* Chart + Cards side by side on wide screens */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 16, marginBottom: 20 }}>

              {/* Chart */}
              <div style={{
                background: t.surface, border: `1px solid ${t.border}`,
                borderRadius: 16, padding: '20px 20px',
                boxShadow: t.cardShadow,
              }}>
                <SectionLabel t={t}>Token usage</SectionLabel>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={chartData} margin={{ top: 4, right: 8, bottom: 4, left: -16 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={t.chartGrid} vertical={false} />
                    <XAxis dataKey="name" stroke={t.textSubtle} tick={{ fill: t.textMuted, fontSize: 12 }} axisLine={false} tickLine={false} />
                    <YAxis stroke={t.textSubtle} tick={{ fill: t.textMuted, fontSize: 11 }} axisLine={false} tickLine={false} />
                    <Tooltip
                      contentStyle={{ background: t.tooltipBg, border: `1px solid ${t.border}`, borderRadius: 10, boxShadow: t.cardShadow }}
                      labelStyle={{ color: t.text, fontWeight: 700 }}
                      itemStyle={{ color: t.textMuted }}
                      cursor={{ fill: t.accentGlow }}
                    />
                    <Bar dataKey="tokens" radius={[8, 8, 0, 0]} maxBarSize={52}>
                      {chartData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>

              {/* Pipeline cards stacked */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                <SectionLabel t={t} style={{ marginBottom: 0 }}>Pipeline results</SectionLabel>
                {['llm_only', 'basic_rag', 'graphrag'].map(key => (
                  <PipelineCard
                    key={key} name={key} data={result[key]}
                    judge={result[`judge_${key}`]}
                    t={t}
                  />
                ))}
              </div>
            </div>
          </>
        )}

        {/* ── History ── */}
        {history.length > 0 && (
          <div style={{
            background: t.surface, border: `1px solid ${t.border}`,
            borderRadius: 16, padding: '22px 24px',
            boxShadow: t.cardShadow,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
              <History size={15} color={t.textMuted} />
              <span style={{ fontSize: 14, fontWeight: 700, color: t.text }}>Query history</span>
              <span style={{
                background: t.surface2, border: `1px solid ${t.border}`,
                borderRadius: 20, padding: '1px 8px', fontSize: 11,
                color: t.textMuted, fontWeight: 600, marginLeft: 4,
              }}>{history.length}</span>
            </div>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead>
                  <tr>
                    {['Question', 'GraphRAG Tokens', 'Reduction', 'Judge', 'BERTScore'].map(h => (
                      <th key={h} style={{
                        padding: '8px 12px', borderBottom: `1px solid ${t.border}`,
                        color: t.textSubtle, textAlign: 'left', fontWeight: 700,
                        fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.06em',
                        whiteSpace: 'nowrap',
                      }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {history.map((row, i) => (
                    <tr
                      key={i}
                      className="history-row"
                      style={{ borderBottom: `1px solid ${t.tableRowBorder}` }}
                      onMouseEnter={e => e.currentTarget.style.background = t.surfaceHover}
                      onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                    >
                      <td style={{ padding: '10px 12px', color: t.text, maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {row.question}
                      </td>
                      <td style={{ padding: '10px 12px', color: PIPELINE_COLORS.graphrag, fontWeight: 700 }}>
                        {row.graphrag_tokens.toLocaleString()}
                      </td>
                      <td style={{ padding: '10px 12px', fontWeight: 800, color: t.reductionStat }}>
                        {row.reduction_pct > 0 ? '-' : '+'}{Math.abs(row.reduction_pct)}%
                      </td>
                      <td style={{ padding: '10px 12px' }}>
                        {row.judge !== '—'
                          ? <JudgeBadge judge={row.judge} t={t} />
                          : <span style={{ color: t.textSubtle }}>—</span>}
                      </td>
                      <td style={{ padding: '10px 12px', color: t.bertText || t.textMuted, fontWeight: 600 }}>
                        {row.bertscore}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ── Footer ── */}
        <div style={{ marginTop: 48, textAlign: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, marginBottom: 6 }}>
            <Network size={13} color="#16a34a" />
            <span style={{ fontSize: 12, color: t.textSubtle, fontWeight: 500 }}>
              TigerGraph GraphRAG Hackathon
            </span>
          </div>
          <div style={{ fontSize: 12, color: t.textSubtle }}>
            Hybrid Retriever · DocumentChunk + Community · num_hops=2
          </div>
        </div>

      </div>
    </div>
  );
}
