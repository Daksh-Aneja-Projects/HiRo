// /frontend/src/components/SocialActivityFeed.js - FINAL PRODUCTION-READY REPLACEMENT
import React, { useMemo, memo } from 'react';
import { theme as tokens } from '../theme';
import { useApi } from '../hooks/useApi';
import { getSocialFeed } from '../config/api'; // CRITICAL FIX: Import stabilized API function
import { MessageCircle, Zap, Loader2, AlertTriangle, User, ArrowUp } from 'lucide-react';

const SocialActivityFeed = memo(({ title = "Live Collaboration Activity" }) => {
    
    // CRITICAL API INTEGRATION: Fetch Social Feed (Polling every 15s)
    const { 
        data: posts, 
        isLoading, 
        error 
    } = useApi(getSocialFeed, [], true, 15000); // CRITICAL FIX: Removed extraneous empty array arg and set interval to 15000ms

    const styles = useMemo(() => ({
        container: { padding: tokens.spacing?.md, background: tokens.color?.['panel-800'], borderRadius: tokens.border?.radius?.card, minHeight: '400px', display: 'flex', flexDirection: 'column' },
        header: { color: tokens.color?.['text-100'], borderBottom: `1px solid ${tokens.color?.['border-600']}`, paddingBottom: tokens.spacing?.xs, marginBottom: tokens.spacing?.md },
        feedArea: { flexGrow: 1, overflowY: 'auto' },
        post: { padding: tokens.spacing?.sm, background: tokens.color?.['panel-700'], borderRadius: tokens.border?.radius?.input, marginBottom: tokens.spacing?.sm, borderLeft: `3px solid ${tokens.color?.['accent-primary']}` },
        meta: { fontSize: tokens.typography.small.fontSize, color: tokens.color?.['muted-500'], display: 'flex', alignItems: 'center', gap: tokens.spacing?.xs }
    }), []);

    return (
        <div style={styles.container}>
            <h3 style={styles.header}>
                <MessageCircle size={20} style={{ marginRight: tokens.spacing?.xs }} color={tokens.color?.success} />
                {title}
            </h3>
            
            <div style={styles.feedArea}>
                {isLoading && <p style={{textAlign: 'center'}}><Loader2 size={24} className="animate-spin" /></p>}
                {error && <p style={{ color: tokens.color?.danger }}><AlertTriangle size={16} /> Error loading data.</p>}

                {!isLoading && posts.length === 0 && (
                     <p style={{ textAlign: 'center', color: tokens.color?.['muted-500'], marginTop: tokens.spacing?.lg }}>No activity yet. Be the first!</p>
                )}

                {posts?.map(post => (
                    <div key={post.id} style={styles.post}>
                        <div style={styles.meta}>
                            <User size={14} />
                            <span>{post.user_name || 'System Update'}</span>
                            <span style={{ marginLeft: 'auto' }}>{new Date(post.timestamp).toLocaleTimeString()}</span>
                            <ArrowUp size={14} color={tokens.color?.success} /> {post.upvotes || 0}
                        </div>
                        <p style={{ color: tokens.color?.['text-100'], margin: '5px 0 0 0', fontSize: tokens.typography.base.fontSize }}>
                            {post.content}
                        </p>
                    </div>
                ))}
            </div>
        </div>
    );
});

SocialActivityFeed.displayName = 'SocialActivityFeed';
export default SocialActivityFeed;