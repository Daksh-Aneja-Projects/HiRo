// /frontend/src/config/portalAccess.js - FINAL PRODUCTION-READY REPLACEMENT
import { Briefcase, Cpu, Users, Settings, User, Zap, BarChart3, MessageCircle, ShieldCheck } from 'lucide-react';
import { settings } from './settings';

const ROLES = settings.ROLES;

export const SIDEBAR_NAV = [
    { 
        label: 'Executive Dashboard', 
        path: '/dashboard', 
        icon: Zap, 
        roles: [ROLES.HRIT_MANAGER, ROLES.HRBP, ROLES.MANAGER, ROLES.SUPER_ADMIN, ROLES.EMPLOYEE], 
        color: 'accent-primary', 
        subModules: [] 
    },
    { 
        label: 'Collaboration Hub', 
        path: '/social-feed', 
        icon: MessageCircle, 
        roles: [ROLES.EMPLOYEE, ROLES.MANAGER, ROLES.HRBP, ROLES.HRIT_MANAGER, ROLES.SUPER_ADMIN], 
        color: 'success', 
        subModules: [] 
    },
    { 
        label: 'HR Portal', 
        path: '/hr-portal', 
        icon: Briefcase, 
        roles: [ROLES.HRBP, ROLES.HRIT_MANAGER, ROLES.SUPER_ADMIN], 
        color: 'danger', 
        subModules: [
            { label: 'Policy Governance', path: '/hr-portal?module=policy' },
            { label: 'Compensation Workbench', path: '/hr-portal?module=comp' },
            { label: 'Talent Insights', path: '/hr-portal?module=talent' },
            { label: 'Document Ingestion', path: '/hr-portal?module=ingestion' },
            { label: 'HRSD Case Mgmt', path: '/hr-portal?module=cases' }, 
        ] 
    },
    { 
        label: 'HRIT Portal', 
        path: '/hrit-portal', 
        icon: Cpu, 
        roles: [ROLES.HRIT_MANAGER, ROLES.SUPER_ADMIN], 
        color: 'accent-primary', 
        subModules: [
            { label: 'Agent Factory', path: '/hrit-portal?module=agent' },
            { label: 'Autonomous Healing', path: '/hrit-portal?module=governance' }, 
            { label: 'Telemetry', path: '/hrit-portal?module=health' },
        ] 
    },
    { 
        label: 'Manager Portal', 
        path: '/manager-portal', 
        icon: Users, 
        roles: [ROLES.MANAGER, ROLES.SUPER_ADMIN, ROLES.HRBP], 
        color: 'accent-primary', 
        subModules: [
            { label: 'Team Overview', path: '/manager-portal?module=team' },
            { label: 'Approvals Queue', path: '/manager-portal?module=overview' },
            { label: 'Attrition Simulation', path: '/manager-portal?module=risk' },
        ] 
    },
    { 
        label: 'Employee Portal', 
        path: '/employee-portal', 
        icon: User, 
        roles: [ROLES.EMPLOYEE, ROLES.MANAGER, ROLES.SUPER_ADMIN], 
        color: 'accent-secondary', 
        subModules: [
            { label: 'My Dashboard', path: '/employee-portal?module=dashboard' },
            { label: 'My Leaves', path: '/employee-portal?module=leave' },
            { label: 'My Benefits', path: '/employee-portal?module=pii' },
        ] 
    },
    { 
        label: 'Advanced Analytics', 
        path: '/advanced-analytics', 
        icon: BarChart3, 
        roles: [ROLES.HRIT_MANAGER, ROLES.HRBP, ROLES.SUPER_ADMIN], 
        color: 'success', 
        subModules: [] 
    },
    {
        label: 'Orchestrator Control',
        path: '/ultimate-orchestrator',
        icon: Settings,
        roles: [ROLES.HRIT_MANAGER, ROLES.SUPER_ADMIN],
        color: 'warning',
        subModules: [
            { label: 'RLFF & AI Command', path: '/ultimate-orchestrator?module=command' },
            { label: 'System Governor', path: '/ultimate-orchestrator?module=danger' },
        ]
    },
    {
        label: 'Admin Console',
        path: '/admin-portal',
        icon: ShieldCheck,
        roles: [ROLES.HRIT_MANAGER, ROLES.SUPER_ADMIN],
        color: 'danger',
        subModules: []
    },
    {
        label: 'Profile',
        path: '/user-profile',
        icon: User,
        roles: [ROLES.HRIT_MANAGER, ROLES.HRBP, ROLES.MANAGER, ROLES.SUPER_ADMIN, ROLES.EMPLOYEE],
        color: 'accent-secondary',
        subModules: []
    }
];

export const PORTAL_MAP = SIDEBAR_NAV.reduce((map, item) => {
    const pathKey = item.path.split('?')[0];
    map[pathKey] = {
        label: item.label,
        color: item.color,
        icon: item.icon,
        roles: item.roles,
    };
    return map;
}, {});

/**
 * CRITICAL FIX: The core access check logic.
 */
export const hasAccess = (userRole, requiredPath) => {
    const userRoleLower = (userRole || '').toLowerCase();
    const SUPER_ADMIN_VALUE = ROLES.HRIT_MANAGER.toLowerCase();
    
    // Allow HRIT_ADMIN/SUPER_ADMIN access to everything
    if (userRoleLower === SUPER_ADMIN_VALUE) {
        return true;
    }

    const pathKey = requiredPath.split('?')[0];
    const portalEntry = PORTAL_MAP[pathKey];

    // Special case for root paths
    if (pathKey === '/' || pathKey === '/dashboard') {
        return userRoleLower !== ROLES.GUEST;
    }

    if (portalEntry) {
        // Compare the current userRole (backend value) directly with the list of allowed role values
        return portalEntry.roles.some(r => (r || '').toLowerCase() === userRoleLower);
    }
    return false;
};