// Manager portal, inside Hiring: the two halves of filling an open requisition.
//
// Left, who already works here and could do the job. The match score is computed
// directly from skills held against skills the role needs, career-ladder
// adjacency and readiness, with no model in the score itself, so the formula is
// shown next to the results rather than hidden behind "AI match".
//
// Right, the external pipeline as a board. Stages run applied -> screen ->
// interview -> offer -> hired, and the backend refuses a skipped stage, so only
// the one legal next move is ever offered plus the reject that is legal anywhere.
//
// Real endpoints: GET /mss/hiring/requisitions/{id}/internal-matches,
// GET|POST /mss/hiring/requisitions/{id}/candidates,
// POST /mss/hiring/candidates/{id}/advance.
import React, { memo, useCallback, useMemo, useState } from 'react';
import { theme as tokens } from '../../theme';
import { useApi } from '../../hooks/useApi';
import { useToast } from '../../hooks/use-toast';
import { getInternalMatches, getCandidates, createCandidate, advanceCandidate } from '../../config/api';
import { ui, Btn, Loading, EmptyState, ErrorNote, fmtDate } from '../employee/shared';
import { CountUp } from '../live/LivePrimitives';
import { UserPlus, ArrowRight, X, Users, Sparkles, CheckCircle2, Info } from 'lucide-react';

const errText = (e) => e?.response?.data?.detail || e?.message || 'The request failed.';

// The order the backend enforces. "rejected" is legal from anywhere, and is
// therefore kept out of the board's column order.
const STAGES = ['applied', 'screen', 'interview', 'offer', 'hired'];
const STAGE_LABEL = {
    applied: 'Applied', screen: 'Screening', interview: 'Interviewing',
    offer: 'Offer out', hired: 'Hired', rejected: 'Not proceeding',
};
const STAGE_COLOR = (t) => ({
    applied: t.color?.['muted-500'], screen: t.color?.['accent-secondary'],
    interview: t.color?.['accent-primary'], offer: t.color?.warning,
    hired: t.color?.success, rejected: t.color?.danger,
});

/* -------------------------------------------------------------------------- */
/* Internal candidates                                                         */
/* -------------------------------------------------------------------------- */
const InternalMatches = memo(({ requisitionId }) => {
    const { data, isLoading, error } = useApi(getInternalMatches, [requisitionId], Boolean(requisitionId));
    const matches = useMemo(() => data?.matches || [], [data]);
    const [openId, setOpenId] = useState(null);

    return (
        <div style={{ ...ui.panel, gridColumn: 'span 5' }}>
            <h3 style={ui.h3}><Users size={16} style={{ verticalAlign: -3, marginRight: 6 }} />Who already works here</h3>
            <p style={ui.hint}>
                People whose skills and career stage fit this role. Filling it internally is faster and cheaper
                than hiring, and it is the thing most often missed because nobody goes looking.
            </p>

            {isLoading && <Loading label="Comparing every employee's skills against this role" />}
            <ErrorNote error={error} context="internal matches" />
            {!isLoading && !error && matches.length === 0 && (
                <EmptyState icon={Users} title="Nobody internal scores well against this role"
                    action="The match needs skills on record. If people's skill profiles are thin, this stays empty even when good candidates exist." />
            )}

            <div className="emp-scroll" style={{ ...ui.scroller('430px'), marginTop: matches.length ? 10 : 0 }}>
                {matches.map((m) => {
                    const open = openId === m.employee_uuid;
                    const score = Number(m.match_score) || 0;
                    return (
                        <div key={m.employee_uuid} style={{ padding: '11px 0', borderBottom: `1px solid ${tokens.color?.['border-600']}` }}>
                            <button type="button" onClick={() => setOpenId(open ? null : m.employee_uuid)}
                                style={{
                                    display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10,
                                    width: '100%', background: 'transparent', border: 'none', padding: 0,
                                    cursor: 'pointer', textAlign: 'left', flexWrap: 'wrap',
                                }}>
                                <span style={{ minWidth: 0 }}>
                                    <span style={{ display: 'block', fontSize: 13, fontWeight: 550, color: tokens.color?.['text-100'] }}>{m.name}</span>
                                    <span style={{ display: 'block', fontSize: 11.5, color: tokens.color?.['muted-600'] }}>
                                        {m.current_title}, {m.current_department}
                                    </span>
                                </span>
                                <span style={{ flexShrink: 0, textAlign: 'right' }}>
                                    <span style={{ display: 'block', fontSize: 16, fontWeight: 640, color: tokens.color?.['accent-primary'] }}>
                                        <CountUp value={score} decimals={0} suffix="%" />
                                    </span>
                                    <span style={{ display: 'block', fontSize: 10.5, color: tokens.color?.['muted-600'] }}>fit</span>
                                </span>
                            </button>

                            <div style={{ height: 5, borderRadius: 3, background: tokens.color?.['border-600'], overflow: 'hidden', marginTop: 6 }}>
                                <div style={{
                                    width: `${Math.min(100, score)}%`, height: '100%', borderRadius: 3,
                                    background: tokens.color?.['accent-primary'], opacity: 0.85,
                                    transition: 'width 0.7s cubic-bezier(0.22, 1, 0.36, 1)',
                                }} />
                            </div>

                            {open && (
                                <div style={{ marginTop: 9 }}>
                                    {m.narrative && (
                                        <p style={{ margin: 0, fontSize: 12.5, lineHeight: 1.55, color: tokens.color?.['text-100'] }}>{m.narrative}</p>
                                    )}
                                    <div style={{ marginTop: 8 }}>
                                        <div style={{ fontSize: 11, color: tokens.color?.['muted-600'], marginBottom: 4 }}>Already has</div>
                                        <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                                            {(m.matched_skills || []).map((s) => (
                                                <span key={s} style={{
                                                    fontSize: 11, padding: '2px 8px', borderRadius: 999,
                                                    color: tokens.color?.success, border: `1px solid ${tokens.color?.success}44`,
                                                    background: `${tokens.color?.success}12`,
                                                }}>{s}</span>
                                            ))}
                                        </div>
                                    </div>
                                    {(m.skill_gaps || []).length > 0 && (
                                        <div style={{ marginTop: 8 }}>
                                            <div style={{ fontSize: 11, color: tokens.color?.['muted-600'], marginBottom: 4 }}>Would need to pick up</div>
                                            <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                                                {m.skill_gaps.map((s) => (
                                                    <span key={s} style={{
                                                        fontSize: 11, padding: '2px 8px', borderRadius: 999,
                                                        color: tokens.color?.warning, border: `1px solid ${tokens.color?.warning}44`,
                                                        background: `${tokens.color?.warning}12`,
                                                    }}>{s}</span>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                    <p style={{ ...ui.hint, marginTop: 8 }}>
                                        {m.tenure_months} months here, average rating {m.average_rating}.
                                    </p>
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>

            {data?.score_formula && (
                <p style={{ ...ui.hint, marginTop: 10, display: 'flex', gap: 6 }}>
                    <Info size={12} style={{ flexShrink: 0, marginTop: 2 }} />
                    <span>{data.score_formula}</span>
                </p>
            )}
        </div>
    );
});
InternalMatches.displayName = 'InternalMatches';

/* -------------------------------------------------------------------------- */
/* External pipeline                                                           */
/* -------------------------------------------------------------------------- */
const CandidateBoard = memo(({ requisitionId }) => {
    const { toast } = useToast();
    const { data, isLoading, error, refetch } = useApi(getCandidates, [requisitionId], Boolean(requisitionId));
    const candidates = useMemo(() => data?.candidates || [], [data]);
    const summary = useMemo(() => data?.pipeline_summary || {}, [data]);

    const [form, setForm] = useState({ name: '', source: '' });
    const [adding, setAdding] = useState(false);
    const [busyId, setBusyId] = useState(null);

    const add = useCallback(async (e) => {
        e.preventDefault();
        if (!form.name.trim()) return;
        setAdding(true);
        try {
            await createCandidate(requisitionId, { name: form.name.trim(), source: form.source.trim() || undefined });
            toast({ title: 'Candidate added', description: `${form.name.trim()} is in at the applied stage.`, variant: 'success' });
            setForm({ name: '', source: '' });
            refetch();
        } catch (err) {
            toast({ title: 'Could not add that candidate', description: errText(err), variant: 'destructive' });
        } finally {
            setAdding(false);
        }
    }, [form, requisitionId, toast, refetch]);

    const move = useCallback(async (candidate, stage) => {
        setBusyId(candidate.candidate_id);
        try {
            await advanceCandidate(candidate.candidate_id, stage);
            toast({
                title: stage === 'rejected' ? 'Candidate closed out' : `Moved to ${STAGE_LABEL[stage].toLowerCase()}`,
                description: `${candidate.name} is now at ${STAGE_LABEL[stage].toLowerCase()}.`,
                variant: 'success',
            });
            refetch();
        } catch (err) {
            toast({ title: 'Could not move that candidate', description: errText(err), variant: 'destructive' });
        } finally {
            setBusyId(null);
        }
    }, [toast, refetch]);

    const byStage = useMemo(() => {
        const map = Object.fromEntries(STAGES.map((s) => [s, []]));
        map.rejected = [];
        candidates.forEach((c) => { (map[c.stage] = map[c.stage] || []).push(c); });
        return map;
    }, [candidates]);

    const active = candidates.filter((c) => c.stage !== 'rejected' && c.stage !== 'hired').length;

    return (
        <div style={{ ...ui.panel, gridColumn: 'span 7' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
                <h3 style={ui.h3}><UserPlus size={16} style={{ verticalAlign: -3, marginRight: 6 }} />The pipeline</h3>
                <span style={{ ...ui.hint, margin: 0 }}>
                    {candidates.length.toLocaleString()} on record, {active.toLocaleString()} still live
                </span>
            </div>
            <p style={ui.hint}>Stages run in order and a skipped stage is refused, so only the next legal move is offered.</p>

            <form onSubmit={add} style={{ display: 'flex', gap: 8, marginTop: 10, flexWrap: 'wrap' }}>
                <input style={{ ...ui.input, flex: '2 1 150px' }} placeholder="Candidate name" value={form.name}
                    onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))} />
                <input style={{ ...ui.input, flex: '1 1 110px' }} placeholder="Where from" value={form.source}
                    onChange={(e) => setForm((p) => ({ ...p, source: e.target.value }))} />
                <Btn type="submit" icon={UserPlus} loading={adding} disabled={!form.name.trim()}>Add</Btn>
            </form>

            {isLoading && <Loading label="Reading the pipeline" />}
            <ErrorNote error={error} context="the candidate pipeline" />
            {!isLoading && !error && candidates.length === 0 && (
                <EmptyState icon={UserPlus} title="No candidates yet"
                    action="Add the first one above. Everyone starts at applied and moves one stage at a time." />
            )}

            {candidates.length > 0 && (
                <>
                    {/* funnel across the stages, from the backend's own summary */}
                    <div style={{ display: 'flex', gap: 4, marginTop: 14, alignItems: 'flex-end', height: 54 }}>
                        {STAGES.map((s) => {
                            const n = Number(summary[s]) || 0;
                            const max = Math.max(1, ...STAGES.map((x) => Number(summary[x]) || 0));
                            return (
                                <div key={s} style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3 }}>
                                    <span style={{ fontSize: 11, fontWeight: 600, color: STAGE_COLOR(tokens)[s] }}>{n}</span>
                                    <div style={{
                                        width: '100%', height: `${Math.max(3, (n / max) * 30)}px`,
                                        background: STAGE_COLOR(tokens)[s], borderRadius: '3px 3px 0 0', opacity: 0.85,
                                        transition: 'height 0.6s cubic-bezier(0.22, 1, 0.36, 1)',
                                    }} />
                                    <span style={{ fontSize: 10, color: tokens.color?.['muted-600'], whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '100%' }}>
                                        {STAGE_LABEL[s]}
                                    </span>
                                </div>
                            );
                        })}
                    </div>

                    <div className="emp-scroll" style={{ ...ui.scroller('330px'), marginTop: 14 }}>
                        {[...STAGES, 'rejected'].map((stage) => {
                            const list = byStage[stage] || [];
                            if (list.length === 0) return null;
                            const color = STAGE_COLOR(tokens)[stage];
                            const nextStage = STAGES[STAGES.indexOf(stage) + 1];
                            return (
                                <div key={stage} style={{ marginBottom: 12 }}>
                                    <div style={{ fontSize: 11.5, fontWeight: 600, color, marginBottom: 5 }}>
                                        {STAGE_LABEL[stage]} ({list.length})
                                    </div>
                                    {list.map((c) => (
                                        <div key={c.candidate_id} style={{
                                            display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10,
                                            padding: '8px 10px', borderRadius: 7, marginBottom: 5, flexWrap: 'wrap',
                                            border: `1px solid ${tokens.color?.['border-600']}`, background: 'var(--bg-input)',
                                            borderLeft: `3px solid ${color}`,
                                        }}>
                                            <div style={{ minWidth: 0 }}>
                                                <div style={{ fontSize: 12.5, fontWeight: 550, color: tokens.color?.['text-100'] }}>{c.name}</div>
                                                <div style={{ fontSize: 11, color: tokens.color?.['muted-600'] }}>
                                                    {c.source && c.source !== 'unspecified' ? `${c.source}, ` : ''}
                                                    added {fmtDate(c.created_at)}
                                                    {(c.stage_history || []).length > 1 && `, ${c.stage_history.length} stages so far`}
                                                </div>
                                            </div>
                                            <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
                                                {nextStage && (
                                                    <Btn tone="ghost" icon={nextStage === 'hired' ? CheckCircle2 : ArrowRight}
                                                        style={{ padding: '4px 10px', fontSize: 11 }}
                                                        loading={busyId === c.candidate_id}
                                                        onClick={() => move(c, nextStage)}>
                                                        {STAGE_LABEL[nextStage]}
                                                    </Btn>
                                                )}
                                                {stage !== 'rejected' && stage !== 'hired' && (
                                                    <Btn tone="ghost" icon={X}
                                                        style={{ padding: '4px 9px', fontSize: 11, color: tokens.color?.danger }}
                                                        loading={busyId === c.candidate_id}
                                                        onClick={() => move(c, 'rejected')}>
                                                        Close out
                                                    </Btn>
                                                )}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            );
                        })}
                    </div>
                </>
            )}
        </div>
    );
});
CandidateBoard.displayName = 'CandidateBoard';

/** Both halves for one requisition, shown once a requisition is chosen. */
const HiringPipeline = memo(({ requisition }) => {
    if (!requisition) {
        return (
            <div style={{ ...ui.panel, gridColumn: 'span 12' }}>
                <EmptyState icon={Sparkles} title="Pick a requisition to work on it"
                    action="Choosing an open requisition shows who internally could do the job, and the candidate pipeline for it." />
            </div>
        );
    }
    return (
        <>
            <div style={{ ...ui.panel, gridColumn: 'span 12', paddingTop: 12, paddingBottom: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
                    <span style={{ fontSize: 14, fontWeight: 600, color: tokens.color?.['text-100'] }}>
                        Filling: {requisition.title}
                    </span>
                    <span style={{ fontSize: 12, color: tokens.color?.['muted-600'] }}>
                        {requisition.department}, {requisition.headcount} to hire, raised {fmtDate(requisition.created_at)}
                    </span>
                </div>
            </div>
            <InternalMatches requisitionId={requisition.requisition_id} />
            <CandidateBoard requisitionId={requisition.requisition_id} />
        </>
    );
});

HiringPipeline.displayName = 'HiringPipeline';
export default HiringPipeline;
