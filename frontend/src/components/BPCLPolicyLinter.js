// /frontend/src/components/BPCLPolicyLinter.js - FINAL PRODUCTION-READY REPLACEMENT (Fixes fontSize TypeErrors)
import React, { useMemo, memo, useState, useCallback } from 'react';
import { theme as tokens } from '../theme';
import { securityScanBpcl } from '../config/api'; // CRITICAL FIX: Import the scanning API function
import { useToast } from '../hooks/use-toast';
import { Shield, Loader2, Zap, AlertTriangle, CheckCircle } from 'lucide-react';

const MOCK_BPCL_CODE = `
BPCL_POLICY {
  NAME: "PTO_LIMIT_CONSECUTIVE_DAYS"
  SCOPE: EMPLOYEE
  CONSTRAINT: IF (transaction.type == "PTO_REQUEST" AND transaction.duration_days > 5) THEN DENY_TRANSACTION
  AUDIT_LEVEL: HIGH
}`;

const BPCLPolicyLinter = memo(() => {
    const { toast } = useToast();
    const [bpclCode, setBpclCode] = useState(MOCK_BPCL_CODE);
    const [isScanning, setIsScanning] = useState(false);
    const [scanResult, setScanResult] = useState(null);

    // CRITICAL: Handle BPCL Scanning
    const handleScan = useCallback(async (e) => {
        e.preventDefault();
        if (!bpclCode.trim() || isScanning) return;

        setIsScanning(true);
        setScanResult(null);

        try {
            // CRITICAL API INTEGRATION: Scan BPCL for security issues
            const response = await securityScanBpcl(bpclCode);
            
            // Assuming response.data contains: { passed: boolean, security_issues: [], policy_conflicts: [] }
            setScanResult(response.data);
            
            if (response.data.passed) {
                toast({ title: 'Scan Passed', description: 'BPCL code is clean and compliant.', variant: 'success' });
            } else {
                 toast({ title: 'Scan Failed', description: 'Policy conflicts or security risks detected.', variant: 'warning' });
            }
        } catch (error) {
            console.error("BPCL scanning failed:", error);
            toast({ title: 'Scan Error', description: error.response?.data?.detail || error.message, variant: 'destructive' });
        } finally {
            setIsScanning(false);
        }
    }, [bpclCode, isScanning, toast]);


    const styles = useMemo(() => ({
        grid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: tokens.spacing?.lg, height: '100%' },
        card: { padding: tokens.spacing?.md, background: tokens.color?.['panel-700'], borderRadius: tokens.border?.radius?.card, display: 'flex', flexDirection: 'column' },
        textarea: { 
            width: '100%', 
            padding: '10px', 
            background: tokens.color?.['panel-800'], 
            border: `1px solid ${tokens.color?.['border-600']}`, 
            borderRadius: tokens.border?.radius?.input, 
            color: tokens.color?.['text-100'], 
            boxSizing: 'border-box', 
            minHeight: '300px', 
            resize: 'vertical', 
            fontFamily: 'monospace', 
            // --- FIX: Added optional chaining ---
            fontSize: tokens.typography?.small?.fontSize 
            // ------------------------------------
        },
        button: (bgColor) => ({ padding: '10px 20px', background: bgColor, border: 'none', borderRadius: tokens.border?.radius?.button, color: tokens.color?.['bg-deep'], cursor: 'pointer', transition: 'all 0.2s ease', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: tokens.spacing?.xs, width: '100%', marginTop: tokens.spacing?.md }),
        resultBox: (passed) => ({ padding: tokens.spacing?.md, background: passed ? tokens.color?.success + '20' : tokens.color?.danger + '20', border: `1px solid ${passed ? tokens.color?.success : tokens.color?.danger}`, borderRadius: tokens.border?.radius?.input, marginTop: tokens.spacing?.md }),
    }), []);

    const passed = scanResult?.passed === true;

    return (
        <div style={styles.grid}>
            {/* BPCL Input */}
            <div style={styles.card}>
                <h3 style={{ color: tokens.color?.['text-100'], margin: 0 }}>Input BPCL Code</h3>
                <form onSubmit={handleScan} style={{ flexGrow: 1, display: 'flex', flexDirection: 'column' }}>
                    <textarea 
                        style={styles.textarea} 
                        value={bpclCode}
                        onChange={(e) => setBpclCode(e.target.value)}
                        placeholder="Enter BPCL code here..."
                        disabled={isScanning}
                        required
                    />
                    <button 
                        type="submit" 
                        style={styles.button(tokens.color?.success)} 
                        disabled={isScanning}
                        className="bpcl-scan-hover"
                    >
                        {isScanning ? <Loader2 size={16} className="animate-spin" /> : <Shield size={16} />}
                        {isScanning ? 'Run Security & Policy Scan' : 'Run Security & Policy Scan'}
                    </button>
                </form>
            </div>

            {/* Scan Results */}
            <div style={styles.card}>
                <h3 style={{ color: tokens.color?.['text-100'], margin: 0 }}>Scan Results</h3>
                
                {scanResult && (
                    <div style={styles.resultBox(passed)}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: tokens.spacing?.sm }}>
                            {passed ? <CheckCircle size={24} color={tokens.color?.success} /> : <AlertTriangle size={24} color={tokens.color?.danger} />}
                            <h4 style={{ margin: 0, color: passed ? tokens.color?.success : tokens.color?.danger }}>
                                Scan Status: {passed ? 'PASSED' : 'FAILED'}
                            </h4>
                        </div>
                        
                        <p style={{ color: tokens.color?.['muted-500'], borderBottom: `1px dotted ${tokens.color?.['border-700']}`, paddingBottom: tokens.spacing?.xs, marginTop: tokens.spacing?.sm }}>
                            Security Issues Found: {scanResult.security_issues?.length || 0}
                        </p>
                        <ul>
                            {scanResult.security_issues?.map((issue, index) => (
                                <li key={index} style={{ color: tokens.color?.danger, 
                                    // --- FIX: Added optional chaining ---
                                    fontSize: tokens.typography?.small?.fontSize 
                                    // ------------------------------------
                                }}>{issue.description || issue}</li>
                            ))}
                        </ul>
                        
                        <p style={{ color: tokens.color?.['muted-500'], borderBottom: `1px dotted ${tokens.color?.['border-700']}`, paddingBottom: tokens.spacing?.xs, marginTop: tokens.spacing?.sm }}>
                            Policy Conflicts Found: {scanResult.policy_conflicts?.length || 0}
                        </p>
                         <ul>
                            {scanResult.policy_conflicts?.map((conflict, index) => (
                                <li key={index} style={{ color: tokens.color?.warning, 
                                    // --- FIX: Added optional chaining ---
                                    fontSize: tokens.typography?.small?.fontSize 
                                    // ------------------------------------
                                }}>{conflict.description || conflict}</li>
                            ))}
                        </ul>
                    </div>
                )}
                 {!scanResult && !isScanning && (
                    <p style={{ textAlign: 'center', color: tokens.color?.['muted-500'], marginTop: tokens.spacing?.xl }}>
                        Submit code to initiate the deep semantic scan.
                    </p>
                )}
            </div>
            
            <style>{`
                .bpcl-scan-hover:hover { box-shadow: 0 0 10px ${tokens.color?.success}77; transform: translateY(-1px); }
            `}</style>
        </div>
    );
});

BPCLPolicyLinter.displayName = 'BPCLPolicyLinter';
export default BPCLPolicyLinter;