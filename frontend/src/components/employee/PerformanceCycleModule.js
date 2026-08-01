// Employee portal: performance cycle status, mounted in the Growth tab.
// Real endpoints: GET /api/ess/performance/my-cycles, POST /api/ess/performance/self-assessment
// (only during the self_assessment stage), POST /api/ess/performance/sign-off (only during
// the signed_off stage, which is when a calibrated rating is ready to be confirmed).
import React, { memo, useCallback, useMemo, useState } from 'react';
import { theme as tokens } from '../../theme';
import { useApi } from '../../hooks/useApi';
import { useToast } from '../../hooks/use-toast';
import { getMyPerformanceCycles, submitSelfAssessment, submitPerformanceSignOff } from '../../config/api';
import { ui, Btn, Loading, EmptyState, ErrorNote, StatusPill } from './shared';
import { Gauge, Send, BadgeCheck } from 'lucide-react';

// What is expected of the employee right now, in plain English, per cycle stage.
const STAGE_COPY = {
    self_assessment: {
        headline: 'Your self-assessment is due',
        detail: 'Write a short summary of your work this cycle and give yourself a rating. Your manager reviews it next.',
    },
    manager_review: {
        headline: 'Waiting on your manager',
        detail: 'Your self-assessment has been submitted. Your manager is reviewing it and adding their own rating now.',
    },
    calibration: {
        headline: 'Ratings are being calibrated',
        detail: 'HR is comparing ratings across the team to keep them fair and consistent. Nothing is needed from you yet.',
    },
    signed_off: {
        headline: 'Your calibrated rating is ready',
        detail: 'Review the rating below and sign off to close out this cycle.',
    },
};

const PerformanceCycleModule = memo(() => {
    const { toast } = useToast();
    const { data: resp, isLoading, error, refetch } = useApi(getMyPerformanceCycles, [], true);
    const entries = useMemo(() => resp?.entries || [], [resp]);

    const [drafts, setDrafts] = useState({});
    const [busyId, setBusyId] = useState(null);

    const draftFor = (cycleId) => drafts[cycleId] || { text: '', rating: 4 };
    const setDraft = (cycleId, patch) => setDrafts((prev) => ({ ...prev, [cycleId]: { ...draftFor(cycleId), ...patch } }));

    const handleSelfAssessment = useCallback(async (entry) => {
        const d = draftFor(entry.cycle_id);
        if (!d.text.trim()) {
            toast({ title: 'Write a few sentences first', description: 'Your self-assessment cannot be empty.', variant: 'destructive' });
            return;
        }
        setBusyId(entry.cycle_id);
        try {
            await submitSelfAssessment({ cycle_id: entry.cycle_id, self_assessment: d.text.trim(), self_rating: Number(d.rating) });
            toast({ title: 'Self-assessment submitted', description: `Sent for "${entry.cycle_name}". Your manager reviews it next.`, variant: 'success' });
            refetch();
        } catch (err) {
            toast({ title: 'Could not submit your self-assessment', description: err.response?.data?.detail || err.message, variant: 'destructive' });
        } finally {
            setBusyId(null);
        }
    }, [drafts, toast, refetch]); // eslint-disable-line react-hooks/exhaustive-deps

    const handleSignOff = useCallback(async (entry) => {
        setBusyId(entry.cycle_id);
        try {
            await submitPerformanceSignOff({ cycle_id: entry.cycle_id });
            toast({ title: 'Signed off', description: `"${entry.cycle_name}" is now closed out.`, variant: 'success' });
            refetch();
        } catch (err) {
            toast({ title: 'Could not sign off', description: err.response?.data?.detail || err.message, variant: 'destructive' });
        } finally {
            setBusyId(null);
        }
    }, [toast, refetch]);

    return (
        <div style={{ ...ui.panel, gridColumn: 'span 12' }}>
            <h3 style={ui.h3}><Gauge size={16} style={{ verticalAlign: '-3px', marginRight: 6 }} />Performance cycle</h3>
            <p style={ui.hint}>Where your current review stands, and what is expected of you now.</p>

            {isLoading && <Loading label="Reading your performance cycles" />}
            <ErrorNote error={error} context="your performance cycles" />
            {!isLoading && !error && entries.length === 0 && (
                <EmptyState icon={Gauge} title="No performance cycle is open for you right now"
                    action="When HR opens a review cycle that includes you, it appears here." />
            )}

            {entries.map((entry) => {
                const copy = STAGE_COPY[entry.cycle_stage] || { headline: 'In progress', detail: '' };
                const d = draftFor(entry.cycle_id);
                const readyToSignOff = entry.cycle_stage === 'signed_off' && !entry.signed_off_by_employee;
                return (
                    <div key={entry.cycle_id} style={{ marginTop: tokens.spacing?.md, padding: '14px 0', borderTop: `1px solid ${tokens.color?.['border-600']}` }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
                            <span style={{ fontWeight: 600, color: tokens.color?.['text-100'] }}>{entry.cycle_name}</span>
                            <StatusPill status={entry.cycle_stage} />
                        </div>
                        <p style={{ margin: '6px 0 0 0', color: tokens.color?.['text-100'], fontSize: tokens.typography?.base?.fontSize }}>{copy.headline}</p>
                        <p style={ui.hint}>{copy.detail}</p>

                        {entry.cycle_stage === 'self_assessment' && (
                            <div style={{ marginTop: 10 }}>
                                <textarea style={{ ...ui.input, minHeight: 90, resize: 'vertical' }}
                                    placeholder="What did you accomplish this cycle, and where did you fall short"
                                    defaultValue={entry.self_assessment || ''}
                                    onChange={(e) => setDraft(entry.cycle_id, { text: e.target.value })} />
                                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 8, flexWrap: 'wrap' }}>
                                    <label style={{ ...ui.label, margin: 0 }}>Self rating out of 5</label>
                                    <input type="range" min="1" max="5" step="0.5" defaultValue={entry.self_rating || 4}
                                        onChange={(e) => setDraft(entry.cycle_id, { rating: e.target.value })}
                                        style={{ flex: '1 1 140px', accentColor: tokens.color?.['accent-primary'] }} />
                                    <span style={{ fontWeight: 600, color: tokens.color?.['text-100'] }}>{d.rating}</span>
                                </div>
                                <div style={{ marginTop: 10 }}>
                                    <Btn tone="success" icon={Send} loading={busyId === entry.cycle_id} onClick={() => handleSelfAssessment(entry)}>
                                        Submit self-assessment
                                    </Btn>
                                </div>
                            </div>
                        )}

                        {(entry.manager_rating != null || entry.calibrated_rating != null) && (
                            <div style={{ display: 'flex', gap: tokens.spacing?.lg, marginTop: 10, flexWrap: 'wrap' }}>
                                {entry.manager_rating != null && (
                                    <div>
                                        <div style={{ fontSize: 11.5, color: tokens.color?.['muted-600'] }}>Manager rating</div>
                                        <div style={{ fontSize: 18, fontWeight: 640, color: tokens.color?.['text-100'] }}>{entry.manager_rating} / 5</div>
                                    </div>
                                )}
                                {entry.calibrated_rating != null && (
                                    <div>
                                        <div style={{ fontSize: 11.5, color: tokens.color?.['muted-600'] }}>Calibrated rating</div>
                                        <div style={{ fontSize: 18, fontWeight: 640, color: tokens.color?.['accent-primary'] }}>{entry.calibrated_rating} / 5</div>
                                    </div>
                                )}
                            </div>
                        )}

                        {readyToSignOff && (
                            <div style={{ marginTop: 10 }}>
                                <Btn tone="success" icon={BadgeCheck} loading={busyId === entry.cycle_id} onClick={() => handleSignOff(entry)}>
                                    Sign off on this review
                                </Btn>
                            </div>
                        )}
                        {entry.signed_off_by_employee && (
                            <p style={{ ...ui.hint, marginTop: 8, color: tokens.color?.success }}>You signed off on this review.</p>
                        )}
                    </div>
                );
            })}
        </div>
    );
});

PerformanceCycleModule.displayName = 'PerformanceCycleModule';
export default PerformanceCycleModule;
