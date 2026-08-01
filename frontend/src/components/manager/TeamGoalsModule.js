// Manager portal: the two things a manager does with the review cycle that no
// other screen covers. Left, the goals the team actually committed to, with a
// comment thread the employee can read. Right, the live performance cycle: the
// manager's own rating on each entry, which is what moves the state machine on
// to calibration.
//
// Real endpoints: GET /mss/goals/team, POST /mss/goals/{id}/comment,
// GET /hr/performance/cycles, GET /mss/performance/cycle-entries?cycle_id=,
// POST /mss/performance/review-entry.
import React, { memo, useCallback, useEffect, useMemo, useState } from 'react';
import { theme as tokens } from '../../theme';
import { useApi } from '../../hooks/useApi';
import { useToast } from '../../hooks/use-toast';
import {
    getTeamGoals, commentOnGoal, listPerformanceCycles, getCycleEntries, reviewCycleEntry,
} from '../../config/api';
import { ui, Btn, Loading, EmptyState, ErrorNote, StatusPill, fmtDate, EmployeeStyles } from '../employee/shared';
import { useEmployeeNames } from './roster';
import { Target, MessageSquare, Send, Gauge, CheckCircle, Circle } from 'lucide-react';

const errText = (e) => e?.response?.data?.detail || e?.message || 'The request failed.';

// What the manager can do right now, per cycle stage, in plain English.
const STAGE_COPY = {
    self_assessment: 'The team is still writing self-assessments. You can rate an entry once it arrives.',
    manager_review: 'Your ratings are what this cycle is waiting on.',
    calibration: 'HR is comparing ratings across teams. Your part is done.',
    signed_off: 'Calibrated ratings are out and employees are signing off.',
};

/* -------------------------------------------------------------------------- */
/* Team goals                                                                  */
/* -------------------------------------------------------------------------- */
const TeamGoalsPanel = memo(() => {
    const { toast } = useToast();
    const { data, isLoading, error, refetch } = useApi(getTeamGoals, [], true);
    const goals = useMemo(() => data?.goals || [], [data]);

    const [drafts, setDrafts] = useState({});
    const [busyId, setBusyId] = useState(null);

    // Goal owners and comment authors both need resolving: no screen shows a raw id.
    const names = useEmployeeNames(useMemo(
        () => goals.flatMap((g) => [g.employee_uuid, ...(g.comments || []).map((c) => c.by)]),
        [goals],
    ));

    const comment = useCallback(async (goal) => {
        const text = (drafts[goal.goal_id] || '').trim();
        if (!text) return;
        setBusyId(goal.goal_id);
        try {
            await commentOnGoal(goal.goal_id, text);
            toast({ title: 'Comment added', description: `Left on "${goal.title}". The goal owner can read it.`, variant: 'success' });
            setDrafts((p) => ({ ...p, [goal.goal_id]: '' }));
            refetch();
        } catch (err) {
            toast({ title: 'Could not leave that comment', description: errText(err), variant: 'destructive' });
        } finally {
            setBusyId(null);
        }
    }, [drafts, toast, refetch]);

    return (
        <div style={{ ...ui.panel, gridColumn: 'span 6' }}>
            <h3 style={ui.h3}><Target size={16} style={{ verticalAlign: -3, marginRight: 6 }} />What your team committed to</h3>
            <p style={ui.hint}>Goals your reports set for themselves, with their key results. A comment is visible to the person who owns the goal.</p>

            {isLoading && <Loading label="Reading your team's goals" />}
            <ErrorNote error={error} context="your team's goals" />
            {!isLoading && !error && goals.length === 0 && (
                <EmptyState icon={Target} title="No one on your team has set a goal yet"
                    action="Goals are written by employees in their own portal. Once one exists it shows up here for you to comment on." />
            )}

            <div className="emp-scroll" style={{ ...ui.scroller('420px'), marginTop: goals.length ? 10 : 0 }}>
                {goals.map((g) => {
                    const krs = g.key_results || [];
                    const done = krs.filter((k) => k.done).length;
                    const comments = g.comments || [];
                    return (
                        <div key={g.goal_id} style={{ padding: '12px 0', borderBottom: `1px solid ${tokens.color?.['border-600']}` }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
                                <div style={{ minWidth: 0 }}>
                                    <div style={{ fontSize: 13.5, fontWeight: 550, color: tokens.color?.['text-100'] }}>{g.title}</div>
                                    <div style={ui.rowMeta}>{names[g.employee_uuid] || 'A team member'}</div>
                                </div>
                                <StatusPill status={g.status} />
                            </div>

                            {g.description && <p style={{ ...ui.hint, marginTop: 4 }}>{g.description}</p>}

                            {krs.length > 0 && (
                                <div style={{ marginTop: 7 }}>
                                    <div style={{ fontSize: 11.5, color: tokens.color?.['muted-600'], marginBottom: 4 }}>
                                        {done} of {krs.length} key results done
                                    </div>
                                    {krs.map((k, i) => (
                                        <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 7, padding: '2px 0' }}>
                                            {k.done
                                                ? <CheckCircle size={13} color={tokens.color?.success} style={{ marginTop: 2, flexShrink: 0 }} />
                                                : <Circle size={13} color={tokens.color?.['muted-500']} style={{ marginTop: 2, flexShrink: 0 }} />}
                                            <span style={{
                                                fontSize: 12.5, lineHeight: 1.45,
                                                color: k.done ? tokens.color?.['muted-600'] : tokens.color?.['text-100'],
                                                textDecoration: k.done ? 'line-through' : 'none',
                                            }}>{k.text}</span>
                                        </div>
                                    ))}
                                </div>
                            )}

                            {comments.length > 0 && (
                                <div style={{ marginTop: 8, paddingLeft: 10, borderLeft: `2px solid ${tokens.color?.['border-600']}` }}>
                                    {comments.map((c, i) => (
                                        <div key={i} style={{ marginBottom: 5 }}>
                                            <span style={{ fontSize: 12.5, color: tokens.color?.['text-100'] }}>{c.text}</span>
                                            <span style={{ fontSize: 11, color: tokens.color?.['muted-600'], marginLeft: 7 }}>
                                                {names[c.by] || 'a manager'}, {fmtDate(c.at)}
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            )}

                            <div style={{ display: 'flex', gap: 7, marginTop: 8, flexWrap: 'wrap' }}>
                                <input style={{ ...ui.input, flex: '1 1 180px' }} placeholder="Leave a comment for this person"
                                    value={drafts[g.goal_id] || ''}
                                    onChange={(e) => setDrafts((p) => ({ ...p, [g.goal_id]: e.target.value }))} />
                                <Btn tone="ghost" icon={MessageSquare} loading={busyId === g.goal_id}
                                    disabled={!(drafts[g.goal_id] || '').trim()} onClick={() => comment(g)}>Comment</Btn>
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
});
TeamGoalsPanel.displayName = 'TeamGoalsPanel';

/* -------------------------------------------------------------------------- */
/* Performance cycle review                                                    */
/* -------------------------------------------------------------------------- */
const CycleReviewPanel = memo(() => {
    const { toast } = useToast();
    const { data: cycleData, isLoading: cyclesLoading, error: cyclesError } = useApi(listPerformanceCycles, [], true);
    const cycles = useMemo(() => cycleData?.cycles || [], [cycleData]);

    const [cycleId, setCycleId] = useState('');
    // Default to whichever cycle is actually waiting on a manager, not just the first.
    useEffect(() => {
        if (cycleId || cycles.length === 0) return;
        const waiting = cycles.find((c) => c.stage === 'manager_review') || cycles[0];
        setCycleId(waiting.cycle_id);
    }, [cycles, cycleId]);

    const { data: entryData, isLoading: entriesLoading, error: entriesError, refetch } =
        useApi(getCycleEntries, [cycleId], Boolean(cycleId));
    const entries = useMemo(() => entryData?.entries || [], [entryData]);

    const [drafts, setDrafts] = useState({});
    const [busyId, setBusyId] = useState(null);

    const names = useEmployeeNames(useMemo(() => entries.map((e) => e.employee_uuid), [entries]));
    const cycle = cycles.find((c) => c.cycle_id === cycleId);

    const draftFor = (uuid) => drafts[uuid] || { rating: 3, comments: '' };
    const setDraft = (uuid, patch) => setDrafts((p) => ({ ...p, [uuid]: { ...draftFor(uuid), ...patch } }));

    const submit = useCallback(async (entry) => {
        const d = draftFor(entry.employee_uuid);
        setBusyId(entry.employee_uuid);
        try {
            await reviewCycleEntry({
                cycle_id: cycleId,
                employee_uuid: entry.employee_uuid,
                manager_rating: Number(d.rating),
                manager_comments: d.comments.trim(),
            });
            toast({
                title: 'Rating recorded',
                description: `${names[entry.employee_uuid] || 'That team member'} rated ${d.rating} out of 5 for this cycle.`,
                variant: 'success',
            });
            refetch();
        } catch (err) {
            toast({ title: 'Could not record that rating', description: errText(err), variant: 'destructive' });
        } finally {
            setBusyId(null);
        }
    }, [cycleId, drafts, names, toast, refetch]); // eslint-disable-line react-hooks/exhaustive-deps

    return (
        <div style={{ ...ui.panel, gridColumn: 'span 6' }}>
            <h3 style={ui.h3}><Gauge size={16} style={{ verticalAlign: -3, marginRight: 6 }} />The review cycle</h3>

            {cyclesLoading && <Loading label="Reading the open cycles" />}
            <ErrorNote error={cyclesError} context="the performance cycles" />
            {!cyclesLoading && !cyclesError && cycles.length === 0 && (
                <EmptyState icon={Gauge} title="No performance cycle has been opened"
                    action="HR opens review cycles. Once one is open, your team's entries appear here for you to rate." />
            )}

            {cycles.length > 0 && (
                <>
                    <div style={{ ...ui.field, marginTop: 8 }}>
                        <label style={ui.label} htmlFor="cyc-pick">Cycle</label>
                        <select id="cyc-pick" style={ui.input} value={cycleId} onChange={(e) => setCycleId(e.target.value)}>
                            {cycles.map((c) => (
                                <option key={c.cycle_id} value={c.cycle_id}>
                                    {c.name} ({String(c.stage).replace(/_/g, ' ')})
                                </option>
                            ))}
                        </select>
                    </div>

                    {cycle && (
                        <p style={ui.hint}>
                            {STAGE_COPY[cycle.stage] || 'This cycle is in progress.'}
                            {cycle.closes_at ? ` It closes on ${fmtDate(cycle.closes_at)}.` : ''}
                        </p>
                    )}
                </>
            )}

            {entriesLoading && <Loading label="Reading your team's entries" />}
            <ErrorNote error={entriesError} context="the entries in this cycle" />
            {cycleId && !entriesLoading && !entriesError && entries.length === 0 && (
                <EmptyState icon={Gauge} title="None of your team are in this cycle"
                    action="A cycle covers the people HR included when opening it." />
            )}

            <div className="emp-scroll" style={{ ...ui.scroller('420px'), marginTop: entries.length ? 8 : 0 }}>
                {entries.map((entry) => {
                    const d = draftFor(entry.employee_uuid);
                    const rated = entry.manager_rating != null;
                    return (
                        <div key={entry.employee_uuid} style={{ padding: '12px 0', borderBottom: `1px solid ${tokens.color?.['border-600']}` }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
                                <span style={{ fontSize: 13.5, fontWeight: 550, color: tokens.color?.['text-100'] }}>
                                    {names[entry.employee_uuid] || 'A team member'}
                                </span>
                                {rated && (
                                    <span style={{ fontSize: 12.5, color: tokens.color?.success, fontWeight: 550 }}>
                                        You rated {entry.manager_rating} out of 5
                                    </span>
                                )}
                            </div>

                            {entry.self_assessment ? (
                                <div style={{ marginTop: 6, padding: '8px 10px', borderRadius: 7, background: 'var(--bg-input)' }}>
                                    <div style={{ fontSize: 11, color: tokens.color?.['muted-600'], marginBottom: 3 }}>
                                        What they said about their own cycle
                                        {entry.self_rating != null ? `, rating themselves ${entry.self_rating} out of 5` : ''}
                                    </div>
                                    <div style={{ fontSize: 12.5, color: tokens.color?.['text-100'], lineHeight: 1.5 }}>{entry.self_assessment}</div>
                                </div>
                            ) : (
                                <p style={{ ...ui.hint, marginTop: 4 }}>They have not written a self-assessment yet.</p>
                            )}

                            {entry.goals?.total > 0 && (
                                <p style={{ ...ui.hint, marginTop: 6 }}>
                                    They hit {entry.goals.achieved} of the {entry.goals.total} goal
                                    {entry.goals.total === 1 ? '' : 's'} they set for themselves.
                                </p>
                            )}

                            {entry.calibrated_rating != null && (
                                <p style={{ ...ui.hint, marginTop: 6, color: tokens.color?.['accent-primary'] }}>
                                    HR calibrated this to {entry.calibrated_rating} out of 5.
                                </p>
                            )}

                            {cycle?.stage === 'manager_review' && (
                                <div style={{ marginTop: 9 }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                                        <label style={{ ...ui.label, margin: 0 }}>Your rating</label>
                                        <input type="range" min="1" max="5" step="0.5"
                                            value={d.rating}
                                            onChange={(e) => setDraft(entry.employee_uuid, { rating: e.target.value })}
                                            style={{ flex: '1 1 130px', accentColor: tokens.color?.['accent-primary'] }} />
                                        <span style={{ fontWeight: 600, color: tokens.color?.['text-100'], minWidth: 26 }}>{d.rating}</span>
                                    </div>
                                    <input style={{ ...ui.input, marginTop: 7 }} placeholder="Why you rated it that way"
                                        value={d.comments} onChange={(e) => setDraft(entry.employee_uuid, { comments: e.target.value })} />
                                    <div style={{ marginTop: 8 }}>
                                        <Btn tone="success" icon={Send} loading={busyId === entry.employee_uuid}
                                            onClick={() => submit(entry)}>
                                            {rated ? 'Change my rating' : 'Record my rating'}
                                        </Btn>
                                    </div>
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>
        </div>
    );
});
CycleReviewPanel.displayName = 'CycleReviewPanel';

const TeamGoalsModule = memo(() => (
    <div style={ui.grid} className="portal-grid">
        <EmployeeStyles />
        <TeamGoalsPanel />
        <CycleReviewPanel />
    </div>
));
TeamGoalsModule.displayName = 'TeamGoalsModule';

export default TeamGoalsModule;
