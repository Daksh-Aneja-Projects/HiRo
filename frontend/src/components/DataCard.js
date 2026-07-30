// DataCard — Linear-style surface. Two modes:
//  • stat:  <DataCard title value unit icon color subtitle />
//  • content/chart: <DataCard title isChart minHeight>{node}</DataCard>
import React, { memo, useMemo } from 'react';
import { theme as tokens } from '../theme';

const DataCard = memo(({ title, value, unit, color, icon, subtitle, isChart, minHeight, children }) => {
    const accent = color || tokens.color?.['accent-primary'];
    // Stat mode (value present): children is the header icon (backward compatible).
    // Content/chart mode (no value): children is the body.
    const isStat = value != null;
    const iconNode = icon || (isStat ? children : null);
    const bodyNode = isStat ? null : children;

    const s = useMemo(() => ({
        card: {
            background: tokens.color?.['panel-800'],
            border: '1px solid var(--border-subtle)',
            borderRadius: tokens.border?.radius?.card,
            padding: '16px 18px',
            display: 'flex',
            flexDirection: 'column',
            gap: 12,
            height: '100%',
            minHeight: minHeight || undefined,
            boxSizing: 'border-box',
            transition: 'border-color 0.18s ease, box-shadow 0.18s ease',
        },
        header: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 },
        title: { fontSize: 12.5, fontWeight: 500, color: tokens.color?.['muted-500'], margin: 0, letterSpacing: '-0.005em' },
        iconWrap: { display: 'grid', placeItems: 'center', width: 26, height: 26, borderRadius: 7, background: 'rgba(255,255,255,0.04)', color: accent, flexShrink: 0 },
        value: { fontSize: 26, fontWeight: 640, letterSpacing: '-0.02em', color: color || tokens.color?.['text-100'], lineHeight: 1, margin: 0, fontVariantNumeric: 'tabular-nums' },
        unit: { fontSize: 13, color: tokens.color?.['muted-500'], fontWeight: 500 },
        subtitle: { fontSize: 12, color: tokens.color?.['muted-600'], marginTop: 2 },
        body: { flexGrow: 1, minHeight: 0 },
    }), [accent, color, minHeight]);

    return (
        <div style={s.card} className="data-card">
            <div style={s.header}>
                <h4 style={s.title}>{title}</h4>
                {iconNode && <span style={s.iconWrap}>{iconNode}</span>}
            </div>

            {isStat ? (
                <div>
                    <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
                        <p style={s.value}>{value}</p>
                        {unit && <span style={s.unit}>{unit}</span>}
                    </div>
                    {subtitle && <div style={s.subtitle}>{subtitle}</div>}
                </div>
            ) : (
                <div style={s.body}>{bodyNode}</div>
            )}

            <style>{`.data-card:hover { border-color: var(--border-strong); box-shadow: var(--shadow-md); }`}</style>
        </div>
    );
});

DataCard.displayName = 'DataCard';
export default DataCard;
