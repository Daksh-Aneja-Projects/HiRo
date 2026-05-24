// /frontend/src/hooks/use-toast.js - FINAL PRODUCTION-READY REPLACEMENT
import React, { createContext, useContext, useState, useCallback, useEffect, useMemo } from 'react';

const ToastContext = createContext(null);

const generateId = () => Math.random().toString(36).substring(2, 9);
const DURATION = 5000; // 5 seconds default duration

export const useToast = () => {
    const context = useContext(ToastContext);
    if (!context) {
        // CRITICAL FIX: Fallback and warning if used outside provider
        console.error("useToast must be used within a ToastProvider.");
        return { toast: () => {}, toasts: [] }; 
    }
    return context;
};

export const ToastProvider = ({ children }) => {
    // CRITICAL FIX 1: Use a functional update for the toast state array
    const [toasts, setToasts] = useState([]);

    // CRITICAL FIX 2: Implement dismissToast as useCallback
    const dismissToast = useCallback((id) => {
        setToasts(prev => prev.filter(toast => toast.id !== id));
    }, []);

    // CRITICAL FIX 3: Implement toast sender as useCallback
    const toast = useCallback(({ title, description, variant = 'info', duration = DURATION }) => {
        const id = generateId();
        const newToast = { id, title, description, variant, duration };

        setToasts(prev => [newToast, ...prev]);

        // Auto-dismiss the toast after its duration
        setTimeout(() => {
            dismissToast(id);
        }, duration);

    }, [dismissToast]);

    // Cleanup Effect (Removes toasts that might have been missed by timeout)
    useEffect(() => {
        if (toasts.length > 5) {
            // Keep the array manageable by enforcing a maximum size if needed, though DURATION should handle this
            setToasts(prev => prev.slice(0, 5));
        }
    }, [toasts]);

    // CRITICAL FIX 4: useMemo for stable provider value
    const value = useMemo(() => ({
        toasts,
        toast,
        dismissToast,
    }), [toasts, toast, dismissToast]);

    return (
        <ToastContext.Provider value={value}>
            {children}
        </ToastContext.Provider>
    );
};