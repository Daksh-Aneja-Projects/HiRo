// Employee portal: Goals / OKRs.
// Real endpoints: GET/POST /api/ess/goals, PUT/DELETE /api/ess/goals/{id},
// POST /api/ess/goals/draft (local model, ~20-40s). Key results are stored by
// the backend as [{text, done}], so every PUT sends the full list back.
import React, { memo, useCallback, useMemo, useState } from 'react';
import { theme as tokens } from '../../theme';
import { useApi } from '../../hooks/useApi';
import { useToast } from '../../hooks/use-toast';
import { getGoals, createGoal, updateGoal, deleteGoalRecord, draftGoal } from '../../config/api';
import DataCard from '../DataCard';
import { CountUp } from '../live/LivePrimitives';
import { ui, Btn, Loading, EmptyState, ErrorNote, EmployeeStyles } from './shared';
import { Target, Sparkles, Send, Trash2, CheckCircle, Circle, ListChecks, Plus, X } from 'lucide-react';

const BLANK = { title: '', description: '' };

const GoalsModule = memo(() => {
    const { toast } = useToast();
    const { data: resp, isLoading, error, refetch } = useApi(getGoals, [], true);
    const goals = useMemo(() => resp?.goals || [], [resp]);

    const [form, setForm] = useState(BLANK);
    const [keyResults, setKeyResults] = useState(['']);
    const [intent, setIntent] = useState('');
    const [isDrafting, setIsDrafting] = useState(false);
    const [isSaving, setIsSaving] = useState(false);
    const [busyId, setBusyId] = useState(null);

    const set = (key) => (e) => setForm((prev) => ({ ...prev, [key]: e.target.value }));
    const setKR = (i) => (e) => setKeyResults((prev) => prev.map((v, idx) => (idx === i ? e.target.value : v)));
    const addKR = () => setKeyResults((prev) => [...prev, '']);
    const removeKR = (i) => setKeyResults((prev) => prev.filter((_, idx) => idx !== i));

    const active = goals.filter((g) => String(g.status).toLowerCase() === 'active').length;
    const totalKR = goals.reduce((sum, g) => sum + (g.key_results || []).length, 0);
    const doneKR = goals.reduce((sum, g) => sum + (g.key_results || []).filter((k) => k.done).length, 0);

    const handleDraft = useCallback(async () => {
        const text = intent.trim();
        if (!text) {
            toast({ title: 'Describe what you are aiming for', description: 'A sentence is enough, the model turns it into a goal.', variant: 'destructive' });
            return;
        }
        setIsDrafting(true);
        try {
            const res = await draftGoal(text);
            const d = res.data || {};
            setForm({ title: d.title || '', description: '' });
            setKeyResults((d.key_results || ['']).length ? d.key_results : ['']);
            toast({ title: 'Draft ready', description: 'The local model wrote a title and key results below. Edit them before saving.', variant: 'success' });
        } catch (err) {
            toast({ title: 'Could not draft this goal', description: err.response?.data?.detail || err.message, variant: 'destructive' });
        } finally {
            setIsDrafting(false);
        }
    }, [intent, toast]);

    const handleSave = useCallback(async (e) => {
        e.preventDefault();
        const title = form.title.trim();
        const krs = keyResults.map((k) => k.trim()).filter(Boolean);
        if (!title) {
            toast({ title: 'Give the goal a title', description: 'A short outcome statement works best.', variant: 'destructive' });
            return;
        }
        setIsSaving(true);
        try {
            await createGoal({ title, description: form.description.trim(), key_results: krs });
            toast({ title: 'Goal saved', description: `"${title}" is on your goals list.`, variant: 'success' });
            setForm(BLANK);
            setKeyResults(['']);
            setIntent('');
            refetch();
        } catch (err) {
            toast({ title: 'Could not save this goal', description: err.response?.data?.detail || err.message, variant: 'destructive' });
        } finally {
            setIsSaving(false);
        }
    }, [form, keyResults, toast, refetch]);

    const toggleKeyResult = useCallback(async (goal, idx) => {
        setBusyId(`${goal.goal_id}:${idx}`);
        try {
            const next = (goal.key_results || []).map((k, i) => (i === idx ? { text: k.text, done: !k.done } : { text: k.text, done: k.done }));
            await updateGoal(goal.goal_id, { key_results: next });
            refetch();
        } catch (err) {
            toast({ title: 'Could not update that key result', description: err.response?.data?.detail || err.message, variant: 'destructive' });
        } finally {
            setBusyId(null);
        }
    }, [refetch, toast]);

    const removeGoal = useCallback(async (goal) => {
        setBusyId(goal.goal_id);
        try {
            await deleteGoalRecord(goal.goal_id);
            toast({ title: 'Goal removed', description: `"${goal.title}" was deleted.`, variant: 'default' });
            refetch();
        } catch (err) {
            toast({ title: 'Could not remove this goal', description: err.response?.data?.detail || err.message, variant: 'destructive' });
        } finally {
            setBusyId(null);
        }
    }, [refetch, toast]);

    return (
        <div style={ui.grid} className="portal-grid">
            <EmployeeStyles />

            <div style={{ gridColumn: 'span 4' }}>
                <DataCard title="Active goals" value={<CountUp value={active} />} unit="goals"
                    icon={<Target size={15} />} color={tokens.color?.['accent-primary']}
                    subtitle={`${goals.length} on record in total`} />
            </div>
            <div style={{ gridColumn: 'span 4' }}>
                <DataCard title="Key results completed" value={<CountUp value={doneKR} />} unit={`of ${totalKR}`}
                    icon={<ListChecks size={15} />} color={tokens.color?.success}
                    subtitle={totalKR ? `${Math.round((doneKR / totalKR) * 100)} percent checked off` : 'No key results written yet'} />
            </div>
            <div style={{ gridColumn: 'span 4' }}>
                <DataCard title="Why this matters" value="Goals and OKRs"
                    icon={<Sparkles size={15} />} color={tokens.color?.['accent-secondary']}
                    subtitle="Draft with AI from a one-line intent, then edit before saving." />
            </div>

            <div style={{ ...ui.panel, gridColumn: 'span 5' }}>
                <h3 style={ui.h3}>Set a new goal</h3>
                <p style={ui.hint}>Describe what you are trying to achieve and the model drafts a title and key results, or write your own below.</p>

                <div style={{ display: 'flex', gap: tokens.spacing?.xs, marginTop: tokens.spacing?.sm, flexWrap: 'wrap' }}>
                    <input style={{ ...ui.input, flex: '1 1 200px' }}
                        placeholder="For example become a better public speaker"
                        value={intent} onChange={(e) => setIntent(e.target.value)} disabled={isDrafting} />
                    <Btn tone="ghost" icon={Sparkles} loading={isDrafting} disabled={!intent.trim() || isSaving} onClick={handleDraft}>
                        Draft with AI
                    </Btn>
                </div>
                {isDrafting && <div style={{ marginTop: tokens.spacing?.sm }}><Loading label="The local model is drafting your goal, this can take up to a minute" /></div>}

                <form onSubmit={handleSave} style={{ marginTop: tokens.spacing?.md }}>
                    <div style={ui.field}>
                        <label style={ui.label} htmlFor="goal-title">Title</label>
                        <input id="goal-title" style={ui.input} placeholder="What outcome are you aiming for"
                            value={form.title} onChange={set('title')} />
                    </div>
                    <div style={ui.field}>
                        <label style={ui.label} htmlFor="goal-desc">Description</label>
                        <textarea id="goal-desc" style={{ ...ui.input, minHeight: 70, resize: 'vertical' }}
                            placeholder="Optional, more context on why this matters"
                            value={form.description} onChange={set('description')} />
                    </div>
                    <div style={ui.field}>
                        <label style={ui.label}>Key results</label>
                        {keyResults.map((kr, i) => (
                            <div key={i} style={{ display: 'flex', gap: 6, marginBottom: 6 }}>
                                <input style={ui.input} placeholder={`Key result ${i + 1}`} value={kr} onChange={setKR(i)} />
                                {keyResults.length > 1 && (
                                    <button type="button" onClick={() => removeKR(i)} aria-label="Remove key result"
                                        style={{ background: 'transparent', border: `1px solid ${tokens.color?.['border-600']}`, borderRadius: tokens.border?.radius?.button, color: tokens.color?.['muted-500'], cursor: 'pointer', padding: '0 10px', flexShrink: 0 }}>
                                        <X size={14} />
                                    </button>
                                )}
                            </div>
                        ))}
                        <Btn type="button" tone="ghost" icon={Plus} onClick={addKR} style={{ padding: '6px 12px', fontSize: 12.5 }}>
                            Add a key result
                        </Btn>
                    </div>

                    <Btn type="submit" tone="success" icon={Send} loading={isSaving} disabled={!form.title.trim()}>
                        Save this goal
                    </Btn>
                </form>
            </div>

            <div style={{ ...ui.panel, gridColumn: 'span 7' }}>
                <h3 style={ui.h3}>Your goals</h3>
                <p style={ui.hint}>Check off a key result as you complete it, or remove a goal you no longer need.</p>

                {isLoading && goals.length === 0 && <Loading label="Reading your goals" />}
                <ErrorNote error={error} context="your goals" />
                {!isLoading && !error && goals.length === 0 && (
                    <EmptyState icon={Target} title="No goals set yet"
                        action="Draft one with AI or write your own on the left. Your manager can see and comment on these." />
                )}

                {goals.length > 0 && (
                    <div className="emp-scroll" style={{ ...ui.scroller('460px'), marginTop: tokens.spacing?.sm }}>
                        {goals.map((g) => (
                            <div key={g.goal_id} style={{ padding: '12px 0', borderBottom: `1px solid ${tokens.color?.['border-600']}` }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                                    <div style={{ minWidth: 0 }}>
                                        <div style={{ color: tokens.color?.['text-100'], fontWeight: 550, fontSize: tokens.typography?.base?.fontSize }}>{g.title}</div>
                                        {g.description && <div style={{ ...ui.hint, margin: '3px 0 0 0' }}>{g.description}</div>}
                                    </div>
                                    <button type="button" onClick={() => removeGoal(g)} disabled={busyId === g.goal_id}
                                        aria-label="Delete goal"
                                        style={{ background: 'transparent', border: 'none', color: tokens.color?.danger, cursor: 'pointer', flexShrink: 0, opacity: busyId === g.goal_id ? 0.5 : 1 }}>
                                        <Trash2 size={15} />
                                    </button>
                                </div>
                                {(g.key_results || []).length === 0 ? (
                                    <p style={{ ...ui.hint, marginTop: 6 }}>No key results written for this goal.</p>
                                ) : (
                                    <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 5 }}>
                                        {g.key_results.map((kr, i) => (
                                            <button key={i} type="button" onClick={() => toggleKeyResult(g, i)}
                                                disabled={busyId === `${g.goal_id}:${i}`}
                                                style={{
                                                    display: 'flex', alignItems: 'center', gap: 8, background: 'transparent',
                                                    border: 'none', padding: 0, cursor: 'pointer', textAlign: 'left', width: '100%',
                                                    opacity: busyId === `${g.goal_id}:${i}` ? 0.5 : 1,
                                                }}>
                                                {kr.done ? <CheckCircle size={15} color={tokens.color?.success} /> : <Circle size={15} color={tokens.color?.['muted-500']} />}
                                                <span style={{
                                                    fontSize: tokens.typography?.small?.fontSize,
                                                    color: kr.done ? tokens.color?.['muted-600'] : tokens.color?.['text-100'],
                                                    textDecoration: kr.done ? 'line-through' : 'none',
                                                }}>{kr.text}</span>
                                            </button>
                                        ))}
                                    </div>
                                )}
                                {(g.comments || []).length > 0 && (
                                    <div style={{ marginTop: 8, paddingLeft: 10, borderLeft: `2px solid ${tokens.color?.['accent-primary']}44` }}>
                                        {g.comments.map((c, i) => (
                                            <p key={i} style={{ ...ui.hint, margin: '2px 0' }}>
                                                Your manager: {typeof c === 'string' ? c : (c.text || '')}
                                            </p>
                                        ))}
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
});

GoalsModule.displayName = 'GoalsModule';
export default GoalsModule;
