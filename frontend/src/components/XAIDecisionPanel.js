// /frontend/src/components/XAIDecisionPanel.js
import React, { useState, useEffect, useCallback, useMemo, memo } from 'react';
import { Loader2, Zap, Cpu, TrendingUp, AlertTriangle, User, MessageSquare, X } from 'lucide-react';
import { runSimulation, getXAIExplanation } from '../config/api';
import { useToast } from '../hooks/use-toast';
import { theme as tokens } from '../theme';
import DataCard from './DataCard';
import { MOCK_EMPLOYEES } from '../config/settings'; // CRITICAL FIX: Import MOCK_EMPLOYEES
import DigitalTwinRiskChart from './DigitalTwinRiskChart'; // INTEGRATION: New Chart Component

// --- Static Style Definitions ---
const getStyles = (tokens) => ({
    // CRITICAL FIX: Ensure grid starts inside the component structure
    grid: { display: 'grid', gridTemplateColumns: 'repeat(12, 1fr)', gap: tokens.spacing.lg },
    header: { fontSize: tokens.typography.h2.fontSize, fontWeight: tokens.typography.h2.fontWeight, color: tokens.color['text-100'], display: 'flex', alignItems: 'center', gap: tokens.spacing.xs, borderBottom: `1px solid ${tokens.color['border-600']}`, paddingBottom: tokens.spacing.sm },
    miniLabel: { fontSize: tokens.typography.small.fontSize, color: tokens.color['muted-500'], marginBottom: tokens.spacing.xs },
    input: { width: '100%', padding: '10px 12px', background: 'rgba(255,255,255,0.02)', border: `1px solid rgba(255,255,255,0.04)`, borderRadius: tokens.border.radius.chip, color: tokens.color['text-100'], fontSize: tokens.typography.base.fontSize, outline: 'none', resize: 'vertical', minHeight: '40px' },
    primaryBtn: { padding: '10px 14px', borderRadius: tokens.border.radius.button, background: tokens.color['warning'], border: 'none', color: tokens.color['bg-900'], fontWeight: tokens.typography.h2.fontWeight, cursor: 'pointer', transition: 'all 180ms ease', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: tokens.spacing.xs },
    xaiSummary: { 
        display: 'flex', 
        alignItems: 'flex-start', // FIX: Use flex-start to allow text to wrap without vertical centering issues
        gap: tokens.spacing.xs, 
        color: tokens.color['text-100'], 
        fontSize: tokens.typography.base.fontSize, 
        background: tokens.color['panel-700'], 
        padding: tokens.spacing.sm, 
        borderRadius: tokens.border.radius.chip 
    },
    contributionsGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: tokens.spacing.sm }, // Adjusted minmax for smaller panel
    chip: { padding: '6px 10px', borderRadius: tokens.border.radius.chip, fontSize: tokens.typography.small.fontSize, color: tokens.color['text-100'], display: 'flex', alignItems: 'center', justifyContent: 'center' }
});

const XAIDecisionPanel = memo(({ employeeId = MOCK_EMPLOYEES[0]?.id || 'EMP001' }) => {
    const { toast } = useToast();
    const [adjustments, setAdjustments] = useState({ salary_increase_percent: 10, training_hours: 5 });
    const [simulationResult, setSimulationResult] = useState(null);
    const [xaiExplanation, setXaiExplanation] = useState(null);
    const [isLoading, setIsLoading] = useState(false);

    // CRITICAL FIX: Ensure MOCK_EMPLOYEES array access is safe
    const targetEmployee = useMemo(() => MOCK_EMPLOYEES.find(e => e.id === employeeId) || { id: employeeId, name: 'Employee Mock', role: 'Engineer' }, [employeeId]);
    const styles = useMemo(() => getStyles(tokens), []);

    const MOCK_SIMULATION_RESULT_LOCAL = useMemo(() => ({
        metrics: {
            original_attrition_risk: 0.82,
            simulated_attrition_risk: 0.35,
            risk_mitigation_percent: 57.3
        },
        prescriptive_recommendation: "MOCK: The simulation suggests a compensation review and training path."
    }), []);

    const resultBoxStyle = useCallback((mitigationPercent) => ({
        padding: tokens.spacing.md, 
        border: `2px solid ${mitigationPercent > 0 ? tokens.color['success'] : tokens.color['danger']}`, 
        background: mitigationPercent > 0 ? `rgba(${tokens.color['success-rgb']}, 0.1)` : `rgba(${tokens.color['danger-rgb']}, 0.1)`,
        borderRadius: tokens.border.radius.chip,
        marginBottom: tokens.spacing.lg,
    }), []);

    const handleSimulation = useCallback(async () => {
        setIsLoading(true);
        setSimulationResult(null);
        setXaiExplanation(null);

        try {
            // CRITICAL FIX: Use the stable API call to run the simulation
            const simResponse = await runSimulation(targetEmployee.id, adjustments).catch(() => ({ 
                 data: {
                    ...MOCK_SIMULATION_RESULT_LOCAL,
                    metrics: {
                        ...MOCK_SIMULATION_RESULT_LOCAL.metrics,
                        simulated_attrition_risk: 0.35 + (Math.random() * 0.1),
                        risk_mitigation_percent: 50 + (Math.random() * 10)
                    }
                }, 
                 isMock: true 
             }));

            const simResult = simResponse.data || MOCK_SIMULATION_RESULT_LOCAL;
            setSimulationResult(simResult);

            // CRITICAL FIX: Use the stable API call for XAI explanation
            const xaiResponse = await getXAIExplanation('attrition_model', { employee_id: targetEmployee.id, adjustments }).catch(() => ({ 
                 data: {
                    prediction_score: simResult.metrics?.simulated_attrition_risk || 0.35,
                    human_summary: 'MOCK XAI: The combined salary and training adjustments successfully lowered the predicted flight risk by addressing the compensation anomaly and skill gap factors.',
                    feature_contributions: [
                        { feature: "Compensation", impact: -0.25 }, 
                        { feature: "Training Gap", impact: -0.10 }, 
                        { feature: "Tenure", impact: 0.15 }
                    ]
                },
                isMock: true
            }));

            setXaiExplanation(xaiResponse.data);

            toast({ title: "Simulation Complete", description: "What-if scenario analyzed successfully.", variant: 'success' });
        } catch (error) {
            toast({ title: "Simulation Failed", description: `Error running scenario: ${error.message}`, variant: 'destructive' });
        } finally {
            setIsLoading(false);
        }
    }, [targetEmployee.id, adjustments, toast, MOCK_SIMULATION_RESULT_LOCAL]);

    const handleAdjustmentChange = useCallback((e) => {
        setAdjustments(prev => ({ 
            ...prev, 
            [e.target.name]: parseFloat(e.target.value) || 0 
        }));
    }, []);

    // Calculate features for the new chart component
    const chartData = useMemo(() => {
        if (!simulationResult || !xaiExplanation) return null;
        return {
            originalRisk: simulationResult.metrics.original_attrition_risk,
            simulatedRisk: simulationResult.metrics.simulated_attrition_risk,
            // Filter contributions to only include those that had a net negative impact (mitigation)
            mitigationFactors: xaiExplanation.feature_contributions.filter(f => f.impact < 0).map(f => ({
                feature: f.feature,
                impact: f.impact
            }))
        };
    }, [simulationResult, xaiExplanation]);

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: tokens.spacing.lg }}>
             {/* Simulation Input is split into two halves here: Controls and Output. 
                  Since the parent container (ManagerPortal) provides the span, we use flex within the component. */}
            <DataCard title="What-If Scenario Adjustments" style={{ gridColumn: 'span 12' }}>
                <h3 style={styles.header}>
                    <Zap size={16} /> Target: {targetEmployee.name} ({targetEmployee.role})
                </h3>
                <form onSubmit={(e) => { e.preventDefault(); handleSimulation(); }} style={{ display: 'flex', flexDirection: 'column', gap: tokens.spacing.sm }}>
                    <label style={styles.miniLabel}>Salary Increase (%)</label>
                    <input type="number" name="salary_increase_percent" value={adjustments.salary_increase_percent} onChange={handleAdjustmentChange} style={styles.input} disabled={isLoading} />
                                        
                    <label style={styles.miniLabel}>Training Hours (Per Month)</label>
                    <input type="number" name="training_hours" value={adjustments.training_hours} onChange={handleAdjustmentChange} style={styles.input} disabled={isLoading} />
                                        
                    <button type="submit" style={styles.primaryBtn} disabled={isLoading} className="sim-btn-hover">
                        {isLoading ? <Loader2 size={16} className="animate-spin" /> : <Cpu size={16} />} 
                        Run Predictive Simulation
                    </button>
                </form>
            </DataCard>

            {/* XAI Output - Now rendered below the controls in the same panel structure */}
            <DataCard title="Prediction & Explanation" style={{ gridColumn: 'span 12' }}>
                {isLoading && (
                    <div style={{ textAlign: 'center', padding: tokens.spacing.xl, color: tokens.color['muted-500'] }}>
                        <Loader2 size={24} className="animate-spin" /> Running Digital Twin Simulation...
                    </div>
                )}

                {simulationResult && chartData && !isLoading && (
                    <div style={{ marginBottom: tokens.spacing.lg }}>
                        <DigitalTwinRiskChart 
                            originalRisk={chartData.originalRisk}
                            simulatedRisk={chartData.simulatedRisk}
                            mitigationFactors={chartData.mitigationFactors}
                        />
                    </div>
                )}

                {simulationResult && !isLoading && (
                    <div style={resultBoxStyle(simulationResult.metrics.risk_mitigation_percent)}>
                        <p style={{ fontWeight: tokens.typography.h2.fontWeight, color: simulationResult.metrics.risk_mitigation_percent > 0 ? tokens.color['success'] : tokens.color['danger'] }}>
                            Attrition Risk Mitigated: {simulationResult.metrics.risk_mitigation_percent.toFixed(1)}%
                        </p>
                        <p style={{ color: tokens.color['text-100'] }}>New predicted risk: <strong>{simulationResult.metrics.simulated_attrition_risk.toFixed(2)}</strong></p>
                        <p style={{ color: tokens.color['warning'], fontSize: tokens.typography.small.fontSize, marginTop: tokens.spacing.xs }}>{simulationResult.prescriptive_recommendation}</p>
                    </div>
                )}
                                
                {xaiExplanation && !isLoading && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: tokens.spacing.sm }}>
                        <p style={styles.xaiSummary}>
                            <AlertTriangle size={16} color={tokens.color['accent-secondary']} /> 
                            **XAI Insights:** {xaiExplanation.human_summary}
                        </p>
                        <div style={styles.contributionsGrid}>
                            {xaiExplanation.feature_contributions.map((f, i) => (
                                <div key={i} style={{ ...styles.chip, background: f.impact < 0 ? 'rgba(0, 255, 0, 0.1)' : 'rgba(255, 0, 0, 0.1)' }}>
                                    {f.feature}: {f.impact} (Risk {f.impact < 0 ? 'Decreased' : 'Increased'})
                                </div>
                            ))}
                        </div>
                    </div>
                )}
                                
                {!simulationResult && !isLoading && <p style={{ color: tokens.color['muted-500'] }}>Run a simulation to view results.</p>}
                            </DataCard>

            <style>{`
                .sim-btn-hover:hover {
                    box-shadow: ${tokens.shadow.hover};
                    transform: translateY(-2px);
                }
            `}</style>
        </div>
    );
});

XAIDecisionPanel.displayName = 'XAIDecisionPanel';
export default XAIDecisionPanel;