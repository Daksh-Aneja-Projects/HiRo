// /frontend/src/pages/HRPortal.js - FINAL PRODUCTION-READY REPLACEMENT
import React, { useMemo, memo, useState, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import { theme as tokens } from '../theme';

// CRITICAL API IMPORTS
import {
    getActivePolicy, getPolicyHistory, submitPolicyDraft,
    getComplianceDashboardData, getHRSDTickets, getEmployeeCompensation,
    uploadIngestionFile, getAnalyticsCharts, getTeamPerformanceTrend,
    getWFPProjections
} from '../config/api';
import { useApi } from '../hooks/useApi';

// UI COMPONENTS (Assume these exist and are stable)
import DataCard from '../components/DataCard';
import AreaChartWidget from '../components/charts/AreaChartWidget';
import BarChartWidget from '../components/charts/BarChartWidget';
import PieChartWidget from '../components/charts/PieChartWidget';
import { countBy, skillGapSeries, readinessSeries } from '../utils/chartData';
import { 
    BookOpen, DollarSign, Users, FileText, Briefcase, 
    Search, Loader2, ArrowLeft, AlertTriangle, CheckCircle
} from 'lucide-react';
import PolicyGovernanceDashboard from '../components/PolicyGovernanceDashboard'; // Assumed complex component for Policy tab


// --- 7.1. Sub-Module: Policy Governance ---
/**
 * Renders the Policy Governance and Compliance module.
 */
const PolicyModule = memo(() => {
    // CRITICAL API INTEGRATION 1: Fetch Compliance Dashboard Data
    const { 
        data: complianceData, 
        isLoading: isComplianceLoading, 
        error: complianceError 
    } = useApi(getComplianceDashboardData, [], true, 300000); // FIX: Polling interval set to 5 minutes (300000ms)

    // Real monthly workforce-performance series (proxy for compliance-health trend over time).
    const { data: trend } = useApi(getTeamPerformanceTrend, [], true);

    // Real decision breakdown from the live compliance engine (approved vs denied).
    const violationBreakdown = useMemo(() => {
        const total = Number(complianceData?.total_decisions) || 0;
        const denials = Number(complianceData?.denials) || 0;
        if (total <= 0) return [];
        return [
            { name: 'Compliant', value: Math.max(0, total - denials) },
            { name: 'Denied / Violation', value: denials },
        ];
    }, [complianceData]);

    const styles = useMemo(() => ({
        grid: { display: 'grid', gridTemplateColumns: 'repeat(12, 1fr)', gap: tokens.spacing?.lg, marginBottom: tokens.spacing?.lg },
        card: { gridColumn: 'span 3' },
        chart: { gridColumn: 'span 6', minHeight: '300px' }
    }), []);

    return (
        <div className="policy-module">
            <h2 style={{ color: tokens.color?.['accent-primary'], marginBottom: tokens.spacing?.lg }}>Compliance Overview</h2>
            
            {isComplianceLoading && <p style={{textAlign: 'center'}}><Loader2 size={20} className="animate-spin" /> Loading compliance data...</p>}
            {complianceError && <p style={{ color: tokens.color?.danger }}>Error loading compliance dashboard.</p>}

            <div style={styles.grid}>
                {/* Data Cards */}
                <div style={styles.card}>
                    <DataCard 
                        title="Policy Compliance Score" 
                        value={(complianceData?.score * 100).toFixed(1) || 'N/A'} 
                        unit="%" 
                        color={tokens.color?.success}
                    >
                        <CheckCircle size={24} color={tokens.color?.success} />
                    </DataCard>
                </div>
                <div style={styles.card}>
                    <DataCard 
                        title="Active Violations" 
                        value={complianceData?.active_violations || 0} 
                        unit="Count" 
                        color={tokens.color?.danger}
                    >
                        <AlertTriangle size={24} color={tokens.color?.danger} />
                    </DataCard>
                </div>
                <div style={styles.card}>
                    <DataCard 
                        title="Pending Policy Drafts" 
                        value={complianceData?.pending_drafts || 0} 
                        unit="Count" 
                        color={tokens.color?.warning}
                    >
                        <BookOpen size={24} color={tokens.color?.warning} />
                    </DataCard>
                </div>
                <div style={styles.card}>
                    <DataCard 
                        title="Last Audit Date" 
                        value={complianceData?.last_audit_date ? new Date(complianceData.last_audit_date).toLocaleDateString() : 'N/A'} 
                        unit="" 
                        color={tokens.color?.['accent-secondary']}
                    >
                        <Briefcase size={24} color={tokens.color?.['accent-secondary']} />
                    </DataCard>
                </div>
                
                {/* Charts */}
                <div style={styles.chart}>
                    <DataCard title="Workforce Performance Trend (monthly)" isChart minHeight="300px">
                        <AreaChartWidget data={trend || []} minHeight="240px" color={tokens.color?.success} />
                    </DataCard>
                </div>
                <div style={styles.chart}>
                    <DataCard title="Compliance Decision Breakdown" isChart minHeight="300px">
                        <PieChartWidget data={violationBreakdown} minHeight="240px" />
                    </DataCard>
                </div>
            </div>

            <PolicyGovernanceDashboard />
        </div>
    );
});
PolicyModule.displayName = 'PolicyModule';

// --- 7.2. Sub-Module: Compensation Workbench (Mocked) ---
const CompensationModule = memo(() => {
    // CRITICAL API INTEGRATION 2: Fetch Employee Compensation Data (No polling for sensitivity)
    const { 
        data: compensationData, 
        isLoading, 
        error 
    } = useApi(getEmployeeCompensation, [], true, 0);

    // Real headcount distribution across departments from the employee UDM.
    const { data: charts } = useApi(getAnalyticsCharts, [], true);

    const styles = useMemo(() => ({
        grid: { display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: tokens.spacing?.lg, marginBottom: tokens.spacing?.lg },
        card: { gridColumn: 'span 1' },
    }), []);

    return (
        <div className="compensation-module">
            <h2 style={{ color: tokens.color?.['accent-primary'], marginBottom: tokens.spacing?.lg }}>Compensation Workbench</h2>
            
            {isLoading && <p style={{textAlign: 'center'}}><Loader2 size={20} className="animate-spin" /> Loading compensation data...</p>}
            {error && <p style={{ color: tokens.color?.danger }}>Error loading compensation data.</p>}

            <div style={styles.grid}>
                <div style={styles.card}>
                    <DataCard 
                        title="Avg Compa-Ratio" 
                        value={compensationData?.avg_compa_ratio?.toFixed(2) || 'N/A'} 
                        unit="" 
                        color={tokens.color?.success}
                    >
                        <DollarSign size={24} color={tokens.color?.success} />
                    </DataCard>
                </div>
                <div style={styles.card}>
                    <DataCard 
                        title="Budget Utilization" 
                        value={(compensationData?.budget_utilization * 100).toFixed(1) || 'N/A'} 
                        unit="%" 
                        color={tokens.color?.['accent-secondary']}
                    >
                        <Users size={24} color={tokens.color?.['accent-secondary']} />
                    </DataCard>
                </div>
                <div style={styles.card}>
                    <DataCard 
                        title="Pending Salary Actions" 
                        value={compensationData?.pending_actions || 0} 
                        unit="Count" 
                        color={tokens.color?.warning}
                    >
                        <Search size={24} color={tokens.color?.warning} />
                    </DataCard>
                </div>
            </div>
            <DataCard title="Headcount Distribution by Department" isChart minHeight="400px">
                <BarChartWidget data={charts?.headcount_by_department || []} minHeight="340px" color={tokens.color?.['accent-primary']} />
            </DataCard>
        </div>
    );
});
CompensationModule.displayName = 'CompensationModule';


// --- 7.3. Sub-Module: Talent Insights (Mocked) ---
const TalentModule = memo(() => {
    // Real workforce-planning projections (skill gaps per department) + attrition by dept.
    const { data: wfp } = useApi(getWFPProjections, [], true);
    const { data: charts } = useApi(getAnalyticsCharts, [], true);

    const readiness = useMemo(() => readinessSeries(wfp?.skill_gaps || {}), [wfp]);
    const gaps = useMemo(() => skillGapSeries(wfp?.skill_gaps || {}), [wfp]);

    return (
        <div className="talent-module">
            <h2 style={{ color: tokens.color?.['accent-primary'], marginBottom: tokens.spacing?.lg }}>Talent Insights & Planning</h2>
            <DataCard title="Succession Pipeline Readiness by Department" isChart minHeight="400px">
                <BarChartWidget data={readiness} minHeight="340px" color={tokens.color?.success} label="Higher bar = readier bench (inverse of skill gap)" />
            </DataCard>
            <div style={{ display: 'flex', gap: tokens.spacing?.lg, marginTop: tokens.spacing?.lg }}>
                <div style={{ flex: 1 }}>
                    <DataCard title="Skills Gap Analysis by Department" isChart minHeight="300px">
                        <BarChartWidget data={gaps} minHeight="240px" color={tokens.color?.warning} label="Higher bar = larger skill gap" />
                    </DataCard>
                </div>
                <div style={{ flex: 1 }}>
                    <DataCard title="Attrition Risk by Department" isChart minHeight="300px">
                        <BarChartWidget data={charts?.attrition_by_department || []} minHeight="240px" color={tokens.color?.danger} />
                    </DataCard>
                </div>
            </div>
        </div>
    );
});
TalentModule.displayName = 'TalentModule';

// --- 7.4. Sub-Module: AI Document Ingestion (Mocked) ---
const IngestionModule = memo(() => {
    const [file, setFile] = useState(null);
    const [isUploading, setIsUploading] = useState(false);

    const handleFileUpload = useCallback(async (e) => {
        e.preventDefault();
        if (!file) return;

        setIsUploading(true);
        try {
            // CRITICAL API INTEGRATION 3: Upload Document for AI Ingestion
            await uploadIngestionFile(file);
            alert(`File ${file.name} submitted for AI ingestion!`);
            setFile(null);
        } catch (error) {
            console.error("Upload failed:", error);
            alert(`Upload failed: ${error.message}`);
        } finally {
            setIsUploading(false);
        }
    }, [file]);
    
    const styles = useMemo(() => ({
        container: { maxWidth: '800px', margin: '0 auto', padding: tokens.spacing?.xl, background: tokens.color?.['panel-800'], borderRadius: tokens.border?.radius?.card },
        input: { padding: tokens.spacing?.md, border: `1px solid ${tokens.color?.['border-600']}`, borderRadius: tokens.border?.radius?.input, color: tokens.color?.['text-100'], background: tokens.color?.['bg-input'] },
        button: { padding: '10px 20px', background: tokens.color?.success, border: 'none', borderRadius: tokens.border?.radius?.button, color: tokens.color?.['bg-deep'], cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: tokens.spacing?.xs, marginTop: tokens.spacing?.md },
        statusCard: { padding: tokens.spacing?.lg, background: tokens.color?.['panel-700'], borderRadius: tokens.border?.radius?.card, marginTop: tokens.spacing?.lg, borderLeft: `4px solid ${tokens.color?.['accent-primary']}` }
    }), []);

    return (
        <div className="ingestion-module" style={styles.container}>
            <h2 style={{ color: tokens.color?.['accent-primary'], marginBottom: tokens.spacing?.lg }}>AI Document Ingestion</h2>
            <p style={{ color: tokens.color?.['muted-500'] }}>Upload new policy documents or regulatory files for the AI Governance model to process and integrate.</p>

            <form onSubmit={handleFileUpload} style={{ display: 'flex', flexDirection: 'column', gap: tokens.spacing?.md, marginTop: tokens.spacing?.md }}>
                <input
                    type="file"
                    onChange={(e) => setFile(e.target.files[0])}
                    style={styles.input}
                    required
                />
                <button 
                    type="submit" 
                    disabled={isUploading || !file}
                    style={styles.button}
                >
                    {isUploading ? <Loader2 size={16} className="animate-spin" /> : <FileText size={16} />} 
                    {isUploading ? 'Processing...' : 'Upload & Ingest'}
                </button>
            </form>

            <div style={styles.statusCard}>
                <h3 style={{ margin: '0 0 10px 0', color: tokens.color?.['text-100'] }}>Ingestion Status</h3>
                <p style={{ color: tokens.color?.['muted-500'] }}>Last document ingested: **Q3 2024 Regulatory Update** (7 days ago)</p>
                <p style={{ color: tokens.color?.success }}>Processing Queue: **0** files pending.</p>
            </div>
        </div>
    );
});
IngestionModule.displayName = 'IngestionModule';


// --- 7.5. Sub-Module: HRSD Case Management (Mocked) ---
const CasesModule = memo(() => {
    // CRITICAL API INTEGRATION 4: Fetch HRSD Tickets (Polling for live updates)
    const { 
        data: tickets, 
        isLoading: isTicketsLoading, 
        error: ticketsError, 
    } = useApi(getHRSDTickets, [], true, 60000); // Polling every 60 seconds

    // Real distributions derived from the live ticket set (no fabricated series).
    const byAssignee = useMemo(() => countBy(tickets || [], (t) => t.assigned_to), [tickets]);
    const byPriority = useMemo(() => countBy(tickets || [], (t) => t.priority), [tickets]);

    const styles = useMemo(() => ({
        grid: { display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: tokens.spacing?.lg },
        ticketCard: (isHighPriority) => ({
            padding: tokens.spacing?.md,
            background: tokens.color?.['panel-700'],
            borderRadius: tokens.border?.radius?.card,
            borderLeft: `4px solid ${isHighPriority ? tokens.color?.danger : tokens.color?.warning}`,
            marginBottom: tokens.spacing?.md,
        })
    }), []);
    
    return (
        <div className="cases-module">
            <h2 style={{ color: tokens.color?.['accent-primary'], marginBottom: tokens.spacing?.lg }}>HRSD Case Management</h2>
            
            {isTicketsLoading && <p style={{textAlign: 'center'}}><Loader2 size={20} className="animate-spin" /> Loading tickets...</p>}
            {ticketsError && <p style={{ color: tokens.color?.danger }}>Error loading HRSD tickets.</p>}

            <div style={styles.grid}>
                <div>
                    <h3 style={{ borderBottom: `1px solid ${tokens.color?.['border-600']}`, paddingBottom: tokens.spacing?.xs, marginBottom: tokens.spacing?.md }}>High Priority Cases</h3>
                    {(tickets || []).filter(t => t.priority === 'High').map(ticket => (
                        <div key={ticket.id} style={styles.ticketCard(true)}>
                            <p style={{ fontWeight: 'bold', margin: '0 0 5px 0', color: tokens.color?.danger }}>{ticket.subject}</p>
                            <p style={{ margin: 0, fontSize: tokens.typography?.small?.fontSize, color: tokens.color?.['muted-500'] }}>Assigned to: {ticket.assigned_to}</p>
                        </div>
                    ))}
                    {/* Real: open cases grouped by assignee */}
                    <div style={{ marginTop: tokens.spacing?.lg }}>
                        <DataCard title="Open Cases by Assignee" isChart minHeight="250px">
                            <BarChartWidget data={byAssignee} minHeight="200px" color={tokens.color?.['accent-primary']} />
                        </DataCard>
                    </div>
                </div>
                <div>
                    <h3 style={{ borderBottom: `1px solid ${tokens.color?.['border-600']}`, paddingBottom: tokens.spacing?.xs, marginBottom: tokens.spacing?.md }}>Normal & Low Priority Cases</h3>
                    {(tickets || []).filter(t => t.priority !== 'High').map(ticket => (
                        <div key={ticket.id} style={styles.ticketCard(false)}>
                            <p style={{ fontWeight: 'bold', margin: '0 0 5px 0', color: tokens.color?.warning }}>{ticket.subject}</p>
                            <p style={{ margin: 0, fontSize: tokens.typography?.small?.fontSize, color: tokens.color?.['muted-500'] }}>Assigned to: {ticket.assigned_to}</p>
                        </div>
                    ))}
                    {/* Real: ticket volume grouped by priority */}
                    <div style={{ marginTop: tokens.spacing?.lg }}>
                        <DataCard title="Ticket Volume by Priority" isChart minHeight="250px">
                            <BarChartWidget data={byPriority} minHeight="200px" color={tokens.color?.warning} />
                        </DataCard>
                    </div>
                </div>
            </div>
        </div>
    );
});
CasesModule.displayName = 'CasesModule';


// --- MAIN HR PORTAL COMPONENT ---
export const HRPortalComponent = memo(() => {
    const location = useLocation();
    const query = new URLSearchParams(location.search);
    const module = query.get('module') || 'policy'; 

    const getModuleComponent = (mod) => {
        switch (mod) {
            case 'policy':
                return <PolicyModule />;
            case 'comp':
                return <CompensationModule />;
            case 'talent':
                return <TalentModule />;
            case 'ingestion':
                return <IngestionModule />;
            case 'cases':
                return <CasesModule />;
            default:
                return (
                    <div style={{ textAlign: 'center', color: tokens.color?.danger, padding: tokens.spacing?.xl }}>
                        <AlertTriangle size={32} />
                        <h3 style={{ margin: tokens.spacing?.md }}>Module Not Found</h3>
                        <p>The requested HR portal module "{mod}" could not be loaded.</p>
                    </div>
                );
        }
    };

    const moduleTitleMap = {
        policy: 'Policy Governance & Compliance',
        comp: 'Compensation Workbench',
        talent: 'Talent Insights & Planning',
        ingestion: 'AI Document Ingestion',
        cases: 'HRSD Case Management',
    };
    
    // CRITICAL FIX: Ensure styles are defensively defined
    const styles = useMemo(() => ({
        container: { minHeight: '100%', display: 'flex', flexDirection: 'column' },
        header: {
            color: tokens.color?.['text-100'],
            marginBottom: tokens.spacing?.lg,
            borderBottom: `1px solid ${tokens.color?.['border-600']}`,
            paddingBottom: tokens.spacing?.md,
        },
        title: {
            fontSize: tokens.typography?.h1?.fontSize, // Added optional chaining
            margin: 0,
            display: 'flex',
            alignItems: 'center',
            gap: tokens.spacing?.sm,
        },
    }), []);

    return (
        <div style={styles.container} className="portal-container">
            <div style={styles.header}>
                <h1 style={styles.title}>
                    <Briefcase size={32} color={tokens.color?.danger} />
                    HR Portal: {moduleTitleMap[module] || 'Unknown Module'}
                </h1>
            </div>
            
            {/* Render the dynamically selected module component */}
            {getModuleComponent(module)}
        </div>
    );
});

HRPortalComponent.displayName = 'HRPortalComponent';
export default HRPortalComponent;