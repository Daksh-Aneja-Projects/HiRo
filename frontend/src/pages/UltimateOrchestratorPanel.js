// /frontend/src/pages/UltimateOrchestratorPanel.js - Orchestrator control for HRIT_ADMIN.
// Modules: command | history | danger. Commands are routed through the local language
// model, so every model-backed action shows a visible in-flight state with an elapsed
// timer. Nothing on this page is simulated.
import React, { useMemo, memo, useState, useCallback, useRef, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { theme as tokens } from '../theme';

import {
    runOrchestrationCommand, getCommandHistory, getOrchestrationResultStatus,
    getProcessExecutionHistory, executeRLFFCommand, resetAllData, getOrchestratorDashboardData,
} from '../config/api';
import { useApi } from '../hooks/useApi';
import { useToast } from '../hooks/use-toast';
import { useAuth } from '../contexts/AuthContext';

import DataCard from '../components/DataCard';
import BarChartWidget from '../components/charts/BarChartWidget';
import AreaChartWidget from '../components/charts/AreaChartWidget';
import { CountUp, LiveMeter, useMetricSeries } from '../components/live/LivePrimitives';
import { countBy } from '../utils/chartData';
import { PortalHeader, UnknownModule, portalShell } from '../components/admin/PortalHeader';
import { ui, Btn, Loading, EmptyState, ErrorNote, EmployeeStyles, fmtDate } from '../components/employee/shared';
import {
    Terminal, History, ShieldAlert, Play, Bot, Gauge, Radio, Sparkles,
    Skull, Snowflake, RotateCcw, ListChecks, ArrowLeft,
} from 'lucide-react';

const MODULES = [
    { key: 'command', label: 'Command', icon: Terminal },
    { key: 'history', label: 'History', icon: History },
    { key: 'danger', label: 'Danger zone', icon: ShieldAlert },
];

const errText = (e) => e?.response?.data?.detail || e?.message || 'The request failed.';

// Every model-backed action needs a visible clock: on CPU these take tens of seconds.
const useElapsed = (running) => {
    const [s, setS] = useState(0);
    const ref = useRef(null);
    useEffect(() => {
        if (!running) { clearInterval(ref.current); return undefined; }
        setS(0);
        ref.current = setInterval(() => setS((n) => n + 1), 1000);
        return () => clearInterval(ref.current);
    }, [running]);
    return s;
};

/* ------------------------------------------------------------------ */
/* Command                                                             */
/* ------------------------------------------------------------------ */
const SUGGESTIONS = [
    'Which department has the highest attrition risk?',
    'Summarise the open HR service cases and tell me which are overdue.',
    'Check whether any compensation change this month skipped an approver.',
];

const CommandModule = memo(() => {
    const { toast } = useToast();
    const { user } = useAuth();
    const [prompt, setPrompt] = useState('');
    const [running, setRunning] = useState(false);
    const [result, setResult] = useState(null);
    const elapsed = useElapsed(running);

    const { data: orch } = useApi(getOrchestratorDashboardData, [], true, 15000);
    const cpuSeries = useMetricSeries('cpu_load', { intervalMs: 3000 });

    const handleRun = useCallback(async (e) => {
        e.preventDefault();
        if (!prompt.trim() || running) return;
        setRunning(true);
        setResult(null);
        try {
            const res = await runOrchestrationCommand(prompt.trim(), { user_id: user?.username, username: user?.username });
            const body = res.data || {};
            setResult({
                id: body.result_id || null,
                agent: body.agent || null,
                summary: body.summary || '',
                status: body.status || 'UNKNOWN',
                prompt: prompt.trim(),
            });
            toast({
                title: 'The orchestrator answered',
                description: body.agent ? `${body.agent} picked this up.` : 'The command was routed and answered.',
                variant: 'success',
            });
        } catch (err) {
            toast({ title: 'The command could not be run', description: errText(err), variant: 'destructive' });
        } finally {
            setRunning(false);
        }
    }, [prompt, running, user, toast]);

    return (
        <div style={ui.grid}>
            <div style={{ ...ui.panel, gridColumn: 'span 5' }}>
                <h3 style={ui.h3}>Ask the orchestrator</h3>
                <p style={ui.hint}>
                    Write what you want in plain English. The orchestrator decides which agent should handle it and answers
                    using the model running on this machine. Nothing is sent to an outside service.
                </p>
                <form onSubmit={handleRun} style={{ marginTop: tokens.spacing?.md }}>
                    <label style={ui.label} htmlFor="orch-prompt">Your request</label>
                    <textarea
                        id="orch-prompt"
                        style={{ ...ui.input, minHeight: 130, resize: 'vertical', fontFamily: tokens.typography?.fontFamily }}
                        value={prompt}
                        onChange={(ev) => setPrompt(ev.target.value)}
                        placeholder={SUGGESTIONS[0]}
                        disabled={running}
                        required
                    />
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, margin: '10px 0 14px 0' }}>
                        {SUGGESTIONS.map((s) => (
                            <button
                                key={s}
                                type="button"
                                disabled={running}
                                onClick={() => setPrompt(s)}
                                className="emp-btn"
                                style={{
                                    padding: '5px 10px', borderRadius: tokens.border?.radius?.full,
                                    border: `1px solid ${tokens.color?.['border-600']}`, background: 'transparent',
                                    color: tokens.color?.['muted-600'], fontSize: '11.5px',
                                    fontFamily: tokens.typography?.fontFamily, cursor: running ? 'not-allowed' : 'pointer',
                                    maxWidth: '100%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                                }}
                            >
                                {s.length > 46 ? `${s.slice(0, 46)}...` : s}
                            </button>
                        ))}
                    </div>
                    <Btn type="submit" icon={Play} loading={running} disabled={!prompt.trim()}>
                        {running ? `Thinking, ${elapsed}s elapsed` : 'Send it to the orchestrator'}
                    </Btn>
                </form>
            </div>

            <div style={{ ...ui.panel, gridColumn: 'span 7', display: 'flex', flexDirection: 'column', minHeight: 320 }}>
                <h3 style={ui.h3}>The answer</h3>
                {running && (
                    <div style={{ marginTop: tokens.spacing?.md }}>
                        <p style={{ ...ui.hint, color: tokens.color?.warning }}>
                            The model is reading your request and deciding which agent should own it. On this machine that
                            normally takes between ten seconds and a minute. {elapsed} second{elapsed === 1 ? '' : 's'} so far.
                        </p>
                        <div style={{ marginTop: tokens.spacing?.md }}>
                            <LiveMeter pct={cpuSeries.length ? cpuSeries[cpuSeries.length - 1].value : 0} label="Processor load while it works" color={tokens.color?.warning} />
                        </div>
                        <div style={{ marginTop: tokens.spacing?.md }}>
                            <AreaChartWidget data={cpuSeries} minHeight="150px" color={tokens.color?.warning} />
                        </div>
                    </div>
                )}
                {!running && !result && (
                    <EmptyState icon={Terminal} title="Nothing has been asked yet" action="Write a request on the left and the orchestrator's answer will appear here." />
                )}
                {!running && result && (
                    <div style={{ marginTop: tokens.spacing?.md }}>
                        <p style={{ ...ui.rowTitle, whiteSpace: 'normal', marginBottom: 8 }}>
                            {result.agent ? `${result.agent} handled this request.` : 'The orchestrator handled this request.'}
                        </p>
                        <p style={{ color: tokens.color?.['muted-500'], fontSize: tokens.typography?.base?.fontSize, lineHeight: 1.6, margin: 0 }}>
                            {result.summary || 'The agent returned no summary for this request.'}
                        </p>
                        <p style={{ ...ui.hint, marginTop: 12 }}>
                            You asked: {result.prompt}
                        </p>
                        <p style={ui.hint}>
                            {String(result.status).toUpperCase() === 'COMPLETED'
                                ? 'The request finished successfully and is kept in the history for anyone to review.'
                                : `The orchestrator reported this as ${String(result.status).toLowerCase().replace(/_/g, ' ')}.`}
                        </p>
                    </div>
                )}
            </div>

            <div style={{ gridColumn: 'span 4' }}>
                <DataCard title="Agents available" value={<CountUp value={orch?.agents ?? 0} />} icon={<Bot size={16} />} subtitle="Ready to take a request" />
            </div>
            <div style={{ gridColumn: 'span 4' }}>
                <DataCard
                    title="Requests in progress"
                    value={<CountUp value={orch?.active_tasks ?? 0} />}
                    color={tokens.color?.['accent-secondary']}
                    icon={<ListChecks size={16} />}
                    subtitle={Number(orch?.active_tasks) > 0 ? 'Being worked on now' : 'The queue is clear'}
                />
            </div>
            <div style={{ gridColumn: 'span 4' }}>
                <DataCard
                    title="Message bus"
                    value={orch?.message_bus_connected ? 'Connected' : 'Not connected'}
                    color={orch?.message_bus_connected ? tokens.color?.success : tokens.color?.warning}
                    icon={<Radio size={16} />}
                    subtitle={orch?.message_bus_connected ? 'Agents can pass work between themselves' : 'Agents answer on their own'}
                />
            </div>
        </div>
    );
});
CommandModule.displayName = 'CommandModule';

/* ------------------------------------------------------------------ */
/* History                                                             */
/* ------------------------------------------------------------------ */
const HistoryModule = memo(() => {
    const { data, isLoading, error, refetch } = useApi(getCommandHistory, [50], true, 30000);
    const rows = useMemo(() => (Array.isArray(data) ? data : []), [data]);
    const byAgent = useMemo(() => countBy(rows, (r) => r.agent || 'Unassigned'), [rows]);

    const [selected, setSelected] = useState(null);
    const [detail, setDetail] = useState(null);
    const [steps, setSteps] = useState(null);
    const [loadingDetail, setLoadingDetail] = useState(false);
    const [detailError, setDetailError] = useState(null);

    const open = useCallback(async (row) => {
        setSelected(row);
        setDetail(null);
        setSteps(null);
        setDetailError(null);
        setLoadingDetail(true);
        try {
            const res = await getOrchestrationResultStatus(row.result_id);
            setDetail(res.data || null);
        } catch (err) {
            setDetailError(errText(err));
        }
        // The step-by-step trace is a separate store and is often empty for a
        // command that completed in one pass. A failure here must not hide the result.
        try {
            const trace = await getProcessExecutionHistory(row.result_id);
            setSteps(Array.isArray(trace.data) ? trace.data : []);
        } catch {
            setSteps([]);
        }
        setLoadingDetail(false);
    }, []);

    if (selected) {
        return (
            <div style={ui.grid}>
                <div style={{ gridColumn: 'span 12' }}>
                    <Btn tone="ghost" icon={ArrowLeft} onClick={() => setSelected(null)}>Back to all commands</Btn>
                </div>
                <div style={{ ...ui.panel, gridColumn: 'span 7' }}>
                    <h3 style={ui.h3}>What was asked</h3>
                    <p style={{ color: tokens.color?.['text-100'], fontSize: tokens.typography?.base?.fontSize, lineHeight: 1.6, marginTop: 10 }}>
                        {selected.prompt}
                    </p>
                    {loadingDetail && <Loading label="Reading the stored result" />}
                    <ErrorNote error={detailError} context="the stored result for this command" />
                    {detail && (
                        <>
                            <h3 style={{ ...ui.h3, marginTop: tokens.spacing?.lg }}>What came back</h3>
                            <p style={{ color: tokens.color?.['muted-500'], fontSize: tokens.typography?.base?.fontSize, lineHeight: 1.6, marginTop: 10 }}>
                                {detail.summary || 'No summary was stored for this command.'}
                            </p>
                            <p style={ui.hint}>
                                {detail.agent ? `${detail.agent} handled it` : 'No agent was recorded'}
                                {detail.user_id ? `, asked by ${detail.user_id}` : ''}
                                {detail.created_at ? ` on ${fmtDate(detail.created_at)}` : ''}.
                                {String(detail.status).toUpperCase() === 'COMPLETED' ? ' It finished successfully.' : ` It is recorded as ${String(detail.status).toLowerCase().replace(/_/g, ' ')}.`}
                            </p>
                        </>
                    )}
                </div>
                <div style={{ ...ui.panel, gridColumn: 'span 5' }}>
                    <h3 style={ui.h3}>Step by step</h3>
                    <p style={ui.hint}>Each stage the platform recorded while working on this request.</p>
                    <div style={{ marginTop: tokens.spacing?.md }}>
                        {steps === null && <Loading label="Reading the trace" />}
                        {steps !== null && steps.length === 0 && (
                            <EmptyState icon={ListChecks} title="No step-by-step trace was kept" action="This command was answered in a single pass, so the platform recorded a result but no intermediate stages." />
                        )}
                        {(steps || []).map((s, i) => (
                            <div key={i} style={ui.listRow}>
                                <div style={ui.rowMain}>
                                    <span style={{ ...ui.rowTitle, whiteSpace: 'normal' }}>{String(s.step || s.stage || s.name || `Stage ${i + 1}`).replace(/_/g, ' ')}</span>
                                    {(s.detail || s.message) && <span style={ui.rowMeta}>{s.detail || s.message}</span>}
                                    {s.timestamp && <span style={ui.rowMeta}>{fmtDate(s.timestamp)}</span>}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div style={ui.grid}>
            <div style={{ gridColumn: 'span 4' }}>
                <DataCard title="Commands on record" value={<CountUp value={rows.length} />} icon={<History size={16} />} subtitle="Most recent first" />
            </div>
            <div style={{ gridColumn: 'span 8' }}>
                <DataCard title="Which agent answered" isChart minHeight="180px">
                    <BarChartWidget data={byAgent} minHeight="130px" color={tokens.color?.['accent-secondary']} />
                </DataCard>
            </div>

            <div style={{ ...ui.panel, gridColumn: 'span 12' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: tokens.spacing?.sm }}>
                    <div>
                        <h3 style={ui.h3}>Everything that has been asked</h3>
                        <p style={ui.hint}>Select any request to read the full answer and the stages behind it.</p>
                    </div>
                    <Btn tone="ghost" icon={Sparkles} onClick={() => refetch()}>Refresh</Btn>
                </div>
                <div style={{ marginTop: tokens.spacing?.md }}>
                    {isLoading && rows.length === 0 && <Loading label="Reading the command history" />}
                    <ErrorNote error={error} context="the command history" />
                    {!isLoading && !error && rows.length === 0 && (
                        <EmptyState icon={Terminal} title="Nothing has been asked yet" action="Send a request from the command section and it will be listed here for everyone to review." />
                    )}
                    <div style={ui.scroller('420px')} className="emp-scroll">
                        {rows.map((r) => (
                            <button
                                key={r.result_id}
                                onClick={() => open(r)}
                                className="hist-row"
                                style={{
                                    ...ui.listRow, width: '100%', textAlign: 'left', background: 'transparent',
                                    border: 'none', borderBottom: `1px solid ${tokens.color?.['border-600']}`,
                                    cursor: 'pointer', fontFamily: tokens.typography?.fontFamily,
                                }}
                            >
                                <div style={ui.rowMain}>
                                    <span style={{ ...ui.rowTitle, whiteSpace: 'normal' }}>{r.prompt}</span>
                                    <span style={ui.rowMeta}>
                                        {r.agent ? `${r.agent} answered` : 'No agent recorded'}
                                        {r.user_id ? ` · asked by ${r.user_id}` : ''}
                                        {r.created_at ? ` · ${fmtDate(r.created_at)}` : ''}
                                    </span>
                                </div>
                                <span style={{
                                    flexShrink: 0, padding: '3px 9px', borderRadius: tokens.border?.radius?.full,
                                    fontSize: '11.5px', whiteSpace: 'nowrap',
                                    color: String(r.status).toUpperCase() === 'COMPLETED' ? tokens.color?.success : tokens.color?.warning,
                                    border: `1px solid ${String(r.status).toUpperCase() === 'COMPLETED' ? tokens.color?.success : tokens.color?.warning}44`,
                                }}>
                                    {String(r.status).toUpperCase() === 'COMPLETED' ? 'Finished' : String(r.status).toLowerCase().replace(/_/g, ' ')}
                                </span>
                            </button>
                        ))}
                    </div>
                </div>
            </div>
            <style>{`.hist-row:hover { background: rgba(255,255,255,0.03) !important; }`}</style>
        </div>
    );
});
HistoryModule.displayName = 'HistoryModule';

/* ------------------------------------------------------------------ */
/* Danger zone                                                         */
/* ------------------------------------------------------------------ */
const PURGE_PHRASE = 'ERASE EVERYTHING';

const DangerModule = memo(() => {
    const { toast } = useToast();
    const [command, setCommand] = useState('');
    const [runningCommand, setRunningCommand] = useState(false);
    const [reply, setReply] = useState(null);
    const elapsed = useElapsed(runningCommand);

    const [confirmText, setConfirmText] = useState('');
    const [purging, setPurging] = useState(false);

    const kernelSeries = useMetricSeries('agent_activity', { intervalMs: 3000, scale: 100 });

    const send = useCallback(async (text) => {
        if (!text.trim() || runningCommand) return;
        if (!window.confirm(`Send "${text.trim()}" to the orchestrator kernel? This changes how every agent behaves.`)) return;
        setRunningCommand(true);
        setReply(null);
        try {
            const res = await executeRLFFCommand(text.trim());
            setReply({ command: text.trim(), status: res.data?.status || 'ACCEPTED', details: res.data?.details || '' });
            toast({ title: 'The kernel accepted the instruction', description: 'Its reasoning is shown below.', variant: 'success' });
        } catch (err) {
            toast({ title: 'The instruction was refused', description: errText(err), variant: 'destructive' });
        } finally {
            setRunningCommand(false);
        }
    }, [runningCommand, toast]);

    const handlePurge = useCallback(async () => {
        if (confirmText !== PURGE_PHRASE) return;
        if (!window.confirm('Last chance. This deletes every record on the platform and cannot be undone. Continue?')) return;
        setPurging(true);
        try {
            await resetAllData();
            setConfirmText('');
            toast({ title: 'The platform has been wiped', description: 'Every record is gone. The platform is back to an empty state.', variant: 'destructive' });
        } catch (err) {
            toast({ title: 'The wipe did not run', description: errText(err), variant: 'destructive' });
        } finally {
            setPurging(false);
        }
    }, [confirmText, toast]);

    return (
        <div style={ui.grid}>
            <div style={{ ...ui.panel, gridColumn: 'span 7' }}>
                <h3 style={ui.h3}>Instruct the agent kernel</h3>
                <p style={ui.hint}>
                    These instructions are read by the model that governs every agent, so they take effect across the whole
                    platform. The model reasons about the instruction first, which takes tens of seconds on this machine.
                </p>
                <div style={{ display: 'flex', gap: tokens.spacing?.xs, marginTop: tokens.spacing?.md, flexWrap: 'wrap' }}>
                    <Btn tone="ghost" icon={Snowflake} disabled={runningCommand} onClick={() => send('FREEZE ALL AGENTS')}>Freeze every agent</Btn>
                    <Btn tone="ghost" icon={RotateCcw} disabled={runningCommand} onClick={() => send('RESET GOVERNOR STATE')}>Reset the governor</Btn>
                </div>
                <div style={{ marginTop: tokens.spacing?.md }}>
                    <label style={ui.label} htmlFor="kernel-command">Or write your own instruction</label>
                    <div style={{ display: 'flex', gap: tokens.spacing?.xs, flexWrap: 'wrap' }}>
                        <input
                            id="kernel-command"
                            style={{ ...ui.input, flex: 1, minWidth: 220, width: 'auto' }}
                            value={command}
                            onChange={(e) => setCommand(e.target.value)}
                            placeholder="e.g. Pause every agent that touches payroll until Friday."
                            disabled={runningCommand}
                        />
                        <Btn icon={Play} loading={runningCommand} disabled={!command.trim()} onClick={() => send(command)}>
                            {runningCommand ? `Reasoning, ${elapsed}s` : 'Send it'}
                        </Btn>
                    </div>
                </div>
                {runningCommand && (
                    <p style={{ ...ui.hint, color: tokens.color?.warning }}>
                        The kernel model is working through the instruction. Leave this page open until it answers.
                    </p>
                )}
                {reply && !runningCommand && (
                    <div style={{
                        marginTop: tokens.spacing?.md, padding: '12px 14px', borderRadius: tokens.border?.radius?.input,
                        border: `1px solid ${tokens.color?.warning}33`, background: `${tokens.color?.warning}0d`,
                    }}>
                        <div style={{ ...ui.rowTitle, whiteSpace: 'normal', marginBottom: 6 }}>
                            The kernel {String(reply.status).toLowerCase().includes('queue') ? 'queued' : 'accepted'} your instruction
                        </div>
                        <p style={{ ...ui.hint, margin: 0, maxHeight: 220, overflowY: 'auto' }} className="emp-scroll">
                            {reply.details || 'The kernel returned no explanation.'}
                        </p>
                    </div>
                )}
            </div>

            <div style={{ gridColumn: 'span 5' }}>
                <DataCard title="Agent workload, live" isChart minHeight="230px">
                    <AreaChartWidget data={kernelSeries} minHeight="180px" color={tokens.color?.warning} label="How busy the agent layer is right now" />
                </DataCard>
            </div>

            <div style={{
                ...ui.panel, gridColumn: 'span 12',
                border: `1px solid ${tokens.color?.danger}44`, background: `${tokens.color?.danger}0a`,
            }}>
                <h3 style={{ ...ui.h3, color: tokens.color?.danger }}>
                    <Skull size={15} style={{ marginRight: 7, verticalAlign: '-2px' }} />
                    Erase every record on the platform
                </h3>
                <p style={ui.hint}>
                    This deletes every employee record, every case, every policy version and every audit entry. There is no
                    backup and no undo. Type <strong style={{ color: tokens.color?.danger }}>{PURGE_PHRASE}</strong> below to
                    unlock the button, then confirm once more.
                </p>
                <div style={{ display: 'flex', gap: tokens.spacing?.xs, marginTop: tokens.spacing?.md, flexWrap: 'wrap', alignItems: 'center' }}>
                    <input
                        aria-label="Type the confirmation phrase"
                        style={{ ...ui.input, width: 'auto', minWidth: 240, flex: '0 1 300px' }}
                        value={confirmText}
                        onChange={(e) => setConfirmText(e.target.value)}
                        placeholder={PURGE_PHRASE}
                    />
                    <Btn tone="danger" icon={Skull} loading={purging} disabled={confirmText !== PURGE_PHRASE} onClick={handlePurge}>
                        {purging ? 'Erasing everything' : 'Erase everything'}
                    </Btn>
                </div>
            </div>
        </div>
    );
});
DangerModule.displayName = 'DangerModule';

/* ------------------------------------------------------------------ */
/* Shell                                                               */
/* ------------------------------------------------------------------ */
const SUBTITLES = {
    command: 'Ask for something in plain English and the orchestrator picks the agent that should handle it.',
    history: 'Every request that has been put to the orchestrator, and what came back.',
    danger: 'Instructions that change how every agent behaves, and the one action that cannot be undone.',
};

export const UltimateOrchestratorPanelComponent = memo(() => {
    const location = useLocation();
    const module = new URLSearchParams(location.search).get('module') || 'command';

    const body = {
        command: <CommandModule />,
        history: <HistoryModule />,
        danger: <DangerModule />,
    }[module] || <UnknownModule name={module} />;

    return (
        <div style={portalShell.page}>
            <PortalHeader
                icon={Gauge}
                accent={tokens.color?.warning}
                title="Orchestrator control"
                subtitle={SUBTITLES[module] || 'Control the agent orchestrator.'}
                basePath="/ultimate-orchestrator"
                modules={MODULES}
                active={module}
            />
            <div style={portalShell.body} className="emp-scroll">{body}</div>
            <EmployeeStyles />
        </div>
    );
});

UltimateOrchestratorPanelComponent.displayName = 'UltimateOrchestratorPanelComponent';
export default UltimateOrchestratorPanelComponent;
