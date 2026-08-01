// Employee portal: dismissible pulse survey card for the Dashboard tab.
// Real endpoint: POST /api/ess/pulse {score, comment}. There is no GET to check
// whether this cycle was already answered, so the duplicate state is learned
// from the backend's own 400 ("You have already responded to this survey.")
// and remembered locally for the month so the card does not nag after that.
import React, { memo, useCallback, useState } from 'react';
import { theme as tokens } from '../../theme';
import { submitPulseSurvey } from '../../config/api';
import { ui, Btn } from './shared';
import { Heart, Send, X, CheckCircle } from 'lucide-react';

const monthKey = () => `hiro_pulse_${new Date().toISOString().slice(0, 7)}`;

const PulseSurveyCard = memo(() => {
    const [state, setState] = useState(() => localStorage.getItem(monthKey()) || 'form');
    const [score, setScore] = useState(8);
    const [comment, setComment] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);

    const dismiss = useCallback(() => {
        localStorage.setItem(monthKey(), 'dismissed');
        setState('dismissed');
    }, []);

    const handleSubmit = useCallback(async () => {
        setIsSubmitting(true);
        try {
            await submitPulseSurvey({ score, comment: comment.trim() });
            localStorage.setItem(monthKey(), 'answered');
            setState('answered');
        } catch (err) {
            const detail = err.response?.data?.detail || err.message;
            if (err.response?.status === 409 || /already/i.test(detail)) {
                localStorage.setItem(monthKey(), 'answered');
                setState('answered');
            } else {
                setState('form');
            }
        } finally {
            setIsSubmitting(false);
        }
    }, [score, comment]);

    if (state === 'dismissed') return null;

    if (state === 'answered') {
        return (
            <div style={{ ...ui.panel, gridColumn: 'span 12', display: 'flex', alignItems: 'center', gap: 10, borderLeft: `3px solid ${tokens.color?.success}` }}>
                <CheckCircle size={16} color={tokens.color?.success} />
                <span style={{ color: tokens.color?.['text-100'], fontSize: tokens.typography?.base?.fontSize }}>
                    You have already answered this cycle&apos;s pulse survey. Thank you.
                </span>
                <button type="button" onClick={dismiss} aria-label="Dismiss"
                    style={{ marginLeft: 'auto', background: 'transparent', border: 'none', color: tokens.color?.['muted-500'], cursor: 'pointer' }}>
                    <X size={15} />
                </button>
            </div>
        );
    }

    return (
        <div style={{ ...ui.panel, gridColumn: 'span 12', borderLeft: `3px solid ${tokens.color?.['accent-secondary']}` }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8, flexWrap: 'wrap' }}>
                <div style={{ minWidth: 0 }}>
                    <h3 style={ui.h3}><Heart size={15} style={{ verticalAlign: '-2px', marginRight: 6 }} />How are you feeling about work this cycle</h3>
                    <p style={ui.hint}>Zero is not at all likely to recommend HiRo as a place to work, ten is extremely likely. It takes a few seconds.</p>
                </div>
                <button type="button" onClick={dismiss} aria-label="Dismiss the pulse survey"
                    style={{ background: 'transparent', border: 'none', color: tokens.color?.['muted-500'], cursor: 'pointer', flexShrink: 0 }}>
                    <X size={16} />
                </button>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: tokens.spacing?.sm, flexWrap: 'wrap' }}>
                <input type="range" min="0" max="10" step="1" value={score}
                    onChange={(e) => setScore(Number(e.target.value))}
                    style={{ flex: '1 1 200px', accentColor: tokens.color?.['accent-secondary'] }} />
                <span style={{ fontSize: 20, fontWeight: 640, color: tokens.color?.['text-100'], minWidth: 28, textAlign: 'center' }}>{score}</span>
            </div>
            <input style={{ ...ui.input, marginTop: tokens.spacing?.sm }}
                placeholder="Optional comment, what is going well or what is not"
                value={comment} onChange={(e) => setComment(e.target.value)} />
            <div style={{ marginTop: tokens.spacing?.sm }}>
                <Btn tone="success" icon={Send} loading={isSubmitting} onClick={handleSubmit}>Send my answer</Btn>
            </div>
        </div>
    );
});

PulseSurveyCard.displayName = 'PulseSurveyCard';
export default PulseSurveyCard;
