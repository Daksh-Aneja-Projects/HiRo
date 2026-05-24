// /frontend/src/components/MainLayout.js - FINAL PRODUCTION-READY REPLACEMENT
import React, { useMemo, memo } from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar'; // Assumed Sidebar component exists
import Navbar from './Navbar'; // Assumed Navbar component exists
import { theme as tokens } from '../theme';

/**
 * Main application layout used when authenticated.
 * It renders the Navbar, Sidebar, and the content via Outlet.
 */
const MainLayout = memo(({ isSidebarExpanded, toggleSidebar }) => {
    
    const styles = useMemo(() => ({
        appContainer: {
            minHeight: '100vh',
            display: 'flex',
            flexDirection: 'column',
            background: tokens.color?.['bg-900'],
        },
        mainContentArea: {
            display: 'flex',
            flexGrow: 1,
            position: 'relative',
            minHeight: 'calc(100vh - 60px)', // Assuming Navbar height is 60px
            overflow: 'hidden', 
        },
        contentView: (isExpanded) => ({
            flexGrow: 1,
            padding: tokens.spacing?.lg,
            minWidth: 0,
            overflowY: 'auto', 
            overflowX: 'hidden',
            transition: 'margin-left 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
        }),
    }), []);

    return (
        <div style={styles.appContainer}>
            {/* The Navbar component typically handles its own rendering and calls toggleSidebar */}
            <Navbar onSidebarToggle={toggleSidebar} /> 

            <div style={styles.mainContentArea}>
                <Sidebar isExpanded={isSidebarExpanded} toggleSidebar={toggleSidebar} />
                
                <div style={styles.contentView(isSidebarExpanded)}>
                    {/* The content for the currently matched route */}
                    <Outlet /> 
                </div>
            </div>
        </div>
    );
});

MainLayout.displayName = 'MainLayout';
export default MainLayout;