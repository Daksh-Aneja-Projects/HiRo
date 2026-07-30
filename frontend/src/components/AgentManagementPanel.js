// /frontend/src/components/AgentManagementPanel.js
// Intent-driven agent factory. The backend plans the agent itself from a natural
// language brief, so this sends { intent } and nothing else. The local model does the
// planning, which takes tens of seconds on CPU, hence the visible in-flight state.
import React, { memo, useState, useCallback, useEffect, useRef } from 'react';
import { theme as tokens } from '../theme';
import { createNewAIAgent, processAgentFinalApproval } from '../config/api';
import { useToast } from '../hooks/use-toast';
import { ui, Btn, EmptyState } from './employee/shared';
import { Bot, Sparkles, CheckCircle, XCircle, Info } from 'lucide-react';

const errText = (e) => e?.response?.data?.detail || e?.message || 'The request failed.';

const EXAMPLES = [
    'Watch every compensation change over ten percent and notify the HRIT team before it is applied.',
    'Audit policy edits each night and raise a case when a change has no approver recorded.',
    'Summarise open HR service tickets each morning and flag any breaching their response time.',
];

const AgentManagementPanel = memo(() => {
    const { toast } = useToast();
    const [intent, setIntent] = useState('');
    const [isCreating, setIsCreating] = useState(false);
    const [elapsed, setElapsed] = useState(0);
    const [deployment, setDeployment] = useState(null);
    const [approving, setApproving] = useState(false);
    const timerRef = useRef(null);

    useEffect(() => () => clearInterval(timerRef.current), []);

    const handleCreate = useCallback(async (e) => {
        e.preventDefault();
        if (!intent.trim() || isCreating) return;

        setIsCreating(true);
        setElapsed(0);
        setDeployment(null);
        clearInterval(timerRef.current);
        timerRef.current = setInterval(() => setElapsed((s) => s + 1), 1000);

        try {
            const res = await createNewAIAgent({ intent: intent.trim() });
            const body = res.data || {};
            setDeployment({
                taskId: body.task_id || null,
                agentId: body.agent_id || null,
                bpmnId: body.bpmn_id || null,
                // The create response carries no project reference today. The sign-off
                // controls only appear if the backend starts sending one, so nothing
                // here invents an identifier.
                projectId: body.project_id || body.final_agent_config?.project_id || null,
                name: body.final_agent_config?.agent_name || null,
                instructions: body.final_agent_config?.instructions_prompt || null,
                tools: (body.final_agent_config?.tools || []).map((t) => t?.name).filter(Boolean),
                model: body.final_agent_config?.model || null,
            });
            toast({
                title: 'Agent planned and queued',
                description: body.final_agent_config?.agent_name
                    ? `${body.final_agent_config.agent_name} was designed from your brief and sent into the deployment pipeline.`
                    : 'The agent was designed from your brief and sent into the deployment pipeline.',
                variant: 'success',
            });
            setIntent('');
        } catch (err) {
            toast({ title: 'The agent could not be created', description: errText(err), variant: 'destructive' });
        } finally {
            clearInterval(timerRef.current);
            setIsCreating(false);
        }
    }, [intent, isCreating, toast]);

    const handleApproval = useCallback(async (approved) => {
        if (!deployment?.taskId || !deployment?.projectId) return;
        const word = approved ? 'approve' : 'reject';
        if (!window.confirm(`Are you sure you want to ${word} the deployment of ${deployment.name || deployment.agentId}?`)) return;
        setApproving(true);
        try {
            await processAgentFinalApproval(deployment.taskId, deployment.projectId, approved, `Final HRIT sign-off: ${approved ? 'approved' : 'rejected'}`);
            toast({
                title: approved ? 'Deployment approved' : 'Deployment rejected',
                description: approved ? 'The agent will now be rolled out.' : 'The agent will not be rolled out.',
                variant: approved ? 'success' : 'destructive',
            });
            setDeployment(null);
        } catch (err) {
            toast({ title: 'The decision could not be recorded', description: errText(err), variant: 'destructive' });
        } finally {
            setApproving(false);
        }
    }, [deployment, toast]);

    return (
        <div style={{ ...ui.panel, height: '100%' }}>
            <h3 style={ui.h3}>
                <Bot size={15} style={{ marginRight: 7, verticalAlign: '-2px' }} color={tokens.color?.['accent-primary']} />
                Describe the agent you need
            </h3>
            <p style={ui.hint}>
                Write what the agent should do in plain English. The local model designs the agent, picks the tools it may
                use and sends it into the deployment pipeline. Planning runs on this machine and usually takes under a minute.
            </p>

            <form onSubmit={handleCreate} style={{ marginTop: tokens.spacing?.md }}>
                <label style={ui.label} htmlFor="agent-intent">What should it do</label>
                <textarea
                    id="agent-intent"
                    style={{ ...ui.input, minHeight: 120, resize: 'vertical', fontFamily: tokens.typography?.fontFamily }}
                    value={intent}
                    onChange={(e) => setIntent(e.target.value)}
                    placeholder={EXAMPLES[0]}
                    disabled={isCreating}
                    required
                />
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, margin: '10px 0 14px 0' }}>
                    {EXAMPLES.map((ex) => (
                        <button
                            key={ex}
                            type="button"
                            onClick={() => setIntent(ex)}
                            disabled={isCreating}
                            className="emp-btn"
                            style={{
                                padding: '5px 10px', borderRadius: tokens.border?.radius?.full,
                                border: `1px solid ${tokens.color?.['border-600']}`, background: 'transparent',
                                color: tokens.color?.['muted-600'], fontSize: '11.5px',
                                fontFamily: tokens.typography?.fontFamily, cursor: isCreating ? 'not-allowed' : 'pointer',
                                maxWidth: '100%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                            }}
                        >
                            {ex.length > 52 ? `${ex.slice(0, 52)}...` : ex}
                        </button>
                    ))}
                </div>
                <Btn type="submit" icon={Sparkles} loading={isCreating} disabled={!intent.trim()}>
                    {isCreating ? `Designing the agent, ${elapsed}s elapsed` : 'Design and deploy this agent'}
                </Btn>
            </form>

            {isCreating && (
                <p style={{ ...ui.hint, color: tokens.color?.warning }}>
                    The model is reading your brief and writing the agent's configuration. Leave this page open until it finishes.
                </p>
            )}

            {!isCreating && !deployment && (
                <div style={{ marginTop: tokens.spacing?.md }}>
                    <EmptyState icon={Bot} title="No agent designed in this session" action="Describe a job above and the factory will build an agent for it." />
                </div>
            )}

            {deployment && (
                <div style={{
                    marginTop: tokens.spacing?.md, padding: '12px 14px',
                    borderRadius: tokens.border?.radius?.input,
                    border: `1px solid ${tokens.color?.success}33`, background: `${tokens.color?.success}0d`,
                }}>
                    <div style={{ ...ui.rowTitle, whiteSpace: 'normal', marginBottom: 6 }}>
                        {deployment.name || 'The new agent'} is queued for rollout
                    </div>
                    <p style={{ ...ui.hint, margin: 0 }}>
                        {deployment.instructions ? `${deployment.instructions} ` : ''}
                        {deployment.tools.length > 0
                            ? `It is allowed to use ${deployment.tools.length} tool${deployment.tools.length === 1 ? '' : 's'}: ${deployment.tools.join(', ').replace(/_/g, ' ')}. `
                            : 'It was given no tools to call. '}
                        {deployment.model ? `It runs on the ${deployment.model} model. ` : ''}
                        The rollout is tracked as {deployment.taskId || 'an unnamed task'}.
                    </p>

                    {deployment.projectId ? (
                        <div style={{ display: 'flex', gap: tokens.spacing?.xs, marginTop: tokens.spacing?.md, flexWrap: 'wrap' }}>
                            <Btn tone="success" icon={CheckCircle} loading={approving} onClick={() => handleApproval(true)}>Approve the rollout</Btn>
                            <Btn tone="danger" icon={XCircle} loading={approving} onClick={() => handleApproval(false)}>Reject it</Btn>
                        </div>
                    ) : (
                        <p style={{ ...ui.hint, display: 'flex', gap: 7, alignItems: 'flex-start', marginTop: 10 }}>
                            <Info size={14} style={{ flexShrink: 0, marginTop: 2 }} />
                            Final sign-off is not available from here. The deployment pipeline owns this step and the platform
                            does not yet tell this console which project the rollout belongs to.
                        </p>
                    )}
                </div>
            )}
        </div>
    );
});

AgentManagementPanel.displayName = 'AgentManagementPanel';
export default AgentManagementPanel;
