// BrainView - the knowledge core up close: a particle sphere inside a thin
// containment ring, departments on a rotating dashed orbit in their brand
// colors, and a stats/search panel that opens when the sphere is clicked.
//
// Honesty rule: the knowledge endpoints (/api/knowledge/*) are still being
// built and may 404. When they do, the sphere is sized by what IS known (the
// live ingestion job count) and the panel says the core is being indexed -
// no fabricated numbers, ever.
import React, { memo, useState } from 'react';
import BrainParticles from './BrainParticles';
import IngestBar from './IngestBar';
import { askKnowledge, syncKnowledge } from '../../config/api';
import './neural.css';

const ORBIT_RX = 0.40; // fraction of stage width
const ORBIT_RY = 0.35; // fraction of stage height

const BrainView = memo(({ world, raw, onRefresh }) => {
    const [panelOpen, setPanelOpen] = useState(false);
    const [query, setQuery] = useState('');
    const [searching, setSearching] = useState(false);
    const [answer, setAnswer] = useState(null);
    const [syncing, setSyncing] = useState(false);
    const [syncNote, setSyncNote] = useState(null);

    const knowledge = raw?.knowledge;
    const ingestion = raw?.ingestion;
    const indexed = Boolean(knowledge);
    const docs = Number(knowledge?.documents ?? knowledge?.notes ?? ingestion?.total ?? 0);
    const pending = Number(ingestion?.pending ?? 0);
    const jobs = Array.isArray(ingestion?.jobs) ? ingestion.jobs : [];
    const depts = (world?.hubs || []).filter((h) => h.name !== 'Platform');

    const runSearch = async () => {
        const q = query.trim();
        if (!q) return;
        setSearching(true);
        setAnswer(null);
        try {
            const res = await askKnowledge(q);
            setAnswer({ ok: true, data: res.data });
        } catch (e) {
            setAnswer({
                ok: false,
                note: e?.response?.status === 404
                    ? 'Search is not available yet. The knowledge core is still being indexed.'
                    : 'The knowledge core could not answer right now.',
            });
        } finally {
            setSearching(false);
        }
    };

    const runSync = async () => {
        setSyncing(true);
        setSyncNote(null);
        try {
            await syncKnowledge();
            setSyncNote('Re-index started.');
            if (onRefresh) onRefresh();
        } catch (e) {
            setSyncNote(e?.response?.status === 404
                ? 'Re-indexing is not available yet.'
                : 'The re-index could not be started.');
        } finally {
            setSyncing(false);
        }
    };

    // The stage is a fixed logical space; everything positions in percent so
    // it holds together at any width without overlap.
    const sphereSize = 300;

    return (
        <div style={ui.wrap}>
            <div style={ui.stage}>
                <IngestBar onIngested={onRefresh} />
                {/* Rotating dashed orbit + brand-colored spokes and domains */}
                <svg viewBox="0 0 1000 640" style={ui.orbitSvg} aria-hidden="true" preserveAspectRatio="xMidYMid meet">
                    <g className="neural-halo-spin" style={{ transformOrigin: '500px 320px' }}>
                        <ellipse cx="500" cy="320" rx={1000 * ORBIT_RX} ry={640 * ORBIT_RY} fill="none" stroke="rgba(255,255,255,0.14)" strokeWidth="1" strokeDasharray="3 8" />
                    </g>
                    {depts.map((d, i) => {
                        const ang = (i / Math.max(1, depts.length)) * Math.PI * 2 - Math.PI / 2;
                        const x = 500 + Math.cos(ang) * 1000 * ORBIT_RX;
                        const y = 320 + Math.sin(ang) * 640 * ORBIT_RY;
                        const ex = 500 + Math.cos(ang) * (sphereSize * 0.5);
                        const ey = 320 + Math.sin(ang) * (sphereSize * 0.5);
                        return (
                            <g key={d.name}>
                                <line x1={ex} y1={ey} x2={x} y2={y} stroke={d.color} strokeWidth="1" strokeOpacity="0.35" strokeDasharray="2 6" />
                                <circle cx={x} cy={y} r="14" fill={`${d.color}1f`} stroke={d.color} strokeWidth="2" />
                                <text
                                    x={x} y={y + (Math.sin(ang) >= 0 ? 30 : -24)} textAnchor="middle"
                                    style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10.5, letterSpacing: '0.08em', fill: d.color, textTransform: 'uppercase' }}
                                >
                                    {d.name.length > 16 ? `${d.name.slice(0, 15)}…` : d.name}
                                </text>
                            </g>
                        );
                    })}
                </svg>

                {/* The sphere itself, with a thin containment ring. Clicking opens the panel. */}
                <button
                    onClick={() => setPanelOpen(true)}
                    style={ui.sphereBtn}
                    aria-label="Open knowledge core stats"
                >
                    <span style={ui.ring} aria-hidden="true" />
                    <BrainParticles size={sphereSize} density={Math.min(1.4, 0.4 + docs * 0.06)} />
                    <span className="mono" style={ui.sphereCaption}>
                        {indexed ? `${docs} ITEMS INDEXED` : `${docs} DOCUMENTS RECEIVED`}
                    </span>
                </button>

                {!indexed && (
                    <p style={ui.indexingNote}>
                        The knowledge core is being indexed. What you see is sized by the {docs} document{docs === 1 ? '' : 's'} the ingestion pipeline has actually received.
                    </p>
                )}
            </div>

            {panelOpen && (
                <aside className="neural-rise" style={ui.panel} aria-label="Knowledge core stats">
                    <div style={ui.panelHeader}>
                        <div className="mono" style={ui.eyebrow}>{'// KNOWLEDGE CORE'}</div>
                        <button onClick={() => setPanelOpen(false)} style={ui.close} aria-label="Close stats panel">
                            <svg width="13" height="13" viewBox="0 0 14 14" aria-hidden="true">
                                <path d="M2 2l10 10M12 2L2 12" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
                            </svg>
                        </button>
                    </div>
                    <div style={ui.panelScroll}>
                        <div style={ui.tileRow}>
                            <div style={ui.tile}>
                                <div className="mono" style={ui.tileValue}>{docs}</div>
                                <div style={ui.tileLabel}>{indexed ? 'Items' : 'Documents'}</div>
                            </div>
                            <div style={ui.tile}>
                                <div className="mono" style={ui.tileValue}>{pending}</div>
                                <div style={ui.tileLabel}>Waiting</div>
                            </div>
                            <div style={ui.tile}>
                                <div className="mono" style={ui.tileValue}>{indexed ? 'Live' : 'Indexing'}</div>
                                <div style={ui.tileLabel}>State</div>
                            </div>
                        </div>

                        <div style={ui.searchRow}>
                            <input
                                value={query}
                                onChange={(e) => setQuery(e.target.value)}
                                onKeyDown={(e) => { if (e.key === 'Enter') runSearch(); }}
                                placeholder="Ask the knowledge core anything"
                                style={ui.searchInput}
                                aria-label="Search the knowledge core"
                            />
                            <button onClick={runSearch} disabled={searching || !query.trim()} style={ui.searchBtn}>
                                {searching ? '…' : 'Ask'}
                            </button>
                        </div>
                        {answer && (
                            <div style={ui.answerCard}>
                                {answer.ok
                                    ? (answer.data?.answer || answer.data?.result || 'The knowledge core returned no text for that.')
                                    : answer.note}
                            </div>
                        )}

                        <div style={ui.sectionTitle}>Recently received</div>
                        {jobs.length === 0 && (
                            <div style={ui.answerCard}>Nothing has been fed to the knowledge core yet. Use the bar above to teach it something.</div>
                        )}
                        {jobs.slice(0, 6).map((j) => (
                            <div key={j.job_id} style={ui.jobRow}>
                                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{j.filename}</span>
                                <span style={{ color: j.status === 'INGESTED' ? 'var(--accent-success)' : 'var(--accent-warning)', flexShrink: 0, fontSize: 10.5 }}>
                                    {j.status === 'INGESTED' ? 'Stored' : String(j.status || '').toLowerCase()}
                                </span>
                            </div>
                        ))}

                        <button onClick={runSync} disabled={syncing} style={ui.syncBtn}>
                            {syncing ? 'Starting…' : 'Re-index everything'}
                        </button>
                        {syncNote && <div style={{ fontSize: 11.5, color: 'var(--text-tertiary)', marginTop: 6 }}>{syncNote}</div>}
                    </div>
                </aside>
            )}
        </div>
    );
});

const ui = {
    wrap: { position: 'absolute', inset: 0, display: 'flex', overflow: 'hidden' },
    stage: { position: 'relative', flexGrow: 1, minWidth: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' },
    orbitSvg: { position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none' },
    sphereBtn: {
        position: 'relative', border: 'none', background: 'transparent', cursor: 'pointer',
        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10, padding: 0,
    },
    ring: {
        position: 'absolute', top: -8, left: '50%', transform: 'translateX(-50%)',
        width: 316, height: 316, borderRadius: '50%', border: '1px solid rgba(251,146,60,0.35)',
        pointerEvents: 'none',
    },
    sphereCaption: { fontSize: 10.5, letterSpacing: '0.14em', color: '#fb923c' },
    indexingNote: {
        margin: '14px 24px 0', maxWidth: 440, textAlign: 'center',
        fontSize: 12.5, lineHeight: 1.5, color: 'var(--text-tertiary)',
    },
    panel: {
        width: 340, flexShrink: 0, margin: 12, display: 'flex', flexDirection: 'column', zIndex: 25,
        background: 'color-mix(in srgb, var(--bg-surface-elevated) 92%, transparent)',
        backdropFilter: 'var(--glass-blur)', WebkitBackdropFilter: 'var(--glass-blur)',
        border: '1px solid var(--border-strong)', borderRadius: 14, boxShadow: 'var(--shadow-lg)',
    },
    panelHeader: {
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '14px 16px 10px', borderBottom: '1px solid var(--border-subtle)', flexShrink: 0,
    },
    eyebrow: { fontSize: 10, letterSpacing: '0.14em', color: '#fb923c' },
    close: {
        border: '1px solid var(--border-subtle)', background: 'transparent', color: 'var(--text-secondary)',
        width: 26, height: 26, borderRadius: 8, cursor: 'pointer', display: 'grid', placeItems: 'center',
    },
    panelScroll: { padding: '12px 16px 16px', overflowY: 'auto', minHeight: 0 },
    tileRow: { display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginBottom: 12 },
    tile: { padding: '10px 8px', borderRadius: 10, textAlign: 'center', background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border-subtle)' },
    tileValue: { fontSize: 16, fontWeight: 600, color: 'var(--text-primary)' },
    tileLabel: { fontSize: 10, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.06em' },
    searchRow: { display: 'flex', gap: 6, marginBottom: 8 },
    searchInput: {
        flexGrow: 1, minWidth: 0, padding: '8px 10px', borderRadius: 8, fontSize: 12.5,
        border: '1px solid var(--border-subtle)', background: 'var(--bg-input)', color: 'var(--text-primary)', outline: 'none', fontFamily: 'inherit',
    },
    searchBtn: {
        border: 'none', borderRadius: 8, padding: '8px 14px', fontSize: 12, fontWeight: 600,
        background: 'var(--accent-primary)', color: '#fff', cursor: 'pointer', fontFamily: 'inherit',
    },
    answerCard: {
        padding: '10px 12px', borderRadius: 10, fontSize: 12.5, lineHeight: 1.5, marginBottom: 8,
        background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border-subtle)', color: 'var(--text-secondary)',
    },
    sectionTitle: {
        margin: '12px 0 8px', fontFamily: "'JetBrains Mono', monospace", fontSize: 10,
        letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--text-tertiary)',
    },
    jobRow: {
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10,
        padding: '7px 2px', fontSize: 12, color: 'var(--text-secondary)', borderBottom: '1px solid var(--border-subtle)',
    },
    syncBtn: {
        marginTop: 12, width: '100%', border: '1px solid var(--border-strong)', borderRadius: 8,
        padding: '8px 0', fontSize: 12, fontWeight: 550, background: 'transparent',
        color: 'var(--text-secondary)', cursor: 'pointer', fontFamily: 'inherit',
    },
};

BrainView.displayName = 'BrainView';
export default BrainView;
