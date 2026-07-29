// /frontend/src/theme.js - APPLE/GOOGLE PREMIUM REWRITE
export const theme = {
    color: {
        'accent-primary': 'var(--accent-primary)',
        'success': 'var(--accent-success)',
        'warning': 'var(--accent-warning)',
        'danger': 'var(--accent-danger)',
        
        'bg-900': 'var(--bg-main)',
        'panel-900': 'var(--bg-surface-elevated)',
        'panel-800': 'var(--bg-surface)',
        'panel-700': 'var(--bg-surface)',
        'panel-600': 'var(--bg-surface-elevated)',
        
        'text-100': 'var(--text-primary)',
        'muted-500': 'var(--text-secondary)',
        
        'border-600': 'var(--border-subtle)',
        'border-700': 'var(--border-subtle)',
        'inner-divider': 'var(--border-subtle)',
    },
    typography: {
        fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
        fontMono: "'JetBrains Mono', monospace",
        h1: { fontSize: '2rem', lineHeight: '1.2', fontWeight: 600, letterSpacing: '-0.02em' },
        h2: { fontSize: '1.25rem', lineHeight: '1.4', fontWeight: 500, letterSpacing: '-0.01em' },
        base: { fontSize: '1rem', lineHeight: '1.5', fontWeight: 400 },
        small: { fontSize: '0.875rem', lineHeight: '1.4', fontWeight: 400 },
    },
    spacing: {
        xxs: '4px',
        xs: '8px',
        sm: '12px',
        md: '16px',
        lg: '24px',
        xl: '32px',
        chartPadding: '16px 20px 10px 10px',
        cardPadding: '24px',
        colGutter: '24px',
    },
    size: {
        sidebarWidthExpanded: '0px', // Replaced by Dock
        sidebarWidthCollapsed: '0px', 
    },
    border: {
        radius: {
            chip: '8px',
            button: '9999px',
            card: '16px',
            full: '9999px',
        }
    },
    shadow: {
        card: 'var(--shadow-sm)',
        hover: 'var(--shadow-md)',
        sidebar: 'var(--shadow-float)',
        activeInset: 'none', 
    },
    ui: {
        sidebarWidth: {
            expanded: '0px',
            collapsed: '0px',
        },
        transition: {
            micro: 'all 0.2s cubic-bezier(0.2, 0.8, 0.2, 1)',
        }
    },
    breakpoints: {
        mobile: '600px',
        tablet: '900px',
        desktop: '1400px',
    },
};