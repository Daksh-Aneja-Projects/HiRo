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

const spread = (i, n, centerX, width) =>
    n <= 1 ? centerX : centerX - width / 2 + (i * width) / (n - 1);

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

        // --- Department hubs (pinned band) ---
        const deptDetail = Array.isArray(wfp?.skill_gap_detail) ? wfp.skill_gap_detail : [];
        const deptNames = deptDetail.map((d) => d.department);
        const hubs = [...deptNames, PLATFORM];
        const slot = W / (hubs.length + 1);
        const hubX = new Map();
        hubs.forEach((name, i) => {
            const x = slot * (i + 1);
            hubX.set(name, x);
            const detail = deptDetail.find((d) => d.department === name);
            nodes.push({
                id: `dept:${name}`,
                type: 'department',
                label: name,
                dept: name,
                color: DEPT_PALETTE[i % DEPT_PALETTE.length],
                r: 17,
                fixed: true,
                seed: { x, y: H * 0.74 },
                metric: detail ? String(detail.headcount) : String(orch?.agents ?? 0),
                meta: detail
                    ? { ...detail, risk: wfp?.skill_gaps?.[name] || null, succession: wfp?.succession_readiness?.[name] ?? null }
                    : { platform: true, agents: orch?.agents ?? 0, health: orch?.system_health, healthReason: orch?.health_reason },
            });
        });
        // Hubs connect in sequence - the layout is a line, not a ring.
        for (let i = 1; i < hubs.length; i++) {
            links.push({ source: `dept:${hubs[i - 1]}`, target: `dept:${hubs[i]}`, tier: 'hub-hub' });
        }

        // --- The brain (pinned) ---
        // The live /knowledge/stats shape is {corpus: {total, by_source}, loop}.
        const docsKnown = Number(knowledge?.corpus?.total ?? ingestion?.total ?? 0);
        nodes.push({
            id: 'brain',
            type: 'brain',
            label: 'Knowledge Core',
            dept: null,
            color: '#fb923c',
            r: 22,
            fixed: true,
            seed: { x: W / 2, y: H * 0.94 },
            metric: String(docsKnown),
            meta: { knowledge, ingestion, indexed: Boolean(knowledge) },
        });
        hubs.forEach((name) => links.push({ source: `dept:${name}`, target: 'brain', tier: 'hub-brain' }));

        // --- Agents (floating above their hub) ---
        const agentNames = Array.isArray(orch?.agent_names) ? orch.agent_names : [];
        const byDept = new Map();
        agentNames.forEach((name) => {
            const dept = AGENT_FACTS[name]?.dept || PLATFORM;
            if (!byDept.has(dept)) byDept.set(dept, []);
            byDept.get(dept).push(name);
        });
        byDept.forEach((names, dept) => {
            const cx = hubX.get(dept) || hubX.get(PLATFORM);
            names.forEach((name, i) => {
                nodes.push({
                    id: `agent:${name}`,
                    type: 'agent',
                    label: humanizeAgentName(name),
                    dept,
                    color: '#8b93f8',
                    r: 9,
                    seed: { x: spread(i, names.length, cx, slot * 0.72), y: H * 0.44 + (i % 2 ? 12 : -12) },
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
            const cx = hubX.get(dept) || hubX.get(PLATFORM);
            group.forEach((t, i) => {
                const id = `task:${t.result_id}`;
                nodes.push({
                    id,
                    type: 'task',
                    label: t.instances > 1 ? `${t.prompt} (x${t.instances})` : t.prompt,
                    dept,
                    color: '#f2c94c',
                    r: 7,
                    seed: { x: spread(i, group.length, cx, slot * 0.86), y: H * 0.24 + (i % 2 ? 16 : -16) },
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

        // --- Connectors from live component health ---
        const checks = health?.checks || {};
        const connectorNames = Object.keys(checks);
        const pcx = hubX.get(PLATFORM);
        connectorNames.forEach((key, i) => {
            const up = String(checks[key]).toUpperCase() === 'UP';
            const id = `connector:${key}`;
            nodes.push({
                id,
                type: 'connector',
                label: CONNECTOR_LABELS[key] || key.replace(/_/g, ' '),
                dept: PLATFORM,
                color: up ? '#3fb9e5' : '#eb5757',
                r: 7,
                seed: { x: spread(i, connectorNames.length, pcx, slot * 1.6), y: H * 0.09 },
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
            hubs: hubs.map((name, i) => ({ name, x: hubX.get(name), color: DEPT_PALETTE[i % DEPT_PALETTE.length] })),
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
