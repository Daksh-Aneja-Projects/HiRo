// /frontend/src/components/ToastContainer.js - FINAL PRODUCTION-READY REPLACEMENT
import React, { useMemo, memo } from 'react';
import { useToast } from '../hooks/use-toast';
import { theme as tokens } from '../theme';
import Toast from './Toast'; // Assuming Toast component exists

const ToastContainer = memo(() => {
    // CRITICAL: The useToast hook should provide the array of active toasts and a dismiss function
    const { toasts, dismissToast } = useToast();

    const styles = useMemo(() => ({
        container: {
            position: 'fixed',
            top: tokens.spacing?.lg, 
            right: tokens.spacing?.lg, 
            zIndex: 7000, 
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'flex-end',
            maxWidth: '400px', 
        }
    }), []);

    if (toasts.length === 0) {
        return null;
    }

    return (
        <div style={styles.container}>
            {toasts.map((toast) => (
                // CRITICAL FIX: Ensure key, dismiss handler, and props are correctly passed
                <Toast 
                    key={toast.id}
                    title={toast.title}
                    description={toast.description}
                    variant={toast.variant}
                    onDismiss={() => dismissToast(toast.id)}
                />
            ))}
        </div>
    );
});

ToastContainer.displayName = 'ToastContainer';
export default ToastContainer;