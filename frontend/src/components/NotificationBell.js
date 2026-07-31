// NotificationBell - what the product uses to tell you something happened.
//
// Before this, every decision was recorded and announced to nobody: you asked
// for time off and had to keep re-opening the page to find out whether anyone
// had decided. Each entry is one sentence and a link to the screen where you
// can act on it.
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Bell, Check } from 'lucide-react';
import { getNotifications, markNotificationRead, markAllNotificationsRead } from '../config/api';

const POLL_MS = 30000;

// "2 minutes ago" reads better than a timestamp for something that just happened.
const timeAgo = (iso) => {
    if (!iso) return '';
    const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
    if (seconds < 60) return 'just now';
    const steps = [[60, 'minute'], [24, 'hour'], [7, 'day'], [4.35, 'week'], [12, 'month']];
    let value = seconds / 60;
    let unit = 'minute';
    for (const [size, next] of steps) {
        if (value < size) break;
        value /= size;
        unit = next;
    }
    const n = Math.floor(value);
    return `${n} ${unit}${n === 1 ? '' : 's'} ago`;
};

const NotificationBell = () => {
    const navigate = useNavigate();
    const [items, setItems] = useState([]);
    const [unread, setUnread] = useState(0);
    const [open, setOpen] = useState(false);
    const [failed, setFailed] = useState(false);
    const wrapRef = useRef(null);

    const load = useCallback(async () => {
        try {
            const res = await getNotifications(20);
            const data = res?.data ?? res;
            setItems(Array.isArray(data?.notifications) ? data.notifications : []);
            setUnread(Number(data?.unread) || 0);
            setFailed(false);
        } catch {
            // A bell that cannot reach the server should go quiet, not shout.
            setFailed(true);
        }
    }, []);

    useEffect(() => {
        load();
        const id = setInterval(load, POLL_MS);
        return () => clearInterval(id);
    }, [load]);

    // Click outside and Escape both close the panel, so it never traps focus.
    useEffect(() => {
        if (!open) return undefined;
        const onDown = (e) => {
            if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false);
        };
        const onKey = (e) => { if (e.key === 'Escape') setOpen(false); };
        document.addEventListener('mousedown', onDown);
        document.addEventListener('keydown', onKey);
        return () => {
            document.removeEventListener('mousedown', onDown);
            document.removeEventListener('keydown', onKey);
        };
    }, [open]);

    const openItem = useCallback(async (item) => {
        setOpen(false);
        if (!item.read) {
            setUnread((n) => Math.max(0, n - 1));
            setItems((list) => list.map((i) => (
                i.notification_id === item.notification_id ? { ...i, read: true } : i)));
            try { await markNotificationRead(item.notification_id); } catch { load(); }
        }
        if (item.link) navigate(item.link);
    }, [navigate, load]);

    const clearAll = useCallback(async () => {
        setUnread(0);
        setItems((list) => list.map((i) => ({ ...i, read: true })));
        try { await markAllNotificationsRead(); } catch { load(); }
    }, [load]);

    const label = useMemo(() => (
        unread ? `Notifications, ${unread} unread` : 'Notifications'
    ), [unread]);

    if (failed && items.length === 0) return null;

    return (
        <div ref={wrapRef} style={styles.wrap}>
            <button
                type="button"
                onClick={() => setOpen((v) => !v)}
                style={styles.bell}
                className="notif-bell"
                aria-label={label}
                aria-expanded={open}
                aria-haspopup="true"
            >
                <Bell size={16} />
                {unread > 0 && (
                    <span style={styles.badge} className="notif-badge">
                        {unread > 9 ? '9+' : unread}
                    </span>
                )}
            </button>

            {open && (
                <div style={styles.panel} role="dialog" aria-label="Notifications">
                    <div style={styles.head}>
                        <span style={styles.headTitle}>Notifications</span>
                        {unread > 0 && (
                            <button type="button" onClick={clearAll} style={styles.clear} className="notif-clear">
                                <Check size={12} /> Mark all read
                            </button>
                        )}
                    </div>

                    <div style={styles.list} className="notif-list">
                        {items.length === 0 && (
                            <p style={styles.empty}>
                                Nothing yet. When someone decides on a request of yours, or something
                                needs your decision, it appears here.
                            </p>
                        )}
                        {items.map((item) => (
                            <button
                                key={item.notification_id}
                                type="button"
                                onClick={() => openItem(item)}
                                style={styles.item(item.read)}
                                className="notif-item"
                            >
                                <span style={styles.dot(item.read)} aria-hidden="true" />
                                <span style={{ minWidth: 0 }}>
                                    <span style={styles.itemTitle(item.read)}>{item.title}</span>
                                    <span style={styles.itemBody}>{item.body}</span>
                                    <span style={styles.itemTime}>{timeAgo(item.created_at)}</span>
                                </span>
                            </button>
                        ))}
                    </div>
                </div>
            )}

            <style>{`
                .notif-bell:hover { border-color: var(--border-strong) !important; color: var(--text-primary) !important; }
                .notif-item:hover { background: var(--bg-elevated) !important; }
                .notif-clear:hover { color: var(--text-primary) !important; }
                .notif-list::-webkit-scrollbar { width: 6px; }
                .notif-list::-webkit-scrollbar-thumb { background: var(--border-strong); border-radius: 3px; }
                @media (prefers-reduced-motion: no-preference) {
                    .notif-badge { animation: notif-pop 220ms cubic-bezier(0.34, 1.56, 0.64, 1); }
                }
                @keyframes notif-pop { from { transform: scale(0.4); opacity: 0; } to { transform: scale(1); opacity: 1; } }
            `}</style>
        </div>
    );
};

const styles = {
    wrap: { position: 'relative', display: 'flex', alignItems: 'center' },
    bell: {
        position: 'relative', display: 'grid', placeItems: 'center', width: 32, height: 32,
        borderRadius: 8, border: '1px solid var(--border-subtle)', background: 'transparent',
        color: 'var(--text-secondary)', cursor: 'pointer', transition: 'all 140ms ease',
    },
    badge: {
        position: 'absolute', top: -5, right: -5, minWidth: 16, height: 16, padding: '0 4px',
        display: 'grid', placeItems: 'center', borderRadius: 999, boxSizing: 'border-box',
        background: 'var(--accent-danger)', color: '#fff', fontSize: 10, fontWeight: 700,
        lineHeight: 1, border: '2px solid var(--bg-main)',
    },
    panel: {
        position: 'absolute', top: 'calc(100% + 10px)', right: 0, width: 'min(360px, calc(100vw - 32px))',
        background: 'var(--bg-panel)', border: '1px solid var(--border-subtle)', borderRadius: 12,
        boxShadow: '0 16px 48px rgba(0,0,0,0.45)', zIndex: 300, overflow: 'hidden',
    },
    head: {
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '11px 14px', borderBottom: '1px solid var(--border-subtle)',
    },
    headTitle: { fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' },
    clear: {
        display: 'inline-flex', alignItems: 'center', gap: 5, border: 'none', background: 'transparent',
        color: 'var(--text-secondary)', fontSize: 11.5, cursor: 'pointer', padding: 0,
    },
    list: { maxHeight: 400, overflowY: 'auto' },
    empty: { margin: 0, padding: '22px 16px', fontSize: 12.5, lineHeight: 1.6, color: 'var(--text-secondary)', textAlign: 'center' },
    item: (read) => ({
        display: 'flex', gap: 10, width: '100%', textAlign: 'left', alignItems: 'flex-start',
        padding: '11px 14px', border: 'none', borderBottom: '1px solid var(--border-subtle)',
        background: read ? 'transparent' : 'color-mix(in srgb, var(--accent-primary) 7%, transparent)',
        cursor: 'pointer', transition: 'background 120ms ease', fontFamily: 'inherit',
    }),
    dot: (read) => ({
        flexShrink: 0, width: 6, height: 6, borderRadius: '50%', marginTop: 6,
        background: read ? 'transparent' : 'var(--accent-primary)',
    }),
    itemTitle: (read) => ({
        display: 'block', fontSize: 12.5, fontWeight: read ? 500 : 600,
        color: 'var(--text-primary)', marginBottom: 2,
    }),
    itemBody: { display: 'block', fontSize: 12, lineHeight: 1.5, color: 'var(--text-secondary)' },
    itemTime: { display: 'block', fontSize: 11, color: 'var(--text-tertiary, var(--text-secondary))', marginTop: 4 },
};

export default NotificationBell;
