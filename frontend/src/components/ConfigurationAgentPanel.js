// /frontend/src/components/ConfigurationAgentPanel.js - FINAL PRODUCTION-READY REPLACEMENT (Fixes fontSize TypeErrors)
import React, { useMemo, memo, useState, useCallback, useRef } from 'react';
import { theme as tokens } from '../theme';
import { streamAgentConfig, getAiModels, setAIProvider } from '../config/api'; // CRITICAL FIX: Import stabilized API functions
import { useApi } from '../hooks/useApi';
import { useToast } from '../hooks/use-toast';
import { Zap, Loader2, Settings, Code, MessageCircle } from 'lucide-react';

const ConfigurationAgentPanel = memo(() => {
    const { toast } = useToast();
    const [prompt, setPrompt] = useState('Tune the HRBP agent to prioritize cost-of-living adjustments.');
    const [output, setOutput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [currentProvider, setCurrentProvider] = useState('Gemini-Flash');
    const eventSourceRef = useRef(null);
    
    // CRITICAL API INTEGRATION 1: Fetch Available AI Models
    const { data: models, isLoading: isModelsLoading } = useApi(getAiModels, [], true, []);

    // CRITICAL: Handle Agent Configuration Streaming
    const handleConfigure = useCallback(async (e) => {
        e.preventDefault();
        if (!prompt.trim() || isLoading) return;

        if (eventSourceRef.current) {
            eventSourceRef.current.close();
        }
        
        setIsLoading(true);
        setOutput('');

        const onChunk = (chunk) => {
             // Assuming the stream sends configuration details/BPCL chunks
            try {
                const data = JSON.parse(chunk);
                setOutput(prev => prev + (data.content || ''));
            } catch (e) {
                setOutput(prev => prev + chunk);
            }
        };

        const onComplete = () => {
            setIsLoading(false);
            toast({ title: 'Agent Config Complete', description: 'Agent configuration stream finalized.', variant: 'success' });
        };

        const onError = (error) => {
            setIsLoading(false);
            setOutput(prev => prev + `\n\n--- STREAM ERROR: ${error.message || 'Connection failed'} ---`);
            toast({ title: 'Stream Error', description: 'Configuration stream failed.', variant: 'destructive' });
        };

        try {
            // CRITICAL API INTEGRATION 2: Use the streaming function
            eventSourceRef.current = streamAgentConfig(prompt, onChunk, onComplete, onError);
        } catch (error) {
            onError(error);
        }

    }, [prompt, isLoading, toast]);
    
    // CRITICAL: Handle AI Provider Switch
    const handleProviderSwitch = useCallback(async (provider) => {
        if (!provider || provider === currentProvider) return;
        
        if (!window.confirm(`Confirm switching the primary AI provider to ${provider}? This affects all agents.`)) return;

        try {
            // CRITICAL API INTEGRATION 3: Switch AI Provider
            await setAIProvider(provider);
            setCurrentProvider(provider);
            toast({ title: 'Provider Switched', description: `Primary AI provider is now set to ${provider}.`, variant: 'warning' });
        } catch (error) {
            toast({ title: 'Switch Failed', description: error.response?.data?.detail || error.message, variant: 'destructive' });
        }
    }, [currentProvider, toast]);


    React.useEffect(() => {
        return () => {
            if (eventSourceRef.current) {
                eventSourceRef.current.close();
            }
        };
    }, []);


    const styles = useMemo(() => ({
        grid: { display: 'grid', gridTemplateColumns: 'repeat(12, 1fr)', gap: tokens.spacing?.lg, minHeight: '500px' },
        formCard: { gridColumn: 'span 5', padding: tokens.spacing?.md, background: tokens.color?.['panel-700'], borderRadius: tokens.border?.radius?.card, display: 'flex', flexDirection: 'column' },
        outputCard: { gridColumn: 'span 7', padding: tokens.spacing?.md, background: tokens.color?.['panel-700'], borderRadius: tokens.border?.radius?.card, display: 'flex', flexDirection: 'column' },
        textarea: { width: '100%', padding: '10px', background: tokens.color?.['bg-input'], border: `1px solid ${tokens.color?.['border-600']}`, borderRadius: tokens.border?.radius?.input, color: tokens.color?.['text-100'], boxSizing: 'border-box', minHeight: '120px', resize: 'vertical', marginBottom: tokens.spacing?.md },
        outputPre: { 
            flexGrow: 1, 
            background: tokens.color?.['panel-800'], 
            padding: tokens.spacing?.sm, 
            borderRadius: tokens.border?.radius?.input, 
            overflow: 'auto', 
            whiteSpace: 'pre-wrap', 
            fontFamily: 'monospace', 
            // --- FIX: Added optional chaining ---
            fontSize: tokens.typography?.small?.fontSize, 
            // ------------------------------------
            color: tokens.color?.['text-100'], 
            marginTop: tokens.spacing?.md 
        },
        button: (bgColor) => ({ padding: '10px 20px', background: bgColor, border: 'none', borderRadius: tokens.border?.radius?.button, color: tokens.color?.['bg-deep'], cursor: 'pointer', transition: 'all 0.2s ease', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: tokens.spacing?.xs, width: '100%' }),
        select: { padding: '8px', background: tokens.color?.['bg-input'], border: `1px solid ${tokens.color?.['border-600']}`, borderRadius: tokens.border?.radius?.input, color: tokens.color?.['text-100'], flexGrow: 1 }
    }), []);

    return (
        <div style={styles.grid}>
            {/* Configuration Form */}
            <div style={styles.formCard}>
                <h3 style={{ color: tokens.color?.['text-100'], margin: 0 }}>Live Agent Configuration</h3>
                <p style={{ color: tokens.color?.['muted-500'], 
                    // --- FIX: Added optional chaining ---
                    fontSize: tokens.typography?.small?.fontSize, 
                    // ------------------------------------
                    marginBottom: tokens.spacing?.md }}>
                    Issue a prompt to stream dynamic configuration changes or BPCL rules.
                </p>
                <form onSubmit={handleConfigure} style={{ flexGrow: 1, display: 'flex', flexDirection: 'column' }}>
                    <textarea 
                        style={styles.textarea} 
                        value={prompt}
                        onChange={(e) => setPrompt(e.target.value)}
                        placeholder="Enter configuration goal..."
                        disabled={isLoading}
                        required
                    />
                    <button 
                        type="submit" 
                        style={styles.button(tokens.color?.['accent-secondary'])} 
                        disabled={isLoading}
                        className="config-stream-hover"
                    >
                        {isLoading ? <Loader2 size={16} className="animate-spin" /> : <Zap size={16} />}
                        {isLoading ? 'Streaming Config...' : 'Stream Configuration'}
                    </button>
                </form>
                
                <div style={{ marginTop: tokens.spacing?.lg, borderTop: `1px solid ${tokens.color?.['border-600']}`, paddingTop: tokens.spacing?.md }}>
                    <h4 style={{ color: tokens.color?.['text-100'], margin: 0 }}>AI Provider Switch</h4>
                    <div style={{ display: 'flex', gap: tokens.spacing?.sm, marginTop: tokens.spacing?.sm }}>
                        <select 
                            style={styles.select} 
                            value={currentProvider} 
                            onChange={(e) => setCurrentProvider(e.target.value)}
                            disabled={isModelsLoading}
                        >
                            {isModelsLoading && <option>Loading Models...</option>}
                            {models?.map(model => (
                                <option key={model.name} value={model.name}>{model.label}</option>
                            ))}
                        </select>
                         <button 
                            onClick={() => handleProviderSwitch(currentProvider)} 
                            style={{ ...styles.button(tokens.color?.warning), width: 'auto', color: tokens.color?.['bg-deep'], padding: '8px 15px' }}
                            className="provider-switch-hover"
                        >
                            <Settings size={16} /> Switch
                        </button>
                    </div>
                </div>
            </div>

            {/* Streaming Output */}
            <div style={styles.outputCard}>
                <h3 style={{ color: tokens.color?.['text-100'], margin: '0 0 10px 0', display: 'flex', alignItems: 'center', gap: tokens.spacing?.xs }}><Code size={20} /> Configuration Output Stream</h3>
                <pre style={styles.outputPre}>
                    {output || (isLoading ? 'Waiting for agent to process configuration...' : 'Configuration stream output will appear here.')}
                    {isLoading && <Loader2 size={16} className="animate-spin" style={{ marginLeft: tokens.spacing?.sm }} />}
                </pre>
            </div>
            
            <style>{`
                .config-stream-hover:hover { box-shadow: 0 0 10px ${tokens.color?.['accent-secondary']}77; transform: translateY(-1px); }
                .provider-switch-hover:hover { box-shadow: 0 0 10px ${tokens.color?.warning}77; transform: translateY(-1px); }
            `}</style>
        </div>
    );
});

ConfigurationAgentPanel.displayName = 'ConfigurationAgentPanel';
export default ConfigurationAgentPanel;