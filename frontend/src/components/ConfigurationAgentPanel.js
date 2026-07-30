// /frontend/src/components/ConfigurationAgentPanel.js
// Live configuration agent: streams the local model's reasoning as it turns a plain
// English goal into a business rule, and lets an administrator change which model the
// platform runs on. Model list and active model both come from the backend.
import React, { memo, useState, useCallback, useRef, useEffect, useMemo } from 'react';
import { theme as tokens } from '../theme';
import { streamAgentConfig, getAiModels, getActiveAIProvider, setAIProvider } from '../config/api';
import { useApi } from '../hooks/useApi';
import { useToast } from '../hooks/use-toast';
import { ui, Btn, EmptyState, ErrorNote } from './employee/shared';
import { Zap, SlidersHorizontal, Code, Square } from 'lucide-react';

const errText = (e) => e?.response?.data?.detail || e?.message || 'The request failed.';

// The agent stream decorates its stage messages with pictographs. Strip them so the
// console stays icon-only.
const clean = (s) => String(s || '').replace(/[\u{1F000}-\u{1FAFF}\u{2190}-\u{27BF}\u{FE0F}]/gu, '').replace(/\s+/g, ' ').trim();

const ConfigurationAgentPanel = memo(() => {
    const { toast } = useToast();
    const [prompt, setPrompt] = useState('');
    const [lines, setLines] = useState([]);
    const [isStreaming, setIsStreaming] = useState(false);
    const [selectedModel, setSelectedModel] = useState('');
    const [switching, setSwitching] = useState(false);
    const sourceRef = useRef(null);
    const outRef = useRef(null);

    const { data: modelsResp, isLoading: modelsLoading, error: modelsError } = useApi(getAiModels, [], true);
    const { data: provider, refetch: refetchProvider } = useApi(getActiveAIProvider, [], true);
    const models = useMemo(() => modelsResp?.models || [], [modelsResp]);

    // Start the dropdown on whatever the platform is actually running.
    useEffect(() => {
        if (provider?.default_model && !selectedModel) setSelectedModel(provider.default_model);
    }, [provider, selectedModel]);

    useEffect(() => () => sourceRef.current?.close(), []);
    useEffect(() => { if (outRef.current) outRef.current.scrollTop = outRef.current.scrollHeight; }, [lines]);

    const stop = useCallback(() => {
        sourceRef.current?.close();
        sourceRef.current = null;
        setIsStreaming(false);
    }, []);

    const handleStream = useCallback((e) => {
        e.preventDefault();
        if (!prompt.trim() || isStreaming) return;

        sourceRef.current?.close();
        setLines([]);
        setIsStreaming(true);

        const onChunk = (chunk) => {
            try {
                const d = JSON.parse(chunk);
                const stage = clean(d.stage);
                const message = clean(d.message);
                if (message) setLines((p) => [...p, { kind: 'step', stage, text: message }]);
                if (d.content) setLines((p) => [...p, { kind: 'code', text: String(d.content) }]);
            } catch {
                setLines((p) => [...p, { kind: 'code', text: String(chunk) }]);
            }
        };
        const onComplete = () => {
            setIsStreaming(false);
            sourceRef.current = null;
            toast({ title: 'The agent finished', description: 'The rule it drafted is shown on the right.', variant: 'success' });
        };
        const onError = () => {
            setIsStreaming(false);
            sourceRef.current = null;
            setLines((p) => [...p, { kind: 'step', stage: 'stopped', text: 'The connection to the agent dropped before it finished.' }]);
            toast({ title: 'The agent stream failed', description: 'The connection dropped before the agent finished. Try again.', variant: 'destructive' });
        };

        try {
            sourceRef.current = streamAgentConfig(prompt.trim(), onChunk, onComplete, onError);
        } catch (err) {
            onError(err);
        }
    }, [prompt, isStreaming, toast]);

    const handleSwitch = useCallback(async () => {
        if (!selectedModel || selectedModel === provider?.default_model) return;
        if (!window.confirm(`Switch the platform to the ${selectedModel} model? Every agent will use it from the next request onward.`)) return;
        setSwitching(true);
        try {
            await setAIProvider(selectedModel);
            toast({ title: 'Model switched', description: `Agents now run on ${selectedModel}.`, variant: 'success' });
            refetchProvider();
        } catch (err) {
            toast({ title: 'Could not switch the model', description: errText(err), variant: 'destructive' });
        } finally {
            setSwitching(false);
        }
    }, [selectedModel, provider, refetchProvider, toast]);

    return (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(12, 1fr)', gap: tokens.spacing?.lg, width: '100%' }}>
            <div style={{ ...ui.panel, gridColumn: 'span 5' }}>
                <h3 style={ui.h3}>Draft a rule with the agent</h3>
                <p style={ui.hint}>Say what the rule should achieve. The agent writes it, checks its own work and corrects itself as it goes. Every step it takes is shown as it happens.</p>
                <form onSubmit={handleStream} style={{ marginTop: tokens.spacing?.md }}>
                    <label style={ui.label} htmlFor="config-prompt">The goal</label>
                    <textarea
                        id="config-prompt"
                        style={{ ...ui.input, minHeight: 120, resize: 'vertical', fontFamily: tokens.typography?.fontFamily }}
                        value={prompt}
                        onChange={(ev) => setPrompt(ev.target.value)}
                        placeholder="e.g. Cost of living adjustments must be reviewed by an HR business partner before payroll runs."
                        disabled={isStreaming}
                        required
                    />
                    <div style={{ display: 'flex', gap: tokens.spacing?.xs, marginTop: tokens.spacing?.sm, flexWrap: 'wrap' }}>
                        <Btn type="submit" icon={Zap} loading={isStreaming} disabled={!prompt.trim()}>
                            {isStreaming ? 'The agent is working' : 'Draft the rule'}
                        </Btn>
                        {isStreaming && <Btn type="button" tone="ghost" icon={Square} onClick={stop}>Stop</Btn>}
                    </div>
                </form>

                <div style={{ marginTop: tokens.spacing?.lg, borderTop: `1px solid ${tokens.color?.['border-600']}`, paddingTop: tokens.spacing?.md }}>
                    <h3 style={ui.h3}>Which model the platform runs on</h3>
                    <p style={ui.hint}>
                        {provider
                            ? `Running ${provider.default_model} through ${provider.provider} at ${provider.base_url}.`
                            : 'Reading the active model from the platform.'}
                    </p>
                    <ErrorNote error={modelsError} context="the list of installed models" />
                    <div style={{ display: 'flex', gap: tokens.spacing?.xs, marginTop: tokens.spacing?.sm, flexWrap: 'wrap' }}>
                        <select
                            aria-label="Model to run"
                            style={{ ...ui.input, flex: 1, minWidth: 190, width: 'auto' }}
                            value={selectedModel}
                            onChange={(ev) => setSelectedModel(ev.target.value)}
                            disabled={modelsLoading || models.length === 0}
                        >
                            {modelsLoading && <option value="">Reading installed models</option>}
                            {!modelsLoading && models.length === 0 && <option value="">No models are installed</option>}
                            {models.map((m) => <option key={m.name} value={m.name}>{m.label || m.name}</option>)}
                        </select>
                        <Btn
                            icon={SlidersHorizontal}
                            loading={switching}
                            onClick={handleSwitch}
                            disabled={!selectedModel || selectedModel === provider?.default_model}
                        >
                            {selectedModel && selectedModel === provider?.default_model ? 'Already active' : 'Switch to this model'}
                        </Btn>
                    </div>
                </div>
            </div>

            <div style={{ ...ui.panel, gridColumn: 'span 7', display: 'flex', flexDirection: 'column', minHeight: 420 }}>
                <h3 style={ui.h3}>
                    <Code size={15} style={{ marginRight: 7, verticalAlign: '-2px' }} color={tokens.color?.['accent-secondary']} />
                    What the agent is doing
                </h3>
                <div ref={outRef} style={{ ...ui.scroller('420px'), marginTop: tokens.spacing?.md, flexGrow: 1 }} className="emp-scroll">
                    {lines.length === 0 && !isStreaming && (
                        <EmptyState icon={Code} title="The agent has not run yet" action="Describe a goal on the left and the agent's working will stream in here line by line." />
                    )}
                    {lines.length === 0 && isStreaming && (
                        <p style={ui.hint}>Waiting for the model to send its first step.</p>
                    )}
                    {lines.map((l, i) => (l.kind === 'step' ? (
                        <div key={i} style={{ display: 'flex', gap: 9, padding: '7px 0', alignItems: 'flex-start' }}>
                            <span style={{
                                marginTop: 5, width: 6, height: 6, borderRadius: 999, flexShrink: 0,
                                background: tokens.color?.['accent-primary'], boxShadow: `0 0 8px ${tokens.color?.['accent-primary']}`,
                            }} />
                            <span style={{ color: tokens.color?.['text-100'], fontSize: tokens.typography?.small?.fontSize, lineHeight: 1.55 }}>
                                {l.text}
                            </span>
                        </div>
                    ) : (
                        <pre key={i} style={{
                            margin: '4px 0 10px 15px', padding: '10px 12px', whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                            background: tokens.color?.['panel-900'], borderRadius: tokens.border?.radius?.input,
                            border: `1px solid ${tokens.color?.['border-600']}`,
                            fontFamily: tokens.typography?.fontMono, fontSize: '11.5px', lineHeight: 1.6,
                            color: tokens.color?.['muted-500'],
                        }}>{l.text}</pre>
                    )))}
                </div>
            </div>
        </div>
    );
});

ConfigurationAgentPanel.displayName = 'ConfigurationAgentPanel';
export default ConfigurationAgentPanel;
