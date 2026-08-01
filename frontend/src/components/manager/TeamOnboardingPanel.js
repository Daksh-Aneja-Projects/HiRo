// Manager portal: how far each new joiner on the team has got, and which of the
// remaining steps are the manager's own to do. Real endpoint: GET /mss/onboarding/team.
//
// Items are owned by hr, manager or employee. A manager cannot complete another
// owner's step, so this only offers the ones that are actually theirs and says
// plainly who is holding up the rest.
import React, { memo, useCallback, useMemo, useState } from 'react';
import { theme as tokens } from '../../theme';
import { useApi } from '../../hooks/useApi';
import { useToast } from '../../hooks/use-toast';
import { getTeamOnboarding, completeTeamOnboardingItem } from '../../config/api';
import { ui, Btn, Loading, EmptyState, ErrorNote, fmtDate } from '../employee/shared';
import { useEmployeeNames } from './roster';
import { ClipboardCheck, CheckCircle, Circle, Building2, UserCog, User } from 'lucide-react';

const errText = (e) => e?.response?.data?.detail || e?.message || 'The request failed.';
const OWNER_LABEL = { hr: 'HR', manager: 'you', employee: 'the new joiner' };
const OWNER_ICON = { hr: Building2, manager: UserCog, employee: User };

const TeamOnboardingPanel = memo(() => {
    const { toast } = useToast();
    const { data, isLoading, error, refetch } = useApi(getTeamOnboarding, [], true);
    const plans = useMemo(() => data?.plans || [], [data]);
    const [busyId, setBusyId] = useState(null);

    const names = useEmployeeNames(useMemo(() => plans.map((p) => p.employee_uuid), [plans]));

    const complete = useCallback(async (itemId, planEmployee) => {
        setBusyId(itemId);
        try {
            await completeTeamOnboardingItem(itemId);
            toast({
                title: 'Step marked done',
                description: `One less thing holding up ${names[planEmployee] || 'this new joiner'}.`,
                variant: 'success',
            });
            refetch();
        } catch (err) {
            toast({ title: 'Could not mark that step done', description: errText(err), variant: 'destructive' });
        } finally {
            setBusyId(null);
        }
    }, [toast, refetch, names]);

    return (
        <div style={{ ...ui.panel, gridColumn: 'span 12' }}>
            <h3 style={ui.h3}><ClipboardCheck size={16} style={{ verticalAlign: -3, marginRight: 6 }} />New joiners on your team</h3>
            <p style={ui.hint}>Every step of each plan, and who it is waiting on. You can only tick off the steps that are yours.</p>

            {isLoading && <Loading label="Reading your team's onboarding plans" />}
            <ErrorNote error={error} context="your team's onboarding plans" />
            {!isLoading && !error && plans.length === 0 && (
                <EmptyState icon={ClipboardCheck} title="No one on your team is onboarding"
                    action="When HR opens an onboarding plan for someone who reports to you, their progress shows up here." />
            )}

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: tokens.spacing?.lg, marginTop: plans.length ? 12 : 0 }}>
                {plans.map((plan) => {
                    const pct = Number(plan.progress?.percent) || 0;
                    const mine = plan.items.filter((i) => i.owner === 'manager' && String(i.status).toUpperCase() !== 'DONE');
                    return (
                        <div key={plan.plan_id} style={{
                            minWidth: 0, padding: '14px 15px', borderRadius: 10,
                            border: `1px solid ${tokens.color?.['border-600']}`, background: 'var(--bg-input)',
                        }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
                                <span style={{ fontSize: 13.5, fontWeight: 600, color: tokens.color?.['text-100'] }}>
                                    {names[plan.employee_uuid] || 'A new joiner'}
                                </span>
                                <span style={{ fontSize: 12, color: pct === 100 ? tokens.color?.success : tokens.color?.['muted-600'] }}>
                                    {plan.progress?.done} of {plan.progress?.total} done
                                </span>
                            </div>
                            <div style={{ marginTop: 7, height: 6, borderRadius: 3, background: tokens.color?.['border-600'], overflow: 'hidden' }}>
                                <div style={{
                                    width: `${pct}%`, height: '100%', borderRadius: 3,
                                    background: pct === 100 ? tokens.color?.success : tokens.color?.['accent-primary'],
                                    transition: 'width 0.6s cubic-bezier(0.22, 1, 0.36, 1)',
                                }} />
                            </div>
                            <div style={{ fontSize: 11, color: tokens.color?.['muted-600'], marginTop: 5 }}>
                                Plan opened {fmtDate(plan.created_at)}
                                {mine.length > 0 && `, ${mine.length} step${mine.length === 1 ? '' : 's'} waiting on you`}
                            </div>

                            <div style={{ marginTop: 10 }}>
                                {plan.items.map((item) => {
                                    const done = String(item.status).toUpperCase() === 'DONE';
                                    const OwnerIcon = OWNER_ICON[item.owner] || User;
                                    const canComplete = item.owner === 'manager' && !done;
                                    return (
                                        <div key={item.item_id} style={{ display: 'flex', alignItems: 'flex-start', gap: 7, padding: '5px 0' }}>
                                            {done
                                                ? <CheckCircle size={14} color={tokens.color?.success} style={{ marginTop: 2, flexShrink: 0 }} />
                                                : <Circle size={14} color={tokens.color?.['muted-500']} style={{ marginTop: 2, flexShrink: 0 }} />}
                                            <div style={{ minWidth: 0, flexGrow: 1 }}>
                                                <div style={{
                                                    fontSize: 12.5, lineHeight: 1.4,
                                                    color: done ? tokens.color?.['muted-600'] : tokens.color?.['text-100'],
                                                    textDecoration: done ? 'line-through' : 'none',
                                                }}>{item.description}</div>
                                                <div style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, color: tokens.color?.['muted-600'], marginTop: 1 }}>
                                                    <OwnerIcon size={10} />
                                                    {done ? 'done' : `waiting on ${OWNER_LABEL[item.owner] || item.owner}`}
                                                </div>
                                            </div>
                                            {canComplete && (
                                                <Btn tone="ghost" style={{ padding: '4px 9px', fontSize: 11, flexShrink: 0 }}
                                                    loading={busyId === item.item_id}
                                                    onClick={() => complete(item.item_id, plan.employee_uuid)}>
                                                    Mark done
                                                </Btn>
                                            )}
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
});

TeamOnboardingPanel.displayName = 'TeamOnboardingPanel';
export default TeamOnboardingPanel;
