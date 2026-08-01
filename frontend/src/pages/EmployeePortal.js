// /frontend/src/pages/EmployeePortal.js
// The employee self-service portal. Every number on every module is read from a
// real backend endpoint; where an endpoint returns nothing, the module says so
// plainly instead of inventing a figure.
import React, { useMemo, memo, useState, useCallback, useRef, useEffect } from 'react';
import { useLocation, Link } from 'react-router-dom';
import { theme as tokens } from '../theme';
import { useAuth } from '../contexts/AuthContext';

import {
    getEmployeeDashboard, submitLeaveRequest, getLeaveBalance, getLeaveHistory,
    getPersonalInfo, recordConsentChange, revealOwnPII, getRecognitionLeaderboard,
    getTimesheets, getRetentionPreference, saveRetentionPreference, submitFeedback, getAnnouncements,
} from '../config/api';
import { useApi } from '../hooks/useApi';
import { useToast } from '../hooks/use-toast';

import DataCard from '../components/DataCard';
import BarChartWidget from '../components/charts/BarChartWidget';
import PieChartWidget from '../components/charts/PieChartWidget';
import AreaChartWidget from '../components/charts/AreaChartWidget';
import { CountUp, LiveMeter } from '../components/live/LivePrimitives';
import DigitalTwinChat from '../components/DigitalTwinChat';

import TimesheetSubmission from '../components/TimesheetSubmission';
import TalentExperienceHub from '../components/TalentExperienceHub';
import PayModule from '../components/employee/PayModule';
import ExpenseModule from '../components/employee/ExpenseModule';
import DocumentsModule from '../components/employee/DocumentsModule';
import OffboardingModule from '../components/employee/OffboardingModule';
import OnboardingPlanModule, { OnboardingPlanCard } from '../components/employee/OnboardingPlanModule';
import GoalsModule from '../components/employee/GoalsModule';
import PerformanceCycleModule from '../components/employee/PerformanceCycleModule';
import PulseSurveyCard from '../components/employee/PulseSurveyCard';
import AskHiRoModule from '../components/employee/AskHiRoModule';
import { ui, Btn, Loading, EmptyState, ErrorNote, StatusPill, fmtDate, readablePolicy, readableRole, EmployeeStyles } from '../components/employee/shared';

import {
    User, Calendar, CheckCircle, XCircle, AlertTriangle, Eye, EyeOff,
    LayoutDashboard, Clock, Wallet, Sparkles, FileText, ReceiptText, Lock,
    Star, Send, Award, MessageSquare, CalendarPlus, Archive, ClipboardCheck, Target,
} from 'lucide-react';

const MODULES = [
    { key: 'dashboard', label: 'My Dashboard', title: 'My dashboard', icon: LayoutDashboard },
    { key: 'onboarding', label: 'Onboarding', title: 'Your onboarding plan', icon: ClipboardCheck },
    { key: 'timesheets', label: 'Timesheets', title: 'Timesheets', icon: Clock },
    { key: 'leave', label: 'Leave', title: 'Leave and balance', icon: Calendar },
    { key: 'pay', label: 'Pay & Benefits', title: 'Pay and benefits', icon: Wallet },
    { key: 'goals', label: 'Goals', title: 'Goals and key results', icon: Target },
    { key: 'ask', label: 'Ask HiRo', title: 'Ask HiRo, and what it tells you', icon: Sparkles },
    { key: 'growth', label: 'Growth', title: 'Skills, career and performance', icon: Sparkles },
    { key: 'documents', label: 'Documents', title: 'My documents', icon: FileText },
    { key: 'expenses', label: 'Expenses', title: 'Expense claims', icon: ReceiptText },
    { key: 'pii', label: 'Privacy', title: 'Privacy, consent and feedback', icon: Lock },
    { key: 'offboarding', label: 'Offboarding', title: 'Offboarding and knowledge transfer', icon: Archive },
];

// Growth pairs the learning hub with the two things it feeds: what you committed
// to this cycle, and where the review of that cycle has got to.
const GrowthModule = memo(() => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: tokens.spacing?.lg }}>
        <TalentExperienceHub />
        <div style={ui.grid} className="portal-grid">
            <EmployeeStyles />
            <PerformanceCycleModule />
        </div>
    </div>
));
GrowthModule.displayName = 'GrowthModule';

/* -------------------------------------------------------------------------- */
/* Dashboard                                                                   */
/* -------------------------------------------------------------------------- */
const EmployeeDashboardModule = memo(() => {
    const { user } = useAuth();

    const { data: dash, isLoading: dashLoading, error: dashError } = useApi(getEmployeeDashboard, [user?.id], !!user?.id);
    const { data: balance, isLoading: balanceLoading } = useApi(getLeaveBalance, [], true);
    const { data: rawHistory } = useApi(getLeaveHistory, [], true);
    const { data: rawSheets } = useApi(getTimesheets, [], true);
    const { data: leaderboard } = useApi(getRecognitionLeaderboard, [], true);
    // Announcements are a broadcast: everyone signed in should see them.
    const { data: announcementsResp } = useApi(getAnnouncements, [], true);
    const announcements = useMemo(() => announcementsResp?.announcements || [], [announcementsResp]);

    const sheets = useMemo(() => (Array.isArray(rawSheets) ? rawSheets : []), [rawSheets]);
    const history = useMemo(
        () => (Array.isArray(rawHistory) ? rawHistory : (rawHistory?.requests || [])),
        [rawHistory]
    );

    const balanceHours = Number(balance?.balance_hours) || 0;
    const usedHours = Number(balance?.used_hours) || 0;
    const entitlement = balanceHours + usedHours;
    const usedPct = entitlement > 0 ? (usedHours / entitlement) * 100 : 0;

    const totalHours = sheets.reduce((sum, s) => sum + (Number(s.hours) || 0), 0);
    const pendingLeave = history.filter((r) => String(r.status || '').toUpperCase().startsWith('PEND')).length;

    const myStars = useMemo(() => {
        const row = (leaderboard || []).find(
            (u) => u.user_id === user?.username || u.user_id === user?.id || u.user_name === user?.full_name
        );
        return Number(row?.stars) || 0;
    }, [leaderboard, user]);

    const recognition = useMemo(
        () => (leaderboard || []).map((u) => ({ name: u.user_name, value: Number(u.stars) || 0 })),
        [leaderboard]
    );

    const hoursTrend = useMemo(
        () => sheets.slice().reverse().map((s) => ({ name: fmtDate(s.week), value: Number(s.hours) || 0 })),
        [sheets]
    );

    return (
        <div style={ui.grid} className="portal-grid">
            <EmployeeStyles />

            {dashError && <div style={{ gridColumn: 'span 12' }}><ErrorNote error={dashError} context="your dashboard summary" /></div>}

            {/* Both render nothing unless there is something real to act on. */}
            <OnboardingPlanCard />
            <PulseSurveyCard />

            <div style={{ gridColumn: 'span 3' }}>
                <DataCard title="Leave hours available" value={<CountUp value={balanceHours} decimals={1} />} unit="hours"
                    icon={<Calendar size={15} />} color={tokens.color?.success}
                    subtitle={balance?.policy ? `Under the ${readablePolicy(balance.policy)} leave policy` : 'Loading your policy'}
                    footer={<LiveMeter pct={usedPct} color={tokens.color?.warning} label="Share of entitlement already used" />} />
            </div>
            <div style={{ gridColumn: 'span 3' }}>
                <DataCard title="Hours logged on timesheets" value={<CountUp value={totalHours} decimals={1} />} unit="hours"
                    icon={<Clock size={15} />} color={tokens.color?.['accent-primary']}
                    subtitle={`Across ${sheets.length} submitted week${sheets.length === 1 ? '' : 's'}`} />
            </div>
            <div style={{ gridColumn: 'span 3' }}>
                <DataCard title="Leave requests awaiting a decision" value={<CountUp value={pendingLeave} />} unit="requests"
                    icon={<CalendarPlus size={15} />} color={tokens.color?.warning}
                    subtitle={`${history.length} request${history.length === 1 ? '' : 's'} on record`} />
            </div>
            <div style={{ gridColumn: 'span 3' }}>
                <DataCard title="Recognition stars received" value={<CountUp value={myStars} />} unit="stars"
                    icon={<Star size={15} />} color={tokens.color?.['accent-secondary']}
                    subtitle="Awarded by colleagues across HiRo" />
            </div>

            <div style={{ ...ui.panel, gridColumn: 'span 5' }}>
                <h3 style={ui.h3}>Where things stand</h3>
                {dashLoading && <Loading label="Loading your summary" />}
                {!dashLoading && (
                    <>
                        <p style={{ ...ui.hint, color: tokens.color?.['text-100'], fontSize: tokens.typography?.base?.fontSize }}>
                            {dash?.dashboard_message || 'No summary message has been generated for your account yet.'}
                        </p>
                        <div style={{ marginTop: tokens.spacing?.sm }}>
                            <div style={ui.listRow}>
                                <div style={ui.rowMain}>
                                    <span style={ui.rowTitle}>Your record</span>
                                    <span style={ui.rowMeta}>{dash?.data?.full_name || user?.full_name || 'Not recorded'}</span>
                                </div>
                                <span style={ui.rowMeta}>{dash?.employee_id || 'No employee id linked'}</span>
                            </div>
                            <div style={ui.listRow}>
                                <div style={ui.rowMain}>
                                    <span style={ui.rowTitle}>Leave used so far</span>
                                    <span style={ui.rowMeta}>Out of {entitlement || 0} hours of entitlement</span>
                                </div>
                                <span style={{ color: tokens.color?.warning, fontWeight: 600 }}>
                                    <CountUp value={usedHours} decimals={1} suffix=" h" />
                                </span>
                            </div>
                            <div style={ui.listRow}>
                                <div style={ui.rowMain}>
                                    <span style={ui.rowTitle}>Latest timesheet</span>
                                    <span style={ui.rowMeta}>{sheets[0] ? `Week ending ${fmtDate(sheets[0].week)}, ${sheets[0].hours} hours` : 'You have not submitted a week yet'}</span>
                                </div>
                                {sheets[0] && <StatusPill status={sheets[0].status} />}
                            </div>
                        </div>
                        {balanceLoading && <Loading label="Loading your leave balance" />}
                    </>
                )}
                <div style={{ display: 'flex', gap: tokens.spacing?.xs, marginTop: tokens.spacing?.md, flexWrap: 'wrap' }}>
                    <Link to="/employee-portal?module=timesheets" style={{ textDecoration: 'none' }}>
                        <Btn tone="ghost" icon={Clock}>Submit a timesheet</Btn>
                    </Link>
                    <Link to="/employee-portal?module=leave" style={{ textDecoration: 'none' }}>
                        <Btn tone="ghost" icon={CalendarPlus}>Request leave</Btn>
                    </Link>
                </div>
            </div>

            <div style={{ gridColumn: 'span 7' }}>
                <DataCard title="Hours you logged, week by week" isChart minHeight="300px">
                    <AreaChartWidget data={hoursTrend} minHeight="260px" color={tokens.color?.['accent-primary']}
                        label="Built from the timesheets you submitted, oldest first." />
                </DataCard>
            </div>

            <div style={{ ...ui.panel, gridColumn: 'span 12' }}>
                <h3 style={ui.h3}>Announcements</h3>
                {announcements.length === 0 ? (
                    <p style={ui.hint}>Nothing has been announced yet.</p>
                ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: tokens.spacing?.xs, marginTop: tokens.spacing?.xs }}>
                        {announcements.slice(0, 5).map((a) => (
                            <div key={a.id} style={ui.listRow}>
                                <div style={ui.rowMain}>
                                    <span style={ui.rowTitle}>{a.title}</span>
                                    <span style={ui.rowMeta}>{a.content}</span>
                                </div>
                                <span style={ui.rowMeta}>{fmtDate(a.created_at)}</span>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            <div style={{ gridColumn: 'span 12' }}>
                <DataCard title="Recognition stars across the organisation" isChart minHeight="300px">
                    <BarChartWidget data={recognition} minHeight="260px" color={tokens.color?.warning}
                        label="Stars colleagues have given each other. Yours are highlighted in the card above." />
                </DataCard>
            </div>
        </div>
    );
});
EmployeeDashboardModule.displayName = 'EmployeeDashboardModule';

/* -------------------------------------------------------------------------- */
/* Leave                                                                       */
/* -------------------------------------------------------------------------- */
const LeaveModule = memo(() => {
    const { toast } = useToast();
    const [form, setForm] = useState({ start_date: '', end_date: '', hours: '' });
    const [isSubmitting, setIsSubmitting] = useState(false);

    const { data: balance, isLoading: balanceLoading, error: balanceError, refetch: refetchBalance } = useApi(getLeaveBalance, [], true);
    const { data: rawHistory, isLoading: historyLoading, error: historyError, refetch: refetchHistory } = useApi(getLeaveHistory, [], true);

    const history = useMemo(
        () => (Array.isArray(rawHistory) ? rawHistory : (rawHistory?.requests || [])),
        [rawHistory]
    );

    const balanceHours = Number(balance?.balance_hours) || 0;
    const usedHours = Number(balance?.used_hours) || 0;
    const entitlement = balanceHours + usedHours;

    const byStatus = useMemo(() => {
        const counts = history.reduce((acc, r) => {
            const k = String(r.status || 'UNKNOWN').toUpperCase();
            acc[k] = (acc[k] || 0) + 1;
            return acc;
        }, {});
        return Object.entries(counts).map(([name, value]) => ({
            name: name.charAt(0) + name.slice(1).toLowerCase().replace(/_/g, ' '),
            value,
        }));
    }, [history]);

    // Working days between the two dates, eight hours each, as a starting figure.
    const suggestedHours = useMemo(() => {
        if (!form.start_date || !form.end_date) return 0;
        const start = new Date(form.start_date);
        const end = new Date(form.end_date);
        if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || end < start) return 0;
        return (Math.round((end - start) / 86400000) + 1) * 8;
    }, [form.start_date, form.end_date]);

    const hoursValue = form.hours === '' ? suggestedHours : Number(form.hours);
    const datesValid = !!form.start_date && !!form.end_date && new Date(form.end_date) >= new Date(form.start_date);
    const valid = datesValid && Number.isFinite(hoursValue) && hoursValue > 0;
    const overBalance = valid && hoursValue > balanceHours;

    const handleSubmit = useCallback(async (e) => {
        e.preventDefault();
        if (!datesValid) {
            toast({ title: 'Check the dates', description: 'Pick a start date and an end date that is on or after it.', variant: 'destructive' });
            return;
        }
        if (!valid) {
            toast({ title: 'Check the hours', description: 'The request must cover more than zero hours.', variant: 'destructive' });
            return;
        }
        setIsSubmitting(true);
        try {
            await submitLeaveRequest({ start_date: form.start_date, end_date: form.end_date, hours: hoursValue });
            toast({
                title: 'Leave requested',
                description: `${hoursValue} hours from ${fmtDate(form.start_date)} to ${fmtDate(form.end_date)} sent to your manager.`,
                variant: 'success',
            });
            setForm({ start_date: '', end_date: '', hours: '' });
            refetchBalance();
            refetchHistory();
        } catch (err) {
            toast({ title: 'Leave request failed', description: err.response?.data?.detail || err.message, variant: 'destructive' });
        } finally {
            setIsSubmitting(false);
        }
    }, [datesValid, valid, form, hoursValue, toast, refetchBalance, refetchHistory]);

    return (
        <div style={ui.grid} className="portal-grid">
            <EmployeeStyles />

            <div style={{ gridColumn: 'span 4' }}>
                <DataCard title="Leave hours available" value={<CountUp value={balanceHours} decimals={1} />} unit="hours"
                    icon={<Calendar size={15} />} color={tokens.color?.success}
                    subtitle={balance?.policy ? `Under the ${readablePolicy(balance.policy)} leave policy` : 'Loading your policy'}
                    footer={<LiveMeter pct={entitlement ? (balanceHours / entitlement) * 100 : 0}
                        color={tokens.color?.success} label="Remaining share of your entitlement" />} />
            </div>
            <div style={{ gridColumn: 'span 4' }}>
                <DataCard title="Leave hours already taken" value={<CountUp value={usedHours} decimals={1} />} unit="hours"
                    icon={<Clock size={15} />} color={tokens.color?.warning}
                    subtitle={`Entitlement on record is ${entitlement} hours`} />
            </div>
            <div style={{ gridColumn: 'span 4' }}>
                <DataCard title="Requests submitted" value={<CountUp value={history.length} />} unit="requests"
                    icon={<CalendarPlus size={15} />} color={tokens.color?.['accent-primary']} />
            </div>

            <div style={{ ...ui.panel, gridColumn: 'span 5' }}>
                <h3 style={ui.h3}>Request leave</h3>
                <p style={ui.hint}>Hours default to eight per calendar day in the range. Adjust them if you are taking part of a day.</p>
                {balanceLoading && <Loading label="Loading your balance" />}
                <ErrorNote error={balanceError} context="your leave balance" />

                <form onSubmit={handleSubmit} style={{ marginTop: tokens.spacing?.md }}>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: tokens.spacing?.sm }}>
                        <div style={ui.field}>
                            <label style={ui.label} htmlFor="leave-start">First day off</label>
                            <input id="leave-start" type="date" style={ui.input} value={form.start_date}
                                onChange={(e) => setForm((p) => ({ ...p, start_date: e.target.value }))} />
                        </div>
                        <div style={ui.field}>
                            <label style={ui.label} htmlFor="leave-end">Last day off</label>
                            <input id="leave-end" type="date" style={ui.input} value={form.end_date} min={form.start_date || undefined}
                                onChange={(e) => setForm((p) => ({ ...p, end_date: e.target.value }))} />
                        </div>
                    </div>
                    <div style={ui.field}>
                        <label style={ui.label} htmlFor="leave-hours">Hours to deduct</label>
                        <input id="leave-hours" type="number" min="1" step="0.5" style={ui.input}
                            placeholder={suggestedHours ? `${suggestedHours} suggested for this range` : 'Pick your dates first'}
                            value={form.hours}
                            onChange={(e) => setForm((p) => ({ ...p, hours: e.target.value }))} />
                    </div>

                    {!datesValid && form.start_date && form.end_date && (
                        <p style={{ ...ui.hint, color: tokens.color?.danger }}>The last day off must be on or after the first day off.</p>
                    )}
                    {overBalance && (
                        <p style={{ ...ui.hint, color: tokens.color?.warning }}>
                            This is more than the {balanceHours} hours you have left. You can still send it, and your manager will decide.
                        </p>
                    )}

                    <Btn type="submit" tone="success" icon={Send} loading={isSubmitting} disabled={!valid}>
                        Send request to my manager
                    </Btn>
                </form>
            </div>

            <div style={{ ...ui.panel, gridColumn: 'span 7' }}>
                <h3 style={ui.h3}>Your leave requests</h3>
                {historyLoading && <Loading label="Loading your leave history" />}
                <ErrorNote error={historyError} context="your leave history" />
                {!historyLoading && !historyError && history.length === 0 && (
                    <EmptyState icon={Calendar} title="No leave requested yet"
                        action="Use the form on the left to send your first request. Approved and rejected requests both stay listed here." />
                )}
                {history.length > 0 && (
                    <div className="emp-scroll" style={{ ...ui.scroller('300px'), marginTop: tokens.spacing?.sm }}>
                        {history.map((r) => (
                            <div key={r.request_id} style={ui.listRow}>
                                <div style={ui.rowMain}>
                                    <span style={ui.rowTitle}>{fmtDate(r.start_date)} to {fmtDate(r.end_date)}</span>
                                    <span style={ui.rowMeta}>{Number(r.hours) || 0} hours, requested {fmtDate(r.submitted_at)}</span>
                                </div>
                                <StatusPill status={r.status} />
                            </div>
                        ))}
                    </div>
                )}
            </div>

            <div style={{ gridColumn: 'span 12' }}>
                <DataCard title="How your requests were decided" isChart minHeight="300px">
                    <PieChartWidget data={byStatus} minHeight="260px" label="Every leave request you have ever submitted, grouped by outcome." />
                </DataCard>
            </div>
        </div>
    );
});
LeaveModule.displayName = 'LeaveModule';

/* -------------------------------------------------------------------------- */
/* Privacy, consent, retention preference and feedback                         */
/* -------------------------------------------------------------------------- */
const PIISecurityModule = memo(() => {
    const { toast } = useToast();
    const { data: personalInfo, isLoading: infoLoading, error: infoError } = useApi(getPersonalInfo, [], true);
    const { data: retention, isLoading: retentionLoading, refetch: refetchRetention } = useApi(getRetentionPreference, [], true);

    const [unmasked, setUnmasked] = useState(null);
    const [isRevealing, setIsRevealing] = useState(false);
    // Clearing the auto-hide timer on unmount avoids a setState on a dead component.
    const hideTimerRef = useRef(null);
    useEffect(() => () => clearTimeout(hideTimerRef.current), []);
    const [consentBusy, setConsentBusy] = useState(null);
    const [preference, setPreference] = useState('');
    const [isSavingPref, setIsSavingPref] = useState(false);
    const [feedback, setFeedback] = useState('');
    const [isSendingFeedback, setIsSendingFeedback] = useState(false);

    const savedPreference = retention?.preference || '';
    const effectivePreference = preference || savedPreference;

    const fields = useMemo(() => ([
        { key: 'full_name', label: 'Full name' },
        { key: 'email', label: 'Work email' },
        { key: 'username', label: 'Sign in name' },
        { key: 'role', label: 'Role on record', format: readableRole },
        { key: 'employee_uuid', label: 'Employee record id' },
    ]), []);

    const handleReveal = useCallback(async () => {
        if (unmasked) { setUnmasked(null); return; }
        setIsRevealing(true);
        try {
            const res = await revealOwnPII();
            setUnmasked(res.data?.fields || {});
            toast({ title: 'Sensitive fields revealed', description: 'They will hide again in thirty seconds. This reveal is written to the audit log.', variant: 'warning' });
            // Tracked so it can be cleared if the module unmounts first.
            hideTimerRef.current = setTimeout(() => setUnmasked(null), 30000);
        } catch (err) {
            toast({ title: 'Could not reveal your details', description: err.response?.data?.detail || err.message, variant: 'destructive' });
        } finally {
            setIsRevealing(false);
        }
    }, [unmasked, toast]);

    const handleConsent = useCallback(async (granted) => {
        setConsentBusy(granted ? 'grant' : 'revoke');
        try {
            await recordConsentChange({ purpose_id: 'marketing', consent_granted: granted, reason: 'Employee preference update' });
            toast({
                title: granted ? 'Marketing consent granted' : 'Marketing consent revoked',
                description: granted ? 'HiRo may contact you about internal programmes.' : 'You will no longer be contacted about internal programmes.',
                variant: 'success',
            });
        } catch (err) {
            toast({ title: 'Could not update your consent', description: err.response?.data?.detail || err.message, variant: 'destructive' });
        } finally {
            setConsentBusy(null);
        }
    }, [toast]);

    const handleSavePreference = useCallback(async () => {
        const value = effectivePreference.trim();
        if (!value) {
            toast({ title: 'Nothing to save', description: 'Tell us what would keep you here before saving.', variant: 'destructive' });
            return;
        }
        setIsSavingPref(true);
        try {
            await saveRetentionPreference(value);
            toast({ title: 'Preference saved', description: 'Your retention preference is on record for HR.', variant: 'success' });
            setPreference('');
            refetchRetention();
        } catch (err) {
            toast({ title: 'Could not save your preference', description: err.response?.data?.detail || err.message, variant: 'destructive' });
        } finally {
            setIsSavingPref(false);
        }
    }, [effectivePreference, toast, refetchRetention]);

    const handleFeedback = useCallback(async (e) => {
        e.preventDefault();
        const text = feedback.trim();
        if (text.length < 5) {
            toast({ title: 'Add a little more', description: 'Write at least a short sentence so your feedback is useful.', variant: 'destructive' });
            return;
        }
        setIsSendingFeedback(true);
        try {
            const res = await submitFeedback(text);
            toast({ title: 'Feedback sent', description: `Recorded as ${res.data?.feedback_id || 'a new entry'} for the HR team.`, variant: 'success' });
            setFeedback('');
        } catch (err) {
            toast({ title: 'Could not send your feedback', description: err.response?.data?.detail || err.message, variant: 'destructive' });
        } finally {
            setIsSendingFeedback(false);
        }
    }, [feedback, toast]);

    return (
        <div style={ui.grid} className="portal-grid">
            <EmployeeStyles />

            <div style={{ ...ui.panel, gridColumn: 'span 6' }}>
                <h3 style={ui.h3}>What we hold about you</h3>
                <p style={ui.hint}>These are the fields on your personnel record. Revealing the protected ones is logged.</p>
                {infoLoading && <Loading label="Loading your record" />}
                <ErrorNote error={infoError} context="your personal record" />

                {personalInfo && (
                    <div style={{ marginTop: tokens.spacing?.sm }}>
                        {fields.map((f) => (
                            <div key={f.key} style={ui.listRow}>
                                <span style={{ ...ui.rowMeta, color: tokens.color?.['muted-500'] }}>{f.label}</span>
                                <span style={{ color: tokens.color?.['text-100'], fontSize: tokens.typography?.base?.fontSize }}>
                                    {f.format ? f.format(personalInfo[f.key]) : (personalInfo[f.key] || 'Not recorded')}
                                </span>
                            </div>
                        ))}
                        {unmasked && Object.entries(unmasked).map(([k, v]) => (
                            <div key={k} style={ui.listRow}>
                                <span style={{ ...ui.rowMeta, color: tokens.color?.warning }}>{k.replace(/_/g, ' ')}</span>
                                <span style={{ color: tokens.color?.warning, fontSize: tokens.typography?.base?.fontSize }}>
                                    {typeof v === 'object' ? JSON.stringify(v) : String(v)}
                                </span>
                            </div>
                        ))}
                    </div>
                )}

                <div style={{ display: 'flex', gap: tokens.spacing?.xs, marginTop: tokens.spacing?.md, flexWrap: 'wrap' }}>
                    <Btn tone="ghost" icon={unmasked ? EyeOff : Eye} loading={isRevealing} disabled={!!infoError} onClick={handleReveal}>
                        {unmasked ? 'Hide protected fields' : 'Reveal protected fields for thirty seconds'}
                    </Btn>
                </div>
            </div>

            <div style={{ ...ui.panel, gridColumn: 'span 6' }}>
                <h3 style={ui.h3}>Consent</h3>
                <p style={ui.hint}>Controls whether HiRo may contact you about internal programmes. Every change is written to the consent ledger.</p>
                <div style={{ display: 'flex', gap: tokens.spacing?.xs, marginTop: tokens.spacing?.md, flexWrap: 'wrap' }}>
                    <Btn tone="success" icon={CheckCircle} loading={consentBusy === 'grant'} disabled={!!consentBusy} onClick={() => handleConsent(true)}>
                        Grant marketing consent
                    </Btn>
                    <Btn tone="danger" icon={XCircle} loading={consentBusy === 'revoke'} disabled={!!consentBusy} onClick={() => handleConsent(false)}>
                        Revoke marketing consent
                    </Btn>
                </div>

                <h3 style={{ ...ui.h3, marginTop: tokens.spacing?.xl }}>What would keep you here</h3>
                <p style={ui.hint}>
                    {retentionLoading ? 'Loading your saved preference.'
                        : savedPreference ? `Currently on record: ${savedPreference}`
                            : 'Nothing on record yet. What you write here goes to HR retention planning.'}
                </p>
                <div style={{ display: 'flex', gap: tokens.spacing?.xs, marginTop: tokens.spacing?.sm, flexWrap: 'wrap' }}>
                    <input style={{ ...ui.input, flex: '1 1 200px' }} placeholder="For example more remote days, or a mentoring track"
                        value={preference} onChange={(e) => setPreference(e.target.value)} />
                    <Btn icon={Award} loading={isSavingPref} disabled={!preference.trim()} onClick={handleSavePreference}>Save</Btn>
                </div>
            </div>

            <div style={{ ...ui.panel, gridColumn: 'span 12' }}>
                <h3 style={ui.h3}>Send feedback to HR</h3>
                <p style={ui.hint}>Goes straight to the HR feedback log with your employee record attached.</p>
                <form onSubmit={handleFeedback} style={{ marginTop: tokens.spacing?.sm }}>
                    <textarea style={{ ...ui.input, minHeight: 90, resize: 'vertical' }}
                        placeholder="Tell HR what is working and what is not"
                        value={feedback} onChange={(e) => setFeedback(e.target.value)} />
                    <div style={{ marginTop: tokens.spacing?.sm }}>
                        <Btn type="submit" icon={MessageSquare} loading={isSendingFeedback} disabled={feedback.trim().length < 5}>
                            Send feedback
                        </Btn>
                    </div>
                </form>
            </div>
        </div>
    );
});
PIISecurityModule.displayName = 'PIISecurityModule';

/* -------------------------------------------------------------------------- */
/* Shell                                                                       */
/* -------------------------------------------------------------------------- */
export const EmployeePortalComponent = memo(() => {
    const location = useLocation();
    const requested = new URLSearchParams(location.search).get('module') || 'dashboard';
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
        tabs: {
            display: 'flex', gap: 6, overflowX: 'auto', overflowY: 'hidden',
            paddingBottom: 4, marginTop: tokens.spacing?.md, maxWidth: '100%',
        },
        tab: (isActive) => ({
            display: 'inline-flex', alignItems: 'center', gap: 7, flexShrink: 0,
            padding: '7px 13px', borderRadius: tokens.border?.radius?.full,
            border: `1px solid ${isActive ? `${tokens.color?.['accent-primary']}55` : tokens.color?.['border-600']}`,
            background: isActive ? `${tokens.color?.['accent-primary']}18` : 'transparent',
            color: isActive ? tokens.color?.['text-100'] : tokens.color?.['muted-500'],
            fontSize: tokens.typography?.button?.fontSize, fontWeight: 500,
            textDecoration: 'none', whiteSpace: 'nowrap', transition: tokens.ui?.transition?.micro,
        }),
        chat: { position: 'fixed', bottom: tokens.spacing?.lg, right: tokens.spacing?.lg, zIndex: 1000 },
    }), []);

    const body = () => {
        switch (requested) {
            case 'dashboard': return <EmployeeDashboardModule />;
            case 'onboarding': return <OnboardingPlanModule />;
            case 'timesheets': return <TimesheetSubmission />;
            case 'leave': return <LeaveModule />;
            case 'pay': return <PayModule />;
            case 'goals': return <GoalsModule />;
            case 'ask': return <AskHiRoModule />;
            case 'growth': return <GrowthModule />;
            case 'documents': return <DocumentsModule />;
            case 'expenses': return <ExpenseModule />;
            case 'pii': return <PIISecurityModule />;
            case 'offboarding': return <OffboardingModule />;
            default:
                return (
                    <EmptyState icon={AlertTriangle} title={`There is no employee section called "${requested}"`}
                        action="Pick one of the sections above to carry on." />
                );
        }
    };

    const Icon = active?.icon || User;

    return (
        <div style={styles.container} className="portal-container">
            <div style={styles.header}>
                <h1 style={styles.title}>
                    <Icon size={26} color={tokens.color?.['accent-secondary']} />
                    {active?.title || 'Employee portal'}
                </h1>
                <p style={styles.subtitle}>Everything shown here is read live from your own employee record.</p>

                <nav style={styles.tabs} className="emp-scroll" aria-label="Employee portal sections">
                    {MODULES.map((m) => {
                        const TabIcon = m.icon;
                        return (
                            <Link key={m.key} to={`/employee-portal?module=${m.key}`} style={styles.tab(m.key === requested)}>
                                <TabIcon size={14} /> {m.label}
                            </Link>
                        );
                    })}
                </nav>
            </div>

            {body()}

            <div style={styles.chat}>
                <DigitalTwinChat isWidget={true} />
            </div>
        </div>
    );
});

EmployeePortalComponent.displayName = 'EmployeePortalComponent';
export default EmployeePortalComponent;
