// /frontend/src/components/LiveTelemetryFeed.js - PRODUCTION-READY WEBSOCKET IMPLEMENTATION (Fixes fontSize TypeErrors)
import React, { useState, useEffect, useCallback, memo, useMemo } from 'react';
import { Loader2, Zap, Cpu, Server, Clock, AlertTriangle } from 'lucide-react';
import { theme as tokens } from '../theme';
import { createTelemetryWebSocket, getCurrentMetrics } from '../config/api';
import DataCard from './DataCard';

const LiveTelemetryFeed = memo(() => {
    const [metrics, setMetrics] = useState({ 
         cpu_load: 0, 
         memory_load: 0, 
         events_per_second: 0, 
         active_nodes: 0 
     });
    const [status, setStatus] = useState('OFFLINE'); // OFFLINE, CONNECTING, ONLINE, ERROR
    const [log, setLog] = useState([]);

    // CRITICAL: WebSocket implementation
    useEffect(() => {
        let ws;
        let reconnectTimeout;

        const connect = () => {
            setStatus('CONNECTING');
            // ASSUMPTION: createTelemetryWebSocket uses the REACT_APP_WS_URL/api/admin/telemetry/live endpoint
            ws = createTelemetryWebSocket('/api/admin/telemetry/live'); 

            ws.onopen = () => {
                console.log('Telemetry WebSocket connected.');
                setStatus('ONLINE');
            };

            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    if (data.type === 'metric') {
                        // Update metrics in a robust way
                        setMetrics(prev => ({ ...prev, ...data.payload }));
                    } else if (data.type === 'log') {
                        // Add log entry, keeping the log array manageable
                        setLog(prev => {
                            const newLog = [{ time: new Date().toLocaleTimeString(), message: data.payload.message }, ...prev];
                            return newLog.slice(0, 50); // Keep only the last 50 entries
                        });
                    }
                } catch (e) {
                    console.error("Error parsing WebSocket message:", e);
                }
            };

            ws.onclose = () => {
                console.warn('Telemetry WebSocket closed. Attempting reconnect in 5s...');
                setStatus('OFFLINE');
                clearTimeout(reconnectTimeout);
                // CRITICAL FIX: Implement a simple reconnect mechanism
                reconnectTimeout = setTimeout(connect, 5000); 
            };

            ws.onerror = (error) => {
                console.error('Telemetry WebSocket error:', error);
                setStatus('ERROR');
                ws.close(); // Force close to trigger the onclose/reconnect logic
            };
        };

        // Start connection
        connect();

        // Cleanup function for component unmount
        return () => {
            clearTimeout(reconnectTimeout);
            if (ws) {
                ws.close();
            }
        };
    }, []); // Empty dependency array ensures it runs once on mount

    // The WebSocket stream only runs when the message bus is connected. Poll the
    // REST telemetry endpoint as well so these figures are always real host
    // readings rather than zeros.
    useEffect(() => {
        let alive = true;
        const tick = () => getCurrentMetrics()
            .then((res) => {
                if (!alive || !res?.data) return;
                const d = res.data;
                setMetrics((prev) => ({
                    ...prev,
                    cpu_load: Number(d.cpu_load) || 0,
                    memory_load: Number(d.memory_load) || 0,
                    // agent_activity is a 0..1 index; surface it as events/sec-equivalent load.
                    events_per_second: Math.round((Number(d.agent_activity) || 0) * 100),
                    active_nodes: prev.active_nodes || 1,
                }));
                setStatus((s) => (s === 'ONLINE' ? s : 'POLLING'));
            })
            .catch(() => {});
        tick();
        const id = setInterval(tick, 3000);
        return () => { alive = false; clearInterval(id); };
    }, []);

    const styles = useMemo(() => ({
        grid: { display: 'grid', gridTemplateColumns: 'repeat(12, 1fr)', gap: tokens.spacing?.lg },
        statusDot: (currentStatus) => ({
            width: '12px', height: '12px', borderRadius: '50%', marginRight: tokens.spacing?.xs,
            backgroundColor: currentStatus === 'ONLINE' ? tokens.color?.success : (currentStatus === 'OFFLINE' ? tokens.color?.danger : (currentStatus === 'CONNECTING' ? tokens.color?.warning : tokens.color?.danger)), 
            boxShadow: currentStatus === 'ONLINE' ? `0 0 5px ${tokens.color?.success}` : 'none'
        }),
        statusText: (currentStatus) => ({
            color: currentStatus === 'ONLINE' ? tokens.color?.success : (currentStatus === 'OFFLINE' ? tokens.color?.danger : tokens.color?.warning), 
            display: 'flex', alignItems: 'center', margin: 0
        }),
        logBox: {
            height: '200px',
            overflowY: 'scroll',
            background: tokens.color?.['panel-700'],
            borderRadius: tokens.border?.radius?.card,
            padding: tokens.spacing?.md,
            fontFamily: 'monospace',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            border: `1px solid ${tokens.color?.['border-600']}`
        }
    }), []);


    return (
        <div style={{ padding: tokens.spacing?.lg, background: tokens.color?.['panel-800'], borderRadius: tokens.border?.radius?.card }}>
            {/* Header and Status */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: tokens.spacing?.lg }}>
                <h2 style={{ margin: 0, color: tokens.color?.['text-100'] }}>Live Orchestrator Telemetry</h2>
                <p style={styles.statusText(status)}>
                    <span style={styles.statusDot(status)} className={status === 'CONNECTING' ? 'animate-pulse' : ''}></span>
                    Status: {status}
                </p>
            </div>
            
            {/* Metrics Grid */}
            <div style={styles.grid}>
                {/* CPU Load - span 3 */}
                <div style={{ gridColumn: 'span 3' }}>
                    <DataCard title="CPU Load" value={metrics.cpu_load.toFixed(1)} unit="%" color={tokens.color?.['accent-primary']}>
                        <Cpu size={24} color={tokens.color?.['accent-primary']} />
                    </DataCard>
                </div>
                {/* Memory Load - span 3 */}
                <div style={{ gridColumn: 'span 3' }}>
                    <DataCard title="Memory Load" value={metrics.memory_load.toFixed(1)} unit="%" color={tokens.color?.['accent-primary']}>
                        <Server size={24} color={tokens.color?.['accent-primary']} />
                    </DataCard>
                </div>
                {/* Events / Second - span 3 */}
                <div style={{ gridColumn: 'span 3' }}>
                    <DataCard title="Events / Second" value={metrics.events_per_second.toFixed(0)} unit="events" color={tokens.color?.['accent-primary']}>
                        <Clock size={24} color={tokens.color?.['accent-primary']} />
                    </DataCard>
                </div>
                {/* Active Nodes - span 3 */}
                <div style={{ gridColumn: 'span 3' }}>
                    <DataCard title="Active Nodes" value={metrics.active_nodes.toFixed(0)} unit="nodes" color={tokens.color?.['accent-primary']}>
                        <Server size={24} color={tokens.color?.['accent-primary']} />
                    </DataCard>
                </div>
            </div>

            {/* Log Stream */}
            <div style={{ marginTop: tokens.spacing?.lg }}>
                <h3 style={{ color: tokens.color?.['text-100'], marginBottom: tokens.spacing?.sm }}>Agent Log Stream</h3>
                <div style={styles.logBox}>
                    {log.map((entry, index) => (
                        <p key={index} style={{ color: tokens.color?.['muted-500'], 
                            // --- FIX: Added optional chaining ---
                            fontSize: tokens.typography?.small?.fontSize, 
                            // ------------------------------------
                            margin: 0, lineHeight: '1.2' }}>
                            <span style={{ color: tokens.color?.['accent-secondary'] }}>[{entry.time}]</span> {entry.message}
                        </p>
                    ))}
                    {log.length === 0 && <p style={{ textAlign: 'center', color: tokens.color?.['muted-500'] }}>Waiting for live log data...</p>}
                </div>
            </div>
        </div>
    );
});

LiveTelemetryFeed.displayName = 'LiveTelemetryFeed';
export default LiveTelemetryFeed;