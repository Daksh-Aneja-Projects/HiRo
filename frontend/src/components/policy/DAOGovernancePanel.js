// DAO Governance - the live proposal list and the voting control.
// Tallies, deadlines and totals are read from the governance ledger; a vote is
// persisted server side and the list is refetched so the bar moves for real.
import React, { memo, useCallback, useMemo, useState } from 'react';
import { theme as tokens } from '../../theme';
import { useApi } from '../../hooks/useApi';
import { useToast } from '../../hooks/use-toast';
import { getActiveProposals, getGovernanceDashboardData, castVote } from '../../config/api';
import DataCard from '../DataCard';
import BarChartWidget from '../charts/BarChartWidget';
import { Gavel, Users, Boxes, ThumbsUp, ThumbsDown, Loader2, Timer, Vote } from 'lucide-react';
import { s, dim, apiError } from './ui';

const timeLeft = (deadline) => {
    if (!deadline) return 'no deadline set';
    const ms = new Date(deadline).getTime() - Date.now();
    if (Number.isNaN(ms)) return 'no deadline set';
    if (ms <= 0) return 'voting window has closed';
    const hours = Math.floor(ms / 3600000);
    if (hours >= 48) return `${Math.floor(hours / 24)} days left to vote`;
    if (hours >= 1) return `${hours} hours left to vote`;
    return `${Math.max(1, Math.round(ms / 60000))} minutes left to vote`;
};

const DAOGovernancePanel = memo(() => {
    const { toast } = useToast();
    const [power, setPower] = useState('100');
    const [busy, setBusy] = useState('');

    const { data: proposalsRaw, isLoading, error, refetch } = useApi(getActiveProposals, [], true, 60000);
    const { data: stats, refetch: refetchStats } = useApi(getGovernanceDashboardData, [], true, 60000);

    const proposals = useMemo(() => (Array.isArray(proposalsRaw) ? proposalsRaw : []), [proposalsRaw]);

    const supportSeries = useMemo(() => proposals.map((p) => {
        const total = (Number(p.votes_for) || 0) + (Number(p.votes_against) || 0);
        return { name: p.title || p.id, value: total ? Math.round((Number(p.votes_for) || 0) / total * 100) : 0 };
    }), [proposals]);

    const vote = useCallback(async (proposal, choice) => {
        const weight = parseFloat(power);
        if (!Number.isFinite(weight) || weight <= 0) {
            toast({ title: 'Set your voting weight', description: 'Enter how much voting power to commit, for example 100.', variant: 'warning' });
            return;
        }
        setBusy(`${proposal.id}:${choice}`);
        try {
            await castVote(proposal.id, choice, weight);
            toast({
                title: choice === 'for' ? 'Voted in favour' : 'Voted against',
                description: `${weight} voting power committed to "${proposal.title || proposal.id}".`,
                variant: 'success',
            });
            refetch();
            refetchStats();
        } catch (err) {
            toast({ title: 'Vote not recorded', description: apiError(err), variant: 'destructive' });
        } finally {
            setBusy('');
        }
    }, [power, toast, refetch, refetchStats]);

    const styles = {
        grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: tokens.spacing?.lg, marginBottom: tokens.spacing?.lg },
        bar: { height: 8, borderRadius: 999, background: 'var(--border-subtle)', overflow: 'hidden', marginTop: 10 },
        list: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(330px, 1fr))', gap: tokens.spacing?.lg },
    };

    return (
        <div>
            <div style={styles.grid}>
                <DataCard title="Proposals open for voting" value={stats?.active_proposals ?? 0} unit="live"
                          color={tokens.color?.['accent-primary']} icon={<Gavel size={22} />} />
                <DataCard title="Voting power in circulation" value={Number(stats?.total_voting_power ?? 0).toLocaleString()} unit="tokens"
                          color={tokens.color?.['accent-secondary']} icon={<Vote size={22} />} />
                <DataCard title="Members who have voted" value={stats?.members_voting ?? 0} unit="people"
                          color={tokens.color?.success} icon={<Users size={22} />} />
                <DataCard title="Ledger blocks in the last day" value={stats?.ledger_commits_24h ?? 0} unit="blocks"
                          color={tokens.color?.warning} icon={<Boxes size={22} />} />
            </div>

            <div style={{ ...s.panel, marginBottom: tokens.spacing?.lg }}>
                <div style={{ ...s.row, justifyContent: 'space-between' }}>
                    <div>
                        <h3 style={s.sectionTitle}><Vote size={16} color={tokens.color?.['accent-primary']} /> Your voting weight</h3>
                        <p style={{ ...s.hint, margin: '8px 0 0' }}>
                            Every vote below commits this much power. The ledger refuses a second vote from the same account on the same proposal.
                        </p>
                    </div>
                    <input style={{ ...s.input, width: 140 }} type="number" min="1" step="1" value={power}
                           onChange={(e) => setPower(e.target.value)} aria-label="Voting power to commit" />
                </div>
            </div>

            {isLoading && proposals.length === 0 && (
                <p style={{ ...s.hint, textAlign: 'center' }}><Loader2 size={16} className="animate-spin" /> Loading open proposals...</p>
            )}
            {error && (
                <p style={{ color: tokens.color?.danger, fontSize: 13 }}>The governance ledger could not be reached: {error}</p>
            )}
            {!isLoading && !error && proposals.length === 0 && (
                <div style={{ ...s.panel, textAlign: 'center', padding: '36px 20px' }}>
                    <Gavel size={24} color={tokens.color?.['muted-600']} />
                    <p style={{ color: tokens.color?.['muted-500'], margin: '10px 0 0', fontSize: 13.5 }}>
                        No proposal is open for voting. New proposals appear here the moment they are raised on the governance ledger.
                    </p>
                </div>
            )}

            <div style={styles.list}>
                {proposals.map((p) => {
                    const forVotes = Number(p.votes_for) || 0;
                    const againstVotes = Number(p.votes_against) || 0;
                    const total = forVotes + againstVotes;
                    const pct = total ? Math.round((forVotes / total) * 100) : 0;
                    const closed = p.deadline ? new Date(p.deadline).getTime() <= Date.now() : false;
                    return (
                        <div key={p.id} style={s.panel}>
                            <h4 style={{ margin: 0, fontSize: 14.5, fontWeight: 600, color: tokens.color?.['text-100'] }}>{p.title || p.id}</h4>
                            <p style={{ ...s.hint, margin: '6px 0 0' }}>
                                Raised by {p.proposer || 'an unnamed member'}. <Timer size={12} style={{ marginBottom: -2 }} /> {timeLeft(p.deadline)}.
                            </p>

                            <div style={styles.bar}>
                                <div style={{ width: `${pct}%`, height: '100%', background: tokens.color?.success, transition: 'width 0.5s cubic-bezier(0.2,0.8,0.2,1)' }} />
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12.5, color: tokens.color?.['muted-500'], marginTop: 6 }}>
                                <span>{pct}% in favour</span>
                                <span>{forVotes.toLocaleString()} for, {againstVotes.toLocaleString()} against</span>
                            </div>

                            <div style={{ ...s.row, marginTop: 14 }}>
                                <button type="button" style={dim(s.btn, closed || busy === `${p.id}:for`)}
                                        disabled={closed || busy === `${p.id}:for`} onClick={() => vote(p, 'for')}>
                                    {busy === `${p.id}:for` ? <Loader2 size={15} className="animate-spin" /> : <ThumbsUp size={15} />} Vote in favour
                                </button>
                                <button type="button" style={dim(s.btnGhost, closed || busy === `${p.id}:against`)}
                                        disabled={closed || busy === `${p.id}:against`} onClick={() => vote(p, 'against')}>
                                    {busy === `${p.id}:against` ? <Loader2 size={15} className="animate-spin" /> : <ThumbsDown size={15} />} Vote against
                                </button>
                            </div>
                            {closed && <p style={{ ...s.hint, margin: '10px 0 0' }}>Voting has closed on this proposal.</p>}
                        </div>
                    );
                })}
            </div>

            <div style={{ marginTop: tokens.spacing?.lg }}>
                <DataCard title="Share of votes in favour, by proposal" isChart minHeight="300px">
                    <BarChartWidget data={supportSeries} minHeight="240px" color={tokens.color?.success}
                                    label="Percentage of committed voting power supporting each open proposal" />
                </DataCard>
            </div>
        </div>
    );
});

DAOGovernancePanel.displayName = 'DAOGovernancePanel';
export default DAOGovernancePanel;
