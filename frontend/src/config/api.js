// /frontend/src/config/api.js - FINAL PRODUCTION-READY API CLIENT (COMPREHENSIVE ROUTES)

/** * This is the final, production-ready "mother of all truth" API client. 
 * All functions return a raw Axios Promise. 
 */
import axios from 'axios';
import { settings } from './settings';

// --- CORE UTILITIES AND CONSTANTS ---
const getToken = () => sessionStorage.getItem('authToken'); 
// CRITICAL FIX: Use API_URL from settings consistently
export const API_URL = settings.BACKEND_API_URL || '/api'; 

// CRITICAL FIX: Use the consolidated WS path for health check
export const WS_URL = settings.WS_BASE_URL || (window.location.protocol.replace('http', 'ws') + '//' + window.location.host); 

// FIX: Corrected the streaming path to match the backend router prefix /api/streaming/agents/config/stream
export const BPCL_STREAM_PATH = `${API_URL}/streaming/agents/config/stream`; 

// EXPORTABLE TOAST FALLBACK: Reference used by interceptor
let interceptorToastFallback = (title, description, variant) => {
    console.warn(`[API INTERCEPTOR ERROR] ${title}: ${description} (Default/Dummy Toast)`);
};

// EXPORT: Setter function to link the real useToast hook later from AuthContext
export const setInterceptorToastFallback = (toastFunction) => {
    if (typeof toastFunction === 'function') {
        interceptorToastFallback = toastFunction;
    }
};

/* -------------------------------------------------------------------------- */
/* --- CORE AXIOS INSTANCE & INTERCEPTORS (Unwrapped) --- */
/* -------------------------------------------------------------------------- */
const api = axios.create({
    baseURL: API_URL,
    headers: {
        'Content-Type': 'application/json'
    },
    timeout: 30000,
});

// Calls that run the local language model finish in tens of seconds on CPU, well past
// the instance default above. Those call sites pass this explicitly.
export const LLM_TIMEOUT_MS = 300000;

api.interceptors.request.use(
    (config) => {
        try {
            const token = getToken();
            if (token && token.length > 0) {
                config.headers.Authorization = `Bearer ${token}`;
            } else {
                delete config.headers.Authorization;
            }
            config.headers['X-Request-ID'] = `frontend_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
            config.headers['X-SI-Integration'] = 'v4.0';
            config.headers['X-Client-Capabilities'] = 'streaming,websocket,simulation';
        } catch (e) {
            console.error("Token Error", e);
            delete config.headers.Authorization;
        }
        return config;
    },
    (error) => {
        console.error("Request Interceptor Error:", error);
        return Promise.reject(error);
    }
);

api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response) {
            const { status, data } = error.response;
            if (status === 401) {
                console.warn("Unauthorized access - clearing session");
                sessionStorage.removeItem('authToken');
                sessionStorage.removeItem('userData');
                interceptorToastFallback('Session Expired', 'Your session has timed out. Please log in again.', 'destructive');
            }
            if (status >= 500) {
                console.error("Server Error:", data);
            }
            if (status === 404) { 
                 console.error(`404 NOT FOUND: API endpoint ${error.config.url} not implemented on the backend.`);
            }
            if (status === 422) { 
                 console.error(`422 UNPROCESSABLE ENTITY: Invalid payload sent to ${error.config.url}.`);
            }
        } else if (error.request) {
            console.error("Network Error - No response received:", error.request);
        } else {
            console.error("Request Error:", error.message);
        }
        return Promise.reject(error);
    }
);

/* -------------------------------------------------------------------------- */
/* --- CONNECTION & HEALTH --- */
/* -------------------------------------------------------------------------- */
export const getSystemHealthStatus = () => api.get('/admin/health');

// CRITICAL FIX: Stabilized testApiConnection to prevent resource exhaustion and 429 flood
export const testApiConnection = async () => {
    let apiConnected = false;
    let wsConnected = false;
    let status = 0;
    let error = null;
    
    // 1. Test API connection using the robust Axios instance
    try {
        const response = await api.get('/health', { timeout: 5000 }); // Quick timeout
        apiConnected = response.status >= 200 && response.status < 300;
        status = response.status;
    } catch (e) {
        // Catch network errors or timeouts (Axios sets response to undefined on network failure)
        apiConnected = false;
        status = e.response?.status || 0;
        error = e.message;
    }

    // 2. Test WebSocket connection (using a simple, quick-disconnect approach)
    try {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host;
        const ws = new WebSocket(`${protocol}//${host}/ws/si-integration?client_id=health_check_${Date.now()}`); 
                     
        // CRITICAL: Use a promise with a race condition to prevent hanging
        await new Promise((resolve) => {
            const timer = setTimeout(() => { ws.close(); resolve(); }, 1000); // Max wait 1 second
            ws.onopen = () => { 
                wsConnected = true; 
                clearTimeout(timer);
                ws.close(); 
                resolve(); 
            };
            ws.onerror = () => { ws.close(); resolve(); };
        });
    } catch (wsError) {
        console.warn('WebSocket test failed (Non-critical):', wsError);
    }

    return { 
         connected: apiConnected, 
         wsConnected, 
         status, 
         error,
         url: API_URL, 
         wsUrl: WS_URL 
     };
};

/* -------------------------------------------------------------------------- */
/* --- AUTHENTICATION & BASE --- */
/* -------------------------------------------------------------------------- */
export const loginUser = (username, password) => {
    const loginData = new URLSearchParams();
    loginData.append('username', username);
    loginData.append('password', password);
    const headers = {
        'Content-Type': 'application/x-www-form-urlencoded', 
         'Accept': 'application/json'
    };
    return api.post('/auth/login', loginData.toString(), { headers, timeout: 10000 });
};
export const logoutUser = () => api.post('/auth/logout');
export const fetchMe = () => api.get('/me');
export const getTestUsers = () => api.get('/auth/test-users');

/* -------------------------------------------------------------------------- */
/* --- ORCHESTRATOR & AI COMMANDS (New & Critical Routes) --- */
/* -------------------------------------------------------------------------- */

/**
 * Executes a natural-language orchestration command.
 * Backend Route: POST /api/command/execute
 */
// LLM-backed: the local model runs on CPU and routinely needs well over the 30s
// instance default, so this call carries its own timeout.
export const runOrchestrationCommand = (prompt, userContext) => api.post('/command/execute', {
    prompt,
    user_id: userContext?.user_id || userContext?.username || 'user',
}, { timeout: LLM_TIMEOUT_MS });

/**
 * Fetches the stored result of a previously executed orchestration command.
 * Backend Route: GET /api/command/status/{result_id}
 */
export const getOrchestrationResultStatus = (resultId) => api.get(`/command/status/${encodeURIComponent(resultId)}`);

/** Recent orchestrator command history. Backend Route: GET /api/command/history */
export const getCommandHistory = (limit = 50) => api.get('/command/history', { params: { limit } });

export const executeOrchestratorCommand = (payload) => api.post('/command/execute', payload);
export const aggregateMetrics = (payload) => api.post('/advanced-analytics/metrics/aggregate', payload);
export const legacyAiCommand = (payload) => api.post('/ai/command', payload);
export const getProcessExecutionHistory = (processId) => api.get(`/orchestrator/history/${encodeURIComponent(processId)}`);
export const getOrchestratorDashboardData = () => api.get('/orchestrator/dashboard');


/* -------------------------------------------------------------------------- */
/* --- DIGITAL TWIN CONTRACTS (New & Critical Routes) --- */
/* -------------------------------------------------------------------------- */

/**
 * Sends a message to a reportee's digital twin and returns the twin's AI reply.
 * Backend Route: POST /api/ai/twin/message/{reportee_id}
 */
export const sendDigitalTwinMessage = (reporteeId, message) =>
    api.post(`/ai/twin/message/${encodeURIComponent(reporteeId)}`, { message });

/**
 * Fetches the persisted conversation with a reportee's digital twin.
 * Backend Route: GET /api/ai/twin/history/{user_id}
 */
export const getDigitalTwinHistory = (userId) => api.get(`/ai/twin/history/${encodeURIComponent(userId)}`);


export const getDigitalTwinXai = () => api.get('/talent-exp/digital-twin/xai');
export const executeDTLACommand = (commandType, data) => api.post('/data/dtla/command', { command_type: commandType, data });
export const synthesizeLearningCurriculum = (employeeId, targetRole = null) => api.post(`/talent-exp/learning/synthesize/${encodeURIComponent(employeeId)}`, { target_role: targetRole });
export const getLearningModules = () => api.get('/talent-exp/learning-modules');


/* -------------------------------------------------------------------------- */
/* SI INTEGRATION: STREAMING & WEB SOCKET ENDPOINTS (Unwrapped) */
/* -------------------------------------------------------------------------- */
export const createTelemetryWebSocket = (clientId = 'dashboard') => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    // CRITICAL FIX: Use the consolidated WS path for Nginx proxy pass
    const ws = new WebSocket(`${protocol}//${host}/ws/si-integration?client_id=${clientId}`); 
     
    // Return the raw WebSocket object, allowing the useAgentWebsocket hook to manage events.
    return ws;
};
// This function needs to be kept as is for backward compatibility or refactor
export const streamAgentConfiguration = (nlPrompt, onChunk, onComplete, onError) => {
    // CRITICAL FIX: Use the correct BPCL_STREAM_PATH defined above
    const eventSource = new EventSource(`${BPCL_STREAM_PATH}?nl_prompt=${encodeURIComponent(nlPrompt)}`);
    eventSource.onmessage = (event) => {
        let isComplete = false;
        try {
            const data = JSON.parse(event.data);
            if (data.status === 'completed' || data.final_bpcl) {
                isComplete = true;
            }
        } catch (e) { /* Handle raw chunk data */ }

        onChunk?.(event.data);
        if (isComplete) {
            onComplete?.();
            eventSource.close();
        }
    };
    eventSource.onerror = (error) => {
        console.error('Streaming error:', error);
        onError?.(error);
        eventSource.close();
    };
    return eventSource;
};

/* -------------------------------------------------------------------------- */
/* --- SI INTEGRATION: DATA & METRICS (Live) --- */
/* -------------------------------------------------------------------------- */
export const runSimulation = (employeeId, adjustments) => api.post('/simulation/run', { employee_id: employeeId, synthetic_adjustments: adjustments, simulation_type: 'what_if', include_recommendations: true });
export const autoResolveAudit = (auditId, failedTransaction, policyText) => api.post(`/remediation/audit/${encodeURIComponent(auditId)}/auto-resolve`, { failed_transaction: failedTransaction, policy_text: policyText, auto_apply: false });
export const remediateAuditLog = (payload) => api.post('/remediation/audit-fail', payload);
export const getSimulationHistory = (employeeId, limit = 10) => api.get(`/simulation/history/${encodeURIComponent(employeeId)}?limit=${limit}`);
export const getRemediationHistory = (auditId) => api.get(`/remediation/history/${encodeURIComponent(auditId)}`);
export const getCurrentMetrics = () => api.get('/telemetry/metrics/live');
export const getAgentActivity = (timeWindowMinutes = 60) => api.get(`/telemetry/agents/activity?time_window_minutes=${timeWindowMinutes}`);
// CRITICAL FIX: Export the stream function correctly
export const streamSelfCorrectingAgent = (nlPrompt, onChunk, onComplete, onError) => streamAgentConfiguration(nlPrompt, onChunk, onComplete, onError);
export const streamAgentConfig = (prompt, onChunk, onComplete, onError) => streamAgentConfiguration(prompt, onChunk, onComplete, onError);
export const getCurrentTelemetry = () => api.get('/telemetry/metrics/live');

/* -------------------------------------------------------------------------- */
/* --- POLICY & GOVERNANCE (Live) --- */
/* -------------------------------------------------------------------------- */
export const getActivePolicy = (policyId) => api.get(`/policy/${encodeURIComponent(policyId)}/active`);
export const getPolicyHistory = (policyId) => api.get(`/policy/${encodeURIComponent(policyId)}/history`);
export const listPolicies = () => api.get('/policy/list');
export const createPolicyDraft = (policyId, data) => api.post(`/policy/${encodeURIComponent(policyId)}/versions`, data);
export const updatePolicyDraftContent = (versionId, data) => api.put(`/policy/versions/${encodeURIComponent(versionId)}/content`, data);
export const submitPolicyForApproval = (versionId, approvers) => api.post(`/policy/versions/${encodeURIComponent(versionId)}/submit`, { approvers });
export const processPolicyApproval = (requestId, action) => api.post(`/policy/approvals/${encodeURIComponent(requestId)}`, action);
export const activateApprovedPolicy = (versionId) => api.post(`/policy/versions/${encodeURIComponent(versionId)}/activate`);
export const manualPolicyRollback = (policyId, targetVersionId) => api.post(`/policy/${encodeURIComponent(policyId)}/rollback`, { target_version_id: targetVersionId });
export const commitToPolicyLedger = (data) => api.post('/policy/ledger/commit', data);
export const getActiveProposals = () => api.get('/dao/proposals/active');
export const castVote = (proposalId, vote, votingPower) => api.post('/dao/vote', { proposal_id: proposalId, vote, voting_power: votingPower });
export const getGovernanceDashboardData = () => api.get('/dao/dashboard');
export const getComplianceDashboardData = () => api.get('/compliance/dashboard');
export const monitorRegulatoryFeeds = (jurisdictions) => api.post('/compliance/monitor_feeds', { jurisdictions });
export const deployBPCLFromPrompt = (policyId, nlPrompt) => api.post(`/policy/deploy-bpcl-from-prompt/${encodeURIComponent(policyId)}`, { nl_prompt: nlPrompt });
export const triggerPolicyImplementation = (versionId, initiatorId, policyId) => api.post('/orchestrator/implement-policy', { version_id: versionId, initiator_id: initiatorId, policy_id: policyId });
export const processAgentFinalApproval = (taskId, projectId, approved, comments = "") => api.post('/admin/agent/deploy/final-approval', { task_id: taskId, project_id: projectId, approved: approved, comments: comments });

/* -------------------------------------------------------------------------- */
/* --- HR MODULES (Live) --- */
/* -------------------------------------------------------------------------- */
export const getEmployeeCompensation = (employeeId) => api.get(`/hr/comp/${encodeURIComponent(employeeId)}`);
export const updateEmployeeCompensation = (data) => api.post('/hr/comp/update', data);
export const getEmployeePerformance = (employeeId) => api.get(`/hr/performance/${encodeURIComponent(employeeId)}`);
export const getTeamPerformance = (params = {}) => api.get('/hr/performance/team-trend', { params });
export const getTimesheets = (params = {}) => api.get('/hr/timesheets', { params });
export const submitTimesheet = (data) => api.post('/hr/timesheets', data);
export const runTimesheetPreCheck = (data) => api.post('/hr/timesheets/pre-check', data);
export const getLeaveBalance = () => api.get('/hr/leave/balance');
export const getLeaveHistory = (params = {}) => api.get('/hr/leave/requests', { params });
export const submitPerformanceReview = (reviewData) => api.post('/hr/performance/review', reviewData);
export const getCareerPath = (employeeId) => api.get(`/hr/career/path/${encodeURIComponent(employeeId)}`);
export const getPeerFeedback = (employeeId) => api.get(`/hr/feedback/peer/${encodeURIComponent(employeeId)}`);
export const getSkillsProfile = () => api.get('/hr/profile/skills');
export const saveSkillsProfile = (data) => api.post('/hr/profile/skills', data);
export const getEmployeePayslips = (params = {}) => api.get('/hr/payslips', { params });
export const getEmployeeBenefits = () => api.get('/hr/benefits');
export const downloadPayslip = (fileKey) => api.get(`/hr/payslips/download/${encodeURIComponent(fileKey)}`, { responseType: 'blob' });
export const submitFeedback = (feedback) => api.post('/hr/feedback', { feedback });
export const getRetentionPreference = () => api.get('/hr/retention/preference');
export const saveRetentionPreference = (preference) => api.post('/hr/retention/preference', { preference });
export const submitExpense = (data, receiptFile) => {
    const formData = new FormData();
    formData.append('expense_data', JSON.stringify(data));
    if (receiptFile) formData.append('receipt', receiptFile);
    return api.post('/hr/expenses', formData, { 
         headers: { 
            'Content-Type': 'multipart/form-data' 
         }
    });
};
export const getExpenses = (params = {}) => api.get('/hr/expenses', { params });
export const decideExpense = (expenseId, approved, comments = '') =>
    api.post(`/hr/expenses/${encodeURIComponent(expenseId)}/decision`, { approved, comments });
export const getPendingTimesheets = (limit = 100) => api.get('/hr/timesheets/pending', { params: { limit } });
export const decideTimesheet = (timesheetId, approved, comments = '') =>
    api.post(`/hr/timesheets/${encodeURIComponent(timesheetId)}/decision`, { approved, comments });
export const createRequisition = (data) => api.post('/mss/hiring/requisitions', data);
export const assignHRSDTicket = (ticketId, assignee) =>
    api.put(`/hrsd/tickets/${encodeURIComponent(ticketId)}/assign`, { assignee });
export const getAuditTrace = (params = {}) => api.get('/hr/audit/trace', { params });
export const getTeamPerformanceTrend = () => api.get('/hr/performance/team-trend');
export const scanExpenseReceipt = (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/hr/expenses/ocr-scan', formData, { 
         headers: { 
            'Content-Type': 'multipart/form-data' 
         } 
     });
};
export const uploadOffboardingFile = (formData) => api.post('/hr/offboarding/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } });
export const submitOffboardingKnowledge = (data) => api.post('/hr/offboarding/knowledge', data);
export const getEmployeeProfile = (employeeId) => api.get(`/hr/profile/${encodeURIComponent(employeeId)}`);
export const updateEmployeeProfile = (employeeId, data) => api.put(`/hr/profile/${encodeURIComponent(employeeId)}`, data);
export const getDocumentDetails = (documentId) => api.get(`/hr/doc/details/${encodeURIComponent(documentId)}`);
export const deleteEmployeeDocument = (documentId) => api.delete(`/hr/doc/delete/${encodeURIComponent(documentId)}`);
export const uploadEmployeeDocument = (employeeId, docType, file) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post(`/hr/doc/ingestion/${encodeURIComponent(employeeId)}/${encodeURIComponent(docType)}`, formData, { 
         headers: { 
            'Content-Type': 'multipart/form-data' 
         } 
     });
};
export const getEmployeeDocuments = () => api.get('/hr/doc/employee-documents');

/* -------------------------------------------------------------------------- */
/* --- ESS (Employee Self-Service) (Live) --- */
/* -------------------------------------------------------------------------- */
export const getEmployeeDashboard = (employeeId) => api.get(`/ess/dashboard/${encodeURIComponent(employeeId)}`);
export const submitLeaveRequest = (data) => api.post('/ess/leave/submit', data);
export const getPersonalInfo = () => api.get('/ess/profile/personal-info');
export const submitPersonalInfoUpdate = (payload) => api.post('/ess/profile/update-request', payload);
export const recordConsentChange = (consentData) => api.post('/pii/update_consent', consentData);
// Decrypts a specific ciphertext token (both are written to the PII access log).
export const getUnmaskedPII = (token, reason = 'Token reveal requested') =>
    api.post('/pii/unmask', { token, reason });
// Employee-facing: decrypts the caller's OWN protected fields server-side.
// A browser never holds a ciphertext token, so this is what the portal uses.
export const revealOwnPII = (reason = 'Employee viewed their own protected fields') =>
    api.post('/pii/reveal-self', { reason });
export const checkUserConsent = (purposeId) => api.get(`/pii/check_consent?purpose_id=${encodeURIComponent(purposeId)}`);

/* -------------------------------------------------------------------------- */
/* --- MSS (Manager Self-Service) (Live) --- */
/* -------------------------------------------------------------------------- */
export const getManagerDashboardData = () => api.get('/admin/dashboard'); 
export const getTeamRoster = (params = {}) => api.get('/mss/team/roster', { params });
export const getRequisitions = (params = {}) => api.get('/mss/hiring/requisitions', { params });
export const getManagerTeamData = (managerId) => api.get(`/mss/team/${encodeURIComponent(managerId)}`);
export const approveLeaveRequest = (requestId, approved, comments = "") => api.post('/mss/leave/approve', { request_id: requestId, approved, comments });
export const getApprovalQueue = () => api.get('/mss/approvals/queue');
export const getHRITApprovalQueue = () => api.get('/mss/approvals/hrit-queue');
export const actionApproval = (payload) => api.post('/mss/approvals/action', payload);

/* -------------------------------------------------------------------------- */
/* --- HRSD (HR Service Delivery) (Live) --- */
/* -------------------------------------------------------------------------- */
export const createHRSDTicket = (subject, description, employeeId) => api.post('/hrsd/tickets', { subject, description, employee_id: employeeId });
export const resolveHRSDTicket = (ticketId, resolutionSummary) => api.put(`/hrsd/tickets/${encodeURIComponent(ticketId)}/resolve`, { resolution_summary: resolutionSummary });
export const getHRSDMonitoringOverview = () => api.get('/hrsd/monitoring/overview');
export const syncServiceNow = () => api.post('/hrsd/integrations/snow/sync');
export const getHRSDTickets = (params = {}) => api.get('/hrsd/tickets', { params }); 

/* -------------------------------------------------------------------------- */
/* --- ADMIN (Live) --- */
/* -------------------------------------------------------------------------- */
// Both plan their work with the local model, so both need the long LLM timeout.
export const createNewAIAgent = (data) => api.post('/admin/agent/create', data, { timeout: LLM_TIMEOUT_MS });
export const executeRLFFCommand = (command) => api.post('/admin/rlff/command', { command }, { timeout: LLM_TIMEOUT_MS });
export const getAdminDashboardData = () => api.get('/admin/dashboard');
export const getAllUsers = (params = {}) => api.get('/admin/users', { params });
export const createUserAccount = (userData) => api.post('/admin/users/create', userData);
export const updateUserRole = (username, role) => api.put(`/admin/users/${encodeURIComponent(username)}/role`, { role });
export const deleteUser = (username) => api.delete(`/admin/users/${encodeURIComponent(username)}`);
export const runSystemIntegrityCheck = (service) => api.post('/admin/system/integrity-check', { service });
export const getAnnouncements = (params = {}) => api.get('/admin/announcement', { params });
export const createAnnouncement = (data) => api.post('/admin/announcement', data);
export const clearSystemCache = () => api.post('/admin/system/cache/clear');
export const getMessageBusStatus = () => api.get('/admin/system/message-bus/status');
export const rotateAgentKeys = () => api.post('/admin/security/rotate-keys');
export const resetAllData = () => api.post('/admin/system/reset-all-data');
export const getHRITPortalData = () => api.get('/admin/dashboard');
export const resetHRITData = () => api.post('/admin/hrit/system/reset-data'); 
export const triggerLegacyDataMigration = (instructions) => api.post('/admin/data/migrate-legacy-chunk', instructions);

/* -------------------------------------------------------------------------- */
/* --- DATA & XAI (Live) --- */
/* -------------------------------------------------------------------------- */
export const getXAIExplanation = (modelName, predictionInput) => api.post('/data/xai/explain', { model_name: modelName, prediction_input: predictionInput });
export const getModelAuditLog = (modelName, limit = 10) => api.get(`/data/xai/audit/${encodeURIComponent(modelName)}?limit=${limit}`);
export const submitDataCorrection = (dataId, corrections) => api.post(`/data/correction/${encodeURIComponent(dataId)}`, { corrections });
export const getActiveAIProvider = () => api.get('/ai/provider/config');
export const setAIProvider = (provider) => api.post('/ai/provider/switch', { provider });
export const runPolicyScan = (policyContent, versionId) => api.post('/policy/scan-policy-for-deployment', { policy_content: policyContent, version_id: versionId });
export const generateText = (prompt, systemInstruction) => api.post('/ai/generate', { prompt, system_instruction: systemInstruction });
export const generateBPMN = (description, domain) => api.post('/ai/generate-bpmn', { description, domain });
export const saveGeneratedWorkflow = (workflowData) => api.post('/ai/workflow/save', workflowData);
export const generateEmbedding = (text) => api.post('/ai/embedding', { text });
export const getAiModels = () => api.get('/ai/models');
export const tokenizePII = (value) => api.post('/pii/tokenize', { value });
export const updateUserConsent = (data) => api.post('/pii/update_consent', data);

/* -------------------------------------------------------------------------- */
/* --- WFP (Workforce Planning) (Live) --- */
/* -------------------------------------------------------------------------- */
export const getWFPProjections = () => api.get('/wfp/projections');
export const predictAttritionRisk = (employeeData) => api.post('/wfp/predict_attrition', employeeData);

/* -------------------------------------------------------------------------- */
/* --- TA (Talent Acquisition) (Live) --- */
/* -------------------------------------------------------------------------- */
export const getTalentPoolSnapshot = () => api.get('/ta/snapshot');
export const predictTAPipelineRisk = (scenarioData) => api.post('/ta/predict_risk', { scenario_data: scenarioData });
export const generateJobDescription = (data) => api.post('/talent/job-description/generate', data);
export const generateJDDraft = (data) => api.post('/talent/job-description/generate-draft', data);
export const getPredictiveRisk = (scenarioData) => predictTAPipelineRisk(scenarioData);

/* -------------------------------------------------------------------------- */
/* --- DEVOPS (Development Operations) (Live) --- */
/* -------------------------------------------------------------------------- */
export const testPQCEncrypt = (plaintext) => api.post('/dev/pqc/encrypt', { plaintext });
export const testPQCDecrypt = (ciphertext) => api.post('/dev/pqc/decrypt', { ciphertext });
export const generatePolicyExecutionTree = (policyVersionId) => api.post('/dev/policy/generate_tree', { policy_version_id: policyVersionId });
export const executePolicyCheckedCommand = (data) => api.post('/dev/policy/checked-command', data);
export const sandboxDeploy = (data) => api.post('/dev/sandbox/deploy', data);
export const securityScanBpcl = (code) => api.post('/dev/policy/scan', { code });

/* -------------------------------------------------------------------------- */
/* --- UTILITY & COLLABORATION (Live) --- */
/* -------------------------------------------------------------------------- */
export const getAdvancedAnalytics = (params = {}) => api.get('/advanced-analytics/metrics', { params });
export const getAnalyticsCharts = () => api.get('/advanced-analytics/charts');
export const uploadIngestionFile = (file) => { 
     const fd = new FormData(); 
     fd.append('file', file); 
     return api.post('/ingestion/upload', fd, { 
         headers: { 
            'Content-Type': 'multipart/form-data' 
         } 
     });
 };
export const getIngestionJobs = (limit = 20) => api.get('/ingestion/jobs', { params: { limit } });
export const getSocialFeed = () => api.get('/social/feed');
export const postSocialPost = (data) => api.post('/social/posts', data);
export const getInnovationIdeas = () => api.get('/innovation/ideas');
export const voteInnovationIdea = (payload) => api.post('/innovation/ideas/vote', payload);
export const createActivitySite = (activityDetails) => api.post(`/social/activity`, activityDetails);
export const getJoinableActivities = () => api.get(`/social/activities`);
export const createPrivateChatLink = (details) => api.post(`/social/chat-link`, details);
export const giveRecognitionStar = (userId, reason) => api.post(`/recognition/star/${encodeURIComponent(userId)}`, { reason });
export const getRecognitionLeaderboard = () => api.get(`/recognition/leaderboard`);

/* -------------------------------------------------------------------------- */
/* --- GENERIC UTILITIES (Unwrapped) --- */
/* -------------------------------------------------------------------------- */
export const get = (url, config = {}) => api.get(url, config);
export const post = (url, data, config = {}) => api.post(url, data, config);
export const put = (url, data, config = {}) => api.put(url, data, config);
export const del = (url, config = {}) => api.delete(url, config);
export const createCancelToken = () => { return axios.CancelToken.source(); };

export default api;

// =========================================================================================================
// FINAL EXPORTS AND ALIASES (Consolidated, No Duplicates)
// =========================================================================================================
export const getHealthStatus = getSystemHealthStatus;
export const getUserData = fetchMe;
export const submitPolicyDraft = createPolicyDraft;
export const policyLedgerCommit = commitToPolicyLedger;
export const getDAOProposals = getActiveProposals;
export const voteOnProposal = castVote;
export const getLeaveRequests = getLeaveHistory;
export const submitExpenseClaim = submitExpense;
export const runOcrScan = scanExpenseReceipt;
export const getEmployeeDashboardData = getEmployeeDashboard;
export const getEmployeeData = getEmployeeDashboard;
export const getPortalData = getManagerDashboardData;
export const getEmployees = getTeamRoster;
export const getApprovalsQueue = getApprovalQueue;
export const processApproval = actionApproval;
export const createNewAgent = createNewAIAgent;
export const deployAgentConfig = createNewAIAgent;
export const getUsers = getAllUsers;
export const createUser = createUserAccount;
export const updateUser = updateUserRole;
export const postAnnouncement = createAnnouncement;
export const triggerPQCKeyRotation = rotateAgentKeys;
export const triggerHardPurge = resetAllData;
export const getHRITDashboardData = getHRITPortalData;
export const getSystemHealth = getSystemHealthStatus;
export const runAttritionSimulation = runSimulation;
export const scanBPCL = securityScanBpcl;
export const generateBPCL = generateBPMN;
export const ingestDataFile = uploadIngestionFile;
export const getGovernanceData = getGovernanceDashboardData;
export const getKernelMetrics = getCurrentTelemetry;
export const getServiceStatus = getSystemHealthStatus;
export const getAutonomousHealingLog = (auditId) => getRemediationHistory(auditId || 'SYSTEM_LOG');
export const getRLFFMonitorStatus = getAdminDashboardData;
export const getServiceNowHealth = getHRSDMonitoringOverview;
export const getFinancialForecast = () => aggregateMetrics({ metric_type: 'financial_impact', query: 'Q1 Payroll Delta' });
export const getPredictiveRiskAlias = getPredictiveRisk;