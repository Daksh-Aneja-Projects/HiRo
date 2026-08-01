// Headcount panel, embedded in the Talent Insights tab: plan headcount per
// department and compare it against the real live headcount.
import React, { useMemo, useState, useCallback } from 'react';
import { theme as tokens } from '../../theme';
import {
    createHeadcountPlan, getHeadcountPlans, updateHeadcountPlan, deleteHeadcountPlan,
    getHeadcountVariance, getAnalyticsDepartments,
} from '../../config/api';
import { useApi } from '../../hooks/useApi';
import { useToast } from '../../hooks/use-toast';
import { ui, Btn, Loading, EmptyState, ErrorNote } from '../employee/shared';
import { useCountUp } from '../live/LivePrimitives';
import { Target, Trash2, Users } from 'lucide-react';

const errText = (e) => e?.response?.data?.detail || e?.message || 'The request failed.';

const PairedBar = ({ dept }) => {
    const max = Math.max(dept.planned_headcount, dept.actual_headcount, 1);
    const plannedPct = useCountUp((dept.planned_headcount / max) * 100, { decimals: 1 });
    const actualPct = useCountUp((dept.actual_headcount / max) * 100, { decimals: 1 });
    const over = dept.variance > 0;
    const badgeColor = dept.variance === 0 ? tokens.color?.success : (over ? tokens.color?.warning : tokens.color?.danger);

    return (
        <div style={{ marginBottom: 14 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
                <strong style={{ fontSize: 12.5, color: tokens.color?.['text-100'] }}>{dept.department}</strong>
                <span style={{ fontSize: 11.5, fontWeight: 600, color: badgeColor, background: `${badgeColor}18`, borderRadius: 999, padding: '2px 8px' }}>
                    {dept.variance === 0 ? 'On plan' : `${over ? '+' : ''}${dept.variance} (${dept.variance_pct}%)`}
                </span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                <BarRow label="Planned" value={dept.planned_headcount} pct={plannedPct} color={tokens.color?.['accent-primary']} />
                <BarRow label="Actual" value={dept.actual_headcount} pct={actualPct} color={over ? tokens.color?.warning : tokens.color?.success} />
            </div>
        </div>
    );
};

const BarRow = ({ label, value, pct, color }) => (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ width: 52, fontSize: 10.5, color: tokens.color?.['muted-600'] }}>{label}</span>
        <div style={{ flex: 1, height: 9, borderRadius: 999, background: 'rgba(255,255,255,0.06)', overflow: 'hidden' }}>
            <div style={{ height: '100%', width: `${pct}%`, borderRadius: 999, background: color, transition: 'width 0.3s ease' }} />
        </div>
        <span style={{ width: 46, textAlign: 'right', fontSize: 11, color: tokens.color?.['muted-500'], fontVariantNumeric: 'tabular-nums' }}>{value.toLocaleString()}</span>
    </div>
);

const HeadcountPanel = () => {
    const { toast } = useToast();
    const { data: plansData, isLoading: plansLoading, error: plansError, refetch: refetchPlans } = useApi(getHeadcountPlans, [], true);
    const { data: varianceData, isLoading: varLoading, error: varError, refetch: refetchVariance } = useApi(getHeadcountVariance, [], true);
    const { data: deptData } = useApi(getAnalyticsDepartments, [], true);

    const plans = useMemo(() => plansData?.plans || [], [plansData]);
    const variance = useMemo(() => varianceData?.departments || [], [varianceData]);
    const departments = deptData?.departments || [];

    const [form, setForm] = useState({ department: '', fiscal_label: 'FY26', planned_headcount: '' });
    const [creating, setCreating] = useState(false);
    const [busy, setBusy] = useState(null);

    const refetchAll = useCallback(() => { refetchPlans(); refetchVariance(); }, [refetchPlans, refetchVariance]);

    const create = useCallback(async (e) => {
        e.preventDefault();
        if (!form.department || !form.fiscal_label.trim() || !form.planned_headcount) {
            toast({ title: 'Fill in every field', description: 'A plan needs a department, a fiscal label and a target headcount.', variant: 'warning' });
            return;
        }
        setCreating(true);
        try {
            await createHeadcountPlan(form.department, form.fiscal_label.trim(), parseInt(form.planned_headcount, 10));
            toast({ title: 'Plan created', description: `${form.department} targeted at ${form.planned_headcount} for ${form.fiscal_label}.`, variant: 'success' });
            setForm({ department: '', fiscal_label: 'FY26', planned_headcount: '' });
            refetchAll();
        } catch (err) {
            toast({ title: 'Could not create the plan', description: errText(err), variant: 'destructive' });
        } finally {
            setCreating(false);
        }
    }, [form, toast, refetchAll]);

    const remove = useCallback(async (plan) => {
        if (!window.confirm(`Delete the ${plan.fiscal_label} headcount plan for ${plan.department}?`)) return;
        setBusy(plan.plan_id);
        try {
            await deleteHeadcountPlan(plan.plan_id);
            toast({ title: 'Plan deleted', variant: 'success' });
            refetchAll();
        } catch (err) {
            toast({ title: 'Could not delete the plan', description: errText(err), variant: 'destructive' });
        } finally {
            setBusy(null);
        }
    }, [toast, refetchAll]);

    const editTarget = useCallback(async (plan) => {
        const next = window.prompt(`New planned headcount for ${plan.department} (${plan.fiscal_label}):`, plan.planned_headcount);
        if (next == null || next.trim() === '' || Number.isNaN(parseInt(next, 10))) return;
        setBusy(plan.plan_id);
        try {
            await updateHeadcountPlan(plan.plan_id, { planned_headcount: parseInt(next, 10) });
            toast({ title: 'Plan updated', variant: 'success' });
            refetchAll();
        } catch (err) {
            toast({ title: 'Could not update the plan', description: errText(err), variant: 'destructive' });
        } finally {
            setBusy(null);
        }
    }, [toast, refetchAll]);

    return (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(12, 1fr)', gap: tokens.spacing?.lg, marginTop: tokens.spacing?.lg }}>
            <div style={{ ...ui.panel, gridColumn: 'span 5' }}>
                <h3 style={ui.h3}><Target size={16} style={{ verticalAlign: -3, marginRight: 6 }} color={tokens.color?.['accent-primary']} />Headcount plans</h3>
                <form onSubmit={create} style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 10, marginBottom: 14 }}>
                    <select style={{ ...ui.input, flex: '1 1 140px' }} value={form.department} onChange={(e) => setForm((p) => ({ ...p, department: e.target.value }))} required>
                        <option value="">Department</option>
                        {departments.map((d) => <option key={d} value={d}>{d}</option>)}
                    </select>
                    <input style={{ ...ui.input, width: 90 }} value={form.fiscal_label} onChange={(e) => setForm((p) => ({ ...p, fiscal_label: e.target.value }))} placeholder="FY26" required />
                    <input type="number" min="0" style={{ ...ui.input, width: 110 }} value={form.planned_headcount} onChange={(e) => setForm((p) => ({ ...p, planned_headcount: e.target.value }))} placeholder="Target" required />
                    <Btn type="submit" loading={creating} style={{ flexShrink: 0 }}>{creating ? 'Saving' : 'Add plan'}</Btn>
                </form>

                {plansLoading && !plansData && <Loading label="Reading headcount plans" />}
                <ErrorNote error={plansError} context="headcount plans" />
                {!plansLoading && !plansError && plans.length === 0 && (
                    <EmptyState icon={Users} title="No headcount plans yet" action="Add one above to start tracking planned vs actual." />
                )}
                <div style={ui.scroller('280px')} className="emp-scroll">
                    {plans.map((p) => (
                        <div key={p.plan_id} style={ui.listRow}>
                            <div style={ui.rowMain}>
                                <span style={ui.rowTitle}>{p.department}</span>
                                <span style={ui.rowMeta}>{p.fiscal_label}, target {p.planned_headcount.toLocaleString()}</span>
                            </div>
                            <div style={{ display: 'flex', gap: 6 }}>
                                <button type="button" onClick={() => editTarget(p)} disabled={busy === p.plan_id}
                                    style={{ background: 'none', border: `1px solid ${tokens.color?.['border-600']}`, borderRadius: 6, color: tokens.color?.['text-100'], fontSize: 11.5, padding: '4px 8px', cursor: 'pointer' }}>
                                    Edit
                                </button>
                                <button type="button" onClick={() => remove(p)} disabled={busy === p.plan_id}
                                    style={{ background: 'none', border: `1px solid ${tokens.color?.danger}44`, borderRadius: 6, color: tokens.color?.danger, padding: '4px 8px', cursor: 'pointer' }}
                                    aria-label={`Delete plan for ${p.department}`}>
                                    <Trash2 size={13} />
                                </button>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            <div style={{ ...ui.panel, gridColumn: 'span 7' }}>
                <h3 style={ui.h3}>Planned vs actual headcount</h3>
                <p style={ui.hint}>The latest plan per department against the real, live headcount.</p>
                {varLoading && !varianceData && <Loading label="Comparing plans against live headcount" />}
                <ErrorNote error={varError} context="headcount variance" />
                {!varLoading && !varError && variance.length === 0 && (
                    <EmptyState icon={Target} title="Nothing to compare yet" action="Once a department has a plan, its planned and actual headcount appear here." />
                )}
                <div style={ui.scroller('300px')} className="emp-scroll">
                    {variance.map((d) => <PairedBar key={d.department} dept={d} />)}
                </div>
            </div>
        </div>
    );
};

export default HeadcountPanel;
