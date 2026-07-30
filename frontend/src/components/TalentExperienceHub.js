// /frontend/src/components/TalentExperienceHub.js - FINAL PRODUCTION-READY REPLACEMENT
import React, { useMemo, memo, useState, useCallback } from 'react';
import { theme as tokens } from '../theme';
import { useAuth } from '../contexts/AuthContext';
import { useApi } from '../hooks/useApi';
import { useToast } from '../hooks/use-toast';
import { synthesizeLearningCurriculum, getLearningModules, getDigitalTwinXai } from '../config/api';
import { Zap, Loader2, BookOpen, User, Send, TrendingUp, AlertTriangle } from 'lucide-react';

const TalentExperienceHub = memo(() => {
    const { user } = useAuth();
    const { toast } = useToast();
    const [targetRole, setTargetRole] = useState('Senior HRBP');
    const [isSynthesizing, setIsSynthesizing] = useState(false);
    const [curriculum, setCurriculum] = useState(null);
    
    // CRITICAL API INTEGRATION 1: Fetch Learning Modules (Static list)
    const { data: modules, isLoading: isModulesLoading } = useApi(getLearningModules, [], true, []);
    
    // CRITICAL API INTEGRATION 2: Fetch Digital Twin XAI (for context)
    const { data: dtXai, isLoading: isXaiLoading } = useApi(getDigitalTwinXai, [], true, {});


    // CRITICAL: Handle Learning Path Synthesis
    const handleSynthesize = useCallback(async (e) => {
        e.preventDefault();
        if (!targetRole || isSynthesizing) return;

        setIsSynthesizing(true);
        setCurriculum(null);

        try {
            // CRITICAL API INTEGRATION 3: Synthesize learning path based on DT data
            const response = await synthesizeLearningCurriculum(user.id, targetRole);
            
            // Assuming response.data contains { path: [{ module: 'A', status: 'suggested' }] }
            setCurriculum(response.data.path || response.data);
            
            toast({ title: 'Path Synthesized', description: `Learning path for ${targetRole} generated.`, variant: 'success' });
        } catch (error) {
            console.error("Synthesis failed:", error);
            toast({ title: 'Synthesis Failed', description: error.response?.data?.detail || error.message, variant: 'destructive' });
        } finally {
            setIsSynthesizing(false);
        }
    }, [targetRole, user.id, isSynthesizing, toast]);

    const styles = useMemo(() => ({
        grid: { display: 'grid', gridTemplateColumns: 'repeat(12, 1fr)', gap: tokens.spacing?.lg, minHeight: '600px' },
        formCard: { gridColumn: 'span 4', padding: tokens.spacing?.md, background: tokens.color?.['panel-700'], borderRadius: tokens.border?.radius?.card, display: 'flex', flexDirection: 'column' },
        resultCard: { gridColumn: 'span 8', padding: tokens.spacing?.md, background: tokens.color?.['panel-700'], borderRadius: tokens.border?.radius?.card },
        input: { padding: '8px 12px', background: tokens.color?.['bg-input'], border: `1px solid ${tokens.color?.['border-600']}`, borderRadius: tokens.border?.radius?.input, color: tokens.color?.['text-100'], width: '100%', boxSizing: 'border-box', marginBottom: tokens.spacing?.md },
        button: (bgColor) => ({ padding: '10px 20px', background: bgColor, border: 'none', borderRadius: tokens.border?.radius?.button, color: tokens.color?.['bg-deep'], cursor: 'pointer', transition: 'all 0.2s ease', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: tokens.spacing?.xs, width: '100%' }),
    }), []);

    return (
        <div style={styles.grid}>
            {/* Synthesis Form */}
            <div style={styles.formCard}>
                <h3 style={{ color: tokens.color?.['text-100'] }}>Synthesize Learning Path</h3>
                <p style={{ color: tokens.color?.['muted-500'], fontSize: tokens.typography.small.fontSize }}>
                    Generate a personalized curriculum based on your Digital Twin's skill gaps.
                </p>
                <form onSubmit={handleSynthesize}>
                    <label style={{ color: tokens.color?.['text-100'], display: 'block', marginBottom: '5px' }}>Target Role:</label>
                    <input type="text" value={targetRole} onChange={e => setTargetRole(e.target.value)} style={styles.input} required />

                    <button 
                        type="submit" 
                        style={styles.button(tokens.color?.['accent-primary'])} 
                        disabled={isSynthesizing || !targetRole}
                        className="synth-path-hover"
                    >
                        {isSynthesizing ? <Loader2 size={16} className="animate-spin" /> : <Zap size={16} />}
                        Synthesize Path
                    </button>
                </form>
                
                <h4 style={{ color: tokens.color?.['text-100'], marginTop: tokens.spacing?.xl }}>Current Skill Gaps</h4>
                 <div style={{ color: tokens.color?.warning, fontSize: tokens.typography.small.fontSize }}>
                    {isXaiLoading ? <p>Loading XAI data...</p> : (
                        (dtXai?.top_gaps || ['Cloud Security', 'BPCL Coding']).map((gap, index) => (
                            <p key={index} style={{ margin: '5px 0', display: 'flex', alignItems: 'center', gap: tokens.spacing?.xs }}>
                                <AlertTriangle size={14} /> {gap}
                            </p>
                        ))
                    )}
                </div>
            </div>

            {/* Results / Curriculum Display */}
            <div style={styles.resultCard}>
                <h3 style={{ color: tokens.color?.['text-100'], margin: 0 }}>Learning Curriculum</h3>
                
                {curriculum ? (
                    <div style={{ marginTop: tokens.spacing?.md }}>
                        {curriculum.map((item, index) => (
                            <p key={index} style={{ color: tokens.color?.['text-100'], padding: '8px 0', borderBottom: `1px dotted ${tokens.color?.['border-600']}` }}>
                                <BookOpen size={16} style={{ marginRight: tokens.spacing?.xs }} color={tokens.color?.success} />
                                **Module:** {item.module} ({item.status})
                            </p>
                        ))}
                    </div>
                ) : (
                    <div style={{ textAlign: 'center', padding: tokens.spacing?.xl, color: tokens.color?.['muted-500'] }}>
                        <p><TrendingUp size={32} /></p>
                        <p>No active personalized learning path. Enter a target role to generate one.</p>
                    </div>
                )}
            </div>
            <style>{`.synth-path-hover:hover { box-shadow: 0 0 10px ${tokens.color?.['accent-primary']}77; transform: translateY(-1px); }`}</style>
        </div>
    );
});

TalentExperienceHub.displayName = 'TalentExperienceHub';
export default TalentExperienceHub;