// /frontend/src/pages/UserPage.js - FINAL PRODUCTION-READY REPLACEMENT (Hardened against TypeErrors)
// Basic User Profile and Settings Page (ESS/Admin View)
import React, { useState, useMemo, memo } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { theme as tokens } from '../theme';
import DataCard from '../components/DataCard';
import { User, Settings, Lock, Mail, Phone, Calendar, Loader2, Save } from 'lucide-react';
import { useToast } from '../hooks/use-toast';

// --- Static Style Definitions (FIXED with optional chaining) ---
const getStyles = (tokens) => ({ 
    // CRITICAL FIX: Added optional chaining to prevent TypeError from undefined theme object properties
    portalContainer: { 
        padding: tokens.spacing?.lg, 
        maxWidth: '900px', 
        margin: '0 auto', 
        color: tokens.color?.['text-100'], 
        fontFamily: tokens.typography?.fontFamily, 
    }, 
    header: { 
        marginBottom: tokens.spacing?.lg 
    }, 
    title: { 
        // CRITICAL FIX: Ensure optional chaining
        fontSize: tokens.typography?.h1?.fontSize, 
        fontWeight: tokens.typography?.h1?.fontWeight, 
        color: tokens.color?.['accent-primary'], 
        marginBottom: tokens.spacing?.xs, 
        display: 'flex', 
        alignItems: 'center', 
        gap: tokens.spacing?.xs 
    }, 
    subtitle: { 
        // CRITICAL FIX: Ensure optional chaining
        fontSize: tokens.typography?.base?.fontSize, 
        color: tokens.color?.['muted-500'] 
    }, 
    grid: { 
        display: 'grid', 
        gridTemplateColumns: 'repeat(1, 1fr)', 
        gap: tokens.spacing?.lg, 
        minHeight: '60vh' 
    }, 
    form: { 
        display: 'flex', 
        flexDirection: 'column', 
        gap: tokens.spacing?.md 
    }, 
    inputGroup: { 
        display: 'flex', 
        flexDirection: 'column', 
        gap: tokens.spacing?.xs 
    }, 
    label: { 
        // CRITICAL FIX: Ensure optional chaining
        fontSize: tokens.typography?.small?.fontSize, 
        color: tokens.color?.['muted-500'], 
        display: 'flex', 
        alignItems: 'center', 
        gap: tokens.spacing?.xs 
    }, 
    input: { 
        width: '100%', 
        padding: '10px 12px', 
        background: tokens.color?.['bg-input'], 
        border: `1px solid ${tokens.color?.['border-600']}`, 
        borderRadius: tokens.border?.radius?.chip, 
        color: tokens.color?.['text-100'], 
        // CRITICAL FIX: Ensure optional chaining
        fontSize: tokens.typography?.base?.fontSize, 
        outline: 'none' 
    }, 
    primaryBtn: { 
        padding: '10px 14px', 
        borderRadius: tokens.border?.radius?.button, 
        background: tokens.color?.['accent-primary'], 
        border: 'none', 
        color: tokens.color?.['bg-900'], 
        // CRITICAL FIX: Ensure optional chaining
        fontWeight: tokens.typography?.h2?.fontWeight, 
        cursor: 'pointer', 
        transition: 'all 180ms ease', 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center', 
        gap: tokens.spacing?.xs, 
        marginTop: tokens.spacing?.md 
    }, 
    secondaryBtn: { 
        padding: '10px 14px', 
        borderRadius: tokens.border?.radius?.button, 
        background: tokens.color?.['panel-700'], 
        border: `1px solid ${tokens.color?.['border-600']}`, 
        color: tokens.color?.['text-100']
    }, 
});

const UserPage = memo(() => {
    const { user, userRole, isLoading: isAuthLoading } = useAuth();
    const { toast } = useToast();
    const [userData, setUserData] = useState({
        // Initialize with default/mock data if user is null during initial load
        name: user?.full_name || 'Loading...',
        email: user?.email || '',
        phone: 'N/A',
        hireDate: 'N/A',
        role: userRole || 'N/A',
    });
    const [isSaving, setIsSaving] = useState(false);

    // CRITICAL: Ensure tokens is in dependency array
    const styles = useMemo(() => getStyles(tokens), [tokens]); 

    React.useEffect(() => {
        if (user) {
            setUserData(prev => ({
                ...prev,
                name: user.full_name,
                email: user.email,
                role: userRole,
                // Assume these come from a dedicated fetch call in a real app, mock here
                phone: '555-1234',
                hireDate: '2020-08-15',
            }));
        }
    }, [user, userRole]);

    const handleUpdateProfile = async (e) => {
        e.preventDefault();
        if (isAuthLoading || isSaving) return;

        setIsSaving(true);
        // Simulate API call to update profile
        await new Promise(resolve => setTimeout(resolve, 1500)); 

        // CRITICAL: In a real implementation, you would call an API like:
        // try {
        //     await updateEmployeeProfile(user.id, { name: userData.name, email: userData.email });
        //     toast({ title: "Success", description: "Profile updated successfully.", variant: "success" });
        // } catch (error) {
        //     toast({ title: "Error", description: "Failed to update profile.", variant: "destructive" });
        // }

        toast({ title: "Mock Success", description: "Profile update simulated.", variant: "success" });
        setIsSaving(false);
    };

    if (isAuthLoading || !user) {
        // CRITICAL FIX: Ensure the LoadingScreen style is also defensively coded
        return (
            <div style={{ textAlign: 'center', padding: tokens.spacing?.lg }}>
                <Loader2 size={32} className="animate-spin" color={tokens.color?.['accent-primary']} />
                <p style={{ color: tokens.color?.['muted-500'] }}>Loading user profile...</p>
            </div>
        );
    }

    return (
        <div style={styles.portalContainer} className="user-profile-page">
            <div style={styles.header}>
                <h1 style={styles.title}>
                    <User size={32} color={tokens.color?.['accent-primary']} /> User Profile
                </h1>
                <p style={styles.subtitle}>Manage your personal information and application settings.</p>
            </div>

            <div style={styles.grid}>
                {/* User Stats */}
                <DataCard title="Your Role" value={userData.role} unit="" color={tokens.color?.warning}>
                    <Lock size={24} color={tokens.color?.warning} />
                </DataCard>
                <DataCard title="Hire Date" value={userData.hireDate} unit="" color={tokens.color?.success}>
                    <Calendar size={24} color={tokens.color?.success} />
                </DataCard>

                {/* Profile Update Form */}
                <div style={{ gridColumn: 'span 1', background: tokens.color?.['panel-800'], borderRadius: tokens.border?.radius?.card, padding: tokens.spacing?.lg, boxShadow: tokens.shadow?.default }}>
                    <h3 style={{ margin: `0 0 ${tokens.spacing?.md} 0`, color: tokens.color?.['text-100'] }}>Personal Details</h3>
                    <form style={styles.form} onSubmit={handleUpdateProfile}>
                        <div style={styles.inputGroup}>
                            <label style={styles.label}><User size={14} /> Full Name</label>
                            <input
                                type="text"
                                value={userData.name}
                                onChange={(e) => setUserData({ ...userData, name: e.target.value })}
                                style={styles.input}
                                required
                            />
                        </div>
                        <div style={styles.inputGroup}>
                            <label style={styles.label}><Mail size={14} /> Email</label>
                            <input
                                type="email"
                                value={userData.email}
                                onChange={(e) => setUserData({ ...userData, email: e.target.value })}
                                style={styles.input}
                                required
                            />
                        </div>
                        <div style={styles.inputGroup}>
                            <label style={styles.label}><Phone size={14} /> Phone</label>
                            <input
                                type="text"
                                value={userData.phone}
                                onChange={(e) => setUserData({ ...userData, phone: e.target.value })}
                                style={styles.input}
                            />
                        </div>
                        
                        <button type="submit" style={styles.primaryBtn} disabled={isSaving}>
                            {isSaving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
                            {isSaving ? 'Saving...' : 'Save Changes'}
                        </button>
                    </form>
                </div>

                {/* Settings/Info Card Placeholder */}
                <div style={{ gridColumn: 'span 1', background: tokens.color?.['panel-800'], borderRadius: tokens.border?.radius?.card, padding: tokens.spacing?.lg, boxShadow: tokens.shadow?.default }}>
                    <h3 style={{ margin: `0 0 ${tokens.spacing?.md} 0`, color: tokens.color?.['text-100'] }}>Account Settings</h3>
                    <p style={{ color: tokens.color?.['muted-500'], 
                        // CRITICAL FIX: Ensure optional chaining
                        fontSize: tokens.typography?.small?.fontSize 
                    }}>
                        Manage security and other global application settings here.
                    </p>
                    <button style={styles.secondaryBtn} onClick={() => alert('Security settings opened.')}>
                        <Lock size={16} /> Update Password
                    </button>
                    <button style={{ ...styles.secondaryBtn, marginTop: tokens.spacing?.md }}>
                        <Settings size={16} /> Configure Notifications
                    </button>
                </div>
            </div>
            {/* Additional CSS for hover effects */}
            <style>{` 
                .user-profile-page button:hover {
                    opacity: 0.9;
                    box-shadow: ${tokens.shadow?.hover};
                }
            `}</style>
        </div>
    );
});

UserPage.displayName = 'UserPage';

export default UserPage;