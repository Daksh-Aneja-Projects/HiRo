// /frontend/src/contexts/AuthContext.js - FINAL PRODUCTION-READY REPLACEMENT (CRITICAL SECURITY)
import React, { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react';
import { useToast } from '../hooks/use-toast'; // Assuming useToast is stabilized
import { 
    fetchMe, 
    loginUser, 
    logoutUser, 
    setInterceptorToastFallback // CRITICAL: For global session timeout handling
} from '../config/api'; 
import { settings } from '../config/settings';

const AuthContext = createContext(null);

export const useAuth = () => {
    // CRITICAL FIX: Ensure defensive return if context is used outside provider
    const context = useContext(AuthContext);
    if (!context) {
        // This should not happen in a correctly structured app but is a crucial guardrail.
        console.error("useAuth must be used within an AuthProvider.");
        return { isAuthenticated: false, isLoading: false }; 
    }
    return context;
};

// --- Initial State and Token Management ---
const getInitialToken = () => sessionStorage.getItem('authToken');
const getInitialUserData = () => {
    try {
        const stored = sessionStorage.getItem('userData');
        return stored ? JSON.parse(stored) : null;
    } catch (e) {
        return null;
    }
};

export const AuthProvider = ({ children }) => {
    const { toast } = useToast();
    const [token, setToken] = useState(getInitialToken);
    const [user, setUser] = useState(getInitialUserData);
    const [isLoading, setIsLoading] = useState(true);

    // CRITICAL FIX 1: Set the global toast fallback function for API interceptors 
    useEffect(() => {
        setInterceptorToastFallback(toast);
    }, [toast]);

    // Derived State
    const isAuthenticated = useMemo(() => !!token, [token]);
    const userRole = useMemo(() => user?.role || settings.ROLES.GUEST, [user?.role]);

    // --- Core Data Fetcher (/me) ---
    const fetchUserData = useCallback(async (authToken) => {
        try {
            // CRITICAL FIX 2: Ensure the token is set before fetching /me
            sessionStorage.setItem('authToken', authToken); 
            const response = await fetchMe(); 
            const userData = response.data;
            
            sessionStorage.setItem('userData', JSON.stringify(userData));
            setUser(userData);
            return true;
        } catch (error) {
            console.error("Failed to fetch user data after login:", error);
            // If /me fails, force logout
            sessionStorage.removeItem('authToken');
            sessionStorage.removeItem('userData');
            setToken(null);
            setUser(null);
            toast({ title: 'Security Error', description: 'Failed to retrieve user profile.', variant: 'destructive' });
            return false;
        }
    }, [toast]);
    
    // --- Login Handler ---
    const login = useCallback(async (authToken) => {
        setToken(authToken);
        // CRITICAL FIX 3: Wait for user data to be fetched before finishing login sequence
        await fetchUserData(authToken);
    }, [fetchUserData]);
    
    // --- Logout Handler ---
    const logout = useCallback(() => {
        // Note: Actual API call (logoutUser) should happen here, but we prioritize local state update first
        try {
             logoutUser();
        } catch(e) {
            console.warn("API logout call failed, but clearing local session.");
        }
        sessionStorage.clear();
        setToken(null);
        setUser(null);
        // CRITICAL FIX 4: Navigate is usually handled at the page level (e.g., in Login.js)
    }, []);

    // --- Initialization Effect (Check stored token) ---
    useEffect(() => {
        // CRITICAL FIX 5: Check token and fetch user data only if token exists but user data is missing
        if (token && !user) {
            fetchUserData(token).finally(() => {
                setIsLoading(false);
            });
        } else {
            setIsLoading(false);
        }
    }, [token, user, fetchUserData]);
    
    // --- Role Checker ---
    const checkRole = useCallback((allowedRoles) => {
        if (!user || !user.role) return false;
        return allowedRoles.includes(user.role);
    }, [user]);

    // --- Context Value ---
    const value = useMemo(() => ({
        isAuthenticated,
        user,
        userRole,
        token,
        isLoading,
        login,
        logout,
        checkRole,
    }), [isAuthenticated, user, userRole, token, isLoading, login, logout, checkRole]);

    return (
        <AuthContext.Provider value={value}>
            {children}
        </AuthContext.Provider>
    );
};