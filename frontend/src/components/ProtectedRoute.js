// ProtectedRoute - decides whether this person may open this screen.
import React, { memo, useEffect, useRef } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { hasAccess } from '../config/portalAccess';
import { useToast } from '../hooks/use-toast';
import LoadingScreen from './LoadingScreen';

const ROLE_NAMES = {
    hrit_admin: 'HRIT administrator',
    hritmanager: 'HRIT administrator',
    hrbp: 'HR business partner',
    manager: 'manager',
    employee: 'employee',
};

const readableRole = (role) => ROLE_NAMES[String(role || '').toLowerCase()]
    || String(role || 'signed-in user').replace(/_/g, ' ');

const PORTAL_NAMES = {
    '/hr-portal': 'HR Operations',
    '/hrit-portal': 'the HRIT console',
    '/manager-portal': 'the manager portal',
    '/employee-portal': 'the employee portal',
    '/admin-portal': 'the admin console',
    '/advanced-analytics': 'advanced analytics',
    '/ultimate-orchestrator': 'orchestrator control',
};

const ProtectedRoute = memo(() => {
    const { isAuthenticated, userRole, isLoading } = useAuth();
    const location = useLocation();
    const { toast } = useToast();

    const allowed = !isLoading && isAuthenticated && hasAccess(userRole, location.pathname);
    const denied = !isLoading && isAuthenticated && !allowed;

    // Telling the user has to happen after the render, not during it. Calling
    // toast() in the render body updated ToastProvider while this component was
    // still rendering, which React warns about and which can drop or duplicate
    // the message depending on when the redirect lands.
    const announced = useRef(null);
    useEffect(() => {
        if (!denied || announced.current === location.pathname) return;
        announced.current = location.pathname;
        const where = PORTAL_NAMES[location.pathname] || 'that screen';
        toast({
            title: 'You do not have access to that',
            description: `Your account is set up as ${readableRole(userRole)}, which cannot open ${where}. You have been brought back to your dashboard.`,
            variant: 'destructive',
        });
    }, [denied, location.pathname, userRole, toast]);

    if (isLoading) return <LoadingScreen />;
    if (!isAuthenticated) return <Navigate to="/login" state={{ from: location }} replace />;
    if (denied) return <Navigate to="/dashboard" replace />;
    return <Outlet />;
});

ProtectedRoute.displayName = 'ProtectedRoute';
export default ProtectedRoute;
