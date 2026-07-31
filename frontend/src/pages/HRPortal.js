// /frontend/src/pages/HRPortal.js - FINAL PRODUCTION-READY REPLACEMENT
import React, { useMemo, memo, useState, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import { theme as tokens } from '../theme';

// CRITICAL API IMPORTS
import {
    getHRSDTickets, createHRSDTicket, getEmployeeCompensation,
    updateEmployeeCompensation,
    uploadIngestionFile, getIngestionJobs, getAnalyticsCharts,
    getWFPProjections, put
} from '../config/api';
import { useApi } from '../hooks/useApi';
import { useToast } from '../hooks/use-toast';

// UI COMPONENTS (Assume these exist and are stable)
import DataCard from '../components/DataCard';
import BarChartWidget from '../components/charts/BarChartWidget';
import { countBy, toArray } from '../utils/chartData';
import {
    DollarSign, Users, FileText, Briefcase,
    Search, Loader2, AlertTriangle, CheckCircle, CheckCircle2, Shield,
    Ticket, MessageSquarePlus, ClipboardCheck
} from 'lucide-react';
import PolicyGovernanceDashboard from '../components/PolicyGovernanceDashboard';
import HRSDMonitoringDashboard, { ticketStatusText } from '../components/HRSDMonitoringDashboard';
import AuditTraceLog from '../components/AuditTraceLog';
import BPCLPolicyLinter from '../components/BPCLPolicyLinter';
import PolicyLifecycleWorkbench from '../components/policy/PolicyLifecycleWorkbench';
import DAOGovernancePanel from '../components/policy/DAOGovernancePanel';
import { s as ps, dim, apiError } from '../components/policy/ui';


// --- 7.1. Sub-Module: Policy Lifecycle ---
// The whole chain lives in PolicyLifecycleWorkbench: choose a policy, read the
// live version and history, draft, edit, scan, approve, activate, roll back and
// attest to the ledger.
const PolicyModule = memo(() => (
    <div className="policy-module">
        <p style={{ ...ps.hint, marginTop: -4 }}>
            Draft a policy, get it signed off, put it live, and leave a tamper-evident record of every step.
        </p>
        <PolicyLifecycleWorkbench />
    </div>
));
PolicyModule.displayName = 'PolicyModule';

// --- Sub-Module: Compliance posture ---
const ComplianceModule = memo(() => (
    <div className="compliance-module">
        <p style={{ ...ps.hint, marginTop: -4 }}>
            How the enforcement engine has been judging real transactions against the live policy set.
        </p>
        <PolicyGovernanceDashboard />
    </div>
));
ComplianceModule.displayName = 'ComplianceModule';

// --- Sub-Module: Rule compiler and linter ---
const RulesModule = memo(() => (
    <div className="rules-module">
        <p style={{ ...ps.hint, marginTop: -4 }}>
            Turn a sentence of plain English into an enforceable rule, and verify any rule before it ships.
        </p>
        <BPCLPolicyLinter />
    </div>
));
RulesModule.displayName = 'RulesModule';

// --- Sub-Module: DAO governance ---
const GovernanceModule = memo(() => (
    <div className="governance-module">
        <p style={{ ...ps.hint, marginTop: -4 }}>
            Proposals open to the workforce, and your vote on each. Votes are written to the governance ledger.
        </p>
        <DAOGovernancePanel />
    </div>
));
GovernanceModule.displayName = 'GovernanceModule';

// --- Sub-Module: Audit trail ---
const AuditModule = memo(() => (
    <div className="audit-module">
        <p style={{ ...ps.hint, marginTop: -4 }}>
            Every decision the policy engine has recorded, with the reason it gave.
        </p>
        <AuditTraceLog />
    </div>
));
AuditModule.displayName = 'AuditModule';

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


// --- 7.3. Sub-Module: Talent Insights ---
const TalentModule = memo(() => {
    // Real workforce-planning projections (skill gaps per department) + attrition by dept.
    const { data: wfp } = useApi(getWFPProjections, [], true);
    const { data: charts } = useApi(getAnalyticsCharts, [], true);

    // Real succession cover, as a percentage of senior roles with someone ready.
    // This used to be the skills-gap vector subtracted from four, so the two
    // charts on this screen were one number and its inverse, and neither had
    // anything to do with succession.
    const readiness = useMemo(() => Object.entries(wfp?.succession_readiness || {})
        .map(([name, r]) => ({ name, value: Math.round((Number(r?.readiness) || 0) * 100) }))
        .sort((a, b) => b.value - a.value), [wfp]);

    // How many of the skills each department needs are actually held broadly
    // enough. This used to be derived from headcount, with no skills involved.
    const gaps = useMemo(() => (wfp?.skill_gap_detail || [])
        .map((d) => ({ name: d.department, value: (d.skills_needed || 0) - (d.skills_covered || 0) }))
        .sort((a, b) => b.value - a.value), [wfp]);

    const gapDetail = useMemo(() => (wfp?.skill_gap_detail || [])
        .filter((d) => (d.missing_skills || []).length)
        .sort((a, b) => (b.missing_skills?.length || 0) - (a.missing_skills?.length || 0)), [wfp]);

    return (
        <div className="talent-module">
            <h2 style={{ color: tokens.color?.['accent-primary'], marginBottom: tokens.spacing?.lg }}>Talent Insights & Planning</h2>
            <DataCard
                title="Succession cover by department"
                subtitle="Share of senior roles with someone on the rung below ready to step up"
                isChart minHeight="400px">
                <BarChartWidget data={readiness} minHeight="340px" color={tokens.color?.success}
                                label="Percent of senior roles covered" />
            </DataCard>
            <div style={{ display: 'flex', gap: tokens.spacing?.lg, marginTop: tokens.spacing?.lg }}>
                <div style={{ flex: 1 }}>
                    <DataCard
                        title="Skills each department is short of"
                        subtitle="Counted against what the work in that department needs"
                        isChart minHeight="300px">
                        <BarChartWidget data={gaps} minHeight="240px" color={tokens.color?.warning}
                                        label="Number of skills not held broadly enough" />
                    </DataCard>
                </div>
                <div style={{ flex: 1 }}>
                    <DataCard title="Attrition Risk by Department" isChart minHeight="300px">
                        <BarChartWidget data={charts?.attrition_by_department || []} minHeight="240px" color={tokens.color?.danger} />
                    </DataCard>
                </div>
            </div>

            {gapDetail.length > 0 && (
                <div style={{ ...ps.panel, marginTop: tokens.spacing?.lg }}>
                    <h3 style={ps.sectionTitle}>What each department is short of</h3>
                    <p style={ps.hint}>A bar height tells you where to look; this tells you what to do about it.</p>
                    <div style={{ marginTop: 12, display: 'grid', gap: 10 }}>
                        {gapDetail.map((d) => (
                            <div key={d.department} style={{ fontSize: 13, lineHeight: 1.55, color: tokens.color?.['text-100'] }}>
                                <strong>{d.department}</strong>
                                <span style={{ color: tokens.color?.['muted-600'] }}>
                                    {' '}covers {d.skills_covered} of {d.skills_needed}. Short of: {d.missing_skills.join(', ')}.
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
});
TalentModule.displayName = 'TalentModule';

// --- 7.4. Sub-Module: AI Document Ingestion ---
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


// --- 7.5. Sub-Module: HRSD Case Management ---
// Real desk work: raise a case, watch the queue, close a case with a written
// resolution. Field names follow the live HRSD payload (ticket_id / title /
// status / priority / assigned_agent).
const PRIORITY_TEXT = { CRITICAL: 'Critical', HIGH: 'Urgent', MEDIUM: 'Normal', LOW: 'Low' };
const priorityText = (p) => PRIORITY_TEXT[String(p || '').toUpperCase()] || 'Unrated';
const priorityColor = (p) => {
    switch (String(p || '').toUpperCase()) {
        case 'CRITICAL':
        case 'HIGH': return tokens.color?.danger;
        case 'MEDIUM': return tokens.color?.warning;
        default: return tokens.color?.['muted-500'];
    }
};
const isOpenCase = (t) => !['CLOSED', 'RESOLVED'].includes(String(t.status || '').toUpperCase());

const CasesModule = memo(() => {
    const { toast } = useToast();
    const {
        data: ticketsResp,
        isLoading: isTicketsLoading,
        error: ticketsError,
        refetch: refetchTickets,
    } = useApi(getHRSDTickets, [{ limit: 200 }], true, 60000);

    // Backend returns { tickets: [...], count }; normalize to an array.
    const tickets = useMemo(() => toArray(ticketsResp), [ticketsResp]);
    // How many cases exist, as opposed to how many are on this page. These read
    // "38 open of 50 on the desk" while the monitoring panel directly above said
    // 605 open of 808, because the page size was being reported as the total.
    const ticketTotal = Number(ticketsResp?.total) || tickets.length;
    const open = useMemo(() => tickets.filter(isOpenCase), [tickets]);

    const [draft, setDraft] = useState({ subject: '', description: '', employee_id: '' });
    const [creating, setCreating] = useState(false);
    const [resolving, setResolving] = useState('');
    const [summaries, setSummaries] = useState({});
    const [showAll, setShowAll] = useState(false);

    const byAgent = useMemo(() => countBy(open, (t) => t.assigned_agent || t.assigned_to), [open]);
    const byPriority = useMemo(() => countBy(open, (t) => priorityText(t.priority)), [open]);

    const raise = useCallback(async (e) => {
        e.preventDefault();
        if (!draft.subject.trim() || !draft.description.trim() || !draft.employee_id.trim()) {
            toast({ title: 'Fill in every field', description: 'A case needs a subject, a description and the employee it concerns.', variant: 'warning' });
            return;
        }
        setCreating(true);
        try {
            const res = await createHRSDTicket(draft.subject.trim(), draft.description.trim(), draft.employee_id.trim());
            toast({
                title: 'Case raised',
                description: `Case ${res.data?.ticket_id} was created and handed to the triage agents.`,
                variant: 'success',
            });
            setDraft({ subject: '', description: '', employee_id: '' });
            refetchTickets();
        } catch (err) {
            toast({ title: 'Could not raise the case', description: apiError(err), variant: 'destructive' });
        } finally {
            setCreating(false);
        }
    }, [draft, toast, refetchTickets]);

    const resolve = useCallback(async (ticket) => {
        const summary = (summaries[ticket.ticket_id] || '').trim();
        if (!summary) {
            toast({ title: 'Write what you did', description: 'A case can only be closed with a resolution the employee can read.', variant: 'warning' });
            return;
        }
        setResolving(ticket.ticket_id);
        try {
            // The endpoint reads this body as a bare JSON string. api.js wraps it
            // in an object, which the server rejects, so the generic client is
            // used against the same documented route.
            await put(`/hrsd/tickets/${encodeURIComponent(ticket.ticket_id)}/resolve`, summary);
            toast({ title: 'Case closed', description: `${ticket.title || ticket.ticket_id} was closed with your resolution.`, variant: 'success' });
            setSummaries((prev) => ({ ...prev, [ticket.ticket_id]: '' }));
            refetchTickets();
        } catch (err) {
            toast({ title: 'Could not close the case', description: apiError(err), variant: 'destructive' });
        } finally {
            setResolving('');
        }
    }, [summaries, toast, refetchTickets]);

    const visible = showAll ? open : open.slice(0, 12);

    const styles = {
        columns: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(330px, 1fr))', gap: tokens.spacing?.lg, alignItems: 'start' },
        caseCard: (p) => ({
            ...ps.panel,
            borderLeft: `3px solid ${priorityColor(p)}`,
            marginBottom: tokens.spacing?.sm,
        }),
        list: { maxHeight: 520, overflowY: 'auto', paddingRight: 4 },
    };

    return (
        <div className="cases-module">
            <p style={{ ...ps.hint, marginTop: -4 }}>
                Raise a case, see where the queue stands, and close cases with a written resolution.
            </p>

            <HRSDMonitoringDashboard />

            <div style={{ ...styles.columns, marginTop: tokens.spacing?.lg }}>
                <div>
                    <div style={ps.panel}>
                        <h3 style={ps.sectionTitle}><MessageSquarePlus size={16} color={tokens.color?.['accent-primary']} /> Raise a case</h3>
                        <form onSubmit={raise} style={{ marginTop: 12 }}>
                            <label style={ps.label}>What is this about</label>
                            <input style={{ ...ps.input, width: '100%' }} value={draft.subject}
                                   onChange={(e) => setDraft((p) => ({ ...p, subject: e.target.value }))}
                                   placeholder="Short subject, for example: missing overtime payment" />
                            <label style={{ ...ps.label, marginTop: 12 }}>What happened</label>
                            <textarea style={{ ...ps.textarea, minHeight: 100, fontFamily: 'inherit', fontSize: 13.5 }} value={draft.description}
                                      onChange={(e) => setDraft((p) => ({ ...p, description: e.target.value }))}
                                      placeholder="Describe the problem so the triage agent can route it correctly." />
                            <label style={{ ...ps.label, marginTop: 12 }}>Who it concerns</label>
                            <input style={{ ...ps.input, width: '100%' }} value={draft.employee_id}
                                   onChange={(e) => setDraft((p) => ({ ...p, employee_id: e.target.value }))}
                                   placeholder="Employee id, for example EMP-001" />
                            <button type="submit" style={{ ...dim(ps.btn, creating), marginTop: 14 }} disabled={creating}>
                                {creating ? <Loader2 size={15} className="animate-spin" /> : <Ticket size={15} />} Raise the case
                            </button>
                        </form>
                    </div>

                    <div style={{ marginTop: tokens.spacing?.lg }}>
                        <DataCard title="Open cases by triage agent" subtitle={`Across the ${tickets.length.toLocaleString()} most recent cases`} isChart minHeight="260px">
                            <BarChartWidget data={byAgent} minHeight="200px" color={tokens.color?.['accent-primary']} />
                        </DataCard>
                    </div>
                    <div style={{ marginTop: tokens.spacing?.lg }}>
                        <DataCard title="Open cases by urgency" subtitle={`Across the ${tickets.length.toLocaleString()} most recent cases`} isChart minHeight="260px">
                            <BarChartWidget data={byPriority} minHeight="200px" color={tokens.color?.warning} />
                        </DataCard>
                    </div>
                </div>

                <div style={ps.panel}>
                    <div style={{ ...ps.row, justifyContent: 'space-between' }}>
                        <h3 style={ps.sectionTitle}><ClipboardCheck size={16} color={tokens.color?.success} /> Cases still open</h3>
                        <span style={{ fontSize: 12.5, color: tokens.color?.['muted-600'] }}>
                            {open.length.toLocaleString()} open in the {tickets.length.toLocaleString()} most recent
                            {ticketTotal > tickets.length ? ` of ${ticketTotal.toLocaleString()} cases` : ' cases'}
                        </span>
                    </div>

                    {isTicketsLoading && tickets.length === 0 && (
                        <p style={{ ...ps.hint, marginTop: 14 }}><Loader2 size={14} className="animate-spin" /> Loading the case queue...</p>
                    )}
                    {ticketsError && (
                        <p style={{ color: tokens.color?.danger, fontSize: 13, marginTop: 14 }}>The case queue could not be read: {ticketsError}</p>
                    )}
                    {!isTicketsLoading && !ticketsError && open.length === 0 && (
                        <p style={{ ...ps.hint, marginTop: 14 }}>Nothing is open. Raise a case on the left when something needs the desk.</p>
                    )}

                    <div style={{ ...styles.list, marginTop: 14 }}>
                        {visible.map((t) => (
                            <div key={t.ticket_id} style={styles.caseCard(t.priority)}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'baseline' }}>
                                    <strong style={{ fontSize: 13.5, color: tokens.color?.['text-100'] }}>{t.title || 'Untitled case'}</strong>
                                    <span style={{ fontSize: 12, color: priorityColor(t.priority) }}>{priorityText(t.priority)}</span>
                                </div>
                                <p style={{ fontSize: 12.5, color: tokens.color?.['muted-500'], margin: '6px 0 0', lineHeight: 1.6 }}>
                                    {t.description || 'No description was given.'}
                                </p>
                                <p style={{ fontSize: 12, color: tokens.color?.['muted-600'], margin: '6px 0 0' }}>
                                    {ticketStatusText(t.status)}, handled by {t.assigned_agent || 'nobody yet'}
                                    {t.created_at ? `, raised ${new Date(t.created_at).toLocaleDateString()}` : ''}.
                                </p>
                                <div style={{ ...ps.row, marginTop: 10 }}>
                                    <input style={{ ...ps.input, flex: 1, minWidth: 170 }} placeholder="What you did to resolve it"
                                           value={summaries[t.ticket_id] || ''}
                                           onChange={(e) => setSummaries((prev) => ({ ...prev, [t.ticket_id]: e.target.value }))} />
                                    <button type="button" style={dim(ps.btnGhost, resolving === t.ticket_id)}
                                            disabled={resolving === t.ticket_id} onClick={() => resolve(t)}>
                                        {resolving === t.ticket_id ? <Loader2 size={15} className="animate-spin" /> : <CheckCircle2 size={15} color={tokens.color?.success} />} Close
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>

                    {open.length > 12 && (
                        <button type="button" style={{ ...ps.btnGhost, marginTop: 12 }} onClick={() => setShowAll((v) => !v)}>
                            {showAll ? 'Show only the first 12' : `Show all ${open.length.toLocaleString()} open cases`}
                        </button>
                    )}
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
            case 'compliance':
                return <ComplianceModule />;
            case 'rules':
                return <RulesModule />;
            case 'governance':
                return <GovernanceModule />;
            case 'audit':
                return <AuditModule />;
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
        policy: 'Policy Lifecycle',
        compliance: 'Compliance Posture',
        rules: 'Rule Compiler',
        governance: 'Workforce Governance',
        audit: 'Audit Trail',
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