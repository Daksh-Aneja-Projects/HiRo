// /frontend/src/components/UnifiedCommandBar.js - FINAL PRODUCTION-READY REPLACEMENT
import React, { useState, useCallback, useMemo, memo } from 'react';
import { Zap, Loader2, Send, ShieldCheck } from 'lucide-react';
import { useCustomization } from '../contexts/CustomizationContext';
import { useAuth } from '../contexts/AuthContext';
import { useToast } from '../hooks/use-toast';
import { 
    runOrchestrationCommand, generateText, runSystemIntegrityCheck 
} from '../config/api'; 
import { theme as tokens } from '../theme';

const UnifiedCommandBar = memo(() => {
    const { userContext } = useAuth();
    const { toast } = useToast();
    const customizationContext = useCustomization() || {};
    const { setOrchestratorResultId, setOrchestratorPrompt } = customizationContext; // Assuming these setters exist
    
    const [prompt, setPrompt] = useState('');
    const [isLoading, setIsLoading] = useState(false);

    // CRITICAL CORE LOGIC: Route command based on content
    const handleCommand = useCallback(async () => {
        if (!prompt.trim() || isLoading) return;
        
        const normalizedPrompt = prompt.trim().toLowerCase();
        setIsLoading(true);
        
        try {
            if (normalizedPrompt.includes('system health') || normalizedPrompt.includes('check integrity')) {
                // Route 1: System Integrity Check (Admin/HRIT)
                toast({ title: "Command Initiated", description: "Running deep system integrity check...", variant: 'info' });
                const response = await runSystemIntegrityCheck('all'); 
                toast({ 
                    title: `Integrity Check: ${response.data.status}`, 
                    description: `Status: ${response.data.details}`, 
                    variant: response.data.status === 'OK' ? 'success' : 'warning' 
                });
                
            } else if (normalizedPrompt.includes('synthesize') || normalizedPrompt.includes('generate text')) {
                // Route 2: Simple Text Generation (Quick AI utility)
                const response = await generateText(prompt, 'You are a concise, helpful assistant.');
                toast({ title: "Text Generation Complete", description: response.data.text.substring(0, 80) + "...", variant: 'success' });

            } else {
                // Route 3: Full Orchestration Command (Requires async tracking)
                // This routes to the async process tracked by OrchestratorResultWidget
                const response = await runOrchestrationCommand(prompt, userContext);
                
                const resultId = response.data?.result_id || 'MOCK_ID_' + Date.now(); 
                
                // CRITICAL FIX: Set result ID to show the tracking widget (OrchestratorResultWidget)
                if (setOrchestratorResultId) {
                    setOrchestratorResultId(resultId);
                    setOrchestratorPrompt(prompt);
                } else {
                    toast({ title: "Orchestration Started", description: `Task ID: ${resultId} (Monitoring not available)`, variant: 'info' });
                }
            }
            
            setPrompt(''); // Clear input after command is sent
            
        } catch (error) {
            console.error("Unified Command failed:", error);
            toast({ 
                title: 'Command Execution Failed', 
                description: error.response?.data?.detail || error.message, 
                variant: 'destructive' 
            });
        } finally {
            setIsLoading(false);
        }
    }, [prompt, isLoading, userContext, toast, setOrchestratorResultId, setOrchestratorPrompt]);

    const styles = useMemo(() => ({
        container: {
            background: tokens.color?.['panel-800'],
            padding: tokens.spacing?.sm,
            borderRadius: tokens.border?.radius?.card,
            boxShadow: tokens.shadow?.hover,
            display: 'flex',
            gap: tokens.spacing?.sm,
            alignItems: 'center',
            width: '100%',
            maxWidth: '800px',
            margin: `${tokens.spacing?.lg} auto`, // Center it in the middle of the screen
        },
        input: {
            flexGrow: 1,
            padding: '10px 12px',
            border: 'none',
            background: tokens.color?.['panel-700'],
            color: tokens.color?.['text-100'],
            borderRadius: tokens.border?.radius?.input,
            outline: 'none',
        },
        button: {
            padding: '10px 15px',
            borderRadius: tokens.border?.radius?.button,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: tokens.spacing?.xs,
            border: 'none',
            background: tokens.color?.['accent-primary'],
            color: tokens.color?.['bg-deep'],
            transition: 'all 0.2s ease',
        }
    }), []);

    return (
        <div style={styles.container}>
            <Zap size={24} color={tokens.color?.['accent-primary']} />
            <input 
                style={styles.input}
                placeholder="Run orchestration command, check system health, or synthesize text..."
                value={prompt} 
                onChange={e => setPrompt(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleCommand()}
            />
            <button 
                onClick={handleCommand}
                style={styles.button}
                title="Execute Unified Command"
                disabled={isLoading} 
                className="command-bar-hover"
            >
                {isLoading ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
            </button>
            <style>{`.command-bar-hover:hover { box-shadow: 0 0 10px ${tokens.color?.['accent-primary']}77; transform: translateY(-1px); }`}</style>
        </div>
    );
});

UnifiedCommandBar.displayName = 'UnifiedCommandBar';
export default UnifiedCommandBar;