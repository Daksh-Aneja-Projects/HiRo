// /frontend/src/pages/Dashboard.js - FINAL PRODUCTION-READY REPLACEMENT (Fixing AI Commander Position)
import React, { useMemo, memo } from 'react';
// FIX: Using absolute path aliases
import { useAuth } from '../contexts/AuthContext';
import { useCustomization } from '../contexts/CustomizationContext';
import { theme as tokens } from '../theme';

// CRITICAL IMPORTS - FIX: Using absolute path aliases
import AI_UI_Commander from '../components/AI_UI_Commander';
import DynamicDashboard from '../components/DynamicDashboard';
import ChartPlaceholder from '../components/ChartPlaceholder';
import DataCard from '../components/DataCard';
// CRITICAL FIX: Ensure all used icons are imported
import { CheckCircle, XCircle, AlertTriangle, Zap, ShieldCheck } from 'lucide-react'; 

// Mock Data / Default Components (Used when no AI config is active)
const DefaultStatCard = ({ title, value, unit, color, Icon }) => (
    <DataCard title={title} value={value} unit={unit} color={color}>
        <Icon size={24} color={color} />
    </DataCard>
);

const DefaultDashboard = memo(() => {
    const styles = useMemo(() => ({
        grid: {
            display: 'grid',
            gridTemplateColumns: 'repeat(12, 1fr)',
            gap: tokens.spacing?.lg,
            marginBottom: tokens.spacing?.lg,
        },
        card: {
            gridColumn: 'span 3',
        },
        chartHalf: {
            gridColumn: 'span 6',
            height: '350px',
        },
        chartFull: {
            gridColumn: 'span 12',
            height: '350px',
        }
    }), []);

    return (
        <>
            <div style={styles.grid}>
                <div style={styles.card}>
                    <DefaultStatCard title="Overall Risk Score" value="0.78" unit="HIGH" color={tokens.color?.danger} Icon={AlertTriangle} />
                </div>
                <div style={styles.card}>
                    {/* CRITICAL: ShieldCheck was not imported previously, ensure it's available */}
                    <DefaultStatCard title="Active Policy Agents" value="42" unit="Agents" color={tokens.color?.success} Icon={ShieldCheck} />
                </div>
                <div style={styles.card}>
                    <DefaultStatCard title="Autonomous Fixes (30d)" value="95%" unit="Success Rate" color={tokens.color?.['accent-primary']} Icon={CheckCircle} />
                </div>
                <div style={styles.card}>
                    <DefaultStatCard title="Active PQC Encryption" value="100%" unit="Coverage" color={tokens.color?.warning} Icon={Zap} />
                </div>
            </div>
            
            <div style={styles.grid}>
                <div style={styles.chartHalf}>
                    <ChartPlaceholder label="Line Chart: Policy Compliance Trend (Default)" minHeight="350px" />
                </div>
                <div style={styles.chartHalf}>
                    <ChartPlaceholder label="Bar Chart: Attrition Risk by Dept (Default)" minHeight="350px" />
                </div>
                <div style={styles.chartFull}>
                     <ChartPlaceholder label="GeoMap: Live Transaction Audit Trace (Default)" minHeight="350px" />
                </div>
            </div>
        </>
    );
});
DefaultDashboard.displayName = 'DefaultDashboard';


// --- CRITICAL FEATURE: AI Configuration Preview Bar ---
const AIConfigPreviewBar = memo(({ commitConfig, revertConfig }) => {
    const styles = useMemo(() => ({
        bar: {
            padding: tokens.spacing?.md,
            marginBottom: tokens.spacing?.lg,
            background: tokens.color?.['warning-700'],
            color: tokens.color?.['text-dark'],
            borderRadius: tokens.border?.radius?.card,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            boxShadow: tokens.shadow?.default,
        },
        button: (bgColor) => ({
            padding: '8px 15px',
            borderRadius: tokens.border?.radius?.button,
            cursor: 'pointer',
            border: 'none',
            // --- FIX: Added optional chaining for defensive access to fontWeight ---
            fontWeight: tokens.typography?.button?.fontWeight, // FIX: Safe access
            // ---------------------------------------------------------------------
            marginLeft: tokens.spacing?.md,
            display: 'flex',
            alignItems: 'center',
            gap: tokens.spacing?.xs,
            background: bgColor,
            color: bgColor === tokens.color?.success ? tokens.color?.['text-dark'] : tokens.color?.['text-100'],
            transition: 'all 0.2s ease',
        })
    }), []);

    return (
        <div style={styles.bar}>
            <div style={{ display: 'flex', alignItems: 'center' }}>
                <AlertTriangle size={20} color={tokens.color?.['text-dark']} style={{ marginRight: tokens.spacing?.sm }} />
                <span style={{ fontWeight: 'bold' }}>AI Configuration Preview Active: </span>
                <span style={{ marginLeft: tokens.spacing?.xs }}>Review the proposed theme and layout changes.</span>
            </div>
            <div>
                <button 
                    onClick={revertConfig} 
                    style={styles.button(tokens.color?.danger)} 
                    title="Discard AI proposed changes"
                    className="preview-revert-hover"
                >
                    <XCircle size={16} /> Revert Preview
                </button>
                <button 
                    onClick={commitConfig} 
                    style={styles.button(tokens.color?.success)} 
                    title="Apply AI proposed changes permanently"
                    className="preview-commit-hover"
                >
                    <CheckCircle size={16} /> Commit Changes
                </button>
            </div>
        </div>
    );
});
AIConfigPreviewBar.displayName = 'AIConfigPreviewBar';


// --- MAIN DASHBOARD COMPONENT ---
export const Dashboard = memo(() => {
    const { user } = useAuth();
    const { 
        synthesizedDashboardConfig, 
        isPreviewing, 
        commitConfig, 
        revertConfig, 
        activeThemeHSL 
    } = useCustomization();

    const userName = user?.full_name || 'User';

    const styles = useMemo(() => ({
        container: {
            display: 'flex',
            flexDirection: 'column',
            gap: tokens.spacing?.lg,
            minHeight: '100%',
        },
        header: {
            color: tokens.color?.['text-100'],
            marginBottom: tokens.spacing?.md,
        },
        // Dynamically adjust header based on active HSL for a holo effect
        h1: {
            // --- FIX: Added optional chaining for defensive access to fontSize ---
            fontSize: tokens.typography?.h1?.fontSize, // FIX: Safe access
            // -------------------------------------------------------------------
            margin: 0,
            background: `linear-gradient(90deg, 
                hsl(var(--user-hue), var(--saturation), var(--lightness)) 0%, 
                ${tokens.color?.['text-100']} 100%)`,
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
        },
        // NEW FIX: Fixed container for the AI Commander
        commanderFixedContainer: {
            position: 'fixed', // Pin to viewport
            bottom: tokens.spacing?.lg,
            right: tokens.spacing?.lg,
            zIndex: 1000, // Ensure it's above other content
        }
    }), [activeThemeHSL]);


    return (
        <div style={styles.container} className="portal-container">
            <div style={styles.header}>
                <h1 style={styles.h1}>Welcome, {userName}!</h1>
                <p style={{ color: tokens.color?.['muted-500'], margin: 0 }}>
                    {synthesizedDashboardConfig ? "AI Synthesized Dashboard: Reviewing Real-Time Report." : "Executive Overview: Core System Health and Metrics."}
                </p>
            </div>

            {/* CRITICAL INTEGRATION: Show the Preview Bar when UI/Theme changes are pending */}
            {isPreviewing && (
                <AIConfigPreviewBar 
                    commitConfig={commitConfig} 
                    revertConfig={revertConfig} 
                />
            )}

            {/* CRITICAL DYNAMIC RENDERING: Switch between dynamic and default content */}
            {synthesizedDashboardConfig ? (
                // Mode 1: AI has generated a temporary dashboard config (e.g., from 'Synthesize report...' command)
                <DynamicDashboard config={synthesizedDashboardConfig} />
            ) : (
                // Mode 2: Default static content
                <DefaultDashboard />
            )}

            {/* CRITICAL INTEGRATION: AI Command Bar is globally available on the dashboard */}
            {/* NEW FIX: Wrapped the commander in a fixed position container */}
            <div style={styles.commanderFixedContainer}>
                <AI_UI_Commander />
            </div>

            <style>{`
                /* Add hover styles for the new preview bar buttons */
                .preview-revert-hover:hover {
                    background: ${tokens.color?.danger} !important;
                    box-shadow: 0 0 8px ${tokens.color?.danger} !important;
                    transform: translateY(-1px);
                }
                .preview-commit-hover:hover {
                    background: ${tokens.color?.success} !important;
                    box-shadow: 0 0 8px ${tokens.color?.success} !important;
                    transform: translateY(-1px);
                }
            `}</style>
        </div>
    );
});

Dashboard.displayName = 'Dashboard';
// CRITICAL FIX: Named export to match App.js import
// No need to export default here.