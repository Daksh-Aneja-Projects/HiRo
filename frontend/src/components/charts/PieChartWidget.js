import React from 'react';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { theme as tokens } from '../../theme';
import ChartEmptyState from './ChartEmptyState';
import { CountUp, prefersReducedMotion } from '../live/LivePrimitives';

const COLORS = [
  tokens.color?.['accent-primary'] || '#0071e3',
  tokens.color?.success || '#34c759',
  tokens.color?.warning || '#ff9f0a',
  tokens.color?.danger || '#ff3b30',
  '#a28bfe',
  '#f368e0'
];

const readable = (v) => String(v ?? '').replace(/_/g, ' ');

// No fake fallback series: an omitted/empty `data` renders the empty state,
// never a hardcoded demo distribution.
const PieChartWidget = ({ data = [], minHeight = "200px", label }) => {
  const total = (data || []).reduce((n, d) => n + (Number(d?.value) || 0), 0);
  return (
    // `height` must be DEFINITE (not 100%) or recharts' ResponsiveContainer
    // resolves against an auto-height parent and grows without bound.
    <div style={{ width: '100%', height: minHeight, minHeight, display: 'flex', flexDirection: 'column' }}>
      {label && <div style={{ fontSize: tokens.typography?.small?.fontSize, color: tokens.color?.['muted-500'], marginBottom: tokens.spacing?.sm }}>{label}</div>}
      {(!data || data.length === 0) ? <ChartEmptyState /> : (
        <div style={{ position: 'relative', flexGrow: 1, minHeight: 0 }}>
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data}
                cx="50%"
                cy="50%"
                innerRadius={60}
                outerRadius={80}
                paddingAngle={4}
                dataKey="value"
                isAnimationActive={!prefersReducedMotion()}
                animationDuration={800}
                animationEasing="ease-out"
              >
                {data.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} stroke="none" />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{ backgroundColor: tokens.color?.['panel-800'] || '#fff', borderRadius: tokens.border?.radius?.card || '8px', border: `1px solid ${tokens.color?.['border-600'] || '#e5e5e5'}`, boxShadow: tokens.shadow?.sm }}
                itemStyle={{ color: tokens.color?.['text-100'] || '#000' }}
              />
              <Legend verticalAlign="bottom" height={36} formatter={readable}
                wrapperStyle={{ fontSize: '12px', color: tokens.color?.['muted-500'] || '#888' }}/>
            </PieChart>
          </ResponsiveContainer>
          {/* Live total in the donut hole. The pie centre sits half the legend
              height above the container centre, hence the -18px correction. */}
          <div style={{
            position: 'absolute', top: '50%', left: '50%',
            transform: 'translate(-50%, calc(-50% - 18px))',
            textAlign: 'center', pointerEvents: 'none',
          }}>
            <div style={{ fontSize: 22, fontWeight: 640, letterSpacing: '-0.02em', color: tokens.color?.['text-100'], fontVariantNumeric: 'tabular-nums', lineHeight: 1.1 }}>
              <CountUp value={total} />
            </div>
            <div style={{ fontSize: 11, color: tokens.color?.['muted-600'] }}>total</div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PieChartWidget;
