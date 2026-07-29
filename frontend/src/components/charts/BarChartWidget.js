import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { theme as tokens } from '../../theme';

const defaultData = [
  { name: 'Mon', value: 20 },
  { name: 'Tue', value: 35 },
  { name: 'Wed', value: 45 },
  { name: 'Thu', value: 30 },
  { name: 'Fri', value: 55 },
  { name: 'Sat', value: 15 },
  { name: 'Sun', value: 10 },
];

const BarChartWidget = ({ data = defaultData, minHeight = "200px", color = tokens.color?.['accent-primary'] || '#0071e3', label }) => {
  return (
    <div style={{ width: '100%', height: '100%', minHeight, display: 'flex', flexDirection: 'column' }}>
      {label && <div style={{ fontSize: tokens.typography?.small?.fontSize, color: tokens.color?.['muted-500'], marginBottom: tokens.spacing?.sm }}>{label}</div>}
      <div style={{ flexGrow: 1 }}>
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
    </div>
  );
};

export default BarChartWidget;
