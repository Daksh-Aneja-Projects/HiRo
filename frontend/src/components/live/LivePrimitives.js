// Live UI primitives: count-up numbers and animated meters driven by rAF.
// Used across portals so "live, not static" visuals share one implementation.
import React, { useEffect, useRef, useState } from 'react';
import { theme as tokens } from '../../theme';
import { getCurrentMetrics } from '../../config/api';

// Rolling live series for "trend" charts that have no historical endpoint.
// Polls the real psutil-backed telemetry and appends timestamped points, so the
// resulting chart is genuinely live rather than a static snapshot.
// `key` is a field on getCurrentMetrics() -> { cpu_load, memory_load, agent_activity }.
export function useMetricSeries(key, { intervalMs = 3000, maxPoints = 24, scale = 1 } = {}) {
  const [series, setSeries] = useState([]);
  useEffect(() => {
    let alive = true;
    const label = () => new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const tick = () => getCurrentMetrics()
      .then((r) => {
        if (!alive || !r?.data) return;
        const v = (Number(r.data[key]) || 0) * scale;
        setSeries((prev) => [...prev, { name: label(), value: Math.round(v * 10) / 10 }].slice(-maxPoints));
      })
      .catch(() => {});
    tick();
    const id = setInterval(tick, intervalMs);
    return () => { alive = false; clearInterval(id); };
  }, [key, intervalMs, maxPoints, scale]);
  return series;
}

export const prefersReducedMotion = () =>
  typeof window !== 'undefined' && window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// Animate a number from its previous value to `value` on change.
export function useCountUp(value, { duration = 900, decimals = 0 } = {}) {
  const [display, setDisplay] = useState(Number(value) || 0);
  const fromRef = useRef(Number(value) || 0);
  const rafRef = useRef(null);
  const startRef = useRef(null);

  useEffect(() => {
    const target = Number(value) || 0;
    const from = fromRef.current;
    if (prefersReducedMotion() || from === target) {
      fromRef.current = target;
      setDisplay(target);
      return;
    }
    startRef.current = null;
    const tick = (ts) => {
      if (startRef.current == null) startRef.current = ts;
      const p = Math.min(1, (ts - startRef.current) / duration);
      const eased = 1 - Math.pow(1 - p, 3); // easeOutCubic
      setDisplay(from + (target - from) * eased);
      if (p < 1) rafRef.current = requestAnimationFrame(tick);
      else fromRef.current = target;
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => rafRef.current && cancelAnimationFrame(rafRef.current);
  }, [value, duration]);

  const factor = Math.pow(10, decimals);
  return Math.round(display * factor) / factor;
}

// Number that counts up, with optional prefix/suffix and formatting.
export const CountUp = ({ value, decimals = 0, prefix = '', suffix = '', style }) => {
  const n = useCountUp(value, { decimals });
  const formatted = decimals > 0 ? n.toFixed(decimals) : Math.round(n).toLocaleString();
  return <span style={style}>{prefix}{formatted}{suffix}</span>;
};

// Horizontal meter that eases to `pct` (0..100).
export const LiveMeter = ({ pct = 0, color, height = 6, label }) => {
  const width = useCountUp(Math.max(0, Math.min(100, pct)), { decimals: 1 });
  const c = color || tokens.color?.['accent-primary'] || '#5e6ad2';
  return (
    <div style={{ width: '100%' }}>
      {label && (
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5,
          fontSize: 11.5, color: 'var(--text-tertiary)' }}>
          <span>{label}</span><span style={{ color: 'var(--text-secondary)' }}>{width.toFixed(0)}%</span>
        </div>
      )}
      <div style={{ height, borderRadius: 999, background: 'rgba(255,255,255,0.06)', overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${width}%`, borderRadius: 999,
          background: `linear-gradient(90deg, ${c}, ${tokens.color?.['accent-2'] || '#3fb9e5'})`,
          transition: 'none', boxShadow: `0 0 12px ${c}66` }} />
      </div>
    </div>
  );
};

// A compact live sparkline that pushes a new point on each `value` change.
export const Sparkline = ({ value, width = 120, height = 32, color, maxPoints = 40 }) => {
  const [points, setPoints] = useState([]);
  useEffect(() => {
    setPoints((prev) => [...prev, Number(value) || 0].slice(-maxPoints));
  }, [value, maxPoints]);
  const c = color || tokens.color?.['accent-2'] || '#3fb9e5';
  if (points.length < 2) return <svg width={width} height={height} />;
  const max = Math.max(...points, 1), min = Math.min(...points, 0);
  const range = max - min || 1;
  const step = width / (maxPoints - 1);
  const d = points
    .map((p, i) => `${i === 0 ? 'M' : 'L'} ${i * step} ${height - ((p - min) / range) * height}`)
    .join(' ');
  return (
    <svg width={width} height={height} style={{ display: 'block' }}>
      <path d={d} fill="none" stroke={c} strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
};
