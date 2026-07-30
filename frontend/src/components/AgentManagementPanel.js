// /frontend/src/components/AgentManagementPanel.js - FINAL PRODUCTION-READY REPLACEMENT
import React, { useMemo, memo, useState, useCallback } from 'react';
import { theme as tokens } from '../theme';
import { createNewAIAgent, processAgentFinalApproval } from '../config/api'; // CRITICAL FIX: Import stabilized API functions
import { useToast } from '../hooks/use-toast';
import { Zap, Loader2, CheckCircle, XCircle } from 'lucide-react';

const AgentManagementPanel = memo(() => {
    const { toast } = useToast();
    const [agentData, setAgentData] = useState({ name: '', role: 'Governance', model: 'llama3.1:8b' });
    const [isCreating, setIsCreating] = useState(false);
    const [deployId, setDeployId] = useState(null); // ID used for approval step

    // CRITICAL: Handle New Agent Creation
    const handleCreateAgent = useCallback(async (e) => {
        e.preventDefault();
        if (!agentData.name || !agentData.role || isCreating) return;
        
        setIsCreating(true);
        setDeployId(null);

        try {
            // CRITICAL API INTEGRATION 1: Create the new agent
            const response = await createNewAIAgent(agentData);
            
            const newDeployId = response.data.deployment_id || `DEPLOY_${Date.now()}`;
            setDeployId(newDeployId);
            
            toast({ title: 'Agent Queued', description: `Agent "${agentData.name}" created. Pending final deployment approval.`, variant: 'info' });
            setAgentData({ name: '', role: 'Governance', model: 'llama3.1:8b' });
        } catch (error) {
            console.error("Agent creation failed:", error);
            toast({ title: 'Deployment Failed', description: error.response?.data?.detail || error.message, variant: 'destructive' });
        } finally {
            setIsCreating(false);
        }
    }, [agentData, isCreating, toast]);
    
    // CRITICAL: Handle Final Deployment Approval (Simulated)
    const handleFinalApproval = useCallback(async (approved) => {
        if (!deployId) return;
        
        const action = approved ? 'Approved' : 'Rejected';
        if (!window.confirm(`Are you sure you want to ${action} deployment ${deployId}?`)) return;

        try {
            // CRITICAL API INTEGRATION 2: Process the final approval step
            await processAgentFinalApproval(deployId, 'HRIT_PROJECT', approved, `Final HRIT sign-off: ${action}`);
            
            toast({ title: `Deployment ${action}`, description: `Agent deployment ${deployId} finalized.`, variant: approved ? 'success' : 'danger' });
            setDeployId(null);
        } catch (error) {
            console.error("Approval failed:", error);
            toast({ title: 'Approval Error', description: error.response?.data?.detail || error.message, variant: 'destructive' });
        }
    }, [deployId, toast]);


    const styles = useMemo(() => ({
        container: { padding: tokens.spacing?.md, background: tokens.color?.['panel-800'], borderRadius: tokens.border?.radius?.card, minHeight: '400px' },
        input: { width: '100%', padding: '10px', background: tokens.color?.['bg-input'], border: `1px solid ${tokens.color?.['border-600']}`, borderRadius: tokens.border?.radius?.input, color: tokens.color?.['text-100'], boxSizing: 'border-box', marginBottom: tokens.spacing?.md },
        button: (bgColor) => ({ padding: '10px 20px', background: bgColor, border: 'none', borderRadius: tokens.border?.radius?.button, color: tokens.color?.['bg-deep'], cursor: 'pointer', transition: 'all 0.2s ease', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: tokens.spacing?.xs, width: '100%' }),
        approvalBar: { border: `2px dashed ${tokens.color?.warning}`, padding: tokens.spacing?.md, borderRadius: tokens.border?.radius?.input, marginTop: tokens.spacing?.lg, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }
    }), []);

    return (
        <div style={styles.container}>
            <h2 style={{ color: tokens.color?.['text-100'], margin: '0 0 20px 0' }}>AI Agent Deployment & Management</h2>
            
            <form onSubmit={handleCreateAgent}>
                <input type="text" placeholder="Agent Name" style={styles.input} value={agentData.name} onChange={e => setAgentData(p => ({ ...p, name: e.target.value }))} required />
                <select style={styles.input} value={agentData.role} onChange={e => setAgentData(p => ({ ...p, role: e.target.value }))}>
                    <option value="Governance">Policy Governance Agent</option>
                    <option value="Remediation">Autonomous Healing Agent</option>
                    <option value="XAI">XAI & Simulation Agent</option>
                </select>
                <select style={styles.input} value={agentData.model} onChange={e => setAgentData(p => ({ ...p, model: e.target.value }))}>
                    <option value="llama3.1:8b">Llama 3.1 8B (Default)</option>
                    <option value="qwen2.5-coder:7b">Qwen 2.5 Coder 7B</option>
                    <option value="mistral:7b-instruct">Mistral 7B Instruct</option>
                </select>
                <button type="submit" style={styles.button(tokens.color?.['accent-primary'])} disabled={isCreating} className="agent-create-hover">
                    {isCreating ? <Loader2 size={16} className="animate-spin" /> : <Zap size={16} />}
                    {isCreating ? 'Requesting Deployment...' : 'Create New Agent'}
                </button>
            </form>

            {/* Deployment Approval Step (Appears after creation) */}
            {deployId && (
                <div style={styles.approvalBar}>
                    <div style={{ color: tokens.color?.warning }}>
                        Deployment **{deployId}** pending final approval.
                    </div>
                    <div style={{ display: 'flex', gap: tokens.spacing?.sm }}>
                        <button onClick={() => handleFinalApproval(true)} style={{...styles.button(tokens.color?.success), width: 'auto', color: tokens.color?.['bg-deep']}} className="agent-approve-hover">
                            <CheckCircle size={16} /> Approve
                        </button>
                        <button onClick={() => handleFinalApproval(false)} style={{...styles.button(tokens.color?.danger), width: 'auto', color: tokens.color?.['text-100'], background: tokens.color?.['danger-700']}} className="agent-reject-hover">
                            <XCircle size={16} /> Reject
                        </button>
                    </div>
                </div>
            )}
            
            <style>{`
                .agent-create-hover:hover { box-shadow: 0 0 10px ${tokens.color?.['accent-primary']}77; transform: translateY(-1px); }
                .agent-approve-hover:hover { box-shadow: 0 0 10px ${tokens.color?.success}77; transform: translateY(-1px); }
                .agent-reject-hover:hover { background: ${tokens.color?.danger} !important; box-shadow: 0 0 10px ${tokens.color?.danger}77; transform: translateY(-1px); }
            `}</style>
        </div>
    );
});

AgentManagementPanel.displayName = 'AgentManagementPanel';
export default AgentManagementPanel;