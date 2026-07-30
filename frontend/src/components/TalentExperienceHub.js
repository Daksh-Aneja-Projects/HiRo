// Employee portal: Growth module.
// Real data only: /api/hr/profile/skills, /api/hr/career/path/{id}, /api/hr/feedback/peer/{id},
// /api/talent-exp/learning-modules, /api/talent-exp/learning/synthesize/{id},
// /api/talent-exp/digital-twin/xai. Empty responses render honest empty states.
import React, { useMemo, memo, useState, useCallback, useEffect } from 'react';
import { theme as tokens } from '../theme';
import { useApi } from '../hooks/useApi';
import { useToast } from '../hooks/use-toast';
import {
    getPersonalInfo, getSkillsProfile, saveSkillsProfile, getCareerPath,
    getPeerFeedback, getLearningModules, synthesizeLearningCurriculum, getDigitalTwinXai,
} from '../config/api';
import DataCard from './DataCard';
import BarChartWidget from './charts/BarChartWidget';
import { CountUp, LiveMeter } from './live/LivePrimitives';
import { ui, Btn, Loading, EmptyState, ErrorNote, fmtDate, EmployeeStyles } from './employee/shared';
import {
    Sparkles, BookOpen, Plus, X, Save, TrendingUp, Brain,
    MessageSquareQuote, GraduationCap, Target,
} from 'lucide-react';

// Turns backend feature keys like Tenure_Months into readable labels.
const humanise = (key) => String(key || '').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

const TalentExperienceHub = memo(() => {
    const { toast } = useToast();

    // The employee UUID lives on the profile record, not on the auth token payload.
    const { data: profile } = useApi(getPersonalInfo, [], true);
    const employeeId = profile?.employee_uuid;

    const { data: skillsProfile, isLoading: skillsLoading, error: skillsError, refetch: refetchSkills } = useApi(getSkillsProfile, [], true);
    const { data: career, isLoading: careerLoading, error: careerError } = useApi(getCareerPath, [employeeId], !!employeeId);
    const { data: peer, isLoading: peerLoading } = useApi(getPeerFeedback, [employeeId], !!employeeId);
    const { data: learning, isLoading: learningLoading } = useApi(getLearningModules, [], true);
    const { data: xai, isLoading: xaiLoading, error: xaiError } = useApi(getDigitalTwinXai, [], true);

    const [skills, setSkills] = useState([]);
    const [draftSkill, setDraftSkill] = useState('');
    const [isSavingSkills, setIsSavingSkills] = useState(false);

    const [targetRole, setTargetRole] = useState('');
    const [isSynthesizing, setIsSynthesizing] = useState(false);
    const [curriculum, setCurriculum] = useState(null);

    // Seed the editor from the saved profile once it arrives.
    useEffect(() => {
        if (Array.isArray(skillsProfile?.skills)) setSkills(skillsProfile.skills);
    }, [skillsProfile]);

    const savedSkills = useMemo(() => (skillsProfile?.skills || []).join('|'), [skillsProfile]);
    const isDirty = skills.join('|') !== savedSkills;

    const modules = useMemo(() => {
        const list = Array.isArray(learning) ? learning : (learning?.modules || []);
        return Array.isArray(list) ? list : [];
    }, [learning]);

    const ladder = useMemo(() => (Array.isArray(career?.path) ? career.path : []), [career]);

    const contributions = useMemo(
        () => (xai?.feature_contributions || []).map((f) => ({ name: humanise(f.feature), value: Number(f.impact) || 0 })),
        [xai]
    );

    const addSkill = useCallback(() => {
        const value = draftSkill.trim();
        if (!value) {
            toast({ title: 'Nothing to add', description: 'Type a skill before adding it.', variant: 'destructive' });
            return;
        }
        if (skills.some((s) => s.toLowerCase() === value.toLowerCase())) {
            toast({ title: 'Already on your profile', description: `${value} is already listed.`, variant: 'warning' });
            return;
        }
        setSkills((prev) => [...prev, value]);
        setDraftSkill('');
    }, [draftSkill, skills, toast]);

    const handleSaveSkills = useCallback(async () => {
        setIsSavingSkills(true);
        try {
            await saveSkillsProfile({ skills });
            toast({ title: 'Skills saved', description: `Your profile now lists ${skills.length} skill${skills.length === 1 ? '' : 's'}.`, variant: 'success' });
            refetchSkills();
        } catch (err) {
            toast({ title: 'Could not save your skills', description: err.response?.data?.detail || err.message, variant: 'destructive' });
        } finally {
            setIsSavingSkills(false);
        }
    }, [skills, toast, refetchSkills]);

    const handleSynthesize = useCallback(async (e) => {
        e.preventDefault();
        const role = targetRole.trim();
        if (!role) {
            toast({ title: 'Pick a target role', description: 'Enter the role you are aiming for so the curriculum can be built around it.', variant: 'destructive' });
            return;
        }
        if (!employeeId) {
            toast({ title: 'Profile not loaded yet', description: 'Your employee record is still loading. Try again in a moment.', variant: 'destructive' });
            return;
        }
        setIsSynthesizing(true);
        setCurriculum(null);
        try {
            const res = await synthesizeLearningCurriculum(employeeId, role);
            const body = res.data || {};
            if (body.status === 'FAILED' || body.error) {
                setCurriculum(null);
                toast({ title: 'The model could not build a curriculum', description: body.details || body.error, variant: 'destructive' });
            } else {
                const plan = body.path || body.curriculum || body.modules || [];
                setCurriculum(Array.isArray(plan) ? plan : []);
                toast({ title: 'Curriculum ready', description: `Built a learning path toward ${role}.`, variant: 'success' });
            }
        } catch (err) {
            toast({ title: 'Curriculum request failed', description: err.response?.data?.detail || err.message, variant: 'destructive' });
        } finally {
            setIsSynthesizing(false);
        }
    }, [targetRole, employeeId, toast]);

    const riskPct = (Number(xai?.prediction_score) || 0) * 100;

    return (
        <div style={ui.grid}>
            <EmployeeStyles />

            {/* Skills profile */}
            <div style={{ ...ui.panel, gridColumn: 'span 5' }}>
                <h3 style={ui.h3}>My skills</h3>
                <p style={ui.hint}>The skills on your profile feed the career and learning recommendations below.</p>

                {skillsLoading && <Loading label="Loading your skills profile" />}
                <ErrorNote error={skillsError} context="your skills profile" />

                <div style={{ display: 'flex', gap: tokens.spacing?.xs, marginTop: tokens.spacing?.md }}>
                    <input
                        style={ui.input}
                        placeholder="Add a skill, for example Policy Analysis"
                        value={draftSkill}
                        onChange={(e) => setDraftSkill(e.target.value)}
                        onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addSkill(); } }}
                    />
                    <Btn type="button" icon={Plus} onClick={addSkill} disabled={!draftSkill.trim()}>Add</Btn>
                </div>

                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7, marginTop: tokens.spacing?.md, minHeight: 30 }}>
                    {skills.length === 0 && !skillsLoading && (
                        <span style={{ ...ui.hint, marginTop: 0 }}>No skills recorded yet. Add the ones you use day to day and save.</span>
                    )}
                    {skills.map((s) => (
                        <span key={s} style={{
                            display: 'inline-flex', alignItems: 'center', gap: 6, padding: '5px 8px 5px 11px',
                            borderRadius: tokens.border?.radius?.full, background: `${tokens.color?.['accent-primary']}14`,
                            border: `1px solid ${tokens.color?.['accent-primary']}33`,
                            color: tokens.color?.['text-100'], fontSize: tokens.typography?.small?.fontSize,
                        }}>
                            {s}
                            <button type="button" aria-label={`Remove ${s}`}
                                onClick={() => setSkills((prev) => prev.filter((x) => x !== s))}
                                style={{ display: 'grid', placeItems: 'center', background: 'transparent', border: 'none', cursor: 'pointer', color: tokens.color?.['muted-500'], padding: 0 }}>
                                <X size={13} />
                            </button>
                        </span>
                    ))}
                </div>

                <div style={{ marginTop: tokens.spacing?.md }}>
                    <Btn icon={Save} tone="success" loading={isSavingSkills} disabled={!isDirty} onClick={handleSaveSkills}>
                        {isDirty ? 'Save skills' : 'Saved'}
                    </Btn>
                </div>
            </div>

            {/* Career ladder */}
            <div style={{ ...ui.panel, gridColumn: 'span 7' }}>
                <h3 style={ui.h3}>Career path</h3>
                {careerLoading && <Loading label="Loading your career path" />}
                <ErrorNote error={careerError} context="your career path" />
                {!careerLoading && !careerError && ladder.length === 0 && (
                    <EmptyState icon={Target} title="No career ladder mapped to your role yet"
                        action="Once HR maps your current role to a progression ladder, the next steps appear here." />
                )}
                {ladder.length > 0 && (
                    <>
                        <p style={ui.hint}>You are currently a {career?.current}. These are the next steps on your ladder.</p>
                        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'stretch', gap: tokens.spacing?.sm, marginTop: tokens.spacing?.md }}>
                            {ladder.map((step, i) => {
                                const isNext = i === 0;
                                return (
                                    <div key={step} style={{
                                        flex: '1 1 120px', minWidth: 0, padding: '12px 13px',
                                        borderRadius: tokens.border?.radius?.card,
                                        background: isNext ? `${tokens.color?.['accent-primary']}14` : 'rgba(255,255,255,0.03)',
                                        border: `1px solid ${isNext ? `${tokens.color?.['accent-primary']}44` : tokens.color?.['border-600']}`,
                                    }}>
                                        <div style={{ fontSize: '11px', color: tokens.color?.['muted-600'], marginBottom: 4 }}>
                                            {isNext ? 'Next step' : `Step ${i + 1}`}
                                        </div>
                                        <div style={{ color: tokens.color?.['text-100'], fontWeight: 550, fontSize: tokens.typography?.base?.fontSize }}>{step}</div>
                                    </div>
                                );
                            })}
                        </div>
                        <div style={{ marginTop: tokens.spacing?.md }}>
                            <LiveMeter pct={100 / ladder.length} color={tokens.color?.['accent-primary']} label="Progress toward the top of this ladder" />
                        </div>
                    </>
                )}
            </div>

            {/* Learning curriculum synthesis */}
            <div style={{ ...ui.panel, gridColumn: 'span 5' }}>
                <h3 style={ui.h3}>Build a learning path</h3>
                <p style={ui.hint}>The local model reads your skills and drafts a curriculum toward the role you name.</p>
                <form onSubmit={handleSynthesize} style={{ marginTop: tokens.spacing?.md }}>
                    <div style={ui.field}>
                        <label style={ui.label} htmlFor="growth-role">Target role</label>
                        <input id="growth-role" style={ui.input} value={targetRole} placeholder={ladder[0] ? `For example ${ladder[0]}` : 'For example Team Lead'}
                            onChange={(e) => setTargetRole(e.target.value)} />
                    </div>
                    <Btn type="submit" icon={Sparkles} loading={isSynthesizing} disabled={!targetRole.trim()}>
                        Generate curriculum
                    </Btn>
                </form>

                {curriculum && curriculum.length > 0 && (
                    <div className="emp-scroll" style={{ ...ui.scroller('220px'), marginTop: tokens.spacing?.md }}>
                        {curriculum.map((item, i) => (
                            <div key={i} style={ui.listRow}>
                                <div style={ui.rowMain}>
                                    <span style={ui.rowTitle}>{item.module || item.title || item.name || String(item)}</span>
                                    {(item.reason || item.status) && <span style={ui.rowMeta}>{item.reason || item.status}</span>}
                                </div>
                                <BookOpen size={15} color={tokens.color?.success} />
                            </div>
                        ))}
                    </div>
                )}
                {curriculum && curriculum.length === 0 && (
                    <EmptyState icon={GraduationCap} title="The model returned an empty plan"
                        action="Try a more specific target role, or add more skills to your profile first." />
                )}
            </div>

            {/* Catalogue of learning modules */}
            <div style={{ ...ui.panel, gridColumn: 'span 7' }}>
                <h3 style={ui.h3}>Assigned learning modules</h3>
                {learningLoading && <Loading label="Loading learning modules" />}
                {!learningLoading && modules.length === 0 && (
                    <EmptyState icon={GraduationCap} title="No learning modules assigned to you"
                        action="Nothing has been published to your account yet. Generate a curriculum on the left to plan your own path in the meantime." />
                )}
                {modules.length > 0 && (
                    <div className="emp-scroll" style={{ ...ui.scroller('220px'), marginTop: tokens.spacing?.sm }}>
                        {modules.map((m, i) => (
                            <div key={m.module_id || m.id || i} style={ui.listRow}>
                                <div style={ui.rowMain}>
                                    <span style={ui.rowTitle}>{m.title || m.name || m.module || 'Untitled module'}</span>
                                    {(m.duration || m.provider) && <span style={ui.rowMeta}>{[m.provider, m.duration].filter(Boolean).join(', ')}</span>}
                                </div>
                                <BookOpen size={15} color={tokens.color?.['accent-secondary']} />
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* Digital twin explanation */}
            <div style={{ ...ui.panel, gridColumn: 'span 5' }}>
                <h3 style={ui.h3}>What your digital twin says</h3>
                {xaiLoading && <Loading label="Loading your model explanation" />}
                <ErrorNote error={xaiError} context="your digital twin explanation" />
                {xai && (
                    <>
                        <p style={{ ...ui.hint, color: tokens.color?.['text-100'], fontSize: tokens.typography?.base?.fontSize }}>
                            {/* The model writes feature keys into its own summary; unpick them so the sentence reads naturally. */}
                            {String(xai.human_summary || '').replace(/\b\w+(?:_\w+)+\b/g, (m) => humanise(m))}
                        </p>
                        <div style={{ marginTop: tokens.spacing?.md }}>
                            <LiveMeter pct={riskPct} color={riskPct > 60 ? tokens.color?.warning : tokens.color?.success} label="Modelled retention risk" />
                        </div>
                        <p style={ui.hint}>
                            Scored by the <strong style={{ color: tokens.color?.['text-100'] }}>{humanise(xai.model_type)}</strong> model on {fmtDate(xai.generated_at)}.
                        </p>
                        <div className="emp-scroll" style={{ ...ui.scroller('170px'), marginTop: tokens.spacing?.sm }}>
                            {(xai.feature_contributions || []).map((f, i) => (
                                <div key={i} style={{ ...ui.listRow, alignItems: 'flex-start' }}>
                                    <div style={ui.rowMain}>
                                        <span style={ui.rowTitle}>{humanise(f.feature)}</span>
                                        <span style={{ ...ui.rowMeta, whiteSpace: 'normal' }}>{f.reason}</span>
                                    </div>
                                    <span style={{ flexShrink: 0, color: tokens.color?.['accent-primary'], fontVariantNumeric: 'tabular-nums', fontSize: tokens.typography?.small?.fontSize }}>
                                        <CountUp value={Number(f.impact) || 0} decimals={2} />
                                    </span>
                                </div>
                            ))}
                        </div>
                    </>
                )}
            </div>

            <div style={{ gridColumn: 'span 7' }}>
                <DataCard title="What drives your digital twin score" isChart minHeight="300px">
                    <BarChartWidget data={contributions} minHeight="260px" color={tokens.color?.['accent-secondary']}
                        label="A taller bar means that factor pushes your score further." />
                </DataCard>
            </div>

            {/* Peer feedback */}
            <div style={{ ...ui.panel, gridColumn: 'span 12' }}>
                <h3 style={ui.h3}>Peer feedback about you</h3>
                {peerLoading && <Loading label="Loading peer feedback" />}
                {!peerLoading && (!Array.isArray(peer) || peer.length === 0) && (
                    <EmptyState icon={MessageSquareQuote} title="No peer feedback recorded yet"
                        action="When colleagues submit feedback about your work it appears here, newest first." />
                )}
                {Array.isArray(peer) && peer.length > 0 && (
                    <div className="emp-scroll" style={{ ...ui.scroller('220px'), marginTop: tokens.spacing?.sm }}>
                        {peer.map((f, i) => (
                            <div key={f.feedback_id || i} style={{ ...ui.listRow, alignItems: 'flex-start' }}>
                                <div style={ui.rowMain}>
                                    <span style={{ ...ui.rowTitle, whiteSpace: 'normal' }}>{f.feedback || f.comment || 'No comment recorded'}</span>
                                    <span style={ui.rowMeta}>{fmtDate(f.submitted_at)}</span>
                                </div>
                                <TrendingUp size={15} color={tokens.color?.success} />
                            </div>
                        ))}
                    </div>
                )}
            </div>

            <div style={{ gridColumn: 'span 12', display: 'flex', alignItems: 'center', gap: 8, color: tokens.color?.['muted-600'], fontSize: tokens.typography?.small?.fontSize }}>
                <Brain size={14} /> Everything on this page is read live from your own record. Nothing here is a sample.
            </div>
        </div>
    );
});

TalentExperienceHub.displayName = 'TalentExperienceHub';
export default TalentExperienceHub;
