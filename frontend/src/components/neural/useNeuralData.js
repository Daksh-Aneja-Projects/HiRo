// useNeuralData - assembles the neural map world from live endpoints only.
// Every node, count and link here traces back to a real API response; nothing
// is invented. Shape adaptation happens HERE, never in the render.
//
// Sources:
//   /api/wfp/projections            -> department hubs (headcount, skill risk)
//   /api/orchestrator/dashboard     -> the real dispatchable agent registry
//   /api/admin/health               -> connector nodes with live up/down state
//   /api/command/history            -> task nodes (recent orchestrator commands)
//   /api/hrsd/monitoring/overview   -> open-case counts (HUD strip)
//   /api/ingestion/jobs             -> what the knowledge core has been fed
//   /api/knowledge/stats            -> knowledge core stats (may 404 while
//                                      being built; the brain degrades honestly)
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
    getWFPProjections,
    getOrchestratorDashboardData,
    getSystemHealthStatus,
    getCommandHistory,
    getHRSDMonitoringOverview,
    getIngestionJobs,
    getKnowledgeStats,
} from '../../config/api';
import { VB } from './ForceGraph';

// Fixed brand palette for departments, assigned in hub order.
export const DEPT_PALETTE = [
    '#5e6ad2', '#3fb9e5', '#4cb782', '#f2c94c', '#fb923c', '#eb5757',
    '#a78bfa', '#f472b6', '#2dd4bf', '#60a5fa', '#a3e635', '#94a3b8', '#8b93f8',
];

const PLATFORM = 'Platform';

// Which functional department each registered agent serves, plus factual
// plain-English descriptions of what each HiRo service really does (curated
// from the backend service sources, not generated).
export const AGENT_FACTS = {
    AIService: {
        dept: PLATFORM,
        role: 'Runs every language request on the local AI engine. All model calls in HiRo go through this service to the on-premise Ollama runtime, so no employee data ever leaves the machine.',
        replaces: 'An analyst manually drafting summaries, answers and reports from raw HR data.',
    },
    ConfigurationAgent: {
        dept: PLATFORM,
        role: 'Deploys configuration and compiled policy changes. It is the bridge between AI-generated policy code and the versioned policy deployment system.',
        replaces: 'A change manager hand-applying configuration and policy updates one by one.',
    },
    WorkforcePlanningService: {
        dept: 'Human Resources',
        role: 'Models attrition and workforce scenarios. It reads live employee records to project headcount, skill gaps and succession readiness for every department.',
        replaces: 'A planning analyst rebuilding headcount and risk spreadsheets every cycle.',
    },
    SyntheticTwinEngine: {
        dept: 'Human Resources',
        role: 'Simulates what-if scenarios on employee digital twins, scoring how a retention or compensation change would shift risk before any real change is made.',
        replaces: 'Trialling retention measures on real people to find out what happens.',
    },
};

// A registered agent name like "WorkforcePlanningService" becomes
// "Workforce Planning Service" - human words, no machine tokens.
export const humanizeAgentName = (name) =>
    String(name || '')
        .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
        .replace(/([A-Z]+)([A-Z][a-z])/g, '$1 $2')
        .trim();

const CONNECTOR_LABELS = {
    postgres: 'PostgreSQL',
    mongodb: 'MongoDB',
    nats: 'Message Bus',
    ai_primary: 'AI Engine',
};

// Radial constellation geometry. HiRo's world is hub-heavy (a dozen large
// departments, a handful of agents), and a horizontal band collapses that into
// a thin strip with dead canvas everywhere else. A ring around the knowledge
// core fills the frame and reads as one organism: the brain at the center,
// departments orbiting it, everything else breathing on the spokes between.
const CENTER = { x: 0.5, y: 0.485 };
const RING = { rx: 0.345, ry: 0.36 };

const hubAngle = (i, n) => -Math.PI / 2 + (i * 2 * Math.PI) / n;

const onRing = (angle, W, H, scale = 1) => ({
    x: W * CENTER.x + Math.cos(angle) * W * RING.rx * scale,
    y: H * CENTER.y + Math.sin(angle) * H * RING.ry * scale,
});

// Hub size carries real mass: the radius grows with the square root of the
// live headcount, so a 3,500-person department visibly outweighs a 4-person
// platform team without dwarfing it.
const hubRadius = (headcount) =>
    Math.max(12, Math.min(27, 12 + Math.sqrt(Math.max(0, Number(headcount) || 0)) * 0.28));

export default function useNeuralData() {
    const [raw, setRaw] = useState(null);
    const [error, setError] = useState(null);
    const [loading, setLoading] = useState(true);

    const refresh = useCallback(async () => {
        try {
            // Only the workforce projection is fatal - it is the hub skeleton.
            // Every other source degrades on its own: a slow or missing
            // endpoint costs its tier of nodes, never the whole map.
            // (Knowledge stats legitimately 404 while another team builds it.)
            // The projection query aggregates the whole workforce on a busy CPU
            // box; one transient failure should not blank the map, so it gets
            // a single retry before the honest error state.
            const wfpWithRetry = () => getWFPProjections().catch(
                () => new Promise((res) => setTimeout(res, 2500)).then(getWFPProjections)
            );
            const [wfp, orch, health, history, hrsd, ingestion, knowledge] = await Promise.all([
                wfpWithRetry(),
                getOrchestratorDashboardData().catch(() => null),
                getSystemHealthStatus().catch(() => null),
                getCommandHistory(20).catch(() => null),
                getHRSDMonitoringOverview().catch(() => null),
                getIngestionJobs(50).catch(() => null),
                getKnowledgeStats().catch(() => null),
            ]);
            setRaw({
                wfp: wfp.data,
                orch: orch?.data || null,
                health: health?.data || null,
                history: Array.isArray(history?.data) ? history.data : [],
                hrsd: hrsd?.data || null,
                ingestion: ingestion?.data || null,
                knowledge: knowledge?.data || null,
            });
            setError(null);
        } catch (e) {
            setError(e?.message || 'The map data could not be loaded.');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { refresh(); }, [refresh]);

    const world = useMemo(() => {
        if (!raw) return null;
        const { wfp, orch, health, history, hrsd, ingestion, knowledge } = raw;

        const nodes = [];
        const links = [];
        const { W, H } = VB;

        // --- Department hubs: a pinned ring around the knowledge core ---
        const deptDetail = Array.isArray(wfp?.skill_gap_detail) ? wfp.skill_gap_detail : [];
        const deptNames = deptDetail.map((d) => d.department);
        const hubs = [...deptNames, PLATFORM];
        const cx = W * CENTER.x;
        const cy = H * CENTER.y;
        const hubPos = new Map();
        const hubAngles = new Map();
        hubs.forEach((name, i) => {
            const angle = hubAngle(i, hubs.length);
            const pos = onRing(angle, W, H);
            hubPos.set(name, pos);
            hubAngles.set(name, angle);
            const detail = deptDetail.find((d) => d.department === name);
            const headcount = detail ? Number(detail.headcount) || 0 : 0;
            nodes.push({
                id: `dept:${name}`,
                type: 'department',
                label: name,
                dept: name,
                color: DEPT_PALETTE[i % DEPT_PALETTE.length],
                r: detail ? hubRadius(headcount) : 14,
                fixed: true,
                seed: pos,
                // Labels sit on the outward side of the ring so they never
                // cross the spokes or each other.
                labelAbove: pos.y < cy,
                metric: detail ? String(detail.headcount) : String(orch?.agents ?? 0),
                meta: detail
                    ? { ...detail, risk: wfp?.skill_gaps?.[name] || null, succession: wfp?.succession_readiness?.[name] ?? null }
                    : { platform: true, agents: orch?.agents ?? 0, health: orch?.system_health, healthReason: orch?.health_reason },
            });
        });
        // Neighbors on the ring connect - the layout is a circle, closed.
        for (let i = 0; i < hubs.length; i++) {
            links.push({ source: `dept:${hubs[i]}`, target: `dept:${hubs[(i + 1) % hubs.length]}`, tier: 'hub-hub' });
        }

        // --- The brain (pinned at the center of the ring) ---
        // The live /knowledge/stats shape is {corpus: {total, by_source}, loop}.
        const docsKnown = Number(knowledge?.corpus?.total ?? ingestion?.total ?? 0);
        nodes.push({
            id: 'brain',
            type: 'brain',
            label: 'Knowledge Core',
            dept: null,
            color: '#fb923c',
            r: 26,
            fixed: true,
            seed: { x: cx, y: cy },
            metric: String(docsKnown),
            meta: { knowledge, ingestion, indexed: Boolean(knowledge) },
        });
        hubs.forEach((name) => links.push({ source: `dept:${name}`, target: 'brain', tier: 'hub-brain' }));

        // --- Workforce motes: the head-count mass made visible ---
        // Each mote stands for a real slice of people (about 400 a dot) drifting
        // around its department hub. They are the reason a big department reads
        // as a living cluster instead of one lonely circle. Derived from the
        // same live headcount as the hub metric; never interactive.
        deptDetail.forEach((d) => {
            const name = d.department;
            const pos = hubPos.get(name);
            const color = DEPT_PALETTE[deptNames.indexOf(name) % DEPT_PALETTE.length];
            const count = Math.max(0, Math.min(9, Math.round((Number(d.headcount) || 0) / 400)));
            const hubR = hubRadius(d.headcount);
            for (let m = 0; m < count; m++) {
                const a = (m * 2.399963) + deptNames.indexOf(name); // golden-angle spacing
                const orbit = hubR + 13 + (m % 3) * 8;
                nodes.push({
                    id: `mote:${name}:${m}`,
                    type: 'mote',
                    label: '',
                    dept: name,
                    color,
                    r: 2.3,
                    seed: { x: pos.x + Math.cos(a) * orbit, y: pos.y + Math.sin(a) * orbit * 0.85 },
                    meta: { peoplePerMote: 400 },
                });
                links.push({ source: `mote:${name}:${m}`, target: `dept:${name}`, tier: 'mote' });
            }
        });

        // --- Agents: breathing on the spoke between the core and their hub ---
        const agentNames = Array.isArray(orch?.agent_names) ? orch.agent_names : [];
        const byDept = new Map();
        agentNames.forEach((name) => {
            const dept = AGENT_FACTS[name]?.dept || PLATFORM;
            if (!byDept.has(dept)) byDept.set(dept, []);
            byDept.get(dept).push(name);
        });
        byDept.forEach((names, dept) => {
            const angle = hubAngles.get(dept) ?? hubAngles.get(PLATFORM);
            names.forEach((name, i) => {
                // Halfway along the spoke, siblings fanned perpendicular to it.
                const base = onRing(angle, W, H, 0.52);
                const perp = angle + Math.PI / 2;
                const off = (i - (names.length - 1) / 2) * 46;
                nodes.push({
                    id: `agent:${name}`,
                    type: 'agent',
                    label: humanizeAgentName(name),
                    dept,
                    color: '#8b93f8',
                    r: 9,
                    seed: { x: base.x + Math.cos(perp) * off, y: base.y + Math.sin(perp) * off },
                    meta: {
                        rawName: name,
                        registered: true,
                        busConnected: Boolean(orch?.message_bus_connected),
                        commands: history.filter((h) => h.agent === name),
                    },
                });
                links.push({ source: `agent:${name}`, target: `dept:${dept}`, tier: 'agent-hub' });
            });
        });

        // --- Tasks: recent orchestrator commands, deduped by prompt ---
        const taskGroups = new Map();
        history.forEach((h) => {
            const key = (h.prompt || '').trim();
            if (!key) return;
            if (!taskGroups.has(key)) taskGroups.set(key, { ...h, instances: 0 });
            taskGroups.get(key).instances += 1;
        });
        const tasks = [...taskGroups.values()].slice(0, 10);
        const tasksByDept = new Map();
        tasks.forEach((t) => {
            const dept = AGENT_FACTS[t.agent]?.dept || PLATFORM;
            if (!tasksByDept.has(dept)) tasksByDept.set(dept, []);
            tasksByDept.get(dept).push(t);
        });
        tasksByDept.forEach((group, dept) => {
            const angle = hubAngles.get(dept) ?? hubAngles.get(PLATFORM);
            group.forEach((t, i) => {
                const id = `task:${t.result_id}`;
                // Between the agents and the hub, fanned either side of the
                // spoke and staggered in depth so a busy department blossoms
                // outward instead of forming a straight overlapping arc.
                const fan = angle + (i - (group.length - 1) / 2) * 0.22;
                const pos = onRing(fan, W, H, 0.72 + (i % 3) * 0.07);
                nodes.push({
                    id,
                    type: 'task',
                    label: t.instances > 1 ? `${t.prompt} (x${t.instances})` : t.prompt,
                    dept,
                    color: '#f2c94c',
                    r: 7,
                    seed: pos,
                    meta: t,
                });
                const agentId = `agent:${t.agent}`;
                if (agentNames.includes(t.agent)) {
                    links.push({ source: id, target: agentId, tier: 'task-agent' });
                } else {
                    links.push({ source: id, target: `dept:${dept}`, tier: 'task-hub' });
                }
            });
        });

        // --- Connectors from live component health: outside the ring ---
        const checks = health?.checks || {};
        const connectorNames = Object.keys(checks);
        const platformAngle = hubAngles.get(PLATFORM);
        connectorNames.forEach((key, i) => {
            const up = String(checks[key]).toUpperCase() === 'UP';
            const id = `connector:${key}`;
            // Beyond the platform hub, arced around its angle: infrastructure
            // sits at the edge of the organism, feeding inward.
            const fan = platformAngle + (i - (connectorNames.length - 1) / 2) * 0.22;
            const pos = onRing(fan, W, H, 1.28);
            nodes.push({
                id,
                type: 'connector',
                label: CONNECTOR_LABELS[key] || key.replace(/_/g, ' '),
                dept: PLATFORM,
                color: up ? '#3fb9e5' : '#eb5757',
                r: 7,
                seed: pos,
                labelAbove: pos.y < cy,
                meta: { component: key, up, overall: health?.status, summary: health?.summary },
            });
            links.push({ source: id, target: `dept:${PLATFORM}`, tier: 'connector-hub' });
        });
        // The AI engine feeds the AI Service directly - a real dependency.
        if (checks.ai_primary && agentNames.includes('AIService')) {
            links.push({ source: 'connector:ai_primary', target: 'agent:AIService', tier: 'connector-agent' });
        }
        // Real message links: with the bus connected, every registered agent
        // passes work over NATS - the gold comms tier.
        if (checks.nats && orch?.message_bus_connected) {
            agentNames.forEach((name) => {
                links.push({ source: `agent:${name}`, target: 'connector:nats', tier: 'agent-comms' });
            });
        }

        return {
            nodes,
            links,
            hubs: hubs.map((name, i) => ({
                name,
                x: hubPos.get(name).x,
                y: hubPos.get(name).y,
                color: DEPT_PALETTE[i % DEPT_PALETTE.length],
            })),
            counts: {
                departments: deptNames.length,
                agents: agentNames.length,
                commands: history.length,
                docs: docsKnown,
                openCases: hrsd?.active_tickets ?? null,
            },
        };
    }, [raw]);

    return { world, raw, error, loading, refresh };
}
