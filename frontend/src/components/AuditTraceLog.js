// Audit trail - every enforcement decision the policy engine has written to
// policy_audit_log, in plain English. Rows are real; nothing is synthesised.
import React, { useMemo, memo, useState, useCallback } from 'react';
import { theme as tokens } from '../theme';
import { useApi } from '../hooks/useApi';
import { getAuditTrace } from '../config/api';
import { countBy } from '../utils/chartData';
import DataCard from './DataCard';
import BarChartWidget from './charts/BarChartWidget';
import { Search, Loader2, AlertTriangle, ScrollText, RefreshCw } from 'lucide-react';
import { s, dim, decisionText, isDenial, humanise } from './policy/ui';

const AuditTraceLog = memo(({ initialAction = '', limit = 50 }) => {
    const [actionInput, setActionInput] = useState(initialAction);
    const [query, setQuery] = useState(() => (initialAction ? { action: initialAction, limit } : { limit }));

    const { data, isLoading, error, refetch } = useApi(getAuditTrace, [query], true);
    const rows = useMemo(() => (Array.isArray(data) ? data : []), [data]);

    const applyFilter = useCallback((e) => {
        e?.preventDefault?.();
        const action = actionInput.trim();
        setQuery(action ? { action, limit } : { limit });
    }, [actionInput, limit]);

    const byDecision = useMemo(() => countBy(rows, (r) => decisionText(r.decision)), [rows]);
    const denied = rows.filter((r) => isDenial(r.decision)).length;

    const styles = {
        table: { width: '100%', borderCollapse: 'collapse', color: tokens.color?.['text-100'] },
        th: { borderBottom: '1px solid var(--border-subtle)', padding: '9px 8px', textAlign: 'left', fontSize: 12, fontWeight: 500, color: tokens.color?.['muted-600'], whiteSpace: 'nowrap' },
        td: { borderBottom: '1px solid var(--border-subtle)', padding: '10px 8px', fontSize: 12.5, verticalAlign: 'top' },
        scroll: { maxHeight: 420, overflowY: 'auto', overflowX: 'auto', marginTop: 12 },
        top: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: tokens.spacing?.lg, marginBottom: tokens.spacing?.lg },
    };

    return (
        <div>
            <div style={styles.top}>
                <DataCard title="Decisions in this view" value={rows.length} unit={rows.length === 1 ? 'entry' : 'entries'}
                          color={tokens.color?.['accent-primary']} icon={<ScrollText size={22} />} />
                <DataCard title="Blocked by policy" value={denied} unit={denied === 1 ? 'entry' : 'entries'}
                          color={denied > 0 ? tokens.color?.danger : tokens.color?.success} icon={<AlertTriangle size={22} />} />
                <DataCard title="How these decisions landed" isChart minHeight="150px">
                    <BarChartWidget data={byDecision} minHeight="110px" color={tokens.color?.['accent-secondary']} />
                </DataCard>
            </div>

            <div style={s.panel}>
                <div style={{ ...s.row, justifyContent: 'space-between' }}>
                    <h3 style={s.sectionTitle}><ScrollText size={16} color={tokens.color?.success} /> Enforcement audit trail</h3>
                    <form onSubmit={applyFilter} style={s.row}>
                        <input style={{ ...s.input, minWidth: 220 }} value={actionInput}
                               onChange={(e) => setActionInput(e.target.value)}
                               placeholder="Filter by what triggered the check" />
                        <button type="submit" style={dim(s.btn, isLoading)} disabled={isLoading}>
                            {isLoading ? <Loader2 size={15} className="animate-spin" /> : <Search size={15} />} Filter
                        </button>
                        <button type="button" style={dim(s.btnGhost, isLoading)} disabled={isLoading} onClick={() => refetch()}>
                            <RefreshCw size={15} /> Refresh
                        </button>
                    </form>
                </div>

                <p style={{ ...s.hint, margin: '10px 0 0' }}>
                    Each row is one decision the enforcement engine recorded, newest first, capped at {limit}.
                </p>

                {error && (
                    <p style={{ color: tokens.color?.danger, fontSize: 13, marginTop: 12 }}>
                        <AlertTriangle size={14} style={{ marginBottom: -2, marginRight: 6 }} />
                        The audit trail could not be read: {error}
                    </p>
                )}

                {!error && !isLoading && rows.length === 0 && (
                    <p style={{ ...s.hint, marginTop: 16 }}>
                        No decision has been recorded yet for this filter. Clear the filter, or activate a policy so the engine starts judging transactions.
                    </p>
                )}

                {rows.length > 0 && (
                    <div style={styles.scroll}>
                        <table style={styles.table}>
                            <thead>
                                <tr>
                                    <th style={styles.th}>When</th>
                                    <th style={styles.th}>What was checked</th>
                                    <th style={styles.th}>Outcome</th>
                                    <th style={styles.th}>Why</th>
                                    <th style={styles.th}>Audit reference</th>
                                </tr>
                            </thead>
                            <tbody>
                                {rows.map((r) => (
                                    <tr key={r.audit_id}>
                                        <td style={styles.td}>{r.timestamp ? new Date(r.timestamp).toLocaleString() : 'not recorded'}</td>
                                        <td style={styles.td}>{humanise(r.action)}</td>
                                        <td style={{ ...styles.td, color: isDenial(r.decision) ? tokens.color?.danger : tokens.color?.success }}>
                                            {decisionText(r.decision)}
                                        </td>
                                        <td style={{ ...styles.td, color: tokens.color?.['muted-500'], maxWidth: 380 }}>
                                            {r.summary || 'No reason was recorded.'}
                                        </td>
                                        <td style={{ ...styles.td, ...s.mono }}>{r.audit_id}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </div>
    );
});

AuditTraceLog.displayName = 'AuditTraceLog';
export default AuditTraceLog;
