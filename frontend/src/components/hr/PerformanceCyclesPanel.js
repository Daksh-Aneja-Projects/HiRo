// HR portal: the middle of the performance loop. Employees write
// self-assessments and managers rate them in their own portals; this is where
// the cycle is opened, moved between stages, and calibrated.
//
// Real endpoints: GET|POST /hr/performance/cycles,
// GET /hr/performance/cycles/{id}/entries, POST .../advance,
// POST .../calibrate-entry.
//
// Stages run self_assessment -> manager_review -> calibration -> signed_off and
// the backend refuses out-of-order transitions with a 409, which is surfaced as
// the reason rather than a generic failure. Calibration is only offered during
// the calibration stage, because that is the only stage the backend will accept
// it in.
import React, { memo, useCallback, useEffect, useMemo, useState } from 'react';
import { theme as tokens } from '../../theme';
import { useApi } from '../../hooks/useApi';
import { useToast } from '../../hooks/use-toast';
import {
    listPerformanceCycles, createPerformanceCycle, getCycleEntriesForHR,
    advancePerformanceCycle, calibratePerformanceEntry, getAnalyticsDepartments,
} from '../../config/api';
import { ui, Btn, Loading, EmptyState, ErrorNote, fmtDate, EmployeeStyles } from '../employee/shared';
import { CountUp } from '../live/LivePrimitives';
import { Gauge, PlusCircle, ChevronRight, Scale, CheckCircle2, AlertTriangle } from 'lucide-react';

const errText = (e) => e?.response?.data?.detail || e?.message || 'The request failed.';

const STAGES = ['self_assessment', 'manager_review', 'calibration', 'signed_off'];
const STAGE_LABEL = {
    self_assessment: 'Self-assessment',
    manager_review: 'Manager review',
    calibration: 'Calibration',
    signed_off: 'Signed off',
};
const STAGE_WAITING = {
    self_assessment: 'Waiting on employees to write their self-assessments.',
    manager_review: 'Waiting on managers to rate their reports.',
    calibration: 'Yours to do: compare ratings across teams and set the calibrated figure.',
    signed_off: 'Calibrated ratings are out. Employees are signing off, and each sign-off writes a real performance review.',
};

/** The four stages as a progress rail, so the state machine is visible. */
const StageRail = ({ stage }) => {
    const at = STAGES.indexOf(stage);
    return (
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap', marginTop: 10 }}>
            {STAGES.map((s, i) => {
                const done = i < at;
                const here = i === at;
                const color = here ? tokens.color?.['accent-primary'] : (done ? tokens.color?.success : tokens.color?.['muted-600']);
                return (
                    <React.Fragment key={s}>
                        <span style={{
                            display: 'inline-flex', alignItems: 'center', gap: 5, padding: '4px 10px',
                            borderRadius: 999, fontSize: 11.5, fontWeight: here ? 600 : 500, color,
                            border: `1px solid ${color}44`, background: here ? `${color}18` : 'transparent',
                            whiteSpace: 'nowrap',
                        }}>
                            {done && <CheckCircle2 size={11} />}
                            {STAGE_LABEL[s]}
                        </span>
                        {i < STAGES.length - 1 && <ChevronRight size={12} color={tokens.color?.['muted-600']} style={{ flexShrink: 0 }} />}
                    </React.Fragment>
                );
            })}
        </div>
    );
};

/** Distribution of the ratings actually recorded, which is what calibration is for. */
const RatingSpread = ({ entries, field, label, color }) => {
    const buckets = useMemo(() => {
        const b = new Map();
        entries.forEach((e) => {
            const v = e[field];
            if (v == null) return;
            const k = Math.round(Number(v) * 2) / 2;
            b.set(k, (b.get(k) || 0) + 1);
        });
        return [...b.entries()].sort((a, b2) => a[0] - b2[0]);
    }, [entries, field]);

    const rated = buckets.reduce((s, [, n]) => s + n, 0);
    if (rated === 0) {
        return <p style={ui.hint}>No {label.toLowerCase()} has been recorded yet.</p>;
    }
    const max = Math.max(...buckets.map(([, n]) => n));
    const mean = entries.reduce((s, e) => s + (Number(e[field]) || 0), 0) / rated;

    return (
        <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
                <span style={{ fontSize: 12, color: tokens.color?.['muted-600'] }}>{label}</span>
                <span style={{ fontSize: 12, color: tokens.color?.['muted-600'] }}>
                    {rated.toLocaleString()} rated, average <CountUp value={mean} decimals={2} />
                </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'flex-end', gap: 4, height: 72, marginTop: 8 }}>
                {buckets.map(([v, n]) => (
                    <div key={v} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3, minWidth: 0 }}>
                        <span style={{ fontSize: 10, color: tokens.color?.['muted-600'] }}>{n}</span>
                        <div title={`${n} rated ${v} out of 5`} style={{
                            width: '100%', height: `${Math.max(3, (n / max) * 52)}px`,
                            background: color, borderRadius: '3px 3px 0 0', opacity: 0.85,
                            transition: 'height 0.5s cubic-bezier(0.22, 1, 0.36, 1)',
                        }} />
                        <span style={{ fontSize: 10, color: tokens.color?.['muted-600'] }}>{v}</span>
                    </div>
                ))}
            </div>
        </div>
    );
};

const PerformanceCyclesPanel = memo(() => {
    const { toast } = useToast();
    const { data: deptData } = useApi(getAnalyticsDepartments, [], true);
    const departments = deptData?.departments || [];

    const { data: listData, isLoading: listLoading, error: listError, refetch: refetchList } =
        useApi(listPerformanceCycles, [], true);
    const cycles = useMemo(() => listData?.cycles || [], [listData]);

    const [activeId, setActiveId] = useState(null);
    useEffect(() => {
        if (!activeId && cycles.length) setActiveId(cycles[0].cycle_id);
    }, [cycles, activeId]);

    const { data: entryData, isLoading: entriesLoading, error: entriesError, refetch: refetchEntries } =
        useApi(getCycleEntriesForHR, [activeId], Boolean(activeId));
    const entries = useMemo(() => entryData?.entries || [], [entryData]);

    const [form, setForm] = useState({ name: '', department: '', opens_at: '', closes_at: '' });
    const [creating, setCreating] = useState(false);
    const [advancing, setAdvancing] = useState(false);
    const [stageProblem, setStageProblem] = useState(null);
    const [drafts, setDrafts] = useState({});
    const [busyUuid, setBusyUuid] = useState(null);
    const [deptFilter, setDeptFilter] = useState('');

    const cycle = cycles.find((c) => c.cycle_id === activeId);
    const nextStage = cycle ? STAGES[STAGES.indexOf(cycle.stage) + 1] : null;

    const create = useCallback(async (e) => {
        e.preventDefault();
        if (!form.name.trim() || !form.department) return;
        setCreating(true);
        try {
            const res = await createPerformanceCycle({
                name: form.name.trim(),
                department: form.department,
                opens_at: form.opens_at || undefined,
                closes_at: form.closes_at || undefined,
            });
            toast({
                title: 'Cycle opened',
                description: `${Number(res.data.employee_count).toLocaleString()} people were included and told their self-assessment is open.`,
                variant: 'success',
            });
            setForm({ name: '', department: '', opens_at: '', closes_at: '' });
            setActiveId(res.data.cycle_id);
            refetchList();
        } catch (err) {
            toast({ title: 'Could not open that cycle', description: errText(err), variant: 'destructive' });
        } finally {
            setCreating(false);
        }
    }, [form, toast, refetchList]);

    const advance = useCallback(async () => {
        if (!cycle) return;
        if (!window.confirm(`Move "${cycle.name}" on to ${STAGE_LABEL[nextStage]}? Everyone still owing work in the current stage loses the chance to submit it.`)) return;
        setAdvancing(true);
        setStageProblem(null);
        try {
            await advancePerformanceCycle(cycle.cycle_id);
            toast({ title: 'Stage moved on', description: `"${cycle.name}" is now at ${STAGE_LABEL[nextStage]}.`, variant: 'success' });
            refetchList();
            refetchEntries();
        } catch (err) {
            // A 409 is the state machine refusing, and the reason is worth reading.
            if (err.response?.status === 409) setStageProblem(errText(err));
            else toast({ title: 'Could not move the stage on', description: errText(err), variant: 'destructive' });
        } finally {
            setAdvancing(false);
        }
    }, [cycle, nextStage, toast, refetchList, refetchEntries]);

    const calibrate = useCallback(async (entry) => {
        const value = drafts[entry.employee_uuid];
        const rating = Number(value != null ? value : entry.manager_rating);
        if (!Number.isFinite(rating)) return;
        setBusyUuid(entry.employee_uuid);
        try {
            await calibratePerformanceEntry(activeId, entry.employee_uuid, rating);
            toast({
                title: 'Calibrated',
                description: `${entry.full_name || 'That person'} is set to ${rating} out of 5 for this cycle.`,
                variant: 'success',
            });
            refetchEntries();
        } catch (err) {
            toast({ title: 'Could not calibrate that entry', description: errText(err), variant: 'destructive' });
        } finally {
            setBusyUuid(null);
        }
    }, [drafts, activeId, toast, refetchEntries]);

    const entryDepts = useMemo(
        () => [...new Set(entries.map((e) => e.department).filter(Boolean))].sort(),
        [entries],
    );
    const shown = useMemo(
        () => (deptFilter ? entries.filter((e) => e.department === deptFilter) : entries),
        [entries, deptFilter],
    );

    const awaiting = useMemo(() => ({
        self: entries.filter((e) => !e.self_assessment).length,
        manager: entries.filter((e) => e.manager_rating == null).length,
        calibrated: entries.filter((e) => e.calibrated_rating != null).length,
        signed: entries.filter((e) => e.signed_off_by_employee).length,
    }), [entries]);

    return (
        <div style={ui.grid} className="portal-grid">
            <EmployeeStyles />

            {/* ---- open a cycle ---- */}
            <div style={{ ...ui.panel, gridColumn: 'span 4' }}>
                <h3 style={ui.h3}><PlusCircle size={16} style={{ verticalAlign: -3, marginRight: 6 }} />Open a review cycle</h3>
                <p style={ui.hint}>Everyone in the department you choose is included and told their self-assessment is open. The population is read from the live employee records, so it is who works there today.</p>
                <form onSubmit={create} style={{ marginTop: 10 }}>
                    <div style={ui.field}>
                        <label style={ui.label} htmlFor="pc-name">What to call it</label>
                        <input id="pc-name" style={ui.input} value={form.name} required
                            placeholder="for example, H2 2026 Performance Review"
                            onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))} />
                    </div>
                    <div style={ui.field}>
                        <label style={ui.label} htmlFor="pc-dept">Who it covers</label>
                        <select id="pc-dept" style={ui.input} value={form.department} required
                            onChange={(e) => setForm((p) => ({ ...p, department: e.target.value }))}>
                            <option value="">Choose a department</option>
                            <option value="all">Everyone in the organisation</option>
                            {departments.map((d) => <option key={d} value={d}>{d}</option>)}
                        </select>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: tokens.spacing?.sm }}>
                        <div style={ui.field}>
                            <label style={ui.label} htmlFor="pc-open">Opens</label>
                            <input id="pc-open" type="date" style={ui.input} value={form.opens_at}
                                onChange={(e) => setForm((p) => ({ ...p, opens_at: e.target.value }))} />
                        </div>
                        <div style={ui.field}>
                            <label style={ui.label} htmlFor="pc-close">Closes</label>
                            <input id="pc-close" type="date" style={ui.input} value={form.closes_at} min={form.opens_at || undefined}
                                onChange={(e) => setForm((p) => ({ ...p, closes_at: e.target.value }))} />
                        </div>
                    </div>
                    <Btn type="submit" icon={PlusCircle} loading={creating} disabled={!form.name.trim() || !form.department}>
                        Open the cycle
                    </Btn>
                </form>

                <div style={{ marginTop: 18, paddingTop: 14, borderTop: `1px solid ${tokens.color?.['border-600']}` }}>
                    <h4 style={{ ...ui.h3, fontSize: 13 }}>Cycles on record</h4>
                    {listLoading && <Loading label="Reading the cycles" />}
                    <ErrorNote error={listError} context="the performance cycles" />
                    {!listLoading && !listError && cycles.length === 0 && (
                        <p style={ui.hint}>No performance cycle has been opened yet.</p>
                    )}
                    {cycles.map((c) => {
                        const on = c.cycle_id === activeId;
                        return (
                            <button key={c.cycle_id} type="button" onClick={() => { setActiveId(c.cycle_id); setStageProblem(null); setDeptFilter(''); }}
                                style={{
                                    display: 'block', width: '100%', textAlign: 'left', cursor: 'pointer', border: 'none',
                                    background: on ? `${tokens.color?.['accent-primary']}14` : 'transparent',
                                    borderRadius: 6, padding: '7px 8px', marginTop: 4,
                                }}>
                                <span style={{ display: 'block', fontSize: 12.5, fontWeight: 550, color: on ? tokens.color?.['accent-primary'] : tokens.color?.['text-100'] }}>
                                    {c.name}
                                </span>
                                <span style={{ display: 'block', fontSize: 11.5, color: tokens.color?.['muted-600'] }}>
                                    {STAGE_LABEL[c.stage] || c.stage}
                                    {c.closes_at ? `, closes ${fmtDate(c.closes_at)}` : ''}
                                </span>
                            </button>
                        );
                    })}
                </div>
            </div>

            {/* ---- run the cycle ---- */}
            <div style={{ ...ui.panel, gridColumn: 'span 8' }}>
                {!cycle && !listLoading && (
                    <EmptyState icon={Gauge} title="No cycle selected"
                        action="Open one on the left, or pick a cycle from the list to run it." />
                )}

                {cycle && (
                    <>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
                            <h3 style={ui.h3}>{cycle.name}</h3>
                            <span style={{ ...ui.hint, margin: 0 }}>
                                {fmtDate(cycle.opens_at)} to {fmtDate(cycle.closes_at)}
                            </span>
                        </div>
                        <StageRail stage={cycle.stage} />
                        <p style={ui.hint}>{STAGE_WAITING[cycle.stage]}</p>

                        {stageProblem && (
                            <div style={{
                                display: 'flex', gap: 9, marginTop: 10, padding: '10px 12px', borderRadius: 8,
                                border: `1px solid ${tokens.color?.warning}33`, background: `${tokens.color?.warning}0d`,
                            }}>
                                <AlertTriangle size={15} color={tokens.color?.warning} style={{ flexShrink: 0, marginTop: 1 }} />
                                <span style={{ fontSize: 12.5, color: tokens.color?.['text-100'], lineHeight: 1.5 }}>{stageProblem}</span>
                            </div>
                        )}

                        {/* live counts across the cycle */}
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: 10, marginTop: 14 }}>
                            {[
                                ['In the cycle', entries.length, tokens.color?.['accent-primary']],
                                ['Self-assessments still owed', awaiting.self, tokens.color?.warning],
                                ['Manager ratings still owed', awaiting.manager, tokens.color?.warning],
                                ['Calibrated', awaiting.calibrated, tokens.color?.success],
                                ['Signed off', awaiting.signed, tokens.color?.success],
                            ].map(([label, value, color]) => (
                                <div key={label} style={{ padding: '10px 12px', borderRadius: 8, background: 'var(--bg-input)', border: `1px solid ${tokens.color?.['border-600']}` }}>
                                    <div style={{ fontSize: 19, fontWeight: 640, color }}><CountUp value={value} /></div>
                                    <div style={{ fontSize: 11, color: tokens.color?.['muted-600'], lineHeight: 1.35, marginTop: 2 }}>{label}</div>
                                </div>
                            ))}
                        </div>

                        {nextStage && (
                            <div style={{ marginTop: 14 }}>
                                <Btn icon={ChevronRight} loading={advancing} onClick={advance}>
                                    Move on to {STAGE_LABEL[nextStage]}
                                </Btn>
                            </div>
                        )}
                        {!nextStage && (
                            <p style={{ ...ui.hint, marginTop: 12, color: tokens.color?.success }}>
                                This cycle is at its final stage. Each employee sign-off writes a real performance review against their record.
                            </p>
                        )}

                        {entries.length > 0 && (
                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(230px, 1fr))', gap: tokens.spacing?.lg, marginTop: 18 }}>
                                <RatingSpread entries={entries} field="self_rating" label="How people rated themselves" color={tokens.color?.['accent-secondary']} />
                                <RatingSpread entries={entries} field="manager_rating" label="How managers rated them" color={tokens.color?.['accent-primary']} />
                                <RatingSpread entries={entries} field="calibrated_rating" label="After calibration" color={tokens.color?.success} />
                            </div>
                        )}
                    </>
                )}
            </div>

            {/* ---- calibrate ---- */}
            {cycle && (
                <div style={{ ...ui.panel, gridColumn: 'span 12' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
                        <h3 style={ui.h3}><Scale size={16} style={{ verticalAlign: -3, marginRight: 6 }} />Calibration</h3>
                        {entryDepts.length > 1 && (
                            <select style={{ ...ui.input, width: 'auto', minWidth: 190 }} value={deptFilter}
                                onChange={(e) => setDeptFilter(e.target.value)}>
                                <option value="">Every department</option>
                                {entryDepts.map((d) => <option key={d} value={d}>{d}</option>)}
                            </select>
                        )}
                    </div>
                    <p style={ui.hint}>
                        {cycle.stage === 'calibration'
                            ? 'Set the rating that goes on record. It defaults to the manager rating; change it where a team is rating harder or softer than the rest.'
                            : `Calibration is only accepted while the cycle is at the calibration stage. This cycle is at ${STAGE_LABEL[cycle.stage]}, so the ratings below are read-only for now.`}
                    </p>

                    {entriesLoading && <Loading label="Reading every entry in this cycle" />}
                    <ErrorNote error={entriesError} context="the entries in this cycle" />
                    {!entriesLoading && !entriesError && entries.length === 0 && (
                        <EmptyState icon={Scale} title="This cycle has no entries"
                            action="A cycle covers the people who were in the chosen department when it was opened." />
                    )}

                    {shown.length > 0 && (
                        <div className="emp-scroll" style={{ ...ui.scroller('420px'), marginTop: 10 }}>
                            {shown.slice(0, 200).map((entry) => {
                                const draft = drafts[entry.employee_uuid];
                                const value = draft != null ? draft : (entry.calibrated_rating != null ? entry.calibrated_rating : (entry.manager_rating != null ? entry.manager_rating : 3));
                                const canCalibrate = cycle.stage === 'calibration' && entry.manager_rating != null;
                                return (
                                    <div key={entry.employee_uuid} style={{ padding: '11px 0', borderBottom: `1px solid ${tokens.color?.['border-600']}` }}>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap' }}>
                                            <div style={{ minWidth: 0 }}>
                                                <span style={{ fontSize: 13, fontWeight: 550, color: tokens.color?.['text-100'] }}>
                                                    {entry.full_name || 'Record with no name on file'}
                                                </span>
                                                <span style={{ ...ui.rowMeta, marginLeft: 8 }}>
                                                    {[entry.job_title, entry.department].filter(Boolean).join(', ') || 'No department on record'}
                                                </span>
                                            </div>
                                            <div style={{ display: 'flex', gap: 16, flexShrink: 0, fontSize: 12 }}>
                                                <span style={{ color: tokens.color?.['muted-600'] }}>
                                                    self {entry.self_rating != null ? entry.self_rating : 'not given'}
                                                </span>
                                                <span style={{ color: tokens.color?.['accent-primary'] }}>
                                                    manager {entry.manager_rating != null ? entry.manager_rating : 'not given'}
                                                </span>
                                                <span style={{ color: entry.calibrated_rating != null ? tokens.color?.success : tokens.color?.['muted-600'] }}>
                                                    final {entry.calibrated_rating != null ? entry.calibrated_rating : 'not set'}
                                                </span>
                                            </div>
                                        </div>

                                        {canCalibrate && (
                                            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 8, flexWrap: 'wrap' }}>
                                                <input type="range" min="1" max="5" step="0.5" value={value}
                                                    onChange={(e) => setDrafts((p) => ({ ...p, [entry.employee_uuid]: e.target.value }))}
                                                    style={{ flex: '1 1 160px', accentColor: tokens.color?.success }} />
                                                <span style={{ fontWeight: 600, color: tokens.color?.['text-100'], minWidth: 26 }}>{value}</span>
                                                <Btn tone="success" style={{ padding: '5px 11px', fontSize: 11.5 }}
                                                    loading={busyUuid === entry.employee_uuid} onClick={() => calibrate(entry)}>
                                                    {entry.calibrated_rating != null ? 'Change the final rating' : 'Set the final rating'}
                                                </Btn>
                                            </div>
                                        )}
                                        {cycle.stage === 'calibration' && entry.manager_rating == null && (
                                            <p style={{ ...ui.hint, marginTop: 4 }}>
                                                Their manager never rated them, so there is nothing to calibrate against.
                                            </p>
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                    )}
                    {shown.length > 200 && (
                        <p style={{ ...ui.hint, marginTop: 8 }}>
                            Showing the first 200 of {shown.length.toLocaleString()}. Filter by department to work through a team at a time.
                        </p>
                    )}
                </div>
            )}
        </div>
    );
});

PerformanceCyclesPanel.displayName = 'PerformanceCyclesPanel';
export default PerformanceCyclesPanel;
