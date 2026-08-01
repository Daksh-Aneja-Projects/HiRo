// HierarchyView - the org as a chain of command: the signed-in operator, the
// Orchestrator (HiRo's one assistant - the same one that answers on the
// Orchestrator Control screen), and every department with its live numbers.
// Flow lines are drawn by measuring the real card rectangles, so they stay
// attached at any width.
import React, { memo, useCallback, useLayoutEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import useCountUp from './useCountUp';
import './neural.css';

const RISK_COLOR = { LOW: 'var(--accent-success)', MEDIUM: 'var(--accent-warning)', HIGH: 'var(--accent-danger)' };

// The ring fills via count-up on mount, so health visibly "charges".
const HealthRing = ({ pct, color }) => {
    const shown = useCountUp(pct, 1100);
    const r = 17;
    const c = 2 * Math.PI * r;
    return (
        <svg width="44" height="44" viewBox="0 0 44 44" aria-hidden="true">
            <circle cx="22" cy="22" r={r} fill="none" stroke="var(--border-subtle)" strokeWidth="3.5" />
            <circle
                cx="22" cy="22" r={r} fill="none" stroke={color} strokeWidth="3.5"
                strokeDasharray={`${(shown / 100) * c} ${c}`} strokeLinecap="round"
                transform="rotate(-90 22 22)"
            />
            <text x="22" y="26" textAnchor="middle" style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10.5, fill: 'var(--text-primary)' }}>
                {shown}
            </text>
        </svg>
    );
};

const Headcount = ({ value }) => {
    const shown = useCountUp(value, 1100);
    return <>{shown.toLocaleString()}</>;
};

const HierarchyView = memo(({ world, raw }) => {
    const { user } = useAuth();
    const navigate = useNavigate();
    const containerRef = useRef(null);
    const operatorRef = useRef(null);
    const copilotRef = useRef(null);
    const deptRefs = useRef(new Map());
    const [lines, setLines] = useState([]);

    const depts = (world?.hubs || []).filter((h) => h.name !== 'Platform');
    const detail = raw?.wfp?.skill_gap_detail || [];
    const risks = raw?.wfp?.skill_gaps || {};
    const orch = raw?.orch;

    const measure = useCallback(() => {
        const box = containerRef.current;
        if (!box || !operatorRef.current || !copilotRef.current) return;
        const base = box.getBoundingClientRect();
        const rel = (el) => {
            const r = el.getBoundingClientRect();
            return { x: r.left - base.left + r.width / 2, top: r.top - base.top, bottom: r.bottom - base.top };
        };
        const op = rel(operatorRef.current);
        const co = rel(copilotRef.current);
        const next = [{ d: `M ${op.x} ${op.bottom} L ${co.x} ${co.top}` }];
        deptRefs.current.forEach((el) => {
            if (!el) return;
            const d = rel(el);
            const midY = co.bottom + (d.top - co.bottom) * 0.5;
            next.push({ d: `M ${co.x} ${co.bottom} C ${co.x} ${midY}, ${d.x} ${midY}, ${d.x} ${d.top}` });
        });
        setLines(next);
    }, []);

    useLayoutEffect(() => {
        measure();
        const box = containerRef.current;
        if (!box || typeof ResizeObserver === 'undefined') return undefined;
        const ro = new ResizeObserver(measure);
        ro.observe(box);
        return () => ro.disconnect();
    }, [measure, world]);

    return (
        <div style={ui.scroller}>
            <div ref={containerRef} style={ui.container}>
                <svg style={ui.linesSvg} aria-hidden="true">
                    {lines.map((l, i) => (
                        <path
                            key={i} d={l.d} fill="none"
                            stroke="rgba(139,147,248,0.4)" strokeWidth="1.2"
                            strokeDasharray="4 6" className="neural-link-animated"
                        />
                    ))}
                </svg>

                {/* Tier 1: the operator */}
                <div ref={operatorRef} className="neural-rise" style={{ ...ui.card, ...ui.operatorCard }}>
                    <span style={ui.avatar}>{(user?.full_name || user?.username || 'U').charAt(0).toUpperCase()}</span>
                    <div>
                        <div style={ui.cardTitle}>{user?.full_name || user?.username || 'Operator'}</div>
                        <div style={ui.cardSub}>Operator - every consequential action traces back to you</div>
                    </div>
                </div>

                {/* Tier 2: the Orchestrator (the product's one assistant) */}
                <div ref={copilotRef} className="neural-rise" style={{ ...ui.card, ...ui.copilotCard, animationDelay: '0.08s' }}>
                    <span style={ui.botTile} className="neural-live-dot" aria-hidden="true">
                        <svg width="20" height="20" viewBox="0 0 20 20">
                            <rect x="4" y="6" width="12" height="9" rx="2.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
                            <circle cx="8" cy="10.5" r="1.2" fill="currentColor" />
                            <circle cx="12" cy="10.5" r="1.2" fill="currentColor" />
                            <path d="M10 6V3.5M10 3.5h.01" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                        </svg>
                    </span>
                    <div style={{ minWidth: 0 }}>
                        <div style={ui.cardTitle}>The Orchestrator</div>
                        <div style={ui.cardSub}>
                            {orch ? `${orch.agents} agents ready - ${orch.message_bus_connected ? 'passing work over the bus' : 'answering directly, bus offline'}` : 'Agent registry unavailable'}
                        </div>
                    </div>
                    <button onClick={() => navigate('/ultimate-orchestrator')} style={ui.chatBtn}>
                        Ask the Orchestrator
                    </button>
                </div>

                {/* Tier 3: department cards with real health numbers */}
                <div style={ui.deptGrid}>
                    {depts.map((d, i) => {
                        const det = detail.find((x) => x.department === d.name);
                        const covered = det ? Math.round(((det.skills_covered || 0) / Math.max(1, det.skills_needed || 1)) * 100) : 0;
                        const risk = risks[d.name];
                        return (
                            <div
                                key={d.name}
                                ref={(el) => (el ? deptRefs.current.set(d.name, el) : deptRefs.current.delete(d.name))}
                                className="neural-rise"
                                style={{ ...ui.card, ...ui.deptCard, boxShadow: `inset 0 2px 0 ${d.color}`, animationDelay: `${0.12 + i * 0.04}s` }}
                            >
                                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                                    <div style={{ minWidth: 0 }}>
                                        <div style={{ ...ui.deptName, color: d.color }}>{d.name}</div>
                                        <div className="mono" style={ui.deptCount}>{det ? <Headcount value={det.headcount} /> : '-'}</div>
                                        <div style={ui.cardSub}>people</div>
                                    </div>
                                    <HealthRing pct={covered} color={d.color} />
                                </div>
                                <div style={ui.deptFoot}>
                                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
                                        <span className="neural-live-dot" style={{ width: 6, height: 6, borderRadius: 999, background: RISK_COLOR[risk] || 'var(--text-tertiary)', display: 'inline-block' }} />
                                        {risk ? `${risk.charAt(0)}${risk.slice(1).toLowerCase()} skill risk` : 'Risk unknown'}
                                    </span>
                                    <span>{det ? `${det.skills_covered} of ${det.skills_needed} skills` : ''}</span>
                                </div>
                            </div>
                        );
                    })}
                </div>
            </div>
        </div>
    );
});

const ui = {
    scroller: { position: 'absolute', inset: 0, overflowY: 'auto', overflowX: 'hidden' },
    container: {
        // space-evenly + a growing dept grid: the chart uses the whole
        // vertical space instead of stacking at the top with dead air below.
        position: 'relative', display: 'flex', flexDirection: 'column', alignItems: 'center',
        justifyContent: 'space-evenly', gap: 22, padding: '22px 22px 46px',
        minHeight: '100%', boxSizing: 'border-box',
    },
    linesSvg: { position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none' },
    card: {
        position: 'relative', zIndex: 1, background: 'var(--bg-surface)',
        border: '1px solid var(--border-subtle)', borderRadius: 12, boxShadow: 'var(--shadow-sm)',
    },
    operatorCard: { display: 'flex', alignItems: 'center', gap: 12, padding: '12px 18px' },
    copilotCard: { display: 'flex', alignItems: 'center', gap: 12, padding: '12px 18px', maxWidth: 'min(560px, 100%)' },
    avatar: {
        width: 34, height: 34, borderRadius: 9, display: 'grid', placeItems: 'center', flexShrink: 0,
        background: 'linear-gradient(135deg, #5e6ad2, #3fb9e5)', color: '#fff', fontSize: 14, fontWeight: 600,
    },
    botTile: {
        width: 34, height: 34, borderRadius: 9, display: 'grid', placeItems: 'center', flexShrink: 0,
        background: 'rgba(94,106,210,0.16)', color: 'var(--accent-bright)', border: '1px solid rgba(94,106,210,0.4)',
    },
    cardTitle: { fontSize: 13.5, fontWeight: 600, color: 'var(--text-primary)' },
    cardSub: { fontSize: 11.5, color: 'var(--text-tertiary)' },
    chatBtn: {
        marginLeft: 8, flexShrink: 0, border: 'none', borderRadius: 8, padding: '8px 13px',
        fontSize: 12, fontWeight: 600, background: 'var(--accent-primary)', color: '#fff',
        cursor: 'pointer', fontFamily: 'inherit',
    },
    deptGrid: {
        display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))',
        gap: 12, width: '100%', maxWidth: 1180, flexGrow: 1, alignContent: 'space-evenly',
    },
    deptCard: { padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 12, justifyContent: 'space-between' },
    deptName: {
        fontFamily: "'JetBrains Mono', monospace", fontSize: 10, letterSpacing: '0.1em',
        textTransform: 'uppercase', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
    },
    deptCount: { fontSize: 19, fontWeight: 600, color: 'var(--text-primary)', marginTop: 2 },
    deptFoot: {
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8,
        fontSize: 11, color: 'var(--text-tertiary)', borderTop: '1px solid var(--border-subtle)', paddingTop: 8,
    },
};

HierarchyView.displayName = 'HierarchyView';
export default HierarchyView;
