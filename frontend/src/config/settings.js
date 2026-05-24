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

// --- Data Structures (Initialized as empty objects/arrays for import safety) ---
// These exports prevent import errors in existing files
export const MOCK_USER_DATA = {};
export const MOCK_EMPLOYEES = [];
export const MOCK_HRSD_TICKETS = [];
export const MOCK_HEALTH_STATUS = {};
export const MOCK_LEAVE_BALANCE = {};
export const MOCK_LEAVE_HISTORY = [];
export const MOCK_APPROVALS_QUEUE = {};
export const MOCK_SIMULATION_RESULT = {};
export const MOCK_GOVERNANCE_DATA = {};
export const MOCK_HEALING_LOG = [];
export const MOCK_RLFF_FEEDBACK = {};
export const MOCK_SERVICENOW_HEALTH = {};
export const MOCK_HRIT_TELEMETRY = {};