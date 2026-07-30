// Explains, in plain English, why the attrition model scored a person the way it
// did. Everything shown comes from /data/xai/explain. There is no mock fallback:
// if the model cannot be reached the panel says so and shows nothing else.
import React, { useMemo, memo } from 'react';
import { theme as tokens } from '../theme';
import { useApi } from '../hooks/useApi';
import { getXAIExplanation } from '../config/api';
import DataCard from './DataCard';
import { CountUp, LiveMeter } from './live/LivePrimitives';
import { ui, Loading, EmptyState, ErrorNote, humanText } from './employee/shared';
import { Brain, ArrowUpRight, ArrowDownRight, Minus, UserSearch } from 'lucide-react';

const MODEL_NAME = 'attrition_model';

// "Heuristic_v2" is a model identifier, not something to put in front of a person.
const readableModel = (raw) => {
    const t = humanText(raw);
    return t ? `${t.charAt(0).toUpperCase()}${t.slice(1)}` : 'the attrition model';
};

const riskWords = (score) => {
    if (score >= 0.7) return 'a high chance of leaving';
    if (score >= 0.4) return 'a moderate chance of leaving';
    return 'a low chance of leaving';
};

const XAIDecisionPanel = memo(({ employeeId, employeeName }) => {
    const enabled = Boolean(employeeId);
    const { data, isLoading, error } = useApi(
        getXAIExplanation,
        [MODEL_NAME, { employee_id: employeeId }],
        enabled,
    );

    const who = employeeName || 'This person';
    const score = Number(data?.prediction_score);
    const hasScore = Number.isFinite(score);

    // Ranked by how hard each factor pushed the score, largest push first.
    const drivers = useMemo(() => (
        (data?.feature_contributions || [])
            .map((f) => ({
                label: humanText(f.feature),
                impact: Number(f.impact) || 0,
                reason: f.reason || '',
            }))
            .sort((a, b) => Math.abs(b.impact) - Math.abs(a.impact))
    ), [data]);

    const strongest = Math.max(...drivers.map((d) => Math.abs(d.impact)), 0.0001);
    const leading = drivers.find((d) => d.impact !== 0);

    const styles = useMemo(() => ({
        row: {
            display: 'flex', alignItems: 'flex-start', gap: tokens.spacing?.sm,
            padding: '11px 0', borderBottom: `1px solid ${tokens.color?.['border-600']}`,
        },
        icon: (up) => ({
            flexShrink: 0, display: 'grid', placeItems: 'center', width: 24, height: 24,
            borderRadius: 7, marginTop: 2,
            color: up ? tokens.color?.danger : tokens.color?.success,
            background: `${up ? tokens.color?.danger : tokens.color?.success}14`,
        }),
        weight: {
            flexShrink: 0, minWidth: 62, textAlign: 'right', fontVariantNumeric: 'tabular-nums',
            fontSize: 13, fontWeight: 600,
        },
    }), []);

    if (!enabled) {
        return (
            <DataCard title="Why the model says what it says" icon={<Brain size={15} />}>
                <EmptyState
                    icon={UserSearch}
                    title="Pick a team member first"
                    action="Once you choose someone, this panel breaks down every factor behind their attrition score."
                />
            </DataCard>
        );
    }

    return (
        <DataCard title="Why the model says what it says" icon={<Brain size={15} />}>
            <ErrorNote error={error} context="the model explanation" />
            {isLoading && !data && <Loading label={`Asking ${readableModel(data?.model_type)} to explain itself`} />}

            {!error && data && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: tokens.spacing?.md }}>
                    {hasScore && (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
                            <p style={{ margin: 0, color: tokens.color?.['text-100'], fontSize: tokens.typography?.base?.fontSize, lineHeight: 1.55 }}>
                                The explanation model puts {who} at{' '}
                                <strong><CountUp value={score * 100} decimals={1} suffix="%" /></strong>, {riskWords(score)}.
                                {leading ? <> The single strongest influence is <strong>{leading.label}</strong>.</> : null}
                            </p>
                            <LiveMeter
                                pct={score * 100}
                                color={score >= 0.7 ? tokens.color?.danger : (score >= 0.4 ? tokens.color?.warning : tokens.color?.success)}
                                height={7}
                            />
                        </div>
                    )}

                    {drivers.length > 0 ? (
                        <div>
                            <p style={{ ...ui.hint, marginTop: 0 }}>
                                Each factor below either pushed the score up, making a departure more likely, or pulled it down.
                            </p>
                            <div style={ui.scroller('260px')} className="emp-scroll">
                                {drivers.map((d, i) => {
                                    const up = d.impact > 0;
                                    const flat = d.impact === 0;
                                    const Icon = flat ? Minus : (up ? ArrowUpRight : ArrowDownRight);
                                    return (
                                        <div key={`${d.label}-${i}`} style={styles.row}>
                                            <span style={{ ...styles.icon(up), color: flat ? tokens.color?.['muted-600'] : undefined }}>
                                                <Icon size={14} />
                                            </span>
                                            <div style={{ flexGrow: 1, minWidth: 0 }}>
                                                <div style={ui.rowTitle}>{d.label}</div>
                                                <div style={{ ...ui.rowMeta, whiteSpace: 'normal', lineHeight: 1.5 }}>
                                                    {d.reason || (flat
                                                        ? 'Made no difference to the score this time.'
                                                        : `${up ? 'Pushed the risk up' : 'Pulled the risk down'} for this person.`)}
                                                </div>
                                                <div style={{ marginTop: 6 }}>
                                                    <LiveMeter
                                                        pct={(Math.abs(d.impact) / strongest) * 100}
                                                        color={flat ? tokens.color?.['muted-600'] : (up ? tokens.color?.danger : tokens.color?.success)}
                                                        height={4}
                                                    />
                                                </div>
                                            </div>
                                            <span style={{ ...styles.weight, color: flat ? tokens.color?.['muted-600'] : (up ? tokens.color?.danger : tokens.color?.success) }}>
                                                {up ? '+' : ''}{(d.impact * 100).toFixed(1)}%
                                            </span>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                    ) : (
                        <EmptyState
                            icon={Brain}
                            title="The model returned a score but no breakdown"
                            action="Without contributing factors there is nothing to explain. Treat the score with caution."
                        />
                    )}

                    <p style={{ ...ui.hint, marginTop: 0 }}>
                        Produced by {readableModel(data.model_type)}
                        {data.generated_at ? ` on ${new Date(data.generated_at).toLocaleString()}` : ''}. This is the
                        explainability model, so its score can differ from the workforce planning figure shown elsewhere.
                    </p>
                </div>
            )}
        </DataCard>
    );
});

XAIDecisionPanel.displayName = 'XAIDecisionPanel';
export default XAIDecisionPanel;
