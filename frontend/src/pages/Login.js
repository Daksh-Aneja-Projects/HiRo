// Login — Linear-inspired split hero. Auth flow unchanged; presentation overhauled.
import React, { useState, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { settings } from '../config/settings';
import { Loader2, ArrowRight, ShieldCheck, GitBranch, Activity } from 'lucide-react';
import { loginUser } from '../config/api';
import BrandLogo from '../components/BrandLogo';

const ROLES = [
    { name: 'HRIT Manager', username: 'hritmanager', roleValue: settings.ROLES.HRIT_MANAGER },
    { name: 'HRBP', username: 'hrbp', roleValue: settings.ROLES.HRBP },
    { name: 'Manager', username: 'manager', roleValue: settings.ROLES.MANAGER },
    { name: 'Employee', username: 'employee', roleValue: settings.ROLES.EMPLOYEE },
];

const FEATURES = [
    { icon: Activity, label: 'Explainable AI decisions', note: 'Every recommendation, traceable' },
    { icon: GitBranch, label: 'Digital-twin simulation', note: 'Model workforce change before it happens' },
    { icon: ShieldCheck, label: 'Governed by policy', note: 'Compliance enforced automatically' },
];

// Ambient orchestration constellation — a live, restrained signature visual.
const Constellation = () => (
    <svg viewBox="0 0 320 320" width="100%" height="100%" style={{ position: 'absolute', inset: 0, opacity: 0.9 }} aria-hidden="true">
        <defs>
            <radialGradient id="node" cx="50%" cy="50%" r="50%">
                <stop offset="0%" stopColor="#8b93f8" />
                <stop offset="100%" stopColor="#5e6ad2" />
            </radialGradient>
        </defs>
        {[[160,160],[70,80],[250,70],[60,240],[260,235],[160,45],[45,160],[275,160]].map((p, i) => (
            <line key={'l'+i} x1="160" y1="160" x2={p[0]} y2={p[1]} stroke="#5e6ad2" strokeOpacity="0.28" strokeWidth="1" />
        ))}
        {[[70,80,3],[250,70,3],[60,240,3],[260,235,3],[160,45,2.5],[45,160,2.5],[275,160,2.5]].map((p, i) => (
            <circle key={'n'+i} cx={p[0]} cy={p[1]} r={p[2]} fill="#3fb9e5" fillOpacity="0.9"
                    style={{ animation: `pulse 3.4s ${i * 0.4}s ease-in-out infinite` }} />
        ))}
        <circle cx="160" cy="160" r="8" fill="url(#node)" style={{ animation: 'pulse 3s ease-in-out infinite' }} />
        <circle cx="160" cy="160" r="8" fill="none" stroke="#8b93f8" strokeOpacity="0.5">
            <animate attributeName="r" values="8;22;8" dur="3.4s" repeatCount="indefinite" />
            <animate attributeName="stroke-opacity" values="0.5;0;0.5" dur="3.4s" repeatCount="indefinite" />
        </circle>
    </svg>
);

const Login = () => {
    const { login, isLoading } = useAuth();
    const navigate = useNavigate();
    const [username, setUsername] = useState('hritmanager');
    const [password, setPassword] = useState('hritmanager');
    const [roleValue, setRoleValue] = useState(settings.ROLES.HRIT_MANAGER);
    const [error, setError] = useState('');

    const handleLogin = useCallback(async (e) => {
        e.preventDefault();
        setError('');
        try {
            const res = await loginUser(username, password);
            const token = res.data.access_token;
            if (!token) throw new Error('No access token received.');
            await login(token);
            navigate('/dashboard', { replace: true });
        } catch (err) {
            setError(err.response?.data?.detail || 'Sign-in failed. Check your credentials and try again.');
        }
    }, [login, username, password, navigate]);

    const pick = (r) => { setUsername(r.username); setPassword(r.username); setRoleValue(r.roleValue); setError(''); };

    const s = useMemo(() => ({
        page: { minHeight: '100vh', width: '100%', display: 'grid', gridTemplateColumns: '1.05fr 0.95fr', background: 'var(--bg-main)' },
        hero: { position: 'relative', overflow: 'hidden', padding: '48px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', borderRight: '1px solid var(--border-subtle)' },
        heroInner: { position: 'relative', zIndex: 2, maxWidth: 460 },
        eyebrow: { fontSize: 12, letterSpacing: '0.16em', textTransform: 'uppercase', color: 'var(--text-tertiary)', fontWeight: 600, marginBottom: 22 },
        headline: { fontSize: 40, lineHeight: 1.08, fontWeight: 640, letterSpacing: '-0.03em', color: 'var(--text-primary)', margin: 0 },
        sub: { marginTop: 16, fontSize: 15.5, lineHeight: 1.6, color: 'var(--text-secondary)', maxWidth: 400 },
        featRow: { display: 'flex', alignItems: 'flex-start', gap: 12, marginTop: 18 },
        authWrap: { display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '48px 40px' },
        card: { width: '100%', maxWidth: 380, display: 'flex', flexDirection: 'column', gap: 22 },
        title: { fontSize: 22, fontWeight: 640, letterSpacing: '-0.02em', color: 'var(--text-primary)', margin: 0 },
        muted: { fontSize: 13.5, color: 'var(--text-secondary)', margin: 0 },
        label: { fontSize: 12.5, color: 'var(--text-secondary)', fontWeight: 500, marginBottom: 6, display: 'block' },
        input: { width: '100%', padding: '11px 13px', background: 'var(--bg-input)', border: '1px solid var(--border-subtle)', borderRadius: 8, color: 'var(--text-primary)', fontSize: 14, outline: 'none', fontFamily: 'inherit' },
        submit: { marginTop: 4, padding: '12px', width: '100%', fontSize: 14, fontWeight: 550, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, border: '1px solid rgba(255,255,255,0.08)', borderRadius: 8, background: 'var(--accent-primary)', color: '#fff', cursor: 'pointer' },
        chipRow: { display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8 },
        chip: (active) => ({ padding: '9px 10px', borderRadius: 8, cursor: 'pointer', fontSize: 12.5, fontWeight: 500, textAlign: 'center', border: `1px solid ${active ? 'var(--accent-primary)' : 'var(--border-subtle)'}`, background: active ? 'rgba(94,106,210,0.16)' : 'transparent', color: active ? 'var(--text-primary)' : 'var(--text-secondary)', transition: 'all 0.15s ease' }),
    }), []);

    return (
        <div style={s.page} className="login-page">
            {/* Hero */}
            <div style={s.hero} className="login-hero">
                <div style={{ position: 'absolute', top: '-10%', right: '-15%', width: 520, height: 520, zIndex: 1 }}>
                    <Constellation />
                </div>
                <BrandLogo size={30} wordmark tagline />
                <div style={s.heroInner}>
                    <div style={s.eyebrow}>Human Intelligence &amp; Resource Orchestration</div>
                    <h1 style={s.headline}>Run your entire workforce from one intelligent surface.</h1>
                    <p style={s.sub}>HiRo unifies hire-to-retire operations with autonomous agents, explainable decisions, and live workforce simulation.</p>
                    <div style={{ marginTop: 30 }}>
                        {FEATURES.map((f) => (
                            <div key={f.label} style={s.featRow}>
                                <span style={{ display: 'grid', placeItems: 'center', width: 30, height: 30, borderRadius: 8, background: 'rgba(94,106,210,0.14)', border: '1px solid var(--border-subtle)', flexShrink: 0 }}>
                                    <f.icon size={15} color="var(--accent-bright)" />
                                </span>
                                <div>
                                    <div style={{ fontSize: 13.5, fontWeight: 550, color: 'var(--text-primary)' }}>{f.label}</div>
                                    <div style={{ fontSize: 12.5, color: 'var(--text-tertiary)', marginTop: 1 }}>{f.note}</div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
                <div style={{ position: 'relative', zIndex: 2, fontSize: 12, color: 'var(--text-tertiary)' }}>
                    Running locally on your own models · No cloud keys
                </div>
            </div>

            {/* Auth */}
            <div style={s.authWrap}>
                <div style={s.card}>
                    <div style={{ marginBottom: 2 }}>
                        <h2 style={s.title}>Sign in</h2>
                        <p style={{ ...s.muted, marginTop: 6 }}>Welcome back. Choose a role below to explore, or sign in directly.</p>
                    </div>
                    <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                        <div>
                            <label style={s.label} htmlFor="username">Username</label>
                            <input id="username" type="text" value={username} onChange={(e) => setUsername(e.target.value)} style={s.input} className="premium-input" placeholder="Enter username" required disabled={isLoading} autoComplete="username" />
                        </div>
                        <div>
                            <label style={s.label} htmlFor="password">Password</label>
                            <input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} style={s.input} className="premium-input" placeholder="Enter password" required disabled={isLoading} autoComplete="current-password" />
                        </div>
                        {error && <div style={{ fontSize: 12.5, color: 'var(--accent-danger)', background: 'rgba(235,87,87,0.10)', border: '1px solid rgba(235,87,87,0.25)', borderRadius: 8, padding: '8px 10px' }}>{error}</div>}
                        <button type="submit" style={s.submit} disabled={isLoading} className="signin-btn">
                            {isLoading ? <Loader2 size={17} className="animate-spin" /> : <>Sign in <ArrowRight size={16} /></>}
                        </button>
                    </form>
                    <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: 18 }}>
                        <div style={{ fontSize: 11.5, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--text-tertiary)', fontWeight: 600, marginBottom: 10 }}>Explore as a role</div>
                        <div style={s.chipRow}>
                            {ROLES.map((r) => (
                                <button key={r.username} type="button" onClick={() => pick(r)} style={s.chip(r.roleValue === roleValue)} className="role-chip">{r.name}</button>
                            ))}
                        </div>
                    </div>
                </div>
            </div>

            <style>{`
                @keyframes pulse { 0%,100% { opacity: 0.55; } 50% { opacity: 1; } }
                @keyframes spin { to { transform: rotate(360deg); } }
                .animate-spin { animation: spin 1s linear infinite; }
                .premium-input:focus { border-color: var(--accent-primary) !important; box-shadow: 0 0 0 3px rgba(94,106,210,0.22) !important; }
                .signin-btn:hover:not(:disabled) { background: var(--accent-bright); box-shadow: var(--glow-accent); }
                .role-chip:hover { border-color: var(--border-strong) !important; color: var(--text-primary) !important; }
                @media (max-width: 900px) {
                    .login-page { grid-template-columns: 1fr !important; }
                    .login-hero { display: none !important; }
                }
                @media (prefers-reduced-motion: reduce) { .animate-spin { animation: none; } }
            `}</style>
        </div>
    );
};

export default Login;
