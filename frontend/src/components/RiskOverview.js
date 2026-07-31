// Organisation-wide workforce risk, read live from workforce planning and the
// analytics warehouse. Nothing on this panel is hardcoded: if a figure is absent
// from the backend the card says so rather than inventing one.
// /compliance/dashboard is deliberately not called here, it is restricted to HR
// business partners and HR IT and returns 403 for a manager.
import React, { useMemo, memo } from 'react';
import { theme as tokens } from '../theme';
import { useApi } from '../hooks/useApi';
import { getWFPProjections, getAnalyticsCharts } from '../config/api';
import DataCard from './DataCard';
import BarChartWidget from './charts/BarChartWidget';
import { CountUp, LiveMeter } from './live/LivePrimitives';
import { ui, Loading, EmptyState, ErrorNote, humanText } from './employee/shared';
import { Users, Star, Clock, Gauge, ShieldAlert, TrendingUp } from 'lucide-react';

// Turns a 0..1 model score into language a person can act on.
const riskBand = (score) => {
    if (score >= 0.7) return { label: 'High', color: tokens.color?.danger, note: 'A large share of the workforce looks likely to leave. Treat retention as urgent.' };
    if (score >= 0.4) return { label: 'Moderate', color: tokens.color?.warning, note: 'Retention pressure is building. Worth a look at pay and workload in the weakest departments.' };
    return { label: 'Low', color: tokens.color?.success, note: 'The workforce looks stable on the factors the model tracks.' };
};

const topN = (series, n) => (Array.isArray(series) ? [...series].sort((a, b) => (b.value || 0) - (a.value || 0)).slice(0, n) : []);

const RiskOverview = memo(() => {
    const { data: wfp, isLoading: wfpLoading, error: wfpError } = useApi(getWFPProjections, [], true);
    const { data: charts, isLoading: chartsLoading, error: chartsError } = useApi(getAnalyticsCharts, [], true);

    const state = wfp?.current_state || {};
    const riskScore = Number(state.overall_risk_score);
    const hasRisk = Number.isFinite(riskScore);
    const band = riskBand(hasRisk ? riskScore : 0);

    // Departments the planner flags as short on the skills they need.
    const skillGaps = useMemo(() => (
        Object.entries(wfp?.skill_gaps || {})
            .filter(([, level]) => String(level).toUpperCase() === 'HIGH')
            .map(([dept]) => dept)
            .sort()
    ), [wfp]);

    const attrition = useMemo(() => topN(charts?.attrition_by_department, 10), [charts]);
    const headcount = useMemo(() => topN(charts?.headcount_by_department, 10), [charts]);

    const styles = useMemo(() => ({
        grid: { ...ui.grid },
        stat: { gridColumn: 'span 3', minWidth: 0 },
        wide: { gridColumn: 'span 12', minWidth: 0 },
        half: { gridColumn: 'span 6', minWidth: 0 },
        chip: {
            display: 'inline-block', padding: '4px 10px', margin: '0 6px 6px 0',
            borderRadius: tokens.border?.radius?.full, fontSize: '11.5px',
            color: tokens.color?.warning, background: `${tokens.color?.warning}14`,
            border: `1px solid ${tokens.color?.warning}44`,
        },
    }), []);

    if (wfpLoading && !wfp) {
        return <Loading label="Reading workforce risk from the planning engine" />;
    }

    return (
        <div style={styles.grid}>
            <div style={styles.stat}>
                <DataCard
                    title="People in the workforce"
                    value={<CountUp value={Number(state.total_employees) || 0} />}
                    icon={<Users size={15} />}
                    subtitle="Everyone currently on the books"
                />
            </div>
            <div style={styles.stat}>
                <DataCard
                    title="People in leadership roles"
                    value={<CountUp value={Number(state.critical_roles) || 0} />}
                    icon={<Star size={15} />}
                    color={tokens.color?.warning}
                    subtitle="Managers and HR roles across the workforce"
                />
            </div>
            <div style={styles.stat}>
                <DataCard
                    title="Average time in post"
                    value={<CountUp value={Number(state.average_tenure_months) || 0} />}
                    unit="months"
                    icon={<Clock size={15} />}
                    subtitle="How long the average person has been here"
                />
            </div>
            <div style={styles.stat}>
                <DataCard
                    title="Average performance rating"
                    value={<CountUp value={Number(state.average_performance_score) || 0} decimals={2} />}
                    unit="out of 5"
                    icon={<Gauge size={15} />}
                    subtitle="Across every recorded review"
                />
            </div>

            <div style={styles.wide}>
                <DataCard title="Overall attrition risk" icon={<ShieldAlert size={15} />} color={band.color}>
                    <ErrorNote error={wfpError} context="the workforce risk score" />
                    {hasRisk ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                            <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
                                <span style={{ fontSize: 30, fontWeight: 640, letterSpacing: '-0.02em', color: band.color, fontVariantNumeric: 'tabular-nums' }}>
                                    <CountUp value={riskScore * 100} decimals={1} suffix="%" />
                                </span>
                                <span style={{ fontSize: 13, fontWeight: 550, color: band.color }}>{band.label} risk</span>
                            </div>
                            <LiveMeter pct={riskScore * 100} color={band.color} height={7} />
                            <p style={{ ...ui.hint, margin: 0 }}>{band.note}</p>
                        </div>
                    ) : (
                        !wfpError && <EmptyState
                            icon={ShieldAlert}
                            title="The planning engine has not scored the workforce yet"
                            action="The score appears once enough performance and tenure records have been ingested."
                        />
                    )}
                </DataCard>
            </div>

            <div style={styles.half}>
                <DataCard title="Attrition risk by department" isChart minHeight="320px" icon={<TrendingUp size={15} />}>
                    <ErrorNote error={chartsError} context="department risk" />
                    {!chartsError && (
                        <BarChartWidget
                            data={attrition}
                            minHeight="250px"
                            color={tokens.color?.danger}
                            label={attrition.length ? 'Ten departments carrying the most flight risk, as a percentage' : undefined}
                        />
                    )}
                </DataCard>
            </div>

            <div style={styles.half}>
                <DataCard title="Where the people are" isChart minHeight="320px" icon={<Users size={15} />}>
                    <ErrorNote error={chartsError} context="department headcount" />
                    {!chartsError && (
                        <BarChartWidget
                            data={headcount}
                            minHeight="250px"
                            color={tokens.color?.['accent-primary']}
                            label={headcount.length ? 'Ten largest departments by headcount' : undefined}
                        />
                    )}
                </DataCard>
            </div>

            <div style={styles.wide}>
                <DataCard title="Departments short on the skills they need" icon={<ShieldAlert size={15} />} color={tokens.color?.warning}>
                    {chartsLoading && !charts && <Loading label="Reading skill coverage" />}
                    {skillGaps.length > 0 ? (
                        <>
                            <p style={{ ...ui.hint, marginTop: 0 }}>
                                The planning engine rates the skill gap in these areas as high. They are the first places
                                a departure will hurt.
                            </p>
                            <div>
                                {skillGaps.map((d) => <span key={d} style={styles.chip}>{humanText(d)}</span>)}
                            </div>
                        </>
                    ) : (
                        !wfpLoading && <EmptyState
                            icon={Gauge}
                            title="No department is flagged as short on skills"
                            action="Skill coverage is adequate everywhere the planning engine can see."
                        />
                    )}
                </DataCard>
            </div>
        </div>
    );
});

RiskOverview.displayName = 'RiskOverview';
export default RiskOverview;
