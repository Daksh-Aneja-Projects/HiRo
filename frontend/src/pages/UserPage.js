// /frontend/src/pages/UserPage.js
// The signed-in user's own profile. Loads the real record from
// GET /api/ess/profile/personal-info and files changes through
// POST /api/ess/profile/update-request, which queues them for HR review.
// Nothing on this page is fabricated: fields the backend does not hold are
// shown as not recorded rather than filled with a plausible looking value.
import React, { useState, useMemo, useEffect, useCallback, memo } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { theme as tokens } from '../theme';
import { useApi } from '../hooks/useApi';
import { useToast } from '../hooks/use-toast';
import { getPersonalInfo, submitPersonalInfoUpdate } from '../config/api';
import DataCard from '../components/DataCard';
import { ui, Btn, Loading, ErrorNote, StatusPill, readableRole, EmployeeStyles } from '../components/employee/shared';
import { User, Mail, Lock, Save, Contact, ShieldCheck, History, Info } from 'lucide-react';

const UserPage = memo(() => {
    const { user, userRole, isLoading: isAuthLoading } = useAuth();
    const { toast } = useToast();

    const { data: profile, isLoading, error, refetch } = useApi(getPersonalInfo, [], true);

    const [form, setForm] = useState({ full_name: '', email: '' });
    const [isSaving, setIsSaving] = useState(false);
    const [requests, setRequests] = useState([]); // change requests filed in this session

    // Seed the form from the real record once it arrives.
    useEffect(() => {
        if (profile) setForm({ full_name: profile.full_name || '', email: profile.email || '' });
    }, [profile]);

    const isDirty = !!profile && (form.full_name !== (profile.full_name || '') || form.email !== (profile.email || ''));
    const emailValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim());
    const nameValid = form.full_name.trim().length >= 2;

    const handleSubmit = useCallback(async (e) => {
        e.preventDefault();
        if (!nameValid) {
            toast({ title: 'Check your name', description: 'Enter your full name, at least two characters.', variant: 'destructive' });
            return;
        }
        if (!emailValid) {
            toast({ title: 'Check your email', description: 'Enter a valid email address.', variant: 'destructive' });
            return;
        }
        setIsSaving(true);
        try {
            const res = await submitPersonalInfoUpdate({
                full_name: form.full_name.trim(),
                email: form.email.trim(),
            });
            const requestId = res.data?.request_id;
            setRequests((prev) => [{
                request_id: requestId,
                status: res.data?.status || 'REQUESTED',
                submitted_at: new Date().toISOString(),
                summary: `Name to "${form.full_name.trim()}", email to "${form.email.trim()}"`,
            }, ...prev]);
            toast({
                title: 'Change request filed',
                description: `HR will review it. Your reference is ${requestId || 'pending'}. Your record stays as it is until they approve.`,
                variant: 'success',
            });
            refetch();
        } catch (err) {
            toast({ title: 'Could not file your change request', description: err.response?.data?.detail || err.message, variant: 'destructive' });
        } finally {
            setIsSaving(false);
        }
    }, [nameValid, emailValid, form, toast, refetch]);

    const styles = useMemo(() => ({
        page: { display: 'flex', flexDirection: 'column', gap: tokens.spacing?.lg, maxWidth: 980, minWidth: 0 },
        header: { borderBottom: `1px solid ${tokens.color?.['border-600']}`, paddingBottom: tokens.spacing?.md },
        title: {
            margin: 0, display: 'flex', alignItems: 'center', gap: tokens.spacing?.sm,
            fontSize: tokens.typography?.h1?.fontSize, fontWeight: tokens.typography?.h1?.fontWeight,
            letterSpacing: '-0.022em', color: tokens.color?.['text-100'],
        },
        subtitle: { margin: '6px 0 0 0', fontSize: tokens.typography?.small?.fontSize, color: tokens.color?.['muted-600'] },
    }), []);

    if (isAuthLoading || !user) {
        return <Loading label="Loading your profile" />;
    }

    return (
        <div style={styles.page} className="user-profile-page">
            <EmployeeStyles />

            <div style={styles.header}>
                <h1 style={styles.title}>
                    <User size={26} color={tokens.color?.['accent-primary']} /> My profile
                </h1>
                <p style={styles.subtitle}>Your record as HiRo holds it. Changes are reviewed by HR before they take effect.</p>
            </div>

            <div style={ui.grid} className="portal-grid">
                <div style={{ gridColumn: 'span 4' }}>
                    <DataCard title="Role on record" value={readableRole(profile?.role || userRole)} unit=""
                        icon={<ShieldCheck size={15} />} color={tokens.color?.warning} />
                </div>
                <div style={{ gridColumn: 'span 4' }}>
                    <DataCard title="Employee record id" value={profile?.employee_uuid || 'Not linked'} unit=""
                        icon={<Contact size={15} />} color={tokens.color?.['accent-secondary']}
                        subtitle={profile?.employee_uuid ? 'Links your login to your HR record' : 'No HR record is linked to this login'} />
                </div>
                <div style={{ gridColumn: 'span 4' }}>
                    <DataCard title="Sign in name" value={profile?.username || user?.username || 'Not recorded'} unit=""
                        icon={<Lock size={15} />} color={tokens.color?.['accent-primary']} />
                </div>

                <div style={{ ...ui.panel, gridColumn: 'span 7' }}>
                    <h3 style={ui.h3}>Personal details</h3>
                    <p style={ui.hint}>
                        <Info size={12} style={{ verticalAlign: '-2px', marginRight: 4 }} />
                        Editing these fields files a change request. It does not overwrite your record directly.
                    </p>

                    {isLoading && <Loading label="Loading your record" />}
                    <ErrorNote error={error} context="your profile" />

                    <form onSubmit={handleSubmit} style={{ marginTop: tokens.spacing?.md }}>
                        <div style={ui.field}>
                            <label style={ui.label} htmlFor="profile-name"><User size={12} style={{ verticalAlign: '-2px', marginRight: 5 }} />Full name</label>
                            <input id="profile-name" style={ui.input} value={form.full_name} disabled={isLoading || !!error}
                                onChange={(e) => setForm((p) => ({ ...p, full_name: e.target.value }))} />
                        </div>
                        <div style={ui.field}>
                            <label style={ui.label} htmlFor="profile-email"><Mail size={12} style={{ verticalAlign: '-2px', marginRight: 5 }} />Email</label>
                            <input id="profile-email" type="email" style={ui.input} value={form.email} disabled={isLoading || !!error}
                                onChange={(e) => setForm((p) => ({ ...p, email: e.target.value }))} />
                        </div>

                        {!nameValid && form.full_name !== '' && (
                            <p style={{ ...ui.hint, color: tokens.color?.danger }}>Your full name needs at least two characters.</p>
                        )}
                        {!emailValid && form.email !== '' && (
                            <p style={{ ...ui.hint, color: tokens.color?.danger }}>That does not look like a valid email address.</p>
                        )}

                        <Btn type="submit" icon={Save} loading={isSaving} disabled={!isDirty || !nameValid || !emailValid}>
                            {isDirty ? 'File change request' : 'No changes to file'}
                        </Btn>
                    </form>
                </div>

                <div style={{ ...ui.panel, gridColumn: 'span 5' }}>
                    <h3 style={ui.h3}>Change requests you filed</h3>
                    <p style={ui.hint}>
                        There is no endpoint yet that lists past change requests, so this shows the ones you filed since opening this page,
                        with the reference the server returned.
                    </p>
                    {requests.length === 0 ? (
                        <div style={{ ...ui.hint, display: 'flex', alignItems: 'center', gap: 7, marginTop: tokens.spacing?.md }}>
                            <History size={14} /> Nothing filed in this session.
                        </div>
                    ) : (
                        <div className="emp-scroll" style={{ ...ui.scroller('260px'), marginTop: tokens.spacing?.sm }}>
                            {requests.map((r) => (
                                <div key={r.request_id} style={ui.listRow}>
                                    <div style={ui.rowMain}>
                                        <span style={{ ...ui.rowTitle, whiteSpace: 'normal' }}>{r.summary}</span>
                                        <span style={ui.rowMeta}>Reference {r.request_id}</span>
                                    </div>
                                    <StatusPill status={r.status} />
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
});

UserPage.displayName = 'UserPage';
export default UserPage;
