// Manager portal: the weekly cadence module. Three things a manager has to stay
// on top of and which nothing else in the portal surfaces: the nudges digest
// (what needs attention right now), one-on-one cadence (who has not been spoken
// to), and service anniversaries.
//
// Real endpoints: GET /mss/nudges, GET|POST|PUT|DELETE /mss/one-on-ones,
// GET /mss/one-on-ones/status, GET /mss/milestones.
// The nudges payload carries a `notes` array naming what the backend could NOT
// compute; it is rendered rather than hidden, so a thin digest never reads as
// "nothing is wrong".
import React, { memo, useCallback, useMemo, useState } from 'react';
import { theme as tokens } from '../../theme';
import { useApi } from '../../hooks/useApi';
import { useToast } from '../../hooks/use-toast';
import {
    getNudges, getOneOnOnes, getOneOnOneStatus, createOneOnOne, updateOneOnOne, deleteOneOnOne,
    getMilestones,
} from '../../config/api';
import { ui, Btn, Loading, EmptyState, ErrorNote, fmtDate, EmployeeStyles } from '../employee/shared';
import { useRoster, useEmployeeNames } from './roster';
import {
    Bell, CalendarClock, Cake, Trash2, Save, Plus, AlertTriangle, Info, CheckCircle2,
} from 'lucide-react';

const errText = (e) => e?.response?.data?.detail || e?.message || 'The request failed.';

const SEVERITY = {
    high: { color: 'danger', icon: AlertTriangle, label: 'Needs attention now' },
    medium: { color: 'warning', icon: Bell, label: 'Worth a look this week' },
    low: { color: 'accent-primary', icon: Info, label: 'For information' },
};

/* -------------------------------------------------------------------------- */
/* Nudges digest                                                              */
/* -------------------------------------------------------------------------- */
const NudgesPanel = memo(() => {
    const { data, isLoading, error } = useApi(getNudges, [], true);
    const nudges = useMemo(() => data?.nudges || [], [data]);
    const notes = useMemo(() => data?.notes || [], [data]);

    return (
        <div style={{ ...ui.panel, gridColumn: 'span 12' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
                <h3 style={ui.h3}><Bell size={16} style={{ verticalAlign: -3, marginRight: 6 }} />What needs you this week</h3>
                {data?.generated_at && <span style={{ ...ui.hint, margin: 0 }}>Worked out {fmtDate(data.generated_at)}</span>}
            </div>
            <p style={ui.hint}>Read from your real approval queue, one-on-one history and team records. Nothing here is a reminder you set yourself.</p>

            {isLoading && <Loading label="Working out what needs your attention" />}
            <ErrorNote error={error} context="your digest" />

            {!isLoading && !error && nudges.length === 0 && (
                <EmptyState icon={CheckCircle2} title="Nothing is waiting on you"
                    action="No overdue approvals, no stale one-on-ones and no flight-risk flags on your team right now." />
            )}

            <div style={{ display: 'grid', gap: 10, marginTop: nudges.length ? 12 : 0 }}>
                {nudges.map((n, i) => {
                    const sev = SEVERITY[n.severity] || SEVERITY.low;
                    const color = tokens.color?.[sev.color];
                    const SevIcon = sev.icon;
                    return (
                        <div key={`${n.kind}-${i}`} style={{
                            display: 'flex', gap: 11, padding: '12px 14px', borderRadius: 10,
                            border: `1px solid ${color}33`, background: `${color}0d`, borderLeft: `3px solid ${color}`,
                        }}>
                            <SevIcon size={17} color={color} style={{ flexShrink: 0, marginTop: 1 }} />
                            <div style={{ minWidth: 0 }}>
                                <div style={{ fontSize: 13.5, fontWeight: 550, color: tokens.color?.['text-100'] }}>{n.headline}</div>
                                {n.detail && <div style={{ fontSize: 12.5, color: tokens.color?.['muted-600'], marginTop: 3, lineHeight: 1.5 }}>{n.detail}</div>}
                                {n.action_hint && (
                                    <div style={{ fontSize: 12.5, color, marginTop: 5 }}>{n.action_hint}</div>
                                )}
                                <div style={{ fontSize: 11, color: tokens.color?.['muted-600'], marginTop: 5 }}>{sev.label}</div>
                            </div>
                        </div>
                    );
                })}
            </div>

            {notes.length > 0 && (
                <div style={{ marginTop: 14, paddingTop: 12, borderTop: `1px solid ${tokens.color?.['border-600']}` }}>
                    <p style={{ ...ui.hint, margin: 0 }}>What this digest could not work out:</p>
                    {notes.map((note, i) => (
                        <p key={i} style={{ ...ui.hint, marginTop: 4 }}>{note}</p>
                    ))}
                </div>
            )}
        </div>
    );
});
NudgesPanel.displayName = 'NudgesPanel';

/* -------------------------------------------------------------------------- */
/* One-on-one cadence                                                          */
/* -------------------------------------------------------------------------- */
const OneOnOnesPanel = memo(() => {
    const { toast } = useToast();
    const roster = useRoster();
    const { data: listData, isLoading, error, refetch } = useApi(getOneOnOnes, [], true);
    const { data: statusData, refetch: refetchStatus } = useApi(getOneOnOneStatus, [], true);

    const meetings = useMemo(() => listData?.one_on_ones || [], [listData]);
    // Only people who have actually been met matter for the history view; the
    // status list covers the whole reporting line and is filtered separately.
    const status = useMemo(() => statusData?.status || [], [statusData]);

    const [form, setForm] = useState({ employee_uuid: '', talking_points: '', notes: '', shared_with_employee: true });
    const [saving, setSaving] = useState(false);
    const [busyId, setBusyId] = useState(null);
    const [editing, setEditing] = useState(null);
    const [draft, setDraft] = useState({ talking_points: '', notes: '' });

    // Every id shown gets resolved to a real name; ids are never displayed raw.
    const ids = useMemo(
        () => [...meetings.map((m) => m.employee_uuid), ...status.slice(0, 30).map((s) => s.employee_uuid)],
        [meetings, status],
    );
    const names = useEmployeeNames(ids);
    const nameOf = useCallback(
        (id) => names[id] || roster.people.find((p) => p.id === id)?.name || 'A team member',
        [names, roster.people],
    );

    const overdue = useMemo(() => status.filter((s) => s.overdue), [status]);
    const neverMet = useMemo(() => overdue.filter((s) => !s.last_held_at), [overdue]);
    const stale = useMemo(
        () => overdue.filter((s) => s.last_held_at).sort((a, b) => (b.days_since || 0) - (a.days_since || 0)),
        [overdue],
    );

    const log = useCallback(async (e) => {
        e.preventDefault();
        if (!form.employee_uuid) {
            toast({ title: 'Pick a team member', description: 'A one-on-one is recorded against one person.', variant: 'destructive' });
            return;
        }
        setSaving(true);
        try {
            await createOneOnOne({
                employee_uuid: form.employee_uuid,
                talking_points: form.talking_points.trim(),
                notes: form.notes.trim(),
                shared_with_employee: form.shared_with_employee,
            });
            toast({
                title: 'One-on-one recorded',
                description: `Logged against ${nameOf(form.employee_uuid)}.${form.shared_with_employee ? ' They can read the notes.' : ' The notes stay private to you.'}`,
                variant: 'success',
            });
            setForm({ employee_uuid: '', talking_points: '', notes: '', shared_with_employee: true });
            refetch();
            refetchStatus();
        } catch (err) {
            toast({ title: 'Could not record that one-on-one', description: errText(err), variant: 'destructive' });
        } finally {
            setSaving(false);
        }
    }, [form, toast, refetch, refetchStatus, nameOf]);

    const saveEdit = useCallback(async (m) => {
        setBusyId(m.id);
        try {
            await updateOneOnOne(m.id, { talking_points: draft.talking_points, notes: draft.notes });
            toast({ title: 'Notes updated', description: `The record for ${nameOf(m.employee_uuid)} has been changed.`, variant: 'success' });
            setEditing(null);
            refetch();
        } catch (err) {
            toast({ title: 'Could not save those notes', description: errText(err), variant: 'destructive' });
        } finally {
            setBusyId(null);
        }
    }, [draft, toast, refetch, nameOf]);

    const remove = useCallback(async (m) => {
        if (!window.confirm(`Delete the one-on-one recorded with ${nameOf(m.employee_uuid)} on ${fmtDate(m.held_at)}? This cannot be undone.`)) return;
        setBusyId(m.id);
        try {
            await deleteOneOnOne(m.id);
            toast({ title: 'One-on-one deleted', description: 'The record has been removed.', variant: 'success' });
            refetch();
            refetchStatus();
        } catch (err) {
            toast({ title: 'Could not delete that record', description: errText(err), variant: 'destructive' });
        } finally {
            setBusyId(null);
        }
    }, [toast, refetch, refetchStatus, nameOf]);

    return (
        <>
            <div style={{ ...ui.panel, gridColumn: 'span 5' }}>
                <h3 style={ui.h3}><Plus size={16} style={{ verticalAlign: -3, marginRight: 6 }} />Record a one-on-one</h3>
                <p style={ui.hint}>Logging it here is what resets the cadence clock for that person.</p>
                <form onSubmit={log} style={{ marginTop: 10 }}>
                    <div style={ui.field}>
                        <label style={ui.label} htmlFor="oo-person">Team member</label>
                        <select id="oo-person" style={ui.input} value={form.employee_uuid}
                            onChange={(e) => setForm((p) => ({ ...p, employee_uuid: e.target.value }))}>
                            <option value="">{roster.isLoading ? 'Loading your team' : 'Select a team member'}</option>
                            {roster.people.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                        </select>
                        <span style={{ ...ui.hint, display: 'block' }}>{roster.summary}</span>
                    </div>
                    <div style={ui.field}>
                        <label style={ui.label} htmlFor="oo-points">What you talked about</label>
                        <input id="oo-points" style={ui.input} value={form.talking_points}
                            placeholder="for example, pipeline review and the enterprise ramp"
                            onChange={(e) => setForm((p) => ({ ...p, talking_points: e.target.value }))} />
                    </div>
                    <div style={ui.field}>
                        <label style={ui.label} htmlFor="oo-notes">Notes</label>
                        <textarea id="oo-notes" style={{ ...ui.input, minHeight: 78, resize: 'vertical' }} value={form.notes}
                            placeholder="Where they stand, and what you agreed to do next"
                            onChange={(e) => setForm((p) => ({ ...p, notes: e.target.value }))} />
                    </div>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', marginBottom: 14 }}>
                        <input type="checkbox" checked={form.shared_with_employee}
                            onChange={(e) => setForm((p) => ({ ...p, shared_with_employee: e.target.checked }))}
                            style={{ accentColor: tokens.color?.['accent-primary'] }} />
                        <span style={{ fontSize: 12.5, color: tokens.color?.['muted-500'] }}>
                            Let this person read the notes
                        </span>
                    </label>
                    <Btn type="submit" tone="success" icon={Save} loading={saving} disabled={!form.employee_uuid}>Record it</Btn>
                </form>
            </div>

            <div style={{ ...ui.panel, gridColumn: 'span 7' }}>
                <h3 style={ui.h3}><CalendarClock size={16} style={{ verticalAlign: -3, marginRight: 6 }} />Who is overdue</h3>
                <p style={ui.hint}>
                    {status.length > 0
                        ? `${overdue.length.toLocaleString()} of ${status.length.toLocaleString()} people on your reporting line are past due for a conversation.`
                        : 'Cadence is worked out from the one-on-ones actually recorded here.'}
                </p>

                {stale.length > 0 && (
                    <div className="emp-scroll" style={{ ...ui.scroller('190px'), marginTop: 10 }}>
                        {stale.slice(0, 40).map((s) => (
                            <div key={s.employee_uuid} style={ui.listRow}>
                                <div style={ui.rowMain}>
                                    <span style={ui.rowTitle}>{nameOf(s.employee_uuid)}</span>
                                    <span style={ui.rowMeta}>Last spoke {fmtDate(s.last_held_at)}</span>
                                </div>
                                <span style={{ flexShrink: 0, color: tokens.color?.warning, fontSize: 12.5, fontWeight: 550 }}>
                                    {s.days_since} days ago
                                </span>
                            </div>
                        ))}
                    </div>
                )}

                {neverMet.length > 0 && (
                    <p style={{ ...ui.hint, marginTop: 10 }}>
                        A further {neverMet.length.toLocaleString()} {neverMet.length === 1 ? 'person has' : 'people have'} no
                        one-on-one on record at all. On a reporting line this size that usually means the cadence has never
                        been logged here rather than that the conversations never happened.
                    </p>
                )}

                {status.length > 0 && overdue.length === 0 && (
                    <EmptyState icon={CheckCircle2} title="Everyone has been spoken to recently"
                        action="No one on your reporting line is past the cadence threshold." />
                )}
            </div>

            <div style={{ ...ui.panel, gridColumn: 'span 12' }}>
                <h3 style={ui.h3}>One-on-ones you have recorded</h3>
                {isLoading && <Loading label="Reading your one-on-one history" />}
                <ErrorNote error={error} context="your one-on-one history" />
                {!isLoading && !error && meetings.length === 0 && (
                    <EmptyState icon={CalendarClock} title="No one-on-ones recorded yet"
                        action="Record the first one with the form above. The cadence view fills in from what you log." />
                )}

                <div className="emp-scroll" style={{ ...ui.scroller('340px'), marginTop: meetings.length ? 8 : 0 }}>
                    {meetings.map((m) => (
                        <div key={m.id} style={{ padding: '12px 0', borderBottom: `1px solid ${tokens.color?.['border-600']}` }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap' }}>
                                <div style={{ minWidth: 0 }}>
                                    <span style={{ fontSize: 13.5, fontWeight: 550, color: tokens.color?.['text-100'] }}>{nameOf(m.employee_uuid)}</span>
                                    <span style={{ ...ui.rowMeta, marginLeft: 8 }}>{fmtDate(m.held_at)}</span>
                                </div>
                                <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
                                    <Btn tone="ghost" style={{ padding: '5px 10px', fontSize: 11.5 }}
                                        onClick={() => {
                                            setEditing(editing === m.id ? null : m.id);
                                            setDraft({ talking_points: m.talking_points || '', notes: m.notes || '' });
                                        }}>
                                        {editing === m.id ? 'Cancel' : 'Edit notes'}
                                    </Btn>
                                    <Btn tone="ghost" icon={Trash2} style={{ padding: '5px 10px', fontSize: 11.5, color: tokens.color?.danger }}
                                        loading={busyId === m.id} onClick={() => remove(m)}>Delete</Btn>
                                </div>
                            </div>

                            {editing === m.id ? (
                                <div style={{ marginTop: 8 }}>
                                    <input style={ui.input} value={draft.talking_points} placeholder="What you talked about"
                                        onChange={(e) => setDraft((p) => ({ ...p, talking_points: e.target.value }))} />
                                    <textarea style={{ ...ui.input, minHeight: 70, marginTop: 8, resize: 'vertical' }} value={draft.notes}
                                        placeholder="Notes" onChange={(e) => setDraft((p) => ({ ...p, notes: e.target.value }))} />
                                    <div style={{ marginTop: 8 }}>
                                        <Btn tone="success" icon={Save} loading={busyId === m.id} onClick={() => saveEdit(m)}>Save the notes</Btn>
                                    </div>
                                </div>
                            ) : (
                                <div style={{ marginTop: 5 }}>
                                    {m.talking_points && <div style={{ fontSize: 12.5, color: tokens.color?.['text-100'] }}>{m.talking_points}</div>}
                                    {m.notes && <div style={{ fontSize: 12.5, color: tokens.color?.['muted-600'], marginTop: 3, lineHeight: 1.5 }}>{m.notes}</div>}
                                    <div style={{ fontSize: 11, color: tokens.color?.['muted-600'], marginTop: 4 }}>
                                        {m.shared_with_employee ? 'Visible to this person' : 'Private to you'}
                                    </div>
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            </div>
        </>
    );
});
OneOnOnesPanel.displayName = 'OneOnOnesPanel';

/* -------------------------------------------------------------------------- */
/* Service anniversaries                                                       */
/* -------------------------------------------------------------------------- */
const MilestonesPanel = memo(() => {
    const { data, isLoading, error } = useApi(getMilestones, [], true);
    const upcoming = useMemo(() => data?.upcoming || [], [data]);
    const recent = useMemo(() => data?.recent || [], [data]);

    const Row = ({ m, ahead }) => (
        <div style={ui.listRow}>
            <div style={ui.rowMain}>
                <span style={ui.rowTitle}>{m.name}</span>
                <span style={ui.rowMeta}>{m.job_title}, {m.department}</span>
            </div>
            <div style={{ flexShrink: 0, textAlign: 'right' }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: tokens.color?.['accent-secondary'] }}>
                    {m.years_of_service} {m.years_of_service === 1 ? 'year' : 'years'}
                </div>
                <div style={{ fontSize: 11, color: tokens.color?.['muted-600'] }}>
                    {ahead
                        ? (m.days_away === 0 ? 'today' : `in ${m.days_away} ${m.days_away === 1 ? 'day' : 'days'}`)
                        : fmtDate(m.anniversary_date)}
                </div>
            </div>
        </div>
    );

    return (
        <div style={{ ...ui.panel, gridColumn: 'span 12' }}>
            <h3 style={ui.h3}><Cake size={16} style={{ verticalAlign: -3, marginRight: 6 }} />Service anniversaries</h3>
            <p style={ui.hint}>Worked out from each person&apos;s real start date. Recognising one of these is a two-second thing that people remember.</p>

            {isLoading && <Loading label="Reading start dates" />}
            <ErrorNote error={error} context="service anniversaries" />

            {!isLoading && !error && upcoming.length === 0 && recent.length === 0 && (
                <EmptyState icon={Cake} title="No anniversaries fall near today"
                    action="This looks ahead and behind by a short window, so it is empty most weeks." />
            )}

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: tokens.spacing?.lg, marginTop: 10 }}>
                {upcoming.length > 0 && (
                    <div style={{ minWidth: 0 }}>
                        <h4 style={{ ...ui.h3, fontSize: 13 }}>Coming up</h4>
                        <div className="emp-scroll" style={ui.scroller('260px')}>
                            {upcoming.slice(0, 40).map((m) => <Row key={m.employee_uuid} m={m} ahead />)}
                        </div>
                    </div>
                )}
                {recent.length > 0 && (
                    <div style={{ minWidth: 0 }}>
                        <h4 style={{ ...ui.h3, fontSize: 13 }}>Just passed</h4>
                        <div className="emp-scroll" style={ui.scroller('260px')}>
                            {recent.slice(0, 40).map((m) => <Row key={m.employee_uuid} m={m} />)}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
});
MilestonesPanel.displayName = 'MilestonesPanel';

const CadenceModule = memo(() => (
    <div style={ui.grid} className="portal-grid">
        <EmployeeStyles />
        <NudgesPanel />
        <OneOnOnesPanel />
        <MilestonesPanel />
    </div>
));
CadenceModule.displayName = 'CadenceModule';

export { NudgesPanel };
export default CadenceModule;
