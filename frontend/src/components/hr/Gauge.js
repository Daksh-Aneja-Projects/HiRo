// Small animated SVG gauges shared by the new HR panels (engagement, headcount).
// Built here rather than in components/live because these two shapes (a signed
// -100..100 arc and a 0..100 ring) are specific to this build's panels.
import React from 'react';
import { theme as tokens } from '../../theme';
import { useCountUp } from '../live/LivePrimitives';

// Semicircle arc for a score that can be negative, e.g. eNPS (-100..100).
export const ArcGauge = ({ value, min = -100, max = 100, label, size = 180 }) => {
    const clamped = Math.max(min, Math.min(max, Number(value) || 0));
    const animated = useCountUp(clamped, { decimals: 1 });
    const pct = (animated - min) / (max - min);
    const w = size, h = size * 0.62, r = size / 2 - 14, cx = size / 2, cy = h - 4;
    const angle = Math.PI * (1 - pct);
    const x = cx + r * Math.cos(angle);
    const y = cy - r * Math.sin(angle);
    const arcPath = (fromPct, toPct) => {
        const a1 = Math.PI * (1 - fromPct), a2 = Math.PI * (1 - toPct);
        const x1 = cx + r * Math.cos(a1), y1 = cy - r * Math.sin(a1);
        const x2 = cx + r * Math.cos(a2), y2 = cy - r * Math.sin(a2);
        return `M ${x1} ${y1} A ${r} ${r} 0 0 1 ${x2} ${y2}`;
    };
    const good = clamped >= 0;
    const color = good ? tokens.color?.success : tokens.color?.danger;
    return (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
            <svg width={w} height={h + 10} viewBox={`0 0 ${w} ${h + 10}`}>
                <path d={arcPath(0, 1)} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth={12} strokeLinecap="round" />
                <path d={arcPath(0, Math.max(0.001, pct))} fill="none" stroke={color} strokeWidth={12} strokeLinecap="round"
                    style={{ filter: `drop-shadow(0 0 6px ${color}66)` }} />
                <circle cx={x} cy={y} r={5} fill={color} />
            </svg>
            <div style={{ fontSize: 28, fontWeight: 650, color, fontVariantNumeric: 'tabular-nums', marginTop: -18 }}>
                {clamped > 0 ? '+' : ''}{animated.toFixed(1)}
            </div>
            {label && <div style={{ fontSize: 12, color: tokens.color?.['muted-600'] }}>{label}</div>}
        </div>
    );
};

// Full ring for a 0..100 share, e.g. survey response rate.
export const RingGauge = ({ pct = 0, size = 120, color, label, sublabel }) => {
    const clamped = Math.max(0, Math.min(100, Number(pct) || 0));
    const animated = useCountUp(clamped, { decimals: 1 });
    const stroke = 11;
    const r = size / 2 - stroke;
    const c = 2 * Math.PI * r;
    const offset = c * (1 - animated / 100);
    const col = color || tokens.color?.['accent-primary'];
    return (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
            <div style={{ position: 'relative', width: size, height: size }}>
                <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
                    <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth={stroke} />
                    <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={col} strokeWidth={stroke}
                        strokeDasharray={c} strokeDashoffset={offset} strokeLinecap="round"
                        style={{ filter: `drop-shadow(0 0 6px ${col}66)` }} />
                </svg>
                <div style={{
                    position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
                    alignItems: 'center', justifyContent: 'center',
                }}>
                    <span style={{ fontSize: 20, fontWeight: 650, color: tokens.color?.['text-100'], fontVariantNumeric: 'tabular-nums' }}>
                        {animated.toFixed(1)}%
                    </span>
                </div>
            </div>
            {label && <div style={{ fontSize: 12, color: tokens.color?.['muted-600'], textAlign: 'center' }}>{label}</div>}
            {sublabel && <div style={{ fontSize: 11, color: tokens.color?.['muted-600'], textAlign: 'center' }}>{sublabel}</div>}
        </div>
    );
};
