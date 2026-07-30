// Shared team-roster access for the Manager portal modules.
// /mss/team/roster is paginated over a real org of thousands, so every consumer
// gets the same honest "showing N of TOTAL" behaviour instead of pretending the
// first page is the whole team.
import React, { useEffect, useMemo, useState } from 'react';
import { theme as tokens } from '../../theme';
import { useApi } from '../../hooks/useApi';
import { getTeamRoster, getEmployeeProfile } from '../../config/api';
import { ui } from '../employee/shared';
import { ChevronLeft, ChevronRight } from 'lucide-react';

export const ROSTER_PAGE = 25;

/** One page of the manager's direct reports, plus paging controls. */
export function useRoster(pageSize = ROSTER_PAGE) {
    const [offset, setOffset] = useState(0);
    const { data, isLoading, error, refetch } = useApi(getTeamRoster, [{ limit: pageSize, offset }], true);

    const people = useMemo(() => (
        (Array.isArray(data) ? data : (data?.roster || [])).map((p) => ({
            id: p.employee_uuid || p.id,
            name: p.full_name || p.employee_uuid || 'Unnamed record',
            email: p.email || '',
        }))
    ), [data]);

    const total = Number(data?.total) || people.length;
    const from = people.length === 0 ? 0 : offset + 1;
    const to = offset + people.length;

    return {
        people,
        total,
        offset,
        pageSize,
        isLoading,
        error,
        refetch,
        managerId: data?.manager_id || null,
        hasPrev: offset > 0,
        hasNext: offset + pageSize < total,
        prev: () => setOffset((o) => Math.max(0, o - pageSize)),
        next: () => setOffset((o) => (o + pageSize < total ? o + pageSize : o)),
        summary: total === 0
            ? 'No direct reports on record'
            : `Showing ${from} to ${to} of ${total.toLocaleString()} people`,
    };
}

const pagerBtn = (off) => ({
    display: 'inline-flex', alignItems: 'center', gap: 4,
    padding: '5px 9px', borderRadius: tokens.border?.radius?.button,
    border: `1px solid ${tokens.color?.['border-600']}`,
    background: 'transparent',
    color: off ? tokens.color?.['muted-600'] : tokens.color?.['text-100'],
    fontSize: '11.5px', fontWeight: 500,
    cursor: off ? 'not-allowed' : 'pointer',
    opacity: off ? 0.5 : 1,
});

/** "Showing 1 to 25 of 4,094 people" with previous / next controls. */
export const RosterPager = ({ roster }) => (
    <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        gap: tokens.spacing?.sm, marginTop: tokens.spacing?.xs, flexWrap: 'wrap',
    }}>
        <span style={{ fontSize: '11.5px', color: tokens.color?.['muted-600'] }}>{roster.summary}</span>
        <span style={{ display: 'flex', gap: 6 }}>
            <button type="button" onClick={roster.prev} disabled={!roster.hasPrev} style={pagerBtn(!roster.hasPrev)}>
                <ChevronLeft size={13} /> Previous
            </button>
            <button type="button" onClick={roster.next} disabled={!roster.hasNext} style={pagerBtn(!roster.hasNext)}>
                Next <ChevronRight size={13} />
            </button>
        </span>
    </div>
);

/** Compact team-member chooser backed by the paged roster. */
export const RosterSelect = ({ roster, value, onChange, label = 'Team member' }) => (
    <div style={{ minWidth: 0 }}>
        <label style={ui.label}>{label}</label>
        <select
            value={value || ''}
            onChange={(e) => onChange(e.target.value)}
            style={ui.input}
            disabled={roster.isLoading}
        >
            <option value="">
                {roster.isLoading ? 'Loading your team' : (roster.people.length ? 'Select a team member' : 'No one on your roster')}
            </option>
            {roster.people.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
            ))}
        </select>
        <RosterPager roster={roster} />
    </div>
);

/**
 * Resolves employee identifiers to real names so no screen ever shows a raw id.
 * Used for approval items, whose employee may sit outside the loaded roster page.
 */
export function useEmployeeNames(ids) {
    const key = useMemo(
        () => Array.from(new Set((ids || []).filter(Boolean))).sort().join(','),
        [ids],
    );
    const [names, setNames] = useState({});

    useEffect(() => {
        const list = key ? key.split(',') : [];
        if (!list.length) return undefined;
        let alive = true;
        Promise.all(list.slice(0, 40).map((id) => (
            getEmployeeProfile(id)
                .then((r) => [id, r.data?.full_name || null])
                .catch(() => [id, null])
        ))).then((pairs) => {
            if (!alive) return;
            setNames(Object.fromEntries(pairs.filter(([, n]) => n)));
        });
        return () => { alive = false; };
    }, [key]);

    return names;
}

/**
 * The recognition endpoint keys stars by login username, while the roster keys
 * people by employee id, so the username is looked up before a star is given.
 */
export const resolveUsername = (employeeId) =>
    getEmployeeProfile(employeeId).then((r) => r.data?.username || null);
