// Compensation review cycles: create a cycle, adjust suggested merit % inline,
// finalize. Every cycle on record is listed from GET /hr/comp/cycles.
import React, { useMemo, useState, useCallback } from 'react';
import { theme as tokens } from '../../theme';
import {
    createCompCycle, listCompCycles, getCompCycle, adjustCompCycleLine, finalizeCompCycle, getAnalyticsDepartments,
} from '../../config/api';
import { useApi } from '../../hooks/useApi';
import { useToast } from '../../hooks/use-toast';
import { ui, Btn, Loading, EmptyState, ErrorNote, money } from '../employee/shared';
import { PlusCircle, FolderOpen, CheckCircle2, AlertTriangle, Save } from 'lucide-react';

const errText = (e) => e?.response?.data?.detail || e?.message || 'The request failed.';
const LINES_SHOWN = 60;

const CompCyclesPanel = () => {
    const { toast } = useToast();
    const { data: deptData } = useApi(getAnalyticsDepartments, [], true);
    const departments = deptData?.departments || [];

    const [department, setDepartment] = useState('');
    const [budgetPct, setBudgetPct] = useState('3.0');
    const [creating, setCreating] = useState(false);

    const [activeCycleId, setActiveCycleId] = useState(null);
    const { data: cycleList, isLoading: listLoading, error: listError, refetch: refetchList } =
        useApi(listCompCycles, [], true);
    const cycles = useMemo(() => cycleList?.cycles || [], [cycleList]);

    const { data: cycle, isLoading: cycleLoading, error: cycleError, refetch: refetchCycle } =
        useApi(getCompCycle, [activeCycleId], Boolean(activeCycleId));

    const [edits, setEdits] = useState({});
    const [savingLine, setSavingLine] = useState(null);
    const [finalizing, setFinalizing] = useState(false);
    const [budgetProblem, setBudgetProblem] = useState(null);
    const [showAllLines, setShowAllLines] = useState(false);

    const lines = useMemo(() => cycle?.lines || [], [cycle]);
    const visibleLines = showAllLines ? lines : lines.slice(0, LINES_SHOWN);

    const openCycle = useCallback((id) => {
        setBudgetProblem(null);
        setEdits({});
        setShowAllLines(false);
        setActiveCycleId(id);
    }, []);

    const create = useCallback(async (e) => {
        e.preventDefault();
        if (!department) {
            toast({ title: 'Pick a department', description: 'A comp cycle is scoped to one department.', variant: 'warning' });
            return;
        }
        setCreating(true);
        try {
            const res = await createCompCycle(department, parseFloat(budgetPct) || 0);
            toast({
                title: 'Cycle created',
                description: `${res.data.lines_created.toLocaleString()} people in ${department} were pre-filled with a suggested merit increase.`,
                variant: 'success',
            });
            refetchList();
            openCycle(res.data.cycle_id);
        } catch (err) {
            toast({ title: 'Could not create the cycle', description: errText(err), variant: 'destructive' });
        } finally {
            setCreating(false);
        }
    }, [department, budgetPct, toast, openCycle, refetchList]);

    const saveLine = useCallback(async (line) => {
        const pct = parseFloat(edits[line.id]);
        if (Number.isNaN(pct)) return;
        setSavingLine(line.id);
        try {
            await adjustCompCycleLine(cycle.cycle_id, line.id, pct);
            toast({ title: 'Line updated', description: `${line.employee_name} set to ${pct}%.`, variant: 'success' });
            refetchCycle();
        } catch (err) {
            toast({ title: 'Could not save that line', description: errText(err), variant: 'destructive' });
        } finally {
            setSavingLine(null);
        }
    }, [edits, cycle, toast, refetchCycle]);

    const finalize = useCallback(async () => {
        if (!window.confirm(`Finalize "${cycle.name}"? This applies every proposed increase as a real pay change.`)) return;
        setFinalizing(true);
        setBudgetProblem(null);
        try {
            const res = await finalizeCompCycle(cycle.cycle_id);
            toast({
                title: 'Cycle finalized',
                description: `${res.data.lines_applied.toLocaleString()} pay changes applied, weighted increase ${res.data.weighted_increase_pct}%.`,
                variant: 'success',
            });
            refetchCycle();
            refetchList();
        } catch (err) {
            if (err.response?.status === 409) {
                setBudgetProblem(errText(err));
            } else {
                toast({ title: 'Could not finalize the cycle', description: errText(err), variant: 'destructive' });
            }
        } finally {
            setFinalizing(false);
        }
    }, [cycle, toast, refetchCycle, refetchList]);

    return (
        <div style={ui.grid} className="portal-grid">
            <div style={{ ...ui.panel, gridColumn: 'span 4' }}>
                <h3 style={ui.h3}><PlusCircle size={16} style={{ verticalAlign: -3, marginRight: 6 }} color={tokens.color?.['accent-primary']} />Start a review cycle</h3>
                <p style={ui.hint}>Every person in the department is pre-filled with a suggested merit increase based on rating, pay position and attrition risk.</p>
                <form onSubmit={create} style={{ marginTop: 10 }}>
                    <div style={ui.field}>
                        <label style={ui.label} htmlFor="cyc-dept">Department</label>
                        <select id="cyc-dept" style={ui.input} value={department} onChange={(e) => setDepartment(e.target.value)} required>
                            <option value="">Choose a department</option>
                            {departments.map((d) => <option key={d} value={d}>{d}</option>)}
                        </select>
                    </div>
                    <div style={ui.field}>
                        <label style={ui.label} htmlFor="cyc-budget">Budget, as a percent of payroll</label>
                        <input id="cyc-budget" type="number" step="0.1" min="0" style={ui.input} value={budgetPct}
                            onChange={(e) => setBudgetPct(e.target.value)} required />
                    </div>
                    <Btn type="submit" icon={PlusCircle} loading={creating}>{creating ? 'Creating' : 'Create cycle'}</Btn>
                </form>

                <div style={{ marginTop: 18, paddingTop: 14, borderTop: `1px solid ${tokens.color?.['border-600']}` }}>
                    <h4 style={{ ...ui.h3, fontSize: 13 }}><FolderOpen size={14} style={{ verticalAlign: -2, marginRight: 5 }} />Cycles on record</h4>
                    {listLoading && <Loading label="Reading the cycles on record" />}
                    <ErrorNote error={listError} context="the list of compensation cycles" />
                    {!listLoading && !listError && cycles.length === 0 && (
                        <p style={ui.hint}>No compensation cycle has been created yet. Start one above.</p>
                    )}
                    {cycles.map((c) => {
                        const isOpen = c.cycle_id === activeCycleId;
                        return (
                            <button key={c.cycle_id} type="button" onClick={() => openCycle(c.cycle_id)}
                                style={{
                                    display: 'block', width: '100%', textAlign: 'left', cursor: 'pointer',
                                    background: isOpen ? `${tokens.color?.['accent-primary']}14` : 'transparent',
                                    border: 'none', borderRadius: 6, padding: '7px 8px', marginTop: 4,
                                }}>
                                <span style={{ display: 'block', fontSize: 12.5, fontWeight: 550, color: isOpen ? tokens.color?.['accent-primary'] : tokens.color?.['text-100'] }}>
                                    {c.name || c.department}
                                </span>
                                <span style={{ display: 'block', fontSize: 11.5, color: tokens.color?.['muted-600'] }}>
                                    {c.department}, budget {c.budget_pct}% of payroll, {c.status === 'finalized' ? 'finalized' : 'still in draft'}
                                </span>
                            </button>
                        );
                    })}
                </div>
            </div>

            <div style={{ ...ui.panel, gridColumn: 'span 8' }}>
                {!activeCycleId && (
                    <EmptyState icon={FolderOpen} title="No cycle open" action="Create a cycle or open one by id to see its lines." />
                )}
                {activeCycleId && cycleLoading && !cycle && <Loading label="Reading the cycle" />}
                {activeCycleId && <ErrorNote error={cycleError} context="that comp cycle" />}

                {cycle && (
                    <>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 10, flexWrap: 'wrap' }}>
                            <div>
                                <h3 style={ui.h3}>{cycle.name}</h3>
                                <p style={ui.hint}>
                                    {cycle.department}, budget {Number(cycle.budget_pct).toFixed(2)}%, status {String(cycle.status).toLowerCase()},
                                    {' '}{lines.length.toLocaleString()} people
                                </p>
                            </div>
                            <Btn icon={CheckCircle2} loading={finalizing} disabled={cycle.status === 'finalized'} onClick={finalize}>
                                {cycle.status === 'finalized' ? 'Finalized' : (finalizing ? 'Finalizing' : 'Finalize cycle')}
                            </Btn>
                        </div>

                        {budgetProblem && (
                            <div style={{ marginTop: 12, padding: '12px 14px', borderRadius: 8, border: `1px solid ${tokens.color?.danger}33`, background: `${tokens.color?.danger}0f`, display: 'flex', gap: 10 }}>
                                <AlertTriangle size={16} color={tokens.color?.danger} style={{ flexShrink: 0, marginTop: 1 }} />
                                <div>
                                    <strong style={{ fontSize: 13, color: tokens.color?.danger }}>The budget does not cover this yet</strong>
                                    <p style={{ margin: '4px 0 0', fontSize: 12.5, color: tokens.color?.danger, lineHeight: 1.55 }}>{budgetProblem}</p>
                                </div>
                            </div>
                        )}

                        <div style={{ ...ui.scroller('440px'), marginTop: 14 }} className="emp-scroll">
                            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12.5 }}>
                                <thead>
                                    <tr style={{ textAlign: 'left', color: tokens.color?.['muted-600'], borderBottom: `1px solid ${tokens.color?.['border-600']}` }}>
                                        <th style={{ padding: '6px 8px' }}>Person</th>
                                        <th style={{ padding: '6px 8px' }}>Current</th>
                                        <th style={{ padding: '6px 8px' }}>Proposed %</th>
                                        <th style={{ padding: '6px 8px' }}>New pay</th>
                                        <th style={{ padding: '6px 8px' }}>Status</th>
                                        <th style={{ padding: '6px 8px' }} />
                                    </tr>
                                </thead>
                                <tbody>
                                    {visibleLines.map((l) => (
                                        <tr key={l.id} style={{ borderBottom: `1px solid ${tokens.color?.['border-600']}` }}>
                                            <td style={{ padding: '6px 8px', color: tokens.color?.['text-100'] }}>{l.employee_name}</td>
                                            <td style={{ padding: '6px 8px', color: tokens.color?.['muted-500'] }}>{money(l.current_comp)}</td>
                                            <td style={{ padding: '6px 8px' }}>
                                                <input
                                                    type="number" step="0.1"
                                                    value={edits[l.id] ?? l.proposed_pct}
                                                    onChange={(e) => setEdits((p) => ({ ...p, [l.id]: e.target.value }))}
                                                    style={{ ...ui.input, width: 72, padding: '4px 7px' }}
                                                    disabled={cycle.status === 'finalized'}
                                                />
                                            </td>
                                            <td style={{ padding: '6px 8px', color: tokens.color?.success }}>{money(l.proposed_new_comp)}</td>
                                            <td style={{ padding: '6px 8px', color: tokens.color?.['muted-600'], textTransform: 'capitalize' }}>{l.status}</td>
                                            <td style={{ padding: '6px 8px' }}>
                                                {cycle.status !== 'finalized' && (
                                                    <button type="button" onClick={() => saveLine(l)} disabled={savingLine === l.id}
                                                        style={{ background: 'none', border: 'none', color: tokens.color?.['accent-primary'], cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4 }}>
                                                        <Save size={13} /> {savingLine === l.id ? 'Saving' : 'Save'}
                                                    </button>
                                                )}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                        {lines.length > LINES_SHOWN && (
                            <button type="button" onClick={() => setShowAllLines((v) => !v)}
                                style={{ marginTop: 10, background: 'none', border: 'none', color: tokens.color?.['accent-primary'], cursor: 'pointer', fontSize: 12.5 }}>
                                {showAllLines ? `Show only the first ${LINES_SHOWN}` : `Show all ${lines.length.toLocaleString()} lines`}
                            </button>
                        )}
                    </>
                )}
            </div>
        </div>
    );
};

export default CompCyclesPanel;
