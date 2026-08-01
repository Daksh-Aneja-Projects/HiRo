import React, { useId } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { theme as tokens } from '../../theme';
import ChartEmptyState from './ChartEmptyState';
import { prefersReducedMotion } from '../live/LivePrimitives';

// Axis labels never show raw enum-style ids; long names are truncated and the
// tooltip carries the full readable name.
const readable = (v) => String(v ?? '').replace(/_/g, ' ');
const tickText = (v) => {
  const s = readable(v);
  return s.length > 14 ? `${s.slice(0, 13)}…` : s;
};

// No fake fallback series: an omitted/empty `data` renders the empty state,
// never a hardcoded demo trend.
const BarChartWidget = ({ data = [], minHeight = "200px", color = tokens.color?.['accent-primary'] || '#0071e3', label }) => {
  const gradientId = `barFill-${useId()}`;
  const animate = !prefersReducedMotion();
  return (
    // `height` must be DEFINITE (not 100%) or recharts' ResponsiveContainer
    // resolves against an auto-height parent and grows without bound.
    <div style={{ width: '100%', height: minHeight, minHeight, display: 'flex', flexDirection: 'column' }}>
      {label && <div style={{ fontSize: tokens.typography?.small?.fontSize, color: tokens.color?.['muted-500'], marginBottom: tokens.spacing?.sm }}>{label}</div>}
      {(!data || data.length === 0) ? <ChartEmptyState /> : (
        <div style={{ flexGrow: 1, minHeight: 0 }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={color} stopOpacity={0.95} />
                  <stop offset="100%" stopColor={color} stopOpacity={0.4} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke={tokens.color?.['border-600'] || '#e5e5e5'} vertical={false} />
              <XAxis dataKey="name" tick={{ fill: tokens.color?.['muted-500'] || '#888', fontSize: 12 }} axisLine={false} tickLine={false}
                tickFormatter={tickText} interval="preserveStartEnd" />
              <YAxis tick={{ fill: tokens.color?.['muted-500'] || '#888', fontSize: 12 }} axisLine={false} tickLine={false} allowDecimals={false} />
              <Tooltip
                contentStyle={{ backgroundColor: tokens.color?.['panel-800'] || '#fff', borderRadius: tokens.border?.radius?.card || '8px', border: `1px solid ${tokens.color?.['border-600'] || '#e5e5e5'}`, boxShadow: tokens.shadow?.sm }}
                itemStyle={{ color: tokens.color?.['text-100'] || '#000' }}
                labelFormatter={readable}
                cursor={{ fill: 'rgba(255,255,255,0.05)' }}
              />
              {/* maxBarSize keeps one or two categories from rendering as giant
                  panel-wide slabs; bars always scale to the axis max. */}
              <Bar dataKey="value" fill={`url(#${gradientId})`} radius={[4, 4, 0, 0]} maxBarSize={44}
                isAnimationActive={animate} animationDuration={750} animationEasing="ease-out" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
};

export default BarChartWidget;
