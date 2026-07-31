// /frontend/src/hooks/use-toast.js - FINAL PRODUCTION-READY REPLACEMENT
import React, { createContext, useContext, useState, useCallback, useEffect, useMemo, useRef } from 'react';

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
    const timers = useRef([]);

    const toast = useCallback((options) => {
        const { title, description, variant = 'info', duration = DURATION } = options || {};

        // A toast with nothing to say is a blank outlined box on screen, which
        // tells the user only that something went wrong somewhere. Refuse it,
        // and say in the console which call was at fault so it can be found.
        if (!String(title || '').trim() && !String(description || '').trim()) {
            console.error('A toast was raised with no title and no description; ignoring it.', options);
            return;
        }

        // One screen makes several requests, so one expired session raised the
        // same message once per request: four identical boxes stacked up saying
        // the same thing. The same message is shown once and its life extended,
        // rather than repeated.
        const id = generateId();
        let isDuplicate = false;
        setToasts(prev => {
            const existing = prev.find(t => t.title === title && t.description === description);
            if (existing) {
                isDuplicate = true;
                return prev;
            }
            return [{ id, title, description, variant, duration }, ...prev];
        });
        if (isDuplicate) return;

        const timer = setTimeout(() => dismissToast(id), duration);
        timers.current.push(timer);
    }, [dismissToast]);

    // Timers outlived the provider, so a dismiss could fire against an unmounted
    // component after signing out.
    useEffect(() => () => {
        timers.current.forEach(clearTimeout);
        timers.current = [];
    }, []);

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