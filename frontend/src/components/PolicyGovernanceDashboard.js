// /frontend/src/components/PolicyGovernanceDashboard.js - FINAL PRODUCTION-READY REPLACEMENT (Polling Stabilized)
import React, { useMemo, memo } from 'react';
import { theme as tokens } from '../theme';
import { useApi } from '../hooks/useApi';
import { getGovernanceDashboardData, getComplianceDashboardData, getAnalyticsCharts } from '../config/api'; // CRITICAL FIX: Import stabilized API functions
import DataCard from './DataCard';
import BarChartWidget from './charts/BarChartWidget';
import PieChartWidget from './charts/PieChartWidget';
import { Shield, Users, Loader2, AlertTriangle, BookOpen, Clock } from 'lucide-react';

const PolicyGovernanceDashboard = memo(() => {
    
    // CRITICAL API INTEGRATION 1: Fetch Governance Data (DAO/Proposals) - Polls every 60s
    // NOTE: Removed extraneous trailing {} argument if it was present
    const { 
        data: governanceData, 
        isLoading: isGovLoading, 
        error: govError 
    } = useApi(getGovernanceDashboardData, [], true, 60000); // CRITICAL FIX: Polling interval set to 60000ms (60 seconds)
    
    // CRITICAL API INTEGRATION 2: Fetch Compliance Data (Policy Status)
    const { 
        data: complianceData, 
        isLoading: isCompLoading, 
        error: compError 
    } = useApi(getComplianceDashboardData, [], true, 60000); // CRITICAL FIX: Polling interval set to 60000ms (60 seconds)

    // Real attrition-by-department series (proxy for compliance risk by group).
    const { data: charts } = useApi(getAnalyticsCharts, [], true);

    const isLoading = isGovLoading || isCompLoading;

    // Data stabilization and display logic
    const policyViolationCount = complianceData?.high_severity_violations || 0;
    const isPolicyUpToDate = complianceData?.latest_version_applied === true;

    // Real compliance decision split (approved vs denied) from the live compliance engine.
    const decisionSplit = useMemo(() => {
        const total = Number(complianceData?.total_decisions) || 0;
        const denials = Number(complianceData?.denials) || 0;
        if (total <= 0) return [];
        return [
            { name: 'Approved', value: Math.max(0, total - denials) },
            { name: 'Denied', value: denials },
        ];
    }, [complianceData]);

    // Real governance activity snapshot from the DAO dashboard.
    const governanceActivity = useMemo(() => ([
        { name: 'Active Proposals', value: Number(governanceData?.active_proposals) || 0 },
        { name: 'Members Voting', value: Number(governanceData?.members_voting) || 0 },
        { name: 'Ledger Commits (24h)', value: Number(governanceData?.ledger_commits_24h) || 0 },
    ]), [governanceData]);

    const styles = useMemo(() => ({
        grid: { display: 'grid', gridTemplateColumns: 'repeat(12, 1fr)', gap: tokens.spacing?.lg, marginBottom: tokens.spacing?.lg },
        card: { gridColumn: 'span 3' },
        chartHalf: { gridColumn: 'span 6', minHeight: '300px' },
    }), []);

    // Placeholder data for rendering safety
    const governance = governanceData || {};
    const compliance = complianceData || {};

    // Determine color based on compliance status
    const statusColor = isPolicyUpToDate ? tokens.color?.success : tokens.color?.danger;


    if (isLoading) {
        return <p style={{ textAlign: 'center', padding: tokens.spacing?.xl }}><Loader2 size={32} className="animate-spin" /> Loading Policy Governance Dashboard...</p>;
    }

    if (govError || compError) {
        return (
            <div style={{ padding: tokens.spacing?.xl, background: tokens.color?.['panel-700'], borderRadius: tokens.border?.radius?.card, color: tokens.color?.danger }}>
                <AlertTriangle size={24} style={{ marginRight: tokens.spacing?.xs, marginBottom: '-3px' }} />
                Error loading one or more dashboard data feeds.
            </div>
        );
    }

    return (
        <div style={styles.grid}>
            {/* Compliance Metrics */}
            <div style={styles.card}>
                <DataCard 
                    title="Latest Policy Version" 
                    value={isPolicyUpToDate ? 'UP TO DATE' : 'STALE'} 
                    unit="Status" 
                    color={statusColor}
                >
                    <Shield size={24} color={statusColor} />
                </DataCard>
            </div>
            <div style={styles.card}>
                <DataCard 
                    title="Time to Policy Audit" 
                    value={compliance.days_to_next_audit || 'N/A'} 
                    unit="Days" 
                    color={tokens.color?.['accent-secondary']}
                >
                    <Clock size={24} color={tokens.color?.['accent-secondary']} />
                </DataCard>
            </div>
            <div style={styles.card}>
                <DataCard 
                    title="High Severity Violations" 
                    value={policyViolationCount} 
                    unit="Count" 
                    color={policyViolationCount > 5 ? tokens.color?.danger : tokens.color?.success}
                >
                    <AlertTriangle size={24} color={policyViolationCount > 5 ? tokens.color?.danger : tokens.color?.success} />
                </DataCard>
            </div>
            
            {/* DAO/Governance Metrics */}
            <div style={styles.card}>
                <DataCard title="Active DAO Proposals" value={governanceData?.active_proposals || 0} unit="Count" color={tokens.color?.['accent-primary']}>
                    <Users size={24} color={tokens.color?.['accent-primary']} />
                </DataCard>
            </div>
            <div style={styles.card}>
                <DataCard title="Policy Ledger Commits (24h)" value={governanceData?.ledger_commits_24h || 0} unit="Commits" color={tokens.color?.warning}>
                    <BookOpen size={24} color={tokens.color?.warning} />
                </DataCard>
            </div>

            {/* Policy Audit and Workflow Status */}
            <div style={styles.chartHalf}>
                <DataCard title="Compliance Decision Split" isChart minHeight="300px">
                    <PieChartWidget data={decisionSplit} minHeight="240px" />
                </DataCard>
            </div>
            <div style={styles.chartHalf}>
                <DataCard title="Governance Activity" isChart minHeight="300px">
                    <BarChartWidget data={governanceActivity} minHeight="240px" color={tokens.color?.['accent-primary']} />
                </DataCard>
            </div>

            <div style={{ gridColumn: 'span 12' }}>
                <DataCard title="Compliance Risk by Department" isChart minHeight="250px">
                    <BarChartWidget data={charts?.attrition_by_department || []} minHeight="200px" color={tokens.color?.warning} />
                </DataCard>
            </div>
        </div>
    );
});

PolicyGovernanceDashboard.displayName = 'PolicyGovernanceDashboard';
export default PolicyGovernanceDashboard;