// Sidebar — Linear-style left navigation rail. Role-aware, keyed on the real
// backend role strings (hrit_admin / hrbp / manager / employee).
import React, { memo, useMemo } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import {
    LayoutDashboard, User, Users, Briefcase, Settings,
    ShieldCheck, Activity, MessagesSquare, Cpu
} from 'lucide-react';
import BrandLogo from './BrandLogo';

const COMMON_TOP = [{ icon: LayoutDashboard, label: 'Dashboard', path: '/dashboard' }];
const COMMON_BOTTOM = [
    { icon: MessagesSquare, label: 'Collaboration', path: '/social-feed' },
    { icon: User, label: 'Profile', path: '/user-profile' },
];

const BY_ROLE = {
    employee: [{ icon: Users, label: 'My Portal', path: '/employee-portal' }],
    manager: [{ icon: Briefcase, label: 'My Team', path: '/manager-portal' }],
    hrbp: [
        { icon: Users, label: 'HR Operations', path: '/hr-portal' },
        { icon: Activity, label: 'Analytics', path: '/advanced-analytics' },
    ],
    hrit_admin: [
        { icon: Settings, label: 'HRIT Console', path: '/hrit-portal' },
        { icon: Activity, label: 'Analytics', path: '/advanced-analytics' },
        { icon: Cpu, label: 'Orchestrator', path: '/ultimate-orchestrator' },
        { icon: ShieldCheck, label: 'Admin', path: '/admin-portal' },
    ],
};

const Sidebar = memo(() => {
    const { userRole, user } = useAuth();
    const location = useLocation();
    const navigate = useNavigate();

    const items = useMemo(() => {
        const mid = BY_ROLE[userRole] || [];
        return [...COMMON_TOP, ...mid, ...COMMON_BOTTOM];
    }, [userRole]);

    const roleLabel = (userRole || 'guest').replace(/_/g, ' ');

    return (
        <aside style={s.rail}>
            <div style={s.brand}>
                <BrandLogo size={26} wordmark />
            </div>

            <nav style={s.nav}>
                {items.map((it) => {
                    const active = location.pathname === it.path || (it.path !== '/dashboard' && location.pathname.startsWith(it.path));
                    return (
                        <button key={it.path} onClick={() => navigate(it.path)}
                                style={{ ...s.item, ...(active ? s.itemActive : null) }}
                                className="nav-item" aria-current={active ? 'page' : undefined}>
                            {active && <span style={s.activeBar} />}
                            <it.icon size={17} strokeWidth={2} style={{ flexShrink: 0 }} />
                            <span>{it.label}</span>
                        </button>
                    );
                })}
            </nav>

            <div style={s.userCard}>
                <span style={s.avatar}>{(user?.full_name || user?.username || 'U').charAt(0).toUpperCase()}</span>
                <div style={{ minWidth: 0 }}>
                    <div style={s.userName}>{user?.full_name || user?.username || 'Guest'}</div>
                    <div style={s.userRole}>{roleLabel}</div>
                </div>
            </div>

            <style>{`
                .nav-item:hover { background: rgba(255,255,255,0.04); color: var(--text-primary); }
            `}</style>
        </aside>
    );
});

const s = {
    rail: {
        width: 248, flexShrink: 0, height: '100vh',
        background: 'var(--bg-surface)', borderRight: '1px solid var(--border-subtle)',
        display: 'flex', flexDirection: 'column', padding: '18px 12px', boxSizing: 'border-box',
    },
    brand: { padding: '6px 8px 20px' },
    nav: { display: 'flex', flexDirection: 'column', gap: 2, flexGrow: 1 },
    item: {
        position: 'relative', display: 'flex', alignItems: 'center', gap: 11,
        padding: '9px 12px', borderRadius: 8, border: 'none', background: 'transparent',
        color: 'var(--text-secondary)', fontSize: 13.5, fontWeight: 500, cursor: 'pointer',
        textAlign: 'left', width: '100%', transition: 'all 0.14s ease', fontFamily: 'inherit',
    },
    itemActive: { background: 'rgba(94,106,210,0.14)', color: 'var(--text-primary)' },
    activeBar: { position: 'absolute', left: -12, top: '50%', transform: 'translateY(-50%)', width: 3, height: 18, borderRadius: 999, background: 'var(--accent-bright)' },
    userCard: {
        display: 'flex', alignItems: 'center', gap: 10, padding: '10px 8px', marginTop: 8,
        borderTop: '1px solid var(--border-subtle)',
    },
    avatar: {
        width: 30, height: 30, borderRadius: 8, flexShrink: 0, display: 'grid', placeItems: 'center',
        background: 'linear-gradient(135deg, #5e6ad2, #3fb9e5)', color: '#fff', fontSize: 13, fontWeight: 600,
    },
    userName: { fontSize: 13, fontWeight: 550, color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' },
    userRole: { fontSize: 11.5, color: 'var(--text-tertiary)', textTransform: 'capitalize' },
};

export default Sidebar;
