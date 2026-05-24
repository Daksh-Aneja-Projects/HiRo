// /frontend/src/components/WorkflowCanvasDesign.js - Placeholder for the core BPCL Design Studio

import React from 'react';
import { theme as tokens } from '../theme';
import { GitBranch, PlusSquare, Code } from 'lucide-react';

const WorkflowCanvasDesign = () => {
    const canvasStyle = {
        // FIX: Set a consistent min height for the canvas area
        minHeight: '350px',
        background: tokens.color['bg-900'],
        border: `1px solid ${tokens.color['accent']}`,
        borderRadius: tokens.border.radius.card,
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        color: tokens.color['accent'],
        fontSize: tokens.typography.base.fontSize,
        marginTop: tokens.spacing.md,
        position: 'relative',
    };

    const nodeStyle = {
        padding: '10px 15px',
        background: tokens.color['panel-700'],
        border: `1px solid ${tokens.color['accent']}`,
        borderRadius: tokens.border.radius.chip,
        marginBottom: tokens.spacing.lg,
        boxShadow: tokens.shadow.default,
        display: 'flex',
        alignItems: 'center',
        gap: tokens.spacing.xs,
        color: tokens.color['text-100']
    };

    return (
        <div style={canvasStyle}>
            <p style={{ position: 'absolute', top: tokens.spacing.md, right: tokens.spacing.md, color: tokens.color['muted-500'] }}>BPCL Visual Canvas Engine (Drag & Drop)</p>
            
            <div style={{...nodeStyle, transform: 'translateY(-50px)'}}>
                <GitBranch size={16} /> START: Policy Intent
            </div>
            <div style={{height: '20px', width: '2px', background: tokens.color['accent'], marginBottom: tokens.spacing.md}}></div>
            <div style={nodeStyle}>
                <Code size={16} /> NODE: Enforcement Engine Logic
            </div>
            <div style={{height: '20px', width: '2px', background: tokens.color['accent'], marginBottom: tokens.spacing.md}}></div>
            <div style={{...nodeStyle, background: tokens.color.danger}}>
                <PlusSquare size={16} /> NODE: Policy Impact Simulation Trigger
            </div>
            
            <button style={{ 
                position: 'absolute', 
                bottom: tokens.spacing.md, 
                left: tokens.spacing.md,
                padding: '8px 12px',
                borderRadius: tokens.border.radius.button,
                background: tokens.color['accent-primary'],
                border: 'none',
                color: tokens.color['bg-900'],
                fontWeight: tokens.typography.h2.fontWeight,
                cursor: 'pointer'
            }}>Edit Canvas</button>
        </div>
    );
};

export default WorkflowCanvasDesign;