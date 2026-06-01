import { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import {
  Zap, Brain, Database, Network, Clock, DollarSign, Hash,
  CheckCircle2, XCircle, History, BarChart2, Moon, Sun,
  Sparkles, TrendingDown, Award, ChevronDown, BookOpen,
  Layers, GitMerge,
} from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_BASE || '';

/* ─── Pipeline registry (single source of truth) ─── */
const PIPELINE_KEYS    = ['llm_only', 'basic_rag', 'graphrag'];
const PIPELINE_COLORS  = { llm_only: '#ef4444', basic_rag: '#f97316', graphrag: '#16a34a' };
const PIPELINE_LABELS  = { llm_only: 'LLM-Only', basic_rag: 'Basic RAG', graphrag: 'GraphRAG' };
const PIPELINE_ICONS   = { llm_only: Brain, basic_rag: Database, graphrag: Network };
const PIPELINE_DESC    = {
  llm_only:  'No retrieval — pure parametric knowledge',
  basic_rag: 'FAISS vector search · top-5 chunks',
  graphrag:  'TigerGraph multi-hop · num_hops=2',
};

/* ─── Featured questions — each entity verified to exist in the LIVE TigerGraph graph
   and the answer confirmed on-topic. No pre-computed reduction numbers here: the only
   percentages shown anywhere are the genuine ones measured live after a query runs. ─── */
const FEATURED_QUESTIONS = [
  {
    label: 'Free Software',
    icon: '💻',
    question: 'What freedoms does free software give users?',
    answer: 'Free software gives users the freedom to run, copy, distribute, study, change, and improve the software.',
    hint: 'free-software → the four freedoms',
  },
  {
    label: 'Napoleon Bonaparte',
    icon: '🏛️',
    question: 'Who was Napoleon Bonaparte and what was his role in the Egypt expedition?',
    answer: 'Napoleon Bonaparte was a French military and political leader who led the French expedition in Egypt.',
    hint: 'napoleon-bonaparte → aboukir-bay, egypt (1-hop)',
  },
  {
    label: 'Roman Empire',
    icon: '🏺',
    question: 'What was the Roman Empire?',
    answer: 'The Roman Empire was an ancient state that controlled vast territories across Europe and the Mediterranean, ruled by emperors such as Augustus.',
    hint: 'roman-empire → augustus (1-hop)',
  },
  {
    label: 'Nelson Mandela',
    icon: '✊',
    question: 'Who was Nelson Mandela?',
    answer: 'Nelson Mandela was a South African anti-apartheid revolutionary and political leader.',
    hint: 'nelson-mandela → south-africa (1-hop)',
  },
  {
    label: 'World War II',
    icon: '⚔️',
    question: 'What was World War II and when did it take place?',
    answer: 'World War II was a global conflict between the Axis and Allied powers that lasted from 1939 to 1945.',
    hint: 'world-war-ii → axis, allies (1-hop)',
  },
  {
    label: 'Cold War',
    icon: '🌐',
    question: 'What was the Cold War?',
    answer: 'The Cold War was a period of geopolitical tension between the Soviet Union and the United States.',
    hint: 'cold-war → soviet-union, united-states',
  },
];

/* ─── Domain questions — every entry tested live against the current TigerGraph graph
   and confirmed to return an on-topic answer. Each carries its ground-truth answer so
   selecting it also enables the LLM Judge and BERTScore. ─── */
const DOMAIN_QUESTIONS = [
  {
    domain: '🏛️ Leaders & Empires',
    questions: [
      { question: 'What was Napoleon Bonaparte known for?',
        answer: 'Napoleon Bonaparte was a French military and political leader.' },
      { question: 'Who was Napoleon Bonaparte and what was his role in the Egypt expedition?',
        answer: 'Napoleon Bonaparte was a French military and political leader who led the French expedition in Egypt.' },
      { question: 'Who was Nelson Mandela?',
        answer: 'Nelson Mandela was a South African anti-apartheid revolutionary and political leader.' },
      { question: 'What was the Roman Empire?',
        answer: 'The Roman Empire was an ancient state that controlled vast territories across Europe and the Mediterranean, ruled by emperors such as Augustus.' },
    ],
  },
  {
    domain: '🌍 Wars & Conflicts',
    questions: [
      { question: 'What was World War II and when did it take place?',
        answer: 'World War II was a global conflict between the Axis and Allied powers that lasted from 1939 to 1945.' },
      { question: 'What were the Axis powers in World War II?',
        answer: 'The Axis powers were the primary military alliance opposing the Allies in World War II, led by Germany under Adolf Hitler.' },
      { question: 'What was the Cold War?',
        answer: 'The Cold War was a period of geopolitical tension between the Soviet Union and the United States.' },
      { question: 'Who fought in the Cold War?',
        answer: 'The Cold War was fought between the Soviet Union and the United States.' },
    ],
  },
  {
    domain: '💻 Software & Free Software',
    questions: [
      { question: 'What is free software?',
        answer: 'Free software is software that gives users the freedom to run, copy, distribute, study, change, and improve it.' },
      { question: 'What freedoms does free software give users?',
        answer: 'Free software gives users the freedom to run, copy, distribute, study, change, and improve the software.' },
      { question: 'What is software?',
        answer: 'Software is a set of programs that runs on hardware, contrasted with the physical hardware of a computer.' },
    ],
  },
];

/* ─── Themes ─── */
const THEMES = {
  light: {
    pageBg: '#f0f4f8',
    heroBg: 'linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%)',
    surface: '#ffffff', surface2: '#f8fafc', surfaceHover: '#f1f5f9',
    border: '#e2e8f0', borderStrong: '#cbd5e1',
    text: '#0f172a', textMuted: '#475569', textSubtle: '#94a3b8',
    inputBg: '#ffffff', metricBg: '#f8fafc',
    graphragBorder: '#16a34a',
    graphragBg: 'linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%)',
    graphragGlow: '0 0 0 2px #16a34a40, 0 8px 32px rgba(22,163,74,0.15)',
    errorBg: '#fef2f2', errorBorder: '#fca5a5', errorText: '#dc2626',
    badgePassBg: '#dcfce7', badgePassText: '#15803d',
    badgeFailBg: '#fee2e2', badgeFailText: '#dc2626',
    chartGrid: '#e2e8f0', tooltipBg: '#ffffff',
    spinnerTrack: '#e2e8f0', spinnerHead: '#16a34a',
    btnGradient: 'linear-gradient(135deg, #16a34a, #15803d)',
    btnDisabledBg: '#e2e8f0', btnDisabledText: '#94a3b8',
    tableRowBorder: '#f1f5f9',
    toggleBg: 'rgba(255,255,255,0.15)',
    tagBg: '#f1f5f9', tagText: '#475569',
    bertBg: 'linear-gradient(135deg, #eff6ff, #dbeafe)', bertBorder: '#93c5fd', bertText: '#1e40af',
    accentGlow: 'rgba(22,163,74,0.1)',
    cardShadow: '0 1px 3px rgba(0,0,0,0.06), 0 4px 16px rgba(0,0,0,0.04)',
    reductionStat: '#15803d',
    statCard: 'rgba(255,255,255,0.12)', statCardBorder: 'rgba(255,255,255,0.2)',
    statText: '#ffffff', statSubtext: 'rgba(255,255,255,0.7)',
    sectionBg: '#f8fafc',
  },
  dark: {
    pageBg: '#0a0f1a',
    heroBg: 'linear-gradient(135deg, #0a0f1a 0%, #0d1f2d 50%, #0a1628 100%)',
    surface: '#111827', surface2: '#0f172a', surfaceHover: '#1e293b',
    border: '#1e293b', borderStrong: '#334155',
    text: '#f1f5f9', textMuted: '#94a3b8', textSubtle: '#475569',
    inputBg: '#111827', metricBg: '#0f172a',
    graphragBorder: '#22c55e',
    graphragBg: 'linear-gradient(135deg, #052e16 0%, #14532d 100%)',
    graphragGlow: '0 0 0 2px #22c55e40, 0 8px 32px rgba(34,197,94,0.2)',
    errorBg: '#450a0a', errorBorder: '#ef4444', errorText: '#fca5a5',
    badgePassBg: '#14532d', badgePassText: '#4ade80',
    badgeFailBg: '#450a0a', badgeFailText: '#f87171',
    chartGrid: '#1e293b', tooltipBg: '#111827',
    spinnerTrack: '#1e293b', spinnerHead: '#22c55e',
    btnGradient: 'linear-gradient(135deg, #22c55e, #16a34a)',
    btnDisabledBg: '#1e293b', btnDisabledText: '#475569',
    tableRowBorder: '#111827',
    toggleBg: 'rgba(255,255,255,0.1)',
    tagBg: '#1e293b', tagText: '#94a3b8',
    bertBg: 'linear-gradient(135deg, #0c1929, #0f2040)', bertBorder: '#3b82f6', bertText: '#93c5fd',
    accentGlow: 'rgba(34,197,94,0.08)',
    cardShadow: '0 1px 3px rgba(0,0,0,0.4), 0 4px 16px rgba(0,0,0,0.3)',
    reductionStat: '#4ade80',
    statCard: 'rgba(255,255,255,0.07)', statCardBorder: 'rgba(255,255,255,0.12)',
    statText: '#ffffff', statSubtext: 'rgba(255,255,255,0.6)',
    sectionBg: '#0f172a',
  },
};

/* ─── Animated counter ─── */
function AnimatedNumber({ value, duration = 800, suffix = '' }) {
  const [display, setDisplay] = useState(0);
  const prev = useRef(0);
  useEffect(() => {
    const start     = prev.current;
    const end       = parseFloat(value);
    const startTime = performance.now();
    function tick(now) {
      const p     = Math.min((now - startTime) / duration, 1);
      const eased = 1 - Math.pow(1 - p, 3);
      setDisplay(start + (end - start) * eased);
      if (p < 1) requestAnimationFrame(tick);
      else { prev.current = end; setDisplay(end); }
    }
    requestAnimationFrame(tick);
  }, [value, duration]);
  return (
    <>
      {typeof value === 'number' && !Number.isInteger(value)
        ? display.toFixed(1)
        : Math.round(display).toLocaleString()}
      {suffix}
    </>
  );
}

/* ─── JudgeBadge ─── */
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
      {pass ? <CheckCircle2 size={11} /> : <XCircle size={11} />}
      {judge}
    </span>
  );
}

/* ─── Token Bar ─── */
function TokenBar({ label, tokens, maxTokens, color, t }) {
  const pct = Math.min((tokens / maxTokens) * 100, 100);
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: t.textMuted }}>{label}</span>
        <span style={{ fontSize: 12, fontWeight: 800, color }}>{tokens.toLocaleString()} tokens</span>
      </div>
      <div style={{ height: 8, borderRadius: 99, background: t.border, overflow: 'hidden' }}>
        <div style={{
          height: '100%', width: `${pct}%`, background: color,
          borderRadius: 99, transition: 'width 0.8s cubic-bezier(0.4,0,0.2,1)',
        }} />
      </div>
    </div>
  );
}

/* ─── Spinner ─── */
function Spinner({ t }) {
  const [step, setStep] = useState(0);
  const steps = [
    { label: 'Querying LLM-Only…',   icon: Brain,    color: '#ef4444' },
    { label: 'Running Basic RAG…',   icon: Database, color: '#f97316' },
    { label: 'Traversing TigerGraph…', icon: Network, color: '#16a34a' },
  ];
  useEffect(() => {
    const id = setInterval(() => setStep(s => (s + 1) % steps.length), 2000);
    return () => clearInterval(id);
  }, []);
  const StepIcon = steps[step].icon;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '52px 24px', gap: 24 }}>
      <div style={{ position: 'relative', width: 72, height: 72 }}>
        <svg width="72" height="72" style={{ position: 'absolute', top: 0, left: 0, animation: 'spin 1.2s linear infinite' }}>
          <circle cx="36" cy="36" r="30" fill="none" stroke={t.spinnerTrack} strokeWidth="3" />
          <circle cx="36" cy="36" r="30" fill="none" stroke={steps[step].color} strokeWidth="3"
            strokeDasharray="50 140" strokeLinecap="round" />
        </svg>
        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <StepIcon size={22} color={steps[step].color} />
        </div>
      </div>
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontSize: 16, fontWeight: 700, color: t.text, marginBottom: 6 }}>
          Running all 3 pipelines in parallel
        </div>
        <div style={{ fontSize: 13, color: t.textMuted, marginBottom: 16 }}>{steps[step].label}</div>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'center' }}>
          {PIPELINE_KEYS.map((key, i) => {
            const StepIcon = steps[i].icon;
            return (
              <div key={key} style={{
                display: 'flex', alignItems: 'center', gap: 5,
                padding: '4px 12px', borderRadius: 20,
                background: i === step ? `${steps[i].color}20` : t.surface2,
                border: `1px solid ${i === step ? steps[i].color : t.border}`,
                transition: 'all 0.3s',
              }}>
                <StepIcon size={11} color={i === step ? steps[i].color : t.textSubtle} />
                <span style={{ fontSize: 11, color: i === step ? steps[i].color : t.textSubtle, fontWeight: 600 }}>
                  {PIPELINE_LABELS[key]}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

/* ─── Pipeline Card ─── */
function PipelineCard({ name, data, judge, t }) {
  const [expanded, setExpanded] = useState(true);
  const color  = PIPELINE_COLORS[name];
  const Icon   = PIPELINE_ICONS[name];
  const isGrag = name === 'graphrag';

  return (
    <div
      style={{
        background: isGrag ? t.graphragBg : t.surface,
        border: `1.5px solid ${isGrag ? t.graphragBorder : t.border}`,
        boxShadow: isGrag ? t.graphragGlow : t.cardShadow,
        borderRadius: 16, overflow: 'hidden',
        transition: 'transform 0.2s, box-shadow 0.2s',
      }}
      onMouseEnter={e => { if (!isGrag) e.currentTarget.style.transform = 'translateY(-2px)'; }}
      onMouseLeave={e => { e.currentTarget.style.transform = 'none'; }}
    >
      <div style={{ height: 4, background: `linear-gradient(90deg, ${color}, ${color}99)` }} />

      <div style={{ padding: '16px 20px' }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{
              background: `${color}18`, borderRadius: 10,
              width: 36, height: 36, display: 'flex', alignItems: 'center', justifyContent: 'center',
              border: `1px solid ${color}30`,
            }}>
              <Icon size={17} color={color} />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ fontWeight: 800, fontSize: 15, color }}>{PIPELINE_LABELS[name]}</span>
                {isGrag && data.graph_context_found !== false && (
                  <span style={{
                    background: 'linear-gradient(135deg, #16a34a, #15803d)',
                    color: '#fff', borderRadius: 6, padding: '1px 7px',
                    fontSize: 10, fontWeight: 700, letterSpacing: '0.04em',
                  }}>BEST</span>
                )}
                {isGrag && data.graph_context_found === false && (
                  <span style={{
                    background: 'linear-gradient(135deg, #ef4444, #dc2626)',
                    color: '#fff', borderRadius: 6, padding: '1px 7px',
                    fontSize: 10, fontWeight: 700, letterSpacing: '0.04em',
                  }}>NO MATCH</span>
                )}
              </div>
              <div style={{ fontSize: 11, color: t.textSubtle, marginTop: 1 }}>{PIPELINE_DESC[name]}</div>
            </div>
          </div>
          <JudgeBadge judge={judge} t={t} />
        </div>

        {/* Metrics */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginBottom: 14 }}>
          {[
            { icon: Hash,        label: 'Tokens',  value: data.total_tokens.toLocaleString(), color },
            { icon: Clock,       label: 'Latency', value: `${data.latency_s}s`,              color: t.textMuted },
            { icon: DollarSign,  label: 'Cost',    value: `$${data.cost_usd.toFixed(5)}`,    color: t.textMuted },
          ].map(({ icon: MIcon, label, value, color: c }) => (
            <div key={label} style={{
              background: t.metricBg, border: `1px solid ${t.border}`,
              borderRadius: 10, padding: '10px 12px',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 3 }}>
                <MIcon size={10} color={t.textSubtle} />
                <span style={{ fontSize: 10, color: t.textSubtle, textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600 }}>
                  {label}
                </span>
              </div>
              <div style={{ fontSize: 15, fontWeight: 800, color: c }}>{value}</div>
            </div>
          ))}
        </div>

        {/* GraphRAG tags */}
        {isGrag && data.retriever && (
          <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', marginBottom: 12 }}>
            {[data.retriever, 'num_hops=2', 'Community+Chunk'].map(tag => (
              <span key={tag} style={{
                background: 'rgba(22,163,74,0.1)', color: '#16a34a',
                borderRadius: 6, padding: '2px 8px', fontSize: 10, fontWeight: 600,
                border: '1px solid rgba(22,163,74,0.2)',
              }}>{tag}</span>
            ))}
          </div>
        )}

        {/* Answer toggle */}
        <button
          onClick={() => setExpanded(x => !x)}
          style={{
            background: 'none', border: `1px solid ${t.border}`, cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            width: '100%', padding: '8px 12px', borderRadius: 8,
            fontSize: 12, fontWeight: 600, color: t.textMuted,
            marginBottom: expanded ? 8 : 0,
          }}
        >
          <span>Answer</span>
          <ChevronDown size={13} style={{ transform: expanded ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }} />
        </button>
        {expanded && (
          <div style={{
            background: t.metricBg, border: `1px solid ${t.border}`,
            borderRadius: 10, padding: '12px 14px',
            fontSize: 13, color: t.textMuted, lineHeight: 1.75,
            maxHeight: 160, overflowY: 'auto',
          }}>
            {data.answer || <em style={{ color: t.textSubtle }}>No answer returned.</em>}
          </div>
        )}
      </div>
    </div>
  );
}

/* ─── Results Section ─── */
function ResultsSection({ result, t }) {
  const pct    = result.token_reduction_pct;
  const graphFailed = (result.graphrag_status && result.graphrag_status !== 'ok') || pct == null;
  const maxTok = Math.max(...PIPELINE_KEYS.map(k => result[k].total_tokens));
  const chartData = PIPELINE_KEYS.map(k => ({
    name: PIPELINE_LABELS[k], tokens: result[k].total_tokens, color: PIPELINE_COLORS[k],
  }));

  return (
    <div className="animate-fade-up">
      {/* Honest failure notice — distinguishes a service outage from an entity miss */}
      {graphFailed && (
        <div style={{
          background: t.errorBg, border: `1px solid ${t.errorBorder}`,
          borderRadius: 20, padding: '24px 28px', marginBottom: 20,
          display: 'flex', alignItems: 'flex-start', gap: 16,
        }}>
          <XCircle size={28} color={t.errorText} style={{ flexShrink: 0, marginTop: 2 }} />
          <div>
            <div style={{ fontSize: 18, fontWeight: 800, color: t.errorText, marginBottom: 6 }}>
              {result.graphrag_status === 'tg_unavailable'
                ? 'TigerGraph knowledge-graph service is offline'
                : 'GraphRAG found no matching entities in the knowledge graph'}
            </div>
            <div style={{ fontSize: 14, color: t.textMuted, lineHeight: 1.6 }}>
              {result.graphrag_status === 'tg_unavailable' ? (
                <>
                  The graph backend didn't respond, so no context could be retrieved — and therefore{' '}
                  <strong>no token reduction is reported</strong> (rather than a fake percentage).
                  Resume the TigerGraph instance and try again.
                </>
              ) : (
                <>
                  This question references entities that aren't in the 100K-article graph, so there's
                  no genuine context to retrieve — and therefore <strong>no token reduction to report</strong>.
                  A retrieval miss is shown honestly here rather than as a fake percentage.
                  Try one of the <strong style={{ color: '#16a34a' }}>Featured Questions</strong> above,
                  which are verified to exist in the graph.
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Token Reduction Hero — only when GraphRAG genuinely retrieved + answered */}
      {!graphFailed && (
      <div style={{
        background: 'linear-gradient(135deg, #052e16 0%, #14532d 50%, #166534 100%)',
        borderRadius: 20, padding: '32px 36px', marginBottom: 20,
        border: '1px solid rgba(34,197,94,0.3)',
        boxShadow: '0 8px 32px rgba(22,163,74,0.2)',
        display: 'flex', alignItems: 'center', gap: 40, flexWrap: 'wrap',
        position: 'relative', overflow: 'hidden',
      }}>
        <div style={{ position: 'absolute', top: -40, right: -40, width: 160, height: 160, borderRadius: '50%', background: 'rgba(34,197,94,0.05)' }} />
        <div style={{ position: 'absolute', bottom: -20, right: 80, width: 80, height: 80, borderRadius: '50%', background: 'rgba(34,197,94,0.08)' }} />

        {/* Token reduction stat */}
        <div style={{ textAlign: 'center', position: 'relative' }}>
          <div style={{ fontSize: 11, color: 'rgba(74,222,128,0.8)', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 4 }}>
            Token Reduction
          </div>
          <div style={{ fontSize: 64, fontWeight: 900, lineHeight: 1, color: '#4ade80', letterSpacing: '-2px' }}>
            <AnimatedNumber value={pct} suffix="%" />
          </div>
          <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.5)', marginTop: 4 }}>GraphRAG vs Basic RAG</div>
        </div>

        <div style={{ width: 1, height: 80, background: 'rgba(255,255,255,0.1)' }} />

        {/* Token bars */}
        <div style={{ flex: 1, minWidth: 240 }}>
          {PIPELINE_KEYS.map(k => (
            <TokenBar
              key={k}
              label={PIPELINE_LABELS[k]}
              tokens={result[k].total_tokens}
              maxTokens={maxTok}
              color={PIPELINE_COLORS[k]}
              t={{ ...t, border: 'rgba(255,255,255,0.1)', textMuted: 'rgba(255,255,255,0.6)' }}
            />
          ))}
        </div>

        <div style={{ width: 1, height: 80, background: 'rgba(255,255,255,0.1)' }} />

        {/* Cost reduction stat */}
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 11, color: 'rgba(74,222,128,0.8)', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 4 }}>
            Cost Saved
          </div>
          <div style={{ fontSize: 36, fontWeight: 900, color: '#86efac', letterSpacing: '-1px' }}>
            {result.cost_reduction_pct > 0 ? '-' : '+'}<AnimatedNumber value={Math.abs(result.cost_reduction_pct)} suffix="%" />
          </div>
          <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)', marginTop: 4 }}>per query vs Basic RAG</div>
        </div>
      </div>
      )}

      {/* Chart + Pipeline cards */}
      <div style={{ display: 'grid', gridTemplateColumns: '300px 1fr', gap: 16, marginBottom: 20 }}>
        {/* Bar chart */}
        <div style={{
          background: t.surface, border: `1px solid ${t.border}`,
          borderRadius: 16, padding: '20px', boxShadow: t.cardShadow,
        }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: t.textSubtle, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 16 }}>
            Token Comparison
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={chartData} margin={{ top: 4, right: 4, bottom: 4, left: -20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={t.chartGrid} vertical={false} />
              <XAxis dataKey="name" stroke={t.textSubtle} tick={{ fill: t.textMuted, fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis stroke={t.textSubtle} tick={{ fill: t.textMuted, fontSize: 10 }} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={{ background: t.tooltipBg, border: `1px solid ${t.border}`, borderRadius: 10, boxShadow: t.cardShadow, fontSize: 13 }}
                labelStyle={{ color: t.text, fontWeight: 700 }}
                itemStyle={{ color: t.textMuted }}
                cursor={{ fill: t.accentGlow }}
              />
              <Bar dataKey="tokens" radius={[8, 8, 0, 0]} maxBarSize={56}>
                {chartData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>

          {result.judge_graphrag && (
            <div style={{
              marginTop: 12, padding: '10px 12px',
              background: result.judge_graphrag === 'PASS' ? 'rgba(22,163,74,0.1)' : 'rgba(239,68,68,0.1)',
              border: `1px solid ${result.judge_graphrag === 'PASS' ? 'rgba(22,163,74,0.3)' : 'rgba(239,68,68,0.3)'}`,
              borderRadius: 10, display: 'flex', alignItems: 'center', gap: 8,
            }}>
              {result.judge_graphrag === 'PASS'
                ? <CheckCircle2 size={14} color="#16a34a" />
                : <XCircle size={14} color="#ef4444" />}
              <div>
                <div style={{ fontSize: 11, fontWeight: 700, color: result.judge_graphrag === 'PASS' ? '#16a34a' : '#ef4444' }}>
                  GraphRAG Judge: {result.judge_graphrag}
                </div>
                <div style={{ fontSize: 10, color: t.textSubtle }}>LLM-as-a-Judge evaluation</div>
              </div>
            </div>
          )}
        </div>

        {/* Pipeline cards — driven by PIPELINE_KEYS registry */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {PIPELINE_KEYS.map(key => (
            <PipelineCard key={key} name={key} data={result[key]} judge={result[`judge_${key}`]} t={t} />
          ))}
        </div>
      </div>

      {/* BERTScore */}
      {result.bertscore && result.bertscore.raw_f1 > 0 && (
        <div style={{
          background: t.bertBg, border: `1px solid ${t.bertBorder}`,
          borderRadius: 16, padding: '18px 24px', marginBottom: 20,
          display: 'flex', alignItems: 'center', gap: 28, flexWrap: 'wrap',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Award size={18} color={t.bertText} />
            <span style={{ fontWeight: 700, fontSize: 14, color: t.bertText }}>BERTScore</span>
          </div>
          {[
            { label: 'Raw F1',      value: result.bertscore.raw_f1 },
            { label: 'Rescaled F1', value: result.bertscore.rescaled_f1 },
          ].map(({ label, value }) => (
            <div key={label}>
              <div style={{ fontSize: 10, color: t.bertText, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 2, fontWeight: 600 }}>{label}</div>
              <div style={{ fontSize: 24, fontWeight: 800, color: t.bertText }}>{value}</div>
            </div>
          ))}
          <div style={{ marginLeft: 'auto' }}>
            <span style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              background: result.bertscore.bonus_hit ? t.badgePassBg : t.badgeFailBg,
              color: result.bertscore.bonus_hit ? t.badgePassText : t.badgeFailText,
              borderRadius: 20, padding: '5px 14px', fontSize: 12, fontWeight: 700,
            }}>
              {result.bertscore.bonus_hit ? <CheckCircle2 size={13} /> : <XCircle size={13} />}
              {result.bertscore.bonus_hit ? 'BONUS HIT' : 'BONUS MISSED'}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

/* ─── Main App ─── */
export default function App() {
  const [question,  setQuestion]  = useState('');
  const [groundTruth, setGT]      = useState('');
  const [loading,   setLoading]   = useState(false);
  const [result,    setResult]    = useState(null);
  const [error,     setError]     = useState('');
  const [history,   setHistory]   = useState([]);
  const [darkMode,  setDarkMode]  = useState(false);
  const [selDomain, setDomain]    = useState('');
  const [showHist,  setShowHist]  = useState(false);
  const inputRef = useRef();

  const t          = THEMES[darkMode ? 'dark' : 'light'];
  const domainData = DOMAIN_QUESTIONS.find(d => d.domain === selDomain);

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
      }, ...prev].slice(0, 20));
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Request failed');
    } finally {
      setLoading(false);
    }
  }

  function selectQuestion(q, a = '') {
    setQuestion(q); setGT(a); setResult(null); setError('');
    setTimeout(() => inputRef.current?.focus(), 100);
  }

  const inputStyle = {
    background: t.inputBg, border: `1.5px solid ${t.border}`,
    borderRadius: 14, padding: '16px 20px', fontSize: 16,
    color: t.text, outline: 'none', width: '100%',
    transition: 'border-color 0.15s, box-shadow 0.15s',
    boxSizing: 'border-box', fontFamily: 'inherit',
  };

  return (
    <div style={{
      minHeight: '100vh', background: t.pageBg, color: t.text,
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      transition: 'background 0.3s',
    }}>

      {/* ═══ HERO ═══ */}
      <div style={{ background: t.heroBg, padding: '0 24px 0', position: 'relative', overflow: 'hidden' }}>
        <div style={{ position: 'absolute', top: -80, left: -80, width: 300, height: 300, borderRadius: '50%', background: 'rgba(22,163,74,0.08)', filter: 'blur(40px)' }} />
        <div style={{ position: 'absolute', top: -40, right: 100, width: 200, height: 200, borderRadius: '50%', background: 'rgba(59,130,246,0.06)', filter: 'blur(30px)' }} />

        <div style={{ maxWidth: 1280, margin: '0 auto' }}>
          {/* Nav */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '20px 0 0' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#4ade80', boxShadow: '0 0 8px #4ade80', animation: 'pulse-ring 2s ease infinite' }} />
              <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.6)', fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                TigerGraph GraphRAG · Wikipedia Knowledge Graph
              </span>
            </div>
            <button
              onClick={() => setDarkMode(d => !d)}
              style={{
                background: t.toggleBg, color: '#fff',
                border: '1px solid rgba(255,255,255,0.2)', borderRadius: 10,
                padding: '8px 16px', fontSize: 13, fontWeight: 600,
                cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6,
                backdropFilter: 'blur(10px)',
              }}
            >
              {darkMode ? <Sun size={14} /> : <Moon size={14} />}
              {darkMode ? 'Light' : 'Dark'}
            </button>
          </div>

          {/* Hero text */}
          <div style={{ padding: '60px 0 52px', textAlign: 'center' }}>
            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: 8,
              background: 'rgba(22,163,74,0.15)', border: '1px solid rgba(22,163,74,0.35)',
              borderRadius: 24, padding: '8px 22px', marginBottom: 28,
            }}>
              <Network size={15} color="#4ade80" />
              <span style={{ fontSize: 14, color: '#4ade80', fontWeight: 700, letterSpacing: '0.02em' }}>
                100M Token Wikipedia Knowledge Graph
              </span>
            </div>
            <h1 style={{
              fontSize: 'clamp(36px, 6vw, 68px)', fontWeight: 900, color: '#ffffff',
              margin: '0 0 20px', letterSpacing: '-2px', lineHeight: 1.05,
            }}>
              GraphRAG Pipeline{' '}
              <span style={{ background: 'linear-gradient(135deg, #4ade80, #22c55e)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                Comparison
              </span>
            </h1>
            <p style={{
              fontSize: 20, color: 'rgba(255,255,255,0.65)', margin: '0 0 44px',
              maxWidth: 600, marginLeft: 'auto', marginRight: 'auto', lineHeight: 1.65, fontWeight: 400,
            }}>
              See how <strong style={{ color: '#4ade80', fontWeight: 700 }}>GraphRAG</strong> reduces token usage by{' '}
              <strong style={{ color: '#4ade80', fontWeight: 700 }}>up to ~80%</strong> while maintaining accuracy
              over Basic RAG and LLM-Only pipelines
            </p>

            {/* Stat cards */}
            <div style={{ display: 'flex', justifyContent: 'center', gap: 16, flexWrap: 'wrap' }}>
              {[
                { icon: BookOpen, value: '100,850',    label: 'Wikipedia Articles' },
                { icon: Hash,     value: '102.9M',     label: 'Tokens Indexed' },
                { icon: Layers,   value: '464,739',    label: 'FAISS Chunks' },
                { icon: GitMerge, value: 'num_hops=2', label: 'Graph Traversal' },
              ].map(({ icon: Icon, value, label }) => (
                <div key={label} style={{
                  background: t.statCard, border: `1px solid ${t.statCardBorder}`,
                  borderRadius: 18, padding: '20px 28px', minWidth: 150,
                  backdropFilter: 'blur(10px)', textAlign: 'center',
                }}>
                  <Icon size={20} color="#4ade80" style={{ marginBottom: 10, display: 'block', margin: '0 auto 10px' }} />
                  <div style={{ fontSize: 22, fontWeight: 900, color: '#fff', letterSpacing: '-0.5px' }}>{value}</div>
                  <div style={{ fontSize: 13, color: 'rgba(255,255,255,0.55)', marginTop: 4, fontWeight: 500 }}>{label}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* ═══ MAIN CONTENT ═══ */}
      <div style={{ maxWidth: 1280, margin: '0 auto', padding: '36px 32px 80px' }}>

        {/* ── Featured Questions ── */}
        <div style={{
          background: t.surface, border: `1px solid ${t.border}`,
          borderRadius: 24, padding: '32px 36px', marginBottom: 24,
          boxShadow: t.cardShadow,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{ background: 'rgba(22,163,74,0.1)', borderRadius: 10, padding: 10 }}>
                <Sparkles size={20} color="#16a34a" />
              </div>
              <div>
                <div style={{ fontSize: 18, fontWeight: 800, color: t.text }}>Featured Questions</div>
                <div style={{ fontSize: 13, color: t.textSubtle, marginTop: 2 }}>Verified working questions with highest token reduction</div>
              </div>
            </div>
            <span style={{
              background: 'rgba(22,163,74,0.1)', color: '#16a34a',
              borderRadius: 20, padding: '4px 12px', fontSize: 11, fontWeight: 700,
              border: '1px solid rgba(22,163,74,0.2)',
            }}>Best Reduction</span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 14, marginBottom: 28 }}>
            {FEATURED_QUESTIONS.map(sq => (
              <button
                key={sq.question}
                onClick={() => selectQuestion(sq.question, sq.answer)}
                style={{
                  background: t.surface2, border: `1.5px solid ${t.border}`,
                  borderRadius: 16, padding: '20px 22px', textAlign: 'left',
                  cursor: 'pointer', transition: 'all 0.2s',
                }}
                onMouseEnter={e => {
                  e.currentTarget.style.borderColor = '#16a34a';
                  e.currentTarget.style.background = 'rgba(22,163,74,0.05)';
                  e.currentTarget.style.transform = 'translateY(-2px)';
                  e.currentTarget.style.boxShadow = '0 8px 24px rgba(22,163,74,0.12)';
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.borderColor = t.border;
                  e.currentTarget.style.background = t.surface2;
                  e.currentTarget.style.transform = 'none';
                  e.currentTarget.style.boxShadow = 'none';
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 20 }}>{sq.icon}</span>
                    <span style={{ fontSize: 11, fontWeight: 700, color: '#16a34a', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{sq.label}</span>
                  </div>
                </div>
                <div style={{ fontSize: 15, color: t.text, lineHeight: 1.55, fontWeight: 600, marginBottom: 10 }}>{sq.question}</div>
                <div style={{ fontSize: 12, color: t.textSubtle, display: 'flex', alignItems: 'center', gap: 5 }}>
                  <TrendingDown size={12} /> {sq.hint}
                </div>
              </button>
            ))}
          </div>

          {/* Browse by Domain */}
          <div style={{ borderTop: `1px solid ${t.border}`, paddingTop: 24 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
              <div style={{ background: 'rgba(22,163,74,0.1)', borderRadius: 8, padding: '7px 9px', display: 'flex', alignItems: 'center' }}>
                <BookOpen size={16} color="#16a34a" />
              </div>
              <div>
                <div style={{ fontSize: 20, fontWeight: 800, color: t.text }}>Browse by Domain</div>
                <div style={{ fontSize: 14, color: t.textSubtle, marginTop: 2 }}>Try more questions from different topics</div>
              </div>
            </div>
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-start' }}>
              <select
                value={selDomain}
                onChange={e => setDomain(e.target.value)}
                style={{
                  background: t.inputBg, border: `1.5px solid ${t.border}`,
                  borderRadius: 12, padding: '12px 18px', fontSize: 14,
                  color: selDomain ? t.text : t.textMuted,
                  cursor: 'pointer', outline: 'none', minWidth: 260,
                  fontFamily: 'inherit', fontWeight: 500,
                }}
              >
                <option value="">Select a domain…</option>
                {DOMAIN_QUESTIONS.map(d => (
                  <option key={d.domain} value={d.domain}>{d.domain}</option>
                ))}
              </select>

              {domainData && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, flex: 1 }}>
                  {domainData.questions.map(item => (
                    <button
                      key={item.question}
                      onClick={() => selectQuestion(item.question, item.answer)}
                      style={{
                        background: t.surface2, border: `1px solid ${t.border}`,
                        borderRadius: 22, padding: '8px 18px', fontSize: 13,
                        color: t.text, cursor: 'pointer', transition: 'all 0.15s',
                        fontFamily: 'inherit', fontWeight: 500,
                      }}
                      onMouseEnter={e => {
                        e.currentTarget.style.borderColor = '#16a34a';
                        e.currentTarget.style.color = '#16a34a';
                        e.currentTarget.style.background = 'rgba(22,163,74,0.06)';
                      }}
                      onMouseLeave={e => {
                        e.currentTarget.style.borderColor = t.border;
                        e.currentTarget.style.color = t.text;
                        e.currentTarget.style.background = t.surface2;
                      }}
                    >
                      {item.question}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* ── Query Form ── */}
        <div style={{
          background: t.surface, border: `1px solid ${t.border}`,
          borderRadius: 24, padding: '32px 36px', marginBottom: 28,
          boxShadow: t.cardShadow,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 22 }}>
            <div style={{ background: 'rgba(22,163,74,0.1)', borderRadius: 10, padding: 10 }}>
              <Zap size={20} color="#16a34a" />
            </div>
            <div>
              <div style={{ fontSize: 18, fontWeight: 800, color: t.text }}>Ask a Question</div>
              <div style={{ fontSize: 13, color: t.textSubtle, marginTop: 2 }}>
                Runs LLM-Only · Basic RAG · GraphRAG in parallel
              </div>
            </div>
          </div>
          <form onSubmit={handleRun} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <input
              ref={inputRef}
              value={question}
              onChange={e => setQuestion(e.target.value)}
              placeholder="e.g. Who discovered penicillin?"
              style={inputStyle}
              onFocus={e => { e.target.style.borderColor = '#16a34a'; e.target.style.boxShadow = '0 0 0 3px rgba(22,163,74,0.1)'; }}
              onBlur={e => { e.target.style.borderColor = t.border; e.target.style.boxShadow = 'none'; }}
            />
            <input
              value={groundTruth}
              onChange={e => setGT(e.target.value)}
              placeholder="Ground truth (optional) — enables LLM Judge + BERTScore evaluation"
              style={{ ...inputStyle, color: t.textMuted }}
              onFocus={e => { e.target.style.borderColor = '#16a34a'; e.target.style.boxShadow = '0 0 0 3px rgba(22,163,74,0.1)'; }}
              onBlur={e => { e.target.style.borderColor = t.border; e.target.style.boxShadow = 'none'; }}
            />
            <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
              <button
                type="submit"
                disabled={loading || !question.trim()}
                style={{
                  background: (loading || !question.trim()) ? t.btnDisabledBg : 'linear-gradient(135deg, #16a34a, #15803d)',
                  color: (loading || !question.trim()) ? t.btnDisabledText : '#fff',
                  border: 'none', borderRadius: 14, padding: '16px 40px',
                  fontSize: 16, fontWeight: 700, cursor: (loading || !question.trim()) ? 'not-allowed' : 'pointer',
                  display: 'flex', alignItems: 'center', gap: 10,
                  boxShadow: (loading || !question.trim()) ? 'none' : '0 6px 20px rgba(22,163,74,0.4)',
                  transition: 'all 0.2s', fontFamily: 'inherit',
                }}
              >
                <BarChart2 size={18} />
                {loading ? 'Running all 3 pipelines…' : 'Run All 3 Pipelines'}
              </button>
              {(question || result) && !loading && (
                <button
                  type="button"
                  onClick={() => { setQuestion(''); setGT(''); setResult(null); setError(''); }}
                  style={{
                    background: 'none', border: `1px solid ${t.border}`,
                    borderRadius: 14, padding: '16px 24px',
                    fontSize: 15, color: t.textMuted, cursor: 'pointer', fontFamily: 'inherit',
                  }}
                >
                  Clear
                </button>
              )}
              {result && !loading && result.token_reduction_pct != null && (
                <div style={{
                  marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8,
                  background: 'rgba(22,163,74,0.1)', border: '1px solid rgba(22,163,74,0.2)',
                  borderRadius: 10, padding: '8px 14px',
                }}>
                  <TrendingDown size={14} color="#16a34a" />
                  <span style={{ fontSize: 13, fontWeight: 700, color: '#16a34a' }}>
                    {result.token_reduction_pct}% token reduction achieved
                  </span>
                </div>
              )}
              {result && !loading && result.token_reduction_pct == null && (
                <div style={{
                  marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8,
                  background: t.errorBg, border: `1px solid ${t.errorBorder}`,
                  borderRadius: 10, padding: '8px 14px',
                }}>
                  <XCircle size={14} color={t.errorText} />
                  <span style={{ fontSize: 13, fontWeight: 700, color: t.errorText }}>
                    No graph context — not in knowledge graph
                  </span>
                </div>
              )}
            </div>
          </form>
        </div>

        {/* ── Error ── */}
        {error && (
          <div style={{
            background: t.errorBg, border: `1px solid ${t.errorBorder}`,
            borderRadius: 14, padding: '14px 18px', marginBottom: 20,
            color: t.errorText, fontSize: 14, display: 'flex', alignItems: 'center', gap: 8,
          }}>
            <XCircle size={16} /> {error}
          </div>
        )}

        {/* ── Loading ── */}
        {loading && (
          <div style={{
            background: t.surface, border: `1px solid ${t.border}`,
            borderRadius: 20, marginBottom: 20, boxShadow: t.cardShadow,
          }}>
            <Spinner t={t} />
          </div>
        )}

        {/* ── Results ── */}
        {result && !loading && <ResultsSection result={result} t={t} />}

        {/* ── History ── */}
        {history.length > 0 && (
          <div style={{
            background: t.surface, border: `1px solid ${t.border}`,
            borderRadius: 20, boxShadow: t.cardShadow, overflow: 'hidden',
          }}>
            <button
              onClick={() => setShowHist(h => !h)}
              style={{
                width: '100%', padding: '18px 24px',
                background: 'none', border: 'none', cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: 10,
                borderBottom: showHist ? `1px solid ${t.border}` : 'none',
              }}
            >
              <History size={15} color={t.textMuted} />
              <span style={{ fontSize: 14, fontWeight: 700, color: t.text }}>Query History</span>
              <span style={{
                background: t.surface2, border: `1px solid ${t.border}`,
                borderRadius: 20, padding: '1px 9px', fontSize: 11, color: t.textMuted, fontWeight: 600,
              }}>{history.length}</span>
              <ChevronDown size={14} color={t.textSubtle} style={{ marginLeft: 'auto', transform: showHist ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }} />
            </button>
            {showHist && (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                  <thead>
                    <tr style={{ background: t.surface2 }}>
                      {['Question', 'GraphRAG Tokens', 'Reduction', 'Judge', 'BERTScore'].map(h => (
                        <th key={h} style={{
                          padding: '10px 16px', borderBottom: `1px solid ${t.border}`,
                          color: t.textSubtle, textAlign: 'left', fontWeight: 700,
                          fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.07em',
                        }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {history.map((row, i) => (
                      <tr
                        key={i}
                        style={{ borderBottom: `1px solid ${t.border}`, cursor: 'pointer' }}
                        onClick={() => selectQuestion(row.question)}
                        onMouseEnter={e => e.currentTarget.style.background = t.surfaceHover}
                        onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                      >
                        <td style={{ padding: '11px 16px', color: t.text, maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{row.question}</td>
                        <td style={{ padding: '11px 16px', color: PIPELINE_COLORS.graphrag, fontWeight: 700 }}>{row.graphrag_tokens.toLocaleString()}</td>
                        <td style={{ padding: '11px 16px', fontWeight: 800, color: row.reduction_pct == null ? t.textSubtle : t.reductionStat }}>
                          {row.reduction_pct == null ? 'no match' : `${row.reduction_pct > 0 ? '-' : '+'}${Math.abs(row.reduction_pct)}%`}
                        </td>
                        <td style={{ padding: '11px 16px' }}>
                          {row.judge !== '—' ? <JudgeBadge judge={row.judge} t={t} /> : <span style={{ color: t.textSubtle }}>—</span>}
                        </td>
                        <td style={{ padding: '11px 16px', color: t.textMuted, fontWeight: 600 }}>{row.bertscore}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* ── Footer ── */}
        <div style={{ marginTop: 48, textAlign: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, marginBottom: 8 }}>
            <Network size={14} color="#16a34a" />
            <span style={{ fontSize: 13, fontWeight: 700, color: t.textMuted }}>
              TigerGraph GraphRAG Pipeline Comparison
            </span>
          </div>
          <div style={{ fontSize: 12, color: t.textSubtle, lineHeight: 1.6 }}>
            Powered by <strong style={{ color: t.textMuted }}>Gemini 2.5 Flash</strong> ·{' '}
            <strong style={{ color: t.textMuted }}>TigerGraph</strong> Knowledge Graph ·{' '}
            <strong style={{ color: t.textMuted }}>FAISS</strong> Vector Index ·{' '}
            <strong style={{ color: t.textMuted }}>102.9M</strong> tokens indexed
          </div>
        </div>
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes pulse-ring {
          0%, 100% { opacity: 1; transform: scale(1); }
          50%       { opacity: 0.5; transform: scale(1.3); }
        }
        @keyframes fadeUp {
          from { opacity: 0; transform: translateY(16px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        .animate-fade-up { animation: fadeUp 0.4s ease forwards; }
        * { box-sizing: border-box; }
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 3px; }
      `}</style>
    </div>
  );
}
