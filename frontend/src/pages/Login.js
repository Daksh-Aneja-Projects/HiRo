// /frontend/src/pages/Login.js - FINAL PRODUCTION-READY REPLACEMENT (Fixes 401 Error + Typography Errors)
import React, { useState, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { settings } from '../config/settings';
import { Loader2, Zap, Shield, Briefcase, Users, User, ArrowRight } from 'lucide-react';
import { loginUser } from '../config/api'; 

const Login = () => {
    const { login, isLoading } = useAuth(); 
    const navigate = useNavigate();
    
    const INITIAL_ROLE_KEY = 'HRIT_MANAGER'; 

    const [username, setUsername] = useState('hritmanager');
    const [password, setPassword] = useState('hritmanager'); 
    
    const [currentRoleValue, setCurrentRoleValue] = useState(settings.ROLES[INITIAL_ROLE_KEY]);
    
    const currentRoleKey = useMemo(() => {
        const foundKey = Object.keys(settings.ROLES).find(key => settings.ROLES[key] === currentRoleValue);
        return foundKey || currentRoleValue.toUpperCase();
    }, [currentRoleValue]);


    const handleLogin = useCallback(async (e) => {
        e.preventDefault();
        try {
            const loginResponse = await loginUser(username, password); 
            const authToken = loginResponse.data.access_token; 

            if (!authToken) {
                throw new Error("Login failed: No access token received.");
            }
            
            await login(authToken); 
            navigate('/dashboard', { replace: true });
        } catch (error) {
            console.error('Login error:', error);
        }
    }, [login, username, password, navigate]); 

    const mockRoles = useMemo(() => [
        { name: 'HRIT Manager', key: 'HRIT_MANAGER', username: 'hritmanager', roleValue: settings.ROLES.HRIT_MANAGER, icon: Zap, color: 'var(--accent-success)' },
        { name: 'HRBP', key: 'HRBP', username: 'hrbp', roleValue: settings.ROLES.HRBP, icon: Briefcase, color: 'var(--accent-danger)' },
        { name: 'Manager', key: 'MANAGER', username: 'manager', roleValue: settings.ROLES.MANAGER, icon: Users, color: 'var(--accent-warning)' },
        { name: 'Employee', key: 'EMPLOYEE', username: 'employee', roleValue: settings.ROLES.EMPLOYEE, icon: User, color: 'var(--accent-primary)' },
    ], []);

    const handleRoleSelect = (mock) => {
        setUsername(mock.username);
        setPassword(mock.username); 
        setCurrentRoleValue(mock.roleValue);
    };

    const styles = useMemo(() => ({
        container: {
            display: 'flex',
            minHeight: '100vh',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'var(--bg-main)',
            fontFamily: "'Inter', sans-serif",
            padding: '24px',
            position: 'relative',
            overflow: 'hidden'
        },
        backgroundGlow: {
            position: 'absolute',
            width: '800px',
            height: '800px',
            background: 'radial-gradient(circle, rgba(var(--accent-primary-rgb), 0.15) 0%, rgba(var(--bg-main), 0) 70%)',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            pointerEvents: 'none',
            zIndex: 0
        },
        loginBox: {
            position: 'relative',
            zIndex: 1,
            width: '100%',
            maxWidth: '440px', 
            padding: '48px 40px',
            textAlign: 'center',
            display: 'flex',
            flexDirection: 'column',
            gap: '32px'
        },
        header: {
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '8px',
        },
        title: {
            fontSize: '32px',
            fontWeight: '600',
            color: 'var(--text-primary)',
            margin: '0',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '12px',
            letterSpacing: '-0.5px'
        },
        subtitle: {
            fontSize: '15px',
            color: 'var(--text-secondary)',
            margin: '0',
            fontWeight: '400'
        },
        form: {
            display: 'flex',
            flexDirection: 'column',
            gap: '20px',
        },
        inputGroup: {
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
            textAlign: 'left'
        },
        input: {
            width: '100%',
            padding: '14px 16px',
            background: 'var(--bg-surface)',
            border: '1px solid var(--border-subtle)',
            borderRadius: '12px',
            color: 'var(--text-primary)',
            fontSize: '15px',
            outline: 'none',
            transition: 'all 0.2s ease',
            boxShadow: 'inset 0 2px 4px rgba(0,0,0,0.02)'
        },
        label: {
            fontSize: '13px',
            color: 'var(--text-secondary)',
            fontWeight: '500',
            marginLeft: '4px'
        },
        roleIndicator: {
            fontSize: '13px',
            color: 'var(--text-secondary)',
            marginBottom: '4px'
        },
        submitButton: {
            marginTop: '8px',
            padding: '14px',
            width: '100%',
            fontSize: '15px',
            fontWeight: '500',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '8px'
        },
        roleSelector: {
            marginTop: '16px',
            paddingTop: '32px',
            borderTop: '1px solid var(--border-subtle)',
            textAlign: 'center',
        },
        roleGrid: {
            display: 'grid',
            gridTemplateColumns: 'repeat(2, 1fr)',
            gap: '12px',
            marginTop: '16px',
        },
        roleButton: (color, isActive) => ({
            background: isActive ? 'var(--bg-surface)' : 'transparent',
            color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
            border: `1px solid ${isActive ? color : 'var(--border-subtle)'}`,
            padding: '12px',
            borderRadius: '12px',
            cursor: 'pointer',
            fontSize: '13px',
            fontWeight: isActive ? '500' : '400',
            transition: 'all 0.2s ease',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '6px',
            boxShadow: isActive ? 'var(--shadow-sm)' : 'none'
        }),
    }), [currentRoleValue]);

    return (
        <div style={styles.container}>
            <div style={styles.backgroundGlow}></div>
            <div style={styles.loginBox} className="glass-panel premium-card">
                <header style={styles.header}>
                    <div style={{
                        background: 'var(--accent-primary)',
                        padding: '12px',
                        borderRadius: '20px',
                        color: 'white',
                        marginBottom: '8px',
                        boxShadow: '0 8px 24px rgba(var(--accent-primary-rgb), 0.3)'
                    }}>
                        <Shield size={32} />
                    </div>
                    <h1 style={styles.title}>HiRo</h1>
                    <p style={styles.subtitle}>Unified Cognitive HRMS Platform</p>
                </header>
                <form onSubmit={handleLogin} style={styles.form}>
                    <p style={styles.roleIndicator}>
                        Current Role: <strong style={{ color: 'var(--accent-primary)', fontWeight: '600' }}>{currentRoleKey.replace('_', ' ')}</strong>
                    </p>
                    <div style={styles.inputGroup}>
                        <label style={styles.label} htmlFor="username">Username</label>
                        <input
                            id="username"
                            type="text"
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            style={styles.input}
                            className="premium-input"
                            placeholder="Enter username"
                            required
                            disabled={isLoading}
                        />
                    </div>
                    <div style={styles.inputGroup}>
                        <label style={styles.label} htmlFor="password">Password</label>
                        <input
                            id="password"
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            style={styles.input}
                            className="premium-input"
                            placeholder="Enter password"
                            required
                            disabled={isLoading}
                        />
                    </div>

                    <button type="submit" style={styles.submitButton} disabled={isLoading} className="premium-button">
                        {isLoading ? <Loader2 size={20} className="animate-spin" /> : 'Sign In'}
                        {!isLoading && <ArrowRight size={18} />}
                    </button>
                </form>
                <div style={styles.roleSelector}>
                    <p style={styles.subtitle}>Quick-Login (Testing Mode)</p>
                    <div style={styles.roleGrid}>
                        {mockRoles.map(mock => (
                            <button
                                key={mock.key}
                                onClick={() => handleRoleSelect(mock)}
                                style={styles.roleButton(mock.color, mock.roleValue === currentRoleValue)}
                                className="role-btn-hover"
                            >
                                <mock.icon size={20} style={{ color: mock.color }} />
                                {mock.name}
                            </button>
                        ))}
                    </div>
                </div>
                <style>{`
                    .premium-input:focus {
                        border-color: var(--accent-primary) !important;
                        box-shadow: 0 0 0 4px rgba(var(--accent-primary-rgb), 0.1) !important;
                    }
                    .role-btn-hover:hover {
                        background: var(--bg-surface) !important;
                        border-color: var(--border-subtle) !important;
                        color: var(--text-primary) !important;
                    }
                `}</style>
            </div>
        </div>
    );
};

export default Login;
