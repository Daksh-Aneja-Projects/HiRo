// /frontend/src/components/StatusChip.js - FINAL PRODUCTION-READY REPLACEMENT
import React, { useMemo, memo } from 'react';
import { theme as tokens } from '../theme';
import { CheckCircle, AlertTriangle, XCircle, Clock } from 'lucide-react';

const StatusChip = memo(({ status, label }) => {

    const normalizeStatus = (s) => s?.toUpperCase() || 'UNKNOWN';
    const currentStatus = normalizeStatus(status);
    const displayLabel = label || currentStatus;

    // CRITICAL: Map status strings to theme tokens and icons
    const statusMap = useMemo(() => ({
        ONLINE: { color: tokens.color?.success, Icon: CheckCircle },
        COMPLETE: { color: tokens.color?.success, Icon: CheckCircle },
        PENDING: { color: tokens.color?.warning, Icon: Clock },
        WARNING: { color: tokens.color?.warning, Icon: AlertTriangle },
        ERROR: { color: tokens.color?.danger, Icon: XCircle },
        OFFLINE: { color: tokens.color?.danger, Icon: XCircle },
        UNKNOWN: { color: tokens.color?.['muted-500'], Icon: Clock },
        ACTIVE: { color: tokens.color?.success, Icon: CheckCircle },
    }), []);

    const { color, Icon } = statusMap[currentStatus] || statusMap['UNKNOWN'];

    const styles = useMemo(() => ({
        chip: {
            display: 'inline-flex',
            alignItems: 'center',
            gap: tokens.spacing?.xs,
            padding: '4px 8px',
            borderRadius: tokens.border?.radius?.chip,
            background: color + '20', // Light background tint
            border: `1px solid ${color}`,
            color: color,
            fontSize: tokens.typography.small.fontSize,
            fontWeight: tokens.typography.h2.fontWeight,
            textTransform: 'uppercase',
        }
    }), [color]);


    return (
        <div style={styles.chip}>
            <Icon size={14} />
            {displayLabel}
        </div>
    );
});

StatusChip.displayName = 'StatusChip';
export default StatusChip;