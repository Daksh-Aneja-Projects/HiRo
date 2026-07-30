// BrandLogo — premium HiRo mark.
// The glyph reads as an "H" whose crossbar is broken by an orchestration core
// (the central node the two columns — Human + Resource — are routed through).
import React, { memo, useId } from 'react';

const BrandLogo = memo(({ size = 32, wordmark = false, tagline = false, style }) => {
    const gid = useId().replace(/:/g, '');
    const tile = (
        <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden="true"
             style={{ display: 'block', flexShrink: 0 }}>
            <defs>
                <linearGradient id={`g-${gid}`} x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
                    <stop stopColor="#7C82FF" />
                    <stop offset="0.55" stopColor="#5E6AD2" />
                    <stop offset="1" stopColor="#3FB9E5" />
                </linearGradient>
                <linearGradient id={`s-${gid}`} x1="16" y1="7" x2="16" y2="25" gradientUnits="userSpaceOnUse">
                    <stop stopColor="#FFFFFF" />
                    <stop offset="1" stopColor="#E7E9FF" />
                </linearGradient>
            </defs>
            {/* Tile */}
            <rect x="0.75" y="0.75" width="30.5" height="30.5" rx="8" fill={`url(#g-${gid})`} />
            {/* Top sheen */}
            <rect x="0.75" y="0.75" width="30.5" height="15" rx="8" fill="#FFFFFF" opacity="0.08" />
            {/* H columns */}
            <rect x="9" y="8.25" width="3.1" height="15.5" rx="1.55" fill={`url(#s-${gid})`} />
            <rect x="19.9" y="8.25" width="3.1" height="15.5" rx="1.55" fill={`url(#s-${gid})`} />
            {/* Crossbar routed into the core */}
            <rect x="11.6" y="14.55" width="3.4" height="2.9" rx="1.2" fill="#FFFFFF" opacity="0.92" />
            <rect x="17" y="14.55" width="3.4" height="2.9" rx="1.2" fill="#FFFFFF" opacity="0.92" />
            {/* Orchestration core */}
            <circle cx="16" cy="16" r="3" fill="#FFFFFF" />
            <circle cx="16" cy="16" r="1.35" fill="#5E6AD2" />
        </svg>
    );

    if (!wordmark) return tile;

    return (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, ...style }}>
            {tile}
            <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1 }}>
                <span style={{ fontWeight: 650, fontSize: size * 0.5, letterSpacing: '-0.02em', color: 'var(--text-primary)' }}>
                    HiRo
                </span>
                {tagline && (
                    <span style={{ marginTop: 3, fontSize: size * 0.235, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--text-tertiary)', fontWeight: 500 }}>
                        Orchestration
                    </span>
                )}
            </div>
        </div>
    );
});

BrandLogo.displayName = 'BrandLogo';
export default BrandLogo;
