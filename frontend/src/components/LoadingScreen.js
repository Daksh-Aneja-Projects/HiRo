// /frontend/src/components/LoadingScreen.js - FINAL PRODUCTION-READY REPLACEMENT (Fixes fontSize TypeErrors)
import React, { useMemo, memo } from 'react';
import { theme as tokens } from '../theme';
import { Loader2, Zap } from 'lucide-react';

const LoadingScreen = memo(() => {

    const styles = useMemo(() => ({
        container: {
            minHeight: '100vh',
            width: '100vw',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            alignItems: 'center',
            background: tokens.color?.['bg-900'],
            position: 'fixed', // Ensure it covers everything
            top: 0,
            left: 0,
            zIndex: 9999,
        },
        logo: {
            display: 'flex',
            alignItems: 'baseline',
            gap: tokens.spacing?.sm,
            marginBottom: tokens.spacing?.lg,
        },
        logoText: {
            // --- FIX: Added optional chaining ---
            fontSize: tokens.typography?.h1?.fontSize,
            fontWeight: tokens.typography?.h1?.fontWeight,
            // ------------------------------------
            color: tokens.color?.['accent-primary'],
            margin: 0,
        },
        loader: {
            color: tokens.color?.['muted-500'],
            display: 'flex',
            alignItems: 'center',
            gap: tokens.spacing?.sm,
            marginTop: tokens.spacing?.md,
        }
    }), []);


    return (
        <div style={styles.container}>
            <div style={styles.logo}>
                <h1 style={styles.logoText}>HiRo</h1>
                <Zap size={40} color={tokens.color?.['accent-primary']} />
            </div>
            <div style={styles.loader}>
                <Loader2 size={24} className="animate-spin" />
                <p style={{ color: tokens.color?.['muted-500'], margin: 0 }}>Initializing AI Kernel...</p>
            </div>
            <style>{`
                /* Ensure animate-spin exists for the loader icon */
                @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
                .animate-spin { animation: spin 1s linear infinite; }
            `}</style>
        </div>
    );
});

LoadingScreen.displayName = 'LoadingScreen';
export default LoadingScreen;
