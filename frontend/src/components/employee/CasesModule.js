// Employee portal: raise an HR case and follow it, including the AI first-line
// suggestion and the two buttons that close the loop.
//
// Real endpoints: GET /hrsd/my-tickets, POST /hrsd/tickets,
// GET /knowledge/tickets/{id}, POST /hrsd/tickets/{id}/resolution-feedback.
//
// The suggestion is generated in the background after the case is raised and is
// only attached when the grounded layer answered AND the answer stayed close to
// its sources. Most cases therefore have no suggestion, and that is said plainly
// rather than dressed up as "still thinking", because nothing further is coming.
//
// "This solved it" resolves the case and records the sources that helped, which
// is what makes them rank higher for the next person. "I still need help"
// records an escalation and leaves the case in the normal queue. Neither button
// exists anywhere else, so without this screen the loop could not close.
import React, { memo, useCallback, useEffect, useMemo, useState } from 'react';
import { theme as tokens } from '../../theme';
import { useApi } from '../../hooks/useApi';
import { useToast } from '../../hooks/use-toast';
import {
    getMyHRSDTickets, createHRSDTicket, getTicketSuggestion, submitResolutionFeedback,
} from '../../config/api';
import { ui, Btn, Loading, EmptyState, ErrorNote, StatusPill, fmtDate, EmployeeStyles } from './shared';
import { CountUp } from '../live/LivePrimitives';
import {
    LifeBuoy, Send, Sparkles, ThumbsUp, ThumbsDown, BookOpen, CheckCircle2, Clock,
} from 'lucide-react';

const errText = (e) => e?.response?.data?.detail || e?.message || 'The request failed.';

const isClosed = (status) => /RESOLVED|CLOSED/i.test(String(status || ''));

/** The AI suggestion for one case, loaded only when the case is opened. */
const SuggestionBlock = memo(({ ticketId, status, onResolved }) => {
    const { toast } = useToast();
    const { data, isLoading, error, refetch } = useApi(getTicketSuggestion, [ticketId], Boolean(ticketId));
    const suggestion = data?.suggested_resolution;
    const [busy, setBusy] = useState(null);
    const [answered, setAnswered] = useState(false);

    // The suggestion lands seconds to a minute after the case is raised, so a
    // freshly raised case is polled a few times rather than looking empty
    // forever. Polling stops once something arrives, or after a minute.
    useEffect(() => {
        if (suggestion || isClosed(status)) return undefined;
        let tries = 0;
        const id = setInterval(() => {
            tries += 1;
            if (tries > 6) { clearInterval(id); return; }
            refetch();
        }, 10000);
        return () => clearInterval(id);
    }, [suggestion, status, refetch]);

    const feedback = useCallback(async (helpful) => {
        setBusy(helpful ? 'yes' : 'no');
        try {
            const res = await submitResolutionFeedback(ticketId, helpful);
            const outcome = res.data?.outcome;
            toast({
                title: helpful ? 'Glad that sorted it' : 'Passed to a person',
                description: outcome === 'resolved_by_ai'
                    ? 'Your case is closed, and the sources that helped will be shown sooner to the next person who asks.'
                    : 'Your case stays open and in the queue. What did not work has been recorded.',
                variant: 'success',
            });
            setAnswered(true);
            if (helpful && onResolved) onResolved();
        } catch (err) {
            toast({ title: 'Could not record that', description: errText(err), variant: 'destructive' });
        } finally {
            setBusy(null);
        }
    }, [ticketId, toast, onResolved]);

    if (isLoading) return <Loading label="Checking whether HiRo has a first answer" />;
    if (error) return <ErrorNote error={error} context="the suggested answer" />;

    if (!suggestion) {
        return (
            <p style={{ ...ui.hint, marginTop: 8 }}>
                {isClosed(status)
                    ? 'This case was handled without an automatic first answer.'
                    : 'HiRo had no grounded answer for this one, so it has gone straight to the team rather than guessing. They will pick it up from the queue.'}
            </p>
        );
    }

    return (
        <div style={{
            marginTop: 10, padding: '13px 15px', borderRadius: 9,
            border: `1px solid ${tokens.color?.['accent-primary']}33`,
            background: `${tokens.color?.['accent-primary']}0d`,
        }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
                <span style={{ fontSize: 12.5, fontWeight: 600, color: tokens.color?.['accent-primary'] }}>
                    <Sparkles size={13} style={{ verticalAlign: -2, marginRight: 5 }} />
                    A first answer from HiRo
                </span>
                <span style={{ fontSize: 11, color: tokens.color?.['muted-600'] }}>
                    matched its sources at {Math.round((Number(suggestion.confidence) || 0) * 100)}%
                </span>
            </div>

            <p style={{ margin: '8px 0 0 0', fontSize: 13.5, lineHeight: 1.6, color: tokens.color?.['text-100'] }}>
                {suggestion.text}
            </p>

            {(suggestion.citations || []).length > 0 && (
                <div style={{ marginTop: 10 }}>
                    <div style={{ fontSize: 11, color: tokens.color?.['muted-600'], marginBottom: 5 }}>
                        <BookOpen size={11} style={{ verticalAlign: -1, marginRight: 4 }} />
                        Taken from
                    </div>
                    {suggestion.citations.map((c, i) => (
                        <div key={c.chunk_id || i} style={{ fontSize: 11.5, color: tokens.color?.['muted-600'], padding: '2px 0' }}>
                            [{i + 1}] {c.title}
                        </div>
                    ))}
                </div>
            )}

            {!answered && !isClosed(status) && (
                <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
                    <Btn tone="success" icon={ThumbsUp} loading={busy === 'yes'} disabled={Boolean(busy)}
                        onClick={() => feedback(true)}>That solved it</Btn>
                    <Btn tone="ghost" icon={ThumbsDown} loading={busy === 'no'} disabled={Boolean(busy)}
                        onClick={() => feedback(false)}>I still need help</Btn>
                </div>
            )}
            {(answered || isClosed(status)) && (
                <p style={{ ...ui.hint, marginTop: 10, color: tokens.color?.success }}>
                    Thanks, that has been recorded.
                </p>
            )}
        </div>
    );
});
SuggestionBlock.displayName = 'SuggestionBlock';

const CasesModule = memo(() => {
    const { toast } = useToast();
    const { data, isLoading, error, refetch } = useApi(getMyHRSDTickets, [{ limit: 100 }], true);

    const tickets = useMemo(() => data?.tickets || [], [data]);
    const total = Number(data?.total ?? tickets.length);

    const [form, setForm] = useState({ subject: '', description: '' });
    const [raising, setRaising] = useState(false);
    const [openId, setOpenId] = useState(null);

    const open = tickets.filter((t) => !isClosed(t.status)).length;
    const closed = tickets.length - open;

    const raise = useCallback(async (e) => {
        e.preventDefault();
        const subject = form.subject.trim();
        const description = form.description.trim();
        if (subject.length < 4 || description.length < 10) {
            toast({
                title: 'Add a little more',
                description: 'A short title and a couple of sentences of detail is enough, and it is what HiRo matches against.',
                variant: 'destructive',
            });
            return;
        }
        setRaising(true);
        try {
            // employee_id is set from the signed-in account server-side; nothing
            // the browser sends can raise a case in somebody else's name.
            const res = await createHRSDTicket(subject, description);
            toast({
                title: 'Case raised',
                description: `${res.data?.message || 'It has been passed to the right team.'} HiRo is checking whether it can answer straight away.`,
                variant: 'success',
            });
            setForm({ subject: '', description: '' });
            setOpenId(res.data?.ticket_id || null);
            refetch();
        } catch (err) {
            toast({ title: 'Could not raise that case', description: errText(err), variant: 'destructive' });
        } finally {
            setRaising(false);
        }
    }, [form, toast, refetch]);

    return (
        <div style={ui.grid} className="portal-grid">
            <EmployeeStyles />

            <div style={{ ...ui.panel, gridColumn: 'span 5' }}>
                <h3 style={ui.h3}><LifeBuoy size={16} style={{ verticalAlign: -3, marginRight: 6 }} />Raise a case</h3>
                <p style={ui.hint}>
                    It goes to the team that handles that kind of thing. HiRo also checks the policy corpus first,
                    and if it finds a grounded answer you get it in seconds instead of waiting.
                </p>
                <form onSubmit={raise} style={{ marginTop: 12 }}>
                    <div style={ui.field}>
                        <label style={ui.label} htmlFor="case-subject">What it is about</label>
                        <input id="case-subject" style={ui.input} value={form.subject}
                            placeholder="for example, my travel expense was rejected"
                            onChange={(e) => setForm((p) => ({ ...p, subject: e.target.value }))} />
                    </div>
                    <div style={ui.field}>
                        <label style={ui.label} htmlFor="case-detail">What happened</label>
                        <textarea id="case-detail" style={{ ...ui.input, minHeight: 110, resize: 'vertical' }}
                            value={form.description}
                            placeholder="The more specific you are, the better the first answer will be."
                            onChange={(e) => setForm((p) => ({ ...p, description: e.target.value }))} />
                    </div>
                    <Btn type="submit" tone="success" icon={Send} loading={raising}
                        disabled={form.subject.trim().length < 4 || form.description.trim().length < 10}>
                        Raise the case
                    </Btn>
                </form>

                {tickets.length > 0 && (
                    <div style={{ display: 'flex', gap: 20, marginTop: 18, paddingTop: 14, borderTop: `1px solid ${tokens.color?.['border-600']}`, flexWrap: 'wrap' }}>
                        <div>
                            <div style={{ fontSize: 20, fontWeight: 640, color: tokens.color?.warning }}><CountUp value={open} /></div>
                            <div style={{ fontSize: 11.5, color: tokens.color?.['muted-600'] }}>still open</div>
                        </div>
                        <div>
                            <div style={{ fontSize: 20, fontWeight: 640, color: tokens.color?.success }}><CountUp value={closed} /></div>
                            <div style={{ fontSize: 11.5, color: tokens.color?.['muted-600'] }}>sorted</div>
                        </div>
                    </div>
                )}
            </div>

            <div style={{ ...ui.panel, gridColumn: 'span 7' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
                    <h3 style={ui.h3}>Your cases</h3>
                    {total > tickets.length && (
                        <span style={{ ...ui.hint, margin: 0 }}>Showing the {tickets.length} most recent of {total.toLocaleString()}</span>
                    )}
                </div>
                <p style={ui.hint}>Only your own cases. Open one to read the first answer and tell HiRo whether it helped.</p>

                {isLoading && <Loading label="Reading your cases" />}
                <ErrorNote error={error} context="your cases" />
                {!isLoading && !error && tickets.length === 0 && (
                    <EmptyState icon={LifeBuoy} title="You have not raised a case"
                        action="Use the form on the left when something needs HR or IT. Everything you raise stays listed here." />
                )}

                <div className="emp-scroll" style={{ ...ui.scroller('560px'), marginTop: tickets.length ? 8 : 0 }}>
                    {tickets.map((t) => {
                        const isOpen = openId === t.ticket_id;
                        return (
                            <div key={t.ticket_id} style={{ padding: '12px 0', borderBottom: `1px solid ${tokens.color?.['border-600']}` }}>
                                <button type="button" onClick={() => setOpenId(isOpen ? null : t.ticket_id)}
                                    style={{
                                        display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 10,
                                        width: '100%', background: 'transparent', border: 'none', padding: 0,
                                        cursor: 'pointer', textAlign: 'left', flexWrap: 'wrap',
                                    }}>
                                    <span style={{ minWidth: 0 }}>
                                        <span style={{ display: 'block', fontSize: 13, fontWeight: 550, color: tokens.color?.['text-100'] }}>
                                            {t.subject}
                                        </span>
                                        <span style={{ display: 'block', fontSize: 11.5, color: tokens.color?.['muted-600'], marginTop: 2 }}>
                                            {isClosed(t.status)
                                                ? <><CheckCircle2 size={11} style={{ verticalAlign: -1, marginRight: 4 }} />Sorted</>
                                                : <><Clock size={11} style={{ verticalAlign: -1, marginRight: 4 }} />With the team</>}
                                            {', raised '}{fmtDate(t.created_at)}
                                        </span>
                                    </span>
                                    <StatusPill status={t.status} />
                                </button>

                                {isOpen && (
                                    <div style={{ marginTop: 8 }}>
                                        {t.description && (
                                            <p style={{ margin: 0, fontSize: 12.5, lineHeight: 1.55, color: tokens.color?.['muted-600'] }}>
                                                {t.description}
                                            </p>
                                        )}
                                        <SuggestionBlock ticketId={t.ticket_id} status={t.status} onResolved={refetch} />
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            </div>
        </div>
    );
});

CasesModule.displayName = 'CasesModule';
export default CasesModule;
