import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { theme as tokens } from '../../theme';
import ChartEmptyState from './ChartEmptyState';

// No fake fallback series: an omitted/empty `data` renders the empty state,
// never a hardcoded demo trend.
const BarChartWidget = ({ data = [], minHeight = "200px", color = tokens.color?.['accent-primary'] || '#0071e3', label }) => {
  return (
    // `height` must be DEFINITE (not 100%) or recharts' ResponsiveContainer
    // resolves against an auto-height parent and grows without bound.
    <div style={{ width: '100%', height: minHeight, minHeight, display: 'flex', flexDirection: 'column' }}>
      {label && <div style={{ fontSize: tokens.typography?.small?.fontSize, color: tokens.color?.['muted-500'], marginBottom: tokens.spacing?.sm }}>{label}</div>}
      {(!data || data.length === 0) ? <ChartEmptyState /> : (
        <div style={{ flexGrow: 1, minHeight: 0 }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={tokens.color?.['border-600'] || '#e5e5e5'} vertical={false} />
              <XAxis dataKey="name" tick={{ fill: tokens.color?.['muted-500'] || '#888', fontSize: 12 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: tokens.color?.['muted-500'] || '#888', fontSize: 12 }} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={{ backgroundColor: tokens.color?.['panel-800'] || '#fff', borderRadius: tokens.border?.radius?.card || '8px', border: `1px solid ${tokens.color?.['border-600'] || '#e5e5e5'}`, boxShadow: tokens.shadow?.sm }}
                itemStyle={{ color: tokens.color?.['text-100'] || '#000' }}
                cursor={{ fill: tokens.color?.['border-600'] || '#f5f5f5' }}
              />
              <Bar dataKey="value" fill={color} radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
};

export default BarChartWidget;
