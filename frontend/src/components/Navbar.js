// /frontend/src/components/Navbar.js - FINAL PRODUCTION-READY REPLACEMENT
import React, { useMemo, memo } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { theme as tokens } from '../theme';
import { settings } from '../config/settings';
import { LogOut, Menu, User } from 'lucide-react';

// --- Status Ring Component (Duplicated from App.js for standalone stability) ---
const StatusRing = memo(({ status = 'online' }) => {
    const statusColor = status === 'online' ? tokens.color?.success : status === 'warning' ? tokens.color?.warning : tokens.color?.danger;
    const pulseClass = status === 'online' ? 'status-pulse-online' : status === 'warning' ? 'status-pulse-warning' : '';
    // CRITICAL FIX: Ensure RGB conversion handles missing tokens defensively
    const statusRgb = status === 'online' ? tokens.color?.['success-rgb'] || '75, 255, 131' : tokens.color?.['warning-rgb'] || '255, 195, 0';
    
    return (
        <div style={{
            position: 'absolute', top: -1,
            right: -1,
            width: '12px', height: '12px',
            background: statusColor,
            borderRadius: '50%',
            border: `2px solid ${tokens.color?.['panel-900']}`,
            zIndex: 10,
        }} className={pulseClass}>
            <style>{`
            @keyframes pulse-online {
                0% { box-shadow: 0 0 0 0 rgba(${statusRgb}, 0.7); }
                70% { box-shadow: 0 0 0 6px rgba(${statusRgb}, 0.0); }
                100% { box-shadow: 0 0 0 0 rgba(${statusRgb}, 0.7);}
            }
            .status-pulse-online {
                animation: pulse-online 2s infinite ease-out;
            }
            @keyframes pulse-warning {
                0% { box-shadow: 0 0 0 0 rgba(${statusRgb}, 0.7); }
                70% { box-shadow: 0 0 0 6px rgba(${statusRgb}, 0.2); }
                100% { box-shadow: 0 0 0 0 rgba(${statusRgb}, 0.7);}
            }
            .status-pulse-warning {
                animation: pulse-warning 2s infinite ease-out;
            }
            `}</style>
        </div>
    );
});
StatusRing.displayName = 'StatusRing';


/**
 * Global application navigation bar.
 */
const Navbar = memo(({ onSidebarToggle }) => {
    const { user, logout, userRole } = useAuth();
    const isAuthenticated = !!user;
    
    // CRITICAL FIX: Determine status dynamically based on the role VALUE
    // This uses the Hrit Manager role (hrit_admin) as the critical monitor.
    const systemStatus = userRole === settings.ROLES.HRIT_MANAGER.toLowerCase() ? 'warning' : 'online';
    const navLinkColor = tokens.color?.['accent-primary'];

    const styles = useMemo(() => ({
        nav: {
            background: tokens.color?.['panel-800'],
            borderBottom: `1px solid ${tokens.color?.['border-600']}`,
            padding: `${tokens.spacing?.sm} ${tokens.spacing?.lg}`,
            height: '60px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            color: tokens.color?.['text-100'],
            position: 'sticky',
            top: 0,
            zIndex: 999,
            boxShadow: tokens.shadow?.card
        },
        logoGroup: {
            fontWeight: 'bold', 
            fontSize: tokens.typography?.h2?.fontSize, // FIX: Optional Chaining
            color: navLinkColor, 
            display: 'flex', 
            alignItems: 'baseline'
        },
        toggleButton: {
            background: 'none',
            border: 'none',
            color: tokens.color?.['text-100'],
            cursor: 'pointer',
            padding: tokens.spacing?.xs
        },
        userInfoGroup: { 
            display: 'flex', 
            gap: tokens.spacing?.lg, 
            alignItems: 'center' 
        },
        profileRing: {
            textDecoration: 'none',
            color: tokens.color?.['accent-secondary'],
            display: 'flex',
            alignItems: 'center',
            position: 'relative',
            padding: tokens.spacing?.sm,
            borderRadius: '50%',
            background: tokens.color?.['panel-900'],
            border: `1px solid ${tokens.color?.['border-600']}`
        },
        logoutButton: {
            background: 'rgba(255, 107, 107, 0.1)',
            color: tokens.color?.danger,
            border: `1px solid ${tokens.color?.danger}`,
            padding: '5px 12px',
            borderRadius: tokens.border?.radius?.button,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: tokens.spacing?.xs,
            // --- FIX: Optional Chaining ---
            fontWeight: tokens.typography?.h2?.fontWeight 
            // -----------------------------
        }
    }), [navLinkColor]);

    if (!isAuthenticated) return (
        <nav style={{ ...styles.nav, justifyContent: 'flex-start' }}>
            <div style={styles.logoGroup}>
                Org360 <span style={{fontSize: tokens.typography?.small?.fontSize, color:tokens.color?.['muted-500'], marginLeft: tokens.spacing?.xs}}>v4.0</span>
            </div>
        </nav>
    );

    return (
        <nav style={styles.nav}>
            <div style={{display: 'flex', alignItems: 'center', gap: tokens.spacing?.md}}>
                <button
                    onClick={onSidebarToggle}
                    style={styles.toggleButton}
                    title="Toggle Sidebar"
                >
                    <Menu size={20} />
                </button>
                <div style={styles.logoGroup}>
                    HiRo <span style={{fontSize: tokens.typography?.small?.fontSize, color:tokens.color?.['muted-500'], marginLeft: tokens.spacing?.xs}}>v4.0</span>
                </div>
            </div>
            
            <div style={styles.userInfoGroup}>
                {/* User Info & Status */}
                <div style={{ display: 'flex', flexDirection: 'column', textAlign: 'right', marginRight: tokens.spacing?.md }}>
                    <span style={{ 
                        // --- FIX: Optional Chaining ---
                        fontSize: tokens.typography?.base?.fontSize, 
                        fontWeight: tokens.typography?.h2?.fontWeight 
                        // -----------------------------
                    }}>
                        {user?.full_name}
                    </span>
                    <span style={{
                        fontSize: tokens.typography?.small?.fontSize,
                        color: systemStatus === 'online' ? tokens.color?.success : tokens.color?.warning
                    }}>
                        Kernel Status: {systemStatus.toUpperCase()}
                    </span>
                </div>
                {/* Profile Link with Status Ring */}
                <Link
                    to="/user-profile"
                    style={styles.profileRing}
                    className="nav-profile-ring-hover"
                    title="View Profile"
                >
                    <User size={20} color={tokens.color?.['accent-secondary']} />
                    <StatusRing status={systemStatus} />
                </Link>
                
                <button
                    onClick={logout}
                    style={styles.logoutButton}
                    title="Logout"
                    className="nav-logout-btn-hover"
                >
                    <LogOut size={16} /> Logout
                </button>
            </div>
             <style>{`
                .nav-logout-btn-hover:hover {
                    background: ${tokens.color?.danger} !important;
                    color: ${tokens.color?.['text-100']} !important;
                    box-shadow: 0 0 8px ${tokens.color?.danger} !important;
                }
                .nav-profile-ring-hover:hover {
                    transform: scale(1.05);
                    background: ${tokens.color?.['panel-700']} !important;
                }
            `}</style>
        </nav>
    );
});

Navbar.displayName = 'Navbar';
export default Navbar;