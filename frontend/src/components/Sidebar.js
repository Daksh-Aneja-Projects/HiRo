// /frontend/src/components/Sidebar.js - FINAL ADVANCED UI VERSION
import React, { memo, useMemo, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { SIDEBAR_NAV, hasAccess } from '../config/portalAccess'; // Keeping hasAccess for robustness
import { Link, useLocation } from 'react-router-dom';
import { theme as tokens } from '../theme';
import { LogOut, ChevronLeft, ChevronRight, User, Briefcase, Cpu, Users, Settings } from 'lucide-react';
import { settings } from '../config/settings'; // CRITICAL FIX: Ensure settings is imported

const Sidebar = memo(({ isExpanded, toggleSidebar }) => {
  const { userRole, logout, user } = useAuth();
  const location = useLocation();

  // Helper to safely get color code from tokens
  const getColorCode = useCallback((item) => {
    return item.color ? tokens.color[item.color] : tokens.color['accent-primary'];
  }, []);

  // Function to check if a main link is active or is the parent of an active sub-module
  const isLinkActive = useCallback((item) => {
    const currentPathname = location.pathname;
    // Check if current URL starts with the item's main path
    if (currentPathname.startsWith(item.path)) {
      // Additional check to prevent matching /hr/comp if current path is /hr-portal/
      // Only consider the base path match if the next character is a '/' or the end of string
      if (currentPathname.length === item.path.length || currentPathname.charAt(item.path.length) === '/') {
        return true;
      }
    }
    // Check if any sub-module path matches (includes query parameters)
    return item.subModules?.some(sub => location.pathname + location.search === sub.path) || false;
  }, [location.pathname, location.search]);

  // Dynamically filter navigation items based on user role
  const filteredNav = useMemo(() => {
    if (!userRole) return [];
    const role = userRole.toUpperCase();
    return SIDEBAR_NAV.filter(item =>
      // CRITICAL FIX: Reverting to the simpler security check from the *attached* file but using hasAccess
      Array.isArray(item.roles) && item.roles.some(r => hasAccess(userRole, item.path))
    );
  }, [userRole]);

  // REPLACED: Footer is now the advanced version with Log Out
  const renderFooter = useMemo(() => (
    <div style={{ padding: tokens.spacing.md, borderTop: `1px solid ${tokens.color['border-600']}` }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: isExpanded ? 'space-between' : 'center',
        cursor: 'pointer',
        padding: isExpanded ? tokens.spacing.sm : tokens.spacing.xs,
        borderRadius: tokens.border.radius.button,
        transition: 'background 200ms ease',
        ...(!isExpanded && { width: 'fit-content', margin: '0 auto' })
      }} onClick={logout} className="sidebar-logout-hover"
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: tokens.spacing.sm }}>
          <LogOut size={20} color={tokens.color.danger} />
          {isExpanded && <span style={{ color: tokens.color.danger, fontWeight: tokens.typography.base.fontWeight }}>Log Out</span>}
        </div>
        {isExpanded && user && <User size={20} color={tokens.color['muted-500']} title={user.full_name} />}
      </div>
    </div>
  ), [isExpanded, logout, user]);

  const sidebarStyle = useMemo(() => ({
    // CRITICAL: Set width to 80px for the collapsed state
    width: isExpanded ? '250px' : '80px',
    background: tokens.color['panel-700'],
    height: '100vh',
    display: 'flex',
    flexDirection: 'column',
    transition: 'width 250ms ease',
    flexShrink: 0,
    boxShadow: tokens.shadow.default,
  }), [isExpanded]);


  // REMOVED: The old renderItem function is replaced by inlining the logic below.

  return (
    <div style={sidebarStyle}>
      {/* Header/Logo (Simplified to match screenshot) */}
      <div style={{
        padding: tokens.spacing.md,
        borderBottom: `1px solid ${tokens.color['border-600']}`,
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexShrink: 0
      }}>
        {/* NEW: Use accent color and hide label when collapsed */}
        {isExpanded && <h2 style={{ fontSize: tokens.typography.h3.size, margin: 0, fontWeight: 700, letterSpacing: '-0.5px' }}>HiRo</h2>}
        {/* Toggle Button (Now always visible) */}
        <div
          onClick={toggleSidebar}
          style={{ cursor: 'pointer', padding: tokens.spacing.xs, borderRadius: '50%', background: tokens.color['panel-800'], marginLeft: isExpanded ? 0 : 'auto' }} // Adjusted margin for collapsed state
          className="sidebar-toggle-hover"
        >
          {isExpanded ? <ChevronLeft size={20} color={tokens.color['muted-500']} /> : <ChevronRight size={20} color={tokens.color['muted-500']} />}
        </div>
      </div>

      {/* Navigation (New Advanced Structure) */}
      <nav style={{ flexGrow: 1, overflowY: 'auto', padding: isExpanded ? tokens.spacing.sm : tokens.spacing.xs }}>
        {filteredNav.map(item => {
          const isActive = isLinkActive(item);
          const colorCode = getColorCode(item);

          return (
            <div key={item.path} style={{ marginBottom: tokens.spacing.sm }}>
              <Link
                to={item.path}
                // Inject the color as a CSS variable for the pulse effect
                style={{
                  '--active-color': colorCode,
                  '--active-bg-color': colorCode + '1A',
                  display: 'flex',
                  alignItems: 'center',
                  gap: tokens.spacing.md,
                  padding: tokens.spacing.sm,
                  borderRadius: tokens.border.radius.button,
                  textDecoration: 'none',
                  // NEW: Dynamic color for link text
                  color: isActive ? colorCode : tokens.color['text-100'],
                  fontWeight: isActive ? 600 : tokens.typography.base.fontWeight,
                  transition: 'all 200ms ease',
                  // NEW: Border-left indicator
                  borderLeft: `4px solid ${isActive ? colorCode : 'transparent'}`,
                  marginBottom: tokens.spacing.xs,
                  // NEW: Light background for active state
                  ...(isActive && {
                    background: colorCode + '1A',
                  }),
                  // Center icon when collapsed
                  justifyContent: isExpanded ? 'flex-start' : 'center',
                  
                }}
                className={`sidebar-nav-link ${isActive ? 'active' : ''}`}
              >
                <item.icon size={20} />
                {isExpanded && item.label}
              </Link>

              {/* Sub-modules for expanded view (Advanced) */}
              {isExpanded && isActive && (
                <div style={{ marginLeft: tokens.spacing.lg, borderLeft: `1px solid ${tokens.color['border-600']}`, paddingLeft: tokens.spacing.md }}>
                  {item.subModules?.map(sub => {
                    const isSubActive = location.pathname + location.search === sub.path;
                    return (
                      <Link
                        key={sub.path}
                        to={sub.path}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: tokens.spacing.md,
                          padding: `${tokens.spacing.xs} 0`,
                          textDecoration: 'none',
                          fontSize: tokens.typography.small.fontSize,
                          // NEW: Dynamic color for sub-link text
                          color: isSubActive ? colorCode : tokens.color['muted-500'],
                          fontWeight: isSubActive ? 600 : tokens.typography.base.fontWeight,
                          transition: 'color 200ms ease',
                        }}
                        className="sidebar-sub-link-hover" // Keeping hover class for potential future styling
                      >
                        <span style={{
                          width: '6px',
                          height: '6px',
                          borderRadius: '50%',
                          // NEW: Dynamic color for bullet point
                          background: isSubActive ? colorCode : tokens.color['muted-500'],
                        }}></span>
                        {sub.label}
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </nav>

      {/* Footer (Advanced Version) */}
      {renderFooter}

      <style>{`
        .sidebar-toggle-hover:hover {
          background: ${tokens.color['panel-700']};
          transform: scale(1.05);
        }
        
        /* NEW: Hover state for the Logout button */
        .sidebar-logout-hover:hover {
          background: rgba(${tokens.color['danger-rgb']}, 0.1) !important;
        }

        /* NEW: Hover state for main navigation links */
        .sidebar-nav-link:hover {
          transform: translateX(2px);
        }
        
        /* NEW: Apply dynamic color and pulse using injected CSS variables */
        .sidebar-nav-link.active {
            animation: sidebar-pulse 2s infinite;
            box-shadow: none; /* Override old box-shadow */
        }

        /* NEW: Keyframes for the pulse effect */
        @keyframes sidebar-pulse {
          0% { box-shadow: 0 0 0 0 var(--active-color, ${tokens.color['accent-primary']})60; }
          70% { box-shadow: 0 0 0 4px var(--active-color, ${tokens.color['accent-primary']})00; }
          100% { box-shadow: 0 0 0 0 var(--active-color, ${tokens.color['accent-primary']})00; }
        }
        
        /* REMOVED: Old sidebar-sub-link-hover - sub links now only change color */
        
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        .animate-spin { animation: spin 1s linear infinite; }
      `}</style>
    </div>
  );
});

export default Sidebar;