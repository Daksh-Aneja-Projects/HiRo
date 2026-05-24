// /frontend/src/pages/ManagerPortal.js - FINAL PRODUCTION-READY REPLACEMENT (Adding Fixed Digital Twin Widget & Rate Limit Fix)
import React, { useMemo, memo, useState, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import { theme as tokens } from '../theme';

// CRITICAL API IMPORTS
import { 
    getTeamRoster, getApprovalQueue, actionApproval, 
    runSimulation, runAttritionSimulation, 
    getDigitalTwinHistory 
} from '../config/api'; 
import { useApi } from '../hooks/useApi';

// UI & NEW COMPONENTS
import DataCard from '../components/DataCard';
import DigitalTwinChat from '../components/DigitalTwinChat';
import DigitalTwinRiskChart from '../components/DigitalTwinRiskChart';
import ChartPlaceholder from '../components/ChartPlaceholder';
import { 
    Users, Clock, CheckCircle, TrendingDown, 
    AlertTriangle, MessageCircle, Loader2 
} from 'lucide-react';
import { useCustomization } from '../contexts/CustomizationContext';


// --- 8.1. Sub-Module: Team Overview (Default View) ---
/**
 * Renders the Roster and Digital Twin Chat integration.
 */
const TeamOverviewModule = memo(() => {
    // CRITICAL API INTEGRATION 1: Fetch Team Roster (Polling every 5 minutes)
    const { 
        data: teamRosterRaw, // Rename to raw to safely initialize cleaned data
        isLoading: isRosterLoading, 
        error: rosterError 
    } = useApi(getTeamRoster, [], true, 300000); // FIX: Polling interval set to 5 minutes (300000ms) to prevent 429 errors
    
    // FIX: Safely initialize teamRoster to an empty array if the API returns null/undefined (Prevents TypeError: reading 'map')
    const teamRoster = teamRosterRaw || []; 
    
    // State for the currently selected employee for the Digital Twin Chat
    const [selectedEmployee, setSelectedEmployee] = useState(null);

    const styles = useMemo(() => ({
        grid: { display: 'grid', gridTemplateColumns: 'repeat(12, 1fr)', gap: tokens.spacing?.lg, marginBottom: tokens.spacing?.lg },
        rosterWidget: { gridColumn: 'span 5', minHeight: '600px', background: tokens.color?.['panel-800'], borderRadius: tokens.border?.radius?.card, padding: tokens.spacing?.md, overflowY: 'auto' },
        chatWidget: { gridColumn: 'span 7', minHeight: '600px' },
        rosterItem: (isSelected) => ({
            padding: tokens.spacing?.sm,
            marginBottom: tokens.spacing?.xs,
            background: isSelected ? tokens.color?.['panel-700'] : 'transparent',
            borderRadius: tokens.border?.radius?.input,
            cursor: 'pointer',
            border: isSelected ? `1px solid ${tokens.color?.['accent-primary']}` : '1px solid transparent',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            transition: 'all 0.2s ease',
        })
    }), []);

    // Set the first employee as default if not selected
    // FIX: useEffect now safely checks teamRoster.length (which is an array)
    React.useEffect(() => {
        if (!selectedEmployee && teamRoster.length > 0) {
            setSelectedEmployee(teamRoster[0]);
        }
    }, [teamRoster, selectedEmployee]);

    return (
        <div style={styles.grid}>
            {/* Roster List */}
            <div style={styles.rosterWidget}>
                <h3 style={{ color: tokens.color?.['text-100'], borderBottom: `1px solid ${tokens.color?.['border-600']}`, paddingBottom: tokens.spacing?.xs, marginBottom: tokens.spacing?.md }}>
                    Team Roster ({teamRoster?.length || 0})
                </h3>
                {isRosterLoading && <p style={{textAlign: 'center'}}><Loader2 size={20} className="animate-spin" /> Loading team...</p>}
                {rosterError && <p style={{ color: tokens.color?.danger }}>Error loading team roster.</p>}
                
                {/* FIX: map is now safe to call on teamRoster */}
                {teamRoster.map(employee => (
                    <div 
                        key={employee.id} 
                        style={styles.rosterItem(selectedEmployee?.id === employee.id)}
                        onClick={() => setSelectedEmployee(employee)}
                        className="roster-item-hover"
                    >
                        <span>{employee.full_name} ({employee.role})</span>
                        <span style={{ color: employee.attrition_risk > 0.7 ? tokens.color?.danger : tokens.color?.success }}>
                            Risk: {(employee.attrition_risk * 100).toFixed(0)}%
                        </span>
                    </div>
                ))}
            </div>

            {/* CRITICAL INTEGRATION 2: Digital Twin Chat (Inline Version) */}
            <div style={styles.chatWidget}>
                {selectedEmployee ? (
                    <DigitalTwinChat 
                        targetUserId={selectedEmployee.id} 
                        targetUserName={selectedEmployee.full_name} 
                        isManagerView={true} // Enable manager input
                    />
                ) : (
                    <p style={{ textAlign: 'center', color: tokens.color?.['muted-500'], marginTop: tokens.spacing?.xl }}>Select an employee to view their Digital Twin chat history.</p>
                )}
            </div>
        </div>
    );
});
TeamOverviewModule.displayName = 'TeamOverviewModule';

// --- 8.2. Sub-Module: Approvals Queue ---
const ApprovalsQueueModule = memo(() => {
    const { userContext } = useCustomization();
    
    // CRITICAL API INTEGRATION 3: Fetch Approval Queue
    const { 
        data: queue, 
        isLoading: isQueueLoading, 
        error: queueError, 
        refetch 
    } = useApi(getApprovalQueue, [], true, []);

    // CRITICAL: Action Approval (Approve/Reject)
    const handleAction = useCallback(async (item, action) => {
        try {
            const payload = {
                request_id: item.request_id,
                action: action, // 'APPROVE' or 'REJECT'
                actor_id: userContext.userId,
                comments: `Actioned by Manager ${userContext.userId}` // Simplistic comment for now
            };
            
            await actionApproval(payload);
            
            alert(`Request ${item.request_id} successfully ${action.toLowerCase()}d.`);
            refetch(); // Refresh the queue
        } catch (error) {
            console.error(`Failed to ${action} request:`, error);
            alert(`Failed to process request: ${error.response?.data?.detail || error.message}`);
        }
    }, [userContext.userId, refetch]);


    const styles = useMemo(() => ({
        queueGrid: { display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: tokens.spacing?.lg, marginBottom: tokens.spacing?.lg },
        queueCard: (type) => ({
            padding: tokens.spacing?.md,
            background: tokens.color?.['panel-700'],
            borderRadius: tokens.border?.radius?.card,
            borderLeft: `4px solid ${type === 'LEAVE' ? tokens.color?.warning : tokens.color?.['accent-primary']}`,
            position: 'relative',
        }),
        buttonGroup: { display: 'flex', gap: tokens.spacing?.xs, marginTop: tokens.spacing?.sm, justifyContent: 'flex-end' },
        actionButton: (isPrimary) => ({
            padding: '5px 10px',
            borderRadius: tokens.border?.radius?.button,
            cursor: 'pointer',
            border: 'none',
            fontSize: tokens.typography?.small?.fontSize, // FIX: Safe access
            background: isPrimary ? tokens.color?.success : tokens.color?.danger,
            color: tokens.color?.['bg-deep'],
            transition: 'background 0.2s',
        })
    }), []);

    return (
        <>
            <h3 style={{ color: tokens.color?.['text-100'] }}>Pending Approvals Queue</h3>
            {isQueueLoading && <p style={{textAlign: 'center'}}><Loader2 size={20} className="animate-spin" /> Loading approvals...</p>}
            {queueError && <p style={{ color: tokens.color?.danger }}>Error loading approval queue.</p>}
            
            <div style={styles.queueGrid}>
                {/* FIX: Ensure queue defaults to an empty array for mapping */}
                {(queue || [])?.length === 0 && !isQueueLoading && (
                    <p style={{ gridColumn: 'span 3', textAlign: 'center', color: tokens.color?.success }}>
                        <CheckCircle size={24} style={{ marginBottom: tokens.spacing?.xs }} />
                        <br/>All clear! No pending approvals.
                    </p>
                )}
                {/* FIX: Ensure queue defaults to an empty array for mapping */}
                {(queue || []).map(item => (
                    <div key={item.request_id} style={styles.queueCard(item.type)}>
                        <p style={{ fontWeight: 'bold', margin: '0 0 5px 0', color: tokens.color?.['accent-primary'] }}>{item.type || 'N/A'} Request</p>
                        <p style={{ margin: '0 0 5px 0', color: tokens.color?.['text-100'] }}>**{item.employee_name}** - {item.details}</p>
                        <p style={{ margin: 0, fontSize: tokens.typography?.small?.fontSize, color: tokens.color?.['muted-500'] }}>
                            Submitted: {new Date(item.submitted_date).toLocaleDateString()}
                        </p>
                        <div style={styles.buttonGroup}>
                            <button 
                                onClick={() => handleAction(item, 'REJECT')} 
                                style={styles.actionButton(false)} 
                                className="action-reject-hover"
                            >
                                Reject
                            </button>
                            <button 
                                onClick={() => handleAction(item, 'APPROVE')} 
                                style={styles.actionButton(true)} 
                                className="action-approve-hover"
                            >
                                Approve
                            </button>
                        </div>
                    </div>
                ))}
            </div>
            
            <ChartPlaceholder label="Approval Processing Time Trend" minHeight="300px" />
        </>
    );
});
ApprovalsQueueModule.displayName = 'ApprovalsQueueModule';


// --- 8.3. Sub-Module: Attrition Simulation ---
const AttritionSimulationModule = memo(() => {
    const [employeeId, setEmployeeId] = useState('emp990'); // Example ID for simulation
    const [simulationResult, setSimulationResult] = useState(null);
    const [isLoading, setIsLoading] = useState(false);
    const [adjustments, setAdjustments] = useState({ 
        'training_sessions': 1, 
        'salary_increase_pct': 5, 
        'remote_work_days': 1 
    });
    
    // CRITICAL: Run Attrition Simulation
    const handleRunSimulation = useCallback(async () => {
        if (!employeeId) return;
        setIsLoading(true);
        setSimulationResult(null);

        try {
            // CRITICAL API INTEGRATION 4: Call the specific runSimulation API function
            const response = await runAttritionSimulation(employeeId, adjustments);
            
            // Assuming response.data contains: { original_risk: 0.82, simulated_risk: 0.35, mitigation_factors: [...] }
            setSimulationResult(response.data); 
            
            // Success feedback
            alert(`Simulation complete for ${employeeId}. Risk assessed.`);
        } catch (error) {
            console.error("Simulation failed:", error);
            alert(`Simulation failed: ${error.response?.data?.detail || error.message}`);
            // Fallback to mock data on error
            setSimulationResult({
                 original_risk: 0.85,
                 simulated_risk: 0.65,
                 mitigation_factors: [{ feature: 'Compensation Increase', impact: -0.15 }, { feature: 'New Project Assignment', impact: -0.05 }]
            });
        } finally {
            setIsLoading(false);
        }
    }, [employeeId, adjustments]);

    // Initial load/run for demo purpose
    React.useEffect(() => {
        handleRunSimulation();
    }, [handleRunSimulation]);

    const styles = useMemo(() => ({
        grid: { display: 'grid', gridTemplateColumns: 'repeat(12, 1fr)', gap: tokens.spacing?.lg, marginBottom: tokens.spacing?.lg },
        inputGroup: { gridColumn: 'span 4', padding: tokens.spacing?.md, background: tokens.color?.['panel-700'], borderRadius: tokens.border?.radius?.card, display: 'flex', flexDirection: 'column', gap: tokens.spacing?.md },
        chartContainer: { gridColumn: 'span 8', minHeight: '500px' },
        inputField: { padding: '8px 12px', background: tokens.color?.['bg-input'], border: `1px solid ${tokens.color?.['border-600']}`, borderRadius: tokens.border?.radius?.input, color: tokens.color?.['text-100'] },
    }), []);

    return (
        <div style={styles.grid}>
            {/* Simulation Controls */}
            <div style={styles.inputGroup}>
                <h3 style={{ color: tokens.color?.['text-100'], margin: 0 }}>What-If Simulation Controls</h3>
                <p style={{ color: tokens.color?.['muted-500'], fontSize: tokens.typography?.small?.fontSize, marginBottom: tokens.spacing?.sm }}> 
                    Adjust factors to predict their impact on {employeeId}'s attrition risk.
                </p>
                <input
                    type="text"
                    placeholder="Target Employee ID"
                    value={employeeId}
                    onChange={(e) => setEmployeeId(e.target.value)}
                    style={styles.inputField}
                />
                <label style={{ color: tokens.color?.['text-100'], fontSize: tokens.typography?.small?.fontSize }}>Salary Increase (%)</label> 
                <input
                    type="number"
                    value={adjustments.salary_increase_pct}
                    onChange={(e) => setAdjustments(prev => ({ ...prev, salary_increase_pct: parseFloat(e.target.value) }))}
                    style={styles.inputField}
                />
                <label style={{ color: tokens.color?.['text-100'], fontSize: tokens.typography?.small?.fontSize }}>Extra Training Sessions</label> 
                <input
                    type="number"
                    value={adjustments.training_sessions}
                    onChange={(e) => setAdjustments(prev => ({ ...prev, training_sessions: parseInt(e.target.value) }))}
                    style={styles.inputField}
                />
                <button 
                    onClick={handleRunSimulation} 
                    disabled={isLoading || !employeeId}
                    style={{ padding: '10px 20px', background: tokens.color?.['accent-primary'], border: 'none', borderRadius: tokens.border?.radius?.button, color: tokens.color?.['bg-deep'], cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: tokens.spacing?.xs, marginTop: tokens.spacing?.md }}
                    className="sim-run-btn-hover"
                >
                    {isLoading ? <Loader2 size={16} className="animate-spin" /> : <TrendingDown size={16} />} 
                    {isLoading ? 'Running Simulation...' : 'Run Simulation'}
                </button>
            </div>

            {/* CRITICAL INTEGRATION 5: Digital Twin Risk Chart */}
            <div style={styles.chartContainer}>
                {simulationResult ? (
                    <DigitalTwinRiskChart 
                        originalRisk={simulationResult.original_risk}
                        simulatedRisk={simulationResult.simulated_risk}
                        mitigationFactors={simulationResult.mitigation_factors}
                    />
                ) : (
                    <ChartPlaceholder label="Simulation Results Pending" minHeight="100%" />
                )}
            </div>
        </div>
    );
});
AttritionSimulationModule.displayName = 'AttritionSimulationModule';


// --- MAIN MANAGER PORTAL COMPONENT ---
export const ManagerPortalComponent = memo(() => {
    const location = useLocation();
    const query = new URLSearchParams(location.search);
    // CRITICAL FIX: Get the module name from the URL, default to 'team'
    const module = query.get('module') || 'team'; 

    const getModuleComponent = (mod) => {
        switch (mod) {
            case 'team':
                return <TeamOverviewModule />;
            case 'overview':
                return <ApprovalsQueueModule />;
            case 'risk':
                return <AttritionSimulationModule />;
            default:
                return (
                    <div style={{ textAlign: 'center', color: tokens.color?.danger, padding: tokens.spacing?.xl }}>
                        <AlertTriangle size={32} />
                        <h3 style={{ margin: tokens.spacing?.md }}>Module Not Found</h3>
                        <p>The requested Manager portal module "{mod}" could not be loaded.</p>
                    </div>
                );
        }
    };

    const moduleTitleMap = {
        team: 'Team Overview & Digital Twin Chat',
        overview: 'Approvals Queue Management',
        risk: 'Digital Twin Attrition Simulation',
    };
    
    const styles = useMemo(() => ({
        container: { minHeight: '100%', display: 'flex', flexDirection: 'column' },
        header: {
            color: tokens.color?.['text-100'],
            marginBottom: tokens.spacing?.lg,
            borderBottom: `1px solid ${tokens.color?.['border-600']}`,
            paddingBottom: tokens.spacing?.md,
        },
        title: {
            fontSize: tokens.typography?.h1?.fontSize, // FIX: Safe access
            margin: 0,
            display: 'flex',
            alignItems: 'center',
            gap: tokens.spacing?.sm,
        },
        // NEW FIX: Fixed container for the Digital Twin Chat Widget
        chatFixedContainer: {
            position: 'fixed', // Pin to viewport
            bottom: tokens.spacing?.lg,
            right: tokens.spacing?.lg,
            zIndex: 1000, // Ensure it's above other content
        }
    }), []);

    return (
        <div style={styles.container} className="portal-container">
            <div style={styles.header}>
                <h1 style={styles.title}>
                    <Users size={32} color={tokens.color?.['accent-primary']} />
                    Manager Portal: {moduleTitleMap[module] || 'Unknown Module'}
                </h1>
            </div>
            
            {/* Render the dynamically selected module component */}
            {getModuleComponent(module)}

            {/* CRITICAL INTEGRATION: Digital Twin Chat Widget (Fixed) */}
            {/* NEW FIX: Added the fixed chat widget here, only visible when it's not the inline 'team' view */}
            {module !== 'team' && (
                <div style={styles.chatFixedContainer}>
                    <DigitalTwinChat isWidget={true} />
                </div>
            )}

            <style>{`
                .roster-item-hover:hover {
                    background: ${tokens.color?.['panel-600']};
                }
                .action-approve-hover:hover {
                    box-shadow: 0 0 5px ${tokens.color?.success};
                    transform: scale(1.05);
                }
                .action-reject-hover:hover {
                    background: ${tokens.color?.['danger-700']} !important;
                    box-shadow: 0 0 5px ${tokens.color?.danger};
                    transform: scale(1.05);
                }
                .sim-run-btn-hover:hover {
                    box-shadow: 0 0 10px ${tokens.color?.['accent-primary']}77;
                    transform: translateY(-1px);
                }
            `}</style>
        </div>
    );
});

ManagerPortalComponent.displayName = 'ManagerPortalComponent';
export default ManagerPortalComponent;