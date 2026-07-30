// Recognition: give a star to a direct report and watch the live leaderboard.
// The picker reads the manager's own team roster; /admin/users is HR IT only and
// returns 403 for a manager, so it is never called from here.
import React, { useMemo, memo, useState, useCallback } from 'react';
import { theme as tokens } from '../theme';
import { useApi } from '../hooks/useApi';
import { useToast } from '../hooks/use-toast';
import { getRecognitionLeaderboard, giveRecognitionStar } from '../config/api';
import { ui, Btn, Loading, EmptyState, ErrorNote } from './employee/shared';
import { useRoster, RosterSelect, resolveUsername } from './manager/roster';
import { CountUp, LiveMeter } from './live/LivePrimitives';
import { Star, Award, Send } from 'lucide-react';

const StarRecognitionWidget = memo(() => {
    const { toast } = useToast();
    const roster = useRoster();
    const [targetId, setTargetId] = useState('');
    const [reason, setReason] = useState('');
    const [isSending, setIsSending] = useState(false);

    // Leaderboard refreshes on its own so a star given elsewhere shows up here too.
    const {
        data: board,
        isLoading: boardLoading,
        error: boardError,
        refetch: refetchBoard,
    } = useApi(getRecognitionLeaderboard, [], true, 30000, []);

    const rows = useMemo(() => (Array.isArray(board) ? board : []), [board]);
    const topStars = rows.length ? Math.max(...rows.map((r) => Number(r.stars) || 0), 1) : 1;
    const totalStars = rows.reduce((sum, r) => sum + (Number(r.stars) || 0), 0);

    const selected = roster.people.find((p) => p.id === targetId);

    const handleGiveStar = useCallback(async (e) => {
        e.preventDefault();
        if (!targetId || !reason.trim() || isSending) return;
        setIsSending(true);
        const displayName = selected?.name || targetId;

        try {
            // Stars are keyed by login username, the roster by employee id.
            const username = await resolveUsername(targetId);
            if (!username) throw new Error(`No login account is linked to ${displayName}, so a star cannot be recorded.`);

            await giveRecognitionStar(username, reason.trim());
            toast({
                title: 'Recognition sent',
                description: `${displayName} now has one more star from you.`,
                variant: 'success',
            });
            setTargetId('');
            setReason('');
            refetchBoard();
        } catch (error) {
            toast({
                title: 'Recognition not recorded',
                description: error.response?.data?.detail || error.message,
                variant: 'destructive',
            });
        } finally {
            setIsSending(false);
        }
    }, [targetId, reason, isSending, selected, toast, refetchBoard]);

    const styles = useMemo(() => ({
        grid: { ...ui.grid },
        left: { ...ui.panel, gridColumn: 'span 5', display: 'flex', flexDirection: 'column', gap: tokens.spacing?.md },
        right: { ...ui.panel, gridColumn: 'span 7', display: 'flex', flexDirection: 'column', gap: tokens.spacing?.sm },
        row: {
            display: 'flex', alignItems: 'center', gap: tokens.spacing?.sm,
            padding: '9px 0', borderBottom: `1px solid ${tokens.color?.['border-600']}`,
        },
        rank: {
            width: 26, flexShrink: 0, textAlign: 'center', fontSize: 12, fontWeight: 600,
            color: tokens.color?.['muted-600'], fontVariantNumeric: 'tabular-nums',
        },
    }), []);

    return (
        <div style={styles.grid}>
            <div style={styles.left}>
                <div>
                    <h3 style={ui.h3}>Give a star</h3>
                    <p style={ui.hint}>
                        Recognition is permanent and visible on the company leaderboard. Say what the person actually did.
                    </p>
                </div>

                <ErrorNote error={roster.error} context="your team roster" />

                <form onSubmit={handleGiveStar} style={{ display: 'flex', flexDirection: 'column', gap: tokens.spacing?.md }}>
                    <RosterSelect roster={roster} value={targetId} onChange={setTargetId} label="Who deserves it" />

                    <div>
                        <label style={ui.label}>Why they deserve it</label>
                        <textarea
                            value={reason}
                            onChange={(e) => setReason(e.target.value)}
                            placeholder="Rebuilt the quarterly close so it runs in a day instead of a week"
                            style={{ ...ui.input, minHeight: 92, resize: 'vertical', lineHeight: 1.5 }}
                            disabled={isSending}
                            required
                        />
                    </div>

                    <Btn type="submit" icon={Send} loading={isSending} disabled={!targetId || !reason.trim()}>
                        Send recognition
                    </Btn>
                </form>
            </div>

            <div style={styles.right}>
                <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: tokens.spacing?.sm }}>
                    <h3 style={ui.h3}>Star leaderboard</h3>
                    <span style={{ fontSize: '11.5px', color: tokens.color?.['muted-600'] }}>
                        <CountUp value={totalStars} /> stars given company wide
                    </span>
                </div>

                <ErrorNote error={boardError} context="the recognition leaderboard" />
                {boardLoading && rows.length === 0 && <Loading label="Reading the leaderboard" />}

                {!boardLoading && rows.length === 0 && !boardError && (
                    <EmptyState
                        icon={Award}
                        title="Nobody has been recognised yet"
                        action="Give the first star and this board starts filling up."
                    />
                )}

                <div style={ui.scroller('340px')} className="emp-scroll">
                    {rows.map((r, i) => (
                        <div key={r.user_id} style={styles.row}>
                            <span style={styles.rank}>{i + 1}</span>
                            <div style={{ flexGrow: 1, minWidth: 0 }}>
                                <div style={ui.rowTitle}>{r.user_name || r.user_id}</div>
                                <LiveMeter
                                    pct={((Number(r.stars) || 0) / topStars) * 100}
                                    color={tokens.color?.warning}
                                    height={4}
                                />
                            </div>
                            <span style={{
                                flexShrink: 0, display: 'inline-flex', alignItems: 'center', gap: 5,
                                color: tokens.color?.warning, fontWeight: 600, fontVariantNumeric: 'tabular-nums',
                            }}>
                                <CountUp value={Number(r.stars) || 0} /> <Star size={14} />
                            </span>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
});

StarRecognitionWidget.displayName = 'StarRecognitionWidget';
export default StarRecognitionWidget;
