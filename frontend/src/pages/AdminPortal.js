// /frontend/src/pages/AdminPortal.js - FINAL PRODUCTION-READY REPLACEMENT
import React, { useMemo, memo, useState, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import { theme as tokens } from '../theme';

// CRITICAL API IMPORTS
import { 
    getAdminDashboardData, getAllUsers, createUserAccount, 
    updateUserRole, deleteUser, triggerPQCKeyRotation, 
    resetAllData, clearSystemCache, runSystemIntegrityCheck 
} from '../config/api'; 
import { useApi } from '../hooks/useApi';
import { useToast } from '../hooks/use-toast';
import { settings } from '../config/settings';

// UI COMPONENTS
import DataCard from '../components/DataCard';
import AreaChartWidget from '../components/charts/AreaChartWidget';
import { useMetricSeries } from '../components/live/LivePrimitives';
import {
    Users, Shield, Settings, AlertTriangle, 
    CheckCircle, XCircle, Loader2, Key, Trash2 
} from 'lucide-react';

// Dedupe: SUPER_ADMIN and HRIT_MANAGER share the value 'hrit_admin'.
const availableRoles = [...new Set(Object.values(settings.ROLES).filter(r => r !== settings.ROLES.GUEST))];

// --- 11.1. Sub-Module: User Management ---
/**
 * Handles viewing, creating, and deleting user accounts.
 */
const UserManagementModule = memo(() => {
    const { toast } = useToast();
    
    // CRITICAL API INTEGRATION 1: Fetch All Users
    const {
        data: usersResp,
        isLoading: isUsersLoading,
        error: usersError,
        refetch: refetchUsers
    } = useApi(getAllUsers, [], true, 300000); // poll every 5 minutes
    // Backend returns { users: [...], count }; normalize to an array for rendering.
    const users = Array.isArray(usersResp) ? usersResp : (usersResp?.users || []);

    const [newUserData, setNewUserData] = useState({ 
        full_name: '', 
        email: '', 
        role: availableRoles[0] 
    });
    const [isCreatingUser, setIsCreatingUser] = useState(false);
    const [selectedUserForEdit, setSelectedUserForEdit] = useState(null);

    // CRITICAL: Handle User Creation
    const handleCreateUser = useCallback(async (e) => {
        e.preventDefault();
        if (!newUserData.full_name || !newUserData.email || !newUserData.role) {
            toast({ title: 'Error', description: 'All fields are required.', variant: 'warning' });
            return;
        }
        setIsCreatingUser(true);
        try {
            await createUserAccount(newUserData);
            toast({ title: 'Success', description: `User ${newUserData.full_name} created successfully.`, variant: 'success' });
            setNewUserData({ full_name: '', email: '', role: availableRoles[0] });
            refetchUsers(); // Refresh the list
        } catch (error) {
            console.error("User creation failed:", error);
            toast({ title: 'Error', description: `Failed to create user: ${error.message}`, variant: 'danger' });
        } finally {
            setIsCreatingUser(false);
        }
    }, [newUserData, refetchUsers, toast]);

    // CRITICAL: Handle User Deletion
    const handleDeleteUser = useCallback(async (userId, userName) => {
        if (!window.confirm(`Are you sure you want to permanently delete user ${userName}? This action cannot be undone.`)) {
            return;
        }
        try {
            await deleteUser(userId);
            toast({ title: 'Success', description: `User ${userName} deleted successfully.`, variant: 'success' });
            refetchUsers(); // Refresh the list
        } catch (error) {
            console.error("User deletion failed:", error);
            toast({ title: 'Error', description: `Failed to delete user: ${error.message}`, variant: 'danger' });
        }
    }, [refetchUsers, toast]);

    const styles = useMemo(() => ({
        grid: { display: 'grid', gridTemplateColumns: 'repeat(12, 1fr)', gap: tokens.spacing?.lg, marginBottom: tokens.spacing?.lg },
        formColumn: { gridColumn: 'span 4', padding: tokens.spacing?.md, background: tokens.color?.['panel-700'], borderRadius: tokens.border?.radius?.card, display: 'flex', flexDirection: 'column', gap: tokens.spacing?.md },
        listColumn: { gridColumn: 'span 8', minHeight: '600px', background: tokens.color?.['panel-800'], borderRadius: tokens.border?.radius?.card, padding: tokens.spacing?.md, overflowY: 'auto' },
        inputField: { padding: '10px 12px', background: tokens.color?.['bg-input'], border: `1px solid ${tokens.color?.['border-600']}`, borderRadius: tokens.border?.radius?.input, color: tokens.color?.['text-100'] },
        listItem: { padding: tokens.spacing?.sm, borderBottom: `1px solid ${tokens.color?.['border-600']}`, display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
        deleteButton: { padding: '5px 10px', background: tokens.color?.danger, border: 'none', borderRadius: tokens.border?.radius?.button, color: tokens.color?.['bg-deep'], cursor: 'pointer', marginLeft: tokens.spacing?.md }
    }), []);

    return (
        <div style={styles.grid}>
            {/* Create User Form */}
            <div style={styles.formColumn}>
                <h3 style={{ color: tokens.color?.['text-100'], margin: 0, borderBottom: `1px solid ${tokens.color?.['border-600']}`, paddingBottom: tokens.spacing?.xs }}>Create New User</h3>
                <form onSubmit={handleCreateUser} style={{ display: 'flex', flexDirection: 'column', gap: tokens.spacing?.md }}>
                    <input
                        type="text"
                        placeholder="Full Name"
                        value={newUserData.full_name}
                        onChange={(e) => setNewUserData(p => ({ ...p, full_name: e.target.value }))}
                        style={styles.inputField}
                        required
                    />
                    <input
                        type="email"
                        placeholder="Email"
                        value={newUserData.email}
                        onChange={(e) => setNewUserData(p => ({ ...p, email: e.target.value }))}
                        style={styles.inputField}
                        required
                    />
                    <select
                        value={newUserData.role}
                        onChange={(e) => setNewUserData(p => ({ ...p, role: e.target.value }))}
                        style={styles.inputField}
                        required
                    >
                        {availableRoles.map(role => (
                            <option key={role} value={role}>{role}</option>
                        ))}
                    </select>
                    <button 
                        type="submit" 
                        disabled={isCreatingUser}
                        style={{ padding: '10px 20px', background: tokens.color?.success, border: 'none', borderRadius: tokens.border?.radius?.button, color: tokens.color?.['bg-deep'], cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: tokens.spacing?.xs }}
                        className="cache-clear-hover" // Using a similar style hover
                    >
                        {isCreatingUser ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle size={16} />} 
                        {isCreatingUser ? 'Creating...' : 'Create Account'}
                    </button>
                </form>
            </div>

            {/* User List */}
            <div style={styles.listColumn}>
                <h3 style={{ color: tokens.color?.['text-100'], borderBottom: `1px solid ${tokens.color?.['border-600']}`, paddingBottom: tokens.spacing?.xs, marginBottom: tokens.spacing?.md }}>
                    Active Users ({users?.length || 0})
                </h3>
                {isUsersLoading && <p style={{textAlign: 'center'}}><Loader2 size={20} className="animate-spin" /> Loading users...</p>}
                {usersError && <p style={{ color: tokens.color?.danger }}>Error loading users list.</p>}
                
                {(users || []).map(user => (
                    <div key={user.id} style={styles.listItem}>
                        <span>{user.full_name} ({user.role}) - <span style={{ color: tokens.color?.['muted-500'] }}>{user.email}</span></span>
                        <button 
                            onClick={() => handleDeleteUser(user.id, user.full_name)} 
                            style={styles.deleteButton}
                            className="user-delete-btn-hover"
                        >
                            <Trash2 size={16} style={{ marginBottom: '-3px' }} />
                        </button>
                    </div>
                ))}
            </div>
        </div>
    );
});
UserManagementModule.displayName = 'UserManagementModule';


// --- 11.2. Sub-Module: System Health ---
const SystemHealthModule = memo(() => {
    // CRITICAL API INTEGRATION 2: Fetch Admin Dashboard Data (Not polling, run on load)
    const { 
        data: dashboard, 
        isLoading: isDashboardLoading, 
        error: dashboardError, 
        refetch: refetchDashboard
    } = useApi(getAdminDashboardData, [], true, 0); // Polling disabled

    // Genuinely live telemetry series (no historical trend endpoint exists): rolling
    // windows built from the real psutil-backed metrics feed, polled every 3s.
    const cpuSeries = useMetricSeries('cpu_load', { intervalMs: 3000 });
    const memSeries = useMetricSeries('memory_load', { intervalMs: 3000 });

    const { toast } = useToast();
    const [isRotating, setIsRotating] = useState(false);
    const [isClearing, setIsClearing] = useState(false);
    const [isChecking, setIsChecking] = useState(false);

    // CRITICAL: Rotate PQC Key
    const handleKeyRotation = useCallback(async () => {
        if (!window.confirm('Are you sure you want to rotate the Post-Quantum Cryptography key? This will affect all future transactions.')) return;
        setIsRotating(true);
        try {
            await triggerPQCKeyRotation();
            toast({ title: 'Success', description: 'PQC Key rotation initiated.', variant: 'success' });
            refetchDashboard();
        } catch (error) {
            console.error("Key rotation failed:", error);
            toast({ title: 'Error', description: `Failed to rotate key: ${error.message}`, variant: 'danger' });
        } finally {
            setIsRotating(false);
        }
    }, [refetchDashboard, toast]);

    // CRITICAL: Clear System Cache
    const handleClearCache = useCallback(async () => {
        if (!window.confirm('Are you sure you want to clear the system cache? This may temporarily impact performance.')) return;
        setIsClearing(true);
        try {
            await clearSystemCache();
            toast({ title: 'Success', description: 'System cache cleared successfully.', variant: 'success' });
            refetchDashboard();
        } catch (error) {
            console.error("Cache clearing failed:", error);
            toast({ title: 'Error', description: `Failed to clear cache: ${error.message}`, variant: 'danger' });
        } finally {
            setIsClearing(false);
        }
    }, [refetchDashboard, toast]);

    // CRITICAL: Run Integrity Check
    const handleIntegrityCheck = useCallback(async () => {
        setIsChecking(true);
        try {
            const response = await runSystemIntegrityCheck();
            toast({ title: 'Check Complete', description: response.data.message || 'System integrity check finished.', variant: response.data.status === 'PASS' ? 'success' : 'warning' });
            refetchDashboard();
        } catch (error) {
            console.error("Integrity check failed:", error);
            toast({ title: 'Error', description: `Integrity check failed: ${error.message}`, variant: 'danger' });
        } finally {
            setIsChecking(false);
        }
    }, [refetchDashboard, toast]);

    const styles = useMemo(() => ({
        grid: { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: tokens.spacing?.lg, marginBottom: tokens.spacing?.lg },
        card: { gridColumn: 'span 1' },
        chart: { gridColumn: 'span 2' },
        buttonGroup: { gridColumn: 'span 4', display: 'flex', gap: tokens.spacing?.lg, justifyContent: 'center', marginTop: tokens.spacing?.md },
        actionButton: (color) => ({
            padding: '12px 24px',
            background: color,
            border: 'none',
            borderRadius: tokens.border?.radius?.button,
            color: tokens.color?.['bg-deep'],
            cursor: 'pointer',
            fontWeight: 'bold',
            display: 'flex',
            alignItems: 'center',
            gap: tokens.spacing?.xs,
            transition: 'all 0.2s ease',
        })
    }), []);

    return (
        <>
            <div style={styles.grid}>
                {/* Dashboard Data Cards */}
                <div style={styles.card}>
                    <DataCard 
                        title="Integrity Score" 
                        value={dashboard?.integrity_score || 'N/A'} 
                        unit="/100" 
                        color={tokens.color?.['accent-secondary']}
                    >
                        <Shield size={24} color={tokens.color?.['accent-secondary']} />
                    </DataCard>
                </div>
                <div style={styles.card}>
                    <DataCard 
                        title="Active PQC Keys" 
                        value={dashboard?.active_pqc_keys || 0} 
                        unit="Count" 
                        color={tokens.color?.warning}
                    >
                        <Key size={24} color={tokens.color?.warning} />
                    </DataCard>
                </div>
                <div style={styles.card}>
                    <DataCard 
                        title="Cache Utilization" 
                        value={dashboard?.cache_util_pct || 'N/A'} 
                        unit="%" 
                        color={tokens.color?.success}
                    >
                        <CheckCircle size={24} color={tokens.color?.success} />
                    </DataCard>
                </div>
                <div style={styles.card}>
                    <DataCard 
                        title="Critical Alerts" 
                        value={dashboard?.critical_alerts || 0} 
                        unit="Count" 
                        color={tokens.color?.danger}
                    >
                        <AlertTriangle size={24} color={tokens.color?.danger} />
                    </DataCard>
                </div>

                {/* Charts — live rolling telemetry */}
                <div style={styles.chart}>
                    <DataCard title="Live CPU Load (%)" isChart minHeight="260px">
                        <AreaChartWidget data={cpuSeries} minHeight="220px" color={tokens.color?.['accent-primary']} />
                    </DataCard>
                </div>
                <div style={styles.chart}>
                    <DataCard title="Live Memory Load (%)" isChart minHeight="260px">
                        <AreaChartWidget data={memSeries} minHeight="220px" color={tokens.color?.['accent-secondary']} />
                    </DataCard>
                </div>
                
                {/* Action Buttons */}
                <div style={styles.buttonGroup}>
                    <button 
                        onClick={handleKeyRotation} 
                        disabled={isRotating}
                        style={styles.actionButton(tokens.color?.warning)}
                        className="pqc-rotate-hover"
                    >
                        {isRotating ? <Loader2 size={16} className="animate-spin" /> : <Key size={16} />} 
                        Rotate PQC Key
                    </button>
                    <button 
                        onClick={handleIntegrityCheck} 
                        disabled={isChecking}
                        style={styles.actionButton(tokens.color?.['accent-secondary'])}
                        className="integrity-check-hover"
                    >
                        {isChecking ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle size={16} />} 
                        Run Integrity Check
                    </button>
                    <button 
                        onClick={handleClearCache} 
                        disabled={isClearing}
                        style={styles.actionButton(tokens.color?.success)}
                        className="cache-clear-hover"
                    >
                        {isClearing ? <Loader2 size={16} className="animate-spin" /> : <XCircle size={16} />} 
                        Clear System Cache
                    </button>
                </div>
            </div>
            {/* Hard Purge Warning */}
            <div style={{ padding: tokens.spacing?.md, background: tokens.color?.danger, borderRadius: tokens.border?.radius?.card, marginTop: tokens.spacing?.lg, textAlign: 'center' }}>
                <p style={{ fontWeight: 'bold', color: tokens.color?.['text-100'] }}>
                    <AlertTriangle size={20} style={{ marginRight: tokens.spacing?.xs, marginBottom: '-3px' }} />
                    DANGER ZONE: System Reset
                </p>
                <button 
                    onClick={() => { if (window.confirm('ABSOLUTELY CRITICAL: This will wipe ALL non-config data. Are you 100% sure?')) resetAllData() }}
                    style={{ padding: '8px 16px', background: tokens.color?.['danger-700'], border: 'none', borderRadius: tokens.border?.radius?.button, color: tokens.color?.['text-100'], cursor: 'pointer', marginTop: tokens.spacing?.sm }}
                    className="hard-purge-hover"
                >
                    Trigger System Hard Purge
                </button>
            </div>
        </>
    );
});
SystemHealthModule.displayName = 'SystemHealthModule';


// --- MAIN ADMIN PORTAL COMPONENT ---
export const AdminPortalComponent = memo(() => {
    const location = useLocation();
    const query = new URLSearchParams(location.search);
    const module = query.get('module') || 'users'; 

    const getModuleComponent = (mod) => {
        switch (mod) {
            case 'users':
                return <UserManagementModule />;
            case 'health':
                return <SystemHealthModule />;
            default:
                return (
                    <div style={{ textAlign: 'center', color: tokens.color?.danger, padding: tokens.spacing?.xl }}>
                        <AlertTriangle size={32} />
                        <h3 style={{ margin: tokens.spacing?.md }}>Module Not Found</h3>
                        <p>The requested Admin portal module "{mod}" could not be loaded.</p>
                    </div>
                );
        }
    };

    const moduleTitleMap = {
        users: 'User & Role Management',
        health: 'System Health & Maintenance',
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
            fontSize: tokens.typography?.h1?.fontSize,
            margin: 0,
            display: 'flex',
            alignItems: 'center',
            gap: tokens.spacing?.sm,
        },
    }), []);

    return (
        <div style={styles.container} className="portal-container">
            <div style={styles.header}>
                <h1 style={styles.title}>
                    <Settings size={32} color={tokens.color?.danger} />
                    Admin Portal: {moduleTitleMap[module] || 'Unknown Module'}
                </h1>
            </div>
            
            {/* Render the dynamically selected module component */}
            {getModuleComponent(module)}
            
            <style>{`
                .user-delete-btn-hover:hover {
                    background: ${tokens.color?.['danger-700']};
                    transform: scale(1.1);
                }
                .pqc-rotate-hover:hover {
                    box-shadow: 0 0 10px ${tokens.color?.warning}77;
                    transform: translateY(-1px);
                }
                .integrity-check-hover:hover {
                    box-shadow: 0 0 10px ${tokens.color?.['accent-secondary']}77;
                    transform: translateY(-1px);
                }
                .cache-clear-hover:hover {
                    box-shadow: 0 0 10px ${tokens.color?.success}77;
                    transform: translateY(-1px);
                }
                .hard-purge-hover:hover {
                    box-shadow: 0 0 15px ${tokens.color?.danger};
                    background: ${tokens.color?.['danger-700']} !important;
                    transform: translateY(-2px);
                }
            `}</style>
        </div>
    );
});

AdminPortalComponent.displayName = 'AdminPortalComponent';
export default AdminPortalComponent;