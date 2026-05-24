// /frontend/src/components/BPCLGenerator.js - FINAL PRODUCTION-READY REPLACEMENT (Fixes fontSize TypeErrors)
import React, { useMemo, memo, useState, useCallback, useRef } from 'react';
import { theme as tokens } from '../theme';
import { streamAgentConfig } from '../config/api'; // CRITICAL FIX: Import the streaming API function
import { useToast } from '../hooks/use-toast';
import { Zap, Loader2, Save, Code } from 'lucide-react';
import CommandResultModal from './CommandResultModal'; // Used for final display

const BPCLGenerator = memo(() => {
    const { toast } = useToast();
    const [prompt, setPrompt] = useState('Write BPCL code to enforce that no employee can take more than 5 days of PTO consecutively.');
    const [output, setOutput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [finalConfig, setFinalConfig] = useState(null); // The final structured BPCL code
    const eventSourceRef = useRef(null);

    // CRITICAL: Handle BPCL Streaming Command
    const handleGenerate = useCallback(async (e) => {
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
        let fullConfigBuffer = '';

        const onChunk = (chunk) => {
            // Assume the backend sends JSON objects per chunk
            try {
                const data = JSON.parse(chunk);
                const content = data.content || '';
                
                // If it contains a final BPCL object, store it
                if (data.final_bpcl) {
                    fullConfigBuffer = data.final_bpcl;
                    setFinalConfig(fullConfigBuffer);
                }
                
                // Append stream content to output
                setOutput(prev => prev + content);
            } catch (e) {
                // Fallback: If not JSON, assume raw text stream
                setOutput(prev => prev + chunk);
            }
        };

        const onComplete = () => {
            setIsLoading(false);
            if (!fullConfigBuffer) {
                // If the stream completed but no final config was marked, use the whole output
                setFinalConfig(output.trim()); 
            }
            toast({ title: 'BPCL Generation Complete', description: 'Agent finished streaming the constraint language.', variant: 'success' });
        };

        const onError = (error) => {
            setIsLoading(false);
            setOutput(prev => prev + `\n\n--- STREAM ERROR: ${error.message || 'Connection failed'} ---`);
            toast({ title: 'Stream Error', description: 'BPCL generation stream failed.', variant: 'destructive' });
        };

        // 2. Start the streaming process
        try {
            // CRITICAL API INTEGRATION: Use the streaming function
            eventSourceRef.current = streamAgentConfig(prompt, onChunk, onComplete, onError);
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
        grid: { display: 'grid', gridTemplateColumns: 'repeat(12, 1fr)', gap: tokens.spacing?.lg, height: '100%' },
        formCard: { gridColumn: 'span 4', padding: tokens.spacing?.md, background: tokens.color?.['panel-700'], borderRadius: tokens.border?.radius?.card, display: 'flex', flexDirection: 'column' },
        outputCard: { gridColumn: 'span 8', padding: tokens.spacing?.md, background: tokens.color?.['panel-700'], borderRadius: tokens.border?.radius?.card, minHeight: '500px', display: 'flex', flexDirection: 'column' },
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
    }), []);

    return (
        <div style={styles.grid}>
            {/* Generation Form */}
            <div style={styles.formCard}>
                <h3 style={{ color: tokens.color?.['text-100'], margin: 0 }}>BPCL Code Generator</h3>
                <p style={{ color: tokens.color?.['muted-500'], 
                    // --- FIX: Added optional chaining ---
                    fontSize: tokens.typography?.small?.fontSize, 
                    // ------------------------------------
                    marginBottom: tokens.spacing?.md }}>
                    Describe the policy constraint you need to encode.
                </p>
                <form onSubmit={handleGenerate} style={{ flexGrow: 1, display: 'flex', flexDirection: 'column' }}>
                    <textarea 
                        style={styles.textarea} 
                        value={prompt}
                        onChange={(e) => setPrompt(e.target.value)}
                        placeholder="Enter policy constraint here..."
                        disabled={isLoading}
                        required
                    />
                    <button 
                        type="submit" 
                        style={styles.button(tokens.color?.warning)} 
                        disabled={isLoading}
                        className="bpcl-generate-hover"
                    >
                        {isLoading ? <Loader2 size={16} className="animate-spin" /> : <Zap size={16} />}
                        {isLoading ? 'Streaming Code...' : 'Generate BPCL (Stream)'}
                    </button>
                </form>
                
                {finalConfig && (
                    <button 
                        onClick={() => setFinalConfig(finalConfig)} // Show modal (This will likely re-show the modal with the same config, which is fine)
                        style={{...styles.button(tokens.color?.success), marginTop: tokens.spacing?.md, color: tokens.color?.['bg-deep']}}
                        className="view-bpcl-config-hover"
                    >
                        <Code size={16} /> View Final Code
                    </button>
                )}
            </div>

            {/* Streaming Output */}
            <div style={styles.outputCard}>
                <h3 style={{ color: tokens.color?.['text-100'], margin: '0 0 10px 0', display: 'flex', alignItems: 'center', gap: tokens.spacing?.xs }}><Code size={20} /> BPCL Stream Output</h3>
                <pre style={styles.outputPre}>
                    {output || (isLoading ? 'Waiting for agent to respond...' : 'BPCL stream output will appear here.')}
                    {isLoading && <Loader2 size={16} className="animate-spin" style={{ marginLeft: tokens.spacing?.sm }} />}
                </pre>
            </div>
            
            {/* Command Result Modal (Used for viewing the final BPCL) */}
            {finalConfig && (
                <CommandResultModal 
                    title="Final BPCL Code"
                    content={finalConfig}
                    traceType="BPCL"
                    onClose={() => setFinalConfig(null)}
                />
            )}
            
            <style>{`
                .bpcl-generate-hover:hover { box-shadow: 0 0 10px ${tokens.color?.warning}77; transform: translateY(-1px); }
                .view-bpcl-config-hover:hover { box-shadow: 0 0 10px ${tokens.color?.success}77; transform: translateY(-1px); }
            `}</style>
        </div>
    );
});

BPCLGenerator.displayName = 'BPCLGenerator';
export default BPCLGenerator;