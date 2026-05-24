// /frontend/src/components/RoleNavDashboard.js - FINAL PRODUCTION-READY REPLACEMENT
import React, { useMemo, memo } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { theme as tokens } from '../theme';
import { SIDEBAR_NAV, hasAccess } from '../config/portalAccess'; // CRITICAL FIX: Import NAV config
import RoleNavCard from './RoleNavCard'; // Assuming RoleNavCard exists
import { Home, Users } from 'lucide-react';

/**
 * Renders a dashboard showing all portals/roles the current user has access to.
 */
const RoleNavDashboard = memo(() => {
    const { user, userRole } = useAuth();
    
    // CRITICAL: Filter roles down to what the user can actually access
    const availablePortals = useMemo(() => {
        return SIDEBAR_NAV.filter(item => hasAccess(userRole, item.path));
    }, [userRole]);

    const styles = useMemo(() => ({
        container: { minHeight: '100%' },
        header: { color: tokens.color?.['text-100'], marginBottom: tokens.spacing?.lg, borderBottom: `1px solid ${tokens.color?.['border-600']}`, paddingBottom: tokens.spacing?.md },
        title: { fontSize: tokens.typography.h1.fontSize, margin: 0, display: 'flex', alignItems: 'center', gap: tokens.spacing?.sm },
        grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: tokens.spacing?.lg, marginTop: tokens.spacing?.lg }
    }), []);

    return (
        <div style={styles.container}>
            <div style={styles.header}>
                <h1 style={styles.title}>
                    <Home size={32} color={tokens.color?.['accent-secondary']} />
                    Role-Based Access Hub
                </h1>
                <p style={{ color: tokens.color?.['muted-500'], margin: 0 }}>
                    Welcome, {user?.full_name}. Select a core portal to begin your work ({userRole} access).
                </p>
            </div>
            
            <p style={{ color: tokens.color?.['text-100'] }}>
                You have access to **{availablePortals.length}** unique portals and tools:
            </p>

            <div style={styles.grid}>
                {availablePortals.map(item => (
                    <RoleNavCard key={item.path} item={item} />
                ))}
            </div>
            
            {availablePortals.length === 0 && (
                <div style={{ textAlign: 'center', color: tokens.color?.danger, padding: tokens.spacing?.xl }}>
                    <AlertTriangle size={32} />
                    <h3 style={{ margin: tokens.spacing?.md }}>Access Restriction</h3>
                    <p>You currently do not have access to any defined portals.</p>
                </div>
            )}
        </div>
    );
});

RoleNavDashboard.displayName = 'RoleNavDashboard';
export default RoleNavDashboard;