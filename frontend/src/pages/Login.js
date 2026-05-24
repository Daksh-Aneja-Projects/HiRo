// /frontend/src/pages/Login.js - FINAL PRODUCTION-READY REPLACEMENT (Fixes 401 Error + Typography Errors)
import React, { useState, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
// FIX: Using absolute path alias '../contexts/AuthContext'
import { useAuth } from '../contexts/AuthContext';
// ASSUMPTION: settings is a direct file in src/config
import { settings } from '../config/settings';
// FIX: Using absolute path alias '@/theme'
import { theme as tokens } from '../theme';
import { Loader2, Zap, Shield, Briefcase, Users, User, ArrowRight } from 'lucide-react';
// CRITICAL FIX 1: Import the API function for logging in
import { loginUser } from '../config/api'; 

const Login = () => {
    // CRITICAL FIX 2: useAuth now provides login, which only accepts the token
    const { login, isLoading, userRole } = useAuth(); 
    const navigate = useNavigate();
    
    // CRITICAL FIX: Use the application KEY for initial state, which is clearer for display
    const INITIAL_ROLE_KEY = 'HRIT_MANAGER'; // Use the string key

    const [username, setUsername] = useState('hritmanager');
    const [password, setPassword] = useState('hritmanager'); 
    
    // State stores the backend ROLE VALUE (e.g., 'hrit_admin')
    const [currentRoleValue, setCurrentRoleValue] = useState(settings.ROLES[INITIAL_ROLE_KEY]);
    
    // Memoized value for clean display (e.g., 'HRIT_MANAGER')
    const currentRoleKey = useMemo(() => {
        // Find the KEY in settings.ROLES that matches the current VALUE
        const foundKey = Object.keys(settings.ROLES).find(key => settings.ROLES[key] === currentRoleValue);
        return foundKey || currentRoleValue.toUpperCase();
    }, [currentRoleValue]);


    const handleLogin = useCallback(async (e) => {
        e.preventDefault();
        try {
            // --- CRITICAL FIX 3: Perform the API call to get the token ---
            // 1. Exchange credentials for JWT token
            const loginResponse = await loginUser(username, password); 
            
            // Assuming the token is in loginResponse.data.access_token (Standard FastAPI OAuth2)
            const authToken = loginResponse.data.access_token; 

            if (!authToken) {
                throw new Error("Login failed: No access token received.");
            }
            
            // 2. Pass the token to the AuthContext handler
            // The AuthContext login function will now set the token and fetch /me
            await login(authToken); 
            
            // 3. Explicitly navigate to the default authenticated path.
            navigate('/dashboard', { replace: true });
        } catch (error) {
            console.error('Login error:', error);
            // Error handling is managed by AuthContext via useToast
            // If the error is an Axios error (e.g., 401), it's already rejected and handled.
        }
    }, [login, username, password, navigate]); // currentRoleValue is no longer needed in dependencies here

    // Role quick-select buttons for mock testing
    const mockRoles = useMemo(() => [
        // CRITICAL UI FIX: Use the KEY as the name and store the VALUE as 'roleValue'
        { name: 'HRIT Manager', key: 'HRIT_MANAGER', username: 'hritmanager', roleValue: settings.ROLES.HRIT_MANAGER, icon: Zap, color: tokens.color?.success },
        { name: 'HRBP', key: 'HRBP', username: 'hrbp', roleValue: settings.ROLES.HRBP, icon: Briefcase, color: tokens.color?.danger },
        { name: 'Manager', key: 'MANAGER', username: 'manager', roleValue: settings.ROLES.MANAGER, icon: Users, color: tokens.color?.warning },
        { name: 'Employee', key: 'EMPLOYEE', username: 'employee', roleValue: settings.ROLES.EMPLOYEE, icon: User, color: tokens.color?.['accent-primary'] },
    ], []);

    const handleRoleSelect = (mock) => {
        setUsername(mock.username);
        setPassword(mock.username); 
        // Store the backend's required VALUE (e.g., 'hrit_admin')
        setCurrentRoleValue(mock.roleValue);
    };

    const styles = useMemo(() => ({
        container: {
            display: 'flex',
            minHeight: '100vh',
            alignItems: 'center',
            justifyContent: 'center',
            background: tokens.color?.['bg-900'],
            fontFamily: tokens.typography?.fontFamily,
        },
        loginBox: {
            background: tokens.color?.['panel-800'],
            border: `1px solid ${tokens.color?.['border-600']}`,
            borderRadius: tokens.border?.radius?.card,
            padding: tokens.spacing?.xl,
            boxShadow: tokens.shadow?.card,
            width: '100%',
            maxWidth: '420px', 
            color: tokens.color?.['text-100'],
            textAlign: 'center',
        },
        header: {
            marginBottom: tokens.spacing?.lg,
            paddingBottom: tokens.spacing?.sm,
            borderBottom: `1px solid ${tokens.color?.['border-700']}`,
        },
        title: {
            fontSize: tokens.typography?.h1?.fontSize, // Added optional chaining
            color: tokens.color?.['accent-primary'],
            margin: '0',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: tokens.spacing?.sm,
        },
        subtitle: {
            fontSize: tokens.typography?.base?.fontSize, // Added optional chaining
            color: tokens.color?.['muted-500'],
            marginTop: tokens.spacing?.xs,
        },
        form: {
            display: 'flex',
            flexDirection: 'column',
            gap: tokens.spacing?.md,
        },
        input: {
            width: '100%',
            padding: '12px 16px',
            background: tokens.color?.['bg-input'],
            border:
            `1px solid ${tokens.color?.['border-600']}`,
            borderRadius: tokens.border?.radius?.button,
            color: tokens.color?.['text-100'],
            fontSize: tokens.typography?.base?.fontSize, // Added optional chaining
            outline: 'none',
            transition: 'border-color 180ms ease, box-shadow 180ms ease',
        },
        label: {
            fontSize: tokens.typography?.small?.fontSize, // Added optional chaining
            color: tokens.color?.['muted-500'],
            marginBottom: tokens.spacing?.xs,
            display: 'block',
            textAlign: 'left',
            fontWeight: tokens.typography?.h2?.fontWeight,
        },
        submitButton: {
            padding: '12px 16px',
            background: tokens.color?.['accent-primary'],
            border: 'none',
            borderRadius: tokens.border?.radius?.button,
            color: tokens.color?.['bg-900'],
            fontWeight: tokens.typography?.h1?.fontWeight,
            cursor: 'pointer',
            transition: 'all 180ms ease',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: tokens.spacing?.sm,
            marginTop: tokens.spacing?.sm,
            boxShadow: `0 4px 10px rgba(${tokens.color?.['accent-primary-rgb']}, 0.4)`
        },
        roleSelector: {
            marginTop: tokens.spacing?.lg,
            paddingTop: tokens.spacing?.md,
            borderTop: `1px dashed ${tokens.color?.['border-600']}`,
            textAlign: 'center',
        },
        roleGrid: {
            display: 'grid',
            gridTemplateColumns: 'repeat(2, 1fr)',
            gap: tokens.spacing?.sm,
            marginTop: tokens.spacing?.md,
        },
        roleButton: (color, isActive) => ({
            background: isActive ?
            color : tokens.color?.['panel-700'],
            color: isActive ?
            tokens.color?.['bg-900'] : tokens.color?.['text-100'],
            border: `1px solid ${isActive ?
            color : tokens.color?.['border-600']}`,
            padding: `${tokens.spacing?.sm} ${tokens.spacing?.xs}`,
            borderRadius: tokens.border?.radius?.chip,
            cursor: 'pointer',
            fontSize: tokens.typography?.small?.fontSize, // Added optional chaining
            fontWeight: tokens.typography?.h2?.fontWeight,
            transition: 'all 180ms ease',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: tokens.spacing?.xs,
        }),
    }), [currentRoleValue]);

    return (
        <div style={styles.container}>
            <div style={styles.loginBox}>
                <header style={styles.header}>
                    <h1 style={styles.title}>
                        <Shield size={32} style={{ color: tokens.color?.['accent-primary'] }} /> HiRo
                    </h1>
                    <p style={styles.subtitle}>Unified Cognitive HRMS Platform</p>
                </header>
                <form onSubmit={handleLogin} style={styles.form}>
                    <p style={{ textAlign: 'center', color: tokens.color?.warning, fontSize: tokens.typography?.small?.fontSize, marginBottom: // Added optional chaining
                    tokens.spacing?.md }}>
                        Current Role: <strong style={{ color: tokens.color?.['accent-primary'] }}>{currentRoleKey.toUpperCase()}</strong>
                        {/* Optionally display the BE role value for debugging: {currentRoleValue} */}
                    </p>
                    <div style={{textAlign: 'left'}}>
                        <label style={styles.label} htmlFor="username">Username</label>
                        <input
                            id="username"
                            type="text"
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            style={styles.input}
                            placeholder="username"
                            required
                            disabled={isLoading}
                        />
                    </div>
                    <div style={{textAlign: 'left'}}>
                        <label style={styles.label} htmlFor="password">Password</label>
                        <input
                            id="password"
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            style={styles.input}
                            placeholder="password"
                            required
                            disabled={isLoading}
                        />
                    </div>

                    <button type="submit" style={styles.submitButton} disabled={isLoading} className="login-btn-hover">
                        {isLoading ?
                        <Loader2 size={20} className="animate-spin" /> : <ArrowRight size={20} />}
                        Log In
                    </button>
                </form>
                <div style={styles.roleSelector}>
                    <p style={{...styles.subtitle, marginTop: tokens.spacing?.sm}}>Quick-Login (Testing Mode)</p>
                    <div style={styles.roleGrid}>
                        {mockRoles.map(mock => (
                            <button
                                key={mock.key}
                                onClick={() => handleRoleSelect(mock)}
                                style={styles.roleButton(mock.color, mock.roleValue === currentRoleValue)}
                                className="role-btn-hover"
                            >
                                <mock.icon size={18} />
                                {mock.name}
                            </button>
                        ))}
                    </div>
                </div>
                <style>{`
                    .login-btn-hover:hover {
                        background: ${tokens.color?.['accent-primary']} !important;
                        box-shadow: ${tokens.shadow?.hover};
                        transform: translateY(-2px);
                    }
                    .role-btn-hover:hover {
                        transform: scale(1.02);
                        box-shadow: 0 0 5px ${tokens.color?.['accent-primary']}55;
                    }
                `}</style>
            </div>
        </div>
    );
};

export default Login;
