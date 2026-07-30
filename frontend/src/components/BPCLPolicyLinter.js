// BPCL rule bench - write a machine-enforceable rule (or have the local model
// draft one from a sentence of plain English) and put it through the real
// verification compiler before it goes anywhere near a policy version.
import React, { memo, useCallback, useState } from 'react';
import { theme as tokens } from '../theme';
import { securityScanBpcl, deployBPCLFromPrompt } from '../config/api';
import { useToast } from '../hooks/use-toast';
import { Shield, Loader2, AlertTriangle, CheckCircle2, Sparkles, Send } from 'lucide-react';
import { s, dim, apiError } from './policy/ui';

const EXAMPLE = `BPCL_POLICY {
  NAME: "PTO_LIMIT_CONSECUTIVE_DAYS"
  SCOPE: EMPLOYEE
  CONSTRAINT: IF (transaction.type == "PTO_REQUEST" AND transaction.duration_days > 5) THEN DENY_TRANSACTION
  AUDIT_LEVEL: HIGH
}`;

const BPCLPolicyLinter = memo(() => {
    const { toast } = useToast();
    const [code, setCode] = useState('');
    const [prompt, setPrompt] = useState('');
    const [policyId, setPolicyId] = useState('');
    const [busy, setBusy] = useState('');
    const [result, setResult] = useState(null);
    const [deployment, setDeployment] = useState(null);

    const scan = useCallback(async (e) => {
        e.preventDefault();
        if (!code.trim()) return;
        setBusy('scan');
        setResult(null);
        try {
            const res = await securityScanBpcl(code);
            setResult(res.data);
            const clean = String(res.data?.status || '').toUpperCase() === 'SECURE';
            toast({
                title: clean ? 'Rule passed verification' : 'Rule needs work',
                description: clean
                    ? 'The compiler found nothing unsafe in this rule.'
                    : `${res.data?.vulnerabilities?.length || 0} problem(s) were flagged.`,
                variant: clean ? 'success' : 'warning',
            });
        } catch (err) {
            toast({ title: 'Verification could not run', description: apiError(err), variant: 'destructive' });
        } finally {
            setBusy('');
        }
    }, [code, toast]);

    const draftFromPrompt = useCallback(async (e) => {
        e.preventDefault();
        const id = policyId.trim();
        if (!id || !prompt.trim()) {
            toast({ title: 'Fill both fields', description: 'Name the policy this rule belongs to and describe the rule in a sentence.', variant: 'warning' });
            return;
        }
        setBusy('draft');
        try {
            const res = await deployBPCLFromPrompt(id, prompt.trim());
            setDeployment(res.data);
            toast({
                title: 'Rule drafting queued',
                description: `The local model is compiling your sentence into a rule for ${id}. Tracking reference ${res.data?.task_id}.`,
                variant: 'success',
            });
        } catch (err) {
            toast({ title: 'Could not queue the rule', description: apiError(err), variant: 'destructive' });
        } finally {
            setBusy('');
        }
    }, [policyId, prompt, toast]);

    const status = String(result?.status || '').toUpperCase();
    const clean = status === 'SECURE';
    const problems = Array.isArray(result?.vulnerabilities) ? result.vulnerabilities : [];

    const styles = {
        grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: tokens.spacing?.lg, alignItems: 'start' },
        verdict: {
            padding: '12px 14px', borderRadius: 10, marginTop: 14,
            border: `1px solid ${clean ? tokens.color?.success : tokens.color?.danger}`,
            background: 'rgba(255,255,255,0.03)',
        },
    };

    return (
        <div style={styles.grid}>
            <div style={s.panel}>
                <h3 style={s.sectionTitle}><Sparkles size={16} color={tokens.color?.['accent-secondary']} /> Draft a rule from a sentence</h3>
                <p style={{ ...s.hint, margin: '8px 0 12px' }}>
                    Describe the rule the way you would to a colleague. The local model compiles it into an enforceable rule and files it against the policy you name.
                </p>
                <form onSubmit={draftFromPrompt}>
                    <label style={s.label}>Policy this rule belongs to</label>
                    <input style={{ ...s.input, width: '100%' }} value={policyId} placeholder="Policy id, for example HR-LEAVE-001"
                           onChange={(e) => setPolicyId(e.target.value)} />
                    <label style={{ ...s.label, marginTop: 12 }}>The rule, in plain English</label>
                    <textarea style={{ ...s.textarea, minHeight: 110, fontFamily: 'inherit', fontSize: 13.5 }} value={prompt}
                              onChange={(e) => setPrompt(e.target.value)}
                              placeholder="Nobody may take more than five consecutive days of leave without their manager approving it first." />
                    <button type="submit" style={{ ...dim(s.btn, busy === 'draft'), marginTop: 12 }} disabled={busy === 'draft'}>
                        {busy === 'draft' ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />} Compile and file the rule
                    </button>
                </form>
                {deployment && (
                    <p style={{ ...s.hint, margin: '12px 0 0' }}>
                        Queued against {deployment.policy_id}. Tracking reference <span style={s.mono}>{deployment.task_id}</span>.
                        The compiled rule is stored server side for review.
                    </p>
                )}
            </div>

            <div style={s.panel}>
                <h3 style={s.sectionTitle}><Shield size={16} color={tokens.color?.success} /> Verify a rule before it ships</h3>
                <p style={{ ...s.hint, margin: '8px 0 12px' }}>
                    Paste a rule and the verification compiler checks it for unsafe constructs. Example shape:
                </p>
                <form onSubmit={scan}>
                    <textarea style={{ ...s.textarea, minHeight: 200 }} value={code} spellCheck={false}
                              onChange={(e) => setCode(e.target.value)} placeholder={EXAMPLE} />
                    <button type="submit" style={{ ...dim(s.btn, busy === 'scan' || !code.trim()), marginTop: 12 }}
                            disabled={busy === 'scan' || !code.trim()}>
                        {busy === 'scan' ? <Loader2 size={15} className="animate-spin" /> : <Shield size={15} />} Run verification
                    </button>
                </form>

                {result && (
                    <div style={styles.verdict}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: clean ? tokens.color?.success : tokens.color?.danger, fontWeight: 600, fontSize: 13.5 }}>
                            {clean ? <CheckCircle2 size={17} /> : <AlertTriangle size={17} />}
                            {clean ? 'Safe to ship' : 'Not safe to ship yet'}
                        </div>
                        <p style={{ color: tokens.color?.['muted-500'], fontSize: 13, margin: '8px 0 0', lineHeight: 1.7 }}>
                            {problems.length === 0
                                ? 'The compiler flagged nothing in this rule.'
                                : `The compiler flagged ${problems.length} problem(s):`}
                        </p>
                        {problems.length > 0 && (
                            <ul style={{ margin: '6px 0 0', paddingLeft: 18, color: tokens.color?.danger, fontSize: 12.5, lineHeight: 1.7 }}>
                                {problems.map((p, i) => (
                                    <li key={i}>{typeof p === 'string' ? p : (p.description || p.message || JSON.stringify(p))}</li>
                                ))}
                            </ul>
                        )}
                        {result.trace && (
                            <p style={{ ...s.mono, marginTop: 10 }}>
                                {typeof result.trace === 'string' ? result.trace : JSON.stringify(result.trace)}
                            </p>
                        )}
                    </div>
                )}
                {!result && busy !== 'scan' && (
                    <p style={{ ...s.hint, margin: '14px 0 0' }}>No rule verified in this session yet.</p>
                )}
            </div>
        </div>
    );
});

BPCLPolicyLinter.displayName = 'BPCLPolicyLinter';
export default BPCLPolicyLinter;
