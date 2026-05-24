// /frontend/src/components/PolicyGovernanceDashboard.js - FINAL PRODUCTION-READY REPLACEMENT (Polling Stabilized)
import React, { useMemo, memo } from 'react';
import { theme as tokens } from '../theme';
import { useApi } from '../hooks/useApi';
import { getGovernanceDashboardData, getComplianceDashboardData } from '../config/api'; // CRITICAL FIX: Import stabilized API functions
import DataCard from './DataCard';
import ChartPlaceholder from './ChartPlaceholder';
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

    const isLoading = isGovLoading || isCompLoading;

    // Data stabilization and display logic
    const policyViolationCount = complianceData?.high_severity_violations || 0;
    const isPolicyUpToDate = complianceData?.latest_version_applied === true;

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
                <ChartPlaceholder label="Policy Audit Queue Trend (Real-Time)" minHeight="100%" />
            </div>
            <div style={styles.chartHalf}>
                <ChartPlaceholder label="Policy Versioning & Rollback History" minHeight="100%" />
            </div>
            
            <div style={{ gridColumn: 'span 12' }}>
                <ChartPlaceholder label="Compliance Risk Breakdown by Geography" minHeight="250px" />
            </div>
        </div>
    );
});

PolicyGovernanceDashboard.displayName = 'PolicyGovernanceDashboard';
export default PolicyGovernanceDashboard;