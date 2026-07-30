// HR service desk health - queue depth, SLA breaches and where every case sits.
// All figures come from /api/hrsd/monitoring/overview.
import React, { useMemo, memo, useCallback, useState } from 'react';
import { theme as tokens } from '../theme';
import { useApi } from '../hooks/useApi';
import { useToast } from '../hooks/use-toast';
import { getHRSDMonitoringOverview, syncServiceNow } from '../config/api';
import DataCard from './DataCard';
import BarChartWidget from './charts/BarChartWidget';
import PieChartWidget from './charts/PieChartWidget';
import { MessageCircle, CheckCircle2, AlertTriangle, Loader2, RefreshCw, Activity } from 'lucide-react';
import { s, dim, apiError } from './policy/ui';

// The service desk stores machine statuses; readers get sentences.
const STATUS_TEXT = {
    NEW: 'Just raised',
    IN_TRIAGE: 'Being triaged',
    IN_RESOLUTION: 'Being worked',
    PENDING_EMPLOYEE: 'Waiting on the employee',
    CLOSED: 'Closed',
    RESOLVED: 'Resolved',
    RESOLVED_BY_AGENT: 'Resolved by an agent',
};
export const ticketStatusText = (raw) => {
    const key = String(raw || '').toUpperCase();
    if (STATUS_TEXT[key]) return STATUS_TEXT[key];
    if (!raw) return 'Unknown';
    const words = String(raw).replace(/_/g, ' ').toLowerCase();
    return words.charAt(0).toUpperCase() + words.slice(1);
};

const HRSDMonitoringDashboard = memo(() => {
    const { toast } = useToast();
    const [isSyncing, setIsSyncing] = useState(false);
    const { data: overview, isLoading, error, refetch } = useApi(getHRSDMonitoringOverview, [], true, 60000);

    const handleSync = useCallback(async () => {
        setIsSyncing(true);
        try {
            const res = await syncServiceNow();
            const external = res.data?.details?.external_configured;
            toast({
                title: 'Sync recorded',
                description: external
                    ? 'The service desk pulled from the connected ServiceNow tenant.'
                    : 'No ServiceNow tenant is connected, so the attempt was logged locally instead.',
                variant: 'success',
            });
            refetch();
        } catch (err) {
            toast({ title: 'Sync failed', description: apiError(err), variant: 'destructive' });
        } finally {
            setIsSyncing(false);
        }
    }, [toast, refetch]);

    const statusSplit = useMemo(() => Object.entries(overview?.tickets_by_status || {})
        .map(([name, value]) => ({ name: ticketStatusText(name), value: Number(value) || 0 })), [overview]);

    const active = Number(overview?.active_tickets) || 0;
    const total = Number(overview?.total_tickets) || 0;
    const breaches = Number(overview?.sla_breaches) || 0;
    const closed = Math.max(0, total - active);

    const throughput = useMemo(() => (total > 0 ? [
        { name: 'Still open', value: active },
        { name: 'Closed out', value: closed },
        { name: 'Past their SLA', value: breaches },
    ] : []), [total, active, closed, breaches]);

    const styles = {
        grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: tokens.spacing?.lg, marginBottom: tokens.spacing?.lg },
        charts: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: tokens.spacing?.lg },
    };

    if (isLoading && !overview) {
        return (
            <p style={{ ...s.hint, textAlign: 'center', padding: tokens.spacing?.xl }}>
                <Loader2 size={18} className="animate-spin" /> Reading the service desk queue...
            </p>
        );
    }

    if (error) {
        return (
            <div style={{ ...s.panel, color: tokens.color?.danger, display: 'flex', gap: 10, alignItems: 'center' }}>
                <AlertTriangle size={20} />
                <span>The service desk did not answer: {error}</span>
            </div>
        );
    }

    return (
        <div>
            <div style={{ ...s.panel, ...s.row, justifyContent: 'space-between', marginBottom: tokens.spacing?.lg }}>
                <span style={{ color: tokens.color?.['muted-500'], fontSize: 13 }}>
                    Triage agents are {String(overview?.agent_status || 'unknown').toLowerCase()}.
                    {' '}{total.toLocaleString()} case(s) have passed through the desk in total.
                </span>
                <button type="button" onClick={handleSync} disabled={isSyncing} style={dim(s.btnGhost, isSyncing)}>
                    {isSyncing ? <Loader2 size={15} className="animate-spin" /> : <RefreshCw size={15} />} Pull from ServiceNow
                </button>
            </div>

            <div style={styles.grid}>
                <DataCard title="Cases still open" value={active} unit={active === 1 ? 'case' : 'cases'}
                          color={tokens.color?.warning} icon={<MessageCircle size={22} />} />
                <DataCard title="Past their response deadline" value={breaches} unit={breaches === 1 ? 'case' : 'cases'}
                          color={breaches > 0 ? tokens.color?.danger : tokens.color?.success} icon={<AlertTriangle size={22} />}
                          subtitle={active > 0 ? `${Math.round((breaches / active) * 100)} percent of open cases` : 'Nothing open'} />
                <DataCard title="Closed out" value={closed} unit={closed === 1 ? 'case' : 'cases'}
                          color={tokens.color?.success} icon={<CheckCircle2 size={22} />} />
                <DataCard title="Triage agents" value={overview?.agent_status || 'Unknown'}
                          color={tokens.color?.['accent-primary']} icon={<Activity size={22} />} />
            </div>

            <div style={styles.charts}>
                <DataCard title="Where the cases sit right now" isChart minHeight="320px">
                    <PieChartWidget data={statusSplit} minHeight="250px" />
                </DataCard>
                <DataCard title="Open, closed and overdue" isChart minHeight="320px">
                    <BarChartWidget data={throughput} minHeight="250px" color={tokens.color?.['accent-primary']} />
                </DataCard>
            </div>
        </div>
    );
});

HRSDMonitoringDashboard.displayName = 'HRSDMonitoringDashboard';
export default HRSDMonitoringDashboard;
