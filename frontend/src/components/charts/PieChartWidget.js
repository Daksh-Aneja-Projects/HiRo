import React from 'react';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { theme as tokens } from '../../theme';
import ChartEmptyState from './ChartEmptyState';

const COLORS = [
  tokens.color?.['accent-primary'] || '#0071e3',
  tokens.color?.success || '#34c759',
  tokens.color?.warning || '#ff9f0a',
  tokens.color?.danger || '#ff3b30',
  '#a28bfe',
  '#f368e0'
];

// No fake fallback series: an omitted/empty `data` renders the empty state,
// never a hardcoded demo distribution.
const PieChartWidget = ({ data = [], minHeight = "200px", label }) => {
  return (
    <div style={{ width: '100%', height: '100%', minHeight, display: 'flex', flexDirection: 'column' }}>
      {label && <div style={{ fontSize: tokens.typography?.small?.fontSize, color: tokens.color?.['muted-500'], marginBottom: tokens.spacing?.sm }}>{label}</div>}
      {(!data || data.length === 0) ? <ChartEmptyState /> : (
        <div style={{ flexGrow: 1 }}>
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data}
                cx="50%"
                cy="50%"
                innerRadius={60}
                outerRadius={80}
                paddingAngle={5}
                dataKey="value"
              >
                {data.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} stroke="none" />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{ backgroundColor: tokens.color?.['panel-800'] || '#fff', borderRadius: tokens.border?.radius?.card || '8px', border: `1px solid ${tokens.color?.['border-600'] || '#e5e5e5'}`, boxShadow: tokens.shadow?.sm }}
                itemStyle={{ color: tokens.color?.['text-100'] || '#000' }}
              />
              <Legend verticalAlign="bottom" height={36} wrapperStyle={{ fontSize: '12px', color: tokens.color?.['muted-500'] || '#888' }}/>
            </PieChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
};

export default PieChartWidget;
