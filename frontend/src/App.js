// /frontend/src/App.js - FINAL PRODUCTION-READY REPLACEMENT (ROOT STRUCTURE)
import React, { memo, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate, Outlet, Link, useLocation } from 'react-router-dom';
// Contexts & Hooks
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { CustomizationProvider } from './contexts/CustomizationContext'; // CRITICAL: Ensure CustomizationProvider is imported
import { ToastProvider } from './hooks/use-toast';
// CRITICAL FIX: Changed from named import to default import: { ErrorBoundary } -> ErrorBoundary
import ErrorBoundary from './components/ErrorBoundary'; // CRITICAL: Ensure global Error Boundary is imported

// Components
import ToastContainer from './components/ToastContainer';
import ProtectedRoute from './components/ProtectedRoute';
import Sidebar from './components/Sidebar';
import Navbar from './components/Navbar'; // CRITICAL: Import stabilized Navbar
import AuthenticatedRouter from './components/AuthenticatedRouter';
import LoadingScreen from './components/LoadingScreen'; // CRITICAL: Import stabilized Loading Screen

// Pages (Lazy Loaded for Performance - Code Splitting)
const Login = React.lazy(() => import('./pages/Login'));
const AdminPortalComponent = React.lazy(() => import('./pages/AdminPortal'));
const HRITPortalComponent = React.lazy(() => import('./pages/HRITPortal'));
const HRPortalComponent = React.lazy(() => import('./pages/HRPortal'));
const ManagerPortalComponent = React.lazy(() => import('./pages/ManagerPortal'));
const EmployeePortalComponent = React.lazy(() => import('./pages/EmployeePortal'));
const UltimateOrchestratorPanelComponent = React.lazy(() => import('./pages/UltimateOrchestratorPanel'));
const DashboardComponent = React.lazy(() => import('./pages/Dashboard').then(module => ({ default: module.Dashboard })));
const UserPage = React.lazy(() => import('./pages/UserPage'));
const SocialFeed = React.lazy(() => import('./pages/SocialFeed').then(module => ({ default: module.SocialFeed })));
const AdvancedAnalyticsComponent = React.lazy(() => import('./pages/AdvancedAnalytics'));

// Config/Theme
import { theme as tokens } from './theme';
import './App.css'; // Global styles import

// --- Main Authenticated Layout Container (Nested Router Element) ---
/**
 * Renders the Floating Dock and the main content Outlet.
 */
// --- Authenticated shell: left Sidebar rail + main column (Navbar + content) ---
const MainLayoutContainer = memo(() => (
    <div style={styles.shell}>
        <Sidebar />
        <div style={styles.mainColumn}>
            <Navbar />
            <div style={styles.contentView}>
                <Suspense fallback={<LoadingScreen />}>
                    <Outlet />
                </Suspense>
            </div>
        </div>
        <style>{`
            @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
            .animate-spin { animation: spin 1s linear infinite; }
        `}</style>
    </div>
));
MainLayoutContainer.displayName = 'MainLayoutContainer';


const AppWrapper = memo(() => {
    const { isAuthenticated } = useAuth();
    return (
        <div className="App" style={styles.appContainer}>
            {isAuthenticated ? (
                <MainLayoutContainer />
            ) : (
                <div style={{ flexGrow: 1, width: '100%' }}>
                    <Outlet />
                </div>
            )}
            <ToastContainer />
        </div>
    );
});
AppWrapper.displayName = 'AppWrapper';


const styles = {
    appContainer: {
        minHeight: '100vh',
        display: 'flex',
        background: tokens.color?.['bg-900'],
        fontFamily: tokens.typography?.fontFamily,
        overflow: 'hidden',
    },
    shell: {
        display: 'flex',
        width: '100%',
        height: '100vh',
        overflow: 'hidden',
    },
    mainColumn: {
        display: 'flex',
        flexDirection: 'column',
        flexGrow: 1,
        minWidth: 0,
        height: '100vh',
        overflow: 'hidden',
    },
    contentView: {
        flexGrow: 1,
        minWidth: 0,
        overflowY: 'auto',
        overflowX: 'hidden',
    },
};


// --- MAIN APP COMPONENT (Router Definition) ---
function App() {
    return (
        // CRITICAL FIX: Wrap everything in the ErrorBoundary
        <ErrorBoundary>
            {/* CRITICAL FIX: Context order: Toast -> Auth -> Customization */}
            <ToastProvider>
                <AuthProvider>
                    <CustomizationProvider>
                        <BrowserRouter>
                            <Routes>
                                {/* 1. Public Route */}
                                <Route path="/login" element={<Suspense fallback={<LoadingScreen />}><Login /></Suspense>} />
                                
                                {/* 2. Authenticated Routes (Wrapped in AppWrapper for unified layout) */}
                                <Route element={<AppWrapper />}>
                                    {/* CRITICAL: Nested Protected Route (Handles JWT check and 403 authorization) */}
                                    <Route element={<ProtectedRoute />}>
                                        
                                        {/* AuthenticatedRouter handles the initial / and /dashboard redirect */}
                                        <Route element={<AuthenticatedRouter />}>
                                            
                                            {/* Core Portal Routes */}
                                            <Route path="/" element={<DashboardComponent />} />
                                            <Route path="/dashboard" element={<DashboardComponent />} />
                                            
                                            <Route path="/employee-portal" element={<EmployeePortalComponent />} />
                                            <Route path="/manager-portal" element={<ManagerPortalComponent />} />
                                            <Route path="/hr-portal" element={<HRPortalComponent />} />
                                            <Route path="/hrit-portal" element={<HRITPortalComponent />} />
                                            <Route path="/admin-portal" element={<AdminPortalComponent />} />
                                            
                                            <Route path="/ultimate-orchestrator" element={<UltimateOrchestratorPanelComponent />} />
                                            
                                            <Route path="/social-feed" element={<SocialFeed />} />
                                            <Route path="/user-profile" element={<UserPage />} />
                                            <Route path="/advanced-analytics" element={<AdvancedAnalyticsComponent />} />
                                        </Route>
                                    </Route>

                                    {/* 3. 404 Fallback/Redirect */}
                                    <Route path="*" element={<Navigate to="/dashboard" replace />} />
                                </Route>
                            </Routes>
                        </BrowserRouter>
                    </CustomizationProvider>
                </AuthProvider>
            </ToastProvider>
        </ErrorBoundary>
    );
}

export default App;