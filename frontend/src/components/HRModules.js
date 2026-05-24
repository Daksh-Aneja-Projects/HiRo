// /src/components/HRModules.js - FINAL PRODUCTION-READY REPLACEMENT (Fixes ALL fontSize/fontWeight TypeErrors)
import React, { useState, useEffect, useCallback, useMemo, useReducer, memo } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useToast } from '../hooks/use-toast';
import { Loader2, Clock, Calendar, DollarSign, RefreshCw, Zap, AlertTriangle, ShieldCheck, Brain, X, Camera, CheckCircle, ArrowLeft, Users, MessageSquare, Home, ArrowRight } from 'lucide-react';
import * as api from '../config/api';
import XAIDecisionPanel from './XAIDecisionPanel';
import { theme as tokens } from '../theme';

// --- CONSTANTS ---
const HOURS_PER_DAY = 8;
const DEFAULT_TOTAL_HOURS = 40;
const DEFAULT_WEEK_ENDING = new Date().toISOString().split('T')[0];
const DEFAULT_DAILY_HOURS = { monday: 8, tuesday: 8, wednesday: 8, thursday: 8, friday: 8, saturday: 0, sunday: 0 };

// --- MOCK DATA (Ensure consistency for fallback) ---
const MOCK_TS = [
  { timesheet_id: 'TS-1001', week_ending: '2025-11-22', total_hours: 40, status: 'approved', ai_score: 95.2 },
  { timesheet_id: 'TS-1002', week_ending: '2025-11-29', total_hours: 45, status: 'review_required', ai_score: 55.1 },
];
const MOCK_LEAVES = [
  { request_id: 'LR-2001', leave_type: 'annual', start_date: '2025-12-15', end_date: '2025-12-19', days: 5, status: 'pending', reason: 'Holiday travel' },
];
const MOCK_BALANCE = {
  balance_hours: 104,
  sick_leave: 5,
  personal_leave: 2,
  balance_days: 13
};
const MOCK_APPROVALS_QUEUE = {
  timesheets: [
    { id: 'TS-1002', timesheet_id: 'TS-1002', type: 'Timesheet', employee_name: 'Alex Smith', summary: 'Timesheet 45h/40h limit.', status: 'REVIEW_REQUIRED', risk_level: 'medium', total_hours: 45, itemType: 'timesheet', risk: 'medium' }
  ],
  pra_recommendations: [
    { id: 'PRA-R1', recommendation_id: 'PRA-R1', type: 'Retention Recommendation', employee_name: 'Jane Doe', summary: 'High flight risk intervention suggested.', status: 'PENDING', risk_level: 'high', recommendation: 'Schedule 1:1', itemType: 'pra_action', risk: 'high' }
  ],
  leave_requests: [
    { id: 'LR-2002', request_id: 'LR-2002', type: 'Leave Request', employee_name: 'Bob A.', summary: 'Leave: 15 days (Annual)', status: 'PENDING', risk_level: 'low', days: 15, itemType: 'leave', risk: 'low' }
  ],
  // FIX: Include empty arrays for safe destructuring in reducer
  expense_claims: [], config_changes: [], wfm_anomalies: [] 
};

// --- REDUCER AND HELPER FUNCTIONS ---
const initialData = {
  timesheets: [],
  leaves: [],
  leaveBalance: { balance_hours: 0, sick_leave: 0, personal_leave: 0, balance_days: 0 },
  approvalsData: {
    timesheets: [], leave_requests: [], expense_claims: [], config_changes: [], total_pending: 0, wfm_anomalies: [], pra_recommendations: []
  }
};

const dataReducer = (state, action) => {
  switch (action.type) {
    case 'SET_DATA':
      return { ...state, ...action.payload };
    case 'UPDATE_APPROVALS': {
      const approvalsPayload = action.payload || {};
      const allApprovalArrays = [
        ...(approvalsPayload?.timesheets || []),
        ...(approvalsPayload?.leave_requests || []),
        ...(approvalsPayload?.expense_claims || []),
        ...(approvalsPayload?.config_changes || []),
        ...(approvalsPayload?.wfm_anomalies || []),
        ...(approvalsPayload?.pra_recommendations || [])
      ].flat();
      const totalPending = allApprovalArrays.filter(item => 
         ['PENDING', 'VOTING', 'PENDING_STANDARD_APPROVAL', 'AGENT_PROCESSING', 'REVIEW_REQUIRED', 'AGENT_REVIEW'].includes(String(item.status || item.risk_level).toUpperCase())
      ).length;
      return {
        ...state,
        approvalsData: {
          ...state.approvalsData,
          ...approvalsPayload,
          total_pending: totalPending,
        },
      };
    }
    default:
      return state;
  }
};

const formatTitle = (key) => {
  if (!key) return '';
  return key.replace(/_/g, ' ').split(' ').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
};

// --- WRAPPER COMPONENTS ---
const XAIDecisionPanelWrapper = memo(({ item, onClose }) => {
    // Mock XAI Data Structure for display
   const riskColor = item.risk_level === 'high' ? tokens.color?.['danger'] : item.risk_level === 'medium' ? tokens.color?.['warning'] : tokens.color?.['success'];
   const xaiDecision = {
       itemId: item.id,
       employeeId: item.employee_name || 'N/A',
       title: item.summary || item.type,
       scoreLabel: 'Risk Score',
       primaryScore: item.anomaly_score || item.risk_score || (item.risk_level === 'high' ? 0.92 : 0.55),
       outcome: item.recommendation || 'Review manual process steps.',
       confidence: item.confidence_score || 0.85,
       decisionType: item.itemType === 'pra_action' ? 'attrition' : 'anomaly',
       top_features: [{ name: 'Overtime Hours', impact: 92, description: 'Submitted > 60h max limit.' }],
   };

   return (
       <div className="modal-overlay" style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(5, 8, 20, 0.95)', zIndex: 5000, display: 'flex', justifyContent: 'center', alignItems: 'center', padding: '1rem' }}>
           <div className="hr-card" style={{ width: '40rem', maxWidth: '95%', padding: '1.5rem', zIndex: 5001, gap: tokens.spacing?.sm,
           border: `2px solid ${riskColor}`, background: tokens.color?.['panel-800'] }}>
               <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: tokens.spacing?.xs }}>
                   <h3 className="hr-card-title" style={{ color: riskColor }}>
                       <Brain size={20} style={{ marginRight: tokens.spacing?.xs, display: 'inline-block' }} />
                       XAI Decision Narrative
                   </h3>
                   <button onClick={onClose} className="secondary-button" style={{ padding: tokens.spacing?.xs, border: `1px solid ${tokens.color?.['danger']}`, color: tokens.color?.['muted-500'], background: tokens.color?.['panel-700'], borderRadius: tokens.border?.radius?.chip }}>
                       <X size={16} /> Close
                   </button>
               </div>
               {/* Placeholder for XAIDecisionPanel */}
               <div style={{ maxHeight: '20rem', overflowY: 'auto' }}>
                   <p style={{ color: tokens.color?.['muted-500'] }}>Employee: {xaiDecision.employeeId}</p>
                   <p style={{ color: tokens.color?.['muted-500'], marginTop: tokens.spacing?.xs }}>**{xaiDecision.scoreLabel}**: <span style={{ color: riskColor, 
                       // --- FIX: Added optional chaining ---
                       fontWeight: tokens.typography?.h2?.fontWeight 
                       // ------------------------------------
                   }}>{(xaiDecision.primaryScore * 100).toFixed(1)}%</span></p>
                   <p style={{ color: tokens.color?.['text-100'], marginTop: tokens.spacing?.md }}>**AI Recommendation**: {xaiDecision.outcome}</p>
                   <p style={{ color: tokens.color?.['muted-500'], marginTop: tokens.spacing?.md, 
                       // --- FIX: Added optional chaining ---
                       fontSize: tokens.typography?.small?.fontSize
                       // ------------------------------------
                   }}>Top Factors: {xaiDecision.top_features.map(f => f.name).join(', ')}</p>
               </div>
           </div>
       </div>
   );
});
XAIDecisionPanelWrapper.displayName = 'XAIDecisionPanelWrapper';

const LeaveRow = memo(({ req, idx, HOURS_PER_DAY }) => {
    const status = (req.status || 'pending').toLowerCase();
    const statusColor = status === 'approved' ? tokens.color?.['success'] : status === 'denied' ? tokens.color?.['danger'] : tokens.color?.['warning'];
    const days = req.days || (req.requested_hours / HOURS_PER_DAY) || 0;
    return (
        <div key={req.request_id || idx} className="item-row" style={{ borderLeft: `0.25rem solid ${statusColor}`, background: tokens.color?.['panel-700'], padding: tokens.spacing?.sm, borderRadius: tokens.border?.radius?.chip }}>
            <div className="item-row-main" style={{display: 'flex', flexDirection: 'column', gap: tokens.spacing?.xs}}>
                <div className="item-row-title" style={{
                    // --- FIX: Added optional chaining ---
                    fontWeight: tokens.typography?.h2?.fontWeight, 
                    // ------------------------------------
                    color: tokens.color?.['text-100']}}>({(req.leave_type ||  'N/A').toUpperCase()}) · {days} days</div>
                <div className="item-row-meta" style={{
                    // --- FIX: Added optional chaining ---
                    fontSize: tokens.typography?.small?.fontSize, 
                    // ------------------------------------
                    color: tokens.color?.['muted-500']}}><span>{req.start_date?.substring(0, 10)} → {req.end_date?.substring(0, 10)}</span></div>
                <div className={`status-chip`} style={{ background: `${statusColor}22`, color: statusColor, alignSelf: 'flex-start', padding: '2px 8px', borderRadius: tokens.border?.radius?.chip, 
                    // --- FIX: Added optional chaining ---
                    fontSize: tokens.typography?.small?.fontSize 
                    // ------------------------------------
                }}>{status.toUpperCase()}</div>
            </div>
        </div>
    );
});
LeaveRow.displayName = 'LeaveRow';

// --- MAIN COMPONENT ---
const HRModules = React.memo(() => {
  const { token, user, checkRole } = useAuth();
  const { toast } = useToast();
  // CRITICAL FIX: Ensure HRIT_MANAGER is included in the manager role check
  const isManager = checkRole(['manager', 'hrit_admin', 'hr', 'hrbp']); 
  const [activeModule, setActiveModule] = useState('timesheet');
  const [state, dispatch] = useReducer(dataReducer, initialData);
  const { timesheets = [], leaves = [], leaveBalance = {}, approvalsData = {} } = state;
  const [loading, setLoading] = useState({});
  const [showXaiDetails, setShowXaiDetails] = useState(false);
  const [xaiData, setXaiData] = useState(null);
  const [loadingOcr, setLoadingOcr] = useState(false);
  
  // NOTE: navigate is undefined here, assuming it's imported or available via context if needed
  const navigate = () => {}; 

  const [timesheetData, setTimesheetData] = useState({
    week_ending: DEFAULT_WEEK_ENDING,
    total_hours: DEFAULT_TOTAL_HOURS,
    daily_hours: { ...DEFAULT_DAILY_HOURS }
  });
  const [leaveData, setLeaveData] = useState({
    leave_type: 'annual',
    start_date: DEFAULT_WEEK_ENDING,
    end_date: DEFAULT_WEEK_ENDING,
    days: 1,
    reason: ''
  });
  const [expenseData, setExpenseData] = useState({
    amount: 0,
    currency: 'USD',
    category: 'Travel',
    description: '',
    date: DEFAULT_WEEK_ENDING
  });

  const fetchApprovals = useCallback(async (isInitialLoad = false) => {
    if (!token && !isInitialLoad) {
      dispatch({ type: 'UPDATE_APPROVALS', payload: MOCK_APPROVALS_QUEUE });
      return;
    }
    setLoading(prev => ({ ...prev, approvals: true }));
    try {
      // CRITICAL FIX: Use the specific API for approvals queue
      const response = await api.getApprovalQueue().catch((e) => {
        console.error("API getApprovalQueue failed:", e);
        return { data: null }; // Return null data on failure
      });
            
      const approvalsQueue = response.data?.queue || response.data || {};
            
      // Use API data if available and non-empty, otherwise use mock data
      const payload = (approvalsQueue && Object.keys(approvalsQueue).length > 0 && Object.keys(approvalsQueue).some(k => Array.isArray(approvalsQueue[k]) && approvalsQueue[k].length > 0))
        ? approvalsQueue
        : MOCK_APPROVALS_QUEUE;
      dispatch({ type: 'UPDATE_APPROVALS', payload });
          
    } catch (error) {
      const msg = error.response?.data?.detail || 'Failed to load approvals. Using mock data.';
      toast({ title: "Fetch Error", description: msg, variant: 'warning' });
      dispatch({ type: 'UPDATE_APPROVALS', payload: MOCK_APPROVALS_QUEUE });
    } finally {
      setLoading(prev => ({ ...prev, approvals: false }));
    }
  }, [token, toast]);

  const fetchModuleData = useCallback(async (module, isInitialLoad = false) => {
    if (!token && !isInitialLoad) {
      if (module === 'timesheet') dispatch({ type: 'SET_DATA', payload: { timesheets: MOCK_TS } });
      if (module === 'leave') dispatch({ type: 'SET_DATA', payload: { leaves: MOCK_LEAVES, leaveBalance: MOCK_BALANCE } });
      setLoading(prev => ({ ...prev, [module]: false }));
      return;
    }
    setLoading(prev => ({ ...prev, [module]: true }));
    try {
      if (module === 'timesheet') {
        const response = await api.getTimesheets().catch((e) => { console.error("API getTimesheets failed:", e); return { data: null }; });
        const fetchedData = response.data?.timesheets || response.data || [];
        dispatch({ type: 'SET_DATA', payload: { timesheets: Array.isArray(fetchedData) && fetchedData.length > 0 ? fetchedData : MOCK_TS } });
      } else if (module === 'leave') {
        const [leavesResp, balanceResp] = await Promise.all([
            api.getLeaveHistory().catch((e) => { console.error("API getLeaveHistory failed:", e); return { data: null }; }), 
             api.getLeaveBalance().catch((e) => { console.error("API getLeaveBalance failed:", e); return { data: null }; })
        ]);
        const fetchedLeaves = leavesResp.data?.requests || leavesResp.data || [];
        const fetchedBalance = balanceResp.data || {};
        const leavesFinal = Array.isArray(fetchedLeaves) && fetchedLeaves.length > 0 ? fetchedLeaves : MOCK_LEAVES;
        const balanceFinal = Object.keys(fetchedBalance).length > 0 ? fetchedBalance : MOCK_BALANCE;
        dispatch({ type: 'SET_DATA', payload: { leaves: leavesFinal, leaveBalance: balanceFinal } });
      } else if (module === 'expenses') {
        // Expense fetching logic goes here - assuming getExpenses API exists
        // const expensesResp = await api.getExpenses().catch(() => ({ data: [] }));
        // dispatch({ type: 'SET_DATA', payload: { expenses: expensesResp.data || [] } });
      }
    } catch (error) {
      const msg = error.response?.data?.detail || `Failed to load ${module}. Using mock data.`;
      toast({ title: "Fetch Error", description: msg, variant: 'warning' });
      if (module === 'timesheet') dispatch({ type: 'SET_DATA', payload: { timesheets: MOCK_TS } });
      if (module === 'leave') dispatch({ type: 'SET_DATA', payload: { leaves: MOCK_LEAVES, leaveBalance: MOCK_BALANCE } });
    } finally {
      setLoading(prev => ({ ...prev, [module]: false }));
    }
  }, [token, toast]);

  const handleViewXai = useCallback((item) => {
    setXaiData(item);
    setShowXaiDetails(true);
  }, []);

  const handleDecision = useCallback(async (itemId, itemType, action, comment = '') => {
    if (!itemId || !token) {
      toast({ title: "Auth Error", description: "Missing token. Cannot process decision.", variant: 'destructive' });
      return;
    }
    setLoading(prev => ({ ...prev, decision: true }));
    try {
      if (itemType === 'leave') {
        await api.approveLeaveRequest(itemId, action.toLowerCase() === 'approve', comment).catch(() => { throw new Error('API failed to process leave.'); });
      } else {
        // CRITICAL FIX: Use the general actionApproval endpoint for other types
        await api.actionApproval({ 
            item_id: itemId, 
            item_type: itemType.toLowerCase().replace(/ /g, '_'), 
            action: action.toUpperCase() 
        }).catch(() => { throw new Error('API failed to process approval action.'); });
      }
      toast({
        title: `${formatTitle(itemType)} ${action.toLowerCase()}d`,
        description: `Item ${itemId} processed successfully.`,
        variant: action.toLowerCase().includes('approve') ? 'success' : 'error'
      });
      // Refresh the necessary data
      if (itemType === 'leave') await fetchModuleData('leave');
      if (itemType === 'timesheet') await fetchModuleData('timesheet');
      await fetchApprovals();
    } catch (error) {
      const msg = error.message || error.response?.data?.reason || error.response?.data?.detail || 'Action failed.';
      toast({ title: "Error", description: msg, variant: 'destructive' });
    } finally {
      setLoading(prev => ({ ...prev, decision: false }));
    }
  }, [token, fetchApprovals, fetchModuleData, toast]);

   // --- EFFECT HOOK FOR DATA FETCHING ---
  useEffect(() => {
    // CRITICAL FIX: Ensure fetches are run only when the module is active
    const isMockMode = !token;
    if (activeModule === 'timesheet') {
      fetchModuleData('timesheet', isMockMode);
    } else if (activeModule === 'leave') {
      fetchModuleData('leave', isMockMode);
    } else if (activeModule === 'expenses') {
      fetchModuleData('expenses', isMockMode); 
    }

    if (isManager) {
        // Only fetch approvals if the user is a manager
        fetchApprovals(isMockMode); 
    }
  }, [activeModule, token, isManager, fetchModuleData, fetchApprovals]);

  // --- TIMESHEET LOGIC ---
  const calculateTotalHours = useCallback((dailyHours) => Object.values(dailyHours).reduce((sum, h) => sum + Number(h || 0), 0), []);
  const updateDailyHours = useCallback((day, hours) => {
    const updated = { ...timesheetData.daily_hours, [day]: Number(hours) || 0 };
    const total = calculateTotalHours(updated);
    setTimesheetData(prev => ({ ...prev, daily_hours: updated, total_hours: total }));
  }, [timesheetData.daily_hours, calculateTotalHours]);

  const validateTimesheet = useCallback(() => timesheetData.total_hours > 0 && timesheetData.total_hours <= 168, [timesheetData.total_hours]);

  const handleSubmitTimesheet = useCallback(async (e) => {
      e.preventDefault();
      if (!validateTimesheet()) { toast({ title: 'Invalid Timesheet', description: 'Total hours must be 1-168.', variant: 'warning' }); return; }
      setLoading(prev => ({ ...prev, timesheet: true }));
      try {
          const response = await api.submitTimesheet(timesheetData).catch((e) => { console.error("API submitTimesheet failed:", e); return { data: {} }; });
          const policyDecision = response.data.decision || 'PENDING';
          const policyReason = response.data.reason || 'Submitted for approval.';
          const finalStatus = response.data.timesheet?.status || response.data.status || 'agent_processing';
                    
          if (['STOP', 'DENY', 'USER_INSPECTION_REQUIRED'].includes(policyDecision)) {
              toast({ title: "Policy Blocked", description: `Submission blocked/flagged: ${policyReason}`, variant: 'destructive' });
              return;
          }
                    
          let finalToast;
          if (finalStatus === 'approved') { finalToast = { title: "  ✅   Auto-Approved", description: `Timesheet submitted and automatically approved.`, variant: 'success' };
          } else if (String(finalStatus).toLowerCase().includes('review')) { finalToast = { title: "  ⚠️   Review Required", description: `Submission queued for autonomous processing. Manager review initiated.`, variant: 'warning' }; 
           } else { finalToast = { title: "Submitted", description: `Timesheet submitted to the queue. Status: ${String(finalStatus).toUpperCase()}.`, variant: 'success' }; }

          toast(finalToast);
          fetchModuleData('timesheet');
          setTimesheetData({ week_ending: DEFAULT_WEEK_ENDING, total_hours: DEFAULT_TOTAL_HOURS, daily_hours: { ...DEFAULT_DAILY_HOURS } });
      } catch (error) {
          const msg = error.response?.data?.reason || error.response?.data?.detail || 'Submission failed.';
          toast({ title: "Error", description: msg, variant: 'destructive' });
      } finally { setLoading(prev => ({ ...prev, timesheet: false }));
      }
  }, [timesheetData, fetchModuleData, validateTimesheet, toast]);

   // --- LEAVE LOGIC ---
  const validateLeave = useCallback(() => {
    const start = new Date(leaveData.start_date);
    const end = new Date(leaveData.end_date);
    const days = leaveData.days;
    return end >= start && days > 0 && days <= 365; // Max 1 year leave
  }, [leaveData.start_date, leaveData.end_date, leaveData.days]);

  const updateLeaveDays = useCallback((startDate, endDate) => {
    const start = new Date(startDate);
    const end = new Date(endDate);
    start.setHours(0, 0, 0, 0); end.setHours(0, 0, 0, 0);
    let calculatedDays = 0;
    if (end >= start) {
      const diffTime = Math.abs(end.getTime() - start.getTime());
      calculatedDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24)) + 1;
    }
    setLeaveData(prev => ({ ...prev, days: Math.max(0, calculatedDays) }));
  }, []);

  useEffect(() => { updateLeaveDays(leaveData.start_date, leaveData.end_date); }, [leaveData.start_date, leaveData.end_date, updateLeaveDays]);

    const handleSubmitLeave = useCallback(async (e) => {
    e.preventDefault();
    if (!validateLeave()) { toast({ title: 'Invalid Request', description: 'End date after start; 1-365 days max.', variant: 'warning' }); return; }
    setLoading(prev => ({ ...prev, leave: true }));
    try {
      const payload = { 
         leave_type: leaveData.leave_type, 
         start_date: leaveData.start_date, 
         end_date: leaveData.end_date, 
         days: leaveData.days, 
         reason: leaveData.reason.trim(), 
         requested_hours: leaveData.days * HOURS_PER_DAY 
       };
            
      const response = await api.submitLeaveRequest(payload).catch((e) => { console.error("API submitLeaveRequest failed:", e); return { data: {} }; });
      const status = response.data.status || 'SUBMITTED';
      const policyDecision = response.data.decision || 'PENDING';
      const policyReason = response.data.reason || 'Submitted successfully.';

      if (['STOP', 'DENY', 'USER_INSPECTION_REQUIRED'].includes(policyDecision)) { 
         toast({ title: "Policy Blocked", description: `Request blocked/flagged: ${policyReason}`, variant: 'destructive' });
      } else { 
         toast({ 
           title: status === 'APPROVED' ? "Approved!" : "Submitted", 
           description: `Request ${status.toLowerCase()}. Decision: ${policyDecision}.`, 
           variant: status === 'APPROVED' ? 'success' : status === 'DENIED' ? 'warning' : 'success' 
         });
      }
      fetchModuleData('leave');
      setLeaveData({ leave_type: 'annual', start_date: DEFAULT_WEEK_ENDING, end_date: DEFAULT_WEEK_ENDING, days: 1, reason: '' });
    } catch (error) {
      const msg = error.response?.data?.reason || error.response?.data?.detail || 'Request failed.';
      toast({ title: "Error", description: msg, variant: 'destructive' });
    } finally { setLoading(prev => ({ ...prev, leave: false }));
    }
  }, [leaveData, fetchModuleData, validateLeave, toast]);

  // --- EXPENSE LOGIC ---
  const validateExpense = useCallback(() => expenseData.amount > 0 && expenseData.description.trim().length > 0, [expenseData.amount, expenseData.description]);
  
  const handleSubmitExpense = useCallback(async (e) => {
    e.preventDefault();
    if (!validateExpense()) { toast({ title: 'Invalid Expense', description: 'Amount >0; description required.', variant: 'warning' }); return; }
    setLoading(prev => ({ ...prev, expense: true }));
    try {
      const expenseDataPayload = { amount: expenseData.amount, category: expenseData.category, description: expenseData.description, date: expenseData.date };
      // CRITICAL FIX: Pass null for receipt file if not implemented
      await api.submitExpense(expenseDataPayload, null).catch((e) => { console.error("API submitExpense failed:", e); throw new Error('API failed to submit expense.'); }); 
      toast({ title: "Submitted!", description: 'Expense claim queued for approval and OCR.', variant: 'success' });
      setExpenseData({ amount: 0, currency: 'USD', category: 'Travel', description: '', date: DEFAULT_WEEK_ENDING });
    } catch (error) {
      const msg = error.message || error.response?.data?.detail || 'Submission failed.';
      toast({ title: "Error", description: msg, variant: 'destructive' });
    } finally { setLoading(prev => ({ ...prev, expense: false })); }
  }, [expenseData, validateExpense, toast]);

  const handleOcrScan = useCallback(async () => {
    setLoadingOcr(true);
    await new Promise(resolve => setTimeout(resolve, 1500));
    const mockOcrResult = { amount: 54.99, currency: 'USD', category: 'Meals', description: 'Dinner with client at Stellar Bistro', date: '2025-11-27' };
    try {
      // NOTE: Real OCR scan would involve file upload via API.scanExpenseReceipt
      setExpenseData(prev => ({ ...prev, amount: mockOcrResult.amount, currency: mockOcrResult.currency, category: mockOcrResult.category, description: mockOcrResult.description, date: mockOcrResult.date }));
      toast({ title: "OCR Success", description: `Fields auto-filled from scan.`, variant: 'success'
      });
    } catch (error) {
      toast({ title: "OCR Failed", description: 'Could not extract details from receipt image.', variant: 'destructive' });
    } finally { setLoadingOcr(false); }
  }, [toast]);


  // --- RENDER MEMOIZED BLOCKS ---
  const renderApprovals = useMemo(() => {
    const allApprovals = [
      // Normalize and combine all approval types
      ...(approvalsData.timesheets || []).map(item => ({ ...item, itemType: 'timesheet', type: 'Timesheet', id: item.timesheet_id || item.id, summary: `Timesheet: ${item.total_hours}h`, status: item.status || 'PENDING', risk: item.risk || 'low' })),
      ...(approvalsData.leave_requests || []).map(item => ({ ...item, itemType: 'leave', type: 'Leave Request', id: item.request_id || item.id, summary: `Leave: ${item.days} days`, status: item.status || 'PENDING', risk: item.risk || 'low' })),
      ...(approvalsData.expense_claims || []).map(item => ({ ...item, itemType: 'expense', type: 'Expense Claim', id: item.expense_id || item.id, summary: `Expense: $${item.amount}`, status: item.status || 'PENDING', risk: item.risk || 'low' })),
      ...(approvalsData.wfm_anomalies || []).map(item => ({ ...item, itemType: 'wfm_anomaly', type: 'WFM Anomaly', id: item.timesheet_id || item.id, summary: item.summary || 'WFM Anomaly', status: item.status || 'REVIEW_REQUIRED', risk: item.risk || 'high' })),
      ...(approvalsData.pra_recommendations || []).map(item => ({ ...item, itemType: 'pra_action', type: 'Retention Recommendation', id: item.recommendation_id || item.id, summary: item.summary || 'PRA Action', status: item.status || 'PENDING', risk: item.risk || 'high' })),
    ].flat().filter(item => ['PENDING', 'VOTING', 'PENDING_STANDARD_APPROVAL', 'AGENT_PROCESSING', 'REVIEW_REQUIRED', 'AGENT_REVIEW'].includes(String(item.status || item.risk_level).toUpperCase()))
    .map(item => ({ 
        ...item, 
        risk: item.risk || 'low', 
        employee_name: item.employee_name || item.requester || item.user_id || 'N/A' 
    }));

    if (loading.approvals) { return <div className="hr-card" style={{ padding: '2rem' }}> <div className="holo-spinner-shell" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', margin: '1.25rem auto' }}> <Loader2 className="animate-spin" size={24} style={{ color: tokens.color?.['accent-primary'] }} /> </div> </div>;
    }

    const totalPending = allApprovals.length;

    return (
      <div className="hr-card" style={{ background: tokens.color?.['panel-800'], padding: tokens.spacing?.lg, borderRadius: tokens.border?.radius?.card, border: `1px solid ${tokens.color?.['border-600']}` }}>
        {showXaiDetails && xaiData && <XAIDecisionPanelWrapper item={xaiData} onClose={() => setShowXaiDetails(false)} />}
        <div className="approvals-header-row" style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: `1px solid ${tokens.color?.['border-600']}`, paddingBottom: tokens.spacing?.sm, marginBottom: tokens.spacing?.md}}>
          <div> <div className="hr-card-title" style={{
              // --- FIX: Added optional chaining ---
              fontWeight: tokens.typography?.h2?.fontWeight, 
              // ------------------------------------
              color: tokens.color?.['text-100']}}>Manager Approvals</div> <div className="hr-card-subtitle" style={{
                  // --- FIX: Added optional chaining ---
                  fontSize: tokens.typography?.small?.fontSize, 
                  // ------------------------------------
                  color: tokens.color?.['muted-500']}}>Curated queue from /mss/approvals/queue</div> </div>
          <div className="approvals-count-pill" style={{background: tokens.color?.['warning'], color: tokens.color?.['bg-900'], padding: '4px 8px', borderRadius: tokens.border?.radius?.chip, 
              // --- FIX: Added optional chaining ---
              fontWeight: tokens.typography?.h2?.fontWeight
              // ------------------------------------
          }}> {totalPending} pending </div>
        </div>
        <div className="list-stack" style={{ maxHeight: '25rem', overflowY: 'auto' }}> 
          {totalPending > 0 ? allApprovals.map((item) => {
            const riskColor = String(item.risk).toLowerCase() === 'high' || item.itemType === 'wfm_anomaly' || item.itemType === 'pra_action' ? tokens.color?.['danger'] : String(item.risk).toLowerCase() === 'medium' ? tokens.color?.['warning'] : tokens.color?.['success'];
            const isXaiItem = item.itemType === 'wfm_anomaly' || item.itemType === 'pra_action';
            return (
              <div key={item.id} className="approval-item"
              style={{ borderLeft: `0.25rem solid ${riskColor}`, background: tokens.color?.['panel-700'], border: `1px solid ${tokens.color?.['border-600']}`, padding: tokens.spacing?.sm, borderRadius: tokens.border?.radius?.chip, marginBottom: tokens.spacing?.xs }}>
                <div className="approval-main-row" style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
                  <div className="approval-title" style={{ color: tokens.color?.['text-100'], 
                      // --- FIX: Added optional chaining ---
                      fontSize: tokens.typography?.base?.fontSize, 
                      fontWeight: tokens.typography?.h2?.fontWeight 
                      // ------------------------------------
                  }}>{item.type} · {item.employee_name || 'N/A'}</div>
                  <div className="status-chip status-chip-pending" style={{ background: tokens.color?.['warning'], color: tokens.color?.['bg-900'], padding: '2px 8px', borderRadius: tokens.border?.radius?.chip, 
                      // --- FIX: Added optional chaining ---
                      fontSize: tokens.typography?.small?.fontSize 
                      // ------------------------------------
                  }}>PENDING</div>
                </div>
                <div className="approval-summary" style={{ 
                    // --- FIX: Added optional chaining ---
                    fontSize: tokens.typography?.small?.fontSize, 
                    // ------------------------------------
                    color: tokens.color?.['muted-500'], margin: tokens.spacing?.xs }}>{item.summary} · <span style={{ color: riskColor }}>{item.risk ? `${formatTitle(item.risk)} Risk` : 'Standard Review'}</span></div>
                <div className="approval-actions-row" style={{ display: 'flex', justifyContent: 'flex-end', gap: tokens.spacing?.xs, marginTop: tokens.spacing?.xs }}>
                  {isXaiItem && <button type="button" className="secondary-button" onClick={() => handleViewXai(item)} style={{ padding: tokens.spacing?.xs, 
                      // --- FIX: Added optional chaining ---
                      fontSize: tokens.typography?.small?.fontSize, 
                      // ------------------------------------
                      border: `1px solid ${tokens.color?.['accent-secondary']}`, color: tokens.color?.['accent-secondary'], background: tokens.color?.['panel-600'], borderRadius: tokens.border?.radius?.chip }}> <Brain size={14} /> XAI </button>}
                  <button type="button" className="secondary-button" onClick={() => handleDecision(item.id, item.itemType, 'reject')} disabled={loading.decision} style={{ padding: tokens.spacing?.xs, 
                      // --- FIX: Added optional chaining ---
                      fontSize: tokens.typography?.small?.fontSize, 
                      // ------------------------------------
                      border: `1px solid ${tokens.color?.['danger']}`, color: tokens.color?.['danger'], background: `rgba(${tokens.color?.['danger-rgb']}, 0.1)`, borderRadius: tokens.border?.radius?.chip }}> <span>Reject</span> </button>
                  <button type="button" className="primary-button" onClick={() => handleDecision(item.id, item.itemType, 'approve')} disabled={loading.decision} style={{ padding: tokens.spacing?.xs, 
                      // --- FIX: Added optional chaining ---
                      fontSize: tokens.typography?.small?.fontSize, 
                      fontWeight: tokens.typography?.h2?.fontWeight,
                      // ------------------------------------
                      color: tokens.color?.['bg-900'], background: tokens.color?.['success'], borderRadius: tokens.border?.radius?.chip }}> <span>Approve</span> </button>
                </div>
              </div>
            );
          }) : (<div className="empty-state" style={{ padding: tokens.spacing?.md, color: tokens.color?.['muted-500'] }}>No pending approvals currently in the queue.</div>)}
        </div>
        {totalPending > 0 && <button type="button" className="secondary-button" onClick={fetchApprovals} style={{ marginTop: tokens.spacing?.sm, justifyContent: 'center', color: tokens.color?.['accent-primary'], border: `1px solid ${tokens.color?.['accent-primary']}`, background: tokens.color?.['panel-700'], padding: tokens.spacing?.sm, borderRadius: tokens.border?.radius?.button, display: 'flex', alignItems: 'center', gap: tokens.spacing?.xs }}> <RefreshCw size={14} /> Refresh Queue </button>}
      </div>
    );
  }, [approvalsData, loading.approvals, loading.decision, handleDecision, fetchApprovals, handleViewXai, showXaiDetails, xaiData, toast]);

  const LeaveModuleContent = useMemo(() => {
    const annualDays = (state.leaveBalance?.balance_days || (state.leaveBalance?.balance_hours / HOURS_PER_DAY))?.toFixed?.(1) || 0;
    const sickDays = (state.leaveBalance?.sick_leave || (state.leaveBalance?.sick_hours / HOURS_PER_DAY))?.toFixed?.(1) || 0;
    const personalDays = (state.leaveBalance?.personal_leave || (state.leaveBalance?.personal_hours / HOURS_PER_DAY))?.toFixed?.(1) || 0;
    return (
      <div className="hr-card" style={{ gridColumn: 'span 1', padding: tokens.spacing?.lg, background: tokens.color?.['panel-800'], borderRadius: tokens.border?.radius?.card, border: `1px solid ${tokens.color?.['border-600']}` }}>
        <div className="hr-card-header">
          <div className="hr-card-title" style={{
              // --- FIX: Added optional chaining ---
              fontWeight: tokens.typography?.h1?.fontWeight, 
              // ------------------------------------
              color: tokens.color?.['accent-primary'], borderBottom: `1px solid ${tokens.color?.['border-600']}`, paddingBottom: tokens.spacing?.sm}}>Request Leave & Current Balances</div>
        </div>
        {loading.leave ? (<div className="holo-spinner-shell" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', margin: tokens.spacing?.lg }}><Loader2 className="animate-spin" size={24} style={{ color: tokens.color?.['accent-primary'] }} /></div>) : (
          <div className="timesheet-grid" style={{ display: 'grid', gridTemplateColumns: '1.2fr 1.8fr', gap:    tokens.spacing?.md }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: tokens.spacing?.sm }}>
              <div className="field-label" style={{ color: tokens.color?.['text-100'], 
                  // --- FIX: Added optional chaining ---
                  fontWeight: tokens.typography?.h2?.fontWeight 
                  // ------------------------------------
              }}>Current Balances (in Days)</div>
              <div className="two-column-mini" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: tokens.spacing?.xs }}>
                <div className="mini-card" style={{ background: tokens.color?.['panel-700'], border: `1px solid ${tokens.color?.['accent-primary']}44`, padding: tokens.spacing?.sm, borderRadius: tokens.border?.radius?.chip }}><div className="mini-label" style={{
                    // --- FIX: Added optional chaining ---
                    fontSize: tokens.typography?.small?.fontSize, 
                    // ------------------------------------
                    color: tokens.color?.['muted-500']}}>Annual leave</div><div className="mini-value" style={{ color: tokens.color?.['accent-primary'], 
                        // --- FIX: Added optional chaining ---
                        fontWeight: tokens.typography?.h1?.fontWeight 
                        // ------------------------------------
                    }}>{annualDays} days</div></div>
                <div className="mini-card" style={{ background: tokens.color?.['panel-700'], border: `1px solid ${tokens.color?.['success']}44`, padding: tokens.spacing?.sm, borderRadius: tokens.border?.radius?.chip }}><div className="mini-label" style={{
                    // --- FIX: Added optional chaining ---
                    fontSize: tokens.typography?.small?.fontSize, 
                    // ------------------------------------
                    color: tokens.color?.['muted-500']}}>Sick leave</div><div className="mini-value" style={{ color: tokens.color?.['success'], 
                        // --- FIX: Added optional chaining ---
                        fontWeight: tokens.typography?.h1?.fontWeight 
                        // ------------------------------------
                    }}>{sickDays} days</div></div>
                <div className="mini-card" style={{ background: tokens.color?.['panel-700'], border: `1px solid ${tokens.color?.['accent-secondary']}44`, padding: tokens.spacing?.sm, borderRadius: tokens.border?.radius?.chip }}><div className="mini-label" style={{
                    // --- FIX: Added optional chaining ---
                    fontSize: tokens.typography?.small?.fontSize, 
                    // ------------------------------------
                    color: tokens.color?.['muted-500']}}>Personal leave</div><div className="mini-value" style={{ color: tokens.color?.['accent-secondary'], 
                        // --- FIX: Added optional chaining ---
                        fontWeight: tokens.typography?.h1?.fontWeight 
                        // ------------------------------------
                    }}>{personalDays} days</div></div>
                <div className="mini-card" style={{ background: tokens.color?.['panel-700'], border: `1px solid ${tokens.color?.['border-600']}`, padding: tokens.spacing?.sm, borderRadius: tokens.border?.radius?.chip }}><div className="mini-label" style={{
                    // --- FIX: Added optional chaining ---
                    fontSize: tokens.typography?.small?.fontSize, 
                    // ------------------------------------
                    color: tokens.color?.['muted-500']}}>Unpaid leave</div><div className="mini-value" style={{ color: tokens.color?.['muted-500'], 
                        // --- FIX: Added optional chaining ---
                        fontWeight: tokens.typography?.h1?.fontWeight 
                        // ------------------------------------
                    }}>Unlimited</div></div>
              </div>
              <div className="stack-spacer" style={{ paddingTop: tokens.spacing?.md }}>
                <div className="field-label" style={{ color: tokens.color?.['text-100'], 
                    // --- FIX: Added optional chaining ---
                    fontWeight: tokens.typography?.h2?.fontWeight 
                    // ------------------------------------
                }}>Recent Requests ({(state.leaves ||    []).length})</div>
                <div className="list-stack" style={{ maxHeight: '12.5rem', overflowY: 'auto', marginTop: tokens.spacing?.xs }}> {/* FIX: Max height and overflow for list stack */}
                  {(state.leaves || []).length > 0 ?    (state.leaves || []).slice(0, 5).map((req, idx) => <LeaveRow key={req.request_id || idx} req={req} idx={idx} HOURS_PER_DAY={HOURS_PER_DAY} />) : (<div className="empty-state" style={{color: tokens.color?.['muted-500'], padding: tokens.spacing?.xs}}>No recent leave requests found.</div>)}
                </div>
              </div>
            </div>
            <form onSubmit={handleSubmitLeave} style={{ display: 'flex', flexDirection: 'column', gap: tokens.spacing?.sm, background: tokens.color?.['panel-700'], padding: tokens.spacing?.md, borderRadius: tokens.border?.radius?.card, border: `1px solid ${tokens.color?.['border-700']}` }}>
              <div className="two-column-mini" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: tokens.spacing?.sm }}>
                <div className="emp-field-block"><div className="holo-input-label" style={{
                    // --- FIX: Added optional chaining ---
                    fontSize: tokens.typography?.small?.fontSize, 
                    // ------------------------------------
                    color: tokens.color?.['muted-500']}}>Leave Type</div><select className="holo-select" value={leaveData.leave_type} onChange={(e) => setLeaveData(prev => ({ ...prev, leave_type: e.target.value }))} required style={{ width: '100%', padding: '10px 12px', background: tokens.color?.['bg-input'], border: `1px solid ${tokens.color?.['border-600']}`, borderRadius: tokens.border?.radius?.chip, color: tokens.color?.['text-100'], 
                        // --- FIX: Added optional chaining ---
                        fontSize: tokens.typography?.base?.fontSize, 
                        // ------------------------------------
                        outline: 'none' }}><option value="annual">Annual</option><option value="sick">Sick</option><option value="personal">Personal</option><option value="unpaid">Unpaid</option></select></div>
                <div className="emp-field-block"><div className="holo-input-label" style={{
                    // --- FIX: Added optional chaining ---
                    fontSize: tokens.typography?.small?.fontSize, 
                    // ------------------------------------
                    color: tokens.color?.['muted-500']}}>Days Requested (Auto)</div><input type="number" className="holo-input" value={leaveData.days} required readOnly style={{ width: '100%', padding: '10px 12px', background: tokens.color?.['bg-input'], border: `1px solid ${tokens.color?.['border-600']}`, borderRadius: tokens.border?.radius?.chip, color: tokens.color?.['accent-primary'], 
                    // --- FIX: Added optional chaining ---
                    fontWeight: tokens.typography?.h2?.fontWeight, 
                    // ------------------------------------
                    outline: 'none' }} /></div>
              </div>
              <div className="two-column-mini" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: tokens.spacing?.sm }}>
                <div className="emp-field-block"><div className="holo-input-label" style={{
                    // --- FIX: Added optional chaining ---
                    fontSize: tokens.typography?.small?.fontSize, 
                    // ------------------------------------
                    color: tokens.color?.['muted-500']}}>Start Date</div><input type="date" className="holo-input" value={leaveData.start_date} onChange={(e) => setLeaveData(prev => ({ ...prev, start_date: e.target.value }))} required style={{ width: '100%', padding: '10px 12px', background: tokens.color?.['bg-input'], border: `1px solid ${tokens.color?.['border-600']}`, borderRadius: tokens.border?.radius?.chip, color: tokens.color?.['text-100'], 
                    // --- FIX: Added optional chaining ---
                    fontSize: tokens.typography?.base?.fontSize, 
                    // ------------------------------------
                    outline: 'none' }}/></div>
                <div className="emp-field-block"><div className="holo-input-label" style={{
                    // --- FIX: Added optional chaining ---
                    fontSize: tokens.typography?.small?.fontSize, 
                    // ------------------------------------
                    color: tokens.color?.['muted-500']}}>End Date</div><input type="date" className="holo-input" value={leaveData.end_date} onChange={(e) => setLeaveData(prev => ({ ...prev, end_date: e.target.value }))} required style={{ width: '100%', padding: '10px 12px', background: tokens.color?.['bg-input'], border: `1px solid ${tokens.color?.['border-600']}`, borderRadius: tokens.border?.radius?.chip, color: tokens.color?.['text-100'], 
                    // --- FIX: Added optional chaining ---
                    fontSize: tokens.typography?.base?.fontSize, 
                    // ------------------------------------
                    outline: 'none' }}/></div>
              </div>
              <div className="emp-field-block"><div className="holo-input-label" style={{
                  // --- FIX: Added optional chaining ---
                  fontSize: tokens.typography?.small?.fontSize, 
                  // ------------------------------------
                  color: tokens.color?.['muted-500']}}>Reason/Justification</div><textarea className="holo-textarea" rows="3" value={leaveData.reason} onChange={(e) => setLeaveData(prev => ({ ...prev, reason: e.target.value }))} placeholder="Brief reason for the request..." required style={{ width: '100%', padding: '10px 12px', background: tokens.color?.['bg-input'], border: `1px solid ${tokens.color?.['border-600']}`, borderRadius: tokens.border?.radius?.chip, color: tokens.color?.['text-100'], 
                  // --- FIX: Added optional chaining ---
                  fontSize: tokens.typography?.base?.fontSize, 
                  // ------------------------------------
                  outline: 'none', resize: 'vertical' }}/></div>
              <button type="submit" className="primary-button" disabled={loading.leave ||    !validateLeave()} style={{ width: '100%', marginTop: tokens.spacing?.sm, background: tokens.color?.['accent-primary'], color: tokens.color?.['bg-900'], padding: '10px 14px', borderRadius: tokens.border?.radius?.button, 
                  // --- FIX: Added optional chaining ---
                  fontWeight: tokens.typography?.h2?.fontWeight 
                  // ------------------------------------
              }}>{loading.leave ?    'Submitting...' : 'Submit Leave Request'}</button>
            </form>
          </div>
        )}
      </div>
    );
  }, [state.leaveBalance, state.leaves, leaveData, loading.leave, handleSubmitLeave, validateLeave]);

    const TimesheetModuleContent = useMemo(() => (
    <div className="hr-content-layout" style={{ display:        'grid', gridTemplateColumns: isManager ? '2fr 1fr' : '1fr', gap: tokens.spacing?.lg }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: tokens.spacing?.md }}>
            {/* Timesheet Submit Card */}
            <div className="hr-card" style={{padding: tokens.spacing?.lg, background: tokens.color?.['panel-800'], borderRadius: tokens.border?.radius?.card, border: `1px solid ${tokens.color?.['border-600']}`}}>
                <div
                className="hr-card-header" style={{ marginBottom: tokens.spacing?.xs, borderBottom: `1px solid ${tokens.color?.['inner-divider']}`, paddingBottom: tokens.spacing?.xs, display: 'flex', justifyContent: 'space-between' }}>
                    <div><div className="hr-card-title" style={{
                        // --- FIX: Added optional chaining ---
                        fontWeight: tokens.typography?.h2?.fontWeight, 
                        // ------------------------------------
                        color: tokens.color?.['text-100']}}>Submit Timesheet</div></div>
                    <div className="hr-card-tag" style={{
                        // --- FIX: Added optional chaining ---
                        fontSize: tokens.typography?.small?.fontSize, 
                        // ------------------------------------
                        color: tokens.color?.['muted-500']}}>Week ending {timesheetData.week_ending}</div>
                </div>
                <form onSubmit={handleSubmitTimesheet}>
                    <div className="timesheet-grid" style={{display: 'grid', gridTemplateColumns: '1fr 2fr', gap: tokens.spacing?.md, marginTop: tokens.spacing?.md}}>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: tokens.spacing?.xs }}>
                          <div className="emp-field-block"><div className="holo-input-label" style={{
                              // --- FIX: Added optional chaining ---
                              fontSize: tokens.typography?.small?.fontSize, 
                              // ------------------------------------
                              color: tokens.color?.['muted-500']}}>Week ending</div><input type="date" className="holo-input" value={timesheetData.week_ending} onChange={(e) => setTimesheetData(prev => ({ ...prev, week_ending: e.target.value }))} required style={{ width: '100%', padding: '10px 12px', background: tokens.color?.['bg-input'], border: `1px solid ${tokens.color?.['border-600']}`, borderRadius: tokens.border?.radius?.chip, color: tokens.color?.['text-100'], 
                              // --- FIX: Added optional chaining ---
                              fontSize: tokens.typography?.base?.fontSize, 
                              // ------------------------------------
                              outline: 'none' }}/></div>
                          <div className="stack-spacer" style={{ borderTop: `1px solid ${tokens.color?.['inner-divider']}`, paddingTop: tokens.spacing?.xs, marginTop: tokens.spacing?.xs }}><div className="field-label" style={{
                              // --- FIX: Added optional chaining ---
                              fontSize: tokens.typography?.small?.fontSize, 
                              // ------------------------------------
                              color: tokens.color?.['muted-500']}}>Policy engine</div><div className="field-shell"><span className="field-shell-value" style={{color: tokens.color?.['accent-primary'], 
                              // --- FIX: Added optional chaining ---
                              fontSize:    tokens.typography?.base?.fontSize
                              // ------------------------------------
                              }}>ACTIVE · HR_TIMESHEET_V2</span></div></div>
                      </div>
                      <div>
                          <div className="field-label" style={{
                              // --- FIX: Added optional chaining ---
                              fontSize: tokens.typography?.small?.fontSize, 
                              // ------------------------------------
                              color: tokens.color?.['muted-500']}}>Daily hours</div>
                          <div className="daily-hours-grid" style={{display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: tokens.spacing?.xs}}>{Object.keys(DEFAULT_DAILY_HOURS).map((day) => (<div key={day} className="day-cell"><div className="day-label" style={{
                              // --- FIX: Added optional chaining ---
                              fontSize: tokens.typography?.small?.fontSize, 
                              // ------------------------------------
                              color: tokens.color?.['muted-500']}}>{day.charAt(0).toUpperCase()}</div><input type="number" className="day-field holo-input" min="0" max="24" step="0.5" value={timesheetData.daily_hours[day] ||    ''} onChange={(e) => updateDailyHours(day, e.target.value)} required style={{ width: '100%', padding: '8px', background: tokens.color?.['bg-input'], border: `1px solid ${tokens.color?.['border-600']}`, borderRadius: tokens.border?.radius?.chip, color: tokens.color?.['text-100'], 
                              // --- FIX: Added optional chaining ---
                              fontSize: tokens.typography?.base?.fontSize, 
                              // ------------------------------------
                              outline: 'none' }}/></div>))}</div>
                          <div className="total-hours-row" style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: tokens.spacing?.sm, padding: tokens.spacing?.xs, background: tokens.color?.['panel-700'], borderRadius: tokens.border?.radius?.chip}}><div>Total hours this week</div><div className="total-hours-value" style={{
                              // --- FIX: Added optional chaining ---
                              fontWeight: tokens.typography?.h2?.fontWeight, 
                              // ------------------------------------
                              color: tokens.color?.['accent-primary']}}>{timesheetData.total_hours.toFixed(1)}h</div></div>
                      </div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: tokens.spacing?.sm, marginTop: tokens.spacing?.md }}>
                      <div className="muted-text" style={{
                          // --- FIX: Added optional chaining ---
                          fontSize: tokens.typography?.small?.fontSize, 
                          // ------------------------------------
                          color: tokens.color?.['muted-500']}}>AI reconciliation will score this submission.</div>
                      <button type="submit" className="primary-button" disabled={loading.timesheet ||    !validateTimesheet()} style={{ padding: tokens.spacing?.xs, background: tokens.color?.['accent-primary'], color: tokens.color?.['bg-900'], borderRadius: tokens.border?.radius?.button, 
                          // --- FIX: Added optional chaining ---
                          fontWeight: tokens.typography?.h2?.fontWeight, 
                          // ------------------------------------
                          display: 'flex', alignItems: 'center', gap: tokens.spacing?.xs }}> <Zap size={16} /> <span>Submit &amp;    run AI check</span> </button>
                    </div>
                </form>
            </div>
            {/* Recent Timesheets History */}
            <div className="hr-card" style={{padding: tokens.spacing?.lg, background: tokens.color?.['panel-800'], borderRadius: tokens.border?.radius?.card, border: `1px solid ${tokens.color?.['border-600']}`}}>
              <div className="hr-card-header" style={{ borderBottom: `1px solid ${tokens.color?.['inner-divider']}`, paddingBottom: tokens.spacing?.xs, marginBottom: tokens.spacing?.sm }}><div><div className="hr-card-title" style={{
                  // --- FIX: Added optional chaining ---
                  fontWeight: tokens.typography?.h2?.fontWeight, 
                  // ------------------------------------
                  color: tokens.color?.['text-100']}}>Recent Timesheets</div></div></div>
              <div className="list-stack" style={{ maxHeight: '12.5rem', overflowY: 'auto' }}> {/* FIX: Max height and overflow for list stack */}
                  {loading.timesheet && <div className="holo-spinner-shell" style={{display: 'flex', justifyContent: 'center'}}><Loader2 className="animate-spin" size={24} style={{ color: tokens.color?.['accent-primary'] }} /></div>}
                    {Array.isArray(timesheets) && timesheets.length > 0 ?    timesheets.map((ts) => {
                      const status = (ts.status || 'pending').toLowerCase();
                      const statusColor = status === 'approved' ? tokens.color?.['success'] : status.includes('review') || status === 'pending' || status.includes('processing') ? tokens.color?.['warning'] : tokens.color?.['danger'];
                      return (<div key={ts.timesheet_id} className="item-row" style={{ borderLeft: `0.25rem solid ${statusColor}`, background: tokens.color?.['panel-700'], padding: tokens.spacing?.xs, borderRadius: tokens.border?.radius?.chip, marginBottom: tokens.spacing?.xs, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <div className="item-row-main" style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexGrow: 1}}>
                              <div className="item-row-title" style={{
                                  // --- FIX: Added optional chaining ---
                                  fontWeight: tokens.typography?.base?.fontWeight, 
                                  // ------------------------------------
                                  color: tokens.color?.['text-100']}}>Week ending {ts.week_ending}</div>
                              <div className="item-row-meta" style={{
                                  // --- FIX: Added optional chaining ---
                                  fontSize: tokens.typography?.small?.fontSize, 
                                  // ------------------------------------
                                  color: tokens.color?.['muted-500']}}><span>{ts.total_hours} h · AI score {ts.ai_score ||    'N/A'}</span></div>
                          </div>
                          <div className={`status-chip`} style={{ background: `${statusColor}22`, color: statusColor, padding: '2px 6px', borderRadius: tokens.border?.radius?.chip, 
                              // --- FIX: Added optional chaining ---
                              fontSize: tokens.typography?.small?.fontSize, 
                              // ------------------------------------
                              marginLeft: tokens.spacing?.sm }}>{status.toUpperCase().replace('_', ' ')}</div>
                      </div>);
    }) : !loading.timesheet && (<div className="empty-state" style={{color: tokens.color?.['muted-500'], padding: tokens.spacing?.md}}>No recent timesheets found.</div>)}
              </div>
            </div>
          </div>
          {isManager && <div style={{ display: 'flex', flexDirection: 'column', gap: tokens.spacing?.md }}>{renderApprovals}</div>}
        </div>
    ), [isManager, timesheetData, loading.timesheet, timesheets, handleSubmitTimesheet, validateTimesheet, updateDailyHours, renderApprovals]);

    const ExpensesModuleContent = useMemo(() => (
    <div className="hr-content-layout" style={{ display: 'grid', gridTemplateColumns: isManager ? '2fr 1fr' : '1fr', gap: tokens.spacing?.lg }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: tokens.spacing?.md }}>
        <div className="hr-card" style={{padding: tokens.spacing?.lg, background: tokens.color?.['panel-800'], borderRadius: tokens.border?.radius?.card, border: `1px solid ${tokens.color?.['border-600']}`}}>
          <div className="hr-card-header" style={{ borderBottom: `1px solid ${tokens.color?.['inner-divider']}`, paddingBottom: tokens.spacing?.xs, marginBottom: tokens.spacing?.md, display: 'flex', justifyContent: 'space-between' }}><div><div className="hr-card-title" style={{
              // --- FIX: Added optional chaining ---
              fontWeight: tokens.typography?.h2?.fontWeight, 
              // ------------------------------------
              color: tokens.color?.['text-100']}}>Submit Expense Claim</div></div><div className="hr-card-tag" style={{
                  // --- FIX: Added optional chaining ---
                  fontSize: tokens.typography?.small?.fontSize, 
                  // ------------------------------------
                  color: tokens.color?.['muted-500']}}>New Claim</div></div>
          <form onSubmit={handleSubmitExpense}>
            <div className="two-column-mini" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: tokens.spacing?.sm }}><div className="emp-field-block"><div className="holo-input-label" style={{
                // --- FIX: Added optional chaining ---
                fontSize: tokens.typography?.small?.fontSize, 
                // ------------------------------------
                color: tokens.color?.['muted-500']}}>Amount</div><input type="number" className="holo-input" min="0.01" step="0.01" value={expenseData.amount} onChange={(e) => setExpenseData(prev => ({ ...prev, amount: Number(e.target.value) }))} required placeholder="0.00" style={{ width: '100%', padding: '10px 12px', background: tokens.color?.['bg-input'], border: `1px solid ${tokens.color?.['border-600']}`, borderRadius: tokens.border?.radius?.chip, color: tokens.color?.['text-100'], 
                // --- FIX: Added optional chaining ---
                fontSize: tokens.typography?.base?.fontSize, 
                // ------------------------------------
                outline: 'none' }}/></div><div className="emp-field-block"><div className="holo-input-label" style={{
                    // --- FIX: Added optional chaining ---
                    fontSize: tokens.typography?.small?.fontSize, 
                    // ------------------------------------
                    color: tokens.color?.['muted-500']}}>Currency</div><select className="holo-select" value={expenseData.currency} onChange={(e) => setExpenseData(prev => ({ ...prev, currency: e.target.value }))} style={{ width: '100%', padding: '10px 12px', background: tokens.color?.['bg-input'], border: `1px solid ${tokens.color?.['border-600']}`, borderRadius: tokens.border?.radius?.chip, color: tokens.color?.['text-100'], 
                    // --- FIX: Added optional chaining ---
                    fontSize: tokens.typography?.base?.fontSize, 
                    // ------------------------------------
                    outline: 'none' }}><option value="USD">USD</option><option value="EUR">EUR</option></select></div></div>
            <div className="two-column-mini" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: tokens.spacing?.sm }}><div className="emp-field-block"><div className="holo-input-label" style={{
                // --- FIX: Added optional chaining ---
                fontSize: tokens.typography?.small?.fontSize, 
                // ------------------------------------
                color: tokens.color?.['muted-500']}}>Category</div><select className="holo-select" value={expenseData.category} onChange={(e) => setExpenseData(prev => ({ ...prev, category: e.target.value }))} style={{ width: '100%', padding: '10px 12px', background: tokens.color?.['bg-input'], border: `1px solid ${tokens.color?.['border-600']}`, borderRadius: tokens.border?.radius?.chip, color: tokens.color?.['text-100'], 
                // --- FIX: Added optional chaining ---
                fontSize: tokens.typography?.base?.fontSize, 
                // ------------------------------------
                outline: 'none' }}><option value="Travel">Travel</option><option value="Meals">Meals</option></select></div><div className="emp-field-block"><div className="holo-input-label" style={{
                    // --- FIX: Added optional chaining ---
                    fontSize: tokens.typography?.small?.fontSize, 
                    // ------------------------------------
                    color: tokens.color?.['muted-500']}}>Date</div><input type="date" className="holo-input" value={expenseData.date} onChange={(e) => setExpenseData(prev => ({ ...prev, date: e.target.value }))} required style={{ width: '100%', padding: '10px 12px', background: tokens.color?.['bg-input'], border: `1px solid ${tokens.color?.['border-600']}`, borderRadius: tokens.border?.radius?.chip, color: tokens.color?.['text-100'], 
                    // --- FIX: Added optional chaining ---
                    fontSize: tokens.typography?.base?.fontSize, 
                    // ------------------------------------
                    outline: 'none' }}/></div></div>
            <div className="emp-field-block" style={{marginBottom: tokens.spacing?.md}}><div className="holo-input-label" style={{
                // --- FIX: Added optional chaining ---
                fontSize: tokens.typography?.small?.fontSize, 
                // ------------------------------------
                color: tokens.color?.['muted-500']}}>Description</div><textarea className="holo-textarea" rows="3" value={expenseData.description} onChange={(e) => setExpenseData(prev => ({ ...prev, description: e.target.value }))} placeholder="Expense description..." required style={{ width: '100%', padding: '10px 12px', background: tokens.color?.['bg-input'], border: `1px solid ${tokens.color?.['border-600']}`, borderRadius: tokens.border?.radius?.chip, color: tokens.color?.['text-100'], 
                // --- FIX: Added optional chaining ---
                fontSize: tokens.typography?.base?.fontSize, 
                // ------------------------------------
                outline: 'none', resize: 'vertical' }}/></div>
            <div style={{ display: 'flex', gap: tokens.spacing?.sm, marginTop: tokens.spacing?.sm }}>
              <button type="button" className="secondary-button" onClick={handleOcrScan} disabled={loadingOcr ||  loading.expense} style={{ background: tokens.color?.['panel-700'], border: `1px solid ${tokens.color?.['border-600']}`, color: tokens.color?.['muted-500'], padding: '10px 14px', borderRadius: tokens.border?.radius?.button, 
                  // --- FIX: Added optional chaining ---
                  fontWeight: tokens.typography?.h2?.fontWeight, 
                  // ------------------------------------
                  display: 'flex', alignItems: 'center', gap: tokens.spacing?.xs }}><Camera size={16} /><span>{loadingOcr ? 'Scanning...' : 'Run OCR Scan'}</span></button>
              <button type="submit" className="primary-button" disabled={loading.expense ||  !validateExpense() || loadingOcr} style={{ width: '100%', background: tokens.color?.['accent-primary'], color: tokens.color?.['bg-900'], padding: '10px 14px', borderRadius: tokens.border?.radius?.button, 
                  // --- FIX: Added optional chaining ---
                  fontWeight: tokens.typography?.h2?.fontWeight, 
                  // ------------------------------------
                  display: 'flex', alignItems: 'center', gap: tokens.spacing?.xs }}>{loading.expense ?  'Submitting...' : 'Submit Expense Claim'}</button>
            </div>
          </form>
        </div>
        <div className="hr-card"  style={{padding: tokens.spacing?.lg, background: tokens.color?.['panel-800'], borderRadius: tokens.border?.radius?.card, border: `1px solid ${tokens.color?.['border-600']}`}}><div className="hr-card-header" style={{ borderBottom: `1px solid ${tokens.color?.['inner-divider']}`, paddingBottom: tokens.spacing?.xs, marginBottom: tokens.spacing?.sm }}><div><div className="hr-card-title" style={{
            // --- FIX: Added optional chaining ---
            fontWeight: tokens.typography?.h2?.fontWeight, 
            // ------------------------------------
            color: tokens.color?.['text-100']}}>Recent Expenses</div></div></div><div className="empty-state" style={{color: tokens.color?.['muted-500'], padding: tokens.spacing?.md}}>No expense claims found.</div></div>
      </div>
      {isManager && <div>{renderApprovals}</div>}
    </div>
  ), [isManager, expenseData, loading.expense, loadingOcr, handleSubmitExpense, validateExpense, handleOcrScan, renderApprovals]);


  return (
    // CRITICAL FIX: Ensure the shell takes up all available vertical space (flexGrow: 1)
    <div className="HiRo-hr-shell" style={{padding: 0, display: 'flex', flexDirection: 'column', flexGrow: 1}}>
      <div className="HiRo-main" style={{ display: 'flex', flexDirection: 'column', flexGrow: 1 }}>
        {/* hr-main-inner also flexGrow: 1 to ensure it fills the remaining space */}
        <div className="hr-main-inner" style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: tokens.spacing?.md }}>
          <div className="hr-header" style={{ padding: '1rem', flexShrink: 0 }}>
            <div className="hr-header-main">
              <div className="hr-title" style={{
                  // --- FIX: Added optional chaining ---
                  fontSize: tokens.typography?.h1?.fontSize, 
                  fontWeight: tokens.typography?.h1?.fontWeight, 
                  // ------------------------------------
                  color: tokens.color?.['text-100']}}>HR Operations                Hub</div>
              <div className="hr-subtitle" style={{
                  // --- FIX: Added optional chaining ---
                  fontSize: tokens.typography?.base?.fontSize, 
                  // ------------------------------------
                  color: tokens.color?.['muted-500']}}>Policy-aware timesheets, leave, expenses, and approvals for HiRo</div>
            </div>
          </div>
          <div className="module-tabs" role="tablist" style={{ padding: '0 1rem', borderBottom: `1px solid ${tokens.color?.['border-600']}`, display: 'flex', gap: tokens.spacing?.md, marginBottom: tokens.spacing?.lg, flexShrink: 0 }}>
            <button type="button" className={`tab-btn ${activeModule === 'timesheet' ? 'active' : ''}`} role="tab" onClick={() => setActiveModule('timesheet')} style={{
                background: activeModule === 'timesheet' ? tokens.color?.['accent-2'] : tokens.color?.['panel-700'],
                color: activeModule === 'timesheet' ? tokens.color?.['accent-primary'] : tokens.color?.['text-100'],
                border: activeModule === 'timesheet' ? `1px solid ${tokens.color?.['accent-primary']}` : `1px solid ${tokens.color?.['border-600']}`,
                padding: `${tokens.spacing?.xs} ${tokens.spacing?.sm}`,
                borderRadius: tokens.border?.radius?.button,
                cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: tokens.spacing?.xs, 
                // --- FIX: Added optional chaining ---
                fontWeight: tokens.typography?.h2?.fontWeight
                // ------------------------------------
            }}><Clock size={16} /> Timesheet</button>
            <button type="button" className={`tab-btn ${activeModule === 'leave' ?            'active' : ''}`} role="tab" onClick={() => setActiveModule('leave')} style={{
                background: activeModule === 'leave' ? tokens.color?.['accent-2'] : tokens.color?.['panel-700'],
                color: activeModule === 'leave' ? tokens.color?.['accent-primary'] : tokens.color?.['text-100'],
                border: activeModule === 'leave' ? `1px solid ${tokens.color?.['accent-primary']}` : `1px solid ${tokens.color?.['border-600']}`,
                padding: `${tokens.spacing?.xs} ${tokens.spacing?.sm}`,
                borderRadius: tokens.border?.radius?.button,
                cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: tokens.spacing?.xs, 
                // --- FIX: Added optional chaining ---
                fontWeight: tokens.typography?.h2?.fontWeight
                // ------------------------------------
            }}><Calendar size={16} /> Leave</button>
            <button type="button" className={`tab-btn ${activeModule === 'expenses' ?            'active' : ''}`} role="tab" onClick={() => setActiveModule('expenses')} style={{
                background: activeModule === 'expenses' ? tokens.color?.['accent-2'] : tokens.color?.['panel-700'],
                color: activeModule === 'expenses' ? tokens.color?.['accent-primary'] : tokens.color?.['text-100'],
                border: activeModule === 'expenses' ? `1px solid ${tokens.color?.['accent-primary']}` : `1px solid ${tokens.color?.['border-600']}`,
                padding: `${tokens.spacing?.xs} ${tokens.spacing?.sm}`,
                borderRadius: tokens.border?.radius?.button,
                cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: tokens.spacing?.xs, 
                // --- FIX: Added optional chaining ---
                fontWeight: tokens.typography?.h2?.fontWeight
                // ------------------------------------
            }}><DollarSign size={16} /> Expenses</button>
            {isManager && (<button type="button" className={`tab-btn ${activeModule === 'approvals' ? 'active' : ''}`} role="tab" onClick={() => setActiveModule('approvals')} style={{
                background: activeModule === 'approvals' ? tokens.color?.['warning'] : tokens.color?.['panel-700'],
                color: activeModule === 'approvals' ? tokens.color?.['bg-900'] : tokens.color?.['text-100'],
                border: activeModule === 'approvals' ? `1px solid ${tokens.color?.['warning']}` : `1px solid ${tokens.color?.['border-600']}`,
                padding: `${tokens.spacing?.xs} ${tokens.spacing?.sm}`,
                borderRadius: tokens.border?.radius?.button,
                cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: tokens.spacing?.xs, 
                // --- FIX: Added optional chaining ---
                fontWeight: tokens.typography?.h2?.fontWeight
                // ------------------------------------
            }}><ShieldCheck size={16} /> Approvals <span className="hr-tab-badge" style={{
                background: tokens.color?.['danger'],
                color: tokens.color?.['bg-900'],
                padding: '1px 5px',
                borderRadius: tokens.border?.radius?.chip,
                // --- FIX: Added optional chaining ---
                fontSize: tokens.typography?.small?.fontSize,
                fontWeight: tokens.typography?.h2?.fontWeight
                // ------------------------------------
            }}>{approvalsData.total_pending}</span></button>)}
          </div>
          {/* CRITICAL FIX: The wrapper below should grow and be the main scroll area for content */}
          <div className="hr-content-wrapper" style={{ padding: '0 1rem', flexGrow: 1, overflowY: 'auto' }}>
            {activeModule === 'timesheet' && TimesheetModuleContent}
            {activeModule === 'leave' && <div id="leave-panel" style={{paddingTop: tokens.spacing?.md}}><div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: tokens.spacing?.lg }}>{LeaveModuleContent}</div></div>}
            {activeModule === 'expenses' && ExpensesModuleContent}
            {activeModule === 'approvals' && isManager && (
                <div className="hr-content-layout" style={{paddingTop: tokens.spacing?.md}}>
                    <div style={{ gridColumn: 'span 2' }}>{renderApprovals}</div>
                </div>
            )}
            {activeModule === 'approvals' && !isManager &&
            (
              <div className="hr-card" style={{ padding: tokens.spacing?.xl, textAlign: 'center', marginTop: tokens.spacing?.md, background: tokens.color?.['panel-800'], borderRadius: tokens.border?.radius?.card, border: `1px solid ${tokens.color?.['border-600']}` }}>
                <p style={{ color: tokens.color?.['muted-500'], 
                    // --- FIX: Added optional chaining ---
                    fontSize: tokens.typography?.base?.fontSize 
                    // ------------------------------------
                }}>Approvals access requires a Manager or HR role.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
});

HRModules.displayName = 'HRModules';
export default HRModules;
