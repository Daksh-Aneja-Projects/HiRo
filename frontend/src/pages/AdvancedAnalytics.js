// /frontend/src/pages/AdvancedAnalytics.js - FINAL ALIASING FIX (Dropdown UI Fix)
// Advanced Analytics Portal - Restricted to HRBP/Admin/HRIT
import React, { useState, useMemo, useEffect, useCallback, memo } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { theme as tokens } from '../theme';
import { TrendingUp, BarChart3, ScatterChart, Zap, Loader2, Filter, Cpu, AlertTriangle, Scale, Send, Clock } from 'lucide-react';
// FIX: Using absolute path aliases
import { aggregateMetrics, getAdvancedAnalytics, getAnalyticsCharts, getAnalyticsDepartments } from '../config/api';
import { useToast } from '../hooks/use-toast';
import DataCard from '../components/DataCard';
import BarChartWidget from '../components/charts/BarChartWidget';
import { ScatterChart as RScatterChart, Scatter, XAxis as RXAxis, YAxis as RYAxis, ZAxis, CartesianGrid as RGrid, Tooltip as RTooltip, ResponsiveContainer as RContainer } from 'recharts';

// --- Static Style Definitions ---
const getStyles = (tokens) => ({
    // Gutter, width and centering come from the shared .portal-container class
    // so this page lines up with every other portal.
    portalContainer: {
        color: tokens.color?.['text-100'],
        fontFamily: tokens.typography?.fontFamily,
    },
    header: {
        marginBottom: tokens.spacing?.lg,
    },
    title: {
        fontSize: tokens.typography?.h1?.fontSize,
        lineHeight: tokens.typography?.h1?.lineHeight,
        fontWeight: tokens.typography?.h1?.fontWeight,
        color: tokens.color?.['text-100'],
        marginBottom: tokens.spacing?.xs,
        display: 'flex',
        alignItems: 'center',
        gap: tokens.spacing?.xs,
    },
    subtitle: {
        fontSize: tokens.typography?.base?.fontSize,
        color: tokens.color?.['muted-500'],
    },
    grid: {
        display: 'grid',
        gridTemplateColumns: 'repeat(12, 1fr)',
        gap: tokens.spacing?.lg,
        alignItems: 'stretch',
    },
    input: {
        width: '100%',
        padding: '10px 12px',
        background: 'rgba(255,255,255,0.02)',
        border: `1px solid rgba(255,255,255,0.04)`,
        borderRadius: tokens.border?.radius?.chip,
        color: tokens.color?.['text-100'],
        fontSize: tokens.typography?.base?.fontSize,
        outline: 'none',
        transition: 'all 180ms ease',
    },
    // NEW FIX: Separate style for select to force background/color
    select: {
        WebkitAppearance: 'none', // Remove default browser styling on Chrome/Safari
        MozAppearance: 'none', // Remove default browser styling on Firefox
        appearance: 'none', // Remove default browser styling
        padding: '10px 12px',
        background: tokens.color?.['panel-700'], // Dark background for the dropdown itself
        border: `1px solid ${tokens.color?.['border-600']}`,
        borderRadius: tokens.border?.radius?.chip,
        color: tokens.color?.['text-100'], // Light text color
        fontSize: tokens.typography?.base?.fontSize,
        outline: 'none',
        cursor: 'pointer',
        transition: 'all 180ms ease',
    },
    primaryBtn: {
        padding: '10px 14px',
        borderRadius: tokens.border?.radius?.button,
        background: `linear-gradient(180deg, rgba(${tokens.color?.['accent-1-rgb'] || '120,90,255'},0.18), rgba(${tokens.color?.['accent-2-rgb'] || '0,200,255'},0.06))`,
        border: `1px solid rgba(${tokens.color?.['accent-1-rgb'] || '120,90,255'},0.16)`,
        color: tokens.color?.['text-100'],
        fontWeight: tokens.typography?.h2?.fontWeight,
        cursor: 'pointer',
        transition: 'all 180ms ease',
        display: 'flex',
        alignItems: 'center',
        gap: tokens.spacing?.xs,
        justifyContent: 'center',
    },
    filterGroup: {
        display: 'flex',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: tokens.spacing?.sm,
        marginBottom: tokens.spacing?.md,
    }
});


// Empty-state wrapper so a chart never renders fake data before real data arrives.
const EmptyChart = memo(({ minHeight = '200px', label }) => (
    <div style={{ minHeight, display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: tokens.color?.['muted-500'], fontSize: tokens.typography?.small?.fontSize, gap: 8 }}>
        <Loader2 size={16} className="animate-spin" /> {label || 'Loading live data...'}
    </div>
));
EmptyChart.displayName = 'EmptyChart';

const ChartOrEmpty = memo(({ data, minHeight, color, label }) => (
    (data && data.length)
        ? <BarChartWidget data={data} minHeight={minHeight} color={color} label={label} />
        : <EmptyChart minHeight={minHeight} />
));
ChartOrEmpty.displayName = 'ChartOrEmpty';

// The least-squares fit through the points, and how much of the variation it
// actually explains. The card was titled "Regression" and drew none, so there
// was nothing on it to read a relationship from.
const fitLine = (points) => {
    const n = points.length;
    if (n < 3) return null;
    const sx = points.reduce((a, p) => a + p.tenure, 0);
    const sy = points.reduce((a, p) => a + p.rating, 0);
    const sxx = points.reduce((a, p) => a + p.tenure * p.tenure, 0);
    const syy = points.reduce((a, p) => a + p.rating * p.rating, 0);
    const sxy = points.reduce((a, p) => a + p.tenure * p.rating, 0);
    const denom = n * sxx - sx * sx;
    if (!denom) return null;
    const slope = (n * sxy - sx * sy) / denom;
    const intercept = (sy - slope * sx) / n;
    const spread = Math.sqrt(denom * (n * syy - sy * sy));
    const r = spread ? (n * sxy - sx * sy) / spread : 0;
    const xs = points.map((p) => p.tenure);
    const lo = Math.min(...xs);
    const hi = Math.max(...xs);
    return {
        r,
        points: [{ tenure: lo, rating: slope * lo + intercept },
                 { tenure: hi, rating: slope * hi + intercept }],
        // Say what the line is worth. A trend line drawn through a cloud with
        // no relationship in it invites a conclusion the data does not support.
        strength: Math.abs(r) < 0.15 ? 'no real relationship between the two'
            : Math.abs(r) < 0.35 ? 'a weak relationship'
            : Math.abs(r) < 0.6 ? 'a moderate relationship'
            : 'a strong relationship',
        direction: slope < 0 ? 'falls' : 'rises',
    };
};

// Real performance-vs-tenure scatter across the sampled workforce.
const PerfTenureScatter = memo(({ points }) => {
    if (!points || !points.length) return <EmptyChart minHeight="300px" />;
    const fit = fitLine(points);
    return (
        <div style={{ width: '100%', height: '100%', minHeight: '300px' }}>
            <RContainer width="100%" height="100%">
                <RScatterChart margin={{ top: 10, right: 20, bottom: 10, left: -10 }}>
                    <RGrid strokeDasharray="3 3" stroke={tokens.color?.['border-600'] || '#e5e5e5'} />
                    <RXAxis type="number" dataKey="tenure" name="Tenure (months)" unit="mo"
                        tick={{ fill: tokens.color?.['muted-500'] || '#888', fontSize: 12 }} axisLine={false} tickLine={false} />
                    <RYAxis type="number" dataKey="rating" name="Rating" domain={[0, 5]}
                        tick={{ fill: tokens.color?.['muted-500'] || '#888', fontSize: 12 }} axisLine={false} tickLine={false} />
                    <ZAxis range={[40, 40]} />
                    <RTooltip cursor={{ strokeDasharray: '3 3' }}
                        contentStyle={{ backgroundColor: tokens.color?.['panel-800'] || '#fff', borderRadius: '8px', border: `1px solid ${tokens.color?.['border-600'] || '#e5e5e5'}` }}
                        itemStyle={{ color: tokens.color?.['text-100'] || '#000' }} />
                    <Scatter name="Employees" data={points} fill={tokens.color?.['accent-primary'] || '#0071e3'} fillOpacity={0.6} />
                    {fit && (
                        <Scatter name="Trend" data={fit.points} line={{ stroke: tokens.color?.warning, strokeWidth: 2 }}
                                 shape={() => null} legendType="none" isAnimationActive={false} />
                    )}
                </RScatterChart>
            </RContainer>
            {fit && (
                <p style={{ margin: '6px 0 0', fontSize: 12, color: tokens.color?.['muted-600'] }}>
                    Across {points.length.toLocaleString()} people, rating {fit.direction} with length of
                    service: {fit.strength} (r = {fit.r.toFixed(2)}).
                </p>
            )}
        </div>
    );
});
PerfTenureScatter.displayName = 'PerfTenureScatter';

// --- Sub-Component: AnalyticsDashboard (Hoisted) ---
const AnalyticsDashboard = memo(() => {
    const { toast } = useToast();
    const [data, setData] = useState({ key_metric: 'N/A', retention: 'N/A' });
    const [charts, setCharts] = useState({ headcount_by_department: [], attrition_by_department: [], perf_vs_tenure: [] });
    const [filters, setFilters] = useState({ department: 'All' });
    const [departments, setDepartments] = useState([]);
    const [isLoading, setIsLoading] = useState(false);

    // CRITICAL FIX: Styles are derived once based on tokens
    const styles = useMemo(() => getStyles(tokens), []);

    // The real department list backing the filter.
    useEffect(() => {
        let alive = true;
        getAnalyticsDepartments()
            .then((r) => { if (alive) setDepartments(r.data?.departments || []); })
            .catch(() => { /* the filter simply stays at "All departments" */ });
        return () => { alive = false; };
    }, []);

    const fetchData = useCallback(async () => {
        setIsLoading(true);
        try {
            const response = await aggregateMetrics({ filters, department: filters.department });
            setData(response.data || { key_metric: 'N/A', retention: 'N/A', attrition_risk: 'N/A', ml_score: 'N/A' });
        } catch (error) {
            toast({ title: 'Could not load analytics', description: error.response?.data?.detail || error.message, variant: 'destructive' });
            setData({ key_metric: 'N/A', retention: 'N/A', attrition_risk: 'N/A', ml_score: 'N/A' });
        } finally {
            setIsLoading(false);
        }
    },
    [filters, toast]);

    useEffect(() => {
        fetchData();
    }, [fetchData]);

    // Chart series for whatever the filter is set to. These used to be fetched
    // once with no department at all, so choosing a department changed the four
    // stat cards and left every chart below them showing the whole company,
    // presented as if it were the filtered view.
    useEffect(() => {
        let alive = true;
        getAnalyticsCharts(filters.department || undefined)
            .then(res => { if (alive && res?.data) setCharts(res.data); })
            .catch(() => { /* leave empty; widgets show their own empty state */ });
        return () => { alive = false; };
    }, [filters.department]);

    const handleFilterChange = useCallback((e) => {
        setFilters(prev => ({ ...prev, [e.target.name]: e.target.value }));
    }, []);

    const statCards = useMemo(() => [
        { id: 1, title: 'Composite workforce health', value: data.key_metric, unit: 'overall', icon: <Zap size={16} />, color: tokens.color?.['success'] },
        { id: 2, title: 'Projected retention', value: data.retention, unit: 'of the workforce', icon: <TrendingUp size={16} />, color: tokens.color?.['warning'] },
        // The band comes from the backend; it used to be the constant "Low"
        // regardless of how high the risk actually was.
        { id: 3, title: 'Attrition risk', value: data.attrition_risk, unit: data.attrition_band || '', icon: <AlertTriangle size={16} />, color: `rgb(${tokens.color?.['accent-2-rgb'] || '0,200,255'})` },
        // This is the average performance rating, not any model's F1 score.
        { id: 4, title: 'Average performance rating', value: data.average_performance || data.ml_score, unit: 'across reviews', icon: <Cpu size={16} />, color: tokens.color?.['text-100'] },
    ], [data]);

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: tokens.spacing?.lg }}>
            <div style={{...styles.filterGroup, borderBottom: tokens.ui?.border?.inner || tokens.color?.['border-600'], paddingBottom: tokens.spacing?.sm}}>
                <Filter size={16} style={{ color: tokens.color?.['muted-500'], flexShrink: 0 }} />
                {/* Real departments from the workforce, not a hardcoded list that
                    never matched the data. */}
                <select
                    name="department"
                    style={{...styles.select, width: '220px'}}
                    value={filters.department}
                    onChange={handleFilterChange}
                    disabled={isLoading}
                    aria-label="Filter by department"
                >
                    <option value="All" style={{ background: tokens.color?.['panel-700'], color: tokens.color?.['text-100'] }}>All departments</option>
                    {departments.map((d) => (
                        <option key={d} value={d} style={{ background: tokens.color?.['panel-700'], color: tokens.color?.['text-100'] }}>{d}</option>
                    ))}
                </select>
                <button
                    onClick={fetchData}
                    style={{...styles.primaryBtn, width: '150px'}}
                    className="analytics-btn-hover-effect"
                    disabled={isLoading}
                >
                    {isLoading ?
                    <Loader2 size={16} className="animate-spin" /> : 'Apply Filters'}
                </button>
            </div>

            <div style={styles.grid} className="portal-grid">
                {/* Stat cards use DataCard's stat mode so figures align with
                    every other portal instead of a bespoke unaligned layout. */}
                {statCards.map((stat) => (
                    <div key={stat.id} style={{ gridColumn: 'span 3' }}>
                        <DataCard title={stat.title} value={stat.value} unit={stat.unit} icon={stat.icon} color={stat.color} />
                    </div>
                ))}
            </div>
            <div style={styles.grid} className="portal-grid">
                {/* Scatter Chart - span 8 (real perf vs tenure across the workforce) */}
                <div style={{ gridColumn: 'span 8' }}>
                    <DataCard title="Performance against length of service" isChart={true} minHeight="300px">
                        <PerfTenureScatter points={charts.perf_vs_tenure} />
                    </DataCard>
                </div>
                {/* Bar Chart - span 4 (real headcount by department) */}
                <div style={{ gridColumn: 'span 4' }}>
                    <DataCard title="Headcount by Department" isChart={true} minHeight="300px">
                        <ChartOrEmpty data={charts.headcount_by_department} minHeight="300px"
                            color={tokens.color?.['accent-primary']} label="Employees per department" />
                    </DataCard>
                </div>
                {/* Attrition risk by department (real avg risk, 0-100) */}
                <div style={{ gridColumn: 'span 12' }}>
                    <DataCard title="Attrition Risk by Department" isChart={true} minHeight="250px">
                        <ChartOrEmpty data={charts.attrition_by_department} minHeight="250px"
                            color={tokens.color?.['warning']} label="Average attrition-risk index (0-100)" />
                    </DataCard>
                </div>
            </div>
            <style>{`
                /* Ensure all options inherit the correct dark background when opened */
                select {
                    /* Forcing the color and background here helps against browser defaults */
                    color: ${tokens.color?.['text-100']} !important;
                    background-color: ${tokens.color?.['panel-700']} !important;
                }
                select option {
                    background-color: ${tokens.color?.['panel-700']} !important;
                    color: ${tokens.color?.['text-100']} !important;
                }
                .analytics-btn-hover-effect:hover:not(:disabled) {
                    transform: translateY(-2px) !important;
                    box-shadow: ${tokens.shadow?.hover} !important;
                 }
                .analytics-input:focus {
                    border-color: rgba(${tokens.color?.['accent-2-rgb'] || '0,200,255'}, 0.8) !important;
                    box-shadow: 0 0 0 2px rgba(${tokens.color?.['accent-2-rgb'] || '0,200,255'}, 0.3) !important;
                }
                @keyframes spin { from { transform: rotate(0deg);
                } to { transform: rotate(360deg); } }
                .animate-spin { animation: spin 1s linear infinite;
                }
            `}</style>
        </div>
    );
});
AnalyticsDashboard.displayName = 'AnalyticsDashboard';

// --- COMPONENT: AdvancedAnalytics ---
const AdvancedAnalytics = memo(() => {
    const styles = useMemo(() => getStyles(tokens), []);
    return (
        <div style={styles.portalContainer} className="portal-container" role="main" aria-label="Advanced Analytics Portal">
            <header style={styles.header}>
                <h1 style={styles.title}>
                    <BarChart3 size={24} style={{ color: tokens.color?.['success'] }} />
                    Advanced Analytics Portal
                </h1>
                <p style={styles.subtitle}>
                    Deep statistical insights and predictive modeling dashboards.
                </p>
            </header>
            <AnalyticsDashboard />
        </div>
    );
});
export default AdvancedAnalytics;