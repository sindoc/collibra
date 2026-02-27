/**
 * Progress.jsx — React + SVG workflow progress bar for id-gen contracts
 * Renders the 7-step Collibra→ORM→SBVR pipeline with MathML/LaTeX support.
 *
 * Props:
 *   contractId   {string}  — c.contract.* ID
 *   step         {number}  — 0–7
 *   status       {string}  — DRAFT | PENDING_APPROVAL | APPROVED | ...
 *   topic        {string}  — topic/project label
 *   serverUrl    {string}  — id-gen server base URL (default: http://localhost:7331)
 *   onAdvance    {fn}      — callback when step advances
 *   onGenerate   {fn}      — callback when new ID is generated
 */

import React, { useState, useEffect, useCallback } from 'react';

// ── constants ─────────────────────────────────────────────────────────────────
const STEPS = [
  { key: 'INIT',       label: 'Init',       desc: 'Contract created' },
  { key: 'EXTRACT',    label: 'Extract',    desc: 'Collibra asset types enumerated' },
  { key: 'CLASSIFY',   label: 'Classify',   desc: 'Types → SBVR Concept Types' },
  { key: 'RELATE',     label: 'Relate',     desc: 'ORM binary fact types identified' },
  { key: 'CONSTRAIN',  label: 'Constrain',  desc: 'Uniqueness + mandatory constraints' },
  { key: 'VERBALIZE',  label: 'Verbalize',  desc: 'SBVR business rules expressed' },
  { key: 'ALIGN',      label: 'Align',      desc: 'Vocab cross-refs applied' },
  { key: 'CONTRACT',   label: 'Contract',   desc: 'Finalized, IDs tracked' },
];

const STATUS_COLORS = {
  DRAFT:            '#1f6feb',
  PENDING_APPROVAL: '#d29922',
  APPROVED:         '#238636',
  REJECTED:         '#da3633',
  ACTIVE:           '#3fb950',
  DEPRECATED:       '#8b949e',
};

const NS_COLORS = {
  c: { bg: '#0e4429', color: '#3fb950', border: '#238636', label: 'c.* Collibra (privileged)' },
  a: { bg: '#1f2d3d', color: '#79c0ff', border: '#1f6feb', label: 'a.* reserved-A' },
  b: { bg: '#2d1f3d', color: '#d2a8ff', border: '#8957e5', label: 'b.* reserved-B' },
};

// ── SVG progress bar ──────────────────────────────────────────────────────────
function SvgBar({ step, total = 7, width = 400, height = 20 }) {
  const pct  = Math.round((step / total) * 100);
  const fill = step < 3 ? '#1f6feb' : step < 6 ? '#d29922' : '#238636';
  const barW = (width * pct) / 100;

  return (
    <svg viewBox={`0 0 ${width} ${height}`} style={{ width: '100%', height }}>
      {/* Track */}
      <rect x={0} y={0} width={width} height={height} rx={height / 2} fill="#30363d" />
      {/* Fill */}
      <rect
        x={0} y={0} width={barW} height={height} rx={height / 2}
        fill={fill}
        style={{ transition: 'width 0.4s ease, fill 0.4s ease' }}
      />
      {/* Percentage text */}
      <text
        x={width / 2} y={height / 2 + 1}
        textAnchor="middle" dominantBaseline="middle"
        fill="#fff" fontSize={height * 0.6} fontFamily="monospace"
      >
        {pct}%
      </text>
      {/* Step markers */}
      {STEPS.map((_, i) => {
        const x = (width * i) / total;
        return (
          <circle
            key={i}
            cx={x} cy={height / 2} r={3}
            fill={i <= step ? fill : '#8b949e'}
            style={{ transition: 'fill 0.3s' }}
          />
        );
      })}
    </svg>
  );
}

// ── Step pipeline ─────────────────────────────────────────────────────────────
function StepPipeline({ step }) {
  return (
    <div style={{ display: 'flex', gap: 0, overflowX: 'auto', margin: '1rem 0' }}>
      {STEPS.map((s, i) => {
        const done   = i < step;
        const active = i === step;
        const dotColor = done ? '#3fb950' : active ? '#58a6ff' : '#30363d';
        const textColor = done ? '#3fb950' : active ? '#58a6ff' : '#8b949e';
        return (
          <div key={s.key} style={{ flex: 1, minWidth: 72, textAlign: 'center', position: 'relative' }}>
            {/* connector line */}
            {i < STEPS.length - 1 && (
              <div style={{
                position: 'absolute', top: 13, left: '50%', right: '-50%',
                height: 2, background: i < step ? '#3fb950' : '#30363d',
                transition: 'background 0.3s', zIndex: 0
              }} />
            )}
            {/* dot */}
            <div style={{
              width: 28, height: 28, borderRadius: '50%',
              background: dotColor, margin: '0 auto 4px',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: '0.65rem', color: '#fff', position: 'relative', zIndex: 1,
              boxShadow: active ? `0 0 0 4px ${dotColor}33` : 'none',
              transition: 'all 0.3s',
            }}>
              {done ? '✓' : i}
            </div>
            <div style={{ fontSize: '0.6rem', color: textColor, whiteSpace: 'nowrap' }}>
              {s.label}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── MathML progress equation ──────────────────────────────────────────────────
function ProgressEquation({ step }) {
  const pct = Math.round((step / 7) * 100);
  return (
    <div style={{
      background: '#0d1117', border: '1px solid #30363d', borderRadius: 6,
      padding: '0.75rem', margin: '0.75rem 0', fontSize: '0.85rem'
    }}>
      <div style={{ fontSize: '0.7rem', color: '#8b949e', marginBottom: 6 }}>
        Workflow progress equation
      </div>
      {/* MathML — rendered natively in browsers with MathML support */}
      <math xmlns="http://www.w3.org/1998/Math/MathML" display="inline">
        <mrow>
          <mi>progress</mi><mo>=</mo>
          <mfrac><mi>step</mi><mn>7</mn></mfrac>
          <mo>&#x00D7;</mo><mn>100</mn><mo>=</mo>
          <mfrac>
            <mrow><mn>{step}</mn><mo>&#x22C5;</mo><mn>100</mn></mrow>
            <mn>7</mn>
          </mfrac>
          <mo>&#x2248;</mo><mn>{pct}</mn><mo>%</mo>
        </mrow>
      </math>
      {/* LaTeX fallback string */}
      <div style={{ fontSize: '0.7rem', color: '#8b949e', marginTop: 6 }}>
        {'$$\\text{progress} = \\frac{' + step + ' \\times 100}{7} \\approx ' + pct + '\\%$$'}
      </div>
    </div>
  );
}

// ── Namespace chip ────────────────────────────────────────────────────────────
function NsChip({ ns }) {
  const s = NS_COLORS[ns] || NS_COLORS.c;
  return (
    <span style={{
      fontSize: '0.7rem', padding: '2px 10px', borderRadius: 12,
      background: s.bg, color: s.color, border: `1px solid ${s.border}`,
      cursor: 'default'
    }} title={s.label}>
      {s.label}
    </span>
  );
}

// ── Log panel ─────────────────────────────────────────────────────────────────
function LogPanel({ logs }) {
  return (
    <div style={{
      fontSize: '0.73rem', color: '#8b949e', marginTop: '0.75rem',
      maxHeight: 120, overflowY: 'auto',
      background: '#0d1117', borderRadius: 4, padding: '0.5rem'
    }}>
      {logs.map((l, i) => (
        <div key={i} style={{ borderBottom: '1px solid #30363d', padding: '2px 0' }}>
          <span style={{ color: '#58a6ff' }}>[{l.ts}]</span> {l.msg}
        </div>
      ))}
    </div>
  );
}

// ── Main Progress component ───────────────────────────────────────────────────
export function Progress({
  contractId: initialId = null,
  step: initialStep = 0,
  status: initialStatus = 'DRAFT',
  topic: initialTopic = '',
  serverUrl = 'http://localhost:7331',
  onAdvance,
  onGenerate,
}) {
  const [cid,    setCid]    = useState(initialId);
  const [step,   setStep]   = useState(initialStep);
  const [status, setStatus] = useState(initialStatus);
  const [topic,  setTopic]  = useState(initialTopic);
  const [ns,     setNs]     = useState('c');
  const [kind,   setKind]   = useState('DataContract');
  const [logs,   setLogs]   = useState([{ ts: 'init', msg: 'Dashboard ready' }]);
  const [eqExpr, setEqExpr] = useState('');
  const [eqMode, setEqMode] = useState('solve');
  const [eqResult, setEqResult] = useState('');

  const pct = Math.round((step / 7) * 100);

  const addLog = useCallback((msg) => {
    const ts = new Date().toISOString().slice(0, 19).replace('T', ' ');
    setLogs(l => [{ ts, msg }, ...l].slice(0, 40));
  }, []);

  // Update status when step changes
  useEffect(() => {
    const STATUS_MAP = ['DRAFT','DRAFT','DRAFT','DRAFT',
                        'PENDING_APPROVAL','PENDING_APPROVAL','PENDING_APPROVAL','APPROVED'];
    setStatus(STATUS_MAP[step] || 'DRAFT');
  }, [step]);

  // Generate ID
  const handleGenerate = useCallback(async () => {
    const t = topic || 'UnnamedProject';
    try {
      const r = await fetch(`${serverUrl}/api/id/gen`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic: t, kind, ns }),
      });
      if (r.ok) {
        const d = await r.json();
        setCid(d.id); setStep(0); setTopic(t);
        addLog(`Generated (server): ${d.id}`);
        onGenerate?.(d.id);
        return;
      }
    } catch (_) {}
    // Client fallback
    const uid = crypto.randomUUID?.() ||
      'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
        const r = Math.random()*16|0;
        return (c==='x'?r:(r&0x3|0x8)).toString(16);
      });
    const id = `${ns}.contract.${uid}`;
    setCid(id); setStep(0); setTopic(t);
    addLog(`Generated (client): ${id}`);
    onGenerate?.(id);
  }, [topic, kind, ns, serverUrl, addLog, onGenerate]);

  // Advance step
  const handleAdvance = useCallback(() => {
    if (!cid) { addLog('Generate an ID first'); return; }
    if (step >= 7) { addLog('Pipeline complete at step 7'); return; }
    const next = step + 1;
    setStep(next);
    addLog(`Step ${next}/7 — ${STEPS[next].key}: ${STEPS[next].desc}`);
    onAdvance?.(next, cid);
  }, [cid, step, addLog, onAdvance]);

  // Equation solver
  const handleSolveEq = useCallback(async () => {
    if (!eqExpr) return;
    try {
      const r = await fetch(`${serverUrl}/api/eq`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ expr: eqExpr, mode: eqMode }),
      });
      if (r.ok) { const d = await r.json(); setEqResult(JSON.stringify(d)); return; }
    } catch (_) {}
    // Client fallback
    try {
      // eslint-disable-next-line no-new-func
      const result = Function('"use strict"; let x=0; return (' + eqExpr + ')')();
      setEqResult(`Result: ${result}`);
    } catch (e) { setEqResult(`Error: ${e.message}`); }
  }, [eqExpr, eqMode, serverUrl]);

  const statusColor = STATUS_COLORS[status] || '#8b949e';

  const card = {
    background: '#161b22', border: '1px solid #30363d',
    borderRadius: 8, padding: '1.25rem', marginBottom: '1rem',
  };
  const btn = (primary) => ({
    fontFamily: 'monospace', fontSize: '0.78rem', padding: '6px 14px',
    borderRadius: 6, cursor: 'pointer', border: '1px solid',
    borderColor: primary ? '#238636' : '#30363d',
    background: primary ? '#238636' : '#161b22',
    color: primary ? '#fff' : '#e6edf3', transition: 'all 0.15s',
  });
  const input = {
    fontFamily: 'monospace', fontSize: '0.78rem', padding: '6px 10px',
    borderRadius: 6, border: '1px solid #30363d',
    background: '#0d1117', color: '#e6edf3',
  };
  const select_ = { ...input, minWidth: 180 };

  return (
    <div style={{ background: '#0d1117', color: '#e6edf3', fontFamily: "'SF Mono','Fira Code',monospace", padding: '1.5rem' }}>
      <h2 style={{ fontSize: '1.2rem', marginBottom: 4 }}>id-gen — Contract Workflow</h2>
      <p style={{ fontSize: '0.8rem', color: '#8b949e', marginBottom: '1.5rem' }}>
        Collibra · ORM · SBVR · 7-step pipeline
      </p>

      {/* Namespace registry */}
      <div style={card}>
        <strong style={{ fontSize: '0.85rem' }}>Namespace Registry</strong>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
          {['c','a','b'].map(n => <NsChip key={n} ns={n} />)}
        </div>
        <div style={{ fontSize: '0.72rem', color: '#8b949e', marginTop: 8 }}>
          Project = Topic → <code>c.topic.*</code> &nbsp;|&nbsp; Topic → Collibra case → <code>c.case.*</code>
        </div>
      </div>

      {/* Contract card */}
      <div style={card}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
          <div>
            <div style={{ fontWeight: 'bold', fontSize: '0.85rem' }}>
              {cid || 'c.contract.<uuid>'}
            </div>
            <div style={{ fontSize: '0.75rem', color: '#8b949e' }}>Topic: {topic || '—'}</div>
          </div>
          <span style={{
            fontSize: '0.7rem', padding: '2px 10px', borderRadius: 12,
            background: statusColor + '22', color: statusColor,
            border: `1px solid ${statusColor}55`
          }}>{status}</span>
        </div>

        {/* SVG bar */}
        <div style={{ marginBottom: 8 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.72rem', color: '#8b949e', marginBottom: 4 }}>
            <span>Step {step}/7 — {STEPS[step]?.key}</span>
            <span>{pct}%</span>
          </div>
          <SvgBar step={step} />
        </div>

        <StepPipeline step={step} />
        <ProgressEquation step={step} />
        <LogPanel logs={logs} />
      </div>

      {/* Controls */}
      <div style={card}>
        <strong style={{ fontSize: '0.85rem' }}>Controls</strong>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 12 }}>
          <select style={select_} value={kind} onChange={e => setKind(e.target.value)}>
            {['DataContract','UseCaseContract','ServiceContract','GovernanceContract'].map(k =>
              <option key={k} value={k}>{k}</option>
            )}
          </select>
          <select style={select_} value={ns} onChange={e => setNs(e.target.value)}>
            <option value="c">c.* — Collibra (privileged)</option>
            <option value="a">a.* — reserved-A</option>
            <option value="b">b.* — reserved-B</option>
          </select>
          <input
            style={{ ...input, minWidth: 200 }}
            type="text" placeholder="Project / Topic label…"
            value={topic} onChange={e => setTopic(e.target.value)}
          />
          <button style={btn(true)} onClick={handleGenerate}>Generate {ns}.contract.* ID</button>
          <button style={btn(false)} onClick={handleAdvance}>Advance Step →</button>
        </div>

        {/* Equation */}
        <div style={{ marginTop: 12 }}>
          <div style={{ fontSize: '0.7rem', color: '#8b949e', marginBottom: 6 }}>Equation solver</div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <input
              style={{ ...input, minWidth: 280 }}
              type="text" placeholder="e.g.  x**2 + 3*x + 2"
              value={eqExpr} onChange={e => setEqExpr(e.target.value)}
            />
            <select style={select_} value={eqMode} onChange={e => setEqMode(e.target.value)}>
              {['solve','latex','plot'].map(m => <option key={m} value={m}>{m}</option>)}
            </select>
            <button style={btn(false)} onClick={handleSolveEq}>Evaluate</button>
          </div>
          {eqResult && (
            <pre style={{ fontSize: '0.75rem', color: '#3fb950', marginTop: 6 }}>
              {eqResult}
            </pre>
          )}
        </div>
      </div>
    </div>
  );
}

export default Progress;
