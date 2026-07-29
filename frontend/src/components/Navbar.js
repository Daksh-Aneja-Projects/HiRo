// /frontend/src/components/Navbar.js - APPLE/GOOGLE PREMIUM REWRITE
import React from 'react';
import { useAuth } from '../contexts/AuthContext';
import { LogOut, User } from 'lucide-react';

const Navbar = () => {
    const { user, isAuthenticated, logout } = useAuth();

    if (!isAuthenticated) return null;

    return (
        <nav className="glass-panel" style={styles.navbar}>
            <div style={styles.leftSection}>
                <div style={styles.logoGroup}>
                    <span style={{fontWeight: 600, fontSize: '1.2rem', color: 'var(--text-primary)'}}>HiRo</span> 
                    <span style={{fontSize: '0.85rem', color: 'var(--text-tertiary)', marginLeft: '8px'}}>v4.0</span>
                </div>
            </div>
            
            <div style={styles.rightSection}>
                <div style={{display: 'flex', alignItems: 'center', gap: '12px'}}>
                    <div style={{textAlign: 'right', display: 'flex', flexDirection: 'column'}}>
                         <span style={{fontSize: '0.9rem', fontWeight: 500, color: 'var(--text-primary)'}}>{user?.username || 'Guest'}</span>
                         <span style={{fontSize: '0.75rem', color: 'var(--text-secondary)'}}>{user?.role || 'Guest'}</span>
                    </div>
                    <div style={{padding: '6px', background: 'var(--bg-main)', borderRadius: '50%'}}>
                        <User size={18} color="var(--text-secondary)"/>
                    </div>
                </div>
                
                <button 
                    onClick={logout} 
                    className="premium-button"
                    style={{marginLeft: '16px', background: 'var(--bg-main)', color: 'var(--accent-danger)', border: '1px solid var(--border-subtle)', boxShadow: 'none'}}
                    title="Logout"
                >
                    <LogOut size={16} />
                </button>
            </div>
        </nav>
    );
};

const styles = {
    navbar: {
        height: '64px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 32px',
        boxSizing: 'border-box',
        position: 'sticky', 
        top: 0, 
        zIndex: 1000,
        borderBottom: '1px solid var(--border-subtle)',
    },
    leftSection: {
        display: 'flex',
        alignItems: 'center',
    },
    logoGroup: {
        display: 'flex',
        alignItems: 'baseline',
    },
    rightSection: {
        display: 'flex',
        alignItems: 'center',
    },
};

export default Navbar;