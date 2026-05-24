// /frontend/src/components/StarRecognitionWidget.js - FINAL PRODUCTION-READY REPLACEMENT
import React, { useMemo, memo, useState, useCallback } from 'react';
import { theme as tokens } from '../theme';
import { useApi } from '../hooks/useApi';
import { useToast } from '../hooks/use-toast';
import { useAuth } from '../contexts/AuthContext';
import { getRecognitionLeaderboard, giveRecognitionStar, getAllUsers } from '../config/api'; 
import { Star, Loader2, AlertTriangle, Send, User } from 'lucide-react';

const StarRecognitionWidget = memo(() => {
    const { user } = useAuth();
    const { toast } = useToast();
    const [targetUserId, setTargetUserId] = useState('');
    const [reason, setReason] = useState('');
    const [isSending, setIsSending] = useState(false);
    
    // CRITICAL API INTEGRATION 1: Fetch Leaderboard (Polling)
    const { 
        data: leaderboard, 
        isLoading: isLeaderboardLoading, 
        error: leaderboardError, 
        refetch: refetchLeaderboard
    } = useApi(getRecognitionLeaderboard, [], true, 30000, []);
    
    // CRITICAL API INTEGRATION 2: Fetch all users for selection (one time fetch)
    const { 
        data: allUsers, 
        isLoading: isUsersLoading 
    } = useApi(getAllUsers, [], true, []);
    
    const usersForSelect = useMemo(() => {
        return allUsers.filter(u => u.id !== user.id); // Cannot recognize self
    }, [allUsers, user.id]);


    // CRITICAL: Handle Giving a Star
    const handleGiveStar = useCallback(async (e) => {
        e.preventDefault();
        if (!targetUserId || !reason || isSending) return;

        setIsSending(true);
        try {
            // CRITICAL API INTEGRATION 3: Give Recognition Star
            await giveRecognitionStar(targetUserId, reason); 
            
            toast({ title: 'Star Given!', description: `Recognition sent to ${targetUserId}.`, variant: 'success' });
            setTargetUserId('');
            setReason('');
            refetchLeaderboard();
        } catch (error) {
            console.error("Recognition failed:", error);
            toast({ title: 'Recognition Failed', description: error.response?.data?.detail || error.message, variant: 'destructive' });
        } finally {
            setIsSending(false);
        }
    }, [targetUserId, reason, isSending, toast, refetchLeaderboard]);


    const styles = useMemo(() => ({
        container: { padding: tokens.spacing?.md, background: tokens.color?.['panel-800'], borderRadius: tokens.border?.radius?.card, minHeight: '450px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: tokens.spacing?.lg },
        section: { display: 'flex', flexDirection: 'column' },
        input: { padding: '8px 12px', background: tokens.color?.['bg-input'], border: `1px solid ${tokens.color?.['border-600']}`, borderRadius: tokens.border?.radius?.input, color: tokens.color?.['text-100'], width: '100%', boxSizing: 'border-box', marginBottom: tokens.spacing?.sm },
        button: (bgColor) => ({ padding: '10px 15px', background: bgColor, border: 'none', borderRadius: tokens.border?.radius?.button, color: tokens.color?.['bg-deep'], cursor: 'pointer', transition: 'all 0.2s ease', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: tokens.spacing?.xs, width: '100%' }),
        item: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: `1px dotted ${tokens.color?.['border-700']}` },
    }), []);

    return (
        <div style={styles.container}>
            {/* Recognition Form */}
            <div style={styles.section}>
                <h3 style={{ color: tokens.color?.['text-100'] }}>Give a Star!</h3>
                <form onSubmit={handleGiveStar} style={{ flexGrow: 1 }}>
                    <label style={{ color: tokens.color?.['muted-500'], fontSize: tokens.typography.small.fontSize }}>Recognize Colleague:</label>
                    <select 
                        value={targetUserId} 
                        onChange={e => setTargetUserId(e.target.value)} 
                        style={styles.input} 
                        disabled={isUsersLoading || isSending}
                        required
                    >
                        <option value="">{isUsersLoading ? 'Loading users...' : 'Select Employee'}</option>
                        {usersForSelect.map(u => (
                            <option key={u.id} value={u.id}>{u.full_name || u.username}</option>
                        ))}
                    </select>
                    
                    <label style={{ color: tokens.color?.['muted-500'], fontSize: tokens.typography.small.fontSize }}>Reason:</label>
                    <textarea 
                        value={reason} 
                        onChange={e => setReason(e.target.value)} 
                        placeholder="e.g., Policy verification on Q4 adjustments" 
                        style={{...styles.input, minHeight: '80px'}} 
                        disabled={isSending}
                        required
                    />
                    
                    <button 
                        type="submit" 
                        style={styles.button(tokens.color?.warning)} 
                        disabled={isSending || !targetUserId || !reason}
                        className="star-send-hover"
                    >
                        {isSending ? <Loader2 size={16} className="animate-spin" /> : <Star size={16} />}
                        Send Recognition Star
                    </button>
                </form>
            </div>
            
            {/* Leaderboard */}
            <div style={styles.section}>
                <h3 style={{ color: tokens.color?.['text-100'] }}>Star Leaderboard</h3>
                {isLeaderboardLoading && <p><Loader2 size={16} className="animate-spin" /></p>}
                {leaderboardError && <p style={{ color: tokens.color?.danger }}>Error loading leaderboard.</p>}
                
                <div style={{ flexGrow: 1, overflowY: 'auto' }}>
                    {leaderboard.slice(0, 5).map((item, index) => (
                        <div key={item.user_id} style={styles.item}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: tokens.spacing?.xs }}>
                                <span style={{ fontWeight: 'bold', color: tokens.color?.['accent-secondary'] }}>#{index + 1}</span>
                                <span style={{ color: tokens.color?.['text-100'] }}>{item.user_name}</span>
                            </div>
                            <span style={{ color: tokens.color?.warning, fontWeight: 'bold' }}>{item.stars} <Star size={16} /></span>
                        </div>
                    ))}
                </div>
            </div>
            <style>{`.star-send-hover:hover { box-shadow: 0 0 10px ${tokens.color?.warning}77; transform: translateY(-1px); }`}</style>
        </div>
    );
});

StarRecognitionWidget.displayName = 'StarRecognitionWidget';
export default StarRecognitionWidget;