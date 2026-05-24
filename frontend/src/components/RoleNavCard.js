// /frontend/src/components/RoleNavCard.js - FINAL PRODUCTION-READY REPLACEMENT
import React, { useMemo, memo } from 'react';
import { Link } from 'react-router-dom';
import { theme as tokens } from '../theme';
import { ArrowRight } from 'lucide-react';

/**
 * Navigation card used on the RoleNavDashboard.
 * @param {object} item - Navigation item from SIDEBAR_NAV.
 */
const RoleNavCard = memo(({ item }) => {
    
    // CRITICAL FIX: Ensure color fallback from token map
    const accentColor = tokens.color?.[item.color] || tokens.color?.['accent-primary'];
    const Icon = item.icon;

    const styles = useMemo(() => ({
        container: {
            background: tokens.color?.['panel-800'],
            borderRadius: tokens.border?.radius?.card,
            padding: tokens.spacing?.lg,
            boxShadow: tokens.shadow?.default,
            borderLeft: `4px solid ${accentColor}`,
            height: '100%',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            transition: 'all 0.3s ease',
        },
        header: {
            display: 'flex',
            alignItems: 'center',
            gap: tokens.spacing?.md,
            marginBottom: tokens.spacing?.md,
        },
        title: {
            color: tokens.color?.['text-100'],
            fontSize: tokens.typography.h3.fontSize,
            margin: 0,
        },
        description: {
            color: tokens.color?.['muted-500'],
            fontSize: tokens.typography.base.fontSize,
            margin: '0 0 10px 0',
        },
        link: {
            textDecoration: 'none',
            color: accentColor,
            fontWeight: 'bold',
            display: 'flex',
            alignItems: 'center',
            gap: tokens.spacing?.xs,
            marginTop: tokens.spacing?.sm,
        }
    }), [accentColor]);

    // Simple description mapping for presentation
    const getDescription = (label) => {
        if (label.includes('HR Portal')) return 'Policy, compensation, and talent management access.';
        if (label.includes('Manager Portal')) return 'Team overview, approvals, and Digital Twin simulations.';
        if (label.includes('Orchestrator')) return 'Control center for AI Agents and system governance.';
        return `Quick access to ${item.label.toLowerCase()} functions.`;
    };

    return (
        <Link to={item.path} style={{ textDecoration: 'none' }}>
            <div style={styles.container} className="nav-card-hover">
                <div style={styles.content}>
                    <div style={styles.header}>
                        <Icon size={32} color={accentColor} />
                        <h3 style={styles.title}>{item.label}</h3>
                    </div>
                    <p style={styles.description}>{getDescription(item.label)}</p>
                </div>
                <div style={styles.link}>
                    Go to Portal <ArrowRight size={16} />
                </div>
            </div>
            <style>{`.nav-card-hover:hover { transform: translateY(-5px); box-shadow: 0 8px 15px ${accentColor}40; }`}</style>
        </Link>
    );
});

RoleNavCard.displayName = 'RoleNavCard';
export default RoleNavCard;