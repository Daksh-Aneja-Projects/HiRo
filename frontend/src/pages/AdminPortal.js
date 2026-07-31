// /frontend/src/pages/AdminPortal.js - Admin Console for the HRIT_ADMIN persona.
// Modules: users | announcements | system | security. Every figure on this page is
// read from the live backend; nothing is seeded, mocked or defaulted to a fake value.
import React, { useMemo, memo, useState, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import { theme as tokens } from '../theme';

import {
    getAdminDashboardData, getAllUsers, createUserAccount, updateUserRole, deleteUser,
    getAnnouncements, createAnnouncement,
    runSystemIntegrityCheck, clearSystemCache, getMessageBusStatus,
    rotateAgentKeys, testPQCEncrypt, testPQCDecrypt,
} from '../config/api';
import { useApi } from '../hooks/useApi';
import { useToast } from '../hooks/use-toast';
import { settings } from '../config/settings';

import DataCard from '../components/DataCard';
import BarChartWidget from '../components/charts/BarChartWidget';
import AreaChartWidget from '../components/charts/AreaChartWidget';
import { CountUp, LiveMeter, useMetricSeries } from '../components/live/LivePrimitives';
import { countBy } from '../utils/chartData';
import { PortalHeader, UnknownModule, portalShell } from '../components/admin/PortalHeader';
// Shared surface primitives. Defined once for the whole app; re-used here rather
// than duplicated per portal.
import { ui, Btn, Loading, EmptyState, ErrorNote, EmployeeStyles, readableRole, fmtDate } from '../components/employee/shared';
import {
    Users, ShieldCheck, Megaphone, Server, Lock, UserPlus, Trash2, Key,
    RefreshCw, Database, Radio, Gauge, AlertTriangle, Inbox, Send, ShieldAlert,
} from 'lucide-react';

const MODULES = [
    { key: 'users', label: 'Users and roles', icon: Users },
    { key: 'announcements', label: 'Announcements', icon: Megaphone },
    { key: 'system', label: 'System', icon: Server },
    { key: 'security', label: 'Security', icon: Lock },
];

// The backend only accepts these four role values. GUEST is a client-side sentinel.
const ROLE_OPTIONS = [...new Set(Object.values(settings.ROLES).filter((r) => r !== settings.ROLES.GUEST))];

const errText = (e) => e?.response?.data?.detail || e?.message || 'The request failed.';

/* ------------------------------------------------------------------ */
/* Users and roles                                                     */
/* ------------------------------------------------------------------ */
const UsersModule = memo(() => {
    const { toast } = useToast();
    const { data, isLoading, error, refetch } = useApi(getAllUsers, [{ limit: 200 }], true);
    const users = useMemo(() => data?.users || [], [data]);

    const [form, setForm] = useState({ username: '', full_name: '', email: '', employee_uuid: '', role: ROLE_OPTIONS[0] });
    const [creating, setCreating] = useState(false);
    const [busyUser, setBusyUser] = useState(null);

    const roleMix = useMemo(() => countBy(users, (u) => readableRole(u.role)), [users]);
    const activeCount = users.filter((u) => u.is_active).length;
    const adminCount = users.filter((u) => u.role === settings.ROLES.HRIT_MANAGER).length;

    const setField = (k) => (e) => setForm((p) => ({ ...p, [k]: e.target.value }));

    const handleCreate = useCallback(async (e) => {
        e.preventDefault();
        // username and role are the only fields the backend requires.
        if (!form.username.trim() || !form.role) {
            toast({ title: 'Sign-in name and role are required', description: 'Give the account a sign-in name and pick the role it should have.', variant: 'destructive' });
            return;
        }
        setCreating(true);
        try {
            const payload = { username: form.username.trim(), role: form.role };
            if (form.email.trim()) payload.email = form.email.trim();
            if (form.full_name.trim()) payload.full_name = form.full_name.trim();
            if (form.employee_uuid.trim()) payload.employee_uuid = form.employee_uuid.trim();
            await createUserAccount(payload);
            toast({ title: 'Account created', description: `${payload.username} can now sign in as a ${readableRole(form.role).toLowerCase()}.`, variant: 'success' });
            setForm({ username: '', full_name: '', email: '', employee_uuid: '', role: ROLE_OPTIONS[0] });
            refetch();
        } catch (err) {
            toast({ title: 'Could not create the account', description: errText(err), variant: 'destructive' });
        } finally {
            setCreating(false);
        }
    }, [form, refetch, toast]);

    // The backend keys users by sign-in name, not by an internal id.
    const handleRoleChange = useCallback(async (user, role) => {
        if (role === user.role) return;
        setBusyUser(user.username);
        try {
            await updateUserRole(user.username, role);
            toast({ title: 'Role updated', description: `${user.full_name || user.username} is now a ${readableRole(role).toLowerCase()}.`, variant: 'success' });
            refetch();
        } catch (err) {
            toast({ title: 'Could not change the role', description: errText(err), variant: 'destructive' });
            refetch();
        } finally {
            setBusyUser(null);
        }
    }, [refetch, toast]);

    const handleDelete = useCallback(async (user) => {
        const who = user.full_name || user.username;
        if (!window.confirm(`Permanently remove the account for ${who} (sign-in name ${user.username})? This cannot be undone.`)) return;
        setBusyUser(user.username);
        try {
            await deleteUser(user.username);
            toast({ title: 'Account removed', description: `${who} can no longer sign in.`, variant: 'success' });
            refetch();
        } catch (err) {
            toast({ title: 'Could not remove the account', description: errText(err), variant: 'destructive' });
        } finally {
            setBusyUser(null);
        }
    }, [refetch, toast]);

    return (
        <div style={ui.grid} className="portal-grid">
            <div style={{ gridColumn: 'span 3' }}>
                <DataCard title="Accounts on the platform" value={<CountUp value={users.length} />} icon={<Users size={16} />} subtitle="Every person who can sign in" />
            </div>
            <div style={{ gridColumn: 'span 3' }}>
                <DataCard title="Able to sign in today" value={<CountUp value={activeCount} />} color={tokens.color?.success} icon={<ShieldCheck size={16} />} subtitle={`${users.length - activeCount} suspended`} />
            </div>
            <div style={{ gridColumn: 'span 6' }}>
                <DataCard title="Who holds which role" isChart minHeight="180px">
                    <BarChartWidget data={roleMix} minHeight="130px" color={tokens.color?.['accent-primary']} />
                </DataCard>
            </div>

            <div style={{ ...ui.panel, gridColumn: 'span 4' }}>
                <h3 style={ui.h3}>Create an account</h3>
                <p style={ui.hint}>The sign-in name and the role are required. Everything else can be filled in later from the person's profile.</p>
                <form onSubmit={handleCreate} style={{ marginTop: tokens.spacing?.md }}>
                    <div style={ui.field}>
                        <label style={ui.label} htmlFor="new-username">Sign-in name</label>
                        <input id="new-username" style={ui.input} value={form.username} onChange={setField('username')} placeholder="e.g. j.patel" required />
                    </div>
                    <div style={ui.field}>
                        <label style={ui.label} htmlFor="new-role">Role</label>
                        <select id="new-role" style={ui.input} value={form.role} onChange={setField('role')} required>
                            {ROLE_OPTIONS.map((r) => <option key={r} value={r}>{readableRole(r)}</option>)}
                        </select>
                    </div>
                    <div style={ui.field}>
                        <label style={ui.label} htmlFor="new-name">Full name</label>
                        <input id="new-name" style={ui.input} value={form.full_name} onChange={setField('full_name')} placeholder="Optional" />
                    </div>
                    <div style={ui.field}>
                        <label style={ui.label} htmlFor="new-email">Work email</label>
                        <input id="new-email" type="email" style={ui.input} value={form.email} onChange={setField('email')} placeholder="Optional" />
                    </div>
                    <div style={ui.field}>
                        <label style={ui.label} htmlFor="new-emp">Employee record to link</label>
                        <input id="new-emp" style={ui.input} value={form.employee_uuid} onChange={setField('employee_uuid')} placeholder="Optional, e.g. EMP-014" />
                    </div>
                    <Btn type="submit" icon={UserPlus} loading={creating}>{creating ? 'Creating the account' : 'Create account'}</Btn>
                </form>
            </div>

            <div style={{ ...ui.panel, gridColumn: 'span 8' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: tokens.spacing?.sm }}>
                    <div>
                        <h3 style={ui.h3}>Directory</h3>
                        <p style={ui.hint}>Change a role from the dropdown. {adminCount} account{adminCount === 1 ? '' : 's'} currently hold full administrator rights.</p>
                    </div>
                    <Btn tone="ghost" icon={RefreshCw} onClick={() => refetch()}>Refresh</Btn>
                </div>
                <div style={{ marginTop: tokens.spacing?.md }}>
                    {isLoading && <Loading label="Reading the account directory" />}
                    <ErrorNote error={error} context="the account directory" />
                    {!isLoading && !error && users.length === 0 && (
                        <EmptyState icon={Users} title="No accounts yet" action="Create the first account with the form on the left." />
                    )}
                    <div style={ui.scroller('420px')} className="emp-scroll">
                        {users.map((u) => (
                            <div key={u.username} style={ui.listRow}>
                                <div style={ui.rowMain}>
                                    <span style={ui.rowTitle}>{u.full_name || u.username}</span>
                                    <span style={ui.rowMeta}>
                                        Signs in as {u.username}
                                        {u.email ? ` · ${u.email}` : ''}
                                        {u.employee_uuid ? ` · linked to employee ${u.employee_uuid}` : ' · not linked to an employee record'}
                                        {u.is_active ? '' : ' · suspended'}
                                    </span>
                                </div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: tokens.spacing?.xs, flexShrink: 0 }}>
                                    <select
                                        aria-label={`Role for ${u.username}`}
                                        value={u.role}
                                        disabled={busyUser === u.username}
                                        onChange={(e) => handleRoleChange(u, e.target.value)}
                                        style={{ ...ui.input, width: 'auto', padding: '6px 9px', fontSize: tokens.typography?.small?.fontSize }}
                                    >
                                        {ROLE_OPTIONS.map((r) => <option key={r} value={r}>{readableRole(r)}</option>)}
                                    </select>
                                    <Btn tone="danger" icon={Trash2} loading={busyUser === u.username} onClick={() => handleDelete(u)} style={{ padding: '7px 10px' }} aria-label={`Remove ${u.username}`}>Remove</Btn>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
});
UsersModule.displayName = 'UsersModule';

/* ------------------------------------------------------------------ */
/* Announcements                                                       */
/* ------------------------------------------------------------------ */
const AnnouncementsModule = memo(() => {
    const { toast } = useToast();
    const { data, isLoading, error, refetch } = useApi(getAnnouncements, [{ limit: 50 }], true);
    const items = useMemo(() => data?.announcements || [], [data]);

    const [form, setForm] = useState({ title: '', content: '' });
    const [posting, setPosting] = useState(false);

    const handlePost = useCallback(async (e) => {
        e.preventDefault();
        if (!form.title.trim() || !form.content.trim()) {
            toast({ title: 'Headline and message are both needed', description: 'Write a short headline and the message body before publishing.', variant: 'destructive' });
            return;
        }
        setPosting(true);
        try {
            await createAnnouncement({ title: form.title.trim(), content: form.content.trim() });
            toast({ title: 'Announcement published', description: 'Everyone on the platform can see it now.', variant: 'success' });
            setForm({ title: '', content: '' });
            refetch();
        } catch (err) {
            toast({ title: 'Could not publish the announcement', description: errText(err), variant: 'destructive' });
        } finally {
            setPosting(false);
        }
    }, [form, refetch, toast]);

    return (
        <div style={ui.grid} className="portal-grid">
            <div style={{ ...ui.panel, gridColumn: 'span 5' }}>
                <h3 style={ui.h3}>Publish an announcement</h3>
                <p style={ui.hint}>Announcements are visible to every signed-in person straight away. There is no draft state, so publish only what is ready.</p>
                <form onSubmit={handlePost} style={{ marginTop: tokens.spacing?.md }}>
                    <div style={ui.field}>
                        <label style={ui.label} htmlFor="ann-title">Headline</label>
                        <input id="ann-title" style={ui.input} value={form.title} onChange={(e) => setForm((p) => ({ ...p, title: e.target.value }))} placeholder="e.g. Payroll cut-off moves to the 24th" required />
                    </div>
                    <div style={ui.field}>
                        <label style={ui.label} htmlFor="ann-body">Message</label>
                        <textarea
                            id="ann-body"
                            style={{ ...ui.input, minHeight: 150, resize: 'vertical', fontFamily: tokens.typography?.fontFamily }}
                            value={form.content}
                            onChange={(e) => setForm((p) => ({ ...p, content: e.target.value }))}
                            placeholder="Explain what is changing and what people need to do."
                            required
                        />
                    </div>
                    <Btn type="submit" icon={Send} loading={posting}>{posting ? 'Publishing' : 'Publish to everyone'}</Btn>
                </form>
            </div>

            <div style={{ ...ui.panel, gridColumn: 'span 7' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <div>
                        <h3 style={ui.h3}>Published so far</h3>
                        <p style={ui.hint}>{items.length} announcement{items.length === 1 ? '' : 's'} on record, newest first.</p>
                    </div>
                    <Btn tone="ghost" icon={RefreshCw} onClick={() => refetch()}>Refresh</Btn>
                </div>
                <div style={{ marginTop: tokens.spacing?.md }}>
                    {isLoading && <Loading label="Reading published announcements" />}
                    <ErrorNote error={error} context="published announcements" />
                    {!isLoading && !error && items.length === 0 && (
                        <EmptyState icon={Megaphone} title="Nothing has been announced yet" action="The first announcement you publish will appear here and on everyone's dashboard." />
                    )}
                    <div style={ui.scroller('480px')} className="emp-scroll">
                        {items.map((a) => (
                            <div key={a.id} style={{ ...ui.listRow, alignItems: 'flex-start', flexDirection: 'column', gap: 6 }}>
                                <span style={{ ...ui.rowTitle, whiteSpace: 'normal' }}>{a.title}</span>
                                <span style={{ ...ui.rowMeta, lineHeight: 1.55 }}>{a.content}</span>
                                <span style={ui.rowMeta}>Posted by {a.author || 'an administrator'} on {fmtDate(a.created_at)}</span>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
});
AnnouncementsModule.displayName = 'AnnouncementsModule';

/* ------------------------------------------------------------------ */
/* System                                                              */
/* ------------------------------------------------------------------ */
const INTEGRITY_TARGETS = [
    { value: 'postgres', label: 'Employee and payroll database' },
    { value: 'redis', label: 'Cache layer' },
    { value: 'mongo', label: 'Document and audit store' },
];

const SystemModule = memo(() => {
    const { toast } = useToast();
    const { data: dash, isLoading: dashLoading, error: dashError, refetch: refetchDash } = useApi(getAdminDashboardData, [], true, 30000);
    const { data: bus } = useApi(getMessageBusStatus, [], true, 30000);

    // No historical telemetry endpoint exists, so these are rolling windows built
    // from the real psutil-backed live metrics feed.
    const cpuSeries = useMetricSeries('cpu_load', { intervalMs: 3000 });
    const memSeries = useMetricSeries('memory_load', { intervalMs: 3000 });

    const [service, setService] = useState(INTEGRITY_TARGETS[0].value);
    const [checking, setChecking] = useState(false);
    const [checkResult, setCheckResult] = useState(null);
    const [clearing, setClearing] = useState(false);

    // The check needs a target service; sending an empty body is rejected.
    const handleIntegrityCheck = useCallback(async () => {
        setChecking(true);
        setCheckResult(null);
        try {
            const res = await runSystemIntegrityCheck(service);
            const body = res.data || {};
            const passed = String(body.status || '').toUpperCase().includes('VERIFIED');
            const label = INTEGRITY_TARGETS.find((t) => t.value === service)?.label || service;
            setCheckResult({ passed, label, detail: body.detail || 'No further detail was reported.' });
            toast({
                title: passed ? 'Integrity verified' : 'Integrity check raised a problem',
                description: `${label}: ${body.detail || 'No further detail was reported.'}`,
                variant: passed ? 'success' : 'destructive',
            });
            refetchDash();
        } catch (err) {
            toast({ title: 'The integrity check could not run', description: errText(err), variant: 'destructive' });
        } finally {
            setChecking(false);
        }
    }, [service, refetchDash, toast]);

    const handleClearCache = useCallback(async () => {
        if (!window.confirm('Clear the system cache? Requests will be slower for a few minutes while it refills.')) return;
        setClearing(true);
        try {
            await clearSystemCache();
            toast({ title: 'Cache cleared', description: 'The cache is empty and will refill as people use the platform.', variant: 'success' });
            refetchDash();
        } catch (err) {
            toast({ title: 'Could not clear the cache', description: errText(err), variant: 'destructive' });
        } finally {
            setClearing(false);
        }
    }, [refetchDash, toast]);

    const busConnected = String(bus?.status || '').toLowerCase() === 'connected';

    return (
        <div style={ui.grid} className="portal-grid">
            <div style={{ gridColumn: 'span 3' }}>
                <DataCard
                    title="Platform integrity"
                    value={<CountUp value={dash?.integrity_score ?? 0} decimals={1} />}
                    unit="out of 100"
                    color={tokens.color?.['accent-primary']}
                    icon={<Gauge size={16} />}
                    footer={<LiveMeter pct={Number(dash?.integrity_score) || 0} color={tokens.color?.['accent-primary']} />}
                />
            </div>
            <div style={{ gridColumn: 'span 3' }}>
                <DataCard
                    title="Cache in use"
                    value={<CountUp value={dash?.cache_util_pct ?? 0} decimals={1} />}
                    unit="%"
                    color={tokens.color?.success}
                    icon={<Database size={16} />}
                    footer={<LiveMeter pct={Number(dash?.cache_util_pct) || 0} color={tokens.color?.success} />}
                />
            </div>
            <div style={{ gridColumn: 'span 3' }}>
                <DataCard
                    title="Alerts needing attention"
                    value={<CountUp value={dash?.critical_alerts ?? 0} />}
                    color={Number(dash?.critical_alerts) > 0 ? tokens.color?.danger : tokens.color?.success}
                    icon={<AlertTriangle size={16} />}
                    subtitle={Number(dash?.critical_alerts) > 0 ? 'Someone needs to look at these' : 'Nothing outstanding'}
                />
            </div>
            <div style={{ gridColumn: 'span 3' }}>
                <DataCard
                    title="Agent message bus"
                    value={busConnected ? 'Connected' : 'Not connected'}
                    color={busConnected ? tokens.color?.success : tokens.color?.warning}
                    icon={<Radio size={16} />}
                    subtitle={busConnected
                        ? `${bus?.pending_messages ?? 0} message${bus?.pending_messages === 1 ? '' : 's'} waiting`
                        : 'Agents are running without the shared event bus'}
                />
            </div>

            {dashError && <div style={{ gridColumn: 'span 12' }}><ErrorNote error={dashError} context="the platform status figures" /></div>}
            {dashLoading && <div style={{ gridColumn: 'span 12' }}><Loading label="Reading platform status" /></div>}

            <div style={{ gridColumn: 'span 6' }}>
                <DataCard title="Processor load, live" isChart minHeight="250px">
                    <AreaChartWidget data={cpuSeries} minHeight="200px" color={tokens.color?.['accent-primary']} label="Sampled from the host every three seconds" />
                </DataCard>
            </div>
            <div style={{ gridColumn: 'span 6' }}>
                <DataCard title="Memory load, live" isChart minHeight="250px">
                    <AreaChartWidget data={memSeries} minHeight="200px" color={tokens.color?.['accent-secondary']} label="Sampled from the host every three seconds" />
                </DataCard>
            </div>

            <div style={{ ...ui.panel, gridColumn: 'span 6' }}>
                <h3 style={ui.h3}>Verify a data store</h3>
                <p style={ui.hint}>Runs a live connection and consistency probe against one store and reports back in plain English.</p>
                <div style={{ display: 'flex', gap: tokens.spacing?.sm, alignItems: 'flex-end', marginTop: tokens.spacing?.md, flexWrap: 'wrap' }}>
                    <div style={{ flex: 1, minWidth: 200 }}>
                        <label style={ui.label} htmlFor="integrity-target">Store to check</label>
                        <select id="integrity-target" style={ui.input} value={service} onChange={(e) => setService(e.target.value)}>
                            {INTEGRITY_TARGETS.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                        </select>
                    </div>
                    <Btn icon={ShieldCheck} loading={checking} onClick={handleIntegrityCheck}>{checking ? 'Checking' : 'Run the check'}</Btn>
                </div>
                {checkResult && (
                    <div style={{
                        marginTop: tokens.spacing?.md, padding: '10px 12px',
                        borderRadius: tokens.border?.radius?.input,
                        border: `1px solid ${(checkResult.passed ? tokens.color?.success : tokens.color?.danger)}33`,
                        background: `${checkResult.passed ? tokens.color?.success : tokens.color?.danger}0f`,
                        color: checkResult.passed ? tokens.color?.success : tokens.color?.danger,
                        fontSize: tokens.typography?.small?.fontSize, lineHeight: 1.55,
                    }}>
                        {checkResult.passed
                            ? `The ${checkResult.label.toLowerCase()} passed its integrity check. ${checkResult.detail}`
                            : `The ${checkResult.label.toLowerCase()} did not pass. ${checkResult.detail}`}
                    </div>
                )}
            </div>

            <div style={{ ...ui.panel, gridColumn: 'span 6' }}>
                <h3 style={ui.h3}>Cache maintenance</h3>
                <p style={ui.hint}>
                    Emptying the cache forces every lookup back to the source of truth. Use it when people report stale figures.
                    {dash?.cache_util_pct != null ? ` The cache is currently ${Number(dash.cache_util_pct).toFixed(1)} percent full.` : ''}
                </p>
                <div style={{ marginTop: tokens.spacing?.md }}>
                    <Btn tone="ghost" icon={Database} loading={clearing} onClick={handleClearCache}>{clearing ? 'Clearing the cache' : 'Empty the cache'}</Btn>
                </div>
            </div>
        </div>
    );
});
SystemModule.displayName = 'SystemModule';

/* ------------------------------------------------------------------ */
/* Security                                                            */
/* ------------------------------------------------------------------ */
const SecurityModule = memo(() => {
    const { toast } = useToast();
    const { data: dash, refetch: refetchDash } = useApi(getAdminDashboardData, [], true, 60000);

    const [rotating, setRotating] = useState(false);
    const [nextRotation, setNextRotation] = useState(null);

    const [plaintext, setPlaintext] = useState('');
    const [ciphertext, setCiphertext] = useState('');
    const [meta, setMeta] = useState(null);
    const [roundTrip, setRoundTrip] = useState(null);
    const [encrypting, setEncrypting] = useState(false);
    const [decrypting, setDecrypting] = useState(false);

    const handleRotate = useCallback(async () => {
        if (!window.confirm('Rotate the encryption keys now? Anything encrypted from this point forward uses the new key.')) return;
        setRotating(true);
        try {
            const res = await rotateAgentKeys();
            setNextRotation(res.data?.next_rotation || null);
            toast({ title: 'Keys rotated', description: `New keys are live${res.data?.next_rotation ? `, next rotation due in ${res.data.next_rotation}` : ''}.`, variant: 'success' });
            refetchDash();
        } catch (err) {
            toast({ title: 'Could not rotate the keys', description: errText(err), variant: 'destructive' });
        } finally {
            setRotating(false);
        }
    }, [refetchDash, toast]);

    const handleEncrypt = useCallback(async () => {
        if (!plaintext.trim()) {
            toast({ title: 'Nothing to encrypt', description: 'Type some sample text first.', variant: 'destructive' });
            return;
        }
        setEncrypting(true);
        setRoundTrip(null);
        try {
            const res = await testPQCEncrypt(plaintext);
            setCiphertext(res.data?.ciphertext || '');
            setMeta(res.data?.metadata || null);
            toast({ title: 'Text encrypted', description: 'The sealed value and the key details are shown below.', variant: 'success' });
        } catch (err) {
            toast({ title: 'Encryption failed', description: errText(err), variant: 'destructive' });
        } finally {
            setEncrypting(false);
        }
    }, [plaintext, toast]);

    const handleDecrypt = useCallback(async () => {
        if (!ciphertext) {
            toast({ title: 'Nothing to unseal', description: 'Encrypt something first, then unseal it to prove the round trip.', variant: 'destructive' });
            return;
        }
        setDecrypting(true);
        try {
            const res = await testPQCDecrypt(ciphertext);
            const recovered = res.data?.plaintext ?? '';
            setRoundTrip(recovered);
            toast({
                title: recovered === plaintext ? 'Round trip verified' : 'Unsealed, but the text differs',
                description: recovered === plaintext ? 'The unsealed text matches what you typed.' : 'The unsealed text does not match the original.',
                variant: recovered === plaintext ? 'success' : 'destructive',
            });
        } catch (err) {
            toast({ title: 'Could not unseal the text', description: errText(err), variant: 'destructive' });
        } finally {
            setDecrypting(false);
        }
    }, [ciphertext, plaintext, toast]);

    const mono = { fontFamily: tokens.typography?.fontMono, fontSize: '11.5px', color: tokens.color?.['muted-500'], wordBreak: 'break-all', lineHeight: 1.6 };

    return (
        <div style={ui.grid} className="portal-grid">
            <div style={{ gridColumn: 'span 4' }}>
                <DataCard
                    title="Encryption keys in service"
                    value={<CountUp value={dash?.active_pqc_keys ?? 0} />}
                    color={tokens.color?.warning}
                    icon={<Key size={16} />}
                    subtitle={nextRotation ? `Next rotation due in ${nextRotation}` : 'Keys protecting stored personal data'}
                />
            </div>
            <div style={{ gridColumn: 'span 4' }}>
                <DataCard
                    title="Open security alerts"
                    value={<CountUp value={dash?.critical_alerts ?? 0} />}
                    color={Number(dash?.critical_alerts) > 0 ? tokens.color?.danger : tokens.color?.success}
                    icon={<ShieldAlert size={16} />}
                    subtitle={Number(dash?.critical_alerts) > 0 ? 'Review these before rotating keys' : 'No alerts outstanding'}
                />
            </div>
            <div style={{ ...ui.panel, gridColumn: 'span 4' }}>
                <h3 style={ui.h3}>Rotate keys</h3>
                <p style={ui.hint}>Retires the current keys and issues fresh ones. Existing data stays readable.</p>
                <div style={{ marginTop: tokens.spacing?.md }}>
                    <Btn icon={RefreshCw} loading={rotating} onClick={handleRotate}>{rotating ? 'Rotating' : 'Rotate now'}</Btn>
                </div>
            </div>

            <div style={{ ...ui.panel, gridColumn: 'span 12' }}>
                <h3 style={ui.h3}>Prove the encryption works</h3>
                <p style={ui.hint}>Seal a sample string with the live key, then unseal it. If the text comes back unchanged, the encryption path is healthy end to end.</p>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(12, 1fr)', gap: tokens.spacing?.lg, marginTop: tokens.spacing?.md }}>
                    <div style={{ gridColumn: 'span 5' }}>
                        <label style={ui.label} htmlFor="pqc-plain">Sample text</label>
                        <textarea
                            id="pqc-plain"
                            style={{ ...ui.input, minHeight: 110, resize: 'vertical', fontFamily: tokens.typography?.fontFamily }}
                            value={plaintext}
                            onChange={(e) => setPlaintext(e.target.value)}
                            placeholder="Type anything, for example a fake national insurance number."
                        />
                        <div style={{ display: 'flex', gap: tokens.spacing?.xs, marginTop: tokens.spacing?.sm, flexWrap: 'wrap' }}>
                            <Btn icon={Lock} loading={encrypting} onClick={handleEncrypt}>{encrypting ? 'Sealing' : 'Seal it'}</Btn>
                            <Btn tone="ghost" icon={ShieldCheck} loading={decrypting} onClick={handleDecrypt} disabled={!ciphertext}>{decrypting ? 'Unsealing' : 'Unseal it'}</Btn>
                        </div>
                    </div>
                    <div style={{ gridColumn: 'span 7', minWidth: 0 }}>
                        {!ciphertext && <EmptyState icon={Inbox} title="Nothing sealed yet" action="Type some sample text and seal it to see the encrypted value and the key that protected it." />}
                        {ciphertext && (
                            <>
                                <div style={ui.label}>Sealed value</div>
                                <div style={{ ...mono, maxHeight: 90, overflowY: 'auto' }} className="emp-scroll">{ciphertext}</div>
                                {meta && (
                                    <p style={{ ...ui.hint, marginTop: 10 }}>
                                        Sealed with {meta.algorithm} using key {meta.key_hash}.
                                        {meta.quantum_risk_flag ? ' This algorithm is flagged as vulnerable to a future quantum attacker.' : ' No quantum vulnerability is flagged for this algorithm.'}
                                    </p>
                                )}
                                {roundTrip != null && (
                                    <p style={{ ...ui.hint, color: roundTrip === plaintext ? tokens.color?.success : tokens.color?.danger }}>
                                        {roundTrip === plaintext
                                            ? 'Unsealed successfully and the text matches the original exactly.'
                                            : `Unsealed, but the result reads "${roundTrip}" which is not what was sealed.`}
                                    </p>
                                )}
                            </>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
});
SecurityModule.displayName = 'SecurityModule';

/* ------------------------------------------------------------------ */
/* Shell                                                               */
/* ------------------------------------------------------------------ */
const SUBTITLES = {
    users: 'Create accounts, change what people are allowed to do, and remove access when someone leaves.',
    announcements: 'Publish a message that everyone signed in to the platform will see.',
    system: 'Live platform status, data store checks and cache maintenance.',
    security: 'Encryption keys and a live proof that the encryption path is working.',
};

export const AdminPortalComponent = memo(() => {
    const location = useLocation();
    const module = new URLSearchParams(location.search).get('module') || 'users';

    const body = {
        users: <UsersModule />,
        announcements: <AnnouncementsModule />,
        system: <SystemModule />,
        security: <SecurityModule />,
    }[module] || <UnknownModule name={module} />;

    return (
        <div style={portalShell.page}>
            <PortalHeader
                icon={ShieldCheck}
                accent={tokens.color?.danger}
                title="Admin console"
                subtitle={SUBTITLES[module] || 'Administration for the HiRo platform.'}
                basePath="/admin-portal"
                modules={MODULES}
                active={module}
            />
            <div style={portalShell.body} className="emp-scroll">{body}</div>
            <EmployeeStyles />
        </div>
    );
});

AdminPortalComponent.displayName = 'AdminPortalComponent';
export default AdminPortalComponent;
