// Conversation with a person's digital twin.
// History comes back as { thread, role, sender, text, ts } and the send call
// returns the twin's real reply, so both are rendered as they arrive. When the
// backend cannot be reached the panel says so instead of inventing a greeting.
import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { Send, Bot, User, Clock, Check, X, Minimize2 } from 'lucide-react';
import { theme as tokens } from '../theme';
import { sendDigitalTwinMessage, getDigitalTwinHistory } from '../config/api';
import { useAuth } from '../contexts/AuthContext';

const formatTime = (value) => {
    const d = new Date(value);
    return Number.isNaN(d.getTime()) ? '' : d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
};

// The model often wraps its whole answer in quotes; they are noise on screen.
const unquote = (s) => String(s ?? '').trim().replace(/^"(.*)"$/s, '$1');

// Normalises a stored row into what this component renders.
const normalise = (row) => ({
    fromTwin: String(row.role || row.sender || '').toLowerCase().includes('twin'),
    text: unquote(row.text),
    ts: row.ts || row.timestamp || new Date().toISOString(),
    status: 'sent',
});

const DigitalTwinChat = ({ targetUserId, targetUserName, isManagerView = false, isWidget = false }) => {
    const { user } = useAuth() || {};

    const chatWith = targetUserId || user?.id;
    const chatWithName = targetUserName || user?.full_name || 'your own twin';

    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [isLoadingHistory, setIsLoadingHistory] = useState(false);
    const [isSending, setIsSending] = useState(false);
    const [loadError, setLoadError] = useState(null);
    const [isMinimized, setIsMinimized] = useState(isWidget);
    const endRef = useRef(null);

    useEffect(() => {
        if (!chatWith) return undefined;
        let alive = true;
        setIsLoadingHistory(true);
        setLoadError(null);
        getDigitalTwinHistory(chatWith)
            .then((res) => {
                if (!alive) return;
                const rows = Array.isArray(res.data) ? res.data : [];
                setMessages(rows.map(normalise));
            })
            .catch((err) => {
                if (!alive) return;
                setMessages([]);
                setLoadError(err.response?.data?.detail || err.message || 'The conversation could not be loaded.');
            })
            .finally(() => { if (alive) setIsLoadingHistory(false); });
        return () => { alive = false; };
    }, [chatWith]);

    useEffect(() => {
        endRef.current?.scrollIntoView({ block: 'nearest' });
    }, [messages]);

    const handleSend = useCallback(async () => {
        const text = input.trim();
        if (!text || !chatWith || isSending) return;
        setInput('');
        setIsSending(true);

        const stamp = new Date().toISOString();
        setMessages((prev) => [...prev, { fromTwin: false, text, ts: stamp, status: 'sending' }]);

        try {
            const res = await sendDigitalTwinMessage(chatWith, text);
            const reply = res.data?.reply;
            setMessages((prev) => {
                const next = prev.map((m) => (m.ts === stamp && !m.fromTwin ? { ...m, status: 'sent' } : m));
                return reply
                    ? [...next, { fromTwin: true, text: unquote(reply), ts: new Date().toISOString(), status: 'sent' }]
                    : next;
            });
        } catch (err) {
            const detail = err.response?.data?.detail || err.message || 'The message could not be delivered.';
            setMessages((prev) => prev.map((m) => (
                m.ts === stamp && !m.fromTwin ? { ...m, status: 'failed', error: detail } : m
            )));
        } finally {
            setIsSending(false);
        }
    }, [input, chatWith, isSending]);

    const shell = useMemo(() => ({
        display: 'flex',
        flexDirection: 'column',
        width: isWidget ? (isMinimized ? '46px' : '330px') : '100%',
        height: isWidget ? (isMinimized ? '46px' : '440px') : '100%',
        minHeight: isWidget ? undefined : '440px',
        background: tokens.color?.['panel-800'],
        border: '1px solid var(--border-subtle)',
        borderRadius: tokens.border?.radius?.card,
        overflow: 'hidden',
        boxShadow: isWidget ? tokens.shadow?.default : 'none',
        boxSizing: 'border-box',
        transition: 'width 0.22s ease, height 0.22s ease',
    }), [isWidget, isMinimized]);

    if (isWidget && isMinimized) {
        return (
            <button
                type="button"
                onClick={() => setIsMinimized(false)}
                title="Open the digital twin conversation"
                style={{
                    width: 46, height: 46, borderRadius: tokens.border?.radius?.full,
                    border: 'none', cursor: 'pointer', display: 'grid', placeItems: 'center',
                    background: tokens.color?.['accent-primary'], color: tokens.color?.['bg-deep'],
                    boxShadow: tokens.shadow?.default,
                }}
            >
                <Bot size={21} />
            </button>
        );
    }

    const canWrite = isManagerView || isWidget;

    return (
        <div style={shell}>
            <div style={{
                padding: '12px 14px', borderBottom: `1px solid ${tokens.color?.['border-600']}`,
                display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, flexShrink: 0,
            }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 9, minWidth: 0 }}>
                    <Bot size={18} color={tokens.color?.['accent-primary']} />
                    <div style={{ minWidth: 0 }}>
                        <div style={{
                            color: tokens.color?.['text-100'], fontSize: tokens.typography?.h3?.fontSize,
                            fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                        }}>
                            Digital twin of {chatWithName}
                        </div>
                        <div style={{ fontSize: '11.5px', color: tokens.color?.['muted-600'] }}>
                            An AI stand-in that answers the way this person would
                        </div>
                    </div>
                </div>
                {isWidget && (
                    <button
                        type="button"
                        onClick={() => setIsMinimized(true)}
                        title="Minimise"
                        style={{ background: 'none', border: 'none', cursor: 'pointer', color: tokens.color?.['muted-500'], display: 'grid', placeItems: 'center' }}
                    >
                        <Minimize2 size={17} />
                    </button>
                )}
            </div>

            <div style={{ flexGrow: 1, minHeight: 0, overflowY: 'auto', padding: '14px' }} className="emp-scroll">
                {isLoadingHistory && (
                    <p style={{ textAlign: 'center', color: tokens.color?.['muted-500'], fontSize: tokens.typography?.small?.fontSize }}>
                        Loading the conversation
                    </p>
                )}

                {loadError && !isLoadingHistory && (
                    <p style={{
                        padding: '10px 12px', borderRadius: tokens.border?.radius?.input,
                        border: `1px solid ${tokens.color?.danger}33`, background: `${tokens.color?.danger}0f`,
                        color: tokens.color?.danger, fontSize: tokens.typography?.small?.fontSize, lineHeight: 1.5,
                    }}>
                        The conversation could not be loaded. {loadError}
                    </p>
                )}

                {!isLoadingHistory && !loadError && messages.length === 0 && (
                    <p style={{ textAlign: 'center', color: tokens.color?.['muted-600'], fontSize: tokens.typography?.small?.fontSize, lineHeight: 1.55, padding: '18px 8px' }}>
                        Nothing has been said yet.
                        {canWrite ? ' Ask a question below to start the conversation.' : ''}
                    </p>
                )}

                {messages.map((m, i) => (
                    <div key={`${m.ts}-${i}`} style={{ display: 'flex', flexDirection: 'column', alignItems: m.fromTwin ? 'flex-start' : 'flex-end', marginBottom: 12 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 4, color: tokens.color?.['muted-600'], fontSize: '11.5px' }}>
                            {m.fromTwin ? <Bot size={12} /> : <User size={12} />}
                            <span>{m.fromTwin ? chatWithName : 'You'}</span>
                        </div>
                        <div style={{
                            padding: '9px 12px', borderRadius: tokens.border?.radius?.input, maxWidth: '85%',
                            wordBreak: 'break-word', lineHeight: 1.55,
                            fontSize: tokens.typography?.base?.fontSize,
                            background: m.fromTwin ? tokens.color?.['panel-700'] : tokens.color?.['accent-primary'],
                            color: m.fromTwin ? tokens.color?.['text-100'] : tokens.color?.['bg-deep'],
                            border: m.status === 'failed' ? `1px solid ${tokens.color?.danger}` : 'none',
                        }}>
                            {m.text}
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginTop: 4, color: tokens.color?.['muted-600'], fontSize: '11px' }}>
                            {formatTime(m.ts)}
                            {m.status === 'sent' && <Check size={11} color={tokens.color?.success} />}
                            {m.status === 'sending' && <Clock size={11} color={tokens.color?.warning} />}
                            {m.status === 'failed' && <X size={11} color={tokens.color?.danger} />}
                        </div>
                        {m.status === 'failed' && (
                            <div style={{ color: tokens.color?.danger, fontSize: '11.5px', marginTop: 2, maxWidth: '85%', lineHeight: 1.45 }}>
                                Not delivered. {m.error}
                            </div>
                        )}
                    </div>
                ))}
                <div ref={endRef} />
            </div>

            {canWrite && (
                <div style={{ padding: '12px 14px', borderTop: `1px solid ${tokens.color?.['border-600']}`, display: 'flex', gap: 8, flexShrink: 0 }}>
                    <input
                        type="text"
                        placeholder={isManagerView ? `Ask ${chatWithName} about workload or blockers` : 'Ask your twin about tasks or goals'}
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => { if (e.key === 'Enter') handleSend(); }}
                        disabled={isSending || !chatWith}
                        style={{
                            flexGrow: 1, minWidth: 0, padding: '9px 11px',
                            borderRadius: tokens.border?.radius?.input,
                            background: tokens.color?.['bg-input'],
                            border: `1px solid ${tokens.color?.['border-600']}`,
                            color: tokens.color?.['text-100'],
                            fontSize: tokens.typography?.base?.fontSize,
                            fontFamily: tokens.typography?.fontFamily,
                            outline: 'none',
                        }}
                    />
                    <button
                        type="button"
                        onClick={handleSend}
                        disabled={!input.trim() || isSending || !chatWith}
                        title="Send"
                        style={{
                            padding: '0 12px', borderRadius: tokens.border?.radius?.button,
                            background: tokens.color?.['accent-primary'], border: 'none',
                            color: tokens.color?.['bg-deep'],
                            cursor: (!input.trim() || isSending) ? 'not-allowed' : 'pointer',
                            opacity: (!input.trim() || isSending) ? 0.55 : 1,
                            display: 'grid', placeItems: 'center',
                        }}
                    >
                        <Send size={17} />
                    </button>
                </div>
            )}
        </div>
    );
};

DigitalTwinChat.displayName = 'DigitalTwinChat';
export default DigitalTwinChat;
