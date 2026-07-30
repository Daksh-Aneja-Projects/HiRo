import React from 'react';
import { Inbox } from 'lucide-react';
import { theme as tokens } from '../../theme';

// Shared "no data yet" state for the chart widgets — shown instead of ever
// falling back to fake demo numbers when the real series is empty.
const ChartEmptyState = ({ message = 'No data yet' }) => (
  <div style={{
    flexGrow: 1, display: 'flex', flexDirection: 'column', alignItems: 'center',
    justifyContent: 'center', gap: 8, color: tokens.color?.['muted-600'] || '#666',
  }}>
    <Inbox size={22} strokeWidth={1.5} />
    <span style={{ fontSize: tokens.typography?.small?.fontSize || '12px' }}>{message}</span>
  </div>
);

export default ChartEmptyState;
