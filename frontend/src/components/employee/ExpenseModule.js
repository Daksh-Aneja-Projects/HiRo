// Employee portal: Expenses module.
// Real endpoints: POST /api/hr/expenses (multipart) and POST /api/hr/expenses/ocr-scan
// (local LLM parses the receipt into a draft). The backend exposes no expense
// history endpoint, so this page only ever shows claims filed from this session.
import React, { memo, useCallback, useMemo, useState } from 'react';
import { theme as tokens } from '../../theme';
import { useToast } from '../../hooks/use-toast';
import { submitExpense, scanExpenseReceipt } from '../../config/api';
import DataCard from '../DataCard';
import PieChartWidget from '../charts/PieChartWidget';
import { CountUp } from '../live/LivePrimitives';
import { ui, Btn, EmptyState, StatusPill, fmtDate, money, EmployeeStyles } from './shared';
import { ScanLine, Send, Paperclip, ReceiptText, Info } from 'lucide-react';

const CATEGORIES = ['Travel', 'Meals', 'Accommodation', 'Equipment', 'Training', 'General'];
const BLANK = { amount: '', currency: 'USD', category: 'Travel', description: '', date: '' };

const ExpenseModule = memo(() => {
    const { toast } = useToast();
    const [form, setForm] = useState(BLANK);
    const [receipt, setReceipt] = useState(null);
    const [isScanning, setIsScanning] = useState(false);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [filed, setFiled] = useState([]); // claims filed in this session, straight from the API response

    const set = (key) => (e) => setForm((prev) => ({ ...prev, [key]: e.target.value }));

    const amountNum = Number(form.amount);
    const valid = form.amount !== '' && Number.isFinite(amountNum) && amountNum > 0 && form.category.trim() !== '';

    const byCategory = useMemo(() => {
        const totals = filed.reduce((acc, e) => {
            acc[e.category] = (acc[e.category] || 0) + (Number(e.amount) || 0);
            return acc;
        }, {});
        return Object.entries(totals).map(([name, value]) => ({ name, value: Math.round(value * 100) / 100 }));
    }, [filed]);

    const total = filed.reduce((sum, e) => sum + (Number(e.amount) || 0), 0);

    const handleScan = useCallback(async () => {
        if (!receipt) {
            toast({ title: 'Attach a receipt first', description: 'Choose a receipt file, then scan it.', variant: 'destructive' });
            return;
        }
        setIsScanning(true);
        try {
            const res = await scanExpenseReceipt(receipt);
            const d = res.data || {};
            setForm((prev) => ({
                amount: d.amount ? String(d.amount) : prev.amount,
                currency: d.currency || prev.currency,
                category: d.category || prev.category,
                description: d.vendor || d.description || prev.description,
                date: d.date || prev.date,
            }));
            toast({ title: 'Receipt scanned', description: 'The model filled in what it could read. Check the fields before you submit.', variant: 'success' });
        } catch (err) {
            toast({ title: 'Could not read that receipt', description: err.response?.data?.detail || err.message, variant: 'destructive' });
        } finally {
            setIsScanning(false);
        }
    }, [receipt, toast]);

    const handleSubmit = useCallback(async (e) => {
        e.preventDefault();
        if (!valid) {
            toast({ title: 'Check the form first', description: 'Enter an amount greater than zero and pick a category.', variant: 'destructive' });
            return;
        }
        setIsSubmitting(true);
        try {
            const res = await submitExpense({
                amount: amountNum,
                currency: form.currency,
                category: form.category,
                description: form.description,
                date: form.date,
            }, receipt);
            const saved = res.data?.expense;
            if (saved) setFiled((prev) => [saved, ...prev]);
            toast({ title: 'Expense filed', description: `${money(amountNum, form.currency)} submitted under ${form.category}.`, variant: 'success' });
            setForm(BLANK);
            setReceipt(null);
        } catch (err) {
            toast({ title: 'Could not file that expense', description: err.response?.data?.detail || err.message, variant: 'destructive' });
        } finally {
            setIsSubmitting(false);
        }
    }, [valid, amountNum, form, receipt, toast]);

    return (
        <div style={ui.grid}>
            <EmployeeStyles />

            <div style={{ ...ui.panel, gridColumn: 'span 5' }}>
                <h3 style={ui.h3}>File an expense</h3>
                <p style={ui.hint}>Attach the receipt and let the local model read it, or fill the fields in yourself.</p>

                <div style={{ marginTop: tokens.spacing?.md, display: 'flex', gap: tokens.spacing?.xs, alignItems: 'center', flexWrap: 'wrap' }}>
                    <label htmlFor="exp-receipt" style={{
                        display: 'inline-flex', alignItems: 'center', gap: 7, cursor: 'pointer',
                        padding: '9px 15px', borderRadius: tokens.border?.radius?.button,
                        border: `1px dashed ${tokens.color?.['border-700']}`,
                        color: tokens.color?.['muted-500'], fontSize: tokens.typography?.button?.fontSize,
                    }}>
                        <Paperclip size={15} /> {receipt ? receipt.name : 'Attach receipt'}
                    </label>
                    <input id="exp-receipt" type="file" style={{ display: 'none' }}
                        onChange={(e) => setReceipt(e.target.files?.[0] || null)} />
                    <Btn type="button" tone="ghost" icon={ScanLine} loading={isScanning} disabled={!receipt || isSubmitting} onClick={handleScan}>
                        Scan receipt
                    </Btn>
                </div>

                <form onSubmit={handleSubmit} style={{ marginTop: tokens.spacing?.md }}>
                    <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: tokens.spacing?.sm }}>
                        <div style={ui.field}>
                            <label style={ui.label} htmlFor="exp-amount">Amount</label>
                            <input id="exp-amount" type="number" min="0.01" step="0.01" placeholder="0.00"
                                style={ui.input} value={form.amount} onChange={set('amount')} />
                        </div>
                        <div style={ui.field}>
                            <label style={ui.label} htmlFor="exp-currency">Currency</label>
                            <input id="exp-currency" style={ui.input} value={form.currency} onChange={set('currency')} maxLength={3} />
                        </div>
                    </div>
                    <div style={ui.field}>
                        <label style={ui.label} htmlFor="exp-category">Category</label>
                        <select id="exp-category" style={ui.input} value={form.category} onChange={set('category')}>
                            {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
                        </select>
                    </div>
                    <div style={ui.field}>
                        <label style={ui.label} htmlFor="exp-date">Date of spend</label>
                        <input id="exp-date" type="date" style={ui.input} value={form.date} onChange={set('date')} />
                    </div>
                    <div style={ui.field}>
                        <label style={ui.label} htmlFor="exp-desc">What was it for</label>
                        <textarea id="exp-desc" style={{ ...ui.input, minHeight: 74, resize: 'vertical' }}
                            placeholder="For example taxi from the airport to the client site"
                            value={form.description} onChange={set('description')} />
                    </div>
                    <Btn type="submit" tone="success" icon={Send} loading={isSubmitting} disabled={!valid || isScanning}>
                        Submit expense
                    </Btn>
                </form>
            </div>

            <div style={{ ...ui.panel, gridColumn: 'span 7' }}>
                <h3 style={ui.h3}>Filed in this session</h3>
                <p style={ui.hint}>
                    <Info size={12} style={{ verticalAlign: '-2px', marginRight: 4 }} />
                    There is no expense history endpoint yet, so this list only shows claims you filed since opening this page. Each row is the record the server returned.
                </p>
                {filed.length === 0 ? (
                    <EmptyState icon={ReceiptText} title="Nothing filed yet"
                        action="Submit a claim on the left and the saved record, including its reference number, appears here." />
                ) : (
                    <div className="emp-scroll" style={{ ...ui.scroller('300px'), marginTop: tokens.spacing?.sm }}>
                        {filed.map((e) => (
                            <div key={e.expense_id} style={ui.listRow}>
                                <div style={ui.rowMain}>
                                    <span style={ui.rowTitle}>{money(e.amount, e.currency)}, {e.category}</span>
                                    <span style={ui.rowMeta}>
                                        {e.description || 'No description given'}, reference {e.expense_id}, filed {fmtDate(e.submitted_at)}
                                        {e.receipt ? `, receipt ${e.receipt}` : ', no receipt attached'}
                                    </span>
                                </div>
                                <StatusPill status={e.status} />
                            </div>
                        ))}
                    </div>
                )}
            </div>

            <div style={{ gridColumn: 'span 4' }}>
                <DataCard title="Filed this session" value={<CountUp value={filed.length} />} unit="claims"
                    icon={<ReceiptText size={15} />} color={tokens.color?.['accent-primary']} />
            </div>
            <div style={{ gridColumn: 'span 8' }}>
                <DataCard title={`Value filed this session, ${money(total)}`} isChart minHeight="260px">
                    <PieChartWidget data={byCategory} minHeight="220px" label="Split of what you filed, by category." />
                </DataCard>
            </div>
        </div>
    );
});

ExpenseModule.displayName = 'ExpenseModule';
export default ExpenseModule;
