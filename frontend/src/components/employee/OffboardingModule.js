// Employee portal: Offboarding knowledge transfer and exit interview.
// Real endpoints: GET /api/ess/offboarding/knowledge/mine (read-back of what you
// handed over), POST /api/ess/offboarding/knowledge (hand something over), and
// POST /api/ess/offboarding/exit-interview (reasons, comments, would_recommend).
import React, { memo, useCallback, useMemo, useState } from 'react';
import { theme as tokens } from '../../theme';
import { useToast } from '../../hooks/use-toast';
import { useApi } from '../../hooks/useApi';
import { submitOffboardingKnowledge, getMyOffboardingKnowledge, submitExitInterview } from '../../config/api';
import DataCard from '../DataCard';
import { CountUp } from '../live/LivePrimitives';
import { ui, Btn, Loading, EmptyState, ErrorNote, fmtDate, EmployeeStyles } from './shared';
import { Send, BookOpenCheck, Archive, ThumbsUp, ThumbsDown, ClipboardX } from 'lucide-react';

const BLANK = { area: '', notes: '', successor: '' };

const REASONS = [
    { key: 'compensation', label: 'Compensation' },
    { key: 'career_growth', label: 'Career growth' },
    { key: 'management', label: 'Management' },
    { key: 'relocation', label: 'Relocation' },
    { key: 'work_life_balance', label: 'Work-life balance' },
    { key: 'role_fit', label: 'Role fit' },
    { key: 'company_direction', label: 'Company direction' },
    { key: 'retirement', label: 'Retirement' },
    { key: 'other', label: 'Other' },
];

const OffboardingModule = memo(() => {
    const { toast } = useToast();
    const { data: resp, isLoading, error, refetch } = useApi(getMyOffboardingKnowledge, [], true);
    const entries = useMemo(() => resp?.entries || [], [resp]);

    const [form, setForm] = useState(BLANK);
    const [isSubmitting, setIsSubmitting] = useState(false);

    const [reasons, setReasons] = useState([]);
    const [comments, setComments] = useState('');
    const [wouldRecommend, setWouldRecommend] = useState(null);
    const [isSendingInterview, setIsSendingInterview] = useState(false);
    const [interviewSent, setInterviewSent] = useState(false);

    const set = (key) => (e) => setForm((prev) => ({ ...prev, [key]: e.target.value }));
    const toggleReason = (key) => setReasons((prev) => (prev.includes(key) ? prev.filter((r) => r !== key) : [...prev, key]));

    const valid = form.area.trim() !== '' && form.notes.trim().length >= 10;
    const interviewValid = reasons.length > 0 && wouldRecommend !== null;

    const handleSubmit = useCallback(async (e) => {
        e.preventDefault();
        if (!valid) {
            toast({
                title: 'Check the form first',
                description: 'Name what you own and write at least a couple of sentences of handover notes.',
                variant: 'destructive',
            });
            return;
        }
        setIsSubmitting(true);
        const area = form.area.trim();
        const successor = form.successor.trim();
        try {
            await submitOffboardingKnowledge({
                title: area,
                content: form.notes.trim() + (successor ? `\n\nSuggested successor: ${successor}` : ''),
            });
            toast({
                title: 'Handover recorded',
                description: `"${area}" is now in the knowledge base. HR and your successor can read it.`,
                variant: 'success',
            });
            setForm(BLANK);
            refetch();
        } catch (err) {
            toast({ title: 'Could not record the handover', description: err.response?.data?.detail || err.message, variant: 'destructive' });
        } finally {
            setIsSubmitting(false);
        }
    }, [valid, form, toast, refetch]);

    const handleInterview = useCallback(async (e) => {
        e.preventDefault();
        if (!interviewValid) {
            toast({ title: 'A couple of things are missing', description: 'Choose at least one reason and say whether you would recommend HiRo.', variant: 'destructive' });
            return;
        }
        setIsSendingInterview(true);
        try {
            await submitExitInterview({ reasons, comments: comments.trim(), would_recommend: wouldRecommend });
            toast({ title: 'Exit interview submitted', description: 'Thank you for the honest feedback, it goes straight to HR.', variant: 'success' });
            setInterviewSent(true);
        } catch (err) {
            toast({ title: 'Could not submit the exit interview', description: err.response?.data?.detail || err.message, variant: 'destructive' });
        } finally {
            setIsSendingInterview(false);
        }
    }, [interviewValid, reasons, comments, wouldRecommend, toast]);

    return (
        <div style={ui.grid} className="portal-grid">
            <EmployeeStyles />

            <div style={{ gridColumn: 'span 4' }}>
                <DataCard title="Handed over so far" value={<CountUp value={entries.length} />} unit="entries"
                    icon={<BookOpenCheck size={15} />} color={tokens.color?.['accent-primary']}
                    subtitle={entries.length ? 'Each entry is saved in the knowledge base' : 'Nothing recorded yet'} />
            </div>
            <div style={{ gridColumn: 'span 8' }}>
                <DataCard title="Why this matters"
                    value="Knowledge transfer"
                    icon={<Archive size={15} />} color={tokens.color?.['accent-secondary']}
                    subtitle="What you write here is what your team keeps after you leave. One entry per area you own works best: a system, a process, a relationship." />
            </div>

            <div style={{ ...ui.panel, gridColumn: 'span 5' }}>
                <h3 style={ui.h3}>Hand something over</h3>
                <p style={ui.hint}>One entry per thing you own. Say what it is, how it works, and who should take it on.</p>

                <form onSubmit={handleSubmit} style={{ marginTop: tokens.spacing?.md }}>
                    <div style={ui.field}>
                        <label style={ui.label} htmlFor="off-area">What you own</label>
                        <input id="off-area" style={ui.input}
                            placeholder="For example the monthly payroll reconciliation"
                            value={form.area} onChange={set('area')} />
                    </div>
                    <div style={ui.field}>
                        <label style={ui.label} htmlFor="off-notes">Handover notes</label>
                        <textarea id="off-notes" style={{ ...ui.input, minHeight: 120, resize: 'vertical' }}
                            placeholder="How it works, where things live, what goes wrong and how you fix it, who to talk to"
                            value={form.notes} onChange={set('notes')} />
                    </div>
                    <div style={ui.field}>
                        <label style={ui.label} htmlFor="off-successor">Who should take this on</label>
                        <input id="off-successor" style={ui.input}
                            placeholder="Name of a colleague, or leave blank if you are not sure"
                            value={form.successor} onChange={set('successor')} />
                    </div>

                    <Btn type="submit" tone="success" icon={Send} loading={isSubmitting} disabled={!valid}>
                        Record this handover
                    </Btn>
                </form>
            </div>

            <div style={{ ...ui.panel, gridColumn: 'span 7' }}>
                <h3 style={ui.h3}>What you have handed over</h3>

                {isLoading && <Loading label="Reading your handover entries" />}
                <ErrorNote error={error} context="your offboarding knowledge" />
                {!isLoading && !error && entries.length === 0 && (
                    <EmptyState icon={BookOpenCheck} title="Nothing handed over yet"
                        action="Record your first entry on the left. It is saved straight to the knowledge base and appears here." />
                )}

                {entries.length > 0 && (
                    <div className="emp-scroll" style={{ ...ui.scroller('360px'), marginTop: tokens.spacing?.sm }}>
                        {entries.map((h) => (
                            <div key={h.entry_id} style={{ ...ui.listRow, alignItems: 'flex-start' }}>
                                <div style={ui.rowMain}>
                                    <span style={ui.rowTitle}>{h.title || 'Untitled'}</span>
                                    <span style={{ ...ui.rowMeta, whiteSpace: 'normal' }}>{h.content || 'No notes written'}</span>
                                </div>
                                <span style={ui.rowMeta}>{fmtDate(h.submitted_at)}</span>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            <div style={{ ...ui.panel, gridColumn: 'span 12' }}>
                <h3 style={ui.h3}><ClipboardX size={16} style={{ verticalAlign: '-3px', marginRight: 6 }} />Exit interview</h3>
                <p style={ui.hint}>Optional, honest feedback that goes straight to HR. Nothing here affects your final pay or references.</p>

                {interviewSent ? (
                    <p style={{ ...ui.hint, marginTop: tokens.spacing?.sm, color: tokens.color?.success }}>Your exit interview has been recorded. Thank you.</p>
                ) : (
                    <form onSubmit={handleInterview} style={{ marginTop: tokens.spacing?.sm }}>
                        <label style={ui.label}>What led to this decision, choose all that apply</label>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: tokens.spacing?.md }}>
                            {REASONS.map((r) => {
                                const active = reasons.includes(r.key);
                                return (
                                    <button key={r.key} type="button" onClick={() => toggleReason(r.key)}
                                        style={{
                                            padding: '6px 12px', borderRadius: tokens.border?.radius?.full,
                                            border: `1px solid ${active ? tokens.color?.['accent-primary'] : tokens.color?.['border-600']}`,
                                            background: active ? `${tokens.color?.['accent-primary']}18` : 'transparent',
                                            color: active ? tokens.color?.['text-100'] : tokens.color?.['muted-500'],
                                            fontSize: 12.5, cursor: 'pointer',
                                        }}>
                                        {r.label}
                                    </button>
                                );
                            })}
                        </div>

                        <div style={ui.field}>
                            <label style={ui.label} htmlFor="exit-comments">Anything else you would like HR to know</label>
                            <textarea id="exit-comments" style={{ ...ui.input, minHeight: 80, resize: 'vertical' }}
                                placeholder="Optional"
                                value={comments} onChange={(e) => setComments(e.target.value)} />
                        </div>

                        <label style={ui.label}>Would you recommend HiRo as a place to work</label>
                        <div style={{ display: 'flex', gap: 8, marginBottom: tokens.spacing?.md }}>
                            <Btn type="button" tone={wouldRecommend === true ? 'success' : 'ghost'} icon={ThumbsUp} onClick={() => setWouldRecommend(true)}>Yes</Btn>
                            <Btn type="button" tone={wouldRecommend === false ? 'danger' : 'ghost'} icon={ThumbsDown} onClick={() => setWouldRecommend(false)}>No</Btn>
                        </div>

                        <Btn type="submit" icon={Send} loading={isSendingInterview} disabled={!interviewValid}>
                            Submit exit interview
                        </Btn>
                    </form>
                )}
            </div>
        </div>
    );
});

OffboardingModule.displayName = 'OffboardingModule';
export default OffboardingModule;
