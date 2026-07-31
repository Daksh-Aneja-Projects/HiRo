// Navbar — slim top bar inside the main column. Shows page context + sign out.
import React from 'react';
import { useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { LogOut } from 'lucide-react';
import NotificationBell from './NotificationBell';

const TITLES = {
    '/dashboard': 'Dashboard',
    '/employee-portal': 'My Portal',
    '/manager-portal': 'My Team',
    '/hr-portal': 'HR Operations',
    '/hrit-portal': 'HRIT Console',
    '/admin-portal': 'Administration',
    '/ultimate-orchestrator': 'Orchestrator',
    '/advanced-analytics': 'Advanced Analytics',
    '/social-feed': 'Collaboration',
    '/user-profile': 'Profile',
};

const Navbar = () => {
    const { user, isAuthenticated, logout } = useAuth();
    const location = useLocation();
    if (!isAuthenticated) return null;

    const title = TITLES[location.pathname]
        || Object.entries(TITLES).find(([p]) => location.pathname.startsWith(p))?.[1]
        || 'HiRo';

    return (
        <header style={styles.bar}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={styles.title}>{title}</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <NotificationBell />
                <span style={styles.rolePill}>{(user?.role || 'guest').replace(/_/g, ' ')}</span>
                <button onClick={logout} style={styles.logout} className="logout-btn" title="Sign out">
                    <LogOut size={15} /> Sign out
                </button>
            </div>
            <style>{`.logout-btn:hover { border-color: var(--border-strong) !important; color: var(--accent-danger) !important; }`}</style>
        </header>
    );
};

const styles = {
    bar: {
        height: 56, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 28px', borderBottom: '1px solid var(--border-subtle)', background: 'color-mix(in srgb, var(--bg-main) 80%, transparent)',
        backdropFilter: 'blur(12px)', WebkitBackdropFilter: 'blur(12px)', position: 'sticky', top: 0, zIndex: 100, boxSizing: 'border-box',
    },
    title: { fontSize: 15, fontWeight: 600, letterSpacing: '-0.01em', color: 'var(--text-primary)' },
    rolePill: {
        fontSize: 11.5, fontWeight: 600, letterSpacing: '0.03em', textTransform: 'capitalize',
        color: 'var(--accent-bright)', background: 'rgba(94,106,210,0.14)', border: '1px solid var(--border-subtle)',
        padding: '4px 10px', borderRadius: 999,
    },
    logout: {
        display: 'flex', alignItems: 'center', gap: 6, fontSize: 12.5, fontWeight: 500,
        color: 'var(--text-secondary)', background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)',
        padding: '7px 12px', borderRadius: 8, cursor: 'pointer', transition: 'all 0.15s ease', fontFamily: 'inherit',
    },
};

export default Navbar;
