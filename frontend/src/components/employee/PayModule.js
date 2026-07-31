// Employee portal: Pay module (payslips + benefits).
// Real data only: GET /api/hr/payslips, GET /api/hr/payslips/download/{period}, GET /api/hr/benefits.
import React, { memo, useCallback, useMemo, useState } from 'react';
import { theme as tokens } from '../../theme';
import { useApi } from '../../hooks/useApi';
import { useToast } from '../../hooks/use-toast';
import { getEmployeePayslips, downloadPayslip, getEmployeeBenefits } from '../../config/api';
import DataCard from '../DataCard';
import AreaChartWidget from '../charts/AreaChartWidget';
import { CountUp, LiveMeter } from '../live/LivePrimitives';
import { ui, Btn, Loading, EmptyState, ErrorNote, fmtDate, money, readablePolicy, EmployeeStyles } from './shared';
import { Download, Receipt, HeartPulse, PiggyBank, CalendarClock, Wallet } from 'lucide-react';

const PayModule = memo(() => {
    const { toast } = useToast();
    const { data: rawSlips, isLoading: slipsLoading, error: slipsError } = useApi(getEmployeePayslips, [], true);
    const { data: benefits, isLoading: benefitsLoading, error: benefitsError } = useApi(getEmployeeBenefits, [], true);
    const [downloading, setDownloading] = useState(null);

    const slips = useMemo(() => (Array.isArray(rawSlips) ? rawSlips : []), [rawSlips]);

    const latestGross = Number(slips[0]?.gross) || 0;
    const annualised = latestGross * 12;

    const trend = useMemo(
        () => slips.slice().reverse().map((s) => ({ name: fmtDate(s.period), value: Math.round(Number(s.gross) || 0) })),
        [slips]
    );

    const handleDownload = useCallback(async (period) => {
        setDownloading(period);
        try {
            const res = await downloadPayslip(period);
            const url = URL.createObjectURL(new Blob([res.data]));
            const a = document.createElement('a');
            a.href = url;
            a.download = `payslip-${period}.txt`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            URL.revokeObjectURL(url);
            toast({ title: 'Payslip downloaded', description: `Saved your payslip for ${fmtDate(period)}.`, variant: 'success' });
        } catch (err) {
            toast({ title: 'Download failed', description: err.response?.data?.detail || err.message, variant: 'destructive' });
        } finally {
            setDownloading(null);
        }
    }, [toast]);

    return (
        <div style={ui.grid}>
            <EmployeeStyles />

            <div style={{ gridColumn: 'span 4' }}>
                <DataCard title="Latest monthly gross" value={<CountUp value={latestGross} prefix="$" />} unit=""
                    icon={<Wallet size={15} />} color={tokens.color?.['accent-primary']}
                    subtitle={slips[0]?.period ? `Period ${fmtDate(slips[0].period)}` : 'No pay record yet'} />
            </div>
            <div style={{ gridColumn: 'span 4' }}>
                <DataCard title="Annualised on current rate" value={<CountUp value={annualised} prefix="$" />} unit=""
                    icon={<PiggyBank size={15} />} color={tokens.color?.success}
                    subtitle="Twelve times your latest monthly gross" />
            </div>
            <div style={{ gridColumn: 'span 4' }}>
                <DataCard title="Pay records on file" value={<CountUp value={slips.length} />} unit="periods"
                    icon={<Receipt size={15} />} color={tokens.color?.['accent-secondary']} />
            </div>

            {/* Payslip list */}
            <div style={{ ...ui.panel, gridColumn: 'span 7' }}>
                <h3 style={ui.h3}>Your payslips</h3>
                <p style={ui.hint}>Each entry is generated from your compensation history. Download saves a copy to your machine.</p>
                {slipsLoading && <Loading label="Loading your payslips" />}
                <ErrorNote error={slipsError} context="your payslips" />
                {!slipsLoading && !slipsError && slips.length === 0 && (
                    <EmptyState icon={Receipt} title="No payslips available yet"
                        action="Payslips appear once a compensation record exists for you. Raise a case with HR if you expected one here." />
                )}
                {slips.length > 0 && (
                    <div className="emp-scroll" style={{ ...ui.scroller('300px'), marginTop: tokens.spacing?.sm }}>
                        {slips.map((s) => (
                            <div key={s.period} style={ui.listRow}>
                                <div style={ui.rowMain}>
                                    <span style={ui.rowTitle}>Period {fmtDate(s.period)}</span>
                                    <span style={ui.rowMeta}>Gross {money(s.gross)} for the month</span>
                                </div>
                                <Btn tone="ghost" icon={Download} loading={downloading === s.period}
                                    disabled={!!downloading} onClick={() => handleDownload(s.period)}>
                                    Download
                                </Btn>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* Benefits */}
            <div style={{ ...ui.panel, gridColumn: 'span 5' }}>
                <h3 style={ui.h3}>Your benefits</h3>
                {benefitsLoading && <Loading label="Loading your benefits" />}
                <ErrorNote error={benefitsError} context="your benefits" />
                {benefits && (
                    <div style={{ marginTop: tokens.spacing?.sm }}>
                        <div style={ui.listRow}>
                            <div style={ui.rowMain}>
                                <span style={ui.rowTitle}>Health cover</span>
                                <span style={ui.rowMeta}>{benefits.health_plan || 'Not recorded'}</span>
                            </div>
                            <HeartPulse size={15} color={tokens.color?.danger} />
                        </div>
                        <div style={ui.listRow}>
                            <div style={ui.rowMain}>
                                <span style={ui.rowTitle}>Retirement match</span>
                                <span style={ui.rowMeta}>Your employer matches contributions up to this share of salary</span>
                            </div>
                            <span style={{ flexShrink: 0, color: tokens.color?.success, fontWeight: 600 }}>
                                {/* A null match is "not recorded", not 0%. Rendering 0
                                    told the employee their employer matches nothing. */}
                                {benefits.retirement_match_pct == null
                                    ? <span style={{ color: tokens.color?.['muted-500'], fontWeight: 500 }}>Not recorded</span>
                                    : <CountUp value={Number(benefits.retirement_match_pct)} suffix="%" />}
                            </span>
                        </div>
                        <div style={ui.listRow}>
                            <div style={ui.rowMain}>
                                <span style={ui.rowTitle}>Annual leave entitlement</span>
                                <span style={ui.rowMeta}>Under the {readablePolicy(benefits.leave_policy)} leave policy</span>
                            </div>
                            <span style={{ flexShrink: 0, color: tokens.color?.['accent-primary'], fontWeight: 600 }}>
                                <CountUp value={Number(benefits.annual_leave_hours) || 0} suffix=" h" />
                            </span>
                        </div>
                        <div style={{ marginTop: tokens.spacing?.md }}>
                            <LiveMeter pct={((Number(benefits.annual_leave_hours) || 0) / 240) * 100}
                                color={tokens.color?.['accent-secondary']}
                                label="Entitlement against a 240 hour reference year" />
                        </div>
                        <p style={ui.hint}>
                            <CalendarClock size={12} style={{ verticalAlign: '-2px', marginRight: 4 }} />
                            Benefits are derived from your leave policy and compensation band. To change them, raise a case with HR.
                        </p>
                    </div>
                )}
            </div>

            <div style={{ gridColumn: 'span 12' }}>
                <DataCard title="Monthly gross over your pay history" isChart minHeight="300px">
                    <AreaChartWidget data={trend} minHeight="260px" color={tokens.color?.success}
                        label="Each point is one compensation period on record, oldest first." />
                </DataCard>
            </div>
        </div>
    );
});

PayModule.displayName = 'PayModule';
export default PayModule;
