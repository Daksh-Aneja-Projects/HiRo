// /frontend/src/components/TelemetryDisplay.js - FINAL PRODUCTION-READY REPLACEMENT
import React, { useMemo, memo } from 'react';
import { theme as tokens } from '../theme';
import { useApi } from '../hooks/useApi';
import { getCurrentTelemetry } from '../config/api'; // CRITICAL FIX: Import stabilized API function
import DataCard from './DataCard';
import { Cpu, Server, Clock, AlertTriangle, Loader2, Zap } from 'lucide-react';

const TelemetryDisplay = memo(() => {
    
    // CRITICAL API INTEGRATION: Fetch Current Telemetry Data
    const { 
        data: metrics, 
        isLoading, 
        error 
    } = useApi(getCurrentTelemetry, [], true, 10000); // CRITICAL FIX: Polling interval explicitly set to 10000ms (10 seconds)

    // Stabilize data access with mock fallback
    const cpuLoad = metrics?.cpu_load?.toFixed(1) || 'N/A';
    const activeAgents = metrics?.active_nodes || 0;
    const latency = metrics?.latency?.toFixed(0) || 'N/A';
    const memoryLoad = metrics?.memory_load?.toFixed(1) || 'N/A';

    const styles = useMemo(() => ({
        grid: { display: 'grid', gridTemplateColumns: 'repeat(12, 1fr)', gap: tokens.spacing?.lg, marginBottom: tokens.spacing?.lg },
        card: { gridColumn: 'span 3' },
    }), []);

    if (isLoading) {
        return <p style={{ textAlign: 'center' }}><Loader2 size={24} className="animate-spin" /> Loading core telemetry...</p>;
    }
    
    return (
        <div style={styles.grid}>
            {/* CPU Load */}
            <div style={styles.card}>
                <DataCard title="CPU Load" value={cpuLoad} unit="%" color={tokens.color?.['accent-primary']}>
                    <Cpu size={24} color={tokens.color?.['accent-primary']} />
                </DataCard>
            </div>
            {/* Active Agents */}
            <div style={styles.card}>
                <DataCard title="Active Agents" value={activeAgents} unit="Nodes" color={tokens.color?.success}>
                    <Zap size={24} color={tokens.color?.success} />
                </DataCard>
            </div>
            {/* Latency */}
            <div style={styles.card}>
                <DataCard title="API Latency" value={latency} unit="ms" color={tokens.color?.warning}>
                    <Clock size={24} color={tokens.color?.warning} />
                </DataCard>
            </div>
            {/* Memory Load */}
            <div style={styles.card}>
                <DataCard title="Memory Load" value={memoryLoad} unit="%" color={tokens.color?.danger}>
                    <Server size={24} color={tokens.color?.danger} />
                </DataCard>
            </div>

            {error && (
                <div style={{ gridColumn: 'span 12', color: tokens.color?.danger, textAlign: 'center' }}>
                    <AlertTriangle size={16} /> Error fetching telemetry data.
                </div>
            )}
        </div>
    );
});

TelemetryDisplay.displayName = 'TelemetryDisplay';
export default TelemetryDisplay;