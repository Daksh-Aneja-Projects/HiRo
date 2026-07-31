// /frontend/src/pages/HRITPortal.js - HRIT console for the HRIT_ADMIN persona.
// Modules: agent | governance | health | models. Everything shown here is read from
// the running platform; there are no seeded figures and no placeholder fallbacks.
import React, { useMemo, memo } from 'react';
import { useLocation } from 'react-router-dom';
import { theme as tokens } from '../theme';

import {
    getOrchestratorDashboardData, getAgentActivity, getServiceNowHealth,
    getActiveAIProvider, getAiModels, getModelAuditLog,
} from '../config/api';
import { useApi } from '../hooks/useApi';

import DataCard from '../components/DataCard';
import BarChartWidget from '../components/charts/BarChartWidget';
import AreaChartWidget from '../components/charts/AreaChartWidget';
import PieChartWidget from '../components/charts/PieChartWidget';
import { CountUp, LiveMeter, useMetricSeries } from '../components/live/LivePrimitives';
import { objToSeries, countBy } from '../utils/chartData';

import AgentManagementPanel from '../components/AgentManagementPanel';
import ConfigurationAgentPanel from '../components/ConfigurationAgentPanel';
import SystemHealthPanel from '../components/SystemHealthPanel';
import LiveTelemetryFeed from '../components/LiveTelemetryFeed';
import { PortalHeader, UnknownModule, portalShell } from '../components/admin/PortalHeader';
import { ui, Loading, EmptyState, ErrorNote, EmployeeStyles, fmtDate } from '../components/employee/shared';
import {
    Cpu, Bot, ScrollText, Activity, Brain, Radio, Boxes, ListChecks,
    Gauge, LifeBuoy, Timer, CheckCircle2,
} from 'lucide-react';

const MODULES = [
    { key: 'agent', label: 'Agent factory', icon: Bot },
    { key: 'governance', label: 'Governance', icon: ScrollText },
    { key: 'health', label: 'System health', icon: Activity },
    { key: 'models', label: 'Models', icon: Brain },
];

/* ------------------------------------------------------------------ */
/* Agent factory                                                       */
/* ------------------------------------------------------------------ */
const AgentModule = memo(() => {
    const { data: orch, isLoading, error } = useApi(getOrchestratorDashboardData, [], true, 15000);
    const { data: activity, isLoading: actLoading, error: actError } = useApi(getAgentActivity, [60], true, 30000);

    const byAgent = useMemo(
        () => (Array.isArray(activity) ? activity : []).map((a) => ({ name: a.agent_id, value: Number(a.events) || 0 })),
        [activity],
    );
    const totalEvents = byAgent.reduce((n, a) => n + a.value, 0);
    const busConnected = Boolean(orch?.message_bus_connected);
    const healthy = String(orch?.system_health || '').toUpperCase() === 'GREEN';

    return (
        <div style={ui.grid} className="portal-grid">
            <div style={{ gridColumn: 'span 3' }}>
                <DataCard title="Agents registered" value={<CountUp value={orch?.agents ?? 0} />} icon={<Boxes size={16} />} subtitle="Available to take work" />
            </div>
            <div style={{ gridColumn: 'span 3' }}>
                <DataCard
                    title="Work in progress"
                    value={<CountUp value={orch?.active_tasks ?? 0} />}
                    color={tokens.color?.['accent-secondary']}
                    icon={<ListChecks size={16} />}
                    subtitle={Number(orch?.active_tasks) > 0 ? 'Tasks running right now' : 'Nothing running right now'}
                />
            </div>
            <div style={{ gridColumn: 'span 3' }}>
                <DataCard
                    title="Orchestrator"
                    value={healthy ? 'Healthy' : (orch?.system_health ? 'Degraded' : 'Unknown')}
                    color={healthy ? tokens.color?.success : tokens.color?.warning}
                    icon={<Gauge size={16} />}
                    footer={<LiveMeter pct={Number(orch?.metrics?.cpu) || 0} color={tokens.color?.['accent-primary']} label="Processor load" />}
                />
            </div>
            <div style={{ gridColumn: 'span 3' }}>
                <DataCard
                    title="Message bus"
                    value={busConnected ? 'Connected' : 'Not connected'}
                    color={busConnected ? tokens.color?.success : tokens.color?.warning}
                    icon={<Radio size={16} />}
                    subtitle={busConnected ? 'Agents can hand work to each other' : 'Agents are working in isolation'}
                />
            </div>

            {error && <div style={{ gridColumn: 'span 12' }}><ErrorNote error={error} context="the orchestrator snapshot" /></div>}
            {isLoading && !orch && <div style={{ gridColumn: 'span 12' }}><Loading label="Reading the orchestrator" /></div>}

            <div style={{ gridColumn: 'span 5' }}>
                <AgentManagementPanel />
            </div>

            <div style={{ ...ui.panel, gridColumn: 'span 7' }}>
                <h3 style={ui.h3}>Which agents have been busy</h3>
                <p style={ui.hint}>
                    {actLoading && !activity ? 'Counting agent activity over the last hour.' : null}
                    {!actLoading && totalEvents === 0
                        ? 'No agent has done anything in the last hour.'
                        : `${totalEvents} action${totalEvents === 1 ? '' : 's'} across ${byAgent.length} agent${byAgent.length === 1 ? '' : 's'} in the last hour.`}
                </p>
                <ErrorNote error={actError} context="agent activity" />
                <div style={{ marginTop: tokens.spacing?.md }}>
                    {byAgent.length === 0 && !actLoading
                        ? <EmptyState icon={Bot} title="No agent activity in the last hour" action="Run a command from the orchestrator console and the agent that handles it will show up here." />
                        : <BarChartWidget data={byAgent} minHeight="260px" color={tokens.color?.['accent-primary']} />}
                </div>
            </div>
        </div>
    );
});
AgentModule.displayName = 'AgentModule';

/* ------------------------------------------------------------------ */
/* Governance                                                          */
/* ------------------------------------------------------------------ */
// Case lifecycle keys are backend enums. Never surface them raw.
const CASE_STAGE_COPY = {
    NEW: 'Just raised',
    IN_TRIAGE: 'Being triaged',
    IN_RESOLUTION: 'Being worked on',
    RESOLVED_BY_AGENT: 'Closed by an agent',
    RESOLVED: 'Resolved',
    CLOSED: 'Closed',
};

const DECISION_COPY = {
    APPROVE: 'was allowed',
    APPROVED: 'was allowed',
    DENY: 'was blocked',
    DENIED: 'was blocked',
    REJECT: 'was blocked',
};

const GovernanceModule = memo(() => {
    const { data: hrsd, isLoading: hrsdLoading, error: hrsdError } = useApi(getServiceNowHealth, [], true, 60000);
    // This panel shows the decisions the policy engine made. It used to pass the
    // language model's name into an endpoint whose path segment is a decision
    // trigger, so it asked for decisions of type "llama3.1:8b" and the log was
    // permanently empty while 266 decisions sat in the table.
    const { data: audit, isLoading: auditLoading, error: auditError } = useApi(getModelAuditLog, ['all', 40], true);

    const lifecycle = useMemo(
        () => objToSeries(hrsd?.tickets_by_status).map((s) => ({
            ...s,
            name: CASE_STAGE_COPY[s.name] || String(s.name).replace(/_/g, ' ').toLowerCase(),
        })),
        [hrsd],
    );
    // The response is {decisions: [...]}, so array-checking the envelope left
    // this empty even once the parameter above was right.
    const rows = useMemo(
        () => (Array.isArray(audit?.decisions) ? audit.decisions : Array.isArray(audit) ? audit : []),
        [audit],
    );
    const decisions = useMemo(() => countBy(rows, (r) => (String(r.decision).toUpperCase().startsWith('APPROV') ? 'Allowed' : 'Blocked')), [rows]);
    const autoResolved = Number(hrsd?.tickets_by_status?.RESOLVED_BY_AGENT) || 0;
    const agentOnline = String(hrsd?.agent_status || '').toLowerCase() === 'online';

    return (
        <div style={ui.grid} className="portal-grid">
            <div style={{ gridColumn: 'span 3' }}>
                <DataCard
                    title="Resolution agent"
                    value={agentOnline ? 'Online' : (hrsd?.agent_status || 'Unknown')}
                    color={agentOnline ? tokens.color?.success : tokens.color?.warning}
                    icon={<LifeBuoy size={16} />}
                    subtitle={agentOnline ? 'Picking up cases without a human' : 'Not currently picking up cases'}
                />
            </div>
            <div style={{ gridColumn: 'span 3' }}>
                <DataCard
                    title="Closed by an agent"
                    value={<CountUp value={autoResolved} />}
                    color={tokens.color?.['accent-primary']}
                    icon={<CheckCircle2 size={16} />}
                    subtitle="Cases resolved with no human touch"
                />
            </div>
            <div style={{ gridColumn: 'span 3' }}>
                <DataCard
                    title="Cases still open"
                    value={<CountUp value={hrsd?.active_tickets ?? 0} />}
                    color={tokens.color?.warning}
                    icon={<ListChecks size={16} />}
                    subtitle={`${hrsd?.total_tickets ?? 0} raised in total`}
                />
            </div>
            <div style={{ gridColumn: 'span 3' }}>
                <DataCard
                    title="Past their deadline"
                    value={<CountUp value={hrsd?.sla_breaches ?? 0} />}
                    color={Number(hrsd?.sla_breaches) > 0 ? tokens.color?.danger : tokens.color?.success}
                    icon={<Timer size={16} />}
                    subtitle={Number(hrsd?.sla_breaches) > 0 ? 'These need a human today' : 'Everything is inside its deadline'}
                />
            </div>

            {hrsdError && <div style={{ gridColumn: 'span 12' }}><ErrorNote error={hrsdError} context="the service delivery posture" /></div>}
            {hrsdLoading && !hrsd && <div style={{ gridColumn: 'span 12' }}><Loading label="Reading the service delivery posture" /></div>}

            <div style={{ gridColumn: 'span 5' }}>
                <DataCard title="Where open work is sitting" isChart minHeight="360px">
                    <PieChartWidget data={lifecycle} minHeight="310px" />
                </DataCard>
            </div>

            <div style={{ ...ui.panel, gridColumn: 'span 7' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: tokens.spacing?.sm }}>
                    <div style={{ minWidth: 0 }}>
                        <h3 style={ui.h3}>Every decision the policy engine made</h3>
                        <p style={ui.hint}>
                            {model
                                ? `Recorded while ${model} was the active model. Each line says what was attempted, what the engine decided and why.`
                                : 'Waiting to learn which model the platform is running.'}
                        </p>
                    </div>
                    {decisions.length > 0 && (
                        <div style={{ width: 150, flexShrink: 0 }}>
                            <BarChartWidget data={decisions} minHeight="90px" color={tokens.color?.success} />
                        </div>
                    )}
                </div>
                <div style={{ marginTop: tokens.spacing?.sm }}>
                    {auditLoading && rows.length === 0 && <Loading label="Reading the decision log" />}
                    <ErrorNote error={auditError} context="the policy decision log" />
                    {!auditLoading && !auditError && rows.length === 0 && (
                        <EmptyState icon={ScrollText} title="No decisions recorded yet" action="As soon as the policy engine allows or blocks something, it will be written here." />
                    )}
                    <div style={ui.scroller('340px')} className="emp-scroll">
                        {rows.map((r) => {
                            const allowed = String(r.decision).toUpperCase().startsWith('APPROV');
                            const verb = DECISION_COPY[String(r.decision).toUpperCase()] || `ended as ${String(r.decision).toLowerCase()}`;
                            return (
                                <div key={r.audit_id} style={ui.listRow}>
                                    <div style={{ display: 'flex', gap: 10, minWidth: 0, alignItems: 'flex-start' }}>
                                        <span style={{
                                            marginTop: 6, width: 6, height: 6, borderRadius: 999, flexShrink: 0,
                                            background: allowed ? tokens.color?.success : tokens.color?.danger,
                                        }} />
                                        <div style={ui.rowMain}>
                                            <span style={{ ...ui.rowTitle, whiteSpace: 'normal' }}>
                                                {String(r.action || 'An action').replace(/_/g, ' ')} {verb}
                                            </span>
                                            <span style={ui.rowMeta}>{r.reason || 'No reason was recorded.'}</span>
                                            <span style={ui.rowMeta}>
                                                {fmtDate(r.timestamp)}
                                                {r.policy_version ? ` · judged by the ${String(r.policy_version).replace(/_/g, ' ').toLowerCase()} rule set` : ''}
                                            </span>
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            </div>
        </div>
    );
});
GovernanceModule.displayName = 'GovernanceModule';

/* ------------------------------------------------------------------ */
/* System health                                                       */
/* ------------------------------------------------------------------ */
const HealthModule = memo(() => {
    const cpuSeries = useMetricSeries('cpu_load', { intervalMs: 3000 });
    // This charted `agent_activity`, which was the average of processor and
    // memory load served under an agent-sounding name. It read about 50 with the
    // agent layer idle. Memory is a real reading; what the agents are actually
    // doing is on the panel below it.
    const memorySeries = useMetricSeries('memory_load', { intervalMs: 3000 });

    return (
        <div style={ui.grid} className="portal-grid">
            <div style={{ gridColumn: 'span 5' }}>
                <SystemHealthPanel />
            </div>
            <div style={{ gridColumn: 'span 7' }}>
                <DataCard title="Memory in use, live" isChart minHeight="240px">
                    <AreaChartWidget data={memorySeries} minHeight="190px" color={tokens.color?.success} label="Host memory, sampled every three seconds" />
                </DataCard>
            </div>
            <div style={{ gridColumn: 'span 12' }}>
                <DataCard title="Processor load, live" isChart minHeight="220px">
                    <AreaChartWidget data={cpuSeries} minHeight="170px" color={tokens.color?.['accent-primary']} label="Host processor load, sampled every three seconds" />
                </DataCard>
            </div>
                        <div style={{ gridColumn: 'span 12' }}>
                <LiveTelemetryFeed />
            </div>
        </div>
    );
});
HealthModule.displayName = 'HealthModule';

/* ------------------------------------------------------------------ */
/* Models                                                              */
/* ------------------------------------------------------------------ */
const ModelsModule = memo(() => {
    const { data: provider, isLoading: provLoading, error: provError } = useApi(getActiveAIProvider, [], true, 60000);
    const { data: modelsResp } = useApi(getAiModels, [], true);
    const models = useMemo(() => modelsResp?.models || [], [modelsResp]);
    const active = String(provider?.status || '').toLowerCase() === 'active';

    return (
        <div style={ui.grid} className="portal-grid">
            <div style={{ gridColumn: 'span 4' }}>
                <DataCard
                    title="Model answering right now"
                    value={provider?.default_model || 'Not reported'}
                    color={active ? tokens.color?.success : tokens.color?.warning}
                    icon={<Brain size={16} />}
                    subtitle={provider ? `Served by ${provider.provider} from ${provider.base_url}` : 'Reading the active model'}
                />
            </div>
            <div style={{ gridColumn: 'span 4' }}>
                <DataCard
                    title="Models installed locally"
                    value={<CountUp value={models.length} />}
                    icon={<Boxes size={16} />}
                    subtitle="Available to switch to without downloading anything"
                />
            </div>
            <div style={{ gridColumn: 'span 4' }}>
                <DataCard
                    title="Inference"
                    value={active ? 'Running on this machine' : 'Not reported as active'}
                    color={active ? tokens.color?.success : tokens.color?.warning}
                    icon={<Cpu size={16} />}
                    subtitle="No prompt or personal data leaves the host"
                />
            </div>

            {provError && <div style={{ gridColumn: 'span 12' }}><ErrorNote error={provError} context="the active model configuration" /></div>}
            {provLoading && !provider && <div style={{ gridColumn: 'span 12' }}><Loading label="Reading the active model" /></div>}

            <div style={{ gridColumn: 'span 12' }}>
                <ConfigurationAgentPanel />
            </div>
        </div>
    );
});
ModelsModule.displayName = 'ModelsModule';

/* ------------------------------------------------------------------ */
/* Shell                                                               */
/* ------------------------------------------------------------------ */
const SUBTITLES = {
    agent: 'Build a new agent from a plain English brief and see what the existing ones have been doing.',
    governance: 'How much work agents are closing on their own, and every decision the policy engine has made.',
    health: 'Live readings from the platform and the services it depends on.',
    models: 'The model answering prompts right now, what else is installed, and the agent that drafts rules.',
};

export const HRITPortalComponent = memo(() => {
    const location = useLocation();
    const module = new URLSearchParams(location.search).get('module') || 'agent';

    const body = {
        agent: <AgentModule />,
        governance: <GovernanceModule />,
        health: <HealthModule />,
        models: <ModelsModule />,
    }[module] || <UnknownModule name={module} />;

    return (
        <div style={portalShell.page}>
            <PortalHeader
                icon={Cpu}
                accent={tokens.color?.['accent-primary']}
                title="HRIT console"
                subtitle={SUBTITLES[module] || 'HR technology operations.'}
                basePath="/hrit-portal"
                modules={MODULES}
                active={module}
            />
            <div style={portalShell.body} className="emp-scroll">{body}</div>
            <EmployeeStyles />
        </div>
    );
});

HRITPortalComponent.displayName = 'HRITPortalComponent';
export default HRITPortalComponent;
