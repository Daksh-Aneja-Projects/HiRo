// /frontend/src/components/cards/DataCard.js - FINAL PRODUCTION-READY REPLACEMENT (Hardened against TypeErrors)
import React, { memo } from 'react';
import { theme as tokens } from '../../theme';
import { TrendingUp } from 'lucide-react';

// FIX: Implement optional chaining for robust theme access
const getStyles = (tokens, color) => ({
    card: {
        background: tokens.color?.['panel-800'],
        borderRadius: tokens.border?.radius?.card,
        padding: tokens.spacing?.lg,
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        height: '100%',
        boxShadow: tokens.shadow?.default,
        transition: 'transform 150ms ease',
    },
    header: {
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: tokens.spacing?.md,
    },
    title: {
        // CRITICAL FIX: Ensure optional chaining
        fontSize: tokens.typography?.small?.fontSize,
        fontWeight: tokens.typography?.small?.fontWeight, 
        color: tokens.color?.['muted-500'],
        margin: 0,
    },
    body: {
        display: 'flex',
        alignItems: 'baseline',
        gap: tokens.spacing?.xs,
    },
    value: {
        // CRITICAL FIX: Ensure optional chaining
        fontSize: tokens.typography?.h2?.fontSize,
        fontWeight: tokens.typography?.h2?.fontWeight, 
        color: color || tokens.color?.['text-100'],
        lineHeight: 1,
        margin: 0,
    },
    unit: {
        // CRITICAL FIX: Ensure optional chaining
        fontSize: tokens.typography?.base?.fontSize,
        color: tokens.color?.['muted-500'],
    },
});

const DataCard = memo(({ title, value, unit, color, children }) => {
    // Determine the color for the primary value/icon, falling back to accent-primary
    const primaryColor = color || tokens.color?.['accent-primary'];
    // CRITICAL: Ensure tokens is in the dependency array or passed/memoized correctly
    const styles = React.useMemo(() => getStyles(tokens, primaryColor), [tokens, primaryColor]);

    return (
        <div style={styles.card} className="data-card">
            <div style={styles.header}>
                <h4 style={styles.title}>{title}</h4>
                {/* Render the icon passed as a child, or a default icon */}
                <div style={{ color: primaryColor }}>
                    {children ? children : <TrendingUp size={24} />}
                </div>
            </div>
            <div style={styles.body}>
                <p style={styles.value}>{value}</p>
                {unit && <span style={styles.unit}>{unit}</span>}
            </div>
            {/* Conditional CSS for hover effects */}
            <style>{` 
                .data-card:hover {
                    transform: translateY(-2px);
                    box-shadow: ${tokens.shadow?.hover};
                }
            `}</style>
        </div>
    );
});

DataCard.displayName = 'DataCard';

export default DataCard;