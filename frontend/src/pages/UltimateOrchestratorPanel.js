// /frontend/src/pages/UltimateOrchestratorPanel.js - FINAL PRODUCTION-READY REPLACEMENT
import React, { useMemo, memo, useState, useCallback, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { theme as tokens } from '../theme';

// CRITICAL API IMPORTS
import { 
    executeRLFFCommand, streamSelfCorrectingAgent, 
    triggerHardPurge, resetAllData, getAdminDashboardData 
} from '../config/api'; 
import { useToast } from '../hooks/use-toast';

// UI COMPONENTS
import DataCard from '../components/DataCard';
import CommandResultModal from '../components/CommandResultModal';
import ChartPlaceholder from '../components/ChartPlaceholder';
import { 
    Settings, Zap, AlertTriangle, Cpu, 
    Trash2, Loader2, ArrowRight 
} from 'lucide-react';


// --- 12.1. Sub-Module: RLFF & AI Command ---
/**
 * Renders the RLFF Command interface with streaming output.
 */
const CommandModule = memo(() => {
    const { toast } = useToast();
    const [prompt, setPrompt] = useState('Synthesize a new BPCL rule for Q4 sales bonus policy.');
    const [output, setOutput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [finalConfig, setFinalConfig] = useState(null);
    const eventSourceRef = useRef(null);

    // CRITICAL: Handle RLFF Streaming Command
    const handleRLFFCommand = useCallback(async (e) => {
        e.preventDefault();
        if (!prompt.trim() || isLoading) return;

        // Cleanup any previous connection
        if (eventSourceRef.current) {
            eventSourceRef.current.close();
        }
        
        setIsLoading(true);
        setOutput('');
        setFinalConfig(null);

        // 1. Define stream handlers
        const onChunk = (chunk) => {
            // Assume the backend sends raw text or JSON objects with a 'content' field
            try {
                const data = JSON.parse(chunk);
                // Check for final BPCL config in the stream
                if (data.final_bpcl) {
                    setFinalConfig(data.final_bpcl);
                }
                setOutput(prev => prev + (data.content || ''));
            } catch (e) {
                // If not JSON, assume it's raw text chunk
                setOutput(prev => prev + chunk);
            }
        };

        const onComplete = () => {
            setIsLoading(false);
            toast({ title: 'Stream Complete', description: 'AI agent finalized the configuration.', variant: 'success' });
        };

        const onError = (error) => {
            setIsLoading(false);
            setOutput(prev => prev + `\n\n--- STREAM ERROR: ${error.message || 'Connection failed'} ---`);
            toast({ title: 'Stream Error', description: 'Agent command stream failed.', variant: 'destructive' });
        };

        // 2. Start the streaming process
        try {
            // CRITICAL API INTEGRATION 1: Use the streaming function
            eventSourceRef.current = streamSelfCorrectingAgent(prompt, onChunk, onComplete, onError);
        } catch (error) {
            onError(error);
        }

    }, [prompt, isLoading, toast]);

    // Cleanup on unmount
    React.useEffect(() => {
        return () => {
            if (eventSourceRef.current) {
                eventSourceRef.current.close();
            }
        };
    }, []);

    const styles = useMemo(() => ({
        grid: { display: 'grid', gridTemplateColumns: '1fr 2fr', gap: tokens.spacing?.lg, marginBottom: tokens.spacing?.lg },
        formCard: { gridColumn: 'span 1', padding: tokens.spacing?.md, background: tokens.color?.['panel-700'], borderRadius: tokens.border?.radius?.card },
        outputCard: { gridColumn: 'span 2', padding: tokens.spacing?.md, background: tokens.color?.['panel-700'], borderRadius: tokens.border?.radius?.card },
        outputPre: { whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontFamily: 'monospace', fontSize: tokens.typography?.small?.fontSize, color: tokens.color?.['text-100'], maxHeight: '550px', overflowY: 'auto', background: tokens.color?.['panel-800'], padding: tokens.spacing?.sm, borderRadius: tokens.border?.radius?.input }, // Added optional chaining
        input: { width: '100%', padding: '10px', background: tokens.color?.['bg-input'], border: `1px solid ${tokens.color?.['border-600']}`, borderRadius: tokens.border?.radius?.input, color: tokens.color?.['text-100'], boxSizing: 'border-box', minHeight: '120px' },
        submitButton: { padding: '10px 20px', background: tokens.color?.['accent-primary'], border: 'none', borderRadius: tokens.border?.radius?.button, color: tokens.color?.['bg-deep'], cursor: 'pointer', transition: 'all 0.2s ease', display: 'flex', alignItems: 'center', gap: tokens.spacing?.xs, justifyContent: 'center', marginTop: tokens.spacing?.md },
    }), []);

    return (
        <div style={styles.grid}>
            {/* Command Input */}
            <div style={styles.formCard}>
                <h3 style={{ color: tokens.color?.['text-100'], margin: 0 }}>RLFF Agent Command</h3>
                <p style={{ color: tokens.color?.['muted-500'], fontSize: tokens.typography?.small?.fontSize, marginBottom: tokens.spacing?.md }}> 
                    Issue a natural language command for the self-correcting agent.
                </p>
                <form onSubmit={handleRLFFCommand}>
                    <textarea 
                        style={styles.input} 
                        value={prompt}
                        onChange={(e) => setPrompt(e.target.value)}
                        placeholder="Enter command here..."
                        required
                    />
                    <button 
                        type="submit" 
                        style={styles.submitButton} 
                        disabled={isLoading}
                        className="rlff-command-hover"
                    >
                        {isLoading ? <Loader2 size={16} className="animate-spin" /> : <Zap size={16} />}
                        {isLoading ? 'Streaming Output...' : 'Execute Streamed Command'}
                    </button>
                </form>

                {/* Final Config Button */}
                {finalConfig && (
                    <button 
                        onClick={() => setFinalConfig(finalConfig)} // Set finalConfig state to show modal
                        style={{ ...styles.submitButton, background: tokens.color?.success, marginTop: tokens.spacing?.md }}
                        className="view-config-hover"
                    >
                        <ArrowRight size={16} /> View Final BPCL Config
                    </button>
                )}
            </div>

            {/* Streaming Output */}
            <div style={styles.outputCard}>
                <h3 style={{ color: tokens.color?.['text-100'], margin: '0 0 10px 0' }}>Agent Response Stream</h3>
                <pre style={styles.outputPre}>
                    {output || (isLoading ? 'Waiting for agent to respond...' : 'Output will appear here.')}
                    {isLoading && <Loader2 size={16} className="animate-spin" style={{ marginLeft: tokens.spacing?.sm }} />}
                </pre>
            </div>
            
            {/* Command Result Modal (Used for viewing the final BPCL) */}
            {finalConfig && (
                <CommandResultModal 
                    title="Final BPCL Configuration"
                    content={finalConfig}
                    traceType="BPCL"
                    onClose={() => setFinalConfig(null)}
                />
            )}
        </div>
    );
});
CommandModule.displayName = 'CommandModule';


// --- 12.2. Sub-Module: System Governor (Danger Zone) ---
/**
 * Renders the high-privilege system controls.
 */
const DangerModule = memo(() => {
    const { toast } = useToast();
    const [isPurging, setIsPurging] = useState(false);
    const [isExecuting, setIsExecuting] = useState(false);
    
    // CRITICAL: Handle Hard Data Purge (Using the API function we stabilized earlier)
    const handleHardPurge = useCallback(async () => {
        if (!window.confirm("!! ABSOLUTE PURGE WARNING !! This will delete ALL transactional, policy, and user data. DO NOT PROCEED unless authorized by the CEO.")) return;
        
        setIsPurging(true);
        try {
            // CRITICAL API INTEGRATION 2: Call the specific resetAllData API function
            await resetAllData(); 
            
            toast({ title: 'Absolute Purge Initiated', description: 'System-wide data deletion is starting. The kernel will reboot.', variant: 'danger' });
        } catch (error) {
            toast({ title: 'Purge Failed', description: error.response?.data?.detail || error.message, variant: 'destructive' });
        } finally {
            setIsPurging(false);
        }
    }, [toast]);
    
    // CRITICAL: Handle System Governor Command (e.g., Freeze All Agents)
    const handleGovernorCommand = useCallback(async (command) => {
        if (!window.confirm(`CONFIRM: Execute System Governor Command: "${command}"? This action is critical.`)) return;
        
        setIsExecuting(true);
        try {
            // CRITICAL API INTEGRATION 3: Use the generic RLFF executor for high-level commands
            await executeRLFFCommand(command); 
            
            toast({ title: 'Governor Command Sent', description: `Command "${command}" executed. Monitor telemetry.`, variant: 'warning' });
        } catch (error) {
            toast({ title: 'Command Failed', description: error.response?.data?.detail || error.message, variant: 'destructive' });
        } finally {
            setIsExecuting(false);
        }
    }, [toast]);


    const styles = useMemo(() => ({
        grid: { display: 'grid', gridTemplateColumns: 'repeat(12, 1fr)', gap: tokens.spacing?.lg, marginBottom: tokens.spacing?.lg },
        card: { gridColumn: 'span 6', padding: tokens.spacing?.md, background: tokens.color?.['panel-800'], borderRadius: tokens.border?.radius?.card, border: `1px solid ${tokens.color?.danger}` },
        commandButton: { padding: '10px 20px', background: tokens.color?.danger, border: 'none', borderRadius: tokens.border?.radius?.button, color: tokens.color?.['text-100'], cursor: 'pointer', transition: 'all 0.2s ease', display: 'flex', alignItems: 'center', gap: tokens.spacing?.xs, justifyContent: 'center' },
    }), []);

    return (
        <div style={styles.grid}>
            {/* System Governor Controls */}
            <div style={styles.card}>
                <h3 style={{ color: tokens.color?.danger, margin: 0, display: 'flex', alignItems: 'center', gap: tokens.spacing?.xs }}><Cpu size={20} /> System Governor (AI Kernel)</h3>
                <p style={{ color: tokens.color?.warning, fontSize: tokens.typography?.small?.fontSize, marginBottom: tokens.spacing?.md }}> 
                    Execute extreme, high-impact commands on the core AI Orchestrator. USE WITH CAUTION.
                </p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: tokens.spacing?.md }}>
                    <button 
                        onClick={() => handleGovernorCommand('FREEZE ALL AGENTS')} 
                        disabled={isExecuting}
                        style={{ ...styles.commandButton, background: tokens.color?.warning }}
                        className="governor-freeze-hover"
                    >
                        {isExecuting ? <Loader2 size={16} className="animate-spin" /> : <Settings size={16} />}
                        {isExecuting ? 'Executing...' : 'FREEZE ALL AGENTS'}
                    </button>
                    <button 
                        onClick={() => handleGovernorCommand('RESET GOVERNOR STATE')} 
                        disabled={isExecuting}
                        style={styles.commandButton}
                        className="governor-reset-hover"
                    >
                        {isExecuting ? <Loader2 size={16} className="animate-spin" /> : <Settings size={16} />}
                        {isExecuting ? 'Executing...' : 'RESET GOVERNOR STATE'}
                    </button>
                </div>
            </div>

            {/* Hard Data Purge */}
            <div style={styles.card}>
                <h3 style={{ color: tokens.color?.danger, margin: 0, display: 'flex', alignItems: 'center', gap: tokens.spacing?.xs }}><AlertTriangle size={20} /> Absolute Data Purge</h3>
                <p style={{ color: tokens.color?.warning, fontSize: tokens.typography?.small?.fontSize, marginBottom: tokens.spacing?.md }}> 
                    Irreversible operation. Deletes all data, resets ledgers, and purges system state. Requires CEO-level authorization.
                </p>
                <button 
                    onClick={handleHardPurge} 
                    disabled={isPurging}
                    style={{ ...styles.commandButton, marginTop: tokens.spacing?.xl }}
                    className="absolute-purge-hover"
                >
                    <Trash2 size={16} />
                    {isPurging ? 'Purging All Data...' : 'HARD DATA PURGE'}
                </button>
            </div>
            
            <div style={{ gridColumn: 'span 12' }}>
                <ChartPlaceholder label="Governor Action Trace Log" minHeight="250px" />
            </div>
        </div>
    );
});
DangerModule.displayName = 'DangerModule';


// --- MAIN ORCHESTRATOR PANEL COMPONENT ---
export const UltimateOrchestratorPanelComponent = memo(() => {
    const location = useLocation();
    const query = new URLSearchParams(location.search);
    // CRITICAL FIX: Get the module name from the URL, default to 'command'
    const module = query.get('module') || 'command'; 

    const getModuleComponent = (mod) => {
        switch (mod) {
            case 'command':
                return <CommandModule />;
            case 'danger':
                return <DangerModule />;
            default:
                return (
                    <div style={{ textAlign: 'center', color: tokens.color?.danger, padding: tokens.spacing?.xl }}>
                        <AlertTriangle size={32} />
                        <h3 style={{ margin: tokens.spacing?.md }}>Module Not Found</h3>
                        <p>The requested Orchestrator panel module "{mod}" could not be loaded.</p>
                    </div>
                );
        }
    };

    const moduleTitleMap = {
        command: 'RLFF & Self-Correction Command Center',
        danger: 'System Governor & Danger Zone',
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
            fontSize: tokens.typography?.h1?.fontSize, // FIX: Safe access
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
                    <Settings size={32} color={tokens.color?.warning} />
                    Ultimate Orchestrator: {moduleTitleMap[module] || 'Unknown Module'}
                </h1>
            </div>
            
            {/* Render the dynamically selected module component */}
            {getModuleComponent(module)}
            
            <style>{`
                .rlff-command-hover:hover {
                    box-shadow: 0 0 10px ${tokens.color?.['accent-primary']}77;
                    transform: translateY(-1px);
                }
                .view-config-hover:hover {
                    box-shadow: 0 0 10px ${tokens.color?.success}77;
                    transform: translateY(-1px);
                }
                .governor-freeze-hover:hover {
                    box-shadow: 0 0 10px ${tokens.color?.warning}99;
                    transform: translateY(-1px);
                }
                .governor-reset-hover:hover {
                    box-shadow: 0 0 10px ${tokens.color?.danger}77;
                    transform: translateY(-1px);
                }
                .absolute-purge-hover:hover {
                    box-shadow: 0 0 20px ${tokens.color?.danger};
                    background: ${tokens.color?.['danger-700']} !important;
                    transform: translateY(-2px);
                }
            `}</style>
        </div>
    );
});

UltimateOrchestratorPanelComponent.displayName = 'UltimateOrchestratorPanelComponent';
export default UltimateOrchestratorPanelComponent;