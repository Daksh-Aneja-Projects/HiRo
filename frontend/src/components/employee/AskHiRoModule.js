// Employee portal: grounded question answering over the real policy and
// knowledge corpus, plus the notification preferences that decide what HiRo is
// allowed to tell you.
//
// Real endpoints: POST /knowledge/ask (local model, slow: uses the long
// timeout), GET|PUT /me/notification-preferences.
//
// The answer path deliberately has two outcomes and both are shown as they come
// back. "answered" carries citations that name the source each claim came from.
// "refused" means the retrieved sources did not cover the question, and is
// rendered as a real answer in its own right rather than being retried,
// softened or padded out with something the model made up.
import React, { memo, useCallback, useMemo, useState } from 'react';
import { theme as tokens } from '../../theme';
import { useApi } from '../../hooks/useApi';
import { useToast } from '../../hooks/use-toast';
import { askKnowledgeQuestion, getNotificationPreferences, updateNotificationPreferences } from '../../config/api';
import { ui, Btn, Loading, ErrorNote, EmployeeStyles } from './shared';
import { Sparkles, Send, BookOpen, ShieldQuestion, Bell, Save, Quote } from 'lucide-react';

const errText = (e) => e?.response?.data?.detail || e?.message || 'The request failed.';

// The backend keys preferences by short kind names. Each one is described by
// what it actually stops arriving, not by its enum.
const KIND_COPY = {
    leave: { label: 'Leave decisions', detail: 'When a leave request of yours is approved or rejected.' },
    timesheet: { label: 'Timesheet decisions', detail: 'When a submitted timesheet is signed off or sent back.' },
    expense: { label: 'Expense decisions', detail: 'When an expense claim is settled or refused.' },
    approval: { label: 'Approvals waiting on you', detail: 'When something needs a decision from you.' },
    case: { label: 'HR case updates', detail: 'When a case you raised moves on or is resolved.' },
    policy: { label: 'Policy changes', detail: 'When a policy that applies to you is changed or replaced.' },
    onboarding: { label: 'Onboarding progress', detail: 'When a step on an onboarding plan is completed.' },
    performance: { label: 'Performance and reviews', detail: 'When a review cycle needs you, or a rating is ready.' },
};

/* -------------------------------------------------------------------------- */
/* Grounded question answering                                                 */
/* -------------------------------------------------------------------------- */
const AskPanel = memo(() => {
    const [question, setQuestion] = useState('');
    const [asking, setAsking] = useState(false);
    const [result, setResult] = useState(null);
    const [failed, setFailed] = useState(null);
    const [asked, setAsked] = useState('');

    const ask = useCallback(async (e) => {
        e.preventDefault();
        const q = question.trim();
        if (q.length < 5) return;
        setAsking(true);
        setFailed(null);
        setResult(null);
        setAsked(q);
        try {
            const res = await askKnowledgeQuestion(q);
            setResult(res.data);
        } catch (err) {
            setFailed(errText(err));
        } finally {
            setAsking(false);
        }
    }, [question]);

    const refused = result?.status === 'refused';

    return (
        <div style={{ ...ui.panel, gridColumn: 'span 7' }}>
            <h3 style={ui.h3}><Sparkles size={16} style={{ verticalAlign: -3, marginRight: 6 }} />Ask HiRo</h3>
            <p style={ui.hint}>
                Answers are built only from the policies and handover notes actually held in HiRo, and every
                claim is shown with the source it came from. If those sources do not cover your question, HiRo
                says so instead of guessing.
            </p>

            <form onSubmit={ask} style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
                <input style={{ ...ui.input, flex: '1 1 240px' }} value={question}
                    placeholder="for example, how do I claim back travel to a client site"
                    onChange={(e) => setQuestion(e.target.value)} />
                <Btn type="submit" icon={Send} loading={asking} disabled={question.trim().length < 5}>Ask</Btn>
            </form>

            {asking && <Loading label="Reading the policy corpus and drafting a grounded answer, this takes a moment" />}

            {failed && <div style={{ marginTop: 12 }}><ErrorNote error={failed} context="an answer" /></div>}

            {result && !asking && (
                <div style={{ marginTop: 14 }}>
                    <div style={{ fontSize: 11.5, color: tokens.color?.['muted-600'], marginBottom: 6 }}>
                        You asked: {asked}
                    </div>

                    {refused ? (
                        <div style={{
                            display: 'flex', gap: 10, padding: '13px 15px', borderRadius: 9,
                            border: `1px solid ${tokens.color?.warning}33`, background: `${tokens.color?.warning}0d`,
                        }}>
                            <ShieldQuestion size={17} color={tokens.color?.warning} style={{ flexShrink: 0, marginTop: 1 }} />
                            <div style={{ minWidth: 0 }}>
                                <div style={{ fontSize: 13.5, fontWeight: 550, color: tokens.color?.['text-100'] }}>
                                    HiRo does not have a grounded answer for this
                                </div>
                                <p style={{ ...ui.hint, marginTop: 4 }}>
                                    {result.reason || 'The sources retrieved do not cover this question.'} Rather than
                                    write something plausible, HiRo has left it unanswered. Raising an HR case is the
                                    reliable next step, and the answer will be added to the corpus.
                                </p>
                            </div>
                        </div>
                    ) : (
                        <div style={{
                            padding: '13px 15px', borderRadius: 9,
                            border: `1px solid ${tokens.color?.success}33`, background: `${tokens.color?.success}0d`,
                        }}>
                            <p style={{ margin: 0, fontSize: 13.5, lineHeight: 1.6, color: tokens.color?.['text-100'] }}>
                                {result.answer}
                            </p>
                        </div>
                    )}

                    {(result.citations || []).length > 0 && (
                        <div style={{ marginTop: 12 }}>
                            <div style={{ fontSize: 11.5, color: tokens.color?.['muted-600'], marginBottom: 6 }}>
                                <BookOpen size={12} style={{ verticalAlign: -2, marginRight: 4 }} />
                                Where this came from
                            </div>
                            {result.citations.map((c, i) => (
                                <div key={c.chunk_id || i} style={{
                                    padding: '9px 11px', borderRadius: 7, marginBottom: 6,
                                    border: `1px solid ${tokens.color?.['border-600']}`, background: 'var(--bg-input)',
                                }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
                                        <span style={{ fontSize: 12.5, fontWeight: 550, color: tokens.color?.['text-100'] }}>
                                            [{i + 1}] {c.title}
                                        </span>
                                        <span style={{ fontSize: 11, color: tokens.color?.['muted-600'], flexShrink: 0 }}>
                                            {Math.round((Number(c.score) || 0) * 100)}% match
                                        </span>
                                    </div>
                                    {c.snippet && (
                                        <p style={{ margin: '5px 0 0 0', fontSize: 12, lineHeight: 1.5, color: tokens.color?.['muted-600'] }}>
                                            <Quote size={11} style={{ verticalAlign: -1, marginRight: 3 }} />
                                            {c.snippet}
                                        </p>
                                    )}
                                </div>
                            ))}
                        </div>
                    )}

                    {result.confidence != null && (
                        <p style={{ ...ui.hint, marginTop: 8 }}>
                            Strongest source matched this question at {Math.round(Number(result.confidence) * 100)}%.
                        </p>
                    )}
                </div>
            )}
        </div>
    );
});
AskPanel.displayName = 'AskPanel';

/* -------------------------------------------------------------------------- */
/* Notification preferences                                                    */
/* -------------------------------------------------------------------------- */
const NotificationPrefsPanel = memo(() => {
    const { toast } = useToast();
    const { data, isLoading, error, refetch } = useApi(getNotificationPreferences, [], true);
    const saved = useMemo(() => data?.kinds || {}, [data]);

    const [pending, setPending] = useState(null);
    const [saving, setSaving] = useState(false);

    const kinds = pending || saved;
    const dirty = pending !== null && Object.keys(saved).some((k) => saved[k] !== pending[k]);

    const toggle = (k) => setPending({ ...kinds, [k]: !kinds[k] });

    const save = useCallback(async () => {
        setSaving(true);
        try {
            await updateNotificationPreferences(kinds);
            toast({ title: 'Preferences saved', description: 'HiRo will only send you the kinds you left switched on.', variant: 'success' });
            setPending(null);
            refetch();
        } catch (err) {
            toast({ title: 'Could not save your preferences', description: errText(err), variant: 'destructive' });
        } finally {
            setSaving(false);
        }
    }, [kinds, toast, refetch]);

    const entries = Object.keys(saved);

    return (
        <div style={{ ...ui.panel, gridColumn: 'span 5' }}>
            <h3 style={ui.h3}><Bell size={16} style={{ verticalAlign: -3, marginRight: 6 }} />What HiRo tells you</h3>
            <p style={ui.hint}>
                Switching one off stops that kind of notification being created at all, not just hidden. Decisions
                still happen and are still recorded; you simply are not pinged about them.
            </p>

            {isLoading && <Loading label="Reading your preferences" />}
            <ErrorNote error={error} context="your notification preferences" />

            <div style={{ marginTop: entries.length ? 10 : 0 }}>
                {entries.map((k) => {
                    const copy = KIND_COPY[k] || { label: k.replace(/_/g, ' '), detail: '' };
                    const on = Boolean(kinds[k]);
                    return (
                        <label key={k} style={{
                            display: 'flex', alignItems: 'flex-start', gap: 10, padding: '10px 0', cursor: 'pointer',
                            borderBottom: `1px solid ${tokens.color?.['border-600']}`,
                        }}>
                            <input type="checkbox" checked={on} onChange={() => toggle(k)}
                                style={{ marginTop: 3, accentColor: tokens.color?.['accent-primary'], flexShrink: 0 }} />
                            <span style={{ minWidth: 0 }}>
                                <span style={{
                                    display: 'block', fontSize: 13, fontWeight: 500,
                                    color: on ? tokens.color?.['text-100'] : tokens.color?.['muted-600'],
                                }}>{copy.label}</span>
                                <span style={{ display: 'block', fontSize: 11.5, color: tokens.color?.['muted-600'], marginTop: 2, lineHeight: 1.45 }}>
                                    {copy.detail}
                                </span>
                            </span>
                        </label>
                    );
                })}
            </div>

            {entries.length > 0 && (
                <div style={{ marginTop: 14 }}>
                    <Btn tone="success" icon={Save} loading={saving} disabled={!dirty} onClick={save}>
                        {dirty ? 'Save these preferences' : 'Nothing changed yet'}
                    </Btn>
                </div>
            )}
        </div>
    );
});
NotificationPrefsPanel.displayName = 'NotificationPrefsPanel';

const AskHiRoModule = memo(() => (
    <div style={ui.grid} className="portal-grid">
        <EmployeeStyles />
        <AskPanel />
        <NotificationPrefsPanel />
    </div>
));
AskHiRoModule.displayName = 'AskHiRoModule';

export { NotificationPrefsPanel };
export default AskHiRoModule;
