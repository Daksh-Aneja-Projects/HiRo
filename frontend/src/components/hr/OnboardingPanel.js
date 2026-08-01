// Onboarding admin, embedded in the Talent Insights tab: build a new hire's
// onboarding plan from the default template plus any extra items. There is no
// "list all plans" endpoint for HR, so this shows the plan just created and a
// session-local history, honestly labeled as such.
import React, { useState, useCallback } from 'react';
import { theme as tokens } from '../../theme';
import { createOnboardingPlan } from '../../config/api';
import { useToast } from '../../hooks/use-toast';
import { ui, Btn, EmptyState } from '../employee/shared';
import { UserPlus, Plus, X, ClipboardList } from 'lucide-react';

const errText = (e) => e?.response?.data?.detail || e?.message || 'The request failed.';
const OWNERS = ['hr', 'manager', 'employee'];

const OnboardingPanel = () => {
    const { toast } = useToast();
    const [employeeUuid, setEmployeeUuid] = useState('');
    const [extraItems, setExtraItems] = useState([]);
    const [creating, setCreating] = useState(false);
    const [created, setCreated] = useState(null);
    const [history, setHistory] = useState([]);

    const addItem = () => setExtraItems((p) => [...p, { description: '', owner: 'hr', due_offset_days: 3 }]);
    const removeItem = (i) => setExtraItems((p) => p.filter((_, idx) => idx !== i));
    const updateItem = (i, field, value) => setExtraItems((p) => p.map((it, idx) => (idx === i ? { ...it, [field]: value } : it)));

    const submit = useCallback(async (e) => {
        e.preventDefault();
        if (!employeeUuid.trim()) {
            toast({ title: 'Enter the employee id', description: 'Whose plan is this for, e.g. EMP-014.', variant: 'warning' });
            return;
        }
        const cleanExtras = extraItems.filter((it) => it.description.trim());
        setCreating(true);
        try {
            const res = await createOnboardingPlan(employeeUuid.trim(), cleanExtras.length ? cleanExtras : undefined);
            setCreated(res.data);
            setHistory((prev) => [{ plan_id: res.data.plan_id, employee_uuid: res.data.employee_uuid }, ...prev].slice(0, 8));
            toast({ title: 'Onboarding plan created', description: `${res.data.items.length} items scheduled for ${res.data.employee_uuid}.`, variant: 'success' });
            setEmployeeUuid('');
            setExtraItems([]);
        } catch (err) {
            toast({ title: 'Could not create the plan', description: errText(err), variant: 'destructive' });
        } finally {
            setCreating(false);
        }
    }, [employeeUuid, extraItems, toast]);

    return (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(12, 1fr)', gap: tokens.spacing?.lg, marginTop: tokens.spacing?.lg }}>
            <div style={{ ...ui.panel, gridColumn: 'span 5' }}>
                <h3 style={ui.h3}><UserPlus size={16} style={{ verticalAlign: -3, marginRight: 6 }} color={tokens.color?.['accent-primary']} />Start an onboarding plan</h3>
                <p style={ui.hint}>The default template (equipment, access, orientation, manager welcome) is applied automatically. Add anything specific to this hire below.</p>
                <form onSubmit={submit} style={{ marginTop: 10 }}>
                    <div style={ui.field}>
                        <label style={ui.label} htmlFor="ob-emp">New hire's employee id</label>
                        <input id="ob-emp" style={ui.input} value={employeeUuid} onChange={(e) => setEmployeeUuid(e.target.value)} placeholder="e.g. EMP-014" required />
                    </div>

                    {extraItems.map((it, i) => (
                        <div key={i} style={{ display: 'flex', gap: 6, marginBottom: 8, alignItems: 'center' }}>
                            <input style={{ ...ui.input, flex: 1 }} value={it.description}
                                onChange={(e) => updateItem(i, 'description', e.target.value)} placeholder="Extra task, e.g. Order a standing desk" />
                            <select style={{ ...ui.input, width: 100 }} value={it.owner} onChange={(e) => updateItem(i, 'owner', e.target.value)}>
                                {OWNERS.map((o) => <option key={o} value={o}>{o}</option>)}
                            </select>
                            <input type="number" min="0" style={{ ...ui.input, width: 66 }} value={it.due_offset_days}
                                onChange={(e) => updateItem(i, 'due_offset_days', e.target.value)} title="Days after start" />
                            <button type="button" onClick={() => removeItem(i)} style={{ background: 'none', border: 'none', color: tokens.color?.danger, cursor: 'pointer' }}>
                                <X size={15} />
                            </button>
                        </div>
                    ))}
                    <button type="button" onClick={addItem} style={{ background: 'none', border: 'none', color: tokens.color?.['accent-primary'], cursor: 'pointer', fontSize: 12.5, display: 'flex', alignItems: 'center', gap: 4, marginBottom: 12 }}>
                        <Plus size={13} /> Add an extra item
                    </button>

                    <div>
                        <Btn type="submit" icon={UserPlus} loading={creating}>{creating ? 'Creating' : 'Create plan'}</Btn>
                    </div>
                </form>

                {history.length > 0 && (
                    <div style={{ marginTop: 16, paddingTop: 12, borderTop: `1px solid ${tokens.color?.['border-600']}` }}>
                        <p style={{ ...ui.hint, margin: '0 0 6px' }}>Created this session:</p>
                        {history.map((h) => (
                            <div key={h.plan_id} style={{ fontSize: 12, color: tokens.color?.['muted-500'] }}>{h.employee_uuid} - {h.plan_id}</div>
                        ))}
                    </div>
                )}
            </div>

            <div style={{ ...ui.panel, gridColumn: 'span 7' }}>
                <h3 style={ui.h3}>Plan just created</h3>
                {!created ? (
                    <EmptyState icon={ClipboardList} title="No plan created yet" action="Create one on the left to see its checklist here." />
                ) : (
                    <div style={ui.scroller('340px')} className="emp-scroll">
                        <p style={{ ...ui.hint, margin: '0 0 10px' }}>{created.plan_id} for {created.employee_uuid}</p>
                        {created.items.map((it) => (
                            <div key={it.item_id} style={ui.listRow}>
                                <div style={ui.rowMain}>
                                    <span style={ui.rowTitle}>{it.description}</span>
                                    <span style={ui.rowMeta}>Owned by {it.owner}, due {it.due_offset_days} day{it.due_offset_days === 1 ? '' : 's'} after start</span>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
};

export default OnboardingPanel;
