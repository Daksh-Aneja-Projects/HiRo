// /frontend/src/components/HRSDMonitoringDashboard.js - FINAL PRODUCTION-READY REPLACEMENT (Polling Rate Reduced)
import React, { useMemo, memo, useCallback, useState } from 'react';
import { theme as tokens } from '../theme';
import { useApi } from '../hooks/useApi';
import { useToast } from '../hooks/use-toast';
import { getHRSDMonitoringOverview, syncServiceNow } from '../config/api'; // CRITICAL FIX: Import stabilized API functions
import DataCard from './DataCard';
import ChartPlaceholder from './ChartPlaceholder';
import { MessageCircle, CheckCircle, AlertTriangle, Loader2, RefreshCw, Clock } from 'lucide-react'; // Added Clock icon

const HRSDMonitoringDashboard = memo(() => {
    const { toast } = useToast();
    const [isSyncing, setIsSyncing] = useState(false);

    // CRITICAL API INTEGRATION 1: Fetch Monitoring Data (Polling every 60s)
    const { 
        data: overview, 
        isLoading, 
        error, 
        refetch 
    } = useApi(getHRSDMonitoringOverview, [], true, 60000); // Polling reduced to every 60 seconds

    // CRITICAL: Handle ServiceNow Sync
    const handleSync = useCallback(async () => {
        setIsSyncing(true);
        try {
            // CRITICAL API INTEGRATION 2: Trigger ServiceNow Sync
            await syncServiceNow();
            toast({ title: 'Sync Initiated', description: 'ServiceNow integration sync initiated. Monitoring results.', variant: 'info' });
            refetch();
        } catch (error) {
            // NOTE: The error structure here relies on Axios interceptors providing a good error object
            toast({ title: 'Sync Failed', description: error.response?.data?.detail || error.message, variant: 'destructive' });
        } finally {
            setIsSyncing(false);
        }
    }, [toast, refetch]);


    const styles = useMemo(() => ({
        grid: { display: 'grid', gridTemplateColumns: 'repeat(12, 1fr)', gap: tokens.spacing?.lg, marginBottom: tokens.spacing?.lg },
        card: { gridColumn: 'span 3' },
        chart: { gridColumn: 'span 6', minHeight: '300px' },
        syncCard: { gridColumn: 'span 12', padding: tokens.spacing?.md, background: tokens.color?.['panel-700'], borderRadius: tokens.border?.radius?.card, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }
    }), []);

    if (isLoading && !overview) {
        return (
            <div style={{ textAlign: 'center', padding: tokens.spacing?.xl }}>
                <Loader2 size={32} className="animate-spin" color={tokens.color?.['accent-primary']} />
                <p style={{ color: tokens.color?.['muted-500'] }}>Loading HRSD operational overview...</p>
            </div>
        );
    }
    
    // Add check for error state to improve UX
    if (error) {
         return (
             <div style={{ textAlign: 'center', padding: tokens.spacing?.xl, color: tokens.color?.danger }}>
                 <AlertTriangle size={32} />
                 <p>Error loading HRSD monitoring data. Please try syncing manually.</p>
             </div>
         );
     }
    
    return (
        <div style={styles.grid}>
            {/* Sync Control */}
            <div style={styles.syncCard}>
                <p style={{ color: tokens.color?.['muted-500'], margin: 0 }}>
                    Last Sync: {overview?.last_sync || 'N/A'}
                </p>
                <button 
                    onClick={handleSync} 
                    disabled={isSyncing} 
                    style={{ padding: '8px 15px', background: tokens.color?.['accent-primary'], border: 'none', borderRadius: tokens.border?.radius?.button, color: tokens.color?.['bg-deep'], cursor: 'pointer', display: 'flex', alignItems: 'center', gap: tokens.spacing?.xs }} 
                    className="hrsd-sync-hover"
                >
                    {isSyncing ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
                    {isSyncing ? 'Syncing...' : 'Force ServiceNow Sync'}
                </button>
            </div>
            
            {/* Metrics Cards */}
            <div style={styles.card}>
                <DataCard title="Open Tickets" value={overview?.open_tickets || 0} unit="Count" color={tokens.color?.warning}>
                    <MessageCircle size={24} color={tokens.color?.warning} />
                </DataCard>
            </div>
            <div style={styles.card}>
                <DataCard title="Autonomous Resolution Rate" value={(overview?.auto_resolution_rate * 100).toFixed(1) || 0} unit="%" color={tokens.color?.success}>
                    <CheckCircle size={24} color={tokens.color?.success} />
                </DataCard>
            </div>
            <div style={styles.card}>
                <DataCard title="Policy Violation Spikes" value={overview?.violation_spikes || 0} unit="Count" color={tokens.color?.danger}>
                    <AlertTriangle size={24} color={tokens.color?.danger} />
                </DataCard>
            </div>
            <div style={styles.card}>
                <DataCard title="Avg. Time to Resolve" value={overview?.avg_resolution_time_hrs || 'N/A'} unit="Hours" color={tokens.color?.['accent-primary']}>
                    <Clock size={24} color={tokens.color?.['accent-primary']} />
                </DataCard>
            </div>

            {/* Charts */}
            <div style={styles.chart}>
                <ChartPlaceholder label="Autonomous Resolution Success Trend" minHeight="100%" />
            </div>
            <div style={styles.chart}>
                <ChartPlaceholder label="Ticket Volume by Channel" minHeight="100%" />
            </div>
            
            <style>{`
                .hrsd-sync-hover:hover { box-shadow: 0 0 10px ${tokens.color?.['accent-primary']}77; transform: translateY(-1px); }
            `}</style>
        </div>
    );
});

HRSDMonitoringDashboard.displayName = 'HRSDMonitoringDashboard';
export default HRSDMonitoringDashboard;