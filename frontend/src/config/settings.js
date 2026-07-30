// /frontend/src/config/settings.js - FINAL PRODUCTION-READY REPLACEMENT
/**
 * Central Configuration (PRODUCTION READY REPLACEMENT)
 */
// --- Core Settings ---
export const settings = {
    // FIX: Define default URL if not set in environment
    BACKEND_API_URL: process.env.REACT_APP_API_URL || '/api',
    WS_BASE_URL: process.env.REACT_APP_WS_URL,
    // CRITICAL: Ensure ORCHESTRATOR URL is available
    ORCHESTRATOR_API_URL: process.env.REACT_APP_ORCHESTRATOR_API_URL || '/api/orchestrator',

    // CRITICAL FINAL FIX: Align ROLES values to match the exact role strings used by the backend.
    ROLES: {
        HRIT_MANAGER: 'hrit_admin',
        HRBP: 'hrbp',
        MANAGER: 'manager',
        EMPLOYEE: 'employee',
        GUEST: 'guest',
        SUPER_ADMIN: 'hrit_admin', // Mapped to hrit_admin for full access in demo
    },

    // UI Theme Configuration
    HRIT_PRIMARY_COLOR: '#42A5F5', // Accent Blue
    HRBP_PRIMARY_COLOR: '#F44336', // Danger Red
};

