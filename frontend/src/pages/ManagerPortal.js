// /frontend/src/pages/ManagerPortal.js
// The manager portal. Every figure on every module is read from a real backend
// endpoint. Where an endpoint returns nothing, the module says so plainly rather
// than inventing a number, and every failure is shown in the user's own words.
import React, { useMemo, memo, useState, useCallback } from 'react';
import { useLocation, Link } from 'react-router-dom';
import { theme as tokens } from '../theme';

import {
    getApprovalQueue, actionApproval,
    getEmployeePerformance, submitPerformanceReview, getTeamPerformanceTrend, getPeerFeedback,
    predictAttritionRisk, runSimulation,
} from '../config/api';
import { useApi } from '../hooks/useApi';
import { useToast } from '../hooks/use-toast';

import DataCard from '../components/DataCard';
import AreaChartWidget from '../components/charts/AreaChartWidget';
import { CountUp, LiveMeter } from '../components/live/LivePrimitives';
import { ui, Btn, Loading, EmptyState, ErrorNote, fmtDate, humanText, EmployeeStyles } from '../components/employee/shared';
import { useRoster, RosterSelect, RosterPager, useEmployeeNames } from '../components/manager/roster';

import DigitalTwinChat from '../components/DigitalTwinChat';
import RiskOverview from '../components/RiskOverview';
import XAIDecisionPanel from '../components/XAIDecisionPanel';
import StarRecognitionWidget from '../components/StarRecognitionWidget';

import {
    Users, CheckSquare, Gauge, ShieldAlert, FlaskConical, Award,
    CheckCircle, XCircle, AlertTriangle, MessageSquare, CalendarDays,
    TrendingDown, Search, Play, UserCheck,
} from 'lucide-react';

const MODULES = [
    { key: 'team', label: 'Team Overview', title: 'Your team', icon: Users, blurb: 'Your direct reports, and a conversation with any of their digital twins.' },
    { key: 'approvals', label: 'Approvals', title: 'Approvals', icon: CheckSquare, blurb: 'Requests from your team that are waiting on a decision from you.' },
    { key: 'performance', label: 'Performance', title: 'Performance', icon: Gauge, blurb: 'How the team is rated over time, and where you record a review.' },
    { key: 'risk', label: 'Workforce Risk', title: 'Workforce risk', icon: ShieldAlert, blurb: 'Where the organisation is most likely to lose people, and why.' },
    { key: 'simulation', label: 'Attrition Simulation', title: 'Attrition simulation', icon: FlaskConical, blurb: 'Test a change on one person before you commit to it.' },
    { key: 'recognition', label: 'Recognition', title: 'Recognition', icon: Award, blurb: 'Give a star to someone who earned it, and see who is being noticed.' },
];

// Old sidebar links used ?module=overview for the approvals queue.
const ALIASES = { overview: 'approvals' };

/* -------------------------------------------------------------------------- */
/* Team overview                                                              */
/* -------------------------------------------------------------------------- */
const TeamModule = memo(() => {
    const roster = useRoster();
    const [selectedId, setSelectedId] = useState(null);
    const [filter, setFilter] = useState('');

    const { data: queue } = useApi(getApprovalQueue, [], true);
    const { data: trend } = useApi(getTeamPerformanceTrend, [], true);

    const pending = Array.isArray(queue) ? queue.length : 0;
    const latest = Array.isArray(trend) && trend.length ? trend[trend.length - 1] : null;

    const shown = useMemo(() => {
        const q = filter.trim().toLowerCase();
        if (!q) return roster.people;
        return roster.people.filter((p) => p.name.toLowerCase().includes(q) || p.email.toLowerCase().includes(q));
    }, [roster.people, filter]);

    const selected = roster.people.find((p) => p.id === selectedId) || null;

    const styles = useMemo(() => ({
        stat: { gridColumn: 'span 4', minWidth: 0 },
        list: { ...ui.panel, gridColumn: 'span 5', display: 'flex', flexDirection: 'column', gap: tokens.spacing?.sm, minHeight: 500 },
        chat: { gridColumn: 'span 7', minWidth: 0, minHeight: 500 },
        person: (active) => ({
            display: 'flex', alignItems: 'center', gap: 10, width: '100%', textAlign: 'left',
            padding: '9px 10px', marginBottom: 4, borderRadius: tokens.border?.radius?.input,
            background: active ? `${tokens.color?.['accent-primary']}18` : 'transparent',
            border: `1px solid ${active ? `${tokens.color?.['accent-primary']}55` : 'transparent'}`,
            cursor: 'pointer', transition: tokens.ui?.transition?.micro, minWidth: 0,
            fontFamily: tokens.typography?.fontFamily,
        }),
        avatar: {
            flexShrink: 0, width: 28, height: 28, borderRadius: tokens.border?.radius?.full,
            display: 'grid', placeItems: 'center', fontSize: 11, fontWeight: 600,
            background: 'rgba(255,255,255,0.05)', color: tokens.color?.['muted-500'],
        },
    }), []);

    return (
        <div style={ui.grid}>
            <div style={styles.stat}>
                <DataCard
                    title="People reporting to you"
                    value={<CountUp value={roster.total} />}
                    icon={<Users size={15} />}
                    subtitle={roster.total > roster.people.length
                        ? `${roster.people.length} loaded on this page`
                        : 'Everyone is loaded'}
                />
            </div>
            <div style={styles.stat}>
                <DataCard
                    title="Waiting on your decision"
                    value={<CountUp value={pending} />}
                    icon={<CheckSquare size={15} />}
                    color={pending > 0 ? tokens.color?.warning : tokens.color?.success}
                    subtitle={pending === 0 ? 'Nothing needs you right now' : 'Requests sitting in your approvals queue'}
                />
            </div>
            <div style={styles.stat}>
                <DataCard
                    title="Latest team rating"
                    value={latest ? <CountUp value={Number(latest.value) || 0} decimals={2} /> : 'Not recorded'}
                    unit={latest ? 'out of 5' : undefined}
                    icon={<Gauge size={15} />}
                    subtitle={latest ? `Monthly average for ${latest.name}` : 'No reviews recorded yet'}
                />
            </div>

            <div style={styles.list}>
                <div>
                    <h3 style={ui.h3}>Your direct reports</h3>
                    <p style={ui.hint}>Pick someone to open a conversation with their digital twin.</p>
                </div>

                <div style={{ position: 'relative' }}>
                    <Search size={14} style={{ position: 'absolute', left: 11, top: '50%', transform: 'translateY(-50%)', color: tokens.color?.['muted-600'] }} />
                    <input
                        type="text"
                        value={filter}
                        onChange={(e) => setFilter(e.target.value)}
                        placeholder="Filter the people on this page"
                        style={{ ...ui.input, paddingLeft: 32 }}
                    />
                </div>

                <ErrorNote error={roster.error} context="your team roster" />
                {roster.isLoading && roster.people.length === 0 && <Loading label="Reading your roster" />}

                <div style={{ ...ui.scroller('300px'), flexGrow: 1 }} className="emp-scroll">
                    {!roster.isLoading && shown.length === 0 && (
                        <EmptyState
                            icon={Users}
                            title={filter ? 'Nobody on this page matches that' : 'No direct reports on record'}
                            action={filter ? 'Clear the filter, or move to another page of the roster.' : 'Once people are assigned to you they appear here.'}
                        />
                    )}
                    {shown.map((p) => (
                        <button
                            key={p.id}
                            type="button"
                            onClick={() => setSelectedId(p.id)}
                            style={styles.person(p.id === selectedId)}
                        >
                            <span style={styles.avatar}>{p.name.slice(0, 2).toUpperCase()}</span>
                            <span style={{ minWidth: 0, display: 'flex', flexDirection: 'column', gap: 2 }}>
                                <span style={ui.rowTitle}>{p.name}</span>
                                <span style={ui.rowMeta}>{p.email || 'No email on record'}</span>
                            </span>
                        </button>
                    ))}
                </div>

                <RosterPager roster={roster} />
            </div>

            <div style={styles.chat}>
                {selected ? (
                    <DigitalTwinChat
                        key={selected.id}
                        targetUserId={selected.id}
                        targetUserName={selected.name}
                        isManagerView
                    />
                ) : (
                    <div style={{ ...ui.panel, height: '100%', display: 'grid', placeItems: 'center' }}>
                        <EmptyState
                            icon={MessageSquare}
                            title="Choose someone from your team"
                            action="Their digital twin answers the way they would, so you can check on workload or blockers without interrupting them."
                        />
                    </div>
                )}
            </div>
        </div>
    );
});
TeamModule.displayName = 'TeamModule';

/* -------------------------------------------------------------------------- */
/* Approvals                                                                  */
/* -------------------------------------------------------------------------- */
const requestKind = (type) => ({
    LEAVE_REQUEST: 'Time off',
    LEAVE: 'Time off',
    TIMESHEET: 'Timesheet',
    EXPENSE: 'Expense claim',
}[String(type || '').toUpperCase()] || humanText(type) || 'Request');

const money = (amount, currency) => {
    const value = Number(amount);
    if (!Number.isFinite(value)) return null;
    try {
        return new Intl.NumberFormat(undefined, { style: 'currency', currency: currency || 'USD' }).format(value);
    } catch {
        return `${currency || 'USD'} ${value.toFixed(2)}`;
    }
};

// The queue carries three different kinds of request, so each one gets a sentence
// that is actually true of it. A timesheet reported as "asked for 41 hours off"
// is the sort of thing a manager approves by mistake.
const describeRequest = (item, who) => {
    const name = who || 'A team member';
    const hours = Number(item.hours) || 0;
    switch (String(item.type || '').toUpperCase()) {
        case 'TIMESHEET':
            return `${name} submitted a timesheet for ${hours} hours${
                item.week_ending ? `, week ending ${fmtDate(item.week_ending)}` : ''}.`;
        case 'EXPENSE': {
            const value = money(item.amount, item.currency);
            return `${name} claimed ${value || 'an expense'}${
                item.category ? ` for ${humanText(item.category).toLowerCase()}` : ''}${
                item.description ? `: ${item.description}` : ''}.`;
        }
        case 'LEAVE_REQUEST':
        case 'LEAVE':
            return `${name} has asked for ${hours} hours off${
                item.start_date ? `, from ${fmtDate(item.start_date)} to ${fmtDate(item.end_date)}` : ''}.`;
        default:
            return `${name} has raised a request.`;
    }
};

const ApprovalsModule = memo(() => {
    const { toast } = useToast();
    const { data: queue, isLoading, error, refetch } = useApi(getApprovalQueue, [], true);

    const items = useMemo(() => (Array.isArray(queue) ? queue : []), [queue]);
    const ids = useMemo(() => items.map((i) => i.employee_uuid), [items]);
    const names = useEmployeeNames(ids);

    const [comments, setComments] = useState({});
    const [busy, setBusy] = useState(null);

    // Only leave hours are comparable; adding timesheet hours to them would be a
    // number that means nothing.
    const leaveHours = items
        .filter((i) => String(i.type || '').toUpperCase().startsWith('LEAVE'))
        .reduce((sum, i) => sum + (Number(i.hours) || 0), 0);

    const decide = useCallback(async (item, approved) => {
        const who = names[item.employee_uuid] || 'this person';
        setBusy(`${item.request_id}:${approved}`);
        try {
            // `approved` must reach the backend as a real boolean, an action string is falsy there.
            await actionApproval({
                request_id: item.request_id,
                approved: Boolean(approved),
                comments: (comments[item.request_id] || '').trim(),
            });
            toast({
                title: approved ? 'Request approved' : 'Request declined',
                description: `${who} has been told about your decision.`,
                variant: approved ? 'success' : 'default',
            });
            setComments((prev) => ({ ...prev, [item.request_id]: '' }));
            refetch();
        } catch (err) {
            toast({
                title: 'The decision was not saved',
                description: err.response?.data?.detail || err.message,
                variant: 'destructive',
            });
        } finally {
            setBusy(null);
        }
    }, [comments, names, toast, refetch]);

    const styles = useMemo(() => ({
        stat: { gridColumn: 'span 4', minWidth: 0 },
        list: { ...ui.panel, gridColumn: 'span 12', display: 'flex', flexDirection: 'column', gap: tokens.spacing?.sm },
        card: {
            padding: '14px 16px', borderRadius: tokens.border?.radius?.card,
            border: `1px solid ${tokens.color?.['border-600']}`,
            borderLeft: `3px solid ${tokens.color?.warning}`,
            background: tokens.color?.['panel-700'], marginBottom: tokens.spacing?.sm,
        },
        pill: {
            display: 'inline-flex', alignItems: 'center', flexShrink: 0,
            padding: '3px 9px', borderRadius: tokens.border?.radius?.full,
            fontSize: '11.5px', fontWeight: 500, whiteSpace: 'nowrap',
            color: tokens.color?.warning, border: `1px solid ${tokens.color?.warning}44`,
            background: `${tokens.color?.warning}14`,
        },
    }), []);

    return (
        <div style={ui.grid}>
            <div style={styles.stat}>
                <DataCard
                    title="Waiting on you"
                    value={<CountUp value={items.length} />}
                    icon={<CheckSquare size={15} />}
                    color={items.length ? tokens.color?.warning : tokens.color?.success}
                    subtitle={items.length ? 'Each one is blocking somebody' : 'Your queue is clear'}
                />
            </div>
            <div style={styles.stat}>
                <DataCard
                    title="Time off requested"
                    value={<CountUp value={leaveHours} />}
                    unit="hours"
                    icon={<CalendarDays size={15} />}
                    subtitle="Time off asked for in this queue"
                />
            </div>
            <div style={styles.stat}>
                <DataCard
                    title="People affected"
                    value={<CountUp value={new Set(ids.filter(Boolean)).size} />}
                    icon={<Users size={15} />}
                    subtitle="Team members with something outstanding"
                />
            </div>

            <div style={styles.list}>
                <div>
                    <h3 style={ui.h3}>Requests from your team</h3>
                    <p style={ui.hint}>
                        A decision here is final and the person is told straight away. Add a note if you are declining.
                    </p>
                </div>

                <ErrorNote error={error} context="your approvals queue" />
                {isLoading && items.length === 0 && <Loading label="Reading your approvals queue" />}

                {!isLoading && items.length === 0 && !error && (
                    <EmptyState
                        icon={CheckCircle}
                        title="Nothing is waiting for you"
                        action="Time off, timesheets and expense claims from your team all land here."
                    />
                )}

                <div style={ui.scroller('440px')} className="emp-scroll">
                    {items.map((item) => {
                        const who = names[item.employee_uuid];
                        return (
                            <div key={item.request_id} style={styles.card}>
                                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: tokens.spacing?.sm, marginBottom: 8 }}>
                                    <span style={{ color: tokens.color?.['accent-primary'], fontSize: '11.5px', fontWeight: 600, letterSpacing: '0.02em', textTransform: 'uppercase' }}>
                                        {requestKind(item.type)}
                                    </span>
                                    <span style={styles.pill}>Awaiting your decision</span>
                                </div>

                                <p style={{ margin: '0 0 6px 0', color: tokens.color?.['text-100'], fontSize: tokens.typography?.base?.fontSize, lineHeight: 1.55 }}>
                                    {describeRequest(item, who)}
                                </p>
                                <p style={{ ...ui.hint, margin: '0 0 10px 0' }}>
                                    Submitted {fmtDate(item.submitted_at)}
                                    {who ? '' : '. The name could not be looked up, so only the record is shown.'}
                                </p>

                                <input
                                    type="text"
                                    value={comments[item.request_id] || ''}
                                    onChange={(e) => setComments((prev) => ({ ...prev, [item.request_id]: e.target.value }))}
                                    placeholder="Optional note the person will see with your decision"
                                    style={{ ...ui.input, marginBottom: 10 }}
                                />

                                <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', flexWrap: 'wrap' }}>
                                    <Btn
                                        tone="ghost"
                                        icon={XCircle}
                                        loading={busy === `${item.request_id}:false`}
                                        disabled={Boolean(busy)}
                                        onClick={() => decide(item, false)}
                                    >
                                        Decline
                                    </Btn>
                                    <Btn
                                        tone="success"
                                        icon={CheckCircle}
                                        loading={busy === `${item.request_id}:true`}
                                        disabled={Boolean(busy)}
                                        onClick={() => decide(item, true)}
                                    >
                                        Approve
                                    </Btn>
                                </div>
                            </div>
                        );
                    })}
                </div>
            </div>
        </div>
    );
});
ApprovalsModule.displayName = 'ApprovalsModule';

/* -------------------------------------------------------------------------- */
/* Performance                                                                */
/* -------------------------------------------------------------------------- */
const RATINGS = [
    { value: 5, label: 'Outstanding, well beyond what the role asks for' },
    { value: 4, label: 'Strong, consistently above expectations' },
    { value: 3, label: 'Solid, doing the job as expected' },
    { value: 2, label: 'Below expectations, needs support' },
    { value: 1, label: 'Not meeting the requirements of the role' },
];

const PerformanceModule = memo(() => {
    const { toast } = useToast();
    const roster = useRoster();
    const [selectedId, setSelectedId] = useState('');
    const [rating, setRating] = useState('');
    const [isSaving, setIsSaving] = useState(false);

    const { data: trend, isLoading: trendLoading, error: trendError } = useApi(getTeamPerformanceTrend, [], true);
    const {
        data: perf, isLoading: perfLoading, error: perfError, refetch: refetchPerf,
    } = useApi(getEmployeePerformance, [selectedId], Boolean(selectedId));
    const { data: feedback, isLoading: feedbackLoading } = useApi(getPeerFeedback, [selectedId], Boolean(selectedId));

    const series = Array.isArray(trend) ? trend : [];
    const first = series[0];
    const last = series[series.length - 1];
    const movement = (first && last) ? Number(last.value) - Number(first.value) : null;

    const selected = roster.people.find((p) => p.id === selectedId);
    const score = Number(perf?.score);
    const peers = Array.isArray(feedback) ? feedback : [];

    const saveReview = useCallback(async (e) => {
        e.preventDefault();
        if (!selectedId || !rating || isSaving) return;
        setIsSaving(true);
        try {
            await submitPerformanceReview({ employee_uuid: selectedId, overall_rating: Number(rating) });
            toast({
                title: 'Review recorded',
                description: `${selected?.name || 'The review'} is now on record at ${rating} out of 5.`,
                variant: 'success',
            });
            setRating('');
            refetchPerf();
        } catch (err) {
            toast({
                title: 'The review was not saved',
                description: err.response?.data?.detail || err.message,
                variant: 'destructive',
            });
        } finally {
            setIsSaving(false);
        }
    }, [selectedId, rating, isSaving, selected, toast, refetchPerf]);

    const styles = useMemo(() => ({
        chart: { gridColumn: 'span 12', minWidth: 0 },
        left: { ...ui.panel, gridColumn: 'span 5', display: 'flex', flexDirection: 'column', gap: tokens.spacing?.md },
        right: { ...ui.panel, gridColumn: 'span 7', display: 'flex', flexDirection: 'column', gap: tokens.spacing?.sm },
    }), []);

    return (
        <div style={ui.grid}>
            <div style={styles.chart}>
                <DataCard
                    title="Team performance over time"
                    isChart
                    minHeight="300px"
                    icon={<Gauge size={15} />}
                    footer={null}
                >
                    <ErrorNote error={trendError} context="the performance trend" />
                    {trendLoading && series.length === 0 && <Loading label="Reading monthly averages" />}
                    {!trendError && (
                        <>
                            <p style={{ ...ui.hint, marginTop: 0 }}>
                                {series.length === 0
                                    ? 'No monthly averages have been recorded yet.'
                                    : movement === null
                                        ? 'Monthly average rating across everyone with a recorded review.'
                                        : `Monthly average rating, ${movement >= 0 ? 'up' : 'down'} ${Math.abs(movement).toFixed(2)} points since ${first.name}.`}
                            </p>
                            <AreaChartWidget
                                data={series}
                                minHeight="220px"
                                color={movement !== null && movement < 0 ? tokens.color?.warning : tokens.color?.['accent-primary']}
                            />
                        </>
                    )}
                </DataCard>
            </div>

            <div style={styles.left}>
                <div>
                    <h3 style={ui.h3}>Record a review</h3>
                    <p style={ui.hint}>What you save here becomes part of the person's permanent record.</p>
                </div>

                <ErrorNote error={roster.error} context="your team roster" />

                <form onSubmit={saveReview} style={{ display: 'flex', flexDirection: 'column', gap: tokens.spacing?.md }}>
                    <RosterSelect roster={roster} value={selectedId} onChange={(v) => { setSelectedId(v); setRating(''); }} label="Who are you reviewing" />

                    <div>
                        <label style={ui.label}>Overall rating</label>
                        <select
                            value={rating}
                            onChange={(e) => setRating(e.target.value)}
                            style={ui.input}
                            disabled={!selectedId || isSaving}
                            required
                        >
                            <option value="">Choose a rating</option>
                            {RATINGS.map((r) => (
                                <option key={r.value} value={r.value}>{r.value} of 5, {r.label}</option>
                            ))}
                        </select>
                    </div>

                    <Btn type="submit" icon={UserCheck} loading={isSaving} disabled={!selectedId || !rating}>
                        Save this review
                    </Btn>
                </form>
            </div>

            <div style={styles.right}>
                <h3 style={ui.h3}>{selected ? `${selected.name} today` : 'Individual record'}</h3>

                {!selectedId && (
                    <EmptyState
                        icon={Gauge}
                        title="Nobody selected"
                        action="Choose a team member on the left to see their current rating and the feedback their peers have left."
                    />
                )}

                {selectedId && (
                    <>
                        <ErrorNote error={perfError} context={`the record for ${selected?.name || 'this person'}`} />
                        {perfLoading && !perf && <Loading label="Reading their record" />}

                        {perf && !perfError && (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                                <div style={{ display: 'flex', alignItems: 'baseline', gap: 9, flexWrap: 'wrap' }}>
                                    <span style={{ fontSize: 28, fontWeight: 640, letterSpacing: '-0.02em', color: tokens.color?.['text-100'], fontVariantNumeric: 'tabular-nums' }}>
                                        {Number.isFinite(score) ? <CountUp value={score} decimals={2} /> : 'Not rated'}
                                    </span>
                                    {Number.isFinite(score) && <span style={{ fontSize: 13, color: tokens.color?.['muted-500'] }}>out of 5</span>}
                                </div>
                                {Number.isFinite(score) && (
                                    <LiveMeter
                                        pct={(score / 5) * 100}
                                        color={score >= 4 ? tokens.color?.success : (score >= 3 ? tokens.color?.['accent-primary'] : tokens.color?.warning)}
                                    />
                                )}
                                <p style={{ ...ui.hint, marginTop: 0 }}>
                                    Last reviewed {fmtDate(perf.last_review_date)}.
                                </p>
                            </div>
                        )}

                        <h3 style={{ ...ui.h3, marginTop: tokens.spacing?.md }}>What their peers said</h3>
                        {feedbackLoading && <Loading label="Reading peer feedback" />}
                        {!feedbackLoading && peers.length === 0 && (
                            <EmptyState
                                icon={MessageSquare}
                                title="No peer feedback on record"
                                action="Nobody has left written feedback for this person yet."
                            />
                        )}
                        <div style={ui.scroller('200px')} className="emp-scroll">
                            {peers.map((f, i) => (
                                <div key={f.id || i} style={{ ...ui.listRow, alignItems: 'flex-start' }}>
                                    <div style={ui.rowMain}>
                                        <span style={{ ...ui.rowTitle, whiteSpace: 'normal' }}>{f.comment || f.text || f.feedback || 'No comment recorded'}</span>
                                        <span style={ui.rowMeta}>{f.from_name || f.author || 'Anonymous colleague'}{f.date ? `, ${fmtDate(f.date)}` : ''}</span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </>
                )}
            </div>
        </div>
    );
});
PerformanceModule.displayName = 'PerformanceModule';

/* -------------------------------------------------------------------------- */
/* Attrition simulation                                                        */
/* -------------------------------------------------------------------------- */
const LEVERS = [
    { key: 'salary_increase_pct', label: 'Pay rise', unit: '%', step: 1 },
    { key: 'training_sessions', label: 'Extra training sessions per quarter', unit: 'sessions', step: 1 },
    { key: 'remote_work_days', label: 'Extra days at home per week', unit: 'days', step: 1 },
];

const readableRecommendation = (rec) => {
    if (!rec) return '';
    if (typeof rec === 'string') return rec;
    return rec.message || '';
};

const SimulationModule = memo(() => {
    const { toast } = useToast();
    const roster = useRoster();
    const [selectedId, setSelectedId] = useState('');
    const [levers, setLevers] = useState({ salary_increase_pct: 5, training_sessions: 1, remote_work_days: 1 });
    const [result, setResult] = useState(null);
    const [simError, setSimError] = useState(null);
    const [isRunning, setIsRunning] = useState(false);

    // The real, current model score for this person, used as the simulation baseline.
    const {
        data: prediction, isLoading: predLoading, error: predError,
    } = useApi(predictAttritionRisk, [{ employee_id: selectedId }], Boolean(selectedId));

    const selected = roster.people.find((p) => p.id === selectedId);
    const baseline = Number(prediction?.risk_score);
    const hasBaseline = Number.isFinite(baseline);

    const run = useCallback(async () => {
        if (!selectedId || isRunning) return;
        setIsRunning(true);
        setResult(null);
        setSimError(null);
        try {
            const res = await runSimulation(selectedId, levers);
            const d = res.data || {};
            const m = d.metrics || {};
            setResult({
                id: d.simulation_id,
                riskDelta: Number(m.risk_score_delta) || 0,
                probabilityChange: Number(m.attrition_probability_change) || 0,
                productivity: Number(m.productivity_impact) || 0,
                cost: Number(m.cost_implication) || 0,
                confidence: Number(d.confidence_score),
                recommendation: readableRecommendation(d.prescriptive_recommendation),
                applied: d.adjustments_applied || {},
            });
            toast({
                title: 'Simulation finished',
                description: `Modelled the effect on ${selected?.name || 'this person'}.`,
                variant: 'success',
            });
        } catch (err) {
            // No invented numbers on failure: the panel stays empty and says why.
            const detail = err.response?.data?.detail || err.message;
            setSimError(detail);
            toast({ title: 'The simulation could not run', description: detail, variant: 'destructive' });
        } finally {
            setIsRunning(false);
        }
    }, [selectedId, levers, isRunning, selected, toast]);

    const projected = (hasBaseline && result) ? Math.max(0, Math.min(1, baseline + result.riskDelta)) : null;

    const styles = useMemo(() => ({
        left: { ...ui.panel, gridColumn: 'span 5', display: 'flex', flexDirection: 'column', gap: tokens.spacing?.md },
        right: { ...ui.panel, gridColumn: 'span 7', display: 'flex', flexDirection: 'column', gap: tokens.spacing?.sm, minHeight: 420 },
        xai: { gridColumn: 'span 12', minWidth: 0 },
        metric: { display: 'flex', flexDirection: 'column', gap: 3, minWidth: 130 },
        metricLabel: { fontSize: '11.5px', color: tokens.color?.['muted-600'] },
        metricValue: { fontSize: 19, fontWeight: 640, color: tokens.color?.['text-100'], fontVariantNumeric: 'tabular-nums' },
    }), []);

    return (
        <div style={ui.grid}>
            <div style={styles.left}>
                <div>
                    <h3 style={ui.h3}>Test a change before you make it</h3>
                    <p style={ui.hint}>
                        Pick someone, set the levers you are considering, and the model projects what it would do to
                        their chance of leaving. Nothing is changed for real.
                    </p>
                </div>

                <ErrorNote error={roster.error} context="your team roster" />
                <RosterSelect roster={roster} value={selectedId} onChange={(v) => { setSelectedId(v); setResult(null); setSimError(null); }} label="Who are you modelling" />

                {selectedId && (
                    <div>
                        <ErrorNote error={predError} context="their current risk score" />
                        {predLoading && !prediction && <Loading label="Reading their current risk" />}
                        {hasBaseline && (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, paddingTop: 4 }}>
                                <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 8 }}>
                                    <span style={styles.metricLabel}>Chance of leaving today</span>
                                    <span style={{ ...styles.metricValue, fontSize: 16 }}>
                                        <CountUp value={baseline * 100} decimals={1} suffix="%" />
                                    </span>
                                </div>
                                <LiveMeter
                                    pct={baseline * 100}
                                    color={baseline >= 0.7 ? tokens.color?.danger : (baseline >= 0.4 ? tokens.color?.warning : tokens.color?.success)}
                                />
                                {prediction?.recommendation && (
                                    <p style={{ ...ui.hint, marginTop: 2 }}>{prediction.recommendation}</p>
                                )}
                            </div>
                        )}
                    </div>
                )}

                {LEVERS.map((l) => (
                    <div key={l.key}>
                        <label style={ui.label}>{l.label}</label>
                        <input
                            type="number"
                            step={l.step}
                            value={levers[l.key]}
                            onChange={(e) => setLevers((p) => ({ ...p, [l.key]: Number(e.target.value) || 0 }))}
                            style={ui.input}
                            disabled={isRunning}
                        />
                    </div>
                ))}

                <Btn icon={Play} onClick={run} loading={isRunning} disabled={!selectedId}>
                    {isRunning ? 'Running the model' : 'Run the simulation'}
                </Btn>
            </div>

            <div style={styles.right}>
                <h3 style={ui.h3}>What the model projects</h3>

                {!result && (
                    <EmptyState
                        icon={simError ? AlertTriangle : TrendingDown}
                        title={simError ? 'The simulation could not run' : 'Nothing modelled yet'}
                        action={simError || 'Choose a team member, set the levers on the left and run the simulation to see the projected effect.'}
                    />
                )}

                {result && (
                    <>
                        {hasBaseline && projected !== null ? (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: tokens.spacing?.md }}>
                                <p style={{ margin: 0, color: tokens.color?.['text-100'], fontSize: tokens.typography?.base?.fontSize, lineHeight: 1.55 }}>
                                    With these changes, {selected?.name || 'this person'} would go from a{' '}
                                    <strong>{(baseline * 100).toFixed(1)}%</strong> chance of leaving to{' '}
                                    <strong style={{ color: result.riskDelta <= 0 ? tokens.color?.success : tokens.color?.danger }}>
                                        {(projected * 100).toFixed(1)}%
                                    </strong>
                                    {result.riskDelta === 0 ? ', which is no change at all.' : (result.riskDelta < 0 ? ', a genuine improvement.' : ', which makes things worse.')}
                                </p>
                                <LiveMeter label="Where they are today" pct={baseline * 100} color={tokens.color?.['muted-500']} height={9} />
                                <LiveMeter
                                    label="Where this change would put them"
                                    pct={projected * 100}
                                    color={result.riskDelta <= 0 ? tokens.color?.success : tokens.color?.danger}
                                    height={9}
                                />
                            </div>
                        ) : (
                            <p style={{ ...ui.hint, marginTop: 0 }}>
                                The model returned a change of {(result.riskDelta * 100).toFixed(1)} points, but the
                                person's current risk score is not available, so a before and after cannot be drawn.
                            </p>
                        )}

                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: tokens.spacing?.lg, paddingTop: tokens.spacing?.sm }}>
                            <div style={styles.metric}>
                                <span style={styles.metricLabel}>Change in risk score</span>
                                <span style={{ ...styles.metricValue, color: result.riskDelta <= 0 ? tokens.color?.success : tokens.color?.danger }}>
                                    {result.riskDelta > 0 ? '+' : ''}{(result.riskDelta * 100).toFixed(1)} points
                                </span>
                            </div>
                            <div style={styles.metric}>
                                <span style={styles.metricLabel}>Effect on their output</span>
                                <span style={styles.metricValue}>
                                    {result.productivity === 0 ? 'No change modelled' : `${result.productivity > 0 ? '+' : ''}${result.productivity}`}
                                </span>
                            </div>
                            <div style={styles.metric}>
                                <span style={styles.metricLabel}>Cost of the change</span>
                                <span style={styles.metricValue}>
                                    {result.cost === 0 ? 'None modelled' : result.cost.toLocaleString()}
                                </span>
                            </div>
                            {Number.isFinite(result.confidence) && (
                                <div style={styles.metric}>
                                    <span style={styles.metricLabel}>How sure the model is</span>
                                    <span style={styles.metricValue}>
                                        <CountUp value={result.confidence * 100} suffix="%" />
                                    </span>
                                </div>
                            )}
                        </div>

                        {result.recommendation && (
                            <p style={{ color: tokens.color?.['text-100'], fontSize: tokens.typography?.base?.fontSize, lineHeight: 1.55, marginBottom: 0 }}>
                                {result.recommendation}
                            </p>
                        )}

                        {Object.keys(result.applied).length > 0 && (
                            <p style={{ ...ui.hint, marginTop: 0 }}>
                                Based on {Object.entries(result.applied)
                                    .map(([k, v]) => `${(LEVERS.find((l) => l.key === k)?.label || humanText(k)).toLowerCase()} set to ${v}`)
                                    .join(', ')}.
                            </p>
                        )}
                    </>
                )}
            </div>

            <div style={styles.xai}>
                <XAIDecisionPanel employeeId={selectedId || null} employeeName={selected?.name} />
            </div>
        </div>
    );
});
SimulationModule.displayName = 'SimulationModule';

/* -------------------------------------------------------------------------- */
/* Shell                                                                      */
/* -------------------------------------------------------------------------- */
export const ManagerPortalComponent = memo(() => {
    const location = useLocation();
    const requested = useMemo(() => {
        const raw = new URLSearchParams(location.search).get('module') || 'team';
        return ALIASES[raw] || raw;
    }, [location.search]);

    const active = MODULES.find((m) => m.key === requested);

    const styles = useMemo(() => ({
        container: { display: 'flex', flexDirection: 'column', gap: tokens.spacing?.lg, minWidth: 0, maxWidth: '100%' },
        header: { borderBottom: `1px solid ${tokens.color?.['border-600']}`, paddingBottom: tokens.spacing?.md },
        title: {
            margin: 0, display: 'flex', alignItems: 'center', gap: tokens.spacing?.sm,
            fontSize: tokens.typography?.h1?.fontSize, fontWeight: tokens.typography?.h1?.fontWeight,
            letterSpacing: '-0.022em', color: tokens.color?.['text-100'],
        },
        subtitle: { margin: '6px 0 0 0', fontSize: tokens.typography?.small?.fontSize, color: tokens.color?.['muted-600'] },
        tabs: { display: 'flex', gap: 6, overflowX: 'auto', overflowY: 'hidden', paddingBottom: 4, marginTop: tokens.spacing?.md, maxWidth: '100%' },
        tab: (isActive) => ({
            display: 'inline-flex', alignItems: 'center', gap: 7, flexShrink: 0,
            padding: '7px 13px', borderRadius: tokens.border?.radius?.full,
            border: `1px solid ${isActive ? `${tokens.color?.['accent-primary']}55` : tokens.color?.['border-600']}`,
            background: isActive ? `${tokens.color?.['accent-primary']}18` : 'transparent',
            color: isActive ? tokens.color?.['text-100'] : tokens.color?.['muted-500'],
            fontSize: tokens.typography?.button?.fontSize, fontWeight: 500,
            textDecoration: 'none', whiteSpace: 'nowrap', transition: tokens.ui?.transition?.micro,
        }),
    }), []);

    const body = () => {
        switch (requested) {
            case 'team': return <TeamModule />;
            case 'approvals': return <ApprovalsModule />;
            case 'performance': return <PerformanceModule />;
            case 'risk': return <RiskOverview />;
            case 'simulation': return <SimulationModule />;
            case 'recognition': return <StarRecognitionWidget />;
            default:
                return (
                    <EmptyState
                        icon={AlertTriangle}
                        title={`There is no manager section called "${requested}"`}
                        action="Pick one of the sections above to carry on."
                    />
                );
        }
    };

    const Icon = active?.icon || Users;

    return (
        <div style={styles.container} className="portal-container">
            <div style={styles.header}>
                <h1 style={styles.title}>
                    <Icon size={26} color={tokens.color?.['accent-primary']} />
                    {active?.title || 'Manager portal'}
                </h1>
                <p style={styles.subtitle}>
                    {active?.blurb || 'Everything here is read live from your own team records.'}
                </p>

                <nav style={styles.tabs} className="emp-scroll" aria-label="Manager portal sections">
                    {MODULES.map((m) => {
                        const TabIcon = m.icon;
                        return (
                            <Link key={m.key} to={`/manager-portal?module=${m.key}`} style={styles.tab(m.key === requested)}>
                                <TabIcon size={14} /> {m.label}
                            </Link>
                        );
                    })}
                </nav>
            </div>

            {body()}
            <EmployeeStyles />
        </div>
    );
});

ManagerPortalComponent.displayName = 'ManagerPortalComponent';
export default ManagerPortalComponent;
