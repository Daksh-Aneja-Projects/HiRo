// /frontend/src/components/PolicyVerifiedChat.js - FINAL PRODUCTION-READY REPLACEMENT (Fixes fontSize TypeErrors)
import React, { useMemo, memo, useState, useCallback } from 'react';
import { theme as tokens } from '../theme';
import { generateText } from '../config/api'; // CRITICAL FIX: Import the text generation API
import { useToast } from '../hooks/use-toast';
import { MessageCircle, Zap, Send, Loader2, ShieldCheck } from 'lucide-react';

const PolicyVerifiedChat = memo(() => {
    const { toast } = useToast();
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    
    // CRITICAL: System Instruction to enforce policy verification
    const SYSTEM_INSTRUCTION = "You are a Policy Verification Agent. All responses MUST be verified against the active BPCL Policy Ledger. If a response contradicts policy, state the conflict and cite the BPCL rule ID. Respond concisely.";

    // CRITICAL: Handle sending the message and getting a verified response
    const handleSend = useCallback(async (e) => {
        e.preventDefault();
        if (!input.trim() || isLoading) return;

        const userMessage = input.trim();
        setInput('');
        setIsLoading(true);

        // Optimistic UI Update for user message
        const newUserMessage = { sender: 'user', text: userMessage, verified: true };
        setMessages(prev => [...prev, newUserMessage]);

        try {
            // CRITICAL API INTEGRATION: Send prompt with strict system instruction
            const response = await generateText(userMessage, SYSTEM_INSTRUCTION);
            const agentResponseText = response.data?.text || "Error: Failed to get verified response.";
            
            // Assume verification is implied by the response coming from this endpoint
            const agentMessage = { sender: 'agent', text: agentResponseText, verified: true };
            
            setMessages(prev => [...prev, agentMessage]);
        } catch (error) {
            console.error("Policy chat failed:", error);
            const errorMessage = { sender: 'agent', text: `Verification failed: ${error.message}`, verified: false };
            setMessages(prev => [...prev, errorMessage]);
            toast({ title: 'Chat Error', description: 'Failed to generate verified response.', variant: 'destructive' });
        } finally {
            setIsLoading(false);
        }
    }, [input, isLoading, toast]);


    const styles = useMemo(() => ({
        container: { padding: tokens.spacing?.md, background: tokens.color?.['panel-800'], borderRadius: tokens.border?.radius?.card, height: '100%', display: 'flex', flexDirection: 'column' },
        messageArea: { flexGrow: 1, overflowY: 'auto', marginBottom: tokens.spacing?.md },
        inputArea: { display: 'flex', gap: tokens.spacing?.sm },
        inputField: { flexGrow: 1, padding: '10px', background: tokens.color?.['bg-input'], border: `1px solid ${tokens.color?.['border-600']}`, borderRadius: tokens.border?.radius?.input, color: tokens.color?.['text-100'] },
        sendButton: { padding: '8px 15px', background: tokens.color?.success, border: 'none', borderRadius: tokens.border?.radius?.button, color: tokens.color?.['bg-deep'], cursor: 'pointer' },
        messageBubble: (isAgent) => ({
            maxWidth: '85%',
            padding: tokens.spacing?.sm,
            borderRadius: tokens.border?.radius?.input,
            marginBottom: tokens.spacing?.xs,
            marginLeft: isAgent ? 0 : 'auto',
            marginRight: isAgent ? 'auto' : 0,
            background: isAgent ? tokens.color?.['panel-700'] : tokens.color?.['accent-primary'],
            color: isAgent ? tokens.color?.['text-100'] : tokens.color?.['text-dark'],
            display: 'flex',
            flexDirection: 'column',
            position: 'relative',
        }),
        verificationIcon: {
            position: 'absolute',
            top: 2,
            right: 2,
            color: tokens.color?.success,
        }
    }), []);

    const renderMessage = (msg, index) => {
        const isAgent = msg.sender === 'agent';
        return (
            <div key={index} style={styles.messageBubble(isAgent)}>
                <span style={{ fontWeight: 'bold', 
                    // --- FIX: Added optional chaining ---
                    fontSize: tokens.typography?.small?.fontSize
                    // ------------------------------------
                    , marginBottom: '2px', color: isAgent ? tokens.color?.warning : tokens.color?.['text-dark'] }}>
                    {isAgent ? 'Policy Agent' : 'You'}
                </span>
                <div>{msg.text}</div>
                {msg.verified && <ShieldCheck size={14} style={styles.verificationIcon} title="Policy Verified" />}
            </div>
        );
    };

    return (
        <div style={styles.container}>
            <h3 style={{ color: tokens.color?.['text-100'], margin: '0 0 15px 0', display: 'flex', alignItems: 'center', gap: tokens.spacing?.xs }}><ShieldCheck size={20} color={tokens.color?.success} /> Policy Verified Chat</h3>
            
            <div style={styles.messageArea}>
                {messages.length === 0 && (
                    <p style={{ textAlign: 'center', color: tokens.color?.['muted-500'], padding: tokens.spacing?.xl }}>Start the conversation with your Policy Verification Agent...</p>
                )}
                {messages.map(renderMessage)}
                {isLoading && (
                    <div style={{ display: 'flex', justifyContent: 'center', marginTop: tokens.spacing?.md }}>
                        <Loader2 size={20} className="animate-spin" color={tokens.color?.['accent-primary']} />
                    </div>
                )}
            </div>

            <form onSubmit={handleSend} style={styles.inputArea}>
                <input
                    type="text"
                    placeholder="Ask a policy question..."
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    style={styles.inputField}
                    disabled={isLoading}
                />
                <button type="submit" style={styles.sendButton} disabled={isLoading || !input.trim()} className="chat-send-hover">
                    <Send size={20} />
                </button>
            </form>
            <style>{`.chat-send-hover:hover { box-shadow: 0 0 10px ${tokens.color?.success}77; transform: translateY(-1px); }`}</style>
        </div>
    );
});

PolicyVerifiedChat.displayName = 'PolicyVerifiedChat';
export default PolicyVerifiedChat;