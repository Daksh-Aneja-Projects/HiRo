// /frontend/src/pages/HRITPortal.js - FINAL PRODUCTION-READY REPLACEMENT (Autonomous Healing Log Array Fix)
import React, { useMemo, memo, useState, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import { theme as tokens } from '../theme';

// CRITICAL API IMPORTS - FIX: Using absolute path aliases
import {
    createNewAIAgent, getHRITDashboardData, getAutonomousHealingLog,
    getServiceNowHealth, resetHRITData, getOrchestratorDashboardData
} from '../config/api';
import { useApi } from '../hooks/useApi';
import { useToast } from '../hooks/use-toast';

// UI & NEW COMPONENTS - FIX: Using absolute path aliases
import DataCard from '../components/DataCard';
import BarChartWidget from '../components/charts/BarChartWidget';
import AreaChartWidget from '../components/charts/AreaChartWidget';
import PieChartWidget from '../components/charts/PieChartWidget';
import { useMetricSeries } from '../components/live/LivePrimitives';
import { countBy } from '../utils/chartData';
// CRITICAL INTEGRATION: Live Telemetry Feed (WebSocket)
import LiveTelemetryFeed from '../components/LiveTelemetryFeed'; 
import { 
    Cpu, Settings, Zap, CheckCircle, 
    XCircle, Loader2, AlertTriangle, MessageSquare
} from 'lucide-react';


// --- 10.1. Sub-Module: Agent Factory ---
/**
 * Renders the form for creating new AI agents.
 */
const AgentFactoryModule = memo(() => {
    const { toast } = useToast();
    const [agentData, setAgentData] = useState({ name: '', role: 'Governance', model: 'llama3.1:8b' });
    const [isCreating, setIsCreating] = useState(false);

    // Real orchestration snapshot: active agents vs active tasks.
    const { data: orch, refetch: refetchOrch } = useApi(getOrchestratorDashboardData, [], true, 60000);
    const agentDist = useMemo(() => ([
        { name: 'Active Agents', value: Number(orch?.agents) || 0 },
        { name: 'Active Tasks', value: Number(orch?.active_tasks) || 0 },
    ]), [orch]);
    
    // CRITICAL: Handle Agent Creation
    const handleCreateAgent = useCallback(async (e) => {
        e.preventDefault();
        if (!agentData.name || !agentData.role || isCreating) return;
        
        setIsCreating(true);
        try {
            // The agent factory is intent-driven: the backend plans the agent from a
            // natural-language brief. Compose one from the form so the request matches
            // the real contract ({intent}) instead of 422-ing on {name, role, model}.
            const intent = `Create an agent named "${agentData.name}" responsible for ${agentData.role}, running on the ${agentData.model} model.`;
            const response = await createNewAIAgent({ intent });

            toast({
                title: 'Agent deployed',
                description: `${agentData.name} created with ID ${response.data?.agent_id || 'pending'}.`,
                variant: 'success',
            });
            setAgentData({ name: '', role: 'Governance', model: 'llama3.1:8b' });
            refetchOrch?.();
        } catch (error) {
            console.error("Agent creation failed:", error);
            toast({ title: 'Deployment Failed', description: error.response?.data?.detail || error.message, variant: 'destructive' });
        } finally {
            setIsCreating(false);
        }
    }, [agentData, isCreating, toast]);

    const styles = useMemo(() => ({
        grid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: tokens.spacing?.lg },
        card: { padding: tokens.spacing?.md, background: tokens.color?.['panel-700'], borderRadius: tokens.border?.radius?.card, minHeight: '300px' },
        formGroup: { marginBottom: tokens.spacing?.md },
        input: { width: '100%', padding: '10px', background: tokens.color?.['bg-input'], border: `1px solid ${tokens.color?.['border-600']}`, borderRadius: tokens.border?.radius?.input, color: tokens.color?.['text-100'], boxSizing: 'border-box' },
        submitButton: { padding: '10px 20px', background: tokens.color?.['accent-primary'], border: 'none', borderRadius: tokens.border?.radius?.button, color: tokens.color?.['bg-deep'], cursor: 'pointer', transition: 'all 0.2s ease', display: 'flex', alignItems: 'center', gap: tokens.spacing?.xs, justifyContent: 'center' },
    }), []);

    return (
        <div style={styles.grid}>
            {/* Agent Creation Form */}
            <div style={styles.card}>
                <h3 style={{ color: tokens.color?.['text-100'] }}>New Autonomous Agent Deployment</h3>
                <form onSubmit={handleCreateAgent}>
                    <div style={styles.formGroup}>
                        <label style={{ color: tokens.color?.['text-100'], display: 'block', marginBottom: '5px' }}>Agent Name</label>
                        <input 
                            type="text" 
                            style={styles.input} 
                            value={agentData.name}
                            onChange={(e) => setAgentData(prev => ({ ...prev, name: e.target.value }))}
                            placeholder="e.g., Policy Auditor 7.1"
                            required
                        />
                    </div>
                    <div style={styles.formGroup}>
                        <label style={{ color: tokens.color?.['text-100'], display: 'block', marginBottom: '5px' }}>Agent Role</label>
                        <select 
                            style={styles.input} 
                            value={agentData.role}
                            onChange={(e) => setAgentData(prev => ({ ...prev, role: e.target.value }))}
                            required
                        >
                            <option value="Governance">Policy Governance</option>
                            <option value="Remediation">Autonomous Healing</option>
                            <option value="Integration">Data Integration</option>
                            <option value="XAI">XAI Analyst</option>
                        </select>
                    </div>
                     <div style={styles.formGroup}>
                        <label style={{ color: tokens.color?.['text-100'], display: 'block', marginBottom: '5px' }}>Base LLM Model</label>
                        <select 
                            style={styles.input} 
                            value={agentData.model}
                            onChange={(e) => setAgentData(prev => ({ ...prev, model: e.target.value }))}
                            required
                        >
                            <option value="llama3.1:8b">Llama 3.1 8B (Default)</option>
                            <option value="qwen2.5-coder:7b">Qwen 2.5 Coder 7B</option>
                            <option value="mistral:7b-instruct">Mistral 7B Instruct</option>
                        </select>
                    </div>
                    <button 
                        type="submit" 
                        style={styles.submitButton} 
                        disabled={isCreating}
                        className="agent-deploy-hover"
                    >
                        {isCreating ? <Loader2 size={16} className="animate-spin" /> : <Zap size={16} />}
                        {isCreating ? 'Deploying Agent...' : 'Deploy New Agent'}
                    </button>
                </form>
            </div>

            {/* Agent Status Overview */}
            <div style={styles.card}>
                <h3 style={{ color: tokens.color?.['text-100'] }}>Active Agent Landscape</h3>
                <BarChartWidget data={agentDist} minHeight="250px" color={tokens.color?.['accent-primary']} />
                <p style={{ color: tokens.color?.['muted-500'], fontSize: tokens.typography?.small?.fontSize, marginTop: tokens.spacing?.md }}>
                    System health: {orch?.system_health || 'LIVE'} | Message bus: {orch?.message_bus_connected ? 'connected' : 'offline'}.
                </p>
                <button style={{ marginTop: tokens.spacing?.md, padding: '8px 15px', background: tokens.color?.['panel-800'], border: `1px solid ${tokens.color?.['border-600']}`, borderRadius: tokens.border?.radius?.button, color: tokens.color?.['text-100'], cursor: 'pointer' }}>
                    View Agent Logs
                </button>
            </div>
        </div>
    );
});
AgentFactoryModule.displayName = 'AgentFactoryModule';

// --- 10.2. Sub-Module: Autonomous Healing Governance ---
/**
 * Monitors policy failure and autonomous remediation attempts.
 */
const GovernanceModule = memo(() => {
    // CRITICAL API INTEGRATION 2: Fetch Autonomous Healing Log (Remediation History)
    const { 
        data: healingLog, 
        isLoading: isLogLoading, 
        error: logError 
    } = useApi(getAutonomousHealingLog, [], true, []);
    
    // CRITICAL API INTEGRATION 3: Fetch ServiceNow Health (Integration Health)
    const { 
        data: serviceNowHealth, 
        isLoading: isHealthLoading, 
        error: healthError 
    } = useApi(getServiceNowHealth, [], true, {});

    // Genuinely live series: no historical "healing rate" endpoint exists, so we build a
    // rolling window from the real psutil-backed agent-activity telemetry (polled every 3s).
    const healingSeries = useMetricSeries('agent_activity', { intervalMs: 3000, scale: 100 });

    // Real distribution of remediation outcomes from the healing trace log.
    const violationDist = useMemo(() => countBy(healingLog || [], (l) => l.status), [healingLog]);

    const styles = useMemo(() => ({
        grid: { display: 'grid', gridTemplateColumns: 'repeat(12, 1fr)', gap: tokens.spacing?.lg, marginBottom: tokens.spacing?.lg },
        logWidget: { gridColumn: 'span 7', minHeight: '400px', background: tokens.color?.['panel-800'], borderRadius: tokens.border?.radius?.card, padding: tokens.spacing?.md, overflowY: 'auto' },
        healthWidget: { gridColumn: 'span 5', minHeight: '400px' },
        logItem: (status) => ({
            padding: tokens.spacing?.xs,
            marginBottom: tokens.spacing?.xs,
            borderLeft: `3px solid ${status === 'RESOLVED' ? tokens.color?.success : (status === 'FAILED' ? tokens.color?.danger : tokens.color?.warning)}`,
            background: tokens.color?.['panel-700'],
            borderRadius: tokens.border?.radius?.input,
            color: tokens.color?.['text-100'],
            fontSize: tokens.typography?.small?.fontSize, // Added optional chaining
        }),
    }), []);

    return (
        <div style={styles.grid}>
            {/* ServiceNow Health Card */}
            <div style={{ gridColumn: 'span 3' }}>
                <DataCard 
                    title="ServiceNow Integration" 
                    value={serviceNowHealth?.status === 'UP' ? 'ONLINE' : 'DOWN'} 
                    unit="Status" 
                    color={serviceNowHealth?.status === 'UP' ? tokens.color?.success : tokens.color?.danger}
                >
                    <MessageSquare size={24} color={serviceNowHealth?.status === 'UP' ? tokens.color?.success : tokens.color?.danger} />
                </DataCard>
            </div>
             {/* Key Metrics */}
            <div style={{ gridColumn: 'span 3' }}>
                <DataCard 
                    title="Successful Auto-Fixes" 
                    value={serviceNowHealth?.successful_fixes || 'N/A'} 
                    unit="Count" 
                    color={tokens.color?.['accent-primary']}
                >
                    <CheckCircle size={24} color={tokens.color?.['accent-primary']} />
                </DataCard>
            </div>
             <div style={{ gridColumn: 'span 6' }}>
                <DataCard title="Live Autonomous Agent Activity" isChart minHeight="150px">
                    <AreaChartWidget data={healingSeries} minHeight="150px" color={tokens.color?.success} label="Rolling agent-activity telemetry (live)" />
                </DataCard>
            </div>

            {/* Autonomous Healing Log */}
            <div style={styles.logWidget}>
                <h3 style={{ color: tokens.color?.['text-100'], borderBottom: `1px solid ${tokens.color?.['border-600']}`, paddingBottom: tokens.spacing?.xs, marginBottom: tokens.spacing?.md }}>
                    Autonomous Healing Trace Log
                </h3>
                {isLogLoading && <p style={{textAlign: 'center'}}><Loader2 size={20} className="animate-spin" /> Loading healing log...</p>}
                {logError && <p style={{ color: tokens.color?.danger }}>Error loading log.</p>}

                {/* FIX: Ensure healingLog defaults to an empty array for mapping and slicing (Prevents TypeError: reading 'slice') */}
                {(healingLog || []).slice(0, 10).map((log, index) => (
                    <div key={index} style={styles.logItem(log.status)}>
                        <span style={{ color: tokens.color?.warning }}>[{log.timestamp}]</span> 
                        <span style={{ fontWeight: 'bold', marginLeft: tokens.spacing?.xs }}>{log.audit_id}</span> 
                        - Attempted fix: {log.action_taken} ({log.status})
                    </div>
                ))}
            </div>
            
            <div style={styles.healthWidget}>
                <DataCard title="Remediation Outcome Distribution" isChart minHeight="100%">
                    <PieChartWidget data={violationDist} minHeight="340px" />
                </DataCard>
            </div>
        </div>
    );
});
GovernanceModule.displayName = 'GovernanceModule';


// --- 10.3. Sub-Module: Telemetry ---
/**
 * Renders the Live Telemetry Feed (WebSocket) and System Health Checks.
 */
const TelemetryModule = memo(() => {
    const { toast } = useToast();
    
    // CRITICAL API INTEGRATION 4: Fetch Admin Dashboard/System Data
    const { 
        data: hritData, 
        isLoading: isHritLoading, 
        error: hritError 
    } = useApi(getHRITDashboardData, [], true, 60000); // CRITICAL FIX: Set polling to 60 seconds (60000ms)

    // CRITICAL: Handle System Reset
    const handleSystemReset = useCallback(async () => {
        if (!window.confirm("WARNING: Are you sure you want to trigger a hard data reset? This action is irreversible.")) return;
        
        try {
            await resetHRITData(); // CRITICAL FIX: Use the specific resetHRITData API function
            toast({ title: 'System Reset Initiated', description: 'Data purge and system re-initialization is starting.', variant: 'danger' });
        } catch (error) {
            toast({ title: 'Reset Failed', description: error.response?.data?.detail || error.message, variant: 'destructive' });
        }
    }, [toast]);
    
    const styles = useMemo(() => ({
        grid: { display: 'grid', gridTemplateColumns: 'repeat(12, 1fr)', gap: tokens.spacing?.lg, marginBottom: tokens.spacing?.lg },
        telemetryWidget: { gridColumn: 'span 12', minHeight: '500px' }, // Full width for the feed
        controlPanel: { gridColumn: 'span 12', padding: tokens.spacing?.md, background: tokens.color?.['panel-700'], borderRadius: tokens.border?.radius?.card, display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
    }), []);
    
    return (
        <div style={styles.grid}>
            {/* CRITICAL INTEGRATION 5: Live Telemetry Feed (WebSocket) */}
            <div style={styles.telemetryWidget}>
                <LiveTelemetryFeed />
            </div>

            {/* System Control Panel */}
            <div style={styles.controlPanel}>
                <div style={{ color: tokens.color?.['muted-500'], display: 'flex', alignItems: 'center', gap: tokens.spacing?.md }}>
                    <Cpu size={24} color={tokens.color?.['accent-primary']} />
                    <p style={{ margin: 0 }}>
                        System Uptime: **{hritData?.uptime || 'N/A'}** | Last Full Check: {hritData?.last_check || 'N/A'}
                    </p>
                </div>
                <button 
                    onClick={handleSystemReset} 
                    style={{ padding: '10px 20px', background: tokens.color?.danger, border: 'none', borderRadius: tokens.border?.radius?.button, color: tokens.color?.['text-100'], cursor: 'pointer' }}
                    className="hrit-reset-hover"
                >
                    <AlertTriangle size={16} style={{ marginRight: tokens.spacing?.xs }} />
                    Trigger Hard System Reset (DANGER)
                </button>
            </div>
        </div>
    );
});
TelemetryModule.displayName = 'TelemetryModule';


// --- MAIN HRIT PORTAL COMPONENT ---
export const HRITPortalComponent = memo(() => {
    const location = useLocation();
    const query = new URLSearchParams(location.search);
    // CRITICAL FIX: Get the module name from the URL, default to 'agent'
    const module = query.get('module') || 'agent'; 

    const getModuleComponent = (mod) => {
        switch (mod) {
            case 'agent':
                return <AgentFactoryModule />;
            case 'governance':
                return <GovernanceModule />;
            case 'health':
                return <TelemetryModule />;
            default:
                return (
                    <div style={{ textAlign: 'center', color: tokens.color?.danger, padding: tokens.spacing?.xl }}>
                        <AlertTriangle size={32} />
                        <h3 style={{ margin: tokens.spacing?.md }}>Module Not Found</h3>
                        <p>The requested HRIT portal module "{mod}" could not be loaded.</p>
                    </div>
                );
        }
    };

    const moduleTitleMap = {
        agent: 'AI Agent Factory & Deployment',
        governance: 'Autonomous Healing Governance',
        health: 'Live Telemetry & System Health',
    };
    
    const styles = useMemo(() => ({
        container: { minHeight: '100%', display: 'flex', flexDirection: 'column' },
        header: {
            color: tokens.color?.['text-100'],
            marginBottom: tokens.spacing?.lg,
            borderBottom: `1px solid ${tokens.color?.['border-600']}`,
            paddingBottom: tokens.spacing?.md,
        },
        title: {
            fontSize: tokens.typography?.h1?.fontSize, // Added optional chaining
            margin: 0,
            display: 'flex',
            alignItems: 'center',
            gap: tokens.spacing?.sm,
        },
    }), []);

    return (
        <div style={styles.container} className="portal-container">
            <div style={styles.header}>
                <h1 style={styles.title}>
                    <Cpu size={32} color={tokens.color?.['accent-primary']} />
                    HRIT Portal: {moduleTitleMap[module] || 'Unknown Module'}
                </h1>
            </div>
            
            {/* Render the dynamically selected module component */}
            {getModuleComponent(module)}
            
            <style>{`
                .agent-deploy-hover:hover {
                    box-shadow: 0 0 10px ${tokens.color?.['accent-primary']}77;
                    transform: translateY(-1px);
                }
                .hrit-reset-hover:hover {
                    background: ${tokens.color?.['danger-700']} !important;
                    box-shadow: 0 0 10px ${tokens.color?.danger} !important;
                    transform: translateY(-1px);
                }
            `}</style>
        </div>
    );
});

HRITPortalComponent.displayName = 'HRITPortalComponent';
export default HRITPortalComponent;