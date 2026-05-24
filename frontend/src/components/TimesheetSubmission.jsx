// /frontend/src/components/TimesheetSubmission.jsx - FINAL PRODUCTION-READY REPLACEMENT
import React, { useState, useCallback, useMemo, memo } from 'react';
import { theme as tokens } from '../theme';
import { useAuth } from '../contexts/AuthContext';
import { useToast } from '../hooks/use-toast';
import { runTimesheetPreCheck, submitTimesheet } from '../config/api'; // CRITICAL FIX: Import stabilized APIs
import { Send, Loader2, CheckCircle, AlertTriangle } from 'lucide-react';

const TimesheetSubmission = memo(() => {
    const { user } = useAuth();
    const { toast } = useToast();
    const [hours, setHours] = useState(40);
    const [period, setPeriod] = useState('2024-W24');
    const [status, setStatus] = useState('READY'); // READY, CHECKING, VIOLATION, PASSED, SUBMITTING
    const [isSubmitting, setIsSubmitting] = useState(false);
    
    const employeeId = user?.id || 'ESS_USER_123';

    // CRITICAL: Handle Policy Pre-Check
    const handlePreCheck = useCallback(async () => {
        if (status === 'CHECKING' || isSubmitting) return;

        setStatus('CHECKING');
        const submissionData = { hours, period, employee_id: employeeId };

        try {
            // CRITICAL API INTEGRATION 1: Run Pre-Check
            const response = await runTimesheetPreCheck(submissionData);
            
            if (response.data.status === 'PASS') {
                setStatus('PASSED');
                toast({ title: 'Policy Check Passed', description: 'Timesheet is compliant with policy.', variant: 'success' });
            } else {
                setStatus('VIOLATION');
                toast({ title: 'Policy Violation', description: response.data.details || 'Violation detected! Review hours.', variant: 'warning' });
            }
        } catch (error) {
            setStatus('READY');
            toast({ title: 'Check Error', description: error.message, variant: 'destructive' });
        }
    }, [hours, period, employeeId, status, isSubmitting, toast]);
    
    // CRITICAL: Handle Timesheet Submission
    const handleSubmit = useCallback(async (e) => {
        e.preventDefault();
        if (isSubmitting || status === 'VIOLATION') return;

        setIsSubmitting(true);
        setStatus('SUBMITTING');
        
        try {
            // CRITICAL API INTEGRATION 2: Submit Timesheet
            await submitTimesheet({ hours, period, employee_id: employeeId, status: 'SUBMITTED' });
            
            toast({ title: 'Submission Success', description: 'Timesheet submitted successfully.', variant: 'success' });
            setStatus('READY');
        } catch (error) {
            setStatus('READY');
            toast({ title: 'Submission Failed', description: error.response?.data?.detail || error.message, variant: 'destructive' });
        } finally {
            setIsSubmitting(false);
        }
    }, [hours, period, employeeId, status, isSubmitting, toast]);


    const styles = useMemo(() => ({
        container: { padding: tokens.spacing?.xl, background: tokens.color?.['panel-800'], borderRadius: tokens.border?.radius?.card, maxWidth: '600px', margin: '0 auto' },
        input: { padding: '10px 12px', background: tokens.color?.['bg-input'], border: `1px solid ${tokens.color?.['border-600']}`, borderRadius: tokens.border?.radius?.input, color: tokens.color?.['text-100'], width: '100%', boxSizing: 'border-box', marginBottom: tokens.spacing?.md },
        buttonRow: { display: 'flex', gap: tokens.spacing?.md, marginTop: tokens.spacing?.lg },
        checkButton: (isPassed) => ({
            background: isPassed ? tokens.color?.success : tokens.color?.warning,
            color: tokens.color?.['bg-deep'],
            width: '50%',
        }),
        submitButton: {
            background: tokens.color?.['accent-primary'],
            color: tokens.color?.['bg-deep'],
            width: '50%',
        },
        baseButton: { padding: '10px 20px', border: 'none', borderRadius: tokens.border?.radius?.button, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: tokens.spacing?.xs, transition: 'all 0.2s ease' }
    }), []);
    
    const isPassed = status === 'PASSED';
    const canSubmit = isPassed || status === 'READY';
    const buttonLabel = isSubmitting ? 'Submitting...' : 'Submit Timesheet';
    
    return (
        <div style={styles.container}>
            <h2 style={{ color: tokens.color?.['text-100'] }}>Timesheet Submission</h2>
            <form onSubmit={handleSubmit}>
                <label style={{ color: tokens.color?.['muted-500'], display: 'block' }}>Total Hours:</label>
                <input type="number" value={hours} onChange={e => setHours(parseInt(e.target.value))} style={styles.input} required />
                
                <label style={{ color: tokens.color?.['muted-500'], display: 'block' }}>Pay Period:</label>
                <input type="text" value={period} onChange={e => setPeriod(e.target.value)} style={styles.input} required />

                <div style={{...styles.buttonRow, marginTop: tokens.spacing?.md }}>
                    <button 
                        type="button" 
                        onClick={handlePreCheck} 
                        style={{...styles.baseButton, ...styles.checkButton(isPassed)}}
                        disabled={status === 'CHECKING'}
                        className="timesheet-check-hover"
                    >
                        {status === 'CHECKING' ? <Loader2 size={16} className="animate-spin" /> : (isPassed ? <CheckCircle size={16} /> : <AlertTriangle size={16} />)}
                        {status === 'CHECKING' ? 'Checking...' : 'Run Policy Pre-Check'}
                    </button>
                    
                    <button 
                        type="submit" 
                        style={{...styles.baseButton, ...styles.submitButton}}
                        disabled={isSubmitting || !canSubmit}
                        className="timesheet-submit-hover"
                    >
                        {isSubmitting ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
                        {buttonLabel}
                    </button>
                </div>

                <p style={{ marginTop: tokens.spacing?.lg, color: tokens.color?.['muted-500'], fontSize: tokens.typography.small.fontSize, textAlign: 'center' }}>
                    Current Status: <span style={{ color: isPassed ? tokens.color?.success : (status === 'VIOLATION' ? tokens.color?.danger : tokens.color?.warning), fontWeight: 'bold' }}>{status}</span>
                </p>
            </form>
            <style>{`
                .timesheet-check-hover:hover { box-shadow: 0 0 10px ${tokens.color?.warning}77; transform: translateY(-1px); }
                .timesheet-submit-hover:hover { box-shadow: 0 0 10px ${tokens.color?.['accent-primary']}77; transform: translateY(-1px); }
            `}</style>
        </div>
    );
});

TimesheetSubmission.displayName = 'TimesheetSubmission';
export default TimesheetSubmission;