// ForceGraph - hand-rolled SVG + rAF force engine (no dependency).
// React renders the SVG skeleton once per data identity; a rAF loop mutates
// transforms directly, so there is zero per-frame reconciliation.
//
// The two hard-won physics rules from the Brain OS recipe are honored here:
// 1. Springs adopt the seed geometry as their rest lengths (clamped), so the
//    band layout is never torn apart by default spring lengths.
// 2. Structural nodes (department hubs, the brain) are pinned; children stay
//    fully live around them. Dragging a pinned node unpins it.
import React, { memo, useEffect, useMemo, useRef } from 'react';
import './neural.css';

export const VB = { W: 1560, H: 680 };

const LINK_STYLE = {
    'hub-hub': { stroke: 'var(--text-tertiary)', width: 1, opacity: 0.35, dash: '3 7' },
    'hub-brain': { stroke: 'rgba(251,146,60,0.45)', width: 1.2, opacity: 0.8, dash: '2 6', animated: true },
    'agent-hub': { stroke: 'rgba(139,147,248,0.4)', width: 1.2, opacity: 0.85 },
    'task-agent': { stroke: 'rgba(242,201,76,0.42)', width: 1, opacity: 0.8, dash: '2 5', animated: true },
    'task-hub': { stroke: 'rgba(242,201,76,0.35)', width: 1, opacity: 0.75, dash: '2 5', animated: true },
    'agent-comms': { stroke: 'rgba(234,179,8,0.5)', width: 1, opacity: 0.8, dash: '1 7', animated: true },
    'connector-hub': { stroke: 'rgba(63,185,229,0.42)', width: 1.1, opacity: 0.8, dash: '4 4', animated: true },
    'connector-agent': { stroke: 'rgba(63,185,229,0.38)', width: 1, opacity: 0.7, dash: '2 4', animated: true },
    // Workforce motes hold to their hub with the faintest possible thread.
    mote: { stroke: 'var(--text-tertiary)', width: 0.6, opacity: 0.14 },
};
const DEFAULT_LINK = { stroke: 'var(--text-tertiary)', width: 1, opacity: 0.3 };

const SPRING_K = 0.018;
const REPULSE = 950;
const ANCHOR_K = 0.014;
const DAMPING = 0.86;
const ALPHA_FLOOR = 0.05; // never zero - the graph must keep breathing
const REST_MIN = 48;
const REST_MAX = 420;

const truncate = (s, n = 18) => (s && s.length > n ? `${s.slice(0, n - 1)}…` : s || '');

const ForceGraph = memo(({ nodes, links, onNodeClick, focus, pulseTs, reduced: reducedProp }) => {
    const svgRef = useRef(null);
    const nodeEls = useRef(new Map());
    const pulseEls = useRef(new Map()); // agent silhouettes, flashed on telemetry
    const linkEls = useRef(new Map());
    const labelEls = useRef(new Map());
    const simRef = useRef({ nodes: [], links: [], byId: new Map(), alpha: 1 });
    const vbRef = useRef({ x: 0, y: 0, w: VB.W, h: VB.H });
    const rafRef = useRef(0);
    const focusRafRef = useRef(0);
    const hoverRef = useRef(null);
    // The owner of the motion decision is the page (see useMotionPreference),
    // because the OS preference alone froze this map for anyone whose machine
    // has animations off, including on battery saver. Reading the media query
    // here as a fallback keeps the component usable on its own.
    const reduced = reducedProp !== undefined
        ? reducedProp
        : (typeof window !== 'undefined'
            && !!window.matchMedia
            && window.matchMedia('(prefers-reduced-motion: reduce)').matches);

    const dataKey = useMemo(() => nodes.map((n) => n.id).join('|'), [nodes]);

    // (Re)build the simulation state whenever the data identity changes.
    useEffect(() => {
        const simNodes = nodes.map((n) => ({
            ...n,
            x: n.seed.x, y: n.seed.y, vx: 0, vy: 0,
            homeX: n.seed.x, homeY: n.seed.y,
            phase: Math.random() * Math.PI * 2,
            dragging: false,
        }));
        const byId = new Map(simNodes.map((n) => [n.id, n]));
        const simLinks = links
            .filter((l) => byId.has(l.source) && byId.has(l.target))
            .map((l) => {
                const a = byId.get(l.source);
                const b = byId.get(l.target);
                // Rule 1: rest length = seed distance, clamped.
                const rest = Math.min(REST_MAX, Math.max(REST_MIN, Math.hypot(a.homeX - b.homeX, a.homeY - b.homeY)));
                return { ...l, a, b, rest };
            });
        simRef.current = { nodes: simNodes, links: simLinks, byId, alpha: 1 };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [dataKey]);

    // The rAF loop: physics tick + imperative transform application.
    useEffect(() => {
        const applyPositions = () => {
            const sim = simRef.current;
            sim.nodes.forEach((n) => {
                const el = nodeEls.current.get(n.id);
                if (el) el.setAttribute('transform', `translate(${n.x},${n.y})`);
            });
            sim.links.forEach((l, i) => {
                const el = linkEls.current.get(i);
                if (el) {
                    el.setAttribute('x1', l.a.x); el.setAttribute('y1', l.a.y);
                    el.setAttribute('x2', l.b.x); el.setAttribute('y2', l.b.y);
                }
            });
        };

        const tick = (t) => {
            const sim = simRef.current;
            sim.alpha = Math.max(ALPHA_FLOOR, sim.alpha * 0.995);
            const a = sim.alpha;
            const time = t * 0.001;

            sim.nodes.forEach((n) => {
                if (n.fixed || n.dragging) return;
                // Ambient drift: per-node phase-offset sinusoids at CONSTANT
                // amplitude. Scaling this by alpha was the "static map" bug:
                // at the 0.05 floor the drift was sub-pixel, so the loop ran
                // forever while nothing visibly moved.
                n.vx += Math.sin(time * 0.7 + n.phase) * 0.06;
                n.vy += Math.cos(time * 0.6 + n.phase * 1.3) * 0.06;
                // Home anchoring - never weaker than 30% strength, or the
                // constant drift walks nodes ~80px off their band.
                const aa = Math.max(a, 0.3);
                n.vx += (n.homeX - n.x) * ANCHOR_K * aa;
                n.vy += (n.homeY - n.y) * ANCHOR_K * aa;
            });

            // Short-range pairwise repulsion (~40 nodes, O(n^2) is nothing).
            for (let i = 0; i < sim.nodes.length; i++) {
                for (let j = i + 1; j < sim.nodes.length; j++) {
                    const p = sim.nodes[i]; const q = sim.nodes[j];
                    const dx = q.x - p.x; const dy = q.y - p.y;
                    const d2 = dx * dx + dy * dy;
                    if (d2 > 22500 || d2 < 0.01) continue; // only inside 150px
                    const d = Math.sqrt(d2);
                    const f = Math.min(2.5, (REPULSE / d2)) * a;
                    const fx = (dx / d) * f; const fy = (dy / d) * f;
                    if (!p.fixed && !p.dragging) { p.vx -= fx; p.vy -= fy; }
                    if (!q.fixed && !q.dragging) { q.vx += fx; q.vy += fy; }
                }
            }

            // Springs along links.
            sim.links.forEach((l) => {
                const dx = l.b.x - l.a.x; const dy = l.b.y - l.a.y;
                const d = Math.hypot(dx, dy) || 1;
                const f = (d - l.rest) * SPRING_K * a;
                const fx = (dx / d) * f; const fy = (dy / d) * f;
                if (!l.a.fixed && !l.a.dragging) { l.a.vx += fx; l.a.vy += fy; }
                if (!l.b.fixed && !l.b.dragging) { l.b.vx -= fx; l.b.vy -= fy; }
            });

            sim.nodes.forEach((n) => {
                if (n.fixed || n.dragging) return;
                n.vx *= DAMPING; n.vy *= DAMPING;
                n.x += n.vx; n.y += n.vy;
            });

            applyPositions();
            rafRef.current = requestAnimationFrame(tick);
        };

        if (reduced) {
            // One static frame: settle springs a little without looping.
            for (let k = 0; k < 60; k++) tickOnce(simRef.current);
            applyPositions();
            return undefined;
        }
        rafRef.current = requestAnimationFrame(tick);
        return () => cancelAnimationFrame(rafRef.current);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [dataKey, reduced]);

    // View application: viewBox + level-of-detail label opacity from zoom.
    const applyView = () => {
        const svg = svgRef.current;
        if (!svg) return;
        const vb = vbRef.current;
        svg.setAttribute('viewBox', `${vb.x} ${vb.y} ${vb.w} ${vb.h}`);
        const zoom = VB.W / vb.w;
        labelEls.current.forEach((el, id) => {
            const tier = el.getAttribute('data-tier');
            let op = 1;
            if (tier === 'agent') op = Math.max(0, Math.min(1, (zoom - 1.15) * 5));
            else if (tier === 'small') op = Math.max(0, Math.min(1, (zoom - 1.25) * 5));
            el.setAttribute('opacity', op);
        });
    };

    useEffect(() => { applyView(); });

    // Eased camera flight (cubic-out, ~650ms), retriggered via focus.ts.
    useEffect(() => {
        if (!focus || !focus.ts) return undefined;
        simRef.current.alpha = Math.max(simRef.current.alpha, 0.5);
        // Clicking a hub pulses its cluster: a radial shock through every
        // floating node of that department, decaying under normal damping.
        if (focus.shock && !reduced) {
            // Radial shock outward from the hub's actual position: the cluster
            // pops as the camera arrives, then settles under normal damping.
            const sx = focus.shockX ?? focus.x;
            const sy = focus.shockY ?? focus.y;
            simRef.current.nodes.forEach((n) => {
                if (n.dept !== focus.shock || n.fixed || n.dragging) return;
                n.vx += (n.x - sx) * 0.03;
                n.vy += (n.y - sy) * 0.025;
            });
            simRef.current.alpha = Math.max(simRef.current.alpha, 0.9);
        }
        const from = { ...vbRef.current };
        const w = VB.W / (focus.zoom || 1);
        const h = VB.H / (focus.zoom || 1);
        const to = { x: focus.x - w / 2, y: focus.y - h / 2, w, h };
        if (reduced) { vbRef.current = to; applyView(); return undefined; }
        const t0 = performance.now();
        const fly = (t) => {
            const p = Math.min(1, (t - t0) / 650);
            const e = 1 - Math.pow(1 - p, 3);
            vbRef.current = {
                x: from.x + (to.x - from.x) * e,
                y: from.y + (to.y - from.y) * e,
                w: from.w + (to.w - from.w) * e,
                h: from.h + (to.h - from.h) * e,
            };
            applyView();
            if (p < 1) focusRafRef.current = requestAnimationFrame(fly);
        };
        focusRafRef.current = requestAnimationFrame(fly);
        return () => cancelAnimationFrame(focusRafRef.current);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [focus]);

    // Telemetry tick: flash every agent silhouette. The class lives on an
    // inner group so the CSS transform never fights the rAF-positioned outer
    // group's translate.
    useEffect(() => {
        if (!pulseTs || reduced) return;
        pulseEls.current.forEach((el) => {
            el.classList.remove('neural-node-pulse');
            // Force a reflow so the animation retriggers on every tick.
            void el.getBoundingClientRect();
            el.classList.add('neural-node-pulse');
        });
    }, [pulseTs, reduced]);

    // ---- Interaction: node drag, pan, zoom ----
    const clientToVb = (cx, cy) => {
        const rect = svgRef.current.getBoundingClientRect();
        const vb = vbRef.current;
        return {
            x: vb.x + ((cx - rect.left) / rect.width) * vb.w,
            y: vb.y + ((cy - rect.top) / rect.height) * vb.h,
        };
    };

    const onPointerDown = (e) => {
        const svg = svgRef.current;
        if (!svg) return;
        const nodeG = e.target.closest && e.target.closest('[data-nodeid]');
        simRef.current.alpha = Math.max(simRef.current.alpha, 0.6);
        if (nodeG) {
            const node = simRef.current.byId.get(nodeG.getAttribute('data-nodeid'));
            if (!node) return;
            node.dragging = true;
            node.fixed = false; // drag unpins
            const move = (ev) => {
                const p = clientToVb(ev.clientX, ev.clientY);
                node.x = p.x; node.y = p.y; node.vx = 0; node.vy = 0;
                node.moved = true;
            };
            const up = () => {
                node.dragging = false;
                window.removeEventListener('pointermove', move);
                window.removeEventListener('pointerup', up);
            };
            window.addEventListener('pointermove', move);
            window.addEventListener('pointerup', up);
        } else {
            const start = { cx: e.clientX, cy: e.clientY, vb: { ...vbRef.current } };
            const rect = svg.getBoundingClientRect();
            const move = (ev) => {
                vbRef.current = {
                    ...start.vb,
                    x: start.vb.x - ((ev.clientX - start.cx) / rect.width) * start.vb.w,
                    y: start.vb.y - ((ev.clientY - start.cy) / rect.height) * start.vb.h,
                };
                applyView();
            };
            const up = () => {
                window.removeEventListener('pointermove', move);
                window.removeEventListener('pointerup', up);
            };
            window.addEventListener('pointermove', move);
            window.addEventListener('pointerup', up);
        }
    };

    const onWheel = (e) => {
        const vb = vbRef.current;
        const factor = e.deltaY > 0 ? 1.12 : 1 / 1.12;
        const newW = Math.min(VB.W * 2, Math.max(VB.W / 4, vb.w * factor));
        const scale = newW / vb.w;
        const p = clientToVb(e.clientX, e.clientY);
        vbRef.current = {
            w: newW,
            h: vb.h * scale,
            x: p.x - (p.x - vb.x) * scale,
            y: p.y - (p.y - vb.y) * scale,
        };
        applyView();
    };

    // ---- Hover isolation: dim non-neighbors, restore per-tier base styles ----
    const neighborSets = useMemo(() => {
        const map = new Map();
        nodes.forEach((n) => map.set(n.id, new Set([n.id])));
        links.forEach((l) => {
            if (map.has(l.source)) map.get(l.source).add(l.target);
            if (map.has(l.target)) map.get(l.target).add(l.source);
        });
        return map;
    }, [nodes, links]);

    const setHover = (id) => {
        hoverRef.current = id;
        const near = id ? neighborSets.get(id) : null;
        nodeEls.current.forEach((el, nid) => {
            el.setAttribute('opacity', !near || near.has(nid) ? 1 : 0.15);
        });
        simRef.current.links.forEach((l, i) => {
            const el = linkEls.current.get(i);
            if (!el) return;
            const base = LINK_STYLE[l.tier] || DEFAULT_LINK;
            const lit = !id || l.source === id || l.target === id;
            // Restore the per-tier base opacity, never a hardcoded gray.
            el.setAttribute('stroke-opacity', lit ? base.opacity : 0.05);
        });
    };

    return (
        <svg
            ref={svgRef}
            viewBox={`0 0 ${VB.W} ${VB.H}`}
            style={{ width: '100%', height: '100%', display: 'block', touchAction: 'none' }}
            onPointerDown={onPointerDown}
            onWheel={onWheel}
            role="img"
            aria-label="Neural map of departments, agents, tasks and systems"
        >
            <g>
                {links.map((l, i) => {
                    const st = LINK_STYLE[l.tier] || DEFAULT_LINK;
                    return (
                        <line
                            key={`${l.source}-${l.target}-${i}`}
                            ref={(el) => (el ? linkEls.current.set(i, el) : linkEls.current.delete(i))}
                            stroke={st.stroke}
                            strokeWidth={st.width}
                            strokeOpacity={st.opacity}
                            strokeDasharray={st.dash || 'none'}
                            className={st.animated ? 'neural-link-animated' : undefined}
                        />
                    );
                })}
            </g>
            <g>
                {nodes.map((n) => (
                    <g
                        key={n.id}
                        data-nodeid={n.id}
                        className="neural-node"
                        ref={(el) => (el ? nodeEls.current.set(n.id, el) : nodeEls.current.delete(n.id))}
                        transform={`translate(${n.seed.x},${n.seed.y})`}
                        onClick={() => onNodeClick && onNodeClick(n)}
                        onPointerEnter={() => setHover(n.id)}
                        onPointerLeave={() => setHover(null)}
                        tabIndex={-1}
                    >
                        {n.type === 'mote' && (
                            // A slice of real headcount drifting around its hub.
                            // Non-interactive by design: the hub is the handle.
                            <circle r={n.r} fill={n.color} opacity="0.55" style={{ pointerEvents: 'none' }} />
                        )}
                        {n.type === 'department' && (
                            <>
                                {/* Soft brand-tinted halo scaled to the hub's mass,
                                    so a large department warms its region of the map. */}
                                <circle r={n.r * 2.6} fill={`${n.color}0a`} style={{ pointerEvents: 'none' }} />
                                <circle r={n.r * 1.7} fill={`${n.color}10`} style={{ pointerEvents: 'none' }} />
                                <circle r={n.r + 7} fill="none" stroke={n.color} strokeWidth="1.4" className="neural-hub-pulse" />
                                <circle r={n.r} fill={`${n.color}26`} stroke={n.color} strokeWidth="1.6" />
                                <text
                                    y="4" textAnchor="middle"
                                    style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10.5, fill: 'var(--text-primary)', pointerEvents: 'none' }}
                                >
                                    {n.metric}
                                </text>
                                <text
                                    ref={(el) => (el ? labelEls.current.set(n.id, el) : labelEls.current.delete(n.id))}
                                    data-tier="dept"
                                    y={n.labelAbove ? -(n.r + 14) : n.r + 22} textAnchor="middle"
                                    style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, letterSpacing: '0.08em', fill: n.color, textTransform: 'uppercase', pointerEvents: 'none' }}
                                >
                                    {truncate(n.label, 20)}
                                </text>
                            </>
                        )}
                        {n.type === 'agent' && (
                            <>
                                <g ref={(el) => (el ? pulseEls.current.set(n.id, el) : pulseEls.current.delete(n.id))}>
                                    <circle r={n.r + 3.5} fill="none" stroke={n.color} strokeWidth="1.5" opacity="0.9" />
                                    <circle r={n.r} fill={n.color} />
                                </g>
                                <text
                                    ref={(el) => (el ? labelEls.current.set(n.id, el) : labelEls.current.delete(n.id))}
                                    data-tier="agent"
                                    y={n.r + 16} textAnchor="middle"
                                    style={{ fontSize: 10.5, fill: 'var(--text-secondary)', pointerEvents: 'none' }}
                                >
                                    {truncate(n.label)}
                                </text>
                            </>
                        )}
                        {n.type === 'connector' && (
                            <>
                                <circle r={n.r + 4} fill="none" stroke={n.color} strokeWidth="1" opacity="0.8" />
                                <circle r={n.r} fill={`${n.color}22`} stroke={n.color} strokeWidth="1.2" />
                                <circle r={1.6} fill={n.color} />
                                <text
                                    ref={(el) => (el ? labelEls.current.set(n.id, el) : labelEls.current.delete(n.id))}
                                    data-tier="small"
                                    y={n.labelAbove ? -(n.r + 9) : n.r + 15} textAnchor="middle"
                                    style={{ fontSize: 10, fill: 'var(--text-tertiary)', pointerEvents: 'none' }}
                                >
                                    {truncate(n.label)}
                                </text>
                            </>
                        )}
                        {n.type === 'task' && (
                            <>
                                <rect
                                    x={-n.r - 3} y={-n.r - 3} width={(n.r + 3) * 2} height={(n.r + 3) * 2}
                                    rx="3" fill="none" stroke={n.color} strokeWidth="1.2"
                                    transform="rotate(45)"
                                />
                                <circle r={n.r - 3} fill={n.color} />
                                <text
                                    ref={(el) => (el ? labelEls.current.set(n.id, el) : labelEls.current.delete(n.id))}
                                    data-tier="small"
                                    y={n.r + 16} textAnchor="middle"
                                    style={{ fontSize: 10, fill: 'var(--text-tertiary)', pointerEvents: 'none' }}
                                >
                                    {truncate(n.label)}
                                </text>
                            </>
                        )}
                        {n.type === 'brain' && (
                            <>
                                <circle r={n.r + 8} fill="none" stroke="#fb923c" strokeWidth="1.2" strokeDasharray="4 6" className="neural-halo-spin" opacity="0.8" />
                                <circle r={n.r} fill="rgba(251,146,60,0.16)" stroke="#fb923c" strokeWidth="1.5" />
                                <text
                                    y="4" textAnchor="middle"
                                    style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, fill: '#fb923c', pointerEvents: 'none' }}
                                >
                                    {n.metric}
                                </text>
                                <text
                                    ref={(el) => (el ? labelEls.current.set(n.id, el) : labelEls.current.delete(n.id))}
                                    data-tier="dept"
                                    y={n.r + 24} textAnchor="middle"
                                    style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, letterSpacing: '0.08em', fill: '#fb923c', textTransform: 'uppercase', pointerEvents: 'none' }}
                                >
                                    {n.label}
                                </text>
                            </>
                        )}
                    </g>
                ))}
            </g>
        </svg>
    );
});

// One synchronous physics step used for the reduced-motion static frame.
function tickOnce(sim) {
    const a = 0.5;
    sim.links.forEach((l) => {
        const dx = l.b.x - l.a.x; const dy = l.b.y - l.a.y;
        const d = Math.hypot(dx, dy) || 1;
        const f = (d - l.rest) * SPRING_K * a;
        const fx = (dx / d) * f; const fy = (dy / d) * f;
        if (!l.a.fixed) { l.a.x += fx; l.a.y += fy; }
        if (!l.b.fixed) { l.b.x -= fx; l.b.y -= fy; }
    });
}

ForceGraph.displayName = 'ForceGraph';
export default ForceGraph;
