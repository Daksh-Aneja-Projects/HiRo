// /frontend/src/components/ChartPlaceholder.js - For elegant, well-aligned chart areas

import React, { useMemo } from 'react';
import { theme as tokens } from '../theme';
import { BarChart3 } from 'lucide-react';

const ChartPlaceholder = ({ label, minHeight = '200px' }) => {
    const style = useMemo(() => ({
        minHeight: minHeight,
        background: tokens.color['panel-700'],
        border: `1px dashed ${tokens.color['border-600']}`,
        borderRadius: tokens.border.radius.chip,
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        color: tokens.color['muted-500'],
        fontSize: tokens.typography.small.fontSize,
        textAlign: 'center',
        marginTop: tokens.spacing.md,
        marginBottom: tokens.spacing.md,
    }), [minHeight]);

    return (
        <div style={style}>
            <BarChart3 size={24} style={{ marginBottom: tokens.spacing.xs, color: tokens.color['accent'] }} />
            <span>{label}</span>
            <span style={{ marginTop: tokens.spacing.xs, fontWeight: tokens.typography.h2.fontWeight, color: tokens.color['accent'] }}>[Live Chart Data Visualization]</span>
        </div>
    );
};

export default ChartPlaceholder;