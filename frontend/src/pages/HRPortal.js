// /frontend/src/pages/HRPortal.js - FINAL PRODUCTION-READY REPLACEMENT
import React, { useMemo, memo, useState, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import { theme as tokens } from '../theme';

// CRITICAL API IMPORTS
import {
    getActivePolicy, getPolicyHistory, submitPolicyDraft,
    getComplianceDashboardData, getHRSDTickets, getEmployeeCompensation,
    updateEmployeeCompensation,
    uploadIngestionFile, getIngestionJobs, getAnalyticsCharts, getTeamPerformanceTrend,
    getWFPProjections
} from '../config/api';
import { useApi } from '../hooks/useApi';
import { useToast } from '../hooks/use-toast';

// UI COMPONENTS (Assume these exist and are stable)
import DataCard from '../components/DataCard';
import AreaChartWidget from '../components/charts/AreaChartWidget';
import BarChartWidget from '../components/charts/BarChartWidget';
import PieChartWidget from '../components/charts/PieChartWidget';
import { countBy, skillGapSeries, readinessSeries, toArray } from '../utils/chartData';
import {
    BookOpen, DollarSign, Users, FileText, Briefcase,
    Search, Loader2, ArrowLeft, AlertTriangle, CheckCircle, Shield
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

// --- 7.2. Sub-Module: Compensation Workbench ---
// Real HRBP workflow: look up an employee, read their decrypted compensation
// from the PII vault, and record an adjustment.
const CompensationModule = memo(() => {
    const { toast } = useToast();
    const [employeeId, setEmployeeId] = useState('');
    const [record, setRecord] = useState(null);
    const [isLooking, setIsLooking] = useState(false);
    const [adjust, setAdjust] = useState({ new_salary: '', new_grade: '', effective_date: '' });
    const [isSaving, setIsSaving] = useState(false);

    // Real headcount distribution across departments from the employee UDM.
    const { data: charts } = useApi(getAnalyticsCharts, [], true);

    const lookup = useCallback(async (e) => {
        e?.preventDefault();
        const id = employeeId.trim();
        if (!id) return toast({ title: 'Enter an employee ID', description: 'For example EMP-001.', variant: 'warning' });
        setIsLooking(true);
        setRecord(null);
        try {
            const res = await getEmployeeCompensation(id);
            setRecord(res.data);
            setAdjust((p) => ({ ...p, new_salary: res.data?.base_salary ?? '' }));
        } catch (err) {
            toast({
                title: 'Could not load compensation',
                description: err.response?.data?.detail || err.message,
                variant: 'destructive',
            });
        } finally {
            setIsLooking(false);
        }
    }, [employeeId, toast]);

    const save = useCallback(async (e) => {
        e.preventDefault();
        if (!record) return;
        setIsSaving(true);
        try {
            await updateEmployeeCompensation({
                employee_id: employeeId.trim(),
                new_salary: parseFloat(adjust.new_salary),
                new_grade: adjust.new_grade || 'UNCHANGED',
                effective_date: adjust.effective_date || new Date().toISOString().slice(0, 10),
            });
            toast({ title: 'Compensation updated', description: `Saved for ${employeeId}.`, variant: 'success' });
            lookup();
        } catch (err) {
            toast({
                title: 'Update failed',
                description: err.response?.data?.detail || err.message,
                variant: 'destructive',
            });
        } finally {
            setIsSaving(false);
        }
    }, [record, employeeId, adjust, toast, lookup]);

    const s = {
        row: { display: 'flex', gap: 10, marginBottom: 18, flexWrap: 'wrap' },
        input: { padding: '9px 12px', background: 'var(--bg-input)', border: '1px solid var(--border-subtle)', borderRadius: 8, color: 'var(--text-primary)', fontSize: 13.5, minWidth: 160 },
        btn: { padding: '9px 16px', background: 'var(--accent-primary)', border: 'none', borderRadius: 8, color: '#fff', fontSize: 13, fontWeight: 550, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 7 },
        grid: { display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: tokens.spacing?.lg, marginBottom: tokens.spacing?.lg },
        hint: { color: 'var(--text-tertiary)', fontSize: 12.5, marginBottom: 14 },
    };

    return (
        <div className="compensation-module">
            <h2 style={{ color: tokens.color?.['accent-primary'], marginBottom: 6 }}>Compensation Workbench</h2>
            <p style={s.hint}>Look up an employee to see their current compensation and record an adjustment.</p>

            <form onSubmit={lookup} style={s.row}>
                <input style={s.input} placeholder="Employee ID (e.g. EMP-001)" value={employeeId}
                       onChange={(e) => setEmployeeId(e.target.value)} />
                <button type="submit" style={s.btn} disabled={isLooking}>
                    {isLooking ? <Loader2 size={15} className="animate-spin" /> : <Search size={15} />} Look up
                </button>
            </form>

            {record && (
                <>
                    <div style={s.grid}>
                        <DataCard title="Base salary" value={record.base_salary ?? 'Not set'} color={tokens.color?.success}
                                  icon={<DollarSign size={22} color={tokens.color?.success} />} />
                        <DataCard title="Bonus target" value={record.bonus_target ?? 'Not set'} color={tokens.color?.['accent-secondary']}
                                  icon={<Users size={22} color={tokens.color?.['accent-secondary']} />} />
                        <DataCard title="Accessed as" value={record.retrieved_by_role || 'unknown'} color={tokens.color?.warning}
                                  icon={<Shield size={22} color={tokens.color?.warning} />} />
                    </div>

                    <form onSubmit={save} style={{ ...s.row, alignItems: 'center' }}>
                        <input style={s.input} type="number" step="0.01" placeholder="New salary"
                               value={adjust.new_salary} onChange={(e) => setAdjust((p) => ({ ...p, new_salary: e.target.value }))} required />
                        <input style={s.input} placeholder="New grade" value={adjust.new_grade}
                               onChange={(e) => setAdjust((p) => ({ ...p, new_grade: e.target.value }))} />
                        <input style={s.input} type="date" value={adjust.effective_date}
                               onChange={(e) => setAdjust((p) => ({ ...p, effective_date: e.target.value }))} />
                        <button type="submit" style={s.btn} disabled={isSaving}>
                            {isSaving ? <Loader2 size={15} className="animate-spin" /> : <CheckCircle size={15} />} Save adjustment
                        </button>
                    </form>
                </>
            )}

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
    const { toast } = useToast();
    const [file, setFile] = useState(null);
    const [isUploading, setIsUploading] = useState(false);

    // Real ingestion history + queue depth.
    const { data: jobsData, refetch: refetchJobs } = useApi(getIngestionJobs, [], true);
    const jobs = jobsData?.jobs || [];

    const handleFileUpload = useCallback(async (e) => {
        e.preventDefault();
        if (!file) return;

        setIsUploading(true);
        try {
            const res = await uploadIngestionFile(file);
            toast({
                title: 'Document ingested',
                description: `${res.data?.filename || file.name} stored as job ${res.data?.job_id || ''}.`,
                variant: 'success',
            });
            setFile(null);
            e.target.reset?.();
            refetchJobs();
        } catch (error) {
            toast({
                title: 'Upload failed',
                description: error.response?.data?.detail || error.message,
                variant: 'destructive',
            });
        } finally {
            setIsUploading(false);
        }
    }, [file, toast, refetchJobs]);
    
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
                <h3 style={{ margin: '0 0 10px 0', color: tokens.color?.['text-100'] }}>Ingestion status</h3>
                {jobs.length === 0 ? (
                    <p style={{ color: tokens.color?.['muted-500'], margin: 0 }}>
                        No documents ingested yet. Upload a file to start building the governance corpus.
                    </p>
                ) : (
                    <>
                        <p style={{ color: tokens.color?.['muted-500'], margin: '0 0 4px' }}>
                            Last ingested: <strong style={{ color: tokens.color?.['text-100'] }}>{jobs[0].filename}</strong>
                            {' '}on {new Date(jobs[0].uploaded_at).toLocaleString()}
                        </p>
                        <p style={{ color: tokens.color?.success, margin: '0 0 12px' }}>
                            {jobsData.pending || 0} file{(jobsData.pending || 0) === 1 ? '' : 's'} pending
                            {' '}, {jobsData.total || jobs.length} ingested in total.
                        </p>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                            {jobs.slice(0, 6).map((j) => (
                                <div key={j.job_id} style={{ display: 'flex', justifyContent: 'space-between', gap: 12, fontSize: 12.5, color: tokens.color?.['muted-500'] }}>
                                    <span style={{ color: tokens.color?.['text-100'], overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{j.filename}</span>
                                    <span>{Math.max(1, Math.round((j.size_bytes || 0) / 1024))} KB, by {j.uploaded_by}</span>
                                </div>
                            ))}
                        </div>
                    </>
                )}
            </div>
        </div>
    );
});
IngestionModule.displayName = 'IngestionModule';


// --- 7.5. Sub-Module: HRSD Case Management (Mocked) ---
const CasesModule = memo(() => {
    // CRITICAL API INTEGRATION 4: Fetch HRSD Tickets (Polling for live updates)
    const {
        data: ticketsResp,
        isLoading: isTicketsLoading,
        error: ticketsError,
    } = useApi(getHRSDTickets, [], true, 60000); // Polling every 60 seconds

    // Backend returns { tickets: [...], count }; normalize to an array.
    const tickets = useMemo(() => toArray(ticketsResp), [ticketsResp]);

    // Real distributions derived from the live ticket set (no fabricated series).
    const byAssignee = useMemo(() => countBy(tickets, (t) => t.assigned_agent || t.assigned_to), [tickets]);
    const byPriority = useMemo(() => countBy(tickets, (t) => t.priority), [tickets]);

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