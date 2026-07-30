// Shared surface primitives for the Employee portal sub-modules.
// Inline-style only, Linear dark aesthetic, lucide icons. No emoji, no em-dashes.
import React from 'react';
import { theme as tokens } from '../../theme';
import { Inbox, Loader2 } from 'lucide-react';

export const ui = {
    // 12-column module grid. Children set their own gridColumn span.
    grid: {
        display: 'grid',
        gridTemplateColumns: 'repeat(12, 1fr)',
        gap: tokens.spacing?.lg,
        alignItems: 'start',
        width: '100%',
        maxWidth: '100%',
        boxSizing: 'border-box',
    },
    panel: {
        background: tokens.color?.['panel-800'],
        border: '1px solid var(--border-subtle)',
        borderRadius: tokens.border?.radius?.card,
        padding: '16px 18px',
        boxSizing: 'border-box',
        minWidth: 0,
    },
    h3: {
        margin: 0,
        fontSize: tokens.typography?.h3?.fontSize,
        fontWeight: 600,
        letterSpacing: '-0.01em',
        color: tokens.color?.['text-100'],
    },
    hint: {
        margin: '6px 0 0 0',
        fontSize: tokens.typography?.small?.fontSize,
        color: tokens.color?.['muted-600'],
        lineHeight: 1.5,
    },
    label: {
        display: 'block',
        marginBottom: 6,
        fontSize: tokens.typography?.small?.fontSize,
        color: tokens.color?.['muted-500'],
        fontWeight: 500,
    },
    input: {
        width: '100%',
        maxWidth: '100%',
        boxSizing: 'border-box',
        padding: '9px 11px',
        background: tokens.color?.['bg-input'],
        border: `1px solid ${tokens.color?.['border-600']}`,
        borderRadius: tokens.border?.radius?.input,
        color: tokens.color?.['text-100'],
        fontSize: tokens.typography?.base?.fontSize,
        fontFamily: tokens.typography?.fontFamily,
        outline: 'none',
    },
    field: { marginBottom: tokens.spacing?.md, minWidth: 0 },
    // Contained scroller so long lists never grow the page.
    scroller: (maxHeight = '320px') => ({ maxHeight, overflowY: 'auto', overflowX: 'hidden', paddingRight: 4 }),
    listRow: {
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: tokens.spacing?.sm,
        padding: '10px 0',
        borderBottom: `1px solid ${tokens.color?.['border-600']}`,
        minWidth: 0,
    },
    rowMain: { minWidth: 0, display: 'flex', flexDirection: 'column', gap: 3 },
    rowTitle: { color: tokens.color?.['text-100'], fontSize: tokens.typography?.base?.fontSize, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' },
    rowMeta: { color: tokens.color?.['muted-600'], fontSize: tokens.typography?.small?.fontSize },
};

const TONE = {
    APPROVED: 'success', SUBMITTED: 'success', PASS: 'success', SAVED: 'success', UPLOADED: 'success', COMPLETED: 'success',
    PENDING: 'warning', PENDING_AGENT_REVIEW: 'warning', IN_REVIEW: 'warning', DRAFT: 'warning', REQUESTED: 'warning',
    REJECTED: 'danger', FAIL: 'danger', BLOCKED: 'danger', DENIED: 'danger',
};

// Turns a backend enum into plain English plus a colour tone.
export const readableStatus = (raw) => {
    const key = String(raw || '').toUpperCase();
    const words = key.replace(/_/g, ' ').toLowerCase();
    const label = words ? words.charAt(0).toUpperCase() + words.slice(1) : 'Unknown';
    return { label: key === 'PENDING_AGENT_REVIEW' ? 'Awaiting review' : label, tone: TONE[key] || 'muted' };
};

export const StatusPill = ({ status }) => {
    const { label, tone } = readableStatus(status);
    const color = tone === 'muted' ? tokens.color?.['muted-500'] : tokens.color?.[tone];
    return (
        <span style={{
            flexShrink: 0, padding: '3px 9px', borderRadius: tokens.border?.radius?.full,
            fontSize: '11.5px', fontWeight: 500, letterSpacing: '-0.005em',
            color, border: `1px solid ${color}44`, background: `${color}14`, whiteSpace: 'nowrap',
        }}>{label}</span>
    );
};

export const Btn = ({ children, icon: Icon, tone = 'primary', loading, disabled, style, ...rest }) => {
    const bg = {
        primary: tokens.color?.['accent-primary'],
        success: tokens.color?.success,
        danger: tokens.color?.danger,
        ghost: 'transparent',
    }[tone];
    const isGhost = tone === 'ghost';
    const off = disabled || loading;
    return (
        <button
            {...rest}
            disabled={off}
            className="emp-btn"
            style={{
                display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 7,
                padding: '9px 15px', borderRadius: tokens.border?.radius?.button,
                border: isGhost ? `1px solid ${tokens.color?.['border-600']}` : 'none',
                background: isGhost ? 'transparent' : bg,
                color: isGhost ? tokens.color?.['text-100'] : tokens.color?.['bg-deep'],
                fontSize: tokens.typography?.button?.fontSize,
                fontWeight: 550, fontFamily: tokens.typography?.fontFamily,
                cursor: off ? 'not-allowed' : 'pointer',
                opacity: off ? 0.55 : 1,
                transition: 'transform 0.16s ease, box-shadow 0.16s ease, opacity 0.16s ease',
                ...style,
            }}
        >
            {loading ? <Loader2 size={15} className="animate-spin" /> : (Icon ? <Icon size={15} /> : null)}
            {children}
        </button>
    );
};

export const Loading = ({ label = 'Loading' }) => (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: tokens.color?.['muted-500'], fontSize: tokens.typography?.small?.fontSize, padding: '14px 0' }}>
        <Loader2 size={15} className="animate-spin" /> {label}
    </div>
);

// Honest empty state: says what is missing and what the user should do next.
export const EmptyState = ({ icon: Icon = Inbox, title, action }) => (
    <div style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        gap: 8, padding: '26px 14px', textAlign: 'center', color: tokens.color?.['muted-600'],
    }}>
        <Icon size={22} strokeWidth={1.5} />
        <div style={{ color: tokens.color?.['muted-500'], fontSize: tokens.typography?.base?.fontSize, fontWeight: 500 }}>{title}</div>
        {action && <div style={{ fontSize: tokens.typography?.small?.fontSize, maxWidth: 380, lineHeight: 1.5 }}>{action}</div>}
    </div>
);

// Surfaces a real backend failure in plain English rather than a raw code.
export const ErrorNote = ({ error, context }) => {
    if (!error) return null;
    const text = typeof error === 'string' ? error : (error.message || 'Request failed');
    const forbidden = /403|Access denied|Required roles/i.test(text);
    return (
        <div style={{
            padding: '10px 12px', borderRadius: tokens.border?.radius?.input,
            border: `1px solid ${tokens.color?.danger}33`, background: `${tokens.color?.danger}0f`,
            color: tokens.color?.danger, fontSize: tokens.typography?.small?.fontSize, lineHeight: 1.5,
        }}>
            {forbidden
                ? `Your account does not have permission to view ${context || 'this data'}. Ask your HR administrator for access.`
                : `${context ? `Could not load ${context}. ` : ''}${text}`}
        </div>
    );
};

// Backend identifiers are never shown raw. These turn them into plain English.
export const humanText = (s) => String(s || '').replace(/_/g, ' ').trim();

const ROLE_LABELS = {
    employee: 'Employee',
    manager: 'Manager',
    hrbp: 'HR business partner',
    hrit_admin: 'HR IT administrator',
};
export const readableRole = (r) => ROLE_LABELS[String(r || '').toLowerCase()] || humanText(r) || 'Not recorded';

// "LEAVE_POLICY_US-TX" reads as "US-TX", so copy can say "the US-TX leave policy".
export const readablePolicy = (p) => humanText(String(p || '').replace(/^LEAVE[_ ]POLICY[_ ]?/i, '')) || 'your local policy';

// Roles the backend allows to read and write the shared document library.
export const DOC_LIBRARY_ROLES = ['manager', 'hrbp', 'hrit_admin'];

export const fmtDate = (v) => {
    if (!v) return 'Not recorded';
    const d = new Date(v);
    return Number.isNaN(d.getTime()) ? String(v) : d.toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' });
};

export const money = (n, currency = 'USD') => {
    const num = Number(n) || 0;
    try { return num.toLocaleString(undefined, { style: 'currency', currency, maximumFractionDigits: 0 }); }
    catch { return `${currency} ${num.toFixed(0)}`; }
};

// Injected once per module tree so buttons get a consistent hover.
export const EmployeeStyles = () => (
    <style>{`
        .emp-btn:not(:disabled):hover { transform: translateY(-1px); box-shadow: var(--shadow-md); }
        .emp-scroll::-webkit-scrollbar { width: 8px; }
        .emp-scroll::-webkit-scrollbar-thumb { background: var(--border-strong); border-radius: 8px; }
    `}</style>
);
