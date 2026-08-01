// HR portal: three review queues that had live endpoints and no screen.
//
// Exit interviews - why people actually left, aggregated across reasons.
// Profile change requests - employee-submitted changes to their own record,
//   approved or refused field by field.
// Knowledge corpus - what the grounded-answer layer can currently answer from,
//   whether the closed feedback loop is working, and the re-index button.
//
// Real endpoints: GET /hr/offboarding/exit-interviews,
// GET /hr/profile-change-requests, POST .../{id}/decide,
// GET /api/knowledge/stats, POST /api/knowledge/sync.
//
// The decide endpoint applies each requested field only where a real column
// exists to write it to, and reports back per field. That per-field result is
// rendered rather than collapsed into "approved", because an approval that
// silently applied half of what was asked for would be a lie.
import React, { memo, useCallback, useMemo, useState } from 'react';
import { theme as tokens } from '../../theme';
import { useApi } from '../../hooks/useApi';
import { useToast } from '../../hooks/use-toast';
import {
    getExitInterviews, getProfileChangeRequests, decideProfileChangeRequest,
    getKnowledgeStats, syncKnowledge,
} from '../../config/api';
import { ui, Btn, Loading, EmptyState, ErrorNote, fmtDate, humanText, EmployeeStyles } from '../employee/shared';
import { CountUp } from '../live/LivePrimitives';
import { useEmployeeNames } from '../manager/roster';
import {
    LogOut, UserCog, BookOpen, CheckCircle, XCircle, RefreshCw, ThumbsUp, ThumbsDown, Database,
} from 'lucide-react';

const errText = (e) => e?.response?.data?.detail || e?.message || 'The request failed.';

// Exit reasons come back as short keys; these are the sentences they stand for.
const REASON_COPY = {
    career_growth: 'No route forward here',
    compensation: 'Pay',
    management: 'Their manager',
    work_life_balance: 'Work and life balance',
    relocation: 'Moving away',
    culture: 'How it feels to work here',
    role_fit: 'The job was not what they wanted',
    other: 'Something else',
};
const reasonLabel = (r) => REASON_COPY[r] || humanText(r);

/* -------------------------------------------------------------------------- */
/* Exit interviews                                                             */
/* -------------------------------------------------------------------------- */
const ExitInterviewsPanel = memo(() => {
    const { data, isLoading, error } = useApi(getExitInterviews, [], true);
    const interviews = useMemo(() => data?.interviews || [], [data]);
    const counts = useMemo(() => data?.reason_counts || {}, [data]);

    const names = useEmployeeNames(useMemo(() => interviews.map((i) => i.employee_uuid), [interviews]));

    const ranked = useMemo(
        () => Object.entries(counts).sort((a, b) => b[1] - a[1]),
        [counts],
    );
    const top = ranked[0]?.[1] || 1;
    const recommend = interviews.filter((i) => i.would_recommend).length;

    return (
        <div style={{ ...ui.panel, gridColumn: 'span 6' }}>
            <h3 style={ui.h3}><LogOut size={16} style={{ verticalAlign: -3, marginRight: 6 }} />Why people left</h3>
            <p style={ui.hint}>Every exit interview submitted, and what the reasons add up to. This is what people said on the way out, not a model&apos;s guess at why.</p>

            {isLoading && <Loading label="Reading the exit interviews" />}
            <ErrorNote error={error} context="the exit interviews" />
            {!isLoading && !error && interviews.length === 0 && (
                <EmptyState icon={LogOut} title="No exit interview has been submitted"
                    action="People completing offboarding are invited to fill one in from their own portal." />
            )}

            {interviews.length > 0 && (
                <>
                    <div style={{ display: 'flex', gap: 20, marginTop: 12, flexWrap: 'wrap' }}>
                        <div>
                            <div style={{ fontSize: 22, fontWeight: 640, color: tokens.color?.['text-100'] }}>
                                <CountUp value={interviews.length} />
                            </div>
                            <div style={{ fontSize: 11.5, color: tokens.color?.['muted-600'] }}>interviews on record</div>
                        </div>
                        <div>
                            <div style={{ fontSize: 22, fontWeight: 640, color: recommend === interviews.length ? tokens.color?.success : tokens.color?.warning }}>
                                <CountUp value={interviews.length ? (recommend / interviews.length) * 100 : 0} decimals={0} suffix="%" />
                            </div>
                            <div style={{ fontSize: 11.5, color: tokens.color?.['muted-600'] }}>would still recommend HiRo</div>
                        </div>
                    </div>

                    {ranked.length > 0 && (
                        <div style={{ marginTop: 16 }}>
                            <div style={{ fontSize: 12, color: tokens.color?.['muted-600'], marginBottom: 7 }}>What they gave as reasons</div>
                            {ranked.map(([reason, n]) => (
                                <div key={reason} style={{ marginBottom: 8 }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12.5, marginBottom: 3 }}>
                                        <span style={{ color: tokens.color?.['text-100'] }}>{reasonLabel(reason)}</span>
                                        <span style={{ color: tokens.color?.['muted-600'] }}>{n}</span>
                                    </div>
                                    <div style={{ height: 6, borderRadius: 3, background: tokens.color?.['border-600'], overflow: 'hidden' }}>
                                        <div style={{
                                            width: `${(n / top) * 100}%`, height: '100%', borderRadius: 3,
                                            background: tokens.color?.danger, opacity: 0.8,
                                            transition: 'width 0.6s cubic-bezier(0.22, 1, 0.36, 1)',
                                        }} />
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}

                    <div className="emp-scroll" style={{ ...ui.scroller('260px'), marginTop: 14 }}>
                        {interviews.map((i) => (
                            <div key={i.interview_id} style={{ padding: '10px 0', borderBottom: `1px solid ${tokens.color?.['border-600']}` }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
                                    <span style={{ fontSize: 12.5, fontWeight: 550, color: tokens.color?.['text-100'] }}>
                                        {names[i.employee_uuid] || 'A leaver'}
                                    </span>
                                    <span style={{ fontSize: 11.5, color: i.would_recommend ? tokens.color?.success : tokens.color?.danger }}>
                                        {i.would_recommend ? 'would recommend' : 'would not recommend'}
                                    </span>
                                </div>
                                <div style={{ fontSize: 11.5, color: tokens.color?.['muted-600'], marginTop: 2 }}>
                                    {(i.reasons || []).map(reasonLabel).join(', ') || 'No reason given'}, {fmtDate(i.submitted_at)}
                                </div>
                                {i.comments && (
                                    <p style={{ margin: '5px 0 0 0', fontSize: 12.5, lineHeight: 1.5, color: tokens.color?.['text-100'] }}>
                                        {i.comments}
                                    </p>
                                )}
                            </div>
                        ))}
                    </div>
                </>
            )}
        </div>
    );
});
ExitInterviewsPanel.displayName = 'ExitInterviewsPanel';

/* -------------------------------------------------------------------------- */
/* Profile change requests                                                     */
/* -------------------------------------------------------------------------- */
const ProfileChangeQueuePanel = memo(() => {
    const { toast } = useToast();
    const { data, isLoading, error, refetch } = useApi(getProfileChangeRequests, [], true);
    const requests = useMemo(() => data?.requests || [], [data]);

    const [comments, setComments] = useState({});
    const [busy, setBusy] = useState(null);
    // Per-field outcomes of the last decision, kept so the refusal reason stays
    // readable after the toast has gone.
    const [outcomes, setOutcomes] = useState({});

    const decide = useCallback(async (req, approve) => {
        setBusy(`${req.request_id}-${approve}`);
        try {
            const res = await decideProfileChangeRequest(req.request_id, approve, (comments[req.request_id] || '').trim());
            // The backend applies each field only where a real column exists and
            // reports back per field: "APPLIED", or a sentence saying why not.
            const results = res.data?.field_results || {};
            const status = res.data?.status;
            const applied = Object.keys(results).filter((k) => results[k] === 'APPLIED');
            const refused = Object.keys(results).filter((k) => results[k] !== 'APPLIED');

            setOutcomes((p) => ({ ...p, [req.request_id]: results }));
            toast({
                title: !approve ? 'Change refused'
                    : status === 'PARTIALLY_APPLIED' ? 'Only part of that change could be applied'
                        : status === 'REFUSED' ? 'Nothing could be applied'
                            : 'Change approved and applied',
                description: !approve
                    ? `${req.username} has been told, and their record is unchanged.`
                    : refused.length === 0
                        ? `${req.username}'s record now holds ${applied.map(humanText).join(', ')}.`
                        : `Applied: ${applied.map(humanText).join(', ') || 'nothing'}. Left unchanged: ${refused.map(humanText).join(', ')}. The reason for each is listed on the request.`,
                variant: approve && refused.length ? 'warning' : 'success',
            });
            setComments((p) => ({ ...p, [req.request_id]: '' }));
            refetch();
        } catch (err) {
            toast({ title: 'Could not record that decision', description: errText(err), variant: 'destructive' });
        } finally {
            setBusy(null);
        }
    }, [comments, toast, refetch]);

    return (
        <div style={{ ...ui.panel, gridColumn: 'span 6' }}>
            <h3 style={ui.h3}><UserCog size={16} style={{ verticalAlign: -3, marginRight: 6 }} />Changes people asked for</h3>
            <p style={ui.hint}>Employees cannot edit their own personnel record directly. They ask, you decide, and an approval writes the change through.</p>

            {isLoading && <Loading label="Reading the queue" />}
            <ErrorNote error={error} context="the profile change queue" />
            {!isLoading && !error && requests.length === 0 && (
                <EmptyState icon={CheckCircle} title="Nothing is waiting on a decision"
                    action="Requests appear here as soon as somebody asks for a change to their own record." />
            )}

            <div className="emp-scroll" style={{ ...ui.scroller('520px'), marginTop: requests.length ? 10 : 0 }}>
                {requests.map((r) => (
                    <div key={r.request_id} style={{ padding: '13px 0', borderBottom: `1px solid ${tokens.color?.['border-600']}` }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
                            <span style={{ fontSize: 13, fontWeight: 550, color: tokens.color?.['text-100'] }}>{r.username}</span>
                            <span style={{ fontSize: 11.5, color: tokens.color?.['muted-600'] }}>asked {fmtDate(r.submitted_at)}</span>
                        </div>

                        <div style={{ marginTop: 7 }}>
                            {Object.entries(r.requested_changes || {}).map(([field, value]) => {
                                const outcome = outcomes[r.request_id]?.[field];
                                const applied = outcome === 'APPLIED';
                                return (
                                    <div key={field} style={{ padding: '3px 0' }}>
                                        <div style={{ display: 'flex', gap: 8, fontSize: 12.5 }}>
                                            <span style={{ color: tokens.color?.['muted-600'], minWidth: 110 }}>{humanText(field)}</span>
                                            <span style={{ color: tokens.color?.['text-100'], wordBreak: 'break-word' }}>
                                                {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                                            </span>
                                        </div>
                                        {outcome && (
                                            <div style={{
                                                fontSize: 11.5, marginTop: 2, paddingLeft: 118, lineHeight: 1.45,
                                                color: applied ? tokens.color?.success : tokens.color?.warning,
                                            }}>
                                                {applied
                                                    ? 'Written to the record.'
                                                    : `Left unchanged. ${String(outcome).replace(/^REFUSED:\s*/, '').replace(/^FAILED:\s*/, 'The write failed: ')}`}
                                            </div>
                                        )}
                                    </div>
                                );
                            })}
                        </div>

                        <input style={{ ...ui.input, marginTop: 8 }} placeholder="Why, in a sentence. The employee sees this."
                            value={comments[r.request_id] || ''}
                            onChange={(e) => setComments((p) => ({ ...p, [r.request_id]: e.target.value }))} />

                        <div style={{ display: 'flex', gap: 7, marginTop: 8, flexWrap: 'wrap' }}>
                            <Btn tone="success" icon={CheckCircle} loading={busy === `${r.request_id}-true`}
                                disabled={Boolean(busy)} onClick={() => decide(r, true)}>Approve and apply</Btn>
                            <Btn tone="danger" icon={XCircle} loading={busy === `${r.request_id}-false`}
                                disabled={Boolean(busy)} onClick={() => decide(r, false)}>Refuse</Btn>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
});
ProfileChangeQueuePanel.displayName = 'ProfileChangeQueuePanel';

/* -------------------------------------------------------------------------- */
/* Knowledge corpus                                                            */
/* -------------------------------------------------------------------------- */
const KnowledgeCorpusPanel = memo(() => {
    const { toast } = useToast();
    const { data, isLoading, error, refetch } = useApi(getKnowledgeStats, [], true);
    const [syncing, setSyncing] = useState(false);

    const corpus = data?.corpus || {};
    const loop = data?.loop || {};
    const bySource = corpus.by_source || {};
    const sources = Object.entries(bySource).sort((a, b) => b[1] - a[1]);
    const total = Number(corpus.total) || 0;
    const helpful = loop.top_helpful_sources || [];

    const sync = useCallback(async () => {
        setSyncing(true);
        try {
            const res = await syncKnowledge();
            const d = res.data || {};
            toast({
                title: 'Corpus re-indexed',
                description: `${Number(d.chunks_indexed ?? d.indexed ?? 0).toLocaleString()} passages are now searchable. Answers reflect this immediately.`,
                variant: 'success',
            });
            refetch();
        } catch (err) {
            toast({ title: 'Could not re-index the corpus', description: errText(err), variant: 'destructive' });
        } finally {
            setSyncing(false);
        }
    }, [toast, refetch]);

    return (
        <div style={{ ...ui.panel, gridColumn: 'span 12' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
                <h3 style={ui.h3}><BookOpen size={16} style={{ verticalAlign: -3, marginRight: 6 }} />What HiRo can answer from</h3>
                <Btn tone="ghost" icon={RefreshCw} loading={syncing} onClick={sync}>Re-index the corpus</Btn>
            </div>
            <p style={ui.hint}>
                Grounded answers are built only from these passages. Anything not indexed here is something HiRo will
                refuse to answer rather than guess at, so the size of this corpus is the ceiling on what it can help with.
            </p>

            {isLoading && <Loading label="Reading the corpus statistics" />}
            <ErrorNote error={error} context="the knowledge corpus statistics" />

            {!isLoading && !error && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: tokens.spacing?.lg, marginTop: 12 }}>
                    <div>
                        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                            <span style={{ fontSize: 28, fontWeight: 650, color: tokens.color?.['accent-primary'] }}>
                                <CountUp value={total} />
                            </span>
                            <span style={{ fontSize: 12, color: tokens.color?.['muted-600'] }}>passages indexed</span>
                        </div>
                        <div style={{ marginTop: 10 }}>
                            {sources.map(([kind, n]) => (
                                <div key={kind} style={{ marginBottom: 7 }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 3 }}>
                                        <span style={{ color: tokens.color?.['text-100'] }}>
                                            <Database size={11} style={{ verticalAlign: -1, marginRight: 4 }} />
                                            {kind === 'policy' ? 'Policy records' : kind === 'knowledge' ? 'Handover notes' : 'Uploaded documents'}
                                        </span>
                                        <span style={{ color: tokens.color?.['muted-600'] }}>{n}</span>
                                    </div>
                                    <div style={{ height: 5, borderRadius: 3, background: tokens.color?.['border-600'], overflow: 'hidden' }}>
                                        <div style={{
                                            width: `${total ? (n / total) * 100 : 0}%`, height: '100%', borderRadius: 3,
                                            background: tokens.color?.['accent-primary'], opacity: 0.8,
                                            transition: 'width 0.6s cubic-bezier(0.22, 1, 0.36, 1)',
                                        }} />
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>

                    <div>
                        <div style={{ fontSize: 12, color: tokens.color?.['muted-600'], marginBottom: 8 }}>
                            Is the loop closing
                        </div>
                        {[
                            ['Cases HiRo suggested a resolution for', loop.suggestions_made, tokens.color?.['accent-primary']],
                            ['Confirmed as the actual fix by a person', loop.solved_by_ai, tokens.color?.success],
                            ['Escalated to a human instead', loop.escalated, tokens.color?.warning],
                        ].map(([label, value, color]) => (
                            <div key={label} style={{ display: 'flex', justifyContent: 'space-between', gap: 8, padding: '6px 0', borderBottom: `1px solid ${tokens.color?.['border-600']}` }}>
                                <span style={{ fontSize: 12.5, color: tokens.color?.['text-100'] }}>{label}</span>
                                <span style={{ fontSize: 13, fontWeight: 600, color, flexShrink: 0 }}>
                                    <CountUp value={Number(value) || 0} />
                                </span>
                            </div>
                        ))}
                        <p style={ui.hint}>
                            Confirmations and rejections feed back into how sources are ranked, so a passage that keeps
                            solving real cases surfaces sooner next time.
                        </p>
                    </div>

                    <div>
                        <div style={{ fontSize: 12, color: tokens.color?.['muted-600'], marginBottom: 8 }}>
                            What has actually helped
                        </div>
                        {helpful.length === 0 ? (
                            <p style={ui.hint}>Nothing has been confirmed helpful yet. Resolve a case with HiRo&apos;s suggestion and it appears here.</p>
                        ) : helpful.map((h, i) => (
                            <div key={i} style={{ display: 'flex', justifyContent: 'space-between', gap: 8, padding: '6px 0', borderBottom: `1px solid ${tokens.color?.['border-600']}` }}>
                                <span style={{ fontSize: 12.5, color: tokens.color?.['text-100'], minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                    {h.title}
                                </span>
                                <span style={{ fontSize: 12, color: tokens.color?.success, flexShrink: 0, whiteSpace: 'nowrap' }}>
                                    <ThumbsUp size={11} style={{ verticalAlign: -1, marginRight: 3 }} />{h.times_helpful}
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
});
KnowledgeCorpusPanel.displayName = 'KnowledgeCorpusPanel';

const PeopleOpsPanel = memo(() => (
    <div style={ui.grid} className="portal-grid">
        <EmployeeStyles />
        <ExitInterviewsPanel />
        <ProfileChangeQueuePanel />
        <KnowledgeCorpusPanel />
    </div>
));
PeopleOpsPanel.displayName = 'PeopleOpsPanel';

export { ExitInterviewsPanel, ProfileChangeQueuePanel, KnowledgeCorpusPanel };
export default PeopleOpsPanel;
