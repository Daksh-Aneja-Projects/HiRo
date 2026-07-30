// /frontend/src/hooks/useAgentWebsocket.js - FINAL PRODUCTION-READY REPLACEMENT
import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { WS_URL } from '../config/api'; // CRITICAL FIX: Import the hardened WS_URL

const RECONNECT_INTERVAL = 5000; // 5 seconds
const PING_INTERVAL = 30000; // 30 seconds
const HISTORY_LIMIT = 20; // rolling telemetry points kept for live charts

export const useAgentWebsocket = () => {
    // CRITICAL FIX 1: Explicitly define all state and refs
    const [isConnected, setIsConnected] = useState(false);
    const [telemetryMetrics, setTelemetryMetrics] = useState(null);
    // Rolling window of recent telemetry for live time-series charts.
    const [telemetryHistory, setTelemetryHistory] = useState([]);
    const wsRef = useRef(null);
    const reconnectTimerRef = useRef(null);
    const pingTimerRef = useRef(null);
    const clientIdRef = useRef(`client-${Date.now()}-${Math.random().toString(36).substring(7)}`);

    // CRITICAL FIX 2: useCallback explicitly used for connection logic
    const connect = useCallback(() => {
        // Prevent multiple connections
        if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
            return;
        }

        // CRITICAL FIX 3: Construct the full WebSocket URL
        const url = `${WS_URL}/ws/si-integration?client_id=${clientIdRef.current}`; 
        
        wsRef.current = new WebSocket(url);

        // 1. Connection Open
        wsRef.current.onopen = () => {
            console.log('WS: Connected to SI Integration stream.');
            setIsConnected(true);
            clearTimeout(reconnectTimerRef.current);

            // Subscribe to Telemetry stream immediately after connecting
            wsRef.current.send(JSON.stringify({ type: 'subscribe_telemetry' }));

            // Start PING interval to keep connection alive
            pingTimerRef.current = setInterval(() => {
                // Ensure check before sending
                if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                    wsRef.current.send(JSON.stringify({ type: 'ping', timestamp: Date.now() }));
                }
            }, PING_INTERVAL);
        };

        // 2. Message Handler
        wsRef.current.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                if (message.type === 'telemetry_metrics') {
                    // Update state with live backend metrics
                    const metrics = message.data;
                    setTelemetryMetrics(metrics);
                    // Append to the rolling history for live charts.
                    setTelemetryHistory((prev) => {
                        const point = {
                            name: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
                            value: Number(metrics?.events_per_second ?? 0),
                            cpu: Number(metrics?.cpu_load ?? 0),
                            memory: Number(metrics?.memory_load ?? 0),
                            latency: Number(metrics?.latency ?? 0),
                        };
                        return [...prev, point].slice(-HISTORY_LIMIT);
                    });
                } else if (message.type === 'simulation_update') {
                    console.log('WS: Agent Update:', message.data);
                }
            } catch (e) {
                console.error('WS: Error parsing message:', e, event.data);
            }
        };

        // 3. Connection Close/Error Handler (Self-Healing Logic)
        const handleCloseOrError = (event) => {
            console.warn('WS: Connection closed/error. Attempting reconnect in 5s.', event);
            setIsConnected(false);
            clearInterval(pingTimerRef.current);
            wsRef.current = null;
            
            // CRITICAL FIX 4: Reconnect logic
            reconnectTimerRef.current = setTimeout(connect, RECONNECT_INTERVAL);
        };

        wsRef.current.onclose = handleCloseOrError;
        wsRef.current.onerror = handleCloseOrError;
    }, []);

    // CRITICAL FIX 5: Run connection once on mount and handle cleanup
    useEffect(() => {
        connect();

        // Cleanup on unmount
        return () => {
            if (wsRef.current) {
                wsRef.current.close();
            }
            clearTimeout(reconnectTimerRef.current);
            clearInterval(pingTimerRef.current);
        };
    }, [connect]);

    // CRITICAL FIX 6: Ensure safe access to send function
    const send = useCallback((data) => {
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify(data));
        } else {
            console.warn("WebSocket not open. Message failed to send:", data);
        }
    }, []);

    // CRITICAL FIX 7: Use useMemo for a stable return object
    const memoizedReturn = useMemo(() => ({
        isConnected,
        telemetryMetrics,
        telemetryHistory,
        send
    }), [isConnected, telemetryMetrics, telemetryHistory, send]);

    return memoizedReturn;
};