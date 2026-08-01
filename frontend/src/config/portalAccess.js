// /frontend/src/config/portalAccess.js - FINAL PRODUCTION-READY REPLACEMENT
import { Briefcase, Cpu, Users, Settings, User, Zap, BarChart3, MessageCircle, ShieldCheck, Network } from 'lucide-react';
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
            { label: 'Policy Lifecycle', path: '/hr-portal?module=policy' },
            { label: 'Compliance Posture', path: '/hr-portal?module=compliance' },
            { label: 'Rule Compiler', path: '/hr-portal?module=rules' },
            { label: 'Workforce Governance', path: '/hr-portal?module=governance' },
            { label: 'Audit Trail', path: '/hr-portal?module=audit' },
            { label: 'Compensation Workbench', path: '/hr-portal?module=comp' },
            { label: 'Comp Review Cycles', path: '/hr-portal?module=compcycles' },
            { label: 'Talent Insights', path: '/hr-portal?module=talent' },
            { label: 'Succession & 9-Box', path: '/hr-portal?module=succession' },
            { label: 'Headcount Planning', path: '/hr-portal?module=headcount' },
            { label: 'Engagement', path: '/hr-portal?module=engagement' },
            { label: 'Onboarding Plans', path: '/hr-portal?module=onboarding' },
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
            { label: 'Governance', path: '/hrit-portal?module=governance' },
            { label: 'System Health', path: '/hrit-portal?module=health' },
            { label: 'Models', path: '/hrit-portal?module=models' },
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
            { label: 'Your Week', path: '/manager-portal?module=cadence' },
            { label: 'Approvals', path: '/manager-portal?module=approvals' },
            { label: 'Goals & Reviews', path: '/manager-portal?module=goals' },
            { label: 'New Joiners', path: '/manager-portal?module=onboarding' },
            { label: 'Hiring', path: '/manager-portal?module=hiring' },
            { label: 'Performance', path: '/manager-portal?module=performance' },
            { label: 'Workforce Risk', path: '/manager-portal?module=risk' },
            { label: 'Attrition Simulation', path: '/manager-portal?module=simulation' },
            { label: 'Recognition', path: '/manager-portal?module=recognition' },
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
            { label: 'Onboarding', path: '/employee-portal?module=onboarding' },
            { label: 'Timesheets', path: '/employee-portal?module=timesheets' },
            { label: 'Leave', path: '/employee-portal?module=leave' },
            { label: 'Pay & Benefits', path: '/employee-portal?module=pay' },
            { label: 'Goals', path: '/employee-portal?module=goals' },
            { label: 'Ask HiRo', path: '/employee-portal?module=ask' },
            { label: 'Growth', path: '/employee-portal?module=growth' },
            { label: 'Documents', path: '/employee-portal?module=documents' },
            { label: 'Expenses', path: '/employee-portal?module=expenses' },
            { label: 'Privacy', path: '/employee-portal?module=pii' },
            { label: 'Offboarding', path: '/employee-portal?module=offboarding' },
        ]
    },
    {
        label: 'Neural Map',
        path: '/neural',
        icon: Network,
        roles: [ROLES.HRIT_MANAGER, ROLES.HRBP, ROLES.SUPER_ADMIN],
        color: 'accent-primary',
        subModules: []
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
            { label: 'Command', path: '/ultimate-orchestrator?module=command' },
            { label: 'History', path: '/ultimate-orchestrator?module=history' },
            { label: 'Danger Zone', path: '/ultimate-orchestrator?module=danger' },
        ]
    },
    {
        label: 'Admin Console',
        path: '/admin-portal',
        icon: ShieldCheck,
        roles: [ROLES.HRIT_MANAGER, ROLES.SUPER_ADMIN],
        color: 'danger',
        subModules: [
            { label: 'Users & Roles', path: '/admin-portal?module=users' },
            { label: 'Announcements', path: '/admin-portal?module=announcements' },
            { label: 'System', path: '/admin-portal?module=system' },
            { label: 'Security', path: '/admin-portal?module=security' },
        ]
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