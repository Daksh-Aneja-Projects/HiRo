// /frontend/src/components/OrchestratorResultWidget.js - VERIFIED PRODUCTION-READY (STABLE) - (Fixes fontSize TypeErrors)

import React, { useState, useEffect, useMemo, memo } from 'react';
import { Loader2, Zap, Clock, CheckCircle, XCircle, AlertTriangle, MessageSquare, X } from 'lucide-react'; // Ensure X is imported
import { theme as tokens } from '../theme';
import { getOrchestrationResultStatus } from '../config/api'; 

const OrchestratorResultWidget = memo(({ resultId, prompt, onDismiss }) => {
    // PENDING, ANALYZING, RUNNING_TWIN, FINALIZING, COMPLETE, ERROR
    const [status, setStatus] = useState('PENDING'); 
    const [progress, setProgress] = useState(10);
    const [finalResult, setFinalResult] = useState('');
    
    // CRITICAL: Polling Implementation
    useEffect(() => {
        let intervalId;
        // Mocking polling for development environment
        const MOCK_POLLING = process.env.NODE_ENV === 'development' && resultId.includes('MOCK_ID_');
        let mockProgress = 10;

        const pollStatus = async () => {
            if (!resultId) {
                clearInterval(intervalId);
                return;
            }

            if (MOCK_POLLING) {
                // Mock state progression
                mockProgress += 10;
                let newStatus = 'RUNNING_TWIN';
                if (mockProgress >= 100) {
                    newStatus = 'COMPLETE';
                    mockProgress = 100;
                }
                setStatus(newStatus);
                setProgress(mockProgress);
                setFinalResult(mockProgress === 100 ? 'Successfully applied proposed configuration.' : '');
                
            } else {
                try {
                    // This calls the backend route /api/orchestrate/status/{resultId}
                    const response = await getOrchestrationResultStatus(resultId);
                    
                    const newStatus = response.data?.status?.toUpperCase() || 'PENDING';
                    const newProgress = response.data?.progress || progress;
                    const newResult = response.data?.final_result || finalResult;

                    setStatus(newStatus);
                    setProgress(newProgress);
                    setFinalResult(newResult);
                } catch (error) {
                    console.error(`Error fetching orchestration status for ID ${resultId}:`, error);
                    setStatus('ERROR');
                    setFinalResult('Failed to connect to the orchestrator status endpoint.');
                }
            }
            
            // Stop polling on terminal states
            if (status === 'COMPLETE' || status === 'ERROR' || mockProgress === 100) {
                clearInterval(intervalId);
                // Optionally dismiss the widget after a few seconds
                setTimeout(onDismiss, 5000); 
            }
        };

        // Start polling every 2 seconds
        if (resultId) {
            intervalId = setInterval(pollStatus, 2000);
            // Run once immediately
            pollStatus(); 
        }

        // Cleanup on unmount or when resultId changes
        return () => {
            clearInterval(intervalId);
        };
    }, [resultId, onDismiss, status, progress, finalResult]); 


    const getStatusDetails = (currentStatus) => {
        switch (currentStatus) {
            case 'COMPLETE':
                return { label: 'Complete', color: tokens.color?.success, Icon: CheckCircle };
            case 'ERROR':
                return { label: 'Error', color: tokens.color?.danger, Icon: XCircle };
            case 'ANALYZING':
            case 'PENDING':
                return { label: 'Analyzing', color: tokens.color?.warning, Icon: Clock };
            case 'RUNNING_TWIN':
            case 'FINALIZING':
            default:
                return { label: 'In Progress', color: tokens.color?.['accent-primary'], Icon: Loader2 };
        }
    };

    const statusDetails = getStatusDetails(status);
    const { Icon } = statusDetails;

    const styles = useMemo(() => ({
        container: {
            width: '350px',
            background: tokens.color?.['panel-800'],
            border: `1px solid ${statusDetails.color}`,
            borderRadius: tokens.border?.radius?.card,
            padding: tokens.spacing?.md,
            boxShadow: `0 4px 12px rgba(0, 0, 0, 0.5)`
        },
        header: {
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: tokens.spacing?.xs,
        },
        title: {
            color: tokens.color?.['text-100'],
            // --- FIX: Added optional chaining ---
            fontWeight: tokens.typography?.h3?.fontWeight,
            fontSize: tokens.typography?.h3?.fontSize,
            // ------------------------------------
            margin: 0,
        },
        closeButton: {
            background: 'none',
            border: 'none',
            color: tokens.color?.['muted-500'],
            cursor: 'pointer',
            padding: 0,
        }
    }), [statusDetails.color]);


    return (
        <div style={styles.container}>
            <div style={styles.header}>
                <h3 style={styles.title}>AI Orchestration Status</h3>
                <button onClick={onDismiss} style={styles.closeButton} title="Dismiss Widget">
                    <X size={18} />
                </button>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: tokens.spacing?.sm }}>
                <span style={{ color: tokens.color?.['muted-500'], 
                    // --- FIX: Added optional chaining ---
                    fontSize: tokens.typography?.small?.fontSize 
                    // ------------------------------------
                }}>
                    Task ID: {resultId}
                </span>
                <span style={{ color: statusDetails.color, 
                    // --- FIX: Added optional chaining ---
                    fontWeight: tokens.typography?.h2?.fontWeight, 
                    fontSize: tokens.typography?.small?.fontSize 
                    // ------------------------------------
                , display: 'flex', alignItems: 'center' }}>
                    <Icon size={16} style={{ marginRight: tokens.spacing?.xs }} className={statusDetails.label === 'In Progress' || statusDetails.label === 'Analyzing' ? 'animate-spin' : ''} />
                    {statusDetails.label.toUpperCase()}
                </span>
            </div>

            <p style={{ color: tokens.color?.['muted-500'], marginBottom: tokens.spacing?.sm, 
                // --- FIX: Added optional chaining ---
                fontSize: tokens.typography?.small?.fontSize
                // ------------------------------------
                , fontStyle: 'italic' }}>
                Command: "{prompt}"
            </p>

            <div style={{ background: tokens.color?.['panel-700'], borderRadius: tokens.border?.radius?.chip, overflow: 'hidden' }}>
                <div 
                    style={{ 
                        width: `${progress}%`, 
                        height: '8px', 
                        background: statusDetails.color,
                        transition: 'width 0.5s ease'
                    }} 
                    title={`${progress}% Complete`}
                />
            </div>
            
            {finalResult && (
                 <p style={{ color: tokens.color?.['text-100'], marginTop: tokens.spacing?.sm, 
                    // --- FIX: Added optional chaining ---
                    fontSize: tokens.typography?.small?.fontSize 
                    // ------------------------------------
                 }}>
                    **Result:** {finalResult}
                 </p>
            )}
        </div>
    );
});

OrchestratorResultWidget.displayName = 'OrchestratorResultWidget';
export default OrchestratorResultWidget;