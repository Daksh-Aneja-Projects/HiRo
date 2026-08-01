// NeuralMap - HiRo's Brain OS view: the whole organization as one living,
// free-flow graph. Department hubs are pinned to a band; agents, requests and
// systems breathe above them; the knowledge core sits at the center of it all.
// Three lenses: Free flow (the map), Brain (the knowledge core), Hierarchy
// (the chain of command). Everything on screen comes from live endpoints.
import React, { memo, useCallback, useMemo, useState } from 'react';
import ForceGraph, { VB } from '../components/neural/ForceGraph';
import useNeuralData from '../components/neural/useNeuralData';
import useCountUp from '../components/neural/useCountUp';
import DossierDrawer from '../components/neural/DossierDrawer';
import BrainView from '../components/neural/BrainView';
import HierarchyView from '../components/neural/HierarchyView';
import IngestBar from '../components/neural/IngestBar';
import { useAgentWebsocket } from '../hooks/useAgentWebsocket';
import '../components/neural/neural.css';

const MODES = [
    { key: 'map', label: 'Free flow' },
    { key: 'brain', label: 'Brain' },
    { key: 'hierarchy', label: 'Hierarchy' },
];

// Live-strip numbers ease toward their targets instead of hard-swapping.
const Count = ({ v }) => <>{useCountUp(v)}</>;

const NeuralMap = memo(() => {
    const { world, raw, error, loading, refresh } = useNeuralData();
    const { telemetryMetrics } = useAgentWebsocket();
    const [mode, setMode] = useState('map');
    const [selected, setSelected] = useState(null);
    const [focus, setFocus] = useState(null);
    const [camIndex, setCamIndex] = useState(-1); // -1 = full map

    // Each telemetry frame from the live WebSocket pulses the agent nodes.
    const pulseTs = useMemo(() => (telemetryMetrics ? Date.now() : 0), [telemetryMetrics]);

    const hubs = useMemo(() => (world?.hubs || []), [world]);

    const flyTo = useCallback((index) => {
        setCamIndex(index);
        if (index < 0) {
            setFocus({ x: VB.W / 2, y: VB.H / 2, zoom: 1, ts: Date.now() });
        } else {
            const hub = hubs[index];
            if (hub) setFocus({ x: hub.x, y: VB.H * 0.44, zoom: 1.4, ts: Date.now() });
        }
    }, [hubs]);

    const onNodeClick = useCallback((node) => {
        setSelected(node);
        if (node.type === 'department') {
            const i = hubs.findIndex((h) => `dept:${h.name}` === node.id);
            if (i >= 0) {
                setCamIndex(i);
                // shock: the cluster pops outward as the camera flies in.
                setFocus({ x: hubs[i].x, y: VB.H * 0.44, zoom: 1.4, ts: Date.now(), shock: hubs[i].name });
            }
        }
    }, [hubs]);

    const counts = world?.counts;

    return (
        <div style={ui.page}>
            {/* HUD, top-left: the instrument's nameplate */}
            <div style={ui.hud}>
                <div className="mono" style={ui.eyebrow}>{'// KNOWLEDGE CORE'}</div>
                <div className="mono" style={ui.title}>
                    NEURAL MAP<span className="neural-cursor">_</span>
                </div>
                <div style={ui.modeRow} role="tablist" aria-label="Map lens">
                    {MODES.map((m) => (
                        <button
                            key={m.key}
                            role="tab"
                            aria-selected={mode === m.key}
                            onClick={() => { setMode(m.key); setSelected(null); }}
                            className="mono"
                            style={{ ...ui.modePill, ...(mode === m.key ? ui.modePillActive : null) }}
                        >
                            {m.label}
                        </button>
                    ))}
                </div>
            </div>

            {/* The canvas area */}
            <div style={ui.canvas}>
                {loading && (
                    <div style={ui.centerNote}>
                        <span className="mono" style={{ letterSpacing: '0.12em', fontSize: 11 }}>ASSEMBLING THE MAP…</span>
                    </div>
                )}
                {!loading && error && (
                    <div style={ui.centerNote}>
                        <p style={{ margin: '0 0 10px', fontSize: 13, color: 'var(--text-secondary)', maxWidth: 380, textAlign: 'center' }}>
                            The map could not load its live data. The backend did not answer.
                        </p>
                        <button onClick={refresh} style={ui.retry}>Try again</button>
                    </div>
                )}
                {!loading && !error && world && (
                    <>
                        {mode === 'map' && (
                            <ForceGraph
                                nodes={world.nodes}
                                links={world.links}
                                onNodeClick={onNodeClick}
                                focus={focus}
                                pulseTs={pulseTs}
                            />
                        )}
                        {mode === 'brain' && <BrainView world={world} raw={raw} onRefresh={refresh} />}
                        {mode === 'hierarchy' && <HierarchyView world={world} raw={raw} />}

                        {mode === 'map' && <IngestBar onIngested={refresh} />}

                        {selected && mode === 'map' && (
                            <DossierDrawer node={selected} onClose={() => setSelected(null)} />
                        )}

                        {/* Camera pill: fly department by department */}
                        {mode === 'map' && hubs.length > 0 && (
                            <div style={ui.camPill}>
                                <button
                                    onClick={() => flyTo(camIndex <= 0 ? hubs.length - 1 : camIndex - 1)}
                                    style={ui.camBtn} aria-label="Previous department"
                                >
                                    <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
                                        <path d="M8 2L4 6l4 4" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
                                    </svg>
                                </button>
                                <button onClick={() => flyTo(-1)} className="mono" style={ui.camLabel}>
                                    {camIndex < 0 ? 'FULL MAP' : (hubs[camIndex]?.name || '').toUpperCase()}
                                </button>
                                <button
                                    onClick={() => flyTo(camIndex >= hubs.length - 1 ? 0 : camIndex + 1)}
                                    style={ui.camBtn} aria-label="Next department"
                                >
                                    <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
                                        <path d="M4 2l4 4-4 4" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
                                    </svg>
                                </button>
                            </div>
                        )}

                        {/* Live strip, bottom-right */}
                        {counts && (
                            <div className="mono" style={ui.liveStrip} aria-hidden="true">
                                <span
                                    className="neural-live-dot"
                                    style={{
                                        width: 7, height: 7, borderRadius: 999, display: 'inline-block',
                                        background: 'var(--accent-success)',
                                    }}
                                />
                                <span>
                                    LIVE · <Count v={counts.departments} /> DEPARTMENTS · <Count v={counts.agents} /> AGENTS · <Count v={counts.commands} /> COMMANDS · <Count v={counts.docs} /> CHUNKS
                                    {counts.openCases != null && <> · <Count v={counts.openCases} /> OPEN CASES</>}
                                </span>
                            </div>
                        )}
                    </>
                )}
            </div>
        </div>
    );
});

const ui = {
    page: {
        position: 'relative', height: '100%', minHeight: 480, overflow: 'hidden',
        display: 'flex', flexDirection: 'column', background: 'var(--bg-main)',
    },
    hud: { position: 'absolute', top: 14, left: 18, zIndex: 20, pointerEvents: 'none' },
    eyebrow: { fontSize: 10, letterSpacing: '0.16em', color: '#fb923c', marginBottom: 3 },
    title: { fontSize: 17, fontWeight: 600, letterSpacing: '0.1em', color: 'var(--text-primary)' },
    modeRow: { display: 'flex', gap: 4, marginTop: 10, pointerEvents: 'auto' },
    modePill: {
        border: '1px solid var(--border-subtle)', background: 'color-mix(in srgb, var(--bg-surface) 85%, transparent)',
        color: 'var(--text-tertiary)', fontSize: 10.5, letterSpacing: '0.08em', textTransform: 'uppercase',
        padding: '5px 11px', borderRadius: 999, cursor: 'pointer',
    },
    modePillActive: { color: 'var(--accent-bright)', border: '1px solid rgba(124,130,255,0.5)', background: 'rgba(94,106,210,0.14)' },
    canvas: { position: 'relative', flexGrow: 1, minHeight: 0, overflow: 'hidden' },
    centerNote: {
        position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center', color: 'var(--text-tertiary)',
    },
    retry: {
        border: '1px solid var(--border-strong)', background: 'transparent', color: 'var(--text-secondary)',
        borderRadius: 8, padding: '7px 16px', fontSize: 12.5, cursor: 'pointer', fontFamily: 'inherit',
    },
    camPill: {
        position: 'absolute', bottom: 16, left: '50%', transform: 'translateX(-50%)', zIndex: 20,
        display: 'flex', alignItems: 'center', gap: 2, padding: 4, borderRadius: 999,
        background: 'color-mix(in srgb, var(--bg-surface-elevated) 90%, transparent)',
        backdropFilter: 'var(--glass-blur)', WebkitBackdropFilter: 'var(--glass-blur)',
        border: '1px solid var(--border-subtle)', boxShadow: 'var(--shadow-md)',
    },
    camBtn: {
        width: 26, height: 26, borderRadius: 999, border: 'none', background: 'transparent',
        color: 'var(--text-secondary)', cursor: 'pointer', display: 'grid', placeItems: 'center',
    },
    camLabel: {
        border: 'none', background: 'transparent', color: 'var(--text-primary)', cursor: 'pointer',
        fontSize: 10.5, letterSpacing: '0.1em', padding: '0 10px', minWidth: 120, textAlign: 'center',
    },
    liveStrip: {
        position: 'absolute', bottom: 16, right: 16, zIndex: 15, pointerEvents: 'none',
        display: 'flex', alignItems: 'flex-start', gap: 7, fontSize: 10, letterSpacing: '0.1em',
        color: 'var(--text-tertiary)', textTransform: 'uppercase',
        maxWidth: 'calc(50% - 130px)', textAlign: 'right', lineHeight: 1.7,
    },
};

NeuralMap.displayName = 'NeuralMap';
export default NeuralMap;
