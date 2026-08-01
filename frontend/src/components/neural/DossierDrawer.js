// DossierDrawer - click any node and read its story in plain English.
// Everything shown here is DERIVED from live data at render time (telemetry,
// command history, health checks, workforce projections) plus a curated map
// of factual role descriptions. Nothing is a stored copy that can drift.
import React, { memo, useEffect } from 'react';
import { AGENT_FACTS } from './useNeuralData';
import './neural.css';

const fmtWhen = (iso) => {
    if (!iso) return 'No activity on record';
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return 'No activity on record';
    return d.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
};

const SectionTitle = ({ children }) => (
    <div style={ui.sectionTitle}>
        <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
            <rect x="1" y="1" width="8" height="8" fill="none" stroke="currentColor" strokeWidth="1.4" />
        </svg>
        <span>{children}</span>
    </div>
);

const Chip = ({ tone = 'neutral', children }) => (
    <span style={{ ...ui.chip, ...ui.chipTones[tone] }}>{children}</span>
);

// The autonomy ladder, derived per the recipe: an agent with no executions is
// human led; executions issued and reviewed by people mean human assisted.
const LADDER = [
    { key: 'human_led', label: 'Human led', desc: 'A person initiates every piece of work this agent does.' },
    { key: 'human_assisted', label: 'Human assisted', desc: 'The agent does the work; a person issues and reviews each request.' },
    { key: 'fully_autonomous', label: 'Fully autonomous', desc: 'The agent acts on its own within policy. Not yet granted to any HiRo agent.' },
];

const deriveLevel = (executions) => (executions > 0 ? 'human_assisted' : 'human_led');

const Ladder = ({ level }) => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
        {[...LADDER].reverse().map((rung, i) => {
            const active = rung.key === level;
            return (
                <div key={rung.key} style={{ display: 'flex', gap: 12 }}>
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                        <span style={{
                            width: 12, height: 12, borderRadius: 999, flexShrink: 0,
                            background: active ? 'var(--accent-bright)' : 'transparent',
                            border: `2px solid ${active ? 'var(--accent-bright)' : 'var(--border-strong)'}`,
                            boxShadow: active ? '0 0 10px rgba(124,130,255,0.7)' : 'none',
                        }} />
                        {i < LADDER.length - 1 && <span style={{ width: 2, flexGrow: 1, minHeight: 26, background: 'var(--border-subtle)' }} />}
                    </div>
                    <div style={{ paddingBottom: i < LADDER.length - 1 ? 14 : 0 }}>
                        <div style={{ fontSize: 12.5, fontWeight: 600, color: active ? 'var(--text-primary)' : 'var(--text-tertiary)' }}>{rung.label}</div>
                        <div style={{ fontSize: 11.5, color: 'var(--text-tertiary)', lineHeight: 1.45 }}>{rung.desc}</div>
                    </div>
                </div>
            );
        })}
    </div>
);

const Tile = ({ label, value }) => (
    <div style={ui.tile}>
        <div className="mono" style={{ fontSize: 17, fontWeight: 600, color: 'var(--text-primary)' }}>{value}</div>
        <div style={{ fontSize: 10.5, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</div>
    </div>
);

const AgentDossier = ({ node }) => {
    const facts = AGENT_FACTS[node.meta.rawName] || {};
    const commands = node.meta.commands || [];
    const completed = commands.filter((c) => c.status === 'COMPLETED').length;
    const lastRun = commands[0]?.created_at;
    const level = deriveLevel(commands.length);
    return (
        <>
            <div style={ui.chipRow}>
                <Chip tone="success">Registered</Chip>
                <Chip tone={node.meta.busConnected ? 'success' : 'warning'}>
                    {node.meta.busConnected ? 'Message bus connected' : 'Answering without the message bus'}
                </Chip>
            </div>
            <SectionTitle>What it does</SectionTitle>
            <p style={ui.body}>{facts.role || 'A registered HiRo agent. Its role description has not been curated yet.'}</p>

            <SectionTitle>Autonomy ladder</SectionTitle>
            <Ladder level={level} />
            <p style={{ ...ui.body, fontSize: 11.5, color: 'var(--text-tertiary)' }}>
                {level === 'human_led'
                    ? 'No commands on record yet, so every future action starts with a person.'
                    : 'Derived from the live record: every run so far was issued by a person through the orchestrator.'}
            </p>

            {facts.replaces && (
                <>
                    <SectionTitle>What it replaces</SectionTitle>
                    <div style={ui.card}>{facts.replaces}</div>
                </>
            )}

            <SectionTitle>The human</SectionTitle>
            <p style={ui.body}>
                {level === 'human_led'
                    ? 'You start every piece of work this agent does, and you see the result before anything changes.'
                    : 'You issue each request and review the answer. The agent never acts without a person behind the command.'}
            </p>

            <SectionTitle>Live record</SectionTitle>
            <div style={ui.tileRow}>
                <Tile label="Runs" value={commands.length} />
                <Tile label="Completed" value={completed} />
                <Tile label="Last run" value={lastRun ? fmtWhen(lastRun) : 'Never'} />
            </div>
            {commands.length > 0 && (
                <>
                    <SectionTitle>Most recent request</SectionTitle>
                    <div style={ui.card}>
                        <div style={{ fontWeight: 550, marginBottom: 4 }}>{commands[0].prompt}</div>
                        <div style={{ fontSize: 11.5, color: 'var(--text-tertiary)' }}>
                            Asked by {commands[0].user_id} on {fmtWhen(commands[0].created_at)}
                        </div>
                    </div>
                </>
            )}
        </>
    );
};

const TaskDossier = ({ node }) => {
    const t = node.meta;
    const done = t.status === 'COMPLETED';
    return (
        <>
            <div style={ui.chipRow}>
                <Chip tone={done ? 'success' : 'warning'}>{done ? 'Completed' : String(t.status || 'In progress').toLowerCase().replace(/_/g, ' ')}</Chip>
                {t.instances > 1 && <Chip>Asked {t.instances} times</Chip>}
            </div>
            <SectionTitle>The request</SectionTitle>
            <p style={ui.body}>{t.prompt}</p>
            <SectionTitle>What happened</SectionTitle>
            <div style={ui.card}>{t.summary || 'The orchestrator recorded a result but no summary.'}</div>
            <SectionTitle>Record</SectionTitle>
            <div style={ui.tileRow}>
                <Tile label="Answered by" value={String(t.agent || 'Unknown').replace(/([a-z0-9])([A-Z])/g, '$1 $2')} />
                <Tile label="Asked by" value={t.user_id || 'Unknown'} />
                <Tile label="When" value={fmtWhen(t.created_at)} />
            </div>
        </>
    );
};

const DeptDossier = ({ node }) => {
    const m = node.meta;
    if (m.platform) {
        return (
            <>
                <div style={ui.chipRow}>
                    <Chip tone={m.health === 'GREEN' ? 'success' : 'warning'}>{m.health === 'GREEN' ? 'Healthy' : 'Degraded'}</Chip>
                    <Chip>{m.agents} agents registered</Chip>
                </div>
                <SectionTitle>What this is</SectionTitle>
                <p style={ui.body}>
                    The platform itself: the agents, data stores and the AI engine that every department draws on.
                </p>
                {m.healthReason && (
                    <>
                        <SectionTitle>Health right now</SectionTitle>
                        <div style={ui.card}>{m.healthReason}</div>
                    </>
                )}
            </>
        );
    }
    const riskTone = { LOW: 'success', MEDIUM: 'warning', HIGH: 'danger' }[m.risk] || 'neutral';
    return (
        <>
            <div style={ui.chipRow}>
                <Chip>{m.headcount} people</Chip>
                {m.risk && <Chip tone={riskTone}>{`${m.risk.charAt(0)}${m.risk.slice(1).toLowerCase()}`} skill risk</Chip>}
            </div>
            <SectionTitle>Skill coverage</SectionTitle>
            <p style={ui.body}>{m.summary}</p>
            <div style={{ height: 6, borderRadius: 999, background: 'var(--border-subtle)', overflow: 'hidden', marginBottom: 14 }}>
                <div style={{
                    height: '100%', borderRadius: 999, background: node.color,
                    width: `${Math.round(((m.skills_covered || 0) / Math.max(1, m.skills_needed || 1)) * 100)}%`,
                }} />
            </div>
            {Array.isArray(m.missing_skills) && m.missing_skills.length > 0 && (
                <>
                    <SectionTitle>Missing skills</SectionTitle>
                    <div style={{ ...ui.chipRow, flexWrap: 'wrap' }}>
                        {m.missing_skills.map((s) => <Chip key={s}>{s}</Chip>)}
                    </div>
                </>
            )}
            {m.succession != null && (
                <>
                    <SectionTitle>Succession readiness</SectionTitle>
                    <div style={ui.card}>
                        {typeof m.succession === 'object' ? JSONFree(m.succession) : String(m.succession)}
                    </div>
                </>
            )}
        </>
    );
};

// Succession readiness may arrive as an object; render it as sentences, never raw JSON.
const JSONFree = (obj) => Object.entries(obj)
    .map(([k, v]) => `${k.replace(/_/g, ' ')}: ${typeof v === 'number' ? v : String(v)}`)
    .join('. ');

const ConnectorDossier = ({ node }) => (
    <>
        <div style={ui.chipRow}>
            <Chip tone={node.meta.up ? 'success' : 'danger'}>{node.meta.up ? 'Up and serving' : 'Down'}</Chip>
        </div>
        <SectionTitle>What this is</SectionTitle>
        <p style={ui.body}>
            {{
                postgres: 'The relational database holding employee, policy and workforce records.',
                mongodb: 'The document store holding command history, tickets and unstructured records.',
                nats: 'The message bus agents use to pass work between themselves in the background.',
                ai_primary: 'The local AI engine (Ollama). Every model call in HiRo runs here, on this machine.',
            }[node.meta.component] || 'A platform component reported by the live health check.'}
        </p>
        <SectionTitle>Platform status</SectionTitle>
        <div style={ui.card}>{node.meta.summary || `Overall status: ${node.meta.overall || 'unknown'}`}</div>
    </>
);

const BrainDossier = ({ node }) => (
    <>
        <div style={ui.chipRow}>
            <Chip tone={node.meta.indexed ? 'success' : 'warning'}>
                {node.meta.indexed ? 'Indexed' : 'Being indexed'}
            </Chip>
            <Chip>{node.metric} documents received</Chip>
        </div>
        <SectionTitle>What this is</SectionTitle>
        <p style={ui.body}>
            Everything HiRo has been taught: uploaded documents, notes and policies. Open the Brain view for stats, search and to teach it something new.
        </p>
        {!node.meta.indexed && (
            <div style={ui.card}>
                The knowledge core is being indexed. The count above reflects documents actually received by the ingestion pipeline.
            </div>
        )}
    </>
);

const DossierDrawer = memo(({ node, onClose }) => {
    useEffect(() => {
        const onKey = (e) => { if (e.key === 'Escape') onClose(); };
        window.addEventListener('keydown', onKey);
        return () => window.removeEventListener('keydown', onKey);
    }, [onClose]);

    if (!node) return null;

    const TYPE_NAMES = { agent: 'Agent', task: 'Request', department: 'Department', connector: 'System', brain: 'Knowledge core' };

    return (
        <aside className="neural-rise" style={ui.drawer} aria-label={`${node.label} dossier`}>
            <div style={ui.header}>
                <div>
                    <div className="mono" style={ui.eyebrow}>{`// ${(TYPE_NAMES[node.type] || 'Node').toUpperCase()}`}</div>
                    <h2 style={ui.title}>{node.label}</h2>
                </div>
                <button onClick={onClose} style={ui.close} aria-label="Close dossier">
                    <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
                        <path d="M2 2l10 10M12 2L2 12" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
                    </svg>
                </button>
            </div>
            <div style={ui.scroll}>
                {node.type === 'agent' && <AgentDossier node={node} />}
                {node.type === 'task' && <TaskDossier node={node} />}
                {node.type === 'department' && <DeptDossier node={node} />}
                {node.type === 'connector' && <ConnectorDossier node={node} />}
                {node.type === 'brain' && <BrainDossier node={node} />}
            </div>
        </aside>
    );
});

const ui = {
    drawer: {
        // Starts below the ingest bar so teaching the brain stays reachable
        // while a dossier is open.
        position: 'absolute', top: 64, right: 12, bottom: 12, width: 380, maxWidth: 'calc(100% - 24px)',
        display: 'flex', flexDirection: 'column', zIndex: 30,
        background: 'color-mix(in srgb, var(--bg-surface-elevated) 92%, transparent)',
        backdropFilter: 'var(--glass-blur)', WebkitBackdropFilter: 'var(--glass-blur)',
        border: '1px solid var(--border-strong)', borderRadius: 14, boxShadow: 'var(--shadow-lg)',
    },
    header: {
        display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between',
        padding: '16px 18px 12px', borderBottom: '1px solid var(--border-subtle)', flexShrink: 0,
    },
    eyebrow: { fontSize: 10, letterSpacing: '0.14em', color: 'var(--text-tertiary)', marginBottom: 4 },
    title: { margin: 0, fontSize: 16, fontWeight: 600, color: 'var(--text-primary)', lineHeight: 1.3 },
    close: {
        border: '1px solid var(--border-subtle)', background: 'transparent', color: 'var(--text-secondary)',
        width: 28, height: 28, borderRadius: 8, cursor: 'pointer', display: 'grid', placeItems: 'center', flexShrink: 0,
    },
    scroll: { padding: '14px 18px 18px', overflowY: 'auto', minHeight: 0 },
    sectionTitle: {
        display: 'flex', alignItems: 'center', gap: 7, margin: '16px 0 8px',
        fontFamily: "'JetBrains Mono', monospace", fontSize: 10, letterSpacing: '0.12em',
        textTransform: 'uppercase', color: 'var(--text-tertiary)',
    },
    body: { margin: '0 0 6px', fontSize: 13, lineHeight: 1.55, color: 'var(--text-secondary)' },
    card: {
        padding: '10px 12px', borderRadius: 10, fontSize: 12.5, lineHeight: 1.5,
        background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border-subtle)', color: 'var(--text-secondary)',
    },
    chipRow: { display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 4 },
    chip: {
        fontSize: 11, padding: '3px 9px', borderRadius: 999, border: '1px solid var(--border-subtle)',
        color: 'var(--text-secondary)', background: 'rgba(255,255,255,0.03)',
    },
    chipTones: {
        neutral: {},
        success: { color: 'var(--accent-success)', border: '1px solid rgba(76,183,130,0.4)' },
        warning: { color: 'var(--accent-warning)', border: '1px solid rgba(242,201,76,0.4)' },
        danger: { color: 'var(--accent-danger)', border: '1px solid rgba(235,87,87,0.4)' },
    },
    tileRow: { display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 },
    tile: {
        padding: '10px 8px', borderRadius: 10, textAlign: 'center',
        background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border-subtle)',
    },
};

DossierDrawer.displayName = 'DossierDrawer';
export default DossierDrawer;
