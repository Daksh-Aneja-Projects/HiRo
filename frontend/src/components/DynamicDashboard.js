// /frontend/src/components/DynamicDashboard.js - FINAL PRODUCTION-READY REPLACEMENT (Fixes fontSize TypeErrors)
import React, { useMemo, memo } from 'react';
import { theme as tokens } from '../theme';
import { useApi } from '../hooks/useApi'; // For dynamic data fetching
import { get } from '../config/api'; // The generic GET utility from the stabilized api.js

// Dynamic Visualization Components (MOCK IMPLEMENTATIONS for now, assuming they exist)
import ChartPlaceholder from './ChartPlaceholder'; 
import DataCard from './DataCard';
import { Loader2, Zap, BarChart, TrendingUp, Cpu, Compass, AlertTriangle } from 'lucide-react'; // Ensure AlertTriangle is imported

// --- WIDGET MAPPER ---
const ComponentMap = {
    StatCard: DataCard,
    BarChart: ChartPlaceholder, // Using Placeholder for complex charts
    LineChart: ChartPlaceholder, 
    PieChart: ChartPlaceholder,
    GeoMap: ChartPlaceholder,
    SynthesizedCard: DataCard, // Using DataCard for general synthesized text/stats
};

const IconMap = {
    StatCard: Zap,
    BarChart: BarChart,
    LineChart: TrendingUp,
    PieChart: Compass,
    GeoMap: Compass,
    SynthesizedCard: Cpu,
};


// --- DYNAMIC WIDGET COMPONENT (Handles fetching and rendering) ---
/**
 * Fetches data for a single widget based on the AI-generated configuration.
 */
const DynamicWidget = memo(({ widgetConfig }) => {
    const { 
        title, 
        metricKey, 
        vizType, 
        dataEndpoint, 
        filters, 
        w, 
        h 
    } = widgetConfig;

    // Use a placeholder function for the API call that uses the GET utility
    const apiFunction = useMemo(() => {
        // Construct the full URL for the dynamic endpoint, adding filters as query params
        const urlWithParams = `${dataEndpoint}?metricKey=${metricKey}&${new URLSearchParams(filters).toString()}`;
        return () => get(urlWithParams);
    }, [dataEndpoint, metricKey, filters]);
    
    // CRITICAL: Use the useApi hook to manage fetching state for this specific widget
    const { data, isLoading, error } = useApi(apiFunction, [apiFunction], true, null);

    // CRITICAL: Determine the visualization component
    const VizComponent = ComponentMap[vizType] || ChartPlaceholder;
    const DefaultIcon = IconMap[vizType] || Loader2;

    const widgetStyles = useMemo(() => ({
        gridColumn: `span ${w}`,
        gridRow: `span ${h}`,
        // Set a minimum height if not explicitly defined by 'h' for better layout
        minHeight: `${(h || 1) * 150}px`, 
        // Ensure error state is visible
        border: error ? `2px solid ${tokens.color?.danger}` : `1px solid ${tokens.color?.['border-600']}`,
        borderRadius: tokens.border?.radius?.card,
        background: tokens.color?.['panel-800'],
        padding: tokens.spacing?.md,
        boxShadow: tokens.shadow?.default,
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
    }), [w, h, error]);


    if (isLoading) {
        return (
            <div style={widgetStyles}>
                <Loader2 size={32} className="animate-spin" color={tokens.color?.['accent-primary']} />
                <p style={{ color: tokens.color?.['muted-500'] }}>Loading {title}...</p>
            </div>
        );
    }

    if (error) {
         return (
            <div style={widgetStyles}>
                <p style={{ color: tokens.color?.danger, textAlign: 'center' }}>
                    Error fetching data for "{title}": {error.message || error}
                </p>
                <p style={{ color: tokens.color?.['muted-500'], 
                    // --- FIX: Added optional chaining ---
                    fontSize: tokens.typography?.small?.fontSize // FIX: Safe access
                    // ------------------------------------
                }}>Endpoint: {dataEndpoint}</p>
            </div>
        );
    }
    
    // --- Render the visualization component ---
    return (
        <div style={widgetStyles} title={`Widget: ${title} (${vizType})`}>
            {/* NOTE: In a full production app, the VizComponent would need to parse 
            the 'data' structure correctly. Here, we pass the raw data and config.
            For placeholders, we pass the title/label.
            */}
            
            {VizComponent === ChartPlaceholder ? (
                 <VizComponent label={`${title} (${vizType})`} minHeight="100%" data={data} />
            ) : (
                // Assuming StatCard/DataCard structure requires value, unit, etc.
                 <DataCard 
                    title={title} 
                    value={data?.value || 'N/A'} 
                    unit={data?.unit || ''} 
                    color={tokens.color?.['accent-primary']}
                >
                    <DefaultIcon size={24} color={tokens.color?.['accent-primary']} />
                </DataCard>
            )}
            
            {/* Optional Footer for debugging */}
             <div style={{ color: tokens.color?.['muted-500'], fontSize: '10px', marginTop: tokens.spacing?.xs, textAlign: 'center' }}>
                Metric: {metricKey}
            </div>
        </div>
    );
});
DynamicWidget.displayName = 'DynamicWidget';


// --- MAIN DYNAMIC DASHBOARD COMPONENT ---
/**
 * Renders the dashboard based on the SynthesizedDashboardSchema config object.
 */
const DynamicDashboard = memo(({ config }) => {

    const styles = useMemo(() => ({
        // CRITICAL FIX: Implement the CSS Grid structure
        dashboardGrid: {
            display: 'grid',
            // Defaulting to a 12-column grid system
            gridTemplateColumns: 'repeat(12, 1fr)', 
            // Setting a flexible row height for vertical responsiveness
            gridAutoRows: 'minmax(150px, auto)', 
            gap: tokens.spacing?.lg,
            width: '100%',
            // Ensure no overflow issues within the main portal-container
            overflow: 'visible', 
        },
        header: {
            gridColumn: 'span 12',
            color: tokens.color?.['text-100'],
            marginBottom: tokens.spacing?.md,
        },
    }), []);

    if (!config || !config.widgets || config.widgets.length === 0) {
        return (
            <div style={{ color: tokens.color?.warning, textAlign: 'center', padding: tokens.spacing?.xl }}>
                <AlertTriangle size={32} />
                <h3 style={{ margin: tokens.spacing?.md }}>Empty Synthesis Result</h3>
                <p>The AI did not generate any widgets for this dashboard configuration. Please try a different command.</p>
            </div>
        );
    }

    return (
        <div style={styles.dashboardGrid}>
            {/* Optionally display a synthesized title/summary card */}
            {config.title && (
                 <div style={styles.header}>
                    <h2 style={{ margin: 0 }}>{config.title}</h2>
                    <p style={{ color: tokens.color?.['muted-500'], 
                        // --- FIX: Added optional chaining ---
                        fontSize: tokens.typography?.base?.fontSize // FIX: Safe access
                        // ------------------------------------
                    }}>
                        Generated from AI Command. Metrics are fetched in real-time.
                    </p>
                 </div>
            )}
            
            {/* Iterate through the AI-generated widgets */}
            {config.widgets.map((widget, index) => (
                <DynamicWidget key={widget.key || index} widgetConfig={widget} />
            ))}
        </div>
    );
});

DynamicDashboard.displayName = 'DynamicDashboard';
export default DynamicDashboard;