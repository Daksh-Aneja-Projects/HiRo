// src/components/DigitalTwinChat.js (PRODUCTION READY - FINAL STABILIZATION)
import React, { useState, useEffect, useCallback, useMemo } from 'react'; 
import { MessageSquare, Send, Bot, User, Clock, Check, X, Minimize2, Maximize2 } from 'lucide-react'; // Added Minimize/Maximize
import { theme as tokens } from '../theme';
import { sendDigitalTwinMessage, getDigitalTwinHistory } from '../config/api'; 
import { useCustomization } from '../contexts/CustomizationContext';
import { useAuth } from '../contexts/AuthContext'; // Import useAuth for current user info

// Utility to format timestamp
const formatTime = (isoString) => new Date(isoString).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

const DigitalTwinChat = ({ targetUserId, targetUserName, isManagerView = false, isWidget = false }) => {
    // CRITICAL FIX: Ensure defensive access to context.
    const { userContext } = useCustomization() || {};
    const { user } = useAuth() || {}; // Use useAuth for robust access to current user

    // Default to current authenticated user if targetUserId is not explicitly provided (i.e., Employee View)
    const actualTargetUserId = targetUserId || user?.id;
    const actualTargetUserName = targetUserName || user?.full_name || 'My Twin';
    
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [isMinimized, setIsMinimized] = useState(isWidget); // Start minimized if it's a fixed widget

    // Determines the role of the current user for display purposes
    const currentUserName = userContext?.userId || 'You';

    const fetchHistory = useCallback(async () => {
        if (!actualTargetUserId) return;
        setIsLoading(true);
        try {
            // This maps to /api/management/digital-twin/history/{targetUserId} (ID 7)
            const response = await getDigitalTwinHistory(actualTargetUserId); 
            const history = response.data || response; 
            setMessages(history.map(msg => ({ 
                ...msg, 
                timestamp: msg.timestamp || new Date().toISOString() 
            })));
        } catch (error) {
            console.error("Failed to fetch digital twin history:", error);
             setMessages([
                { sender: 'twin_bot', text: `Welcome, ${actualTargetUserName}. I am your Digital Twin. I can help track personalized tasks and goals.`, timestamp: new Date(Date.now() - 3600000).toISOString(), status: 'COMPLETE' },
             ]);
        } finally {
            setIsLoading(false);
        }
    }, [actualTargetUserId, actualTargetUserName]);

    // Initial load of history
    useEffect(() => {
        fetchHistory();
    }, [fetchHistory]);
    
    const handleSend = useCallback(async () => {
        if (!input.trim() || !actualTargetUserId) return;

        const messageText = input.trim();
        setInput(''); // Clear input immediately
        
        // Optimistic UI Update
        const newMessage = { 
            sender: currentUserName, 
            text: messageText, 
            timestamp: new Date().toISOString(), 
            status: 'PENDING' 
        };
        setMessages(prev => [...prev, newMessage]);

        try {
            // This maps to the /api/management/digital-twin/chat route (ID 8)
            const response = await sendDigitalTwinMessage(actualTargetUserId, messageText);
            
            // Update the optimistic message with a 'COMPLETE' status
            setMessages(prev => prev.map(msg => 
                msg === newMessage ? { ...msg, status: 'COMPLETE', timestamp: response?.timestamp || newMessage.timestamp } : msg
            ));

        } catch (error) {
            console.error("Failed to send digital twin message:", error);
            // On failure, revert the message status or remove it
            setMessages(prev => prev.map(msg => 
                msg === newMessage ? { ...msg, status: 'ERROR', text: `Failed to send: ${messageText}` } : msg
            ));
        }
    }, [input, actualTargetUserId, currentUserName]);

    // Message rendering logic
    const renderMessage = (msg, index) => {
        const isUser = msg.sender === currentUserName || msg.sender === 'You';
        const isTwin = msg.sender.toLowerCase().includes('twin') || msg.sender.toLowerCase().includes('bot');
        const isError = msg.status === 'ERROR';

        const bubbleStyle = {
            padding: tokens.spacing?.sm,
            borderRadius: tokens.border?.radius?.input,
            maxWidth: '80%',
            marginBottom: tokens.spacing?.xs,
            wordBreak: 'break-word',
            ... (isUser ? {
                background: tokens.color?.['accent-primary'],
                color: tokens.color?.['text-dark'],
                marginLeft: 'auto',
                borderBottomRightRadius: '2px',
            } : {
                background: isError ? tokens.color?.['danger-700'] : tokens.color?.['panel-700'],
                color: tokens.color?.['text-100'],
                marginRight: 'auto',
                borderBottomLeftRadius: '2px',
            })
        };

        const icon = isTwin ? <Bot size={16} /> : <User size={16} />;

        return (
            <div key={index} style={{ display: 'flex', flexDirection: 'column', alignItems: isUser ? 'flex-end' : 'flex-start' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: tokens.spacing?.xs, marginBottom: '4px', color: tokens.color?.['muted-500'], 
                    // --- FIX: Added optional chaining ---
                    fontSize: tokens.typography?.small?.fontSize 
                    // ------------------------------------
                }}>
                    {!isUser && icon}
                    <span style={{ 
                        // --- FIX: Added optional chaining ---
                        fontWeight: tokens.typography?.body?.fontWeight 
                        // ------------------------------------
                    }}>{isUser ? 'You' : actualTargetUserName || 'Twin'}</span>
                    {isUser && icon}
                </div>
                <div style={bubbleStyle}>
                    {msg.text}
                </div>
                <div style={{ 
                    // --- FIX: Added optional chaining ---
                    fontSize: tokens.typography?.small?.fontSize, 
                    // ------------------------------------
                    color: tokens.color?.['muted-500'], marginTop: '-4px', marginBottom: tokens.spacing?.sm, display: 'flex', alignItems: 'center', gap: tokens.spacing?.xs }}>
                    {formatTime(msg.timestamp)}
                    {msg.status === 'COMPLETE' && <Check size={12} color={tokens.color?.success} />}
                    {msg.status === 'PENDING' && <Clock size={12} color={tokens.color?.warning} />}
                    {msg.status === 'ERROR' && <X size={12} color={tokens.color?.danger} />}
                </div>
            </div>
        );
    };


    const chatContainerStyle = useMemo(() => ({
        display: 'flex',
        flexDirection: 'column',
        // CRITICAL: Dynamic dimensions for widget mode
        width: isWidget ? (isMinimized ? '60px' : '300px') : '100%',
        height: isWidget ? (isMinimized ? '60px' : '400px') : '100%',
        transition: 'all 0.3s ease-in-out',
        background: tokens.color?.['panel-800'],
        borderRadius: tokens.border?.radius?.card,
        overflow: 'hidden',
        boxShadow: tokens.shadow?.default,
        // CRITICAL: Fixed positioning for widget mode
        position: isWidget ? 'fixed' : 'relative',
        bottom: isWidget ? tokens.spacing?.lg : 'auto',
        right: isWidget ? tokens.spacing?.lg : 'auto',
        zIndex: isWidget ? 5000 : 'auto', // High z-index for fixed widget
    }), [isWidget, isMinimized]);


    if (isMinimized && isWidget) {
        return (
            <div style={chatContainerStyle} onClick={() => setIsMinimized(false)}>
                <div style={{ padding: tokens.spacing?.sm, display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', cursor: 'pointer', background: tokens.color?.['accent-primary'] }}>
                    <Bot size={24} color={tokens.color?.['bg-deep']} title="Digital Twin Chat (Click to expand)" />
                </div>
            </div>
        );
    }
    
    return (
        <div style={chatContainerStyle}>
            {/* Header */}
            <div style={{ padding: tokens.spacing?.md, borderBottom: `1px solid ${tokens.color?.['border-600']}`, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: tokens.spacing?.sm }}>
                    <Bot size={24} color={tokens.color?.['accent-primary']} />
                    <h3 style={{ margin: 0, color: tokens.color?.['text-100'], 
                        // CRITICAL: Ensure visibility in minimized header
                        fontSize: isMinimized ? tokens.typography?.small?.fontSize : tokens.typography?.base?.fontSize 
                    }}>
                        {actualTargetUserName}'s Digital Twin
                    </h3>
                </div>
                {isWidget && (
                    <button onClick={() => setIsMinimized(true)} style={{ background: 'none', border: 'none', cursor: 'pointer' }} title="Minimize Chat">
                        <Minimize2 size={20} color={tokens.color?.['muted-500']} />
                    </button>
                )}
            </div>

            {/* Message Area */}
            <div style={{ flexGrow: 1, overflowY: 'auto', padding: tokens.spacing?.md }}>
                {isLoading ? 
                    <p style={{textAlign: 'center', color: tokens.color?.['muted-500']}}>Loading history...</p> 
                    : messages.map(renderMessage)}
            </div>

            {/* Input is visible only if it is the Manager View OR it is the Employee Widget View */}
            {(isManagerView || isWidget) && (
                <div style={{ padding: tokens.spacing?.md, borderTop: `1px solid ${tokens.color?.['border-600']}`, display: 'flex', gap: tokens.spacing?.xs }}>
                    <input
                        type="text"
                        placeholder={isManagerView ? "Type reminder/task for the employee's twin..." : "Ask your twin about tasks or goals..."}
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                        style={{ flexGrow: 1, padding: '10px', borderRadius: '8px', background: tokens.color?.['bg-input'], border: `1px solid ${tokens.color?.['border-600']}`, color: tokens.color?.['text-100'] }}
                    />
                    <button onClick={handleSend} style={{ padding: '8px', borderRadius: '8px', background: tokens.color?.['accent-primary'], border: 'none', cursor: 'pointer' }} disabled={!input.trim() || isLoading}>
                        <Send size={20} color={tokens.color?.['bg-deep']} />
                    </button>
                </div>
            )}
        </div>
    );
};

DigitalTwinChat.displayName = 'DigitalTwinChat';
export default DigitalTwinChat;