// /frontend/src/pages/AdvancedAnalytics.js - FINAL ALIASING FIX (Dropdown UI Fix)
// Advanced Analytics Portal - Restricted to HRBP/Admin/HRIT
import React, { useState, useMemo, useEffect, useCallback, memo } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { theme as tokens } from '../theme';
import { TrendingUp, BarChart3, ScatterChart, Zap, Loader2, Filter, Cpu, AlertTriangle, Scale, Send, Clock } from 'lucide-react';
// FIX: Using absolute path aliases
import { aggregateMetrics, getAdvancedAnalytics } from '../config/api';
import { useToast } from '../hooks/use-toast';
import DataCard from '../components/DataCard';
import ChartPlaceholder from '../components/ChartPlaceholder'; 

const MOCK_ANALYTICS_RESULT = {
    metric: 'Average Attrition Time',
    result: '15.5 months',
    breakdown: [{ value: 0.15, label: 'Low Engagement' }, { value: 0.85,
    label: 'High Compa-Ratio' }],
};

// --- Static Style Definitions ---
const getStyles = (tokens) => ({
    portalContainer: {
        padding: tokens.spacing?.xl,
        maxWidth: tokens.breakpoints?.desktop,
        margin: '0 auto',
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
        gap: tokens.spacing?.colGutter,
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
        gap: tokens.spacing?.sm,
        marginBottom: tokens.spacing?.md,
    }
});


// --- Sub-Component: AnalyticsDashboard (Hoisted) ---
const AnalyticsDashboard = memo(() => {
    const { toast } = useToast();
    const [data, setData] = useState({ key_metric: 'N/A', retention: 'N/A' });
    const [filters, setFilters] = useState({ department: 'All', time: 'Q4' });
    const [isLoading, setIsLoading] = useState(false);

    // CRITICAL FIX: Styles are derived once based on tokens
    const styles = useMemo(() => getStyles(tokens), []);

    const fetchData = useCallback(async () => {
        setIsLoading(true);
        try {
            const response = await aggregateMetrics({ filters });
            const advancedData = response.data || { key_metric: '92.5%', retention: '90%', attrition_risk: '4.5/10',
            ml_score: '98.1%' };
            setData(advancedData);
        } catch (error) {
            toast({ title: "API Error", description: "Failed to load advanced metrics.", variant: 'destructive' });
            setData({ key_metric: 'N/A', retention: 'N/A', attrition_risk: 'N/A', ml_score: 'N/A' });
        } finally {
            setIsLoading(false);
        }
    },
    [filters, toast]);

    useEffect(() => {
        fetchData();
    }, [fetchData]);

    const handleFilterChange = useCallback((e) => {
        setFilters(prev => ({ ...prev, [e.target.name]: e.target.value }));
    }, []);

    const mockStats = useMemo(() => [
        { id: 1, title: 'Key Metric Score', value: data.key_metric, unit: 'Composite', icon: Zap, color: tokens.color?.['success'], span: 3 },
        { id: 2, title: 'Retention Rate', value: data.retention, unit: 'Yearly', icon: TrendingUp, color: tokens.color?.['warning'], span: 3 },
        { id: 3, title: 'Attrition Risk Index', value: data.attrition_risk, unit: 'Low', icon: AlertTriangle, color: `rgb(${tokens.color?.['accent-2-rgb'] || '0,200,255'})`, span: 3 },
        { id: 4, title: 'ML Model Performance F1 Score', value: data.ml_score, unit: 'F1 Score', icon:
        Cpu, color: tokens.color?.['text-100'], span: 3 },
    ], [data]);

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: tokens.spacing?.lg }}>
            <div style={{...styles.filterGroup, borderBottom: tokens.ui?.border?.inner || tokens.color?.['border-600'], paddingBottom: tokens.spacing?.sm}}>
                <Filter size={16} style={{ color: tokens.color?.['muted-500'], marginTop: '10px' }} />
                <select 
                    name="department" 
                    // FIX: Use the new styles.select for the dark UI look
                    style={{...styles.select, width: '200px'}} 
                    value={filters.department} 
                    onChange={handleFilterChange} 
                    disabled={isLoading} 
                    aria-label="Department Filter"
                >
                    <option value="All" style={{ background: tokens.color?.['panel-700'], color: tokens.color?.['text-100'] }}>All Departments</option>
                    <option value="Tech" style={{ background: tokens.color?.['panel-700'], color: tokens.color?.['text-100'] }}>Technology</option>
                    <option value="HR" style={{ background: tokens.color?.['panel-700'], color: tokens.color?.['text-100'] }}>Human Resources</option>
                    <option value="Finance" style={{ background: tokens.color?.['panel-700'], color: tokens.color?.['text-100'] }}>Finance</option>
                </select>
                <select 
                    name="time" 
                    // FIX: Use the new styles.select for the dark UI look
                    style={{...styles.select, width: '150px'}} 
                    value={filters.time} 
                    onChange={handleFilterChange} 
                    disabled={isLoading} 
                    aria-label="Time Period Filter"
                >
                    {/* OPTION FIX: While the <select> style usually handles options, forcing option styles ensures maximum compatibility */}
                    <option value="Q4" style={{ background: tokens.color?.['panel-700'], color: tokens.color?.['text-100'] }}>Q4 2025</option>
                    <option value="Q3" style={{ background: tokens.color?.['panel-700'], color: tokens.color?.['text-100'] }}>Q3 2025</option>
                    <option value="FY" style={{ background: tokens.color?.['panel-700'], color: tokens.color?.['text-100'] }}>Full Year 2025</option>
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

            <div style={styles.grid}>
                {/* Stat Cards - span 3 each */}
                {mockStats.map(stat =>
                    (
                        <div key={stat.id} style={{ gridColumn: 'span 3' }}>
                            <DataCard title={stat.title}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: tokens.spacing?.sm }}>
                                    {stat.icon && <stat.icon
                                    size={20} color={tokens.color?.['text-100']} />}
                                    <p style={{ fontSize: tokens.typography?.h1?.fontSize, fontWeight: tokens.typography?.h1?.fontWeight, color: stat.color }}>
                                        {stat.value} <span style={{ fontSize: tokens.typography?.base?.fontSize, color: tokens.color?.['muted-500'] }}>{stat.unit}</span>
                                    </p>
                                </div>
                            </DataCard>
                        </div>
                ))}
            </div>
            <div style={styles.grid}>
                {/* Scatter Chart - span 8 */}
                <div style={{ gridColumn: 'span 8' }}>
                    <DataCard title="Performance vs. Tenure Regression" isChart={true} minHeight="300px">
                        <ChartPlaceholder label="Scatter Plot: Performance vs Tenure" minHeight="300px" />
                    </DataCard>
                </div>
                {/* Bar Chart - span 4 */}
                <div style={{ gridColumn: 'span 4' }}>
                    <DataCard title="Diversity Distribution" isChart={true} minHeight="300px">
                        <ChartPlaceholder label="Bar Chart: Headcount by Demographic" minHeight="300px" />
                    </DataCard>
                </div>
                {/* Deep Dive (Full Width) */}
                <div style={{ gridColumn: 'span 12' }}>
                    <DataCard title="Unstructured Data Analysis (AI Insights)" isChart={true} minHeight="250px">
                        <ChartPlaceholder label="Unstructured Text Cluster Map" minHeight="250px" />
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
        <div style={styles.portalContainer} role="main" aria-label="Advanced Analytics Portal">
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