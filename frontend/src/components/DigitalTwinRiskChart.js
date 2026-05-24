// /frontend/src/components/DigitalTwinRiskChart.js - STABILIZED (Fixes fontSize TypeErrors)
import React, { useMemo, memo } from 'react';
import { theme as tokens } from '../theme';
import ChartPlaceholder from './ChartPlaceholder'; 
import { AlertTriangle, TrendingDown, CheckCircle } from 'lucide-react'; 

/** * DigitalTwinRiskChart: Visualizes the impact of a 'What-If' simulation. 
 * @param {number} originalRisk - Original attrition risk score (e.g., 0.82) 
 * @param {number} simulatedRisk - Simulated attrition risk score (e.g., 0.35) 
 * @param {Array} mitigationFactors - Key factors that drove risk mitigation. 
 */
const DigitalTwinRiskChart = memo(({ originalRisk, simulatedRisk, mitigationFactors = [] }) => {
        
    // CRITICAL FIX 1: Ensure risk scores are treated as fractions (0.0 to 1.0) and converted to %
    // Calculate the percentage difference for display
    const originalRiskPct = (originalRisk * 100).toFixed(1);
    const simulatedRiskPct = (simulatedRisk * 100).toFixed(1);
    const riskDifference = (originalRiskPct - simulatedRiskPct).toFixed(1);
    
    // Success means the risk has gone down (difference is positive)
    const isSuccess = parseFloat(riskDifference) > 0;
    const isNeutral = parseFloat(riskDifference) === 0;

    const styles = useMemo(() => ({
        container: { display: 'flex', flexDirection: 'column', gap: tokens.spacing?.md, height: '100%' },
        riskHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingBottom: tokens.spacing?.sm, borderBottom: `1px solid ${tokens.color?.['border-600']}` },
        summaryGrid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: tokens.spacing?.md, textAlign: 'center' },
        summaryCard: { padding: tokens.spacing?.sm, borderRadius: tokens.border?.radius?.card, background: tokens.color?.['panel-700'] },
        // --- FIX: Added optional chaining ---
        riskValue: { fontSize: tokens.typography?.h2?.fontSize, fontWeight: tokens.typography?.h2?.fontWeight, margin: 0 },
        riskLabel: { color: tokens.color?.['muted-500'], fontSize: tokens.typography?.small?.fontSize },
        // ------------------------------------
        factorRow: { display: 'flex', justifyContent: 'space-between', padding: `${tokens.spacing?.xs} 0`, borderBottom: `1px dotted ${tokens.color?.['border-700']}` }
    }), []);

    const DifferenceIcon = isSuccess ? TrendingDown : (isNeutral ? AlertTriangle : AlertTriangle);
    const differenceColor = isSuccess ? tokens.color?.success : (isNeutral ? tokens.color?.warning : tokens.color?.danger);
    const impactColor = isSuccess ? tokens.color?.success : tokens.color?.danger;

    return (
        <div style={styles.container}>
            <div style={styles.riskHeader}>
                <h3 style={{ margin: 0, color: tokens.color?.['text-100'] }}>Risk Simulation Analysis</h3>
                <span style={{ color: tokens.color?.['accent-secondary'], display: 'flex', alignItems: 'center' }}>
                    <AlertTriangle size={18} style={{ marginRight: tokens.spacing?.xs }} /> XAI Insight
                </span>
            </div>

            {/* Summary Grid */}
            <div style={styles.summaryGrid}>
                <div style={styles.summaryCard}>
                    <p style={styles.riskValue}>{originalRiskPct}%</p>
                    <p style={styles.riskLabel}>Original Attrition Risk</p>
                </div>
                <div style={styles.summaryCard}>
                    <p style={styles.riskValue}>{simulatedRiskPct}%</p>
                    <p style={styles.riskLabel}>Simulated Risk</p>
                </div>
            </div>

            {/* Mitigation Summary */}
            <div style={{ ...styles.summaryGrid, border: `1px solid ${differenceColor}`, borderRadius: tokens.border?.radius?.card }}>
                <div style={{ ...styles.summaryCard, background: 'transparent' }}>
                    <div style={{ ...styles.riskValue, color: differenceColor }}>
                        {parseFloat(riskDifference) > 0 ? '+' : ''}{riskDifference}%
                    </div>
                    <span style={styles.riskLabel}>Risk Reduction</span>
                </div>
                <div style={{ ...styles.summaryCard, background: 'transparent', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', color: impactColor }}>
                    <DifferenceIcon size={24} style={{ marginBottom: tokens.spacing?.xs }} />
                    <span style={styles.riskLabel}>Mitigation Status</span>
                </div>
            </div>
                        
            <div style={{ flexGrow: 1 }}>
                {/* The Bar Chart Placeholder is assumed to be a separate component displaying factors */}
                <ChartPlaceholder label="Bar Chart: Risk Mitigation by Factor" minHeight="200px" />
            </div>

            <h4 style={{ ...styles.riskHeader, borderBottom: 'none' }}>Top Mitigation Drivers</h4>
            <div style={{ overflowY: 'auto', maxHeight: '100px' }}>
                {mitigationFactors.length > 0 ? (
                    mitigationFactors.map((factor, index) => (
                        <div key={index} style={styles.factorRow}>
                            <span>{factor.feature}</span>
                            <span style={{ color: factor.impact < 0 ? tokens.color?.success : tokens.color?.danger }}>
                                {/* Display impact as a percentage with +/- sign */}
                                {/* CRITICAL FIX 2: Ensure impact is correctly formatted and signed */}
                                {factor.impact > 0 ? `+${(factor.impact * 100).toFixed(1)}%` : `${(factor.impact * 100).toFixed(1)}%`}
                            </span>
                        </div>
                    ))
                ) : (
                    <p style={{ ...styles.factorRow, justifyContent: 'center' }}>No specific mitigation factors identified.</p>
                )}
            </div>
        </div>
    );
});

DigitalTwinRiskChart.displayName = 'DigitalTwinRiskChart';
export default DigitalTwinRiskChart;