// Shared header + in-page module switcher for the HRIT, Orchestrator and Admin consoles.
// Every module keeps a persistent, clickable way back to its siblings so the user is
// never trapped inside a sub-view.
import React, { memo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { theme as tokens } from '../../theme';
import { Compass } from 'lucide-react';

export const PortalHeader = memo(({ icon: Icon, accent, title, subtitle, basePath, modules = [], active, actions }) => {
    const navigate = useNavigate();
    const color = accent || tokens.color?.['accent-primary'];

    const go = useCallback((key) => navigate(`${basePath}?module=${key}`), [navigate, basePath]);

    return (
        <div style={{ flexShrink: 0 }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: tokens.spacing?.md }}>
                <div style={{ display: 'flex', gap: 12, minWidth: 0 }}>
                    <span style={{
                        display: 'grid', placeItems: 'center', width: 38, height: 38, flexShrink: 0,
                        borderRadius: 10, background: `${color}18`, border: `1px solid ${color}33`,
                    }}>
                        <Icon size={19} color={color} />
                    </span>
                    <div style={{ minWidth: 0 }}>
                        <h1 style={{
                            margin: 0, fontSize: tokens.typography?.h1?.fontSize, fontWeight: 600,
                            letterSpacing: '-0.022em', color: tokens.color?.['text-100'],
                        }}>{title}</h1>
                        {subtitle && (
                            <p style={{
                                margin: '5px 0 0 0', fontSize: tokens.typography?.small?.fontSize,
                                color: tokens.color?.['muted-600'], lineHeight: 1.5, maxWidth: 720,
                            }}>{subtitle}</p>
                        )}
                    </div>
                </div>
                {actions && <div style={{ flexShrink: 0 }}>{actions}</div>}
            </div>

            <div style={{
                display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 16, paddingBottom: 10,
                borderBottom: `1px solid ${tokens.color?.['border-600']}`,
            }}>
                {modules.map(({ key, label, icon: TabIcon }) => {
                    const on = key === active;
                    return (
                        <button
                            key={key}
                            onClick={() => go(key)}
                            className="portal-tab"
                            aria-current={on ? 'page' : undefined}
                            style={{
                                display: 'inline-flex', alignItems: 'center', gap: 7,
                                padding: '7px 13px', borderRadius: tokens.border?.radius?.button,
                                border: `1px solid ${on ? `${color}44` : 'transparent'}`,
                                background: on ? `${color}18` : 'transparent',
                                color: on ? color : tokens.color?.['muted-500'],
                                fontSize: tokens.typography?.button?.fontSize,
                                fontWeight: on ? 600 : 500,
                                fontFamily: tokens.typography?.fontFamily,
                                cursor: 'pointer', whiteSpace: 'nowrap',
                                transition: 'color 0.16s ease, background 0.16s ease',
                            }}
                        >
                            {TabIcon && <TabIcon size={14} />}
                            {label}
                        </button>
                    );
                })}
            </div>
            <style>{`.portal-tab:hover { color: ${tokens.color?.['text-100']} !important; background: rgba(255,255,255,0.04) !important; }`}</style>
        </div>
    );
});
PortalHeader.displayName = 'PortalHeader';

// Shown when the URL asks for a module this console does not have. The header tabs
// above it stay visible, so this is a dead end the user can always walk out of.
export const UnknownModule = memo(({ name }) => (
    <div style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        gap: 10, padding: '48px 16px', textAlign: 'center', color: tokens.color?.['muted-600'],
    }}>
        <Compass size={24} strokeWidth={1.5} />
        <div style={{ color: tokens.color?.['text-100'], fontSize: tokens.typography?.h3?.fontSize, fontWeight: 600 }}>
            That section does not exist here
        </div>
        <div style={{ fontSize: tokens.typography?.small?.fontSize, maxWidth: 420, lineHeight: 1.55 }}>
            Nothing in this console is called "{name}". Pick one of the sections above to carry on.
        </div>
    </div>
));
UnknownModule.displayName = 'UnknownModule';

// Page frame: fixed header, single contained scroller. The page itself never
// scrolls. The horizontal gutter comes from the shared .portal-shell-page class
// in App.css (one definition for the whole app), so pair `page` with
// `className="portal-shell-page"` and never add outer padding here.
export const portalShell = {
    page: { height: '100%', display: 'flex', flexDirection: 'column', minHeight: 0, boxSizing: 'border-box' },
    body: {
        flex: 1, minHeight: 0, overflowY: 'auto', overflowX: 'hidden',
        paddingTop: tokens.spacing?.lg, paddingRight: 4,
        // The page cannot scroll, so the breathing room at the end of the
        // content belongs to this inner scroller.
        paddingBottom: tokens.spacing?.xl,
    },
};

export default PortalHeader;
