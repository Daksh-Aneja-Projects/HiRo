// Shared inline-style atoms for the HRBP policy / governance surfaces.
// Plain style objects only, so every consumer keeps the Linear dark aesthetic
// without three copies of the same input + button declarations.
import { theme as tokens } from '../../theme';

export const s = {
    input: {
        padding: '9px 12px',
        background: 'var(--bg-input)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 8,
        color: 'var(--text-primary)',
        fontSize: 13.5,
        minWidth: 160,
        boxSizing: 'border-box',
    },
    textarea: {
        width: '100%',
        padding: '11px 13px',
        background: 'var(--bg-input)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 8,
        color: 'var(--text-primary)',
        fontFamily: tokens.typography?.fontMono,
        fontSize: 12.5,
        lineHeight: 1.55,
        resize: 'vertical',
        boxSizing: 'border-box',
    },
    btn: {
        padding: '9px 14px',
        background: 'var(--accent-primary)',
        border: '1px solid transparent',
        borderRadius: 8,
        color: '#fff',
        fontSize: 13,
        fontWeight: 550,
        cursor: 'pointer',
        display: 'inline-flex',
        alignItems: 'center',
        gap: 7,
        whiteSpace: 'nowrap',
    },
    btnGhost: {
        padding: '9px 14px',
        background: 'transparent',
        border: '1px solid var(--border-subtle)',
        borderRadius: 8,
        color: 'var(--text-primary)',
        fontSize: 13,
        fontWeight: 500,
        cursor: 'pointer',
        display: 'inline-flex',
        alignItems: 'center',
        gap: 7,
        whiteSpace: 'nowrap',
    },
    row: { display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' },
    panel: {
        background: tokens.color?.['panel-800'],
        border: '1px solid var(--border-subtle)',
        borderRadius: tokens.border?.radius?.card,
        padding: '16px 18px',
        boxSizing: 'border-box',
    },
    label: { fontSize: 12, fontWeight: 500, color: tokens.color?.['muted-500'], marginBottom: 6, display: 'block' },
    hint: { color: tokens.color?.['muted-600'], fontSize: 12.5, margin: '0 0 14px' },
    sectionTitle: { margin: 0, fontSize: 14.5, fontWeight: 600, color: tokens.color?.['text-100'], display: 'flex', alignItems: 'center', gap: 8 },
    mono: { fontFamily: tokens.typography?.fontMono, fontSize: 12, color: tokens.color?.['muted-500'], wordBreak: 'break-all' },
};

// Disabled buttons should read as disabled, not as a live control.
export const dim = (style, disabled) => (disabled ? { ...style, opacity: 0.5, cursor: 'not-allowed' } : style);

// Human-readable lifecycle wording. Raw enums never reach the reader.
export const POLICY_STATUS_TEXT = {
    draft: 'Draft, still editable',
    review: 'Waiting on approvers',
    approved: 'Approved, ready to activate',
    active: 'Live and enforced',
    deprecated: 'Superseded by a newer version',
    archived: 'Archived',
};

export const statusText = (status) =>
    POLICY_STATUS_TEXT[String(status || '').toLowerCase()] ||
    (status ? String(status).replace(/_/g, ' ').toLowerCase() : 'Unknown state');

export const statusColor = (status) => {
    switch (String(status || '').toLowerCase()) {
        case 'active': return tokens.color?.success;
        case 'approved': return tokens.color?.['accent-secondary'];
        case 'review': return tokens.color?.warning;
        case 'deprecated':
        case 'archived': return tokens.color?.['muted-600'];
        default: return tokens.color?.['accent-primary'];
    }
};

// Enforcement decisions in plain English.
export const decisionText = (decision) => {
    switch (String(decision || '').toUpperCase()) {
        case 'DENY':
        case 'BLOCK':
        case 'STOP': return 'Denied by policy';
        case 'APPROVE':
        case 'ALLOW':
        case 'PASS': return 'Approved by policy';
        case 'ESCALATE': return 'Escalated for human review';
        case 'WARN': return 'Allowed with a warning';
        default: return decision ? String(decision).replace(/_/g, ' ').toLowerCase() : 'No decision recorded';
    }
};

export const isDenial = (decision) => ['DENY', 'BLOCK', 'STOP'].includes(String(decision || '').toUpperCase());

// "policy_scan" -> "Policy scan"
export const humanise = (raw) => {
    if (!raw) return 'Unspecified';
    const words = String(raw).replace(/[_-]+/g, ' ').trim().toLowerCase();
    return words.charAt(0).toUpperCase() + words.slice(1);
};

export const apiError = (err) =>
    (typeof err?.response?.data?.detail === 'string' && err.response.data.detail) ||
    err?.message ||
    'The server did not explain the failure.';
