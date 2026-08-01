// Engagement tab: eNPS gauge, response-rate ring, theme chips. Every honest
// degraded state the backend can send (anonymity floor, LLM unreachable, no
// comments, no responses yet) has its own plain-English message here.
import React, { useMemo } from 'react';
import { theme as tokens } from '../../theme';
import { getEngagementSummary } from '../../config/api';
import { useApi } from '../../hooks/useApi';
import { ui, Loading, EmptyState, ErrorNote } from '../employee/shared';
import { ArcGauge, RingGauge } from './Gauge';
import { Smile, ShieldAlert, MessageSquareOff, Quote, Users2 } from 'lucide-react';

const EngagementPanel = () => {
    const { data, isLoading, error } = useApi(getEngagementSummary, [], true, 60000);

    const hasThemes = Array.isArray(data?.themes);
    const belowFloor = Boolean(data?.note);
    const noResponses = data?.responses === 0;

    const promoterPct = useMemo(() => {
        if (!data?.responses) return null;
        return Math.round((data.promoters / data.responses) * 100);
    }, [data]);

    return (
        <div style={ui.grid} className="portal-grid">
            {isLoading && !data && <div style={{ gridColumn: 'span 12' }}><Loading label="Reading the latest pulse survey" /></div>}
            <ErrorNote error={error} context="the engagement pulse" />

            {data && (
                <>
                    <div style={{ ...ui.panel, gridColumn: 'span 4', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10 }}>
                        <h3 style={{ ...ui.h3, alignSelf: 'flex-start' }}>Employee Net Promoter Score</h3>
                        {noResponses ? (
                            <EmptyState icon={Smile} title="No responses yet for this survey" action={data.note || 'Once people respond to the open pulse, the score appears here.'} />
                        ) : (
                            <ArcGauge value={data.enps} label={`From ${data.responses.toLocaleString()} response${data.responses === 1 ? '' : 's'} this survey`} />
                        )}
                    </div>

                    <div style={{ ...ui.panel, gridColumn: 'span 4', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10 }}>
                        <h3 style={{ ...ui.h3, alignSelf: 'flex-start' }}>Who responded</h3>
                        <RingGauge
                            pct={data.response_rate_pct || 0}
                            color={tokens.color?.['accent-primary']}
                            label={`${data.responses.toLocaleString()} of the workforce answered`}
                            sublabel={data.survey_id ? `Survey ${data.survey_id}` : null}
                        />
                    </div>

                    <div style={{ ...ui.panel, gridColumn: 'span 4', display: 'flex', flexDirection: 'column', gap: 12, justifyContent: 'center' }}>
                        <h3 style={ui.h3}>How the score breaks down</h3>
                        {noResponses ? (
                            <p style={ui.hint}>Nothing to break down until someone responds.</p>
                        ) : (
                            <>
                                <BreakdownRow icon={Users2} label="Promoters (score 9-10)" value={data.promoters} color={tokens.color?.success} />
                                <BreakdownRow label="Passive (score 7-8)" value={data.passives} color={tokens.color?.['muted-500']} />
                                <BreakdownRow label="Detractors (score 0-6)" value={data.detractors} color={tokens.color?.danger} />
                                {promoterPct != null && <p style={{ ...ui.hint, margin: 0 }}>{promoterPct}% of respondents are promoters.</p>}
                            </>
                        )}
                    </div>

                    {belowFloor && (
                        <div style={{ ...ui.panel, gridColumn: 'span 12', borderLeft: `3px solid ${tokens.color?.warning}`, display: 'flex', gap: 12, alignItems: 'flex-start' }}>
                            <ShieldAlert size={18} color={tokens.color?.warning} style={{ flexShrink: 0, marginTop: 2 }} />
                            <div>
                                <h3 style={{ ...ui.h3, fontSize: 13.5 }}>Comment themes withheld to protect anonymity</h3>
                                <p style={{ ...ui.hint, margin: '4px 0 0' }}>{data.note}</p>
                            </div>
                        </div>
                    )}

                    {!belowFloor && !noResponses && (
                        <div style={{ ...ui.panel, gridColumn: 'span 12' }}>
                            <h3 style={ui.h3}>What people are saying</h3>
                            <p style={ui.hint}>Recurring themes the local model found across anonymous comments, paraphrased so no single response is identifiable.</p>
                            {hasThemes ? (
                                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginTop: 12 }}>
                                    {data.themes.map((t, i) => (
                                        <div key={`${t.theme}-${i}`} style={{
                                            ...ui.panel, background: tokens.color?.['panel-700'], flex: '1 1 260px', maxWidth: 360,
                                        }}>
                                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                                                <strong style={{ color: tokens.color?.['text-100'], fontSize: 13.5 }}>{t.theme}</strong>
                                                <span style={{
                                                    fontSize: 11.5, fontWeight: 600, color: tokens.color?.['accent-primary'],
                                                    background: `${tokens.color?.['accent-primary']}18`, borderRadius: 999, padding: '2px 9px',
                                                }}>{t.count}</span>
                                            </div>
                                            {t.representative_quote && (
                                                <p style={{ ...ui.hint, margin: '8px 0 0', display: 'flex', gap: 6 }}>
                                                    <Quote size={12} style={{ flexShrink: 0, marginTop: 3 }} />
                                                    <span>{t.representative_quote}</span>
                                                </p>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <div style={{ marginTop: 8 }}>
                                    <EmptyState icon={MessageSquareOff} title="Themes unavailable" action={data.themes_note || 'The local model could not be reached to theme the comments. Scores above are unaffected.'} />
                                </div>
                            )}
                        </div>
                    )}
                </>
            )}
        </div>
    );
};

const BreakdownRow = ({ label, value, color }) => (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span style={{ width: 8, height: 8, borderRadius: 999, background: color, flexShrink: 0 }} />
        <span style={{ flex: 1, fontSize: 13, color: tokens.color?.['text-100'] }}>{label}</span>
        <span style={{ fontSize: 13, fontWeight: 600, color, fontVariantNumeric: 'tabular-nums' }}>{value}</span>
    </div>
);

export default EngagementPanel;
