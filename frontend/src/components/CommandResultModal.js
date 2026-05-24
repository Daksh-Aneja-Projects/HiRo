// /frontend/src/components/CommandResultModal.js - STABILIZED (Fixes fontSize TypeErrors)

import React, { useMemo, memo } from 'react';
import { theme as tokens } from '../theme';
import { X, Clipboard, Save, Code, Zap, XCircle } from 'lucide-react'; 

const CommandResultModal = memo(({ 
    title, 
    content, 
    traceType = 'JSON', 
    onClose, 
    onAction, 
    actionLabel = 'Run Remediation', 
    // CRITICAL FIX: Use Zap as a default icon if none is provided
    actionIcon: ActionIcon = Zap 
}) => {

    const handleCopy = () => {
        navigator.clipboard.writeText(content).then(() => {
            alert('Trace content copied to clipboard!');
        }).catch(err => {
            console.error('Could not copy text: ', err);
        });
    };

    const styles = useMemo(() => ({
        overlay: {
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0, 0, 0, 0.85)',
            backdropFilter: 'blur(8px)',
            zIndex: 6000,
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
        },
        modal: {
            width: '90%',
            maxWidth: '700px',
            background: tokens.color?.['panel-800'],
            // CRITICAL FIX: Consistent color for the main border
            border: `1px solid ${tokens.color?.['accent-primary']}`, 
            borderRadius: tokens.border?.radius?.card,
            boxShadow: `0 0 20px rgba(${tokens['accent-primary-rgb']}, 0.4)`,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            maxHeight: '90vh',
        },
        header: {
            padding: tokens.spacing?.md,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            borderBottom: `1px solid ${tokens.color?.['border-600']}`,
        },
        title: {
            margin: 0,
            // --- FIX: Added optional chaining ---
            fontSize: tokens.typography?.h2?.fontSize,
            // ------------------------------------
            color: tokens.color?.['text-100'],
            display: 'flex',
            alignItems: 'center',
        },
        contentArea: {
            flexGrow: 1,
            padding: tokens.spacing?.md,
            overflowY: 'auto',
            background: tokens.color?.['panel-900'],
        },
        codeBlock: {
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            fontFamily: 'monospace',
            // --- FIX: Added optional chaining ---
            fontSize: tokens.typography?.small?.fontSize,
            // ------------------------------------
            lineHeight: 1.4,
            color: tokens.color?.['text-100'],
        },
        footer: {
            padding: tokens.spacing?.md,
            borderTop: `1px solid ${tokens.color?.['border-600']}`,
            display: 'flex',
            justifyContent: 'flex-end',
            gap: tokens.spacing?.md,
        },
        actionButton: {
            padding: '10px 15px',
            borderRadius: tokens.border?.radius?.button,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: tokens.spacing?.xs,
            // --- FIX: Added optional chaining ---
            fontWeight: tokens.typography?.button?.fontWeight,
            // ------------------------------------
            transition: 'all 0.2s ease',
            border: 'none',
            background: tokens.color?.['accent-primary'],
            color: tokens.color?.['bg-deep'],
        }
    }), [tokens]);

    return (
        <div style={styles.overlay} onClick={onClose}>
            <div style={styles.modal} onClick={e => e.stopPropagation()}>
                <div style={styles.header}>
                    <h2 style={styles.title}>
                        <Code size={24} style={{ marginRight: tokens.spacing?.sm }} /> 
                        {title}
                    </h2>
                    <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: tokens.color?.['text-100'] }} className="modal-close-btn-hover">
                        <X size={24} />
                    </button>
                </div>

                <div style={styles.contentArea}>
                    <pre style={styles.codeBlock}>
                        {content}
                    </pre>
                </div>

                <div style={styles.footer}>
                    <button onClick={handleCopy} style={{ ...styles.actionButton, background: tokens.color?.['panel-700'], color: tokens.color?.['text-100'] }} className="modal-copy-btn-hover">
                        <Clipboard size={16} /> Copy Trace
                    </button>
                    {onAction && (
                        <button onClick={onAction} style={styles.actionButton} className="modal-action-btn-hover">
                            <ActionIcon size={16} /> {actionLabel}
                        </button>
                    )}
                </div>
            </div>
            <style>{`
                .modal-close-btn-hover:hover {
                    color: ${tokens.color?.['danger']} !important;
                    transform: scale(1.1);
                }
                .modal-copy-btn-hover:hover {
                    box-shadow: ${tokens.shadow?.hover};
                    background: ${tokens.color?.['panel-600']} !important;
                }
                .modal-action-btn-hover:hover {
                    box-shadow: 0 0 10px ${tokens.color?.['danger']}55;
                    transform: translateY(-2px);
                }
            `}</style>
        </div>
    );
});

CommandResultModal.displayName = 'CommandResultModal';
export default CommandResultModal;