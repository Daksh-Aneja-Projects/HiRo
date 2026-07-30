// /frontend/src/components/SystemHealthPanel.js
// Live probe of the platform's dependencies. Renders only what /admin/health actually
// reported: no seeded service list, no invented latency figures.
import React, { useMemo, memo } from 'react';
import { theme as tokens } from '../theme';
import { useApi } from '../hooks/useApi';
import { getSystemHealthStatus } from '../config/api';
import StatusChip from './StatusChip';
import { ui, Loading, EmptyState, ErrorNote } from './employee/shared';
import { Activity, Database, Radio, Cpu, Server, HeartPulse } from 'lucide-react';

// The health payload keys are machine names. These turn them into something a
// non-technical reader understands.
const SERVICE_COPY = {
    postgres: { label: 'Employee and payroll database', icon: Database, healthy: 'Answering queries normally.', unhealthy: 'Not answering. Records may fail to load.' },
    mongo: { label: 'Document and audit store', icon: Database, healthy: 'Storing documents and audit entries.', unhealthy: 'Unreachable. New audit entries may be lost.' },
    redis: { label: 'Cache layer', icon: Activity, healthy: 'Serving cached lookups.', unhealthy: 'Down. Every lookup goes to the database instead.' },
    nats: { label: 'Agent message bus', icon: Radio, healthy: 'Agents can talk to each other.', unhealthy: 'Down. Agents run in isolation.' },
    ai_primary: { label: 'Local language model', icon: Cpu, healthy: 'Ready to answer prompts.', unhealthy: 'Not responding. AI features will fail.' },
};

const describe = (key) => SERVICE_COPY[key] || {
    label: String(key).replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase()),
    icon: Server,
    healthy: 'Reporting healthy.',
    unhealthy: 'Reporting a problem.',
};

const SystemHealthPanel = memo(() => {
    const { data, isLoading, error } = useApi(getSystemHealthStatus, [], true, 30000);

    const services = useMemo(() => Object.entries(data?.checks || {}).map(([key, state]) => {
        const copy = describe(key);
        const up = String(state).toUpperCase() === 'UP';
        return { key, up, label: copy.label, icon: copy.icon, note: up ? copy.healthy : copy.unhealthy };
    }), [data]);

    const down = services.filter((s) => !s.up).length;
    const overall = String(data?.status || '').toUpperCase();

    return (
        <div style={{ ...ui.panel, height: '100%', display: 'flex', flexDirection: 'column' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: tokens.spacing?.sm }}>
                <div style={{ minWidth: 0 }}>
                    <h3 style={ui.h3}>
                        <HeartPulse size={15} style={{ marginRight: 7, verticalAlign: '-2px' }} color={tokens.color?.['accent-primary']} />
                        Dependency health
                    </h3>
                    <p style={ui.hint}>
                        {services.length === 0
                            ? 'Waiting for the first live probe.'
                            : down === 0
                                ? `All ${services.length} dependencies answered on the last probe.`
                                : `${down} of ${services.length} dependencies did not answer on the last probe.`}
                        {data?.timestamp ? ` Last checked at ${new Date(data.timestamp).toLocaleTimeString()}.` : ''}
                    </p>
                </div>
                {overall && <StatusChip status={overall === 'HEALTHY' ? 'ONLINE' : 'ERROR'} label={overall === 'HEALTHY' ? 'Healthy' : 'Degraded'} />}
            </div>

            <div style={{ marginTop: tokens.spacing?.md, flexGrow: 1, minHeight: 0 }}>
                {isLoading && services.length === 0 && <Loading label="Probing platform dependencies" />}
                <ErrorNote error={error} context="the dependency health probe" />
                {!isLoading && !error && services.length === 0 && (
                    <EmptyState icon={Server} title="No dependencies were reported" action="The health endpoint answered but listed no services to check." />
                )}
                <div style={ui.scroller('300px')} className="emp-scroll">
                    {services.map(({ key, up, label, icon: Icon, note }) => (
                        <div key={key} style={ui.listRow}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
                                <Icon size={16} color={up ? tokens.color?.success : tokens.color?.danger} />
                                <div style={ui.rowMain}>
                                    <span style={ui.rowTitle}>{label}</span>
                                    <span style={ui.rowMeta}>{note}</span>
                                </div>
                            </div>
                            <StatusChip status={up ? 'ONLINE' : 'OFFLINE'} label={up ? 'Up' : 'Down'} />
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
});

SystemHealthPanel.displayName = 'SystemHealthPanel';
export default SystemHealthPanel;
