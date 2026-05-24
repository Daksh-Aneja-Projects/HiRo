// /frontend/src/components/ProtectedRoute.js - FINAL PRODUCTION-READY REPLACEMENT (CRITICAL SECURITY)
import React, { useMemo, memo } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { hasAccess } from '../config/portalAccess'; // CRITICAL FIX: Import access control utility
import { useToast } from '../hooks/use-toast';
import LoadingScreen from './LoadingScreen'; // Assuming this component exists

/**
 * Ensures the user is authenticated and authorized to access the current route.
 */
const ProtectedRoute = memo(() => {
    const { isAuthenticated, userRole, isLoading } = useAuth();
    const location = useLocation();
    const { toast } = useToast();
    
    // 1. Wait for Auth Context to finish loading (essential for correct role assignment)
    if (isLoading) {
        return <LoadingScreen />;
    }

    // 2. Authentication Check (401)
    if (!isAuthenticated) {
        // Redirect unauthenticated users to login, storing the attempted path
        return <Navigate to="/login" state={{ from: location }} replace />;
    }

    // 3. Authorization Check (403)
    const currentPath = location.pathname;
    
    // CRITICAL FIX: Check if the user's role has access to the current path
    if (!hasAccess(userRole, currentPath)) {
        console.warn(`Access Denied: User role ${userRole} attempted to access ${currentPath}.`);
        
        // Notify the user of the access failure
        toast({
            title: 'Access Denied (403)',
            description: `Your role (${userRole}) is not authorized for this portal or feature.`,
            variant: 'destructive',
        });

        // Redirect unauthorized users to a safe default location (Dashboard)
        return <Navigate to="/dashboard" replace />;
    }

    // 4. Access Granted
    return <Outlet />;
});

ProtectedRoute.displayName = 'ProtectedRoute';
export default ProtectedRoute;