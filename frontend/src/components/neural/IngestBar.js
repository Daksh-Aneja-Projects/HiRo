// IngestBar - "dump into the brain": a note or a dropped document goes to the
// live ingestion pipeline (/api/ingestion/upload), the same store the
// document ingestion tab feeds. Notes are stored as small text documents.
import React, { memo, useRef, useState } from 'react';
import { uploadIngestionFile } from '../../config/api';
import './neural.css';

const IngestBar = memo(({ onIngested }) => {
    const [text, setText] = useState('');
    const [busy, setBusy] = useState(false);
    const [message, setMessage] = useState(null);
    const [dragOver, setDragOver] = useState(false);
    const fileRef = useRef(null);
    const hideTimer = useRef(null);

    const say = (msg) => {
        setMessage(msg);
        clearTimeout(hideTimer.current);
        hideTimer.current = setTimeout(() => setMessage(null), 6000);
    };

    const send = async (file) => {
        const note = text.trim();
        if (!file && !note) return;
        setBusy(true);
        try {
            const payload = file || new File([note], `note-${Date.now()}.txt`, { type: 'text/plain' });
            const res = await uploadIngestionFile(payload);
            setText('');
            // Surface what the pipeline actually did: stored, and (for text
            // files) how many searchable chunks landed in the corpus.
            const d = res?.data || {};
            const idx = d.indexing || {};
            const stored = d.message || `"${payload.name}" was stored.`;
            const indexedNote = idx.status === 'indexed'
                ? ` Indexed into ${idx.chunks} searchable chunk${idx.chunks === 1 ? '' : 's'} - the brain can answer about it now.`
                : (idx.reason ? ` ${idx.reason}` : '');
            say(`${stored}${indexedNote}`);
            if (onIngested) onIngested();
        } catch (e) {
            say('That could not be stored. The ingestion pipeline did not accept it.');
        } finally {
            setBusy(false);
        }
    };

    return (
        <div
            style={{ ...ui.bar, ...(dragOver ? ui.barDragOver : null) }}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
                e.preventDefault();
                setDragOver(false);
                const f = e.dataTransfer.files && e.dataTransfer.files[0];
                if (f) send(f);
            }}
        >
            <svg width="15" height="15" viewBox="0 0 16 16" aria-hidden="true" style={{ color: '#fb923c', flexShrink: 0 }}>
                <path d="M8 1l1.4 3.6L13 6l-3.6 1.4L8 11 6.6 7.4 3 6l3.6-1.4L8 1zM13 10l.7 1.8 1.8.7-1.8.7-.7 1.8-.7-1.8-1.8-.7 1.8-.7.7-1.8z" fill="currentColor" />
            </svg>
            <input
                value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') send(null); }}
                placeholder="Dump into the brain: a note, a policy, a decision. Or drop a document."
                style={ui.input}
                aria-label="Teach the knowledge core"
                disabled={busy}
            />
            <input
                ref={fileRef}
                type="file"
                style={{ display: 'none' }}
                onChange={(e) => { const f = e.target.files && e.target.files[0]; if (f) send(f); e.target.value = ''; }}
            />
            <button onClick={() => fileRef.current && fileRef.current.click()} style={ui.attach} aria-label="Attach a document" disabled={busy}>
                <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true">
                    <path d="M13.5 7.5l-5.2 5.2a3.2 3.2 0 01-4.5-4.5l5.6-5.6a2.1 2.1 0 013 3L7 11a1 1 0 01-1.4-1.4l4.8-4.8" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
                </svg>
            </button>
            <button onClick={() => send(null)} style={ui.learn} disabled={busy || !text.trim()}>
                {busy ? 'Learning…' : 'Learn it'}
            </button>
            {message && <div className="neural-rise" style={ui.toast}>{message}</div>}
        </div>
    );
});

const ui = {
    bar: {
        position: 'absolute', top: 14, right: 14, zIndex: 20,
        display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px',
        width: 'min(460px, calc(100% - 28px))',
        background: 'color-mix(in srgb, var(--bg-surface-elevated) 90%, transparent)',
        backdropFilter: 'var(--glass-blur)', WebkitBackdropFilter: 'var(--glass-blur)',
        border: '1px solid var(--border-subtle)', borderRadius: 12, boxShadow: 'var(--shadow-md)',
    },
    barDragOver: { border: '1px solid #fb923c', boxShadow: '0 0 0 1px rgba(251,146,60,0.5)' },
    input: {
        flexGrow: 1, minWidth: 0, border: 'none', outline: 'none', background: 'transparent',
        color: 'var(--text-primary)', fontSize: 12.5, fontFamily: 'inherit',
    },
    attach: {
        border: '1px solid var(--border-subtle)', background: 'transparent', color: 'var(--text-secondary)',
        width: 28, height: 28, borderRadius: 8, cursor: 'pointer', display: 'grid', placeItems: 'center', flexShrink: 0,
    },
    learn: {
        border: 'none', borderRadius: 8, padding: '7px 12px', fontSize: 12, fontWeight: 600,
        background: '#fb923c', color: '#1a0f05', cursor: 'pointer', flexShrink: 0, fontFamily: 'inherit',
    },
    toast: {
        position: 'absolute', top: 'calc(100% + 8px)', right: 0, padding: '9px 12px',
        borderRadius: 10, fontSize: 12, color: 'var(--text-primary)', maxWidth: 360,
        background: 'color-mix(in srgb, var(--bg-surface-elevated) 94%, transparent)',
        border: '1px solid var(--border-strong)', boxShadow: 'var(--shadow-md)',
    },
};

IngestBar.displayName = 'IngestBar';
export default IngestBar;
