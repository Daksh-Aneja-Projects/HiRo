// Manager portal: Hiring module.
// Real endpoints: GET/POST /api/mss/hiring/requisitions and
// POST /api/talent/job-description/generate (local model). Nothing is fabricated
// when there are no requisitions yet.
import React, { memo, useCallback, useMemo, useState } from 'react';
import { theme as tokens } from '../../theme';
import { useApi } from '../../hooks/useApi';
import { useToast } from '../../hooks/use-toast';
import { getRequisitions, createRequisition, generateJobDescription } from '../../config/api';
import DataCard from '../DataCard';
import { CountUp } from '../live/LivePrimitives';
import { ui, Btn, Loading, EmptyState, ErrorNote, StatusPill, fmtDate, EmployeeStyles } from '../employee/shared';
import { Briefcase, Building2, Users, Send, Sparkles, FileText } from 'lucide-react';
import HiringPipeline from './HiringPipeline';

const SENIORITIES = ['', 'Junior', 'Mid-Level', 'Senior', 'Lead', 'Principal'];
const BLANK = { title: '', department: '', headcount: '1', seniority: '', justification: '' };

// Turns the model's structured draft into one editable block of text.
const draftToText = (d) => [
    d.title,
    '',
    d.summary,
    '',
    'What you will do:',
    ...(d.responsibilities || []).map((r) => `- ${r}`),
    '',
    'What we are looking for:',
    ...(d.requirements || []).map((r) => `- ${r}`),
    ...(Array.isArray(d.nice_to_have) && d.nice_to_have.length
        ? ['', 'Nice to have:', ...d.nice_to_have.map((r) => `- ${r}`)]
        : []),
].filter((line) => line !== undefined && line !== null).join('\n');

const HiringModule = memo(() => {
    const { toast } = useToast();
    const { data: resp, isLoading, error, refetch } = useApi(getRequisitions, [], true);
    const requisitions = useMemo(() => resp?.requisitions || [], [resp]);

    const [form, setForm] = useState(BLANK);
    const [jdDraft, setJdDraft] = useState('');
    const [isDrafting, setIsDrafting] = useState(false);
    const [isSubmitting, setIsSubmitting] = useState(false);
    // Which requisition the pipeline below is working on.
    const [selectedId, setSelectedId] = useState(null);
    const selected = useMemo(
        () => requisitions.find((r) => r.requisition_id === selectedId) || null,
        [requisitions, selectedId],
    );

    const set = (key) => (e) => setForm((prev) => ({ ...prev, [key]: e.target.value }));

    const headcountNum = Number(form.headcount);
    const valid = form.title.trim() !== '' && Number.isFinite(headcountNum) && headcountNum >= 1;

    const openCount = requisitions.filter((r) => String(r.status).toUpperCase() === 'OPEN').length;
    const totalHeadcount = requisitions.reduce((sum, r) => sum + (Number(r.headcount) || 0), 0);
    const departments = new Set(requisitions.map((r) => r.department).filter(Boolean)).size;

    const handleDraft = useCallback(async () => {
        if (!form.title.trim()) {
            toast({ title: 'Give the role a title first', description: 'The model needs at least a job title to draft from.', variant: 'destructive' });
            return;
        }
        setIsDrafting(true);
        try {
            const res = await generateJobDescription({
                title: form.title.trim(),
                department: form.department.trim(),
                seniority: form.seniority,
            });
            setJdDraft(draftToText(res.data || {}));
            toast({ title: 'Draft ready', description: 'The local model wrote a first draft below. Edit it before you use it.', variant: 'success' });
        } catch (err) {
            toast({ title: 'Could not draft the description', description: err.response?.data?.detail || err.message, variant: 'destructive' });
        } finally {
            setIsDrafting(false);
        }
    }, [form.title, form.department, form.seniority, toast]);

    const handleSubmit = useCallback(async (e) => {
        e.preventDefault();
        if (!valid) {
            toast({ title: 'Check the form first', description: 'Give the role a title and a headcount of at least one.', variant: 'destructive' });
            return;
        }
        setIsSubmitting(true);
        try {
            const res = await createRequisition({
                title: form.title.trim(),
                department: form.department.trim(),
                headcount: headcountNum,
                seniority: form.seniority,
                justification: form.justification.trim(),
            });
            const ref = res.data?.requisition?.requisition_id;
            toast({
                title: 'Requisition opened',
                description: `${form.title.trim()} is now open${ref ? `, reference ${ref}` : ''}. HR can see it straight away.`,
                variant: 'success',
            });
            setForm(BLANK);
            refetch();
        } catch (err) {
            toast({ title: 'Could not open the requisition', description: err.response?.data?.detail || err.message, variant: 'destructive' });
        } finally {
            setIsSubmitting(false);
        }
    }, [valid, form, headcountNum, toast, refetch]);

    return (
        <div style={ui.grid} className="portal-grid">
            <EmployeeStyles />

            <div style={{ gridColumn: 'span 4' }}>
                <DataCard title="Open requisitions" value={<CountUp value={openCount} />} unit="roles"
                    icon={<Briefcase size={15} />} color={tokens.color?.['accent-primary']}
                    subtitle={requisitions.length === openCount
                        ? 'Everything raised is still open'
                        : `${requisitions.length} raised in total`} />
            </div>
            <div style={{ gridColumn: 'span 4' }}>
                <DataCard title="People being hired for" value={<CountUp value={totalHeadcount} />} unit="positions"
                    icon={<Users size={15} />} color={tokens.color?.success}
                    subtitle="Total headcount across all requisitions" />
            </div>
            <div style={{ gridColumn: 'span 4' }}>
                <DataCard title="Departments hiring" value={<CountUp value={departments} />} unit="departments"
                    icon={<Building2 size={15} />} color={tokens.color?.['accent-secondary']} />
            </div>

            <div style={{ ...ui.panel, gridColumn: 'span 5' }}>
                <h3 style={ui.h3}>Open a hiring requisition</h3>
                <p style={ui.hint}>Describe the role you need. Once opened, the requisition is visible to HR immediately.</p>

                <form onSubmit={handleSubmit} style={{ marginTop: tokens.spacing?.md }}>
                    <div style={ui.field}>
                        <label style={ui.label} htmlFor="req-title">Role title</label>
                        <input id="req-title" style={ui.input} placeholder="For example Senior Data Engineer"
                            value={form.title} onChange={set('title')} />
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: tokens.spacing?.sm }}>
                        <div style={ui.field}>
                            <label style={ui.label} htmlFor="req-dept">Department</label>
                            <input id="req-dept" style={ui.input} placeholder="For example Engineering"
                                value={form.department} onChange={set('department')} />
                        </div>
                        <div style={ui.field}>
                            <label style={ui.label} htmlFor="req-count">Headcount</label>
                            <input id="req-count" type="number" min="1" step="1" style={ui.input}
                                value={form.headcount} onChange={set('headcount')} />
                        </div>
                    </div>
                    <div style={ui.field}>
                        <label style={ui.label} htmlFor="req-seniority">Seniority</label>
                        <select id="req-seniority" style={ui.input} value={form.seniority} onChange={set('seniority')}>
                            {SENIORITIES.map((s) => <option key={s} value={s}>{s || 'Not specified'}</option>)}
                        </select>
                    </div>
                    <div style={ui.field}>
                        <label style={ui.label} htmlFor="req-why">Why the role is needed</label>
                        <textarea id="req-why" style={{ ...ui.input, minHeight: 70, resize: 'vertical' }}
                            placeholder="For example the data platform team has doubled its workload this quarter"
                            value={form.justification} onChange={set('justification')} />
                    </div>

                    <div style={{ display: 'flex', gap: tokens.spacing?.sm, flexWrap: 'wrap' }}>
                        <Btn type="button" tone="ghost" icon={Sparkles} loading={isDrafting}
                            disabled={!form.title.trim() || isSubmitting} onClick={handleDraft}>
                            Draft job description with AI
                        </Btn>
                        <Btn type="submit" tone="success" icon={Send} loading={isSubmitting} disabled={!valid || isDrafting}>
                            Open requisition
                        </Btn>
                    </div>
                </form>

                {isDrafting && <div style={{ marginTop: tokens.spacing?.sm }}><Loading label="The local model is writing a first draft, this can take a minute" /></div>}

                {jdDraft && (
                    <div style={{ marginTop: tokens.spacing?.md }}>
                        <label style={ui.label} htmlFor="req-jd">Job description draft, written by the local model</label>
                        <textarea id="req-jd" style={{ ...ui.input, minHeight: 220, resize: 'vertical', lineHeight: 1.55 }}
                            value={jdDraft} onChange={(e) => setJdDraft(e.target.value)} />
                        <p style={ui.hint}>
                            Edit the draft here and copy it into your job posting. It is not stored with the requisition.
                        </p>
                    </div>
                )}
            </div>

            <div style={{ ...ui.panel, gridColumn: 'span 7' }}>
                <h3 style={ui.h3}>Requisitions on record</h3>
                <p style={ui.hint}>Every requisition raised, newest first, with its current state.</p>

                {isLoading && requisitions.length === 0 && <Loading label="Reading the requisitions" />}
                <ErrorNote error={error} context="the hiring requisitions" />
                {!isLoading && !error && requisitions.length === 0 && (
                    <EmptyState icon={Briefcase} title="No hiring requisitions yet"
                        action="Open the first one with the form on the left. HR sees it the moment it is raised." />
                )}

                {requisitions.length > 0 && (
                    <>
                        <p style={ui.hint}>Choose one to see who internally could do the job, and to work its candidate pipeline.</p>
                        <div className="emp-scroll" style={{ ...ui.scroller('420px'), marginTop: tokens.spacing?.sm }}>
                            {requisitions.map((r) => {
                                const chosen = r.requisition_id === selectedId;
                                return (
                                    <button key={r.requisition_id} type="button"
                                        onClick={() => setSelectedId(chosen ? null : r.requisition_id)}
                                        style={{
                                            ...ui.listRow, alignItems: 'flex-start', width: '100%', textAlign: 'left',
                                            cursor: 'pointer', border: 'none', borderRadius: 7,
                                            borderBottom: `1px solid ${tokens.color?.['border-600']}`,
                                            background: chosen ? `${tokens.color?.['accent-primary']}12` : 'transparent',
                                        }}>
                                        <div style={ui.rowMain}>
                                            <span style={{ ...ui.rowTitle, color: chosen ? tokens.color?.['accent-primary'] : undefined }}>
                                                {r.title}{r.seniority ? `, ${r.seniority}` : ''}
                                            </span>
                                            <span style={ui.rowMeta}>
                                                {r.department || 'No department given'}, {Number(r.headcount) || 1} position{Number(r.headcount) === 1 ? '' : 's'},
                                                opened {fmtDate(r.created_at)}
                                            </span>
                                            {r.justification && (
                                                <span style={{ ...ui.rowMeta, display: 'flex', gap: 5, alignItems: 'flex-start' }}>
                                                    <FileText size={12} style={{ flexShrink: 0, marginTop: 2 }} />
                                                    <span>{r.justification}</span>
                                                </span>
                                            )}
                                        </div>
                                        <StatusPill status={r.status} />
                                    </button>
                                );
                            })}
                        </div>
                    </>
                )}
            </div>

            <HiringPipeline requisition={selected} />
        </div>
    );
});

HiringModule.displayName = 'HiringModule';
export default HiringModule;
