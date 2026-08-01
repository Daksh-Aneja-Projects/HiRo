// Succession tab: nominate a successor, see the plan grouped by role, and a
// 3x3 nine-box grid people can click into. The nine-box's "potential" axis is a
// documented heuristic on the backend, not a measurement, so its disclaimer is
// always shown, never hidden behind a tooltip.
import React, { useMemo, useState, useCallback } from 'react';
import { theme as tokens } from '../../theme';
import { getSuccessionPlan, getNineBox, createSuccessionNomination } from '../../config/api';
import { useApi } from '../../hooks/useApi';
import { useToast } from '../../hooks/use-toast';
import { ui, Btn, Loading, EmptyState, ErrorNote, fmtDate } from '../employee/shared';
import { UserPlus, Users, Info, Grid3x3, X } from 'lucide-react';

const READINESS_TEXT = { ready_now: 'Ready now', ready_soon: 'Ready in 1-2 years', develop: 'Needs development' };
const readinessText = (r) => READINESS_TEXT[r] || r || 'Not rated';
const readinessColor = (r) => {
    if (r === 'ready_now') return tokens.color?.success;
    if (r === 'ready_soon') return tokens.color?.warning;
    return tokens.color?.['muted-500'];
};

const errText = (e) => e?.response?.data?.detail || e?.message || 'The request failed.';

const NineBoxGrid = ({ data }) => {
    const [openCell, setOpenCell] = useState(null);
    const PERF = ['High', 'Solid', 'Low'];
    const POT = ['Low', 'Medium', 'High'];
    const cellFor = (p, q) => (data?.cells || []).find((c) => c.performance === p && c.potential === q);
    const max = Math.max(1, ...(data?.cells || []).map((c) => c.count || 0));

    return (
        <div>
            <div style={{ display: 'grid', gridTemplateColumns: 'auto repeat(3, 1fr)', gap: 6, maxWidth: 560 }}>
                <div />
                {POT.map((q) => (
                    <div key={q} style={{ textAlign: 'center', fontSize: 11, color: tokens.color?.['muted-600'], fontWeight: 600 }}>
                        {q} potential
                    </div>
                ))}
                {PERF.map((p) => (
                    <React.Fragment key={p}>
                        <div style={{ display: 'flex', alignItems: 'center', fontSize: 11, color: tokens.color?.['muted-600'], fontWeight: 600, writingMode: 'vertical-rl', transform: 'rotate(180deg)', justifyContent: 'center' }}>
                            {p} performance
                        </div>
                        {POT.map((q) => {
                            const cell = cellFor(p, q);
                            const count = cell?.count || 0;
                            const intensity = 0.08 + 0.55 * (count / max);
                            const open = openCell === `${p}:${q}`;
                            return (
                                <button
                                    key={q}
                                    type="button"
                                    onClick={() => setOpenCell(open ? null : `${p}:${q}`)}
                                    style={{
                                        minHeight: 74, border: `1px solid ${open ? tokens.color?.['accent-primary'] : 'var(--border-subtle)'}`,
                                        borderRadius: 8, background: `rgba(94,106,210,${intensity})`, cursor: count ? 'pointer' : 'default',
                                        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 2,
                                        color: tokens.color?.['text-100'], fontFamily: 'inherit',
                                    }}
                                >
                                    <span style={{ fontSize: 20, fontWeight: 650, fontVariantNumeric: 'tabular-nums' }}>{count.toLocaleString()}</span>
                                    <span style={{ fontSize: 10.5, color: tokens.color?.['muted-600'] }}>{count === 1 ? 'person' : 'people'}</span>
                                </button>
                            );
                        })}
                    </React.Fragment>
                ))}
            </div>

            {openCell && (() => {
                const [p, q] = openCell.split(':');
                const cell = cellFor(p, q);
                return (
                    <div style={{ ...ui.panel, marginTop: 14, background: tokens.color?.['panel-700'] }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <h4 style={{ margin: 0, fontSize: 13.5, color: tokens.color?.['text-100'] }}>{p} performance, {q} potential ({cell?.count || 0} people)</h4>
                            <button type="button" onClick={() => setOpenCell(null)} style={{ background: 'none', border: 'none', color: tokens.color?.['muted-500'], cursor: 'pointer' }}>
                                <X size={16} />
                            </button>
                        </div>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 10, maxHeight: 200, overflowY: 'auto' }} className="emp-scroll">
                            {(cell?.people || []).map((person) => (
                                <span key={person.employee_uuid} title={`${person.department} - ${person.job_title}`} style={{
                                    fontSize: 12, padding: '5px 10px', borderRadius: 999, background: tokens.color?.['panel-800'],
                                    border: `1px solid ${tokens.color?.['border-600']}`, color: tokens.color?.['text-100'],
                                }}>
                                    {person.name}
                                </span>
                            ))}
                            {!cell?.people?.length && <span style={{ ...ui.hint, margin: 0 }}>No sample listed for this cell.</span>}
                        </div>
                    </div>
                );
            })()}
        </div>
    );
};

const SuccessionPanel = () => {
    const { toast } = useToast();
    const { data: plan, isLoading: planLoading, error: planError, refetch: refetchPlan } = useApi(getSuccessionPlan, [], true);
    const { data: nineBox, isLoading: nbLoading, error: nbError } = useApi(getNineBox, [], true);

    const [form, setForm] = useState({ role_or_person_uuid: '', nominee_uuid: '', readiness: 'ready_soon', rationale: '' });
    const [submitting, setSubmitting] = useState(false);

    const roles = useMemo(() => plan?.roles || [], [plan]);
    const deptReadiness = useMemo(() => Object.entries(plan?.department_readiness || {}), [plan]);

    const submit = useCallback(async (e) => {
        e.preventDefault();
        if (!form.role_or_person_uuid.trim() || !form.nominee_uuid.trim() || !form.rationale.trim()) {
            toast({ title: 'Fill in every field', description: 'A nomination needs the role or person, the nominee, and a rationale.', variant: 'warning' });
            return;
        }
        setSubmitting(true);
        try {
            await createSuccessionNomination({
                role_or_person_uuid: form.role_or_person_uuid.trim(),
                nominee_uuid: form.nominee_uuid.trim(),
                readiness: form.readiness,
                rationale: form.rationale.trim(),
            });
            toast({ title: 'Nomination recorded', description: 'It now appears in the succession plan below.', variant: 'success' });
            setForm({ role_or_person_uuid: '', nominee_uuid: '', readiness: 'ready_soon', rationale: '' });
            refetchPlan();
        } catch (err) {
            toast({ title: 'Could not record the nomination', description: errText(err), variant: 'destructive' });
        } finally {
            setSubmitting(false);
        }
    }, [form, toast, refetchPlan]);

    return (
        <div style={ui.grid} className="portal-grid">
            <div style={{ ...ui.panel, gridColumn: 'span 4' }}>
                <h3 style={ui.h3}><UserPlus size={16} style={{ verticalAlign: -3, marginRight: 6 }} color={tokens.color?.['accent-primary']} />Nominate a successor</h3>
                <p style={ui.hint}>Identify a critical role or the person who holds it, and who could step up.</p>
                <form onSubmit={submit} style={{ marginTop: 10 }}>
                    <div style={ui.field}>
                        <label style={ui.label} htmlFor="succ-role">Role or the person who holds it</label>
                        <input id="succ-role" style={ui.input} value={form.role_or_person_uuid}
                            onChange={(e) => setForm((p) => ({ ...p, role_or_person_uuid: e.target.value }))}
                            placeholder="Employee id of the role holder, e.g. EMP-014" />
                    </div>
                    <div style={ui.field}>
                        <label style={ui.label} htmlFor="succ-nominee">Nominee</label>
                        <input id="succ-nominee" style={ui.input} value={form.nominee_uuid}
                            onChange={(e) => setForm((p) => ({ ...p, nominee_uuid: e.target.value }))}
                            placeholder="Employee id of the successor, e.g. EMP-021" />
                    </div>
                    <div style={ui.field}>
                        <label style={ui.label} htmlFor="succ-readiness">Readiness</label>
                        <select id="succ-readiness" style={ui.input} value={form.readiness}
                            onChange={(e) => setForm((p) => ({ ...p, readiness: e.target.value }))}>
                            {Object.entries(READINESS_TEXT).map(([v, t]) => <option key={v} value={v}>{t}</option>)}
                        </select>
                    </div>
                    <div style={ui.field}>
                        <label style={ui.label} htmlFor="succ-rationale">Why this person</label>
                        <textarea id="succ-rationale" style={{ ...ui.input, minHeight: 90, resize: 'vertical' }}
                            value={form.rationale} onChange={(e) => setForm((p) => ({ ...p, rationale: e.target.value }))}
                            placeholder="What makes them a strong bench candidate for this role." />
                    </div>
                    <Btn type="submit" icon={UserPlus} loading={submitting}>{submitting ? 'Recording' : 'Record nomination'}</Btn>
                </form>
            </div>

            <div style={{ ...ui.panel, gridColumn: 'span 8' }}>
                <h3 style={ui.h3}>Succession plan by role</h3>
                <p style={ui.hint}>Every nomination on record, grouped by the role it covers.</p>
                {planLoading && !plan && <Loading label="Reading the succession plan" />}
                <ErrorNote error={planError} context="the succession plan" />
                {!planLoading && !planError && roles.length === 0 && (
                    <EmptyState icon={Users} title="No nominations recorded yet" action="Use the form on the left to nominate the first successor." />
                )}
                <div style={ui.scroller('420px')} className="emp-scroll">
                    {roles.map((r) => (
                        <div key={r.role_or_person} style={{ ...ui.listRow, alignItems: 'flex-start', flexDirection: 'column', gap: 6 }}>
                            <span style={{ ...ui.rowTitle, whiteSpace: 'normal' }}>Role held by {r.role_or_person}</span>
                            {r.nominations.map((n) => (
                                <div key={n.nomination_id} style={{ fontSize: 12.5, color: tokens.color?.['muted-500'], lineHeight: 1.55, paddingLeft: 4 }}>
                                    <strong style={{ color: tokens.color?.['text-100'] }}>{n.nominee_name || n.nominee_uuid}</strong>
                                    {' - '}
                                    <span style={{ color: readinessColor(n.readiness) }}>{readinessText(n.readiness)}</span>
                                    {' - '}{n.rationale}
                                    <span style={{ display: 'block', color: tokens.color?.['muted-600'] }}>
                                        Nominated by {n.nominated_by} on {fmtDate(n.created_at)}
                                    </span>
                                </div>
                            ))}
                        </div>
                    ))}
                </div>
            </div>

            {deptReadiness.length > 0 && (
                <div style={{ ...ui.panel, gridColumn: 'span 12' }}>
                    <h3 style={ui.h3}>Bench cover by department</h3>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 10, marginTop: 10 }}>
                        {deptReadiness.map(([dept, r]) => (
                            <div key={dept} style={{ ...ui.panel, background: tokens.color?.['panel-700'] }}>
                                <strong style={{ fontSize: 13, color: tokens.color?.['text-100'] }}>{dept}</strong>
                                <p style={{ ...ui.hint, margin: '4px 0 0' }}>{r.summary}</p>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            <div style={{ ...ui.panel, gridColumn: 'span 12' }}>
                <h3 style={ui.h3}><Grid3x3 size={16} style={{ verticalAlign: -3, marginRight: 6 }} color={tokens.color?.['accent-primary']} />Nine-box: performance vs potential</h3>
                <p style={ui.hint}>{nineBox?.scope || 'The leadership pipeline: senior-band roles and the rungs just below them.'}</p>
                {nbLoading && !nineBox && <Loading label="Building the nine-box" />}
                <ErrorNote error={nbError} context="the nine-box grid" />
                {nineBox && (
                    <>
                        <NineBoxGrid data={nineBox} />
                        <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start', marginTop: 14, padding: '10px 12px', borderRadius: 8, background: `${tokens.color?.warning}0f`, border: `1px solid ${tokens.color?.warning}33` }}>
                            <Info size={15} color={tokens.color?.warning} style={{ flexShrink: 0, marginTop: 1 }} />
                            <p style={{ margin: 0, fontSize: 12, color: tokens.color?.warning, lineHeight: 1.5 }}>
                                {nineBox.heuristic_note || 'Potential is a heuristic, not a measurement. Treat placement as a starting conversation, not a verdict.'}
                            </p>
                        </div>
                    </>
                )}
            </div>
        </div>
    );
};

export default SuccessionPanel;
