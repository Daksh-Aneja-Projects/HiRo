// /frontend/src/components/AuditTraceLog.js - FINAL PRODUCTION-READY REPLACEMENT (Fixes fontSize TypeErrors)
import React, { useMemo, memo, useState, useCallback } from 'react';
import { theme as tokens } from '../theme';
import { useApi } from '../hooks/useApi';
import { getAuditTrace } from '../config/api'; // CRITICAL FIX: Import stabilized API function
import { Clock, Search, Loader2, AlertTriangle, Shield } from 'lucide-react';

const AuditTraceLog = memo(({ initialFilters = {} }) => {
    const [filters, setFilters] = useState(initialFilters);
    
    // CRITICAL API INTEGRATION: Fetch audit logs based on current filters
    const { 
        data: auditLogs = [], // Default to empty array for safe mapping
        isLoading, 
        error, 
        refetch 
    } = useApi(getAuditTrace, [{ params: filters }], true, []); // Pass filters as params in the API call

    const handleFilterChange = useCallback((key, value) => {
        setFilters(prev => ({ ...prev, [key]: value }));
    }, []);

    const handleRefetch = useCallback(() => {
        refetch();
    }, [refetch]);

    const styles = useMemo(() => ({
        container: { background: tokens.color?.['panel-800'], borderRadius: tokens.border?.radius?.card, padding: tokens.spacing?.md, height: '100%', display: 'flex', flexDirection: 'column' },
        header: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: tokens.spacing?.md, borderBottom: `1px solid ${tokens.color?.['border-600']}`, paddingBottom: tokens.spacing?.xs },
        input: { padding: '8px 12px', background: tokens.color?.['bg-input'], border: `1px solid ${tokens.color?.['border-600']}`, borderRadius: tokens.border?.radius?.input, color: tokens.color?.['text-100'], flexGrow: 1, minWidth: '150px' },
        logArea: { flexGrow: 1, overflowY: 'auto', marginTop: tokens.spacing?.md },
        logTable: { width: '100%', borderCollapse: 'collapse', color: tokens.color?.['text-100'] },
        // --- FIX: Added optional chaining ---
        th: { borderBottom: `1px solid ${tokens.color?.['border-600']}`, padding: '10px 5px', textAlign: 'left', color: tokens.color?.['accent-secondary'], fontSize: tokens.typography?.small?.fontSize },
        td: { borderBottom: `1px dotted ${tokens.color?.['border-700']}`, padding: '10px 5px', fontSize: tokens.typography?.small?.fontSize },
        // ------------------------------------
    }), []);

    return (
        <div style={styles.container}>
            <div style={styles.header}>
                <h3 style={{ margin: 0, color: tokens.color?.['text-100'] }}>
                    <Shield size={20} style={{ marginRight: tokens.spacing?.xs }} color={tokens.color?.success} />
                    PQC Audit Trace Log
                </h3>
            </div>
            
            {/* Filter Controls */}
            <div style={{ display: 'flex', gap: tokens.spacing?.sm, marginBottom: tokens.spacing?.md }}>
                <input 
                    type="text" 
                    placeholder="Filter by User ID" 
                    value={filters.user_id || ''} 
                    onChange={e => handleFilterChange('user_id', e.target.value)} 
                    style={styles.input} 
                />
                <input 
                    type="text" 
                    placeholder="Filter by Policy" 
                    value={filters.policy_id || ''} 
                    onChange={e => handleFilterChange('policy_id', e.target.value)} 
                    style={styles.input} 
                />
                <button 
                    onClick={handleRefetch} 
                    disabled={isLoading}
                    style={{ padding: '8px 15px', background: tokens.color?.['accent-primary'], border: 'none', borderRadius: tokens.border?.radius?.button, color: tokens.color?.['bg-deep'], cursor: 'pointer', display: 'flex', alignItems: 'center' }}
                >
                    {isLoading ? <Loader2 size={16} className="animate-spin" /> : <Search size={16} />}
                </button>
            </div>

            {/* Log Display Area */}
            <div style={styles.logArea}>
                {isLoading && <p style={{ textAlign: 'center' }}><Loader2 size={24} className="animate-spin" /> Fetching logs...</p>}
                {error && <p style={{ color: tokens.color?.danger, textAlign: 'center' }}><AlertTriangle size={24} /> Error: {error.message}</p>}
                
                <table style={styles.logTable}>
                    <thead>
                        <tr>
                            <th style={styles.th}>Timestamp</th>
                            <th style={styles.th}>Event</th>
                            <th style={styles.th}>User ID</th>
                            <th style={styles.th}>Status</th>
                            <th style={styles.th}>Trace ID</th>
                        </tr>
                    </thead>
                    <tbody>
                        {auditLogs.slice(0, 20).map(log => (
                            <tr key={log.trace_id}>
                                <td style={styles.td}>{new Date(log.timestamp).toLocaleTimeString()}</td>
                                <td style={styles.td}>{log.event_type}</td>
                                <td style={styles.td}>{log.user_id}</td>
                                <td style={styles.td}>
                                    <span style={{ color: log.status === 'SUCCESS' ? tokens.color?.success : tokens.color?.danger }}>
                                        {log.status}
                                    </span>
                                </td>
                                <td style={styles.td}>{log.trace_id.substring(0, 8)}...</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
                {auditLogs.length === 0 && !isLoading && !error && (
                    <p style={{ textAlign: 'center', color: tokens.color?.['muted-500'], marginTop: tokens.spacing?.md }}>No audit entries found for the current filters.</p>
                )}
            </div>
        </div>
    );
});

AuditTraceLog.displayName = 'AuditTraceLog';
export default AuditTraceLog;