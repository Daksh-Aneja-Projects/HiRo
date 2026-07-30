// /frontend/src/components/AuthenticatedRouter.js - FINAL PRODUCTION-READY REPLACEMENT
import React, { useMemo, memo } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Navigate, Outlet } from 'react-router-dom';
import { settings } from '../config/settings';
import { hasAccess } from '../config/portalAccess';

const ROLES = settings.ROLES;

// Maps the backend role string to a preferred landing path.
// Note: ROLES.SUPER_ADMIN and ROLES.HRIT_MANAGER are the same wire value
// ('hrit_admin') — there is no distinct admin role — so only one entry is kept.
const ROLE_TO_PATH_MAP = {
    [ROLES.HRIT_MANAGER]: '/hrit-portal',
    [ROLES.HRBP]: '/hr-portal',
    [ROLES.MANAGER]: '/manager-portal',
    [ROLES.EMPLOYEE]: '/employee-portal',
};

/**
 * Component responsible for:
 * 1. Determining the user's default landing page upon successful authentication.
 * 2. Redirecting the user to a fallback dashboard if their specific portal is restricted (though usually handled by ProtectedRoute).
 */
const AuthenticatedRouter = memo(() => {
    const { user, userRole, isLoading } = useAuth();
    
    // CRITICAL FIX: The logic must wait for loading to complete
    if (isLoading) {
        // Return null or a simple spinner component if needed, but for routing, null is fine.
        return null; 
    }

    if (!user || !userRole) {
        // Should be caught by ProtectedRoute, but we handle it defensively here
        return <Navigate to="/login" replace />;
    }
    
    // Convert role to lowercase for consistent map lookup
    const roleKey = userRole?.toLowerCase(); 
    
    // 1. Determine the target path
    let targetPath = ROLE_TO_PATH_MAP[roleKey] || '/dashboard';
    
    // 2. CRITICAL FIX: Ensure the resolved target path is accessible. 
    // If not, fall back to the generic dashboard.
    if (!hasAccess(userRole, targetPath)) {
        console.warn(`User role ${userRole} does not have access to ${targetPath}. Redirecting to /dashboard.`);
        targetPath = '/dashboard';
    }
    
    // 3. If the current path is the root "/" or "/dashboard", redirect to the role-specific path.
    // NOTE: useLocation is often used here, but since this component is nested directly under 
    // the generic / and /dashboard routes (see App.js), a simple check is sufficient.
    const currentPath = window.location.pathname;
    
    // If the user lands on the base path or the generic dashboard, redirect them.
    if (currentPath === '/' || currentPath === '/dashboard') {
        // Navigate only if the determined target path is different
        if (targetPath !== currentPath) {
            return <Navigate to={targetPath} replace />;
        }
    }
    
    // Otherwise, allow the nested routes (Outlet) to render normally.
    return <Outlet />;
});

AuthenticatedRouter.displayName = 'AuthenticatedRouter';
export default AuthenticatedRouter;