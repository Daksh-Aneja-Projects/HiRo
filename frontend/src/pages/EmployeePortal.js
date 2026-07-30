// /frontend/src/pages/EmployeePortal.js - FINAL PRODUCTION-READY REPLACEMENT (Digital Twin Widget Fixed)
import React, { useMemo, memo, useState, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import { theme as tokens } from '../theme';
import { useAuth } from '../contexts/AuthContext';

// CRITICAL API IMPORTS
import {
    getEmployeeDashboard, submitLeaveRequest, getLeaveBalance,
    getPersonalInfo, recordConsentChange, getEmployeeBenefits,
    getUnmaskedPII, getWFPProjections, getRecognitionLeaderboard,
    getLeaveHistory
} from '../config/api';
import { useApi } from '../hooks/useApi';
import { useToast } from '../hooks/use-toast';

// UI & NEW COMPONENTS
import DataCard from '../components/DataCard';
import BarChartWidget from '../components/charts/BarChartWidget';
import { skillGapSeries, countBy } from '../utils/chartData';
import DigitalTwinChat from '../components/DigitalTwinChat'; // CRITICAL: Import DigitalTwinChat
import { 
    User, Calendar, Shield, CreditCard, 
    CheckCircle, XCircle, Loader2, AlertTriangle, 
    DollarSign, BookOpen
} from 'lucide-react';


// --- 9.1. Sub-Module: My Dashboard ---
/**
 * Renders the personalized Employee Dashboard overview.
 */
const EmployeeDashboardModule = memo(() => {
    const { user } = useAuth();
    
    // CRITICAL API INTEGRATION 1: Fetch Employee Dashboard Data
    const { 
        data: dashboardData, 
        isLoading, 
        error 
    } = useApi(getEmployeeDashboard, [user?.id], true, 0); // CRITICAL FIX: Polling disabled (0ms)

    // Real workforce-planning skill gaps + live recognition leaderboard.
    const { data: wfp } = useApi(getWFPProjections, [], true);
    const { data: leaderboard } = useApi(getRecognitionLeaderboard, [], true);
    const skillGaps = useMemo(() => skillGapSeries(wfp?.skill_gaps || {}), [wfp]);
    const recognition = useMemo(
        () => (leaderboard || []).map((u) => ({ name: u.user_name, value: Number(u.stars) || 0 })),
        [leaderboard]
    );

    const styles = useMemo(() => ({
        grid: { display: 'grid', gridTemplateColumns: 'repeat(12, 1fr)', gap: tokens.spacing?.lg, marginBottom: tokens.spacing?.lg },
        card: { gridColumn: 'span 3' },
        chart: { gridColumn: 'span 6', minHeight: '350px' },
        full: { gridColumn: 'span 12', minHeight: '350px' },
    }), []);

    return (
        <div style={styles.grid}>
            {isLoading && <p style={{ gridColumn: 'span 12', textAlign: 'center' }}><Loader2 size={24} className="animate-spin" /> Loading personalized dashboard...</p>}
            {error && <p style={{ gridColumn: 'span 12', color: tokens.color?.danger }}>Error loading dashboard data: {error.message}</p>}
            
            <div style={styles.card}>
                <DataCard 
                    title="Current Performance" 
                    value={dashboardData?.performance_score || 'N/A'} 
                    unit="Score" 
                    color={tokens.color?.success} 
                >
                    <CheckCircle size={24} color={tokens.color?.success} />
                </DataCard>
            </div>
            <div style={styles.card}>
                <DataCard 
                    title="Compensation Ratio" 
                    value={`${(dashboardData?.comp_ratio * 100)?.toFixed(1) || 'N/A'}`} 
                    unit="%" 
                    color={tokens.color?.['accent-primary']}
                >
                    <DollarSign size={24} color={tokens.color?.['accent-primary']} />
                </DataCard>
            </div>
             <div style={styles.card}>
                <DataCard 
                    title="Open Learning Modules" 
                    value={dashboardData?.open_learning_modules || 3} 
                    unit="Count" 
                    color={tokens.color?.warning}
                >
                    <BookOpen size={24} color={tokens.color?.warning} />
                </DataCard>
            </div>
             <div style={styles.card}>
                <DataCard 
                    title="Last Audit Trace" 
                    value={dashboardData?.last_audit_id || 'Secure'} 
                    unit="ID" 
                    color={tokens.color?.['accent-secondary']}
                >
                    <Shield size={24} color={tokens.color?.['accent-secondary']} />
                </DataCard>
            </div>
            
            <div style={styles.chart}>
                <DataCard title="Skill Gap by Department (workforce planning)" isChart minHeight="350px">
                    <BarChartWidget data={skillGaps} minHeight="290px" color={tokens.color?.['accent-primary']} label="Higher bar = larger organizational skill gap" />
                </DataCard>
            </div>
             <div style={styles.chart}>
                <DataCard title="Recognition Leaderboard (stars)" isChart minHeight="350px">
                    <BarChartWidget data={recognition} minHeight="290px" color={tokens.color?.warning} />
                </DataCard>
            </div>
        </div>
    );
});
EmployeeDashboardModule.displayName = 'EmployeeDashboardModule';

// --- 9.2. Sub-Module: My Leaves ---
const LeaveModule = memo(() => {
    const { toast } = useToast();
    const { user } = useAuth();
    const [leaveData, setLeaveData] = useState({ start_date: '', end_date: '', reason: '' });
    const [isSubmitting, setIsSubmitting] = useState(false);
    
    // CRITICAL API INTEGRATION 2: Fetch Leave Balance
    const { 
        data: balanceData, 
        isLoading: isBalanceLoading, 
        error: balanceError, 
        refetch: refetchBalance 
    } = useApi(getLeaveBalance, [], true, 0); // CRITICAL FIX: Polling disabled (0ms)

    // Real leave history grouped by approval status.
    const { data: leaveHistory } = useApi(getLeaveHistory, [], true, 0);
    const leaveByStatus = useMemo(
        () => countBy(Array.isArray(leaveHistory) ? leaveHistory : (leaveHistory?.requests || []), (r) => r.status),
        [leaveHistory]
    );

    // CRITICAL: Handle Leave Submission
    const handleSubmitLeave = useCallback(async (e) => {
        e.preventDefault();
        if (!leaveData.start_date || !leaveData.end_date || !leaveData.reason) {
            return toast({ title: "Validation Error", description: "All fields are required.", variant: 'destructive' });
        }
        
        setIsSubmitting(true);
        try {
            // Backend contract is { start_date, end_date, hours } — derive hours
            // from the requested date range (8h per working day, min 1 day).
            const start = new Date(leaveData.start_date);
            const end = new Date(leaveData.end_date);
            const days = Math.max(1, Math.round((end - start) / 86400000) + 1);
            const payload = {
                start_date: leaveData.start_date,
                end_date: leaveData.end_date,
                hours: days * 8,
            };
            await submitLeaveRequest(payload);
            
            toast({ title: 'Leave Submitted', description: 'Your request has been sent for manager approval.', variant: 'success' });
            setLeaveData({ start_date: '', end_date: '', reason: '' }); // Clear form
            refetchBalance(); // Refresh balance data
        } catch (error) {
            console.error("Leave submission failed:", error);
            toast({ title: 'Submission Failed', description: error.response?.data?.detail || error.message, variant: 'destructive' });
        } finally {
            setIsSubmitting(false);
        }
    }, [leaveData, user?.id, toast, refetchBalance]);


    const styles = useMemo(() => ({
        // FIX: Ensuring the grid uses fractional units (1fr 2fr is already correct for responsiveness)
        grid: { display: 'grid', gridTemplateColumns: '1fr 2fr', gap: tokens.spacing?.lg, marginBottom: tokens.spacing?.lg },
        card: { padding: tokens.spacing?.md, background: tokens.color?.['panel-700'], borderRadius: tokens.border?.radius?.card, minHeight: '300px' },
        formGroup: { marginBottom: tokens.spacing?.md },
        // FIX: Added maxWidth: '100%' to prevent input/textarea overflow
        input: { width: '100%', maxWidth: '100%', padding: '10px', background: tokens.color?.['bg-input'], border: `1px solid ${tokens.color?.['border-600']}`, borderRadius: tokens.border?.radius?.input, color: tokens.color?.['text-100'], boxSizing: 'border-box' },
        submitButton: { padding: '10px 20px', background: tokens.color?.success, border: 'none', borderRadius: tokens.border?.radius?.button, color: tokens.color?.['bg-deep'], cursor: 'pointer', transition: 'all 0.2s ease', display: 'flex', alignItems: 'center', gap: tokens.spacing?.xs },
    }), []);

    return (
        <div style={styles.grid}>
            {/* Leave Balance */}
            <div style={styles.card}>
                <h3 style={{ color: tokens.color?.['text-100'] }}>Current Leave Balance</h3>
                {isBalanceLoading && <p style={{textAlign: 'center'}}><Loader2 size={20} className="animate-spin" /> Loading...</p>}
                {balanceError && <p style={{ color: tokens.color?.danger }}>Error: {balanceError.message}</p>}
                <DataCard 
                    title="Available PTO" 
                    value={balanceData?.pto_days || 'N/A'} 
                    unit="Days" 
                    color={tokens.color?.success}
                >
                    <Calendar size={24} color={tokens.color?.success} />
                </DataCard>
                <p style={{ color: tokens.color?.['muted-500'], marginTop: tokens.spacing?.md }}>Last update: {new Date().toLocaleDateString()}</p>
            </div>
            
            {/* Leave Request Form */}
            <div style={styles.card}>
                <h3 style={{ color: tokens.color?.['text-100'] }}>Submit New Leave Request</h3>
                <form onSubmit={handleSubmitLeave}>
                    <div style={styles.formGroup}>
                        <label style={{ color: tokens.color?.['text-100'], display: 'block', marginBottom: '5px' }}>Start Date</label>
                        <input 
                            type="date" 
                            style={styles.input} 
                            value={leaveData.start_date}
                            onChange={(e) => setLeaveData(prev => ({ ...prev, start_date: e.target.value }))}
                        />
                    </div>
                    <div style={styles.formGroup}>
                        <label style={{ color: tokens.color?.['text-100'], display: 'block', marginBottom: '5px' }}>End Date</label>
                        <input 
                            type="date" 
                            style={styles.input} 
                            value={leaveData.end_date}
                            onChange={(e) => setLeaveData(prev => ({ ...prev, end_date: e.target.value }))}
                        />
                    </div>
                    <div style={styles.formGroup}>
                        <label style={{ color: tokens.color?.['text-100'], display: 'block', marginBottom: '5px' }}>Reason</label>
                        <textarea 
                            // Uses the fixed input style with minHeight added
                            style={{ ...styles.input, minHeight: '80px' }} 
                            value={leaveData.reason}
                            onChange={(e) => setLeaveData(prev => ({ ...prev, reason: e.target.value }))}
                            placeholder="Brief reason for the leave"
                        />
                    </div>
                    <button 
                        type="submit" 
                        style={styles.submitButton} 
                        disabled={isSubmitting}
                        className="leave-submit-hover"
                    >
                        {isSubmitting ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle size={16} />}
                        {isSubmitting ? 'Submitting...' : 'Submit Request'}
                    </button>
                </form>
            </div>

             <div style={{ gridColumn: 'span 2' }}>
                <DataCard title="Leave History & Approval Status" isChart minHeight="250px">
                    <BarChartWidget data={leaveByStatus} minHeight="200px" color={tokens.color?.['accent-secondary']} />
                </DataCard>
            </div>
        </div>
    );
});
LeaveModule.displayName = 'LeaveModule';


// --- 9.3. Sub-Module: My PII & Benefits ---
const PIISecurityModule = memo(() => {
    const { toast } = useToast();
    // CRITICAL API INTEGRATION 3: Fetch Personal Info and Benefits
    const { 
        data: personalInfo, 
        isLoading: isInfoLoading, 
        error: infoError 
    } = useApi(getPersonalInfo, [], true, 0); // CRITICAL FIX: Polling disabled (0ms)
    
    const { 
        data: benefits, 
        isLoading: isBenefitsLoading, 
        error: benefitsError 
    } = useApi(getEmployeeBenefits, [], true, 0); // CRITICAL FIX: Polling disabled (0ms)

    const [isConsenting, setIsConsenting] = useState(false);
    const [piiMasked, setPiiMasked] = useState(true);
    const [maskedPiiData, setMaskedPiiData] = useState({});

    // CRITICAL: Handle Consent Change
    const handleConsentToggle = useCallback(async (isGranted) => {
        setIsConsenting(true);
        try {
            // CRITICAL FIX: Use the specific recordConsentChange API function
            await recordConsentChange({ 
                purpose_id: 'marketing', 
                consent_granted: isGranted, 
                reason: 'User preference update' 
            }); 
            
            toast({ title: 'Consent Updated', description: `Your marketing consent is now ${isGranted ? 'granted' : 'revoked'}.`, variant: 'success' });
        } catch (error) {
            toast({ title: 'Consent Error', description: 'Failed to update consent.', variant: 'destructive' });
        } finally {
            setIsConsenting(false);
        }
    }, [toast]);
    
    // CRITICAL: Handle PII Unmasking (High Security Action)
    const handleUnmaskPII = useCallback(async () => {
        if (!piiMasked) {
            setPiiMasked(true);
            return;
        }

        try {
            // CRITICAL FIX: Use the specific getUnmaskedPII API function
            const response = await getUnmaskedPII(); 
            setMaskedPiiData(response.data);
            setPiiMasked(false);
            
            toast({ title: 'PII Revealed', description: 'PII unmasked for 30 seconds. This action is fully logged.', variant: 'warning' });
            
            // Re-mask after 30 seconds
            setTimeout(() => {
                setPiiMasked(true);
                setMaskedPiiData({});
                toast({ title: 'PII Re-Masked', description: 'Personal Information has been automatically re-masked.', variant: 'info' });
            }, 30000); 

        } catch (error) {
            toast({ title: 'Security Error', description: error.response?.data?.detail || 'Failed to unmask PII. Check audit logs.', variant: 'destructive' });
        }
    }, [piiMasked, toast]);


    const styles = useMemo(() => ({
        grid: { display: 'grid', gridTemplateColumns: '2fr 1fr', gap: tokens.spacing?.lg, marginBottom: tokens.spacing?.lg },
        card: { padding: tokens.spacing?.md, background: tokens.color?.['panel-700'], borderRadius: tokens.border?.radius?.card, minHeight: '300px' },
        dataRow: { display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: `1px dotted ${tokens.color?.['border-700']}` },
        buttonGroup: { display: 'flex', gap: tokens.spacing?.md, marginTop: tokens.spacing?.lg },
        piiButton: (isMasking) => ({
            padding: '10px 20px', 
            background: isMasking ? tokens.color?.danger : tokens.color?.warning, 
            color: tokens.color?.['bg-deep'], 
            border: 'none', 
            borderRadius: tokens.border?.radius?.button, 
            cursor: 'pointer',
        }),
        benefitsList: { listStyleType: 'none', padding: 0 }
    }), []);

    // Helper function to display data (masked or unmasked)
    const getPiiValue = (key, defaultValue) => {
        if (piiMasked) {
            // Simple mask
            return '***********';
        }
        return maskedPiiData[key] || personalInfo?.[key] || defaultValue;
    };


    return (
        <div style={styles.grid}>
            {/* PII Management */}
            <div style={styles.card}>
                <h3 style={{ color: tokens.color?.['text-100'] }}>Personal Information & Security</h3>
                {isInfoLoading && <p style={{textAlign: 'center'}}><Loader2 size={20} className="animate-spin" /> Loading info...</p>}
                
                {/* FIX: Explicitly handle 403 Forbidden error */}
                {infoError && infoError.message?.includes('403') && (
                     <div style={{ color: tokens.color?.danger, textAlign: 'center', padding: tokens.spacing?.md }}>
                        <AlertTriangle size={24} style={{ marginBottom: tokens.spacing?.xs }} />
                        <p>Access Forbidden (403). Your account lacks permission to view this data.</p>
                    </div>
                )}
                {/* FIX: Only render data if no critical error, or if error is just a standard network error */}
                {(!infoError || !infoError.message?.includes('403')) && (
                    <>
                        <div style={styles.dataRow}>
                            <span style={{ color: tokens.color?.['muted-500'] }}>Full Name:</span>
                            <span style={{ color: tokens.color?.['text-100'] }}>{getPiiValue('full_name', 'N/A')}</span>
                        </div>
                        <div style={styles.dataRow}>
                            <span style={{ color: tokens.color?.['muted-500'] }}>Personal Email:</span>
                            <span style={{ color: tokens.color?.['text-100'] }}>{getPiiValue('personal_email', 'N/A')}</span>
                        </div>
                        <div style={styles.dataRow}>
                            <span style={{ color: tokens.color?.['muted-500'] }}>Home Address:</span>
                            <span style={{ color: tokens.color?.['text-100'] }}>{getPiiValue('address', 'N/A')}</span>
                        </div>
                        <div style={styles.dataRow}>
                            <span style={{ color: tokens.color?.['muted-500'] }}>SSN/Tax ID:</span>
                            <span style={{ color: tokens.color?.['text-100'], fontWeight: 'bold' }}>{getPiiValue('ssn', '***-**-****')}</span>
                        </div>
                    </>
                )}


                <div style={styles.buttonGroup}>
                    <button 
                        onClick={handleUnmaskPII} 
                        style={styles.piiButton(piiMasked)} 
                        className="pii-unmask-hover"
                        // Disable if there's a critical info error (e.g., 403)
                        disabled={!!infoError}
                    >
                         {piiMasked ? <Shield size={16} /> : <AlertTriangle size={16} />}
                        {piiMasked ? 'Unmask PII (30s)' : 'Re-Mask PII'}
                    </button>
                    <button 
                        onClick={() => handleConsentToggle(false)} 
                        disabled={isConsenting || !!infoError} 
                        style={{ ...styles.piiButton(true), background: tokens.color?.['panel-800'], color: tokens.color?.danger }}
                        className="pii-revoke-hover"
                    >
                         {isConsenting ? <Loader2 size={16} className="animate-spin" /> : <XCircle size={16} />}
                        Revoke Marketing Consent
                    </button>
                </div>
            </div>
            
            {/* Benefits Overview */}
            <div style={styles.card}>
                <h3 style={{ color: tokens.color?.['text-100'] }}>My Benefits Snapshot</h3>
                {isBenefitsLoading && <p style={{textAlign: 'center'}}><Loader2 size={20} className="animate-spin" /> Loading benefits...</p>}
                {benefitsError && <p style={{ color: tokens.color?.danger }}>Error: {benefitsError.message}</p>}
                <ul style={styles.benefitsList}>
                    {/* FIX: Add defensive check for benefits array */}
                    {(benefits || []).slice(0, 3).map((b, index) => (
                        <li key={index} style={{ padding: '8px 0', borderBottom: `1px dotted ${tokens.color?.['border-700']}`, color: tokens.color?.['text-100'] }}>
                            <span style={{ fontWeight: 'bold', color: tokens.color?.['accent-primary'] }}>{b.name}</span>: {b.coverage}
                        </li>
                    ))}
                    {/* FIX: Add defensive check for benefits array length */}
                    {(benefits || []).length > 3 && (
                        <li style={{ padding: '8px 0', color: tokens.color?.['muted-500'], fontSize: tokens.typography?.small?.fontSize }}>... and {(benefits || []).length - 3} more benefits.</li>
                    )}
                </ul>
                <button style={{ marginTop: tokens.spacing?.md, padding: '8px 15px', background: tokens.color?.['accent-secondary'], border: 'none', borderRadius: tokens.border?.radius?.button, color: tokens.color?.['bg-deep'], cursor: 'pointer' }}>
                    Manage Enrollments
                </button>
            </div>
        </div>
    );
});
PIISecurityModule.displayName = 'PIISecurityModule';


// --- MAIN EMPLOYEE PORTAL COMPONENT ---
export const EmployeePortalComponent = memo(() => {
    const location = useLocation();
    const query = new URLSearchParams(location.search);
    // CRITICAL FIX: Get the module name from the URL, default to 'dashboard'
    const module = query.get('module') || 'dashboard'; 

    const getModuleComponent = (mod) => {
        switch (mod) {
            case 'dashboard':
                return <EmployeeDashboardModule />;
            case 'leave':
                return <LeaveModule />;
            case 'pii':
                return <PIISecurityModule />;
            default:
                return (
                    <div style={{ textAlign: 'center', color: tokens.color?.danger, padding: tokens.spacing?.xl }}>
                        <AlertTriangle size={32} />
                        <h3 style={{ margin: tokens.spacing?.md }}>Module Not Found</h3>
                        <p>The requested Employee portal module "{mod}" could not be loaded.</p>
                    </div>
                );
        }
    };

    const moduleTitleMap = {
        dashboard: 'My Personalized Dashboard',
        leave: 'Leave Management & Balance',
        pii: 'PII Security & Benefits',
    };
    
    const styles = useMemo(() => ({
        container: { minHeight: '100%', display: 'flex', flexDirection: 'column' },
        header: {
            color: tokens.color?.['text-100'],
            marginBottom: tokens.spacing?.lg,
            borderBottom: `1px solid ${tokens.color?.['border-600']}`,
            paddingBottom: tokens.spacing?.md,
        },
        title: {
            fontSize: tokens.typography?.h1?.fontSize, // FIX: Safe access
            margin: 0,
            display: 'flex',
            alignItems: 'center',
            gap: tokens.spacing?.sm,
        },
        // NEW FIX: Fixed container for the Digital Twin Chat Widget
        chatFixedContainer: {
            position: 'fixed', // Pin to viewport
            bottom: tokens.spacing?.lg,
            right: tokens.spacing?.lg,
            zIndex: 1000, // Ensure it's above other content
        }
    }), []);

    return (
        <div style={styles.container} className="portal-container">
            <div style={styles.header}>
                <h1 style={styles.title}>
                    <User size={32} color={tokens.color?.['accent-secondary']} />
                    Employee Portal: {moduleTitleMap[module] || 'Unknown Module'}
                </h1>
            </div>
            
            {/* Render the dynamically selected module component */}
            {getModuleComponent(module)}
            
            {/* CRITICAL INTEGRATION: Digital Twin Chat Widget */}
            {/* NEW FIX: Wrapped the chat widget in a fixed position container */}
            <div style={styles.chatFixedContainer}>
                <DigitalTwinChat isWidget={true} />
            </div>

            <style>{`
                .leave-submit-hover:hover {
                    box-shadow: 0 0 10px ${tokens.color?.success}77;
                    transform: translateY(-1px);
                }
                .pii-unmask-hover:hover {
                    box-shadow: 0 0 10px ${tokens.color?.warning}77;
                    transform: translateY(-1px);
                }
                .pii-revoke-hover:hover {
                    color: ${tokens.color?.danger} !important;
                }
            `}</style>
        </div>
    );
});

EmployeePortalComponent.displayName = 'EmployeePortalComponent';
export default EmployeePortalComponent;