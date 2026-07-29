// /frontend/src/components/AgentStatusMonitor.jsx - FINAL PRODUCTION-READY REPLACEMENT
import React, { useMemo, memo } from 'react';
import { theme as tokens } from '../theme';
import { useAgentWebsocket } from '../hooks/useAgentWebsocket'; // CRITICAL FIX: Import WebSocket hook

// UI COMPONENTS
import DataCard from './DataCard';
import AreaChartWidget from './charts/AreaChartWidget';
import BarChartWidget from './charts/BarChartWidget';
import { Cpu, Server, CheckCircle, Loader2, AlertTriangle, MessageCircle } from 'lucide-react';

const AgentStatusMonitor = memo(() => {
    
    // CRITICAL API INTEGRATION: Use the WebSocket hook for live data
    const {
        isConnected,
        telemetryMetrics,
        telemetryHistory
    } = useAgentWebsocket();

    // Live resource-utilization snapshot for the bar chart (real system metrics).
    const resourceData = useMemo(() => ([
        { name: 'CPU', value: Number(telemetryMetrics?.cpu_load ?? 0) },
        { name: 'Memory', value: Number(telemetryMetrics?.memory_load ?? 0) },
        { name: 'Disk', value: Number(telemetryMetrics?.disk_usage ?? 0) },
    ]), [telemetryMetrics]);

    // Calculate derived status and values
    const primaryStatus = isConnected ? 'ONLINE' : 'OFFLINE';
    const statusColor = isConnected ? tokens.color?.success : tokens.color?.danger;
    
    // Default to zero or N/A when metrics are not yet received
    const cpuLoad = telemetryMetrics?.cpu_load?.toFixed(1) || 'N/A';
    const activeAgents = telemetryMetrics?.active_nodes || 0;
    const messagesPerSecond = telemetryMetrics?.events_per_second?.toFixed(0) || 0;


    const styles = useMemo(() => ({
        grid: { display: 'grid', gridTemplateColumns: 'repeat(12, 1fr)', gap: tokens.spacing?.lg, marginBottom: tokens.spacing?.lg },
        card: { gridColumn: 'span 3' },
        chart: { gridColumn: 'span 6', minHeight: '300px' },
        statusHeader: { gridColumn: 'span 12', padding: tokens.spacing?.sm, borderRadius: tokens.border?.radius?.input, background: tokens.color?.['panel-700'], borderLeft: `4px solid ${statusColor}` }
    }), [statusColor]);


    return (
        <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            <div style={styles.statusHeader}>
                <h3 style={{ margin: 0, color: tokens.color?.['text-100'], display: 'flex', alignItems: 'center', gap: tokens.spacing?.xs }}>
                    <Server size={20} color={statusColor} /> 
                    Orchestrator Kernel Status: {primaryStatus} 
                    {!isConnected && <span style={{ color: tokens.color?.warning, marginLeft: tokens.spacing?.sm }}>(Attempting Reconnect...)</span>}
                </h3>
            </div>
            
            <div style={{...styles.grid, marginTop: tokens.spacing?.lg}}>
                {/* Metrics Cards */}
                <div style={styles.card}>
                    <DataCard title="CPU Load" value={cpuLoad} unit="%" color={tokens.color?.warning}>
                        <Cpu size={24} color={tokens.color?.warning} />
                    </DataCard>
                </div>
                <div style={styles.card}>
                    <DataCard title="Active Agents" value={activeAgents} unit="Nodes" color={tokens.color?.['accent-primary']}>
                        <CheckCircle size={24} color={tokens.color?.['accent-primary']} />
                    </DataCard>
                </div>
                <div style={styles.card}>
                    <DataCard title="Event Bus TPS" value={messagesPerSecond} unit="Msg/s" color={tokens.color?.success}>
                        <MessageCircle size={24} color={tokens.color?.success} />
                    </DataCard>
                </div>
                <div style={styles.card}>
                    <DataCard title="WS Latency" value={telemetryMetrics?.latency?.toFixed(0) || 'N/A'} unit="ms" color={tokens.color?.danger}>
                        <AlertTriangle size={24} color={tokens.color?.danger} />
                    </DataCard>
                </div>
                
                {/* Charts — live data from the telemetry stream */}
                <div style={styles.chart}>
                    {telemetryHistory && telemetryHistory.length > 0 ? (
                        <AreaChartWidget label="Event Throughput (msg/s)" minHeight="100%" data={telemetryHistory} />
                    ) : (
                        <AreaChartWidget label="Event Throughput (msg/s) — awaiting telemetry..." minHeight="100%" data={[]} />
                    )}
                </div>
                <div style={styles.chart}>
                    <BarChartWidget label="System Resource Utilization (%)" minHeight="100%" data={resourceData} />
                </div>
            </div>
        </div>
    );
});

AgentStatusMonitor.displayName = 'AgentStatusMonitor';
export default AgentStatusMonitor;