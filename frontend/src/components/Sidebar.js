// /frontend/src/components/Sidebar.js - APPLE/GOOGLE FLOATING DOCK OVERHAUL
import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { 
    LayoutDashboard, Users, ShieldCheck, 
    Settings, Briefcase, Activity
} from 'lucide-react';
import { settings } from '../config/settings';

const FloatingDock = () => {
    const { userRole, logout } = useAuth();
    const location = useLocation();
    const navigate = useNavigate();

    // Reusing the same role-based rendering logic but streamlined for the dock
    const navItems = [];

    if (userRole === settings.ROLES.EMPLOYEE) {
        navItems.push({ icon: <LayoutDashboard size={20} />, label: 'Dashboard', path: '/dashboard' });
        navItems.push({ icon: <Users size={20} />, label: 'Portal', path: '/employee-portal' });
    } else if (userRole === settings.ROLES.MANAGER) {
        navItems.push({ icon: <LayoutDashboard size={20} />, label: 'Dashboard', path: '/dashboard' });
        navItems.push({ icon: <Briefcase size={20} />, label: 'Team', path: '/manager-portal' });
    } else if (userRole === settings.ROLES.HRBP || userRole === settings.ROLES.HR_MANAGER) {
        navItems.push({ icon: <LayoutDashboard size={20} />, label: 'Dashboard', path: '/dashboard' });
        navItems.push({ icon: <Users size={20} />, label: 'HR', path: '/hr-portal' });
    } else if (userRole === settings.ROLES.HRIT_ADMIN) {
        navItems.push({ icon: <LayoutDashboard size={20} />, label: 'Dashboard', path: '/dashboard' });
        navItems.push({ icon: <Settings size={20} />, label: 'HRIT', path: '/hrit-portal' });
        navItems.push({ icon: <Activity size={20} />, label: 'Analytics', path: '/advanced-analytics' });
    } else if (userRole === settings.ROLES.SYS_ADMIN) {
        navItems.push({ icon: <LayoutDashboard size={20} />, label: 'Dashboard', path: '/dashboard' });
        navItems.push({ icon: <Settings size={20} />, label: 'HRIT', path: '/hrit-portal' });
        navItems.push({ icon: <ShieldCheck size={20} />, label: 'Admin', path: '/admin-portal' });
        navItems.push({ icon: <Activity size={20} />, label: 'Orchestrator', path: '/ultimate-orchestrator' });
    }

    return (
        <div className="dynamic-island-dock">
            {navItems.map((item, idx) => {
                const isActive = location.pathname.startsWith(item.path);
                return (
                    <div 
                        key={idx}
                        className={`dock-item ${isActive ? 'active' : ''}`}
                        onClick={() => navigate(item.path)}
                        title={item.label}
                    >
                        {item.icon}
                    </div>
                );
            })}
        </div>
    );
};

export default FloatingDock;