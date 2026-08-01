// Employee portal: onboarding plan.
// Real endpoints: GET /api/ess/onboarding/my-plan, POST /api/ess/onboarding/items/{item_id}/complete.
// When there is no plan the backend returns {plan: null}: this is treated as an
// honest absence, not an empty shell, so nothing renders at all in that case.
import React, { memo, useCallback, useMemo, useState } from 'react';
import { theme as tokens } from '../../theme';
import { useApi } from '../../hooks/useApi';
import { useToast } from '../../hooks/use-toast';
import { getMyOnboardingPlan, completeOnboardingItem } from '../../config/api';
import { ui, Btn, Loading, EmptyState, humanText } from './shared';
import { ClipboardCheck, CheckCircle, Circle, UserCog, User, Building2 } from 'lucide-react';

const OWNER_LABEL = { hr: 'HR', manager: 'Your manager', employee: 'You' };
const OWNER_ICON = { hr: Building2, manager: UserCog, employee: User };

/** Shared checklist body used by both the dashboard card and the full view. */
const PlanChecklist = ({ plan, onComplete, busyId, limit }) => {
    const items = limit ? plan.items.slice(0, limit) : plan.items;
    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {items.map((item) => {
                const OwnerIcon = OWNER_ICON[item.owner] || User;
                const done = String(item.status).toUpperCase() === 'DONE';
                const canComplete = item.owner === 'employee' && !done;
                return (
                    <div key={item.item_id} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '6px 0' }}>
                        {done ? <CheckCircle size={16} color={tokens.color?.success} style={{ marginTop: 1, flexShrink: 0 }} />
                            : <Circle size={16} color={tokens.color?.['muted-500']} style={{ marginTop: 1, flexShrink: 0 }} />}
                        <div style={{ minWidth: 0, flexGrow: 1 }}>
                            <div style={{
                                fontSize: tokens.typography?.small?.fontSize,
                                color: done ? tokens.color?.['muted-600'] : tokens.color?.['text-100'],
                                textDecoration: done ? 'line-through' : 'none',
                            }}>{item.description}</div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginTop: 2, color: tokens.color?.['muted-600'], fontSize: 11.5 }}>
                                <OwnerIcon size={11} /> {OWNER_LABEL[item.owner] || humanText(item.owner)}
                            </div>
                        </div>
                        {canComplete && (
                            <Btn tone="ghost" style={{ padding: '5px 10px', fontSize: 11.5, flexShrink: 0 }}
                                loading={busyId === item.item_id} onClick={() => onComplete(item.item_id)}>
                                Mark done
                            </Btn>
                        )}
                    </div>
                );
            })}
        </div>
    );
};

/** Prominent checklist card for the Dashboard tab. Renders nothing without a plan. */
export const OnboardingPlanCard = memo(() => {
    const { toast } = useToast();
    const { data: resp, isLoading, refetch } = useApi(getMyOnboardingPlan, [], true);
    const [busyId, setBusyId] = useState(null);
    const plan = resp?.plan;

    const handleComplete = useCallback(async (itemId) => {
        setBusyId(itemId);
        try {
            await completeOnboardingItem(itemId);
            toast({ title: 'Marked as done', description: 'Nice work, your onboarding plan is updated.', variant: 'success' });
            refetch();
        } catch (err) {
            toast({ title: 'Could not mark that as done', description: err.response?.data?.detail || err.message, variant: 'destructive' });
        } finally {
            setBusyId(null);
        }
    }, [toast, refetch]);

    if (isLoading || !plan) return null;

    return (
        <div style={{ ...ui.panel, gridColumn: 'span 12', borderLeft: `3px solid ${tokens.color?.['accent-primary']}` }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', flexWrap: 'wrap', gap: 8 }}>
                <h3 style={ui.h3}><ClipboardCheck size={16} style={{ verticalAlign: '-3px', marginRight: 6 }} />Your onboarding plan</h3>
                <span style={{ ...ui.hint, margin: 0 }}>{plan.progress.done} of {plan.progress.total} steps done, {plan.progress.percent.toFixed(0)}%</span>
            </div>
            <PlanChecklist plan={plan} onComplete={handleComplete} busyId={busyId} limit={5} />
        </div>
    );
});
OnboardingPlanCard.displayName = 'OnboardingPlanCard';

/** Full onboarding view for its own tab. Only mounted when a plan exists. */
const OnboardingPlanModule = memo(() => {
    const { toast } = useToast();
    const { data: resp, isLoading, error, refetch } = useApi(getMyOnboardingPlan, [], true);
    const [busyId, setBusyId] = useState(null);
    const plan = resp?.plan;

    const handleComplete = useCallback(async (itemId) => {
        setBusyId(itemId);
        try {
            await completeOnboardingItem(itemId);
            toast({ title: 'Marked as done', description: 'Nice work, your onboarding plan is updated.', variant: 'success' });
            refetch();
        } catch (err) {
            toast({ title: 'Could not mark that as done', description: err.response?.data?.detail || err.message, variant: 'destructive' });
        } finally {
            setBusyId(null);
        }
    }, [toast, refetch]);

    const byOwner = useMemo(() => {
        if (!plan) return {};
        return plan.items.reduce((acc, i) => {
            (acc[i.owner] = acc[i.owner] || []).push(i);
            return acc;
        }, {});
    }, [plan]);

    return (
        <div style={ui.grid} className="portal-grid">
            {isLoading && <div style={{ gridColumn: 'span 12' }}><Loading label="Reading your onboarding plan" /></div>}
            {error && <div style={{ gridColumn: 'span 12', color: tokens.color?.danger }}>Could not load your onboarding plan. {error}</div>}

            {!isLoading && !error && !plan && (
                <div style={{ gridColumn: 'span 12' }}>
                    <EmptyState icon={ClipboardCheck} title="You do not have an onboarding plan"
                        action="Plans are created by HR for new joiners. If you have just started and nothing is here, ask your HR business partner to open one." />
                </div>
            )}

            {!isLoading && plan && (
                <>
                    <div style={{ ...ui.panel, gridColumn: 'span 12' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', flexWrap: 'wrap', gap: 8 }}>
                            <h3 style={ui.h3}>Your onboarding plan</h3>
                            <span style={ui.hint}>{plan.progress.done} of {plan.progress.total} steps done</span>
                        </div>
                        <div style={{ marginTop: 8, height: 8, borderRadius: 4, background: tokens.color?.['border-600'], overflow: 'hidden' }}>
                            <div style={{ width: `${plan.progress.percent}%`, height: '100%', background: tokens.color?.success, transition: 'width 0.4s ease' }} />
                        </div>
                    </div>

                    {Object.entries(byOwner).map(([owner, items]) => (
                        <div key={owner} style={{ ...ui.panel, gridColumn: 'span 4' }}>
                            <h3 style={ui.h3}>{OWNER_LABEL[owner] || humanText(owner)}</h3>
                            <p style={ui.hint}>{items.filter((i) => String(i.status).toUpperCase() === 'DONE').length} of {items.length} done</p>
                            <div style={{ marginTop: 8 }}>
                                <PlanChecklist plan={{ items }} onComplete={handleComplete} busyId={busyId} />
                            </div>
                        </div>
                    ))}
                </>
            )}
        </div>
    );
});
OnboardingPlanModule.displayName = 'OnboardingPlanModule';
export default OnboardingPlanModule;
