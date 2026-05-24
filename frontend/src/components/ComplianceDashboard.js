// /frontend/src/components/ComplianceDashboard.js - FINAL PRODUCTION-READY REPLACEMENT (Adding Polling Fix)
import React, { useMemo, memo } from 'react';
import { theme as tokens } from '../theme';
import { useApi } from '../hooks/useApi';
import { getGovernanceDashboardData, getComplianceDashboardData } from '../config/api'; // CRITICAL FIX: Import stabilized API functions

// UI COMPONENTS
import DataCard from './DataCard';
import ChartPlaceholder from './ChartPlaceholder';
import { Shield, Users, Zap, Loader2, AlertTriangle, MessageCircle } from 'lucide-react';

const ComplianceDashboard = memo(() => {
    
    // CRITICAL API INTEGRATION 1: Fetch Governance Data (DAO/Proposals)
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
    const activeProposals = governanceData?.active_proposals || 0;
    const complianceScore = ((complianceData?.score || 0) * 100).toFixed(1);
    const regulatoryFeedStatus = complianceData?.regulatory_feed_status || 'UNKNOWN';
    const totalVotingPower = governanceData?.total_voting_power?.toFixed(0) || 'N/A';
    
    const regStatusColor = regulatoryFeedStatus === 'ONLINE' ? tokens.color?.success : (regulatoryFeedStatus === 'DEGRADED' ? tokens.color?.warning : tokens.color?.danger);

    const styles = useMemo(() => ({
        grid: { display: 'grid', gridTemplateColumns: 'repeat(12, 1fr)', gap: tokens.spacing?.lg, marginBottom: tokens.spacing?.lg },
        card: { gridColumn: 'span 3' },
        chartHalf: { gridColumn: 'span 6', minHeight: '300px' },
    }), []);


    if (isLoading) {
        return <p style={{ textAlign: 'center', padding: tokens.spacing?.xl }}><Loader2 size={32} className="animate-spin" /> Loading Compliance Dashboard...</p>;
    }

    if (govError || compError) {
        return (
            <div style={{ padding: tokens.spacing?.xl, background: tokens.color?.['panel-700'], borderRadius: tokens.border?.radius?.card, color: tokens.color?.danger }}>
                <AlertTriangle size={24} style={{ marginRight: tokens.spacing?.xs, marginBottom: '-3px' }} />
                Error loading compliance data feeds.
            </div>
        );
    }

    return (
        <div style={styles.grid}>
            {/* Governance Metrics */}
            <div style={styles.card}>
                <DataCard title="Active Proposals" value={activeProposals} unit="Count" color={tokens.color?.['accent-secondary']}>
                    <Users size={24} color={tokens.color?.['accent-secondary']} />
                </DataCard>
            </div>
            <div style={styles.card}>
                <DataCard title="Members Voting" value={governanceData?.members_voting || 'N/A'} unit="Count" color={tokens.color?.warning}>
                    <Users size={24} color={tokens.color?.warning} />
                </DataCard>
            </div>
            <div style={styles.card}>
                <DataCard title="Total Voting Power" value={totalVotingPower} unit="Units" color={tokens.color?.['accent-primary']}>
                    <Zap size={24} color={tokens.color?.['accent-primary']} />
                </DataCard>
            </div>
            
            {/* Compliance Metrics */}
            <div style={styles.card}>
                <DataCard title="Overall Compliance Score" value={complianceScore} unit="%" color={tokens.color?.success}>
                    <Shield size={24} color={tokens.color?.success} />
                </DataCard>
            </div>
            <div style={styles.card}>
                <DataCard title="Regulatory Feed Status" value={regulatoryFeedStatus} unit="State" color={regStatusColor}>
                    <MessageCircle size={24} color={regStatusColor} />
                </DataCard>
            </div>

            {/* Charts */}
            <div style={styles.chartHalf}>
                <ChartPlaceholder label="Governance Voting Activity Trend" minHeight="100%" />
            </div>
            <div style={styles.chartHalf}>
                <ChartPlaceholder label="Policy Violation Distribution by Type" minHeight="100%" />
            </div>
        </div>
    );
});

ComplianceDashboard.displayName = 'ComplianceDashboard';
export default ComplianceDashboard;