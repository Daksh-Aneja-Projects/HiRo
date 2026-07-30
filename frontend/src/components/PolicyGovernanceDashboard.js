// Compliance posture for the HRBP: how the enforcement engine has actually been
// deciding, how many high severity breaches are open, and whether the live
// policy set is current. Every figure comes from /api/compliance/dashboard,
// which aggregates the real policy_audit_log.
import React, { useMemo, memo } from 'react';
import { theme as tokens } from '../theme';
import { useApi } from '../hooks/useApi';
import { getComplianceDashboardData } from '../config/api';
import DataCard from './DataCard';
import PieChartWidget from './charts/PieChartWidget';
import { Shield, Loader2, AlertTriangle, Clock, Radio, ScrollText } from 'lucide-react';
import { s } from './policy/ui';

const feedText = (status) => {
    switch (String(status || '').toUpperCase()) {
        case 'ONLINE': return 'Live';
        case 'DEGRADED': return 'Patchy';
        case 'OFFLINE': return 'Down';
        default: return status ? String(status).toLowerCase() : 'Unknown';
    }
};

const PolicyGovernanceDashboard = memo(() => {
    const { data, isLoading, error } = useApi(getComplianceDashboardData, [], true, 60000);

    const total = Number(data?.total_decisions) || 0;
    const denials = Number(data?.denials) || 0;
    const approved = Math.max(0, total - denials);
    const denialRate = total ? (denials / total) * 100 : 0;
    const violations = Number(data?.high_severity_violations) || 0;
    const upToDate = data?.latest_version_applied === true;

    const decisionSplit = useMemo(() => (total > 0
        ? [{ name: 'Allowed by policy', value: approved }, { name: 'Denied by policy', value: denials }]
        : []), [total, approved, denials]);

    const styles = {
        grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: tokens.spacing?.lg, marginBottom: tokens.spacing?.lg },
        lower: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: tokens.spacing?.lg },
    };

    if (isLoading && !data) {
        return (
            <p style={{ ...s.hint, textAlign: 'center', padding: tokens.spacing?.xl }}>
                <Loader2 size={18} className="animate-spin" /> Reading the compliance ledger...
            </p>
        );
    }

    if (error) {
        return (
            <div style={{ ...s.panel, color: tokens.color?.danger, display: 'flex', gap: 10, alignItems: 'center' }}>
                <AlertTriangle size={20} />
                <span>The compliance service did not answer: {error}</span>
            </div>
        );
    }

    return (
        <div>
            <div style={styles.grid}>
                <DataCard title="Decisions that followed policy" value={total ? (100 - denialRate).toFixed(1) : '0.0'} unit="%"
                          color={tokens.color?.success} icon={<Shield size={22} />}
                          subtitle={total ? `${approved.toLocaleString()} of ${total.toLocaleString()} decisions` : 'No decisions recorded yet'} />
                <DataCard title="Open high severity breaches" value={violations} unit={violations === 1 ? 'case' : 'cases'}
                          color={violations > 0 ? tokens.color?.danger : tokens.color?.success} icon={<AlertTriangle size={22} />}
                          subtitle={violations > 0 ? 'Needs an HRBP review' : 'Nothing outstanding'} />
                <DataCard title="Next scheduled audit" value={data?.days_to_next_audit ?? 0} unit="days away"
                          color={tokens.color?.['accent-secondary']} icon={<Clock size={22} />} />
                <DataCard title="Regulatory feeds" value={feedText(data?.regulatory_feed_status)}
                          color={String(data?.regulatory_feed_status).toUpperCase() === 'ONLINE' ? tokens.color?.success : tokens.color?.warning}
                          icon={<Radio size={22} />}
                          subtitle={upToDate ? 'Live policy set is the newest one' : 'A newer policy version has not been applied'} />
            </div>

            <div style={styles.lower}>
                <DataCard title="How the engine decided" isChart minHeight="320px">
                    <PieChartWidget data={decisionSplit} minHeight="250px" />
                </DataCard>

                <div style={s.panel}>
                    <h3 style={s.sectionTitle}><ScrollText size={16} color={tokens.color?.['accent-primary']} /> What this means</h3>
                    {total === 0 ? (
                        <p style={{ ...s.hint, marginTop: 12 }}>
                            The enforcement engine has not judged a single transaction yet, so there is no compliance record to read.
                            Activate a policy version and the decisions will start landing here.
                        </p>
                    ) : (
                        <p style={{ color: tokens.color?.['muted-500'], fontSize: 13.5, lineHeight: 1.85, marginTop: 12 }}>
                            The engine has judged {total.toLocaleString()} transactions against the live policy set.
                            It let {approved.toLocaleString()} through and blocked {denials.toLocaleString()},
                            a denial rate of {denialRate.toFixed(1)} percent.
                            {' '}{violations > 0
                                ? `${violations} of those breaches are rated high severity and are still open.`
                                : 'No high severity breach is currently open.'}
                            {' '}{upToDate
                                ? 'The version being enforced is the newest approved one.'
                                : 'A newer approved version exists but is not the one being enforced, so activate it before the next audit.'}
                            {' '}The next audit is {data?.days_to_next_audit ?? 0} days away.
                        </p>
                    )}
                </div>
            </div>
        </div>
    );
});

PolicyGovernanceDashboard.displayName = 'PolicyGovernanceDashboard';
export default PolicyGovernanceDashboard;
