// Sidebar — Linear-style left navigation rail.
// Driven by config/portalAccess.SIDEBAR_NAV, which is the SAME source hasAccess()
// uses to authorize routes. Keeping one source of truth means a link can never
// appear that the route guard would reject, and sub-modules are reachable by
// clicking instead of only by hand-typing ?module=.
import React, { memo, useMemo } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { SIDEBAR_NAV, hasAccess } from '../config/portalAccess';
import { LayoutDashboard } from 'lucide-react';
import BrandLogo from './BrandLogo';

const Sidebar = memo(() => {
    const { userRole, user } = useAuth();
    const location = useLocation();
    const navigate = useNavigate();
    const search = location.search;

    const items = useMemo(
        () => SIDEBAR_NAV.filter((item) => hasAccess(userRole, item.path)),
        [userRole]
    );

    const roleLabel = (userRole || 'guest').replace(/_/g, ' ');
    const activeModule = new URLSearchParams(search).get('module');

    return (
        <aside style={s.rail}>
            <div style={s.brand}>
                <BrandLogo size={26} wordmark />
            </div>

            <nav style={s.nav}>
                {items.map((it) => {
                    const Icon = it.icon || LayoutDashboard;
                    const onPage = location.pathname === it.path;
                    const subs = it.subModules || [];
                    return (
                        <div key={it.path}>
                            <button
                                onClick={() => navigate(it.path)}
                                style={{ ...s.item, ...(onPage ? s.itemActive : null) }}
                                className="nav-item"
                                aria-current={onPage ? 'page' : undefined}
                            >
                                {onPage && <span style={s.activeBar} />}
                                <Icon size={17} strokeWidth={2} style={{ flexShrink: 0 }} />
                                <span>{it.label}</span>
                            </button>

                            {/* Sub-modules appear once you are on the parent page, so
                                every screen the portal can render is reachable. */}
                            {onPage && subs.length > 0 && (
                                <div style={s.subList}>
                                    {subs.map((sub) => {
                                        const subModule = new URLSearchParams(sub.path.split('?')[1] || '').get('module');
                                        const subActive = activeModule
                                            ? activeModule === subModule
                                            : sub === subs[0];
                                        return (
                                            <button
                                                key={sub.path}
                                                onClick={() => navigate(sub.path)}
                                                style={{ ...s.subItem, ...(subActive ? s.subItemActive : null) }}
                                                className="nav-subitem"
                                            >
                                                {sub.label}
                                            </button>
                                        );
                                    })}
                                </div>
                            )}
                        </div>
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
                .nav-subitem:hover { color: var(--text-primary); background: rgba(255,255,255,0.03); }
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
    nav: { display: 'flex', flexDirection: 'column', gap: 2, flexGrow: 1, overflowY: 'auto', minHeight: 0 },
    item: {
        position: 'relative', display: 'flex', alignItems: 'center', gap: 11,
        padding: '9px 12px', borderRadius: 8, border: 'none', background: 'transparent',
        color: 'var(--text-secondary)', fontSize: 13.5, fontWeight: 500, cursor: 'pointer',
        textAlign: 'left', width: '100%', transition: 'all 0.14s ease', fontFamily: 'inherit',
    },
    itemActive: { background: 'rgba(94,106,210,0.14)', color: 'var(--text-primary)' },
    activeBar: { position: 'absolute', left: -12, top: '50%', transform: 'translateY(-50%)', width: 3, height: 18, borderRadius: 999, background: 'var(--accent-bright)' },
    subList: { display: 'flex', flexDirection: 'column', gap: 1, margin: '2px 0 6px', paddingLeft: 28, borderLeft: '1px solid var(--border-subtle)', marginLeft: 20 },
    subItem: {
        border: 'none', background: 'transparent', color: 'var(--text-tertiary)',
        fontSize: 12.5, padding: '6px 10px', borderRadius: 6, cursor: 'pointer',
        textAlign: 'left', width: '100%', fontFamily: 'inherit', transition: 'all 0.14s ease',
    },
    subItemActive: { color: 'var(--accent-bright)', fontWeight: 550 },
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

Sidebar.displayName = 'Sidebar';
export default Sidebar;
