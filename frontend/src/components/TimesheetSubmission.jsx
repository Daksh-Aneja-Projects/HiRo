// Employee portal: Timesheets module.
// Real data only: GET /api/hr/timesheets, POST /api/hr/timesheets/pre-check,
// POST /api/hr/timesheets. Nothing is fabricated when the history is empty.
import React, { useState, useCallback, useMemo, memo } from 'react';
import { theme as tokens } from '../theme';
import { useApi } from '../hooks/useApi';
import { useToast } from '../hooks/use-toast';
import { getTimesheets, runTimesheetPreCheck, submitTimesheet } from '../config/api';
import DataCard from './DataCard';
import BarChartWidget from './charts/BarChartWidget';
import { CountUp, LiveMeter } from './live/LivePrimitives';
import { ui, Btn, Loading, EmptyState, ErrorNote, StatusPill, fmtDate, EmployeeStyles } from './employee/shared';
import { Clock, Send, ShieldCheck, CheckCircle, AlertTriangle, CalendarDays, Timer } from 'lucide-react';

const STANDARD_WEEK_HOURS = 40;

// Sunday of the current week, as the natural default for "week ending".
const defaultWeekEnding = () => {
    const d = new Date();
    d.setDate(d.getDate() + (7 - d.getDay()) % 7);
    return d.toISOString().slice(0, 10);
};

const TimesheetSubmission = memo(() => {
    const { toast } = useToast();
    const { data: rawSheets, isLoading, error, refetch } = useApi(getTimesheets, [], true);

    const [hours, setHours] = useState('');
    const [weekEnding, setWeekEnding] = useState(defaultWeekEnding);
    const [check, setCheck] = useState(null);      // null | { status, messages, reason }
    const [isChecking, setIsChecking] = useState(false);
    const [isSubmitting, setIsSubmitting] = useState(false);

    const sheets = useMemo(() => (Array.isArray(rawSheets) ? rawSheets : []), [rawSheets]);

    const stats = useMemo(() => {
        const total = sheets.reduce((sum, s) => sum + (Number(s.hours) || 0), 0);
        const latest = sheets[0];
        return {
            count: sheets.length,
            total,
            average: sheets.length ? total / sheets.length : 0,
            latestHours: Number(latest?.hours) || 0,
            latestWeek: latest?.week,
        };
    }, [sheets]);

    // Oldest to newest so the chart reads left to right in time order.
    const chartData = useMemo(
        () => sheets.slice().reverse().map((s) => ({ name: fmtDate(s.week), value: Number(s.hours) || 0 })),
        [sheets]
    );

    const hoursNum = Number(hours);
    const formValid = weekEnding !== '' && hours !== '' && Number.isFinite(hoursNum) && hoursNum > 0 && hoursNum <= 168;

    const handlePreCheck = useCallback(async () => {
        if (!formValid) {
            toast({ title: 'Check the form first', description: 'Enter a week ending date and total hours between 1 and 168.', variant: 'destructive' });
            return;
        }
        setIsChecking(true);
        try {
            const res = await runTimesheetPreCheck({ hours: hoursNum });
            setCheck(res.data);
            const passed = res.data?.status === 'PASS';
            toast({
                title: passed ? 'Policy check passed' : 'Policy check flagged this week',
                description: (res.data?.messages || [])[0] || res.data?.reason || 'Policy engine responded.',
                variant: passed ? 'success' : 'warning',
            });
        } catch (err) {
            setCheck(null);
            toast({ title: 'Policy check failed', description: err.response?.data?.detail || err.message, variant: 'destructive' });
        } finally {
            setIsChecking(false);
        }
    }, [formValid, hoursNum, toast]);

    const handleSubmit = useCallback(async (e) => {
        e.preventDefault();
        if (!formValid) {
            toast({ title: 'Check the form first', description: 'Enter a week ending date and total hours between 1 and 168.', variant: 'destructive' });
            return;
        }
        setIsSubmitting(true);
        try {
            const res = await submitTimesheet({ total_hours: hoursNum, week_ending: weekEnding });
            toast({
                title: 'Timesheet submitted',
                description: res.data?.status === 'PENDING_AGENT_REVIEW'
                    ? 'Sent for review because the policy engine wants a second look at these hours.'
                    : `Recorded ${hoursNum} hours for the week ending ${fmtDate(weekEnding)}.`,
                variant: 'success',
            });
            setHours('');
            setCheck(null);
            refetch();
        } catch (err) {
            toast({ title: 'Submission failed', description: err.response?.data?.detail || err.message, variant: 'destructive' });
        } finally {
            setIsSubmitting(false);
        }
    }, [formValid, hoursNum, weekEnding, toast, refetch]);

    const checkPassed = check?.status === 'PASS';

    return (
        <div style={ui.grid}>
            <EmployeeStyles />

            {/* KPI row, live count-ups over the real history */}
            <div style={{ gridColumn: 'span 3' }}>
                <DataCard title="Weeks submitted" value={<CountUp value={stats.count} />} unit="weeks"
                    icon={<CalendarDays size={15} />} color={tokens.color?.['accent-primary']}
                    subtitle={stats.latestWeek ? `Latest week ending ${fmtDate(stats.latestWeek)}` : 'Nothing submitted yet'} />
            </div>
            <div style={{ gridColumn: 'span 3' }}>
                <DataCard title="Total hours logged" value={<CountUp value={stats.total} decimals={1} />} unit="hours"
                    icon={<Clock size={15} />} color={tokens.color?.success} />
            </div>
            <div style={{ gridColumn: 'span 3' }}>
                <DataCard title="Average per week" value={<CountUp value={stats.average} decimals={1} />} unit="hours"
                    icon={<Timer size={15} />} color={tokens.color?.['accent-secondary']} />
            </div>
            <div style={{ gridColumn: 'span 3' }}>
                <DataCard title="Latest week against the 40 hour standard" value={<CountUp value={stats.latestHours} decimals={1} />} unit="hours"
                    icon={<ShieldCheck size={15} />} color={tokens.color?.warning}
                    footer={<LiveMeter pct={(stats.latestHours / STANDARD_WEEK_HOURS) * 100}
                        color={stats.latestHours > STANDARD_WEEK_HOURS ? tokens.color?.danger : tokens.color?.success}
                        label="Of a standard week" />} />
            </div>

            {/* Submission form */}
            <div style={{ ...ui.panel, gridColumn: 'span 5' }}>
                <h3 style={ui.h3}>Submit a week</h3>
                <p style={ui.hint}>Run the policy pre-check first to see whether the hours breach the standard working week before anything is recorded.</p>

                <form onSubmit={handleSubmit} style={{ marginTop: tokens.spacing?.md }}>
                    <div style={ui.field}>
                        <label style={ui.label} htmlFor="ts-week">Week ending</label>
                        <input id="ts-week" type="date" style={ui.input} value={weekEnding}
                            onChange={(e) => { setWeekEnding(e.target.value); setCheck(null); }} />
                    </div>
                    <div style={ui.field}>
                        <label style={ui.label} htmlFor="ts-hours">Total hours worked</label>
                        <input id="ts-hours" type="number" min="1" max="168" step="0.5" placeholder="For example 38.5"
                            style={ui.input} value={hours}
                            onChange={(e) => { setHours(e.target.value); setCheck(null); }} />
                    </div>

                    <div style={{ display: 'flex', gap: tokens.spacing?.sm, flexWrap: 'wrap' }}>
                        <Btn type="button" tone="ghost" icon={ShieldCheck} loading={isChecking}
                            disabled={!formValid || isSubmitting} onClick={handlePreCheck}>
                            Run policy pre-check
                        </Btn>
                        <Btn type="submit" tone="success" icon={Send} loading={isSubmitting} disabled={!formValid || isChecking}>
                            Submit timesheet
                        </Btn>
                    </div>
                </form>

                {check && (
                    <div style={{
                        marginTop: tokens.spacing?.md, padding: '11px 13px',
                        borderRadius: tokens.border?.radius?.input,
                        border: `1px solid ${(checkPassed ? tokens.color?.success : tokens.color?.warning)}33`,
                        background: `${(checkPassed ? tokens.color?.success : tokens.color?.warning)}0f`,
                    }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 7, color: checkPassed ? tokens.color?.success : tokens.color?.warning, fontWeight: 550, fontSize: tokens.typography?.base?.fontSize }}>
                            {checkPassed ? <CheckCircle size={15} /> : <AlertTriangle size={15} />}
                            {checkPassed ? 'These hours comply with policy' : 'Policy would flag these hours'}
                        </div>
                        {(check.messages || []).map((m, i) => (
                            <p key={i} style={{ ...ui.hint, color: tokens.color?.['muted-500'] }}>{m}</p>
                        ))}
                        {!checkPassed && <p style={ui.hint}>You can still submit. It will be routed for review instead of being recorded straight away.</p>}
                    </div>
                )}
            </div>

            {/* History */}
            <div style={{ ...ui.panel, gridColumn: 'span 7' }}>
                <h3 style={ui.h3}>Your submitted weeks</h3>
                {isLoading && <Loading label="Loading your timesheet history" />}
                <ErrorNote error={error} context="your timesheets" />
                {!isLoading && !error && sheets.length === 0 && (
                    <EmptyState icon={CalendarDays} title="No timesheets submitted yet"
                        action="Fill in the form on the left to record your first week. Submitted weeks appear here with their approval status." />
                )}
                {sheets.length > 0 && (
                    <div className="emp-scroll" style={{ ...ui.scroller('300px'), marginTop: tokens.spacing?.sm }}>
                        {sheets.map((s) => (
                            <div key={s.id} style={ui.listRow}>
                                <div style={ui.rowMain}>
                                    <span style={ui.rowTitle}>Week ending {fmtDate(s.week)}</span>
                                    <span style={ui.rowMeta}>{Number(s.hours) || 0} hours, submitted {fmtDate(s.submitted_at)}</span>
                                </div>
                                <StatusPill status={s.status} />
                            </div>
                        ))}
                    </div>
                )}
            </div>

            <div style={{ gridColumn: 'span 12' }}>
                <DataCard title="Hours per week over your submitted history" isChart minHeight="300px">
                    <BarChartWidget data={chartData} minHeight="260px" color={tokens.color?.['accent-primary']}
                        label="Each bar is one submitted week. The standard working week is 40 hours." />
                </DataCard>
            </div>
        </div>
    );
});

TimesheetSubmission.displayName = 'TimesheetSubmission';
export default TimesheetSubmission;
