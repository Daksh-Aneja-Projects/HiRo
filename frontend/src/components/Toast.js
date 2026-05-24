// /frontend/src/components/Toast.js - FINAL PRODUCTION-READY REPLACEMENT
import React, { useMemo, memo } from 'react';
import { theme as tokens } from '../theme';
import { CheckCircle, AlertTriangle, XCircle, Info } from 'lucide-react';

const Toast = memo(({ title, description, variant, onDismiss }) => {

    const variantMap = useMemo(() => ({
        success: { color: tokens.color?.success, Icon: CheckCircle },
        warning: { color: tokens.color?.warning, Icon: AlertTriangle },
        destructive: { color: tokens.color?.danger, Icon: XCircle },
        info: { color: tokens.color?.['accent-secondary'], Icon: Info },
    }), []);

    const { color, Icon } = variantMap[variant] || variantMap.info;

    const styles = useMemo(() => ({
        card: {
            background: tokens.color?.['panel-800'],
            border: `1px solid ${color}`,
            borderRadius: tokens.border?.radius?.card,
            padding: tokens.spacing?.md,
            boxShadow: tokens.shadow?.xl,
            width: '300px',
            marginBottom: tokens.spacing?.md,
            display: 'flex',
            gap: tokens.spacing?.sm,
            alignItems: 'flex-start',
            position: 'relative',
        },
        title: {
            margin: 0,
            fontSize: tokens.typography.base.fontSize,
            fontWeight: tokens.typography.h2.fontWeight,
            color: color,
        },
        description: {
            margin: '4px 0 0 0',
            fontSize: tokens.typography.small.fontSize,
            color: tokens.color?.['text-100'],
        },
        dismissButton: {
            position: 'absolute',
            top: tokens.spacing?.xs,
            right: tokens.spacing?.xs,
            background: 'none',
            border: 'none',
            color: tokens.color?.['muted-500'],
            cursor: 'pointer',
            padding: 0,
            transition: 'color 0.2s',
        }
    }), [color]);


    return (
        <div style={styles.card}>
            <Icon size={20} color={color} />
            <div style={{ flexGrow: 1 }}>
                <p style={styles.title}>{title}</p>
                {description && <p style={styles.description}>{description}</p>}
            </div>
            <button onClick={onDismiss} style={styles.dismissButton} className="toast-dismiss-hover">
                <XCircle size={16} />
            </button>
            <style>{`.toast-dismiss-hover:hover { color: ${tokens.color?.danger} !important; }`}</style>
        </div>
    );
});

Toast.displayName = 'Toast';
export default Toast;