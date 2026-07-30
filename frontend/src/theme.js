// /frontend/src/theme.js — Linear-inspired design tokens.
// Colors resolve to the CSS variables defined in index.css so a single palette
// drives the whole app. Every key referenced across the codebase is provided.
export const theme = {
    color: {
        // Accents
        'accent-primary': 'var(--accent-primary)',
        'accent-secondary': 'var(--accent-secondary)',
        'accent-bright': 'var(--accent-bright)',
        'accent-2': 'var(--accent-2)',
        'accent-1-rgb': 'var(--accent-primary-rgb)',
        'accent-2-rgb': 'var(--accent-2-rgb)',
        'success': 'var(--accent-success)',
        'warning': 'var(--accent-warning)',
        'warning-700': 'var(--accent-warning-strong)',
        'danger': 'var(--accent-danger)',
        'danger-700': '#c0392b',
        'danger-rgb': 'var(--accent-danger-rgb)',
        'accent': 'var(--accent-primary)',

        // Surfaces
        'bg-900': 'var(--bg-main)',
        'bg-deep': 'var(--bg-deep)',
        'bg-input': 'var(--bg-input)',
        'panel-900': 'var(--bg-surface-elevated)',
        'panel-800': 'var(--bg-surface)',
        'panel-700': 'var(--bg-surface-elevated)',
        'panel-600': 'var(--bg-elevated-2)',

        // Text
        'text-100': 'var(--text-primary)',
        'text-dark': '#0b0c0e',
        'muted-500': 'var(--text-secondary)',
        'muted-600': 'var(--text-tertiary)',

        // Structure
        'border-600': 'var(--border-subtle)',
        'border-700': 'var(--border-strong)',
        'inner-divider': 'var(--border-subtle)',
    },
    typography: {
        fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
        fontMono: "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace",
        h1: { fontSize: '1.75rem', lineHeight: '1.15', fontWeight: 600, letterSpacing: '-0.022em' },
        h2: { fontSize: '1.125rem', lineHeight: '1.3', fontWeight: 600, letterSpacing: '-0.014em' },
        h3: { fontSize: '0.9375rem', lineHeight: '1.35', fontWeight: 600, letterSpacing: '-0.01em' },
        base: { fontSize: '0.875rem', lineHeight: '1.5', fontWeight: 400 },
        body: { fontSize: '0.875rem', lineHeight: '1.55', fontWeight: 400 },
        button: { fontSize: '0.8125rem', lineHeight: '1', fontWeight: 500, letterSpacing: '-0.005em' },
        small: { fontSize: '0.78125rem', lineHeight: '1.45', fontWeight: 400 },
    },
    spacing: {
        xxs: '4px', xs: '8px', sm: '12px', md: '16px', lg: '24px', xl: '32px',
        chartPadding: '16px 20px 10px 10px',
        cardPadding: '20px',
        colGutter: '20px',
    },
    size: { sidebarWidthExpanded: '248px', sidebarWidthCollapsed: '68px' },
    border: {
        radius: { chip: '8px', input: '8px', button: '8px', card: '12px', full: '9999px' },
    },
    shadow: {
        sm: 'var(--shadow-sm)',
        default: 'var(--shadow-md)',
        card: 'var(--shadow-sm)',
        hover: 'var(--shadow-md)',
        xl: 'var(--shadow-lg)',
        sidebar: 'var(--shadow-float)',
        glow: 'var(--glow-accent)',
        activeInset: 'none',
    },
    ui: {
        sidebarWidth: { expanded: '248px', collapsed: '68px' },
        border: { inner: '1px solid var(--border-subtle)' },
        transition: { micro: 'all 0.16s cubic-bezier(0.2, 0.8, 0.2, 1)' },
    },
    breakpoints: { mobile: '600px', tablet: '900px', desktop: '1400px' },
};
