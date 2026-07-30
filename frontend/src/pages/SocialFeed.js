// /frontend/src/pages/SocialFeed.js - live social feed, recognition leaderboard, and innovation-vote chart
import React, { useMemo, memo, useState, useCallback } from 'react';
import { theme as tokens } from '../theme';

// CRITICAL API IMPORTS
import {
    getSocialFeed, postSocialPost, getRecognitionLeaderboard,
    giveRecognitionStar, getInnovationIdeas
} from '../config/api';
import { useApi } from '../hooks/useApi';
import { useToast } from '../hooks/use-toast';
import { useAuth } from '../contexts/AuthContext';

// UI COMPONENTS
import DataCard from '../components/DataCard';
import BarChartWidget from '../components/charts/BarChartWidget';
import { 
    MessageCircle, Zap, Star, Users, 
    Send, Loader2, ArrowUp, ArrowDown 
} from 'lucide-react';

// --- Sub-Component: Post Creator ---
const PostCreator = memo(({ refetchFeed }) => {
    const { user } = useAuth();
    const { toast } = useToast();
    const [content, setContent] = useState('');
    const [isPosting, setIsPosting] = useState(false);

    const handlePostSubmit = useCallback(async (e) => {
        e.preventDefault();
        if (!content.trim()) return;

        setIsPosting(true);
        try {
            const payload = { 
                content: content.trim(), 
                user_id: user.id,
                user_name: user.full_name 
            };
            
            // CRITICAL API INTEGRATION 1: Post Social Content
            await postSocialPost(payload); 
            
            toast({ title: 'Post Sent', description: 'Your message has been shared with the organization.', variant: 'success' });
            setContent('');
            refetchFeed(); // Immediately refresh the main feed
        } catch (error) {
            console.error("Post failed:", error);
            toast({ title: 'Post Failed', description: error.response?.data?.detail || error.message, variant: 'destructive' });
        } finally {
            setIsPosting(false);
        }
    }, [content, user, toast, refetchFeed]);

    const styles = useMemo(() => ({
        card: { padding: tokens.spacing?.md, background: tokens.color?.['panel-700'], borderRadius: tokens.border?.radius?.card, marginBottom: tokens.spacing?.lg },
        textarea: { width: '100%', padding: '10px', background: tokens.color?.['bg-input'], border: `1px solid ${tokens.color?.['border-600']}`, borderRadius: tokens.border?.radius?.input, color: tokens.color?.['text-100'], boxSizing: 'border-box', minHeight: '80px', resize: 'vertical' },
        button: { padding: '8px 15px', background: tokens.color?.success, border: 'none', borderRadius: tokens.border?.radius?.button, color: tokens.color?.['bg-deep'], cursor: 'pointer', transition: 'all 0.2s ease', display: 'flex', alignItems: 'center', gap: tokens.spacing?.xs, float: 'right', marginTop: tokens.spacing?.xs },
    }), []);

    return (
        <div style={styles.card}>
            <form onSubmit={handlePostSubmit}>
                <textarea
                    style={styles.textarea}
                    value={content}
                    onChange={(e) => setContent(e.target.value)}
                    placeholder="Share an achievement, ask a question, or give a shout-out to a colleague..."
                    disabled={isPosting}
                />
                <button 
                    type="submit" 
                    style={styles.button} 
                    disabled={isPosting || !content.trim()}
                    className="post-submit-hover"
                >
                    {isPosting ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
                    Post
                </button>
            </form>
        </div>
    );
});
PostCreator.displayName = 'PostCreator';

// --- Sub-Component: Social Feed List ---
const FeedList = memo(({ posts, isLoading, error }) => {
    const styles = useMemo(() => ({
        post: { padding: tokens.spacing?.md, background: tokens.color?.['panel-700'], borderRadius: tokens.border?.radius?.card, marginBottom: tokens.spacing?.md, borderLeft: `4px solid ${tokens.color?.['accent-primary']}` },
        header: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: tokens.spacing?.xs },
        meta: { fontSize: tokens.typography?.small?.fontSize, color: tokens.color?.['muted-500'] }, // Added optional chaining
        content: { color: tokens.color?.['text-100'], whiteSpace: 'pre-wrap', wordBreak: 'break-word', marginBottom: tokens.spacing?.sm },
        status: { textAlign: 'center', color: tokens.color?.['muted-500'], padding: tokens.spacing?.xl }
    }), []);

    if (isLoading) {
        return <div style={styles.status}><Loader2 size={24} className="animate-spin" /> Loading feed...</div>;
    }
    if (error) {
        return <div style={styles.status}><p style={{ color: tokens.color?.danger }}>Error loading feed: {error.message}</p></div>;
    }
    if (posts?.length === 0) {
        return <div style={styles.status}><p>No posts yet. Be the first to share something!</p></div>;
    }

    return (
        <div>
            {posts?.map(post => (
                <div key={post.id} style={styles.post}>
                    <div style={styles.header}>
                        <span style={{ fontWeight: 'bold', color: tokens.color?.['accent-primary'] }}>{post.user_name || 'Anonymous'}</span>
                        <span style={styles.meta}>{new Date(post.timestamp).toLocaleString()}</span>
                    </div>
                    <p style={styles.content}>{post.content}</p>
                    <div style={{ display: 'flex', gap: tokens.spacing?.md, fontSize: tokens.typography?.small?.fontSize, color: tokens.color?.['muted-500'] }}>
                        <span><ArrowUp size={14} style={{ marginRight: '4px' }} /> {post.upvotes || 0}</span>
                        <span><ArrowDown size={14} style={{ marginRight: '4px' }} /> {post.downvotes || 0}</span>
                    </div>
                </div>
            ))}
        </div>
    );
});
FeedList.displayName = 'FeedList';

// --- Sub-Component: Recognition Leaderboard ---
const RecognitionLeaderboard = memo(({ leaderboard, isLoading, error, refetchLeaderboard }) => {
    const { toast } = useToast();
    const { user } = useAuth();
    
    // CRITICAL: Handle Giving a Recognition Star
    const handleGiveStar = useCallback(async (targetUserId, targetUserName) => {
        const reason = window.prompt(`Give a Star to ${targetUserName}? Enter a brief reason:`);
        if (!reason) return;

        try {
            // CRITICAL API INTEGRATION 3: Give Recognition Star
            await giveRecognitionStar(targetUserId, reason); 
            toast({ title: 'Star Given!', description: `You recognized ${targetUserName} for: ${reason}`, variant: 'warning' });
            refetchLeaderboard();
        } catch (error) {
            console.error("Recognition failed:", error);
            toast({ title: 'Recognition Failed', description: error.response?.data?.detail || error.message, variant: 'destructive' });
        }
    }, [toast, refetchLeaderboard]);


    const styles = useMemo(() => ({
        card: { padding: tokens.spacing?.md, background: tokens.color?.['panel-800'], borderRadius: tokens.border?.radius?.card, minHeight: '400px', overflowY: 'auto' },
        item: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', borderBottom: `1px dotted ${tokens.color?.['border-700']}` },
        starButton: { padding: '5px 10px', background: tokens.color?.warning, border: 'none', borderRadius: tokens.border?.radius?.button, color: tokens.color?.['bg-deep'], cursor: 'pointer', transition: 'all 0.2s ease', display: 'flex', alignItems: 'center', gap: tokens.spacing?.xs, fontSize: tokens.typography?.small?.fontSize }, // Added optional chaining
    }), []);

    return (
        <div style={styles.card}>
            <h3 style={{ color: tokens.color?.['text-100'], borderBottom: `1px solid ${tokens.color?.['border-600']}`, paddingBottom: tokens.spacing?.xs, marginBottom: tokens.spacing?.md }}>
                <Star size={20} color={tokens.color?.warning} style={{ marginRight: tokens.spacing?.xs }} /> Recognition Leaderboard
            </h3>
            {isLoading && <p style={{textAlign: 'center'}}><Loader2 size={20} className="animate-spin" /> Loading leaderboard...</p>}
            {error && <p style={{ color: tokens.color?.danger }}>Error loading leaderboard.</p>}
            
            {leaderboard?.map((item, index) => (
                <div key={item.user_id} style={styles.item}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: tokens.spacing?.xs }}>
                        <span style={{ fontWeight: 'bold', color: tokens.color?.['accent-secondary'] }}>#{index + 1}</span>
                        <span style={{ color: tokens.color?.['text-100'] }}>{item.user_name}</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: tokens.spacing?.md }}>
                        <span style={{ color: tokens.color?.warning, fontWeight: 'bold' }}>{item.stars} <Star size={16} /></span>
                        {item.user_id !== user.id && ( // Cannot give star to self
                            <button 
                                onClick={() => handleGiveStar(item.user_id, item.user_name)}
                                style={styles.starButton}
                                className="give-star-hover"
                            >
                                <Star size={14} /> Give Star
                            </button>
                        )}
                    </div>
                </div>
            ))}
        </div>
    );
});
RecognitionLeaderboard.displayName = 'RecognitionLeaderboard';


// --- MAIN SOCIAL FEED COMPONENT ---
export const SocialFeed = memo(() => {
    // CRITICAL API INTEGRATION 2: Fetch Social Feed (Polls every 30s for a 'live' feel)
    const { 
        data: posts, 
        isLoading: isFeedLoading, 
        error: feedError, 
        refetch: refetchFeed 
    } = useApi(getSocialFeed, [], true, 30000); // CRITICAL FIX: Corrected polling interval to 30000ms
    
    // CRITICAL API INTEGRATION 4: Fetch Recognition Leaderboard
    const { 
        data: leaderboard, 
        isLoading: isLeaderboardLoading, 
        error: leaderboardError, 
        refetch: refetchLeaderboard
    } = useApi(getRecognitionLeaderboard, [], true, []);

    // CRITICAL API INTEGRATION 5: Innovation ideas, charted by real vote counts.
    const { data: ideas } = useApi(getInnovationIdeas, [], true);
    const ideaVotes = useMemo(
        () => (Array.isArray(ideas) ? ideas : (ideas?.ideas || []))
            .map((i) => ({ name: i.title || i.name || i.idea || 'Idea', value: Number(i.votes ?? i.upvotes ?? i.score) || 0 }))
            .slice(0, 8),
        [ideas]
    );

    const styles = useMemo(() => ({
        grid: { display: 'grid', gridTemplateColumns: '2fr 1fr', gap: tokens.spacing?.lg },
        feedColumn: { gridColumn: 'span 2' }, // Take full width initially
        sidebarColumn: { gridColumn: 'span 1' },
        header: {
            color: tokens.color?.['text-100'],
            marginBottom: tokens.spacing?.lg,
            borderBottom: `1px solid ${tokens.color?.['border-600']}`,
            paddingBottom: tokens.spacing?.md,
        },
        title: {
            fontSize: tokens.typography?.h1?.fontSize, // Added optional chaining
            margin: 0,
            display: 'flex',
            alignItems: 'center',
            gap: tokens.spacing?.sm,
        },
    }), []);

    // NOTE: We switch to a 2-column grid after the post creator
    return (
        <div className="portal-container">
            <div style={styles.header}>
                <h1 style={styles.title}>
                    <MessageCircle size={32} color={tokens.color?.success} />
                    Collaboration Hub: Social Feed & Recognition
                </h1>
            </div>

            {/* Post Creator (Always Full Width) */}
            <PostCreator refetchFeed={refetchFeed} />

            <div style={styles.grid}>
                {/* Main Feed */}
                <div style={styles.feedColumn}>
                    <h3 style={{ color: tokens.color?.['text-100'], marginBottom: tokens.spacing?.md }}>Latest Posts</h3>
                    <FeedList 
                        posts={posts || []} 
                        isLoading={isFeedLoading} 
                        error={feedError} 
                    />
                </div>

                {/* Sidebar: Leaderboard */}
                <div style={styles.sidebarColumn}>
                    <RecognitionLeaderboard 
                        leaderboard={leaderboard || []} 
                        isLoading={isLeaderboardLoading} 
                        error={leaderboardError}
                        refetchLeaderboard={refetchLeaderboard}
                    />
                     <div style={{ marginTop: tokens.spacing?.lg }}>
                        <DataCard title="Innovation Ideas by Votes" isChart minHeight="250px">
                            <BarChartWidget data={ideaVotes} minHeight="200px" color={tokens.color?.['accent-primary']} />
                        </DataCard>
                    </div>
                </div>
            </div>

            <style>{`
                .post-submit-hover:hover {
                    box-shadow: 0 0 10px ${tokens.color?.success}77;
                    transform: translateY(-1px);
                }
                .give-star-hover:hover {
                    box-shadow: 0 0 5px ${tokens.color?.warning}77;
                    transform: scale(1.05);
                }
            `}</style>
        </div>
    );
});

SocialFeed.displayName = 'SocialFeed';
export default SocialFeed;