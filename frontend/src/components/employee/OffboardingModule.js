// Employee portal: Offboarding knowledge transfer.
// Real endpoint: POST /api/hr/offboarding/knowledge. The backend exposes no way
// for an employee to read entries back and file upload is restricted to HR IT
// administrators, so this page lists only what was handed over in this session
// and says so plainly.
import React, { memo, useCallback, useState } from 'react';
import { theme as tokens } from '../../theme';
import { useToast } from '../../hooks/use-toast';
import { submitOffboardingKnowledge } from '../../config/api';
import DataCard from '../DataCard';
import { CountUp } from '../live/LivePrimitives';
import { ui, Btn, EmptyState, StatusPill, EmployeeStyles } from './shared';
import { Send, BookOpenCheck, UserRoundCheck, Info, Archive } from 'lucide-react';

const BLANK = { area: '', notes: '', successor: '' };

const OffboardingModule = memo(() => {
    const { toast } = useToast();
    const [form, setForm] = useState(BLANK);
    const [isSubmitting, setIsSubmitting] = useState(false);
    // Entries handed over in this session, straight from the API responses.
    const [handedOver, setHandedOver] = useState([]);

    const set = (key) => (e) => setForm((prev) => ({ ...prev, [key]: e.target.value }));

    const valid = form.area.trim() !== '' && form.notes.trim().length >= 10;

    const handleSubmit = useCallback(async (e) => {
        e.preventDefault();
        if (!valid) {
            toast({
                title: 'Check the form first',
                description: 'Name what you own and write at least a couple of sentences of handover notes.',
                variant: 'destructive',
            });
            return;
        }
        setIsSubmitting(true);
        const area = form.area.trim();
        const successor = form.successor.trim();
        try {
            const res = await submitOffboardingKnowledge({
                title: area,
                content: form.notes.trim() + (successor ? `\n\nSuggested successor: ${successor}` : ''),
            });
            const entryId = res.data?.entry_id;
            setHandedOver((prev) => [{
                entry_id: entryId,
                area,
                successor,
                status: res.data?.status || 'SUBMITTED',
                at: new Date(),
            }, ...prev]);
            toast({
                title: 'Handover recorded',
                description: `"${area}" is now in the knowledge base${entryId ? `, reference ${entryId}` : ''}. HR and your successor can read it.`,
                variant: 'success',
            });
            setForm(BLANK);
        } catch (err) {
            toast({ title: 'Could not record the handover', description: err.response?.data?.detail || err.message, variant: 'destructive' });
        } finally {
            setIsSubmitting(false);
        }
    }, [valid, form, toast]);

    return (
        <div style={ui.grid} className="portal-grid">
            <EmployeeStyles />

            <div style={{ gridColumn: 'span 4' }}>
                <DataCard title="Handed over in this session" value={<CountUp value={handedOver.length} />} unit="entries"
                    icon={<BookOpenCheck size={15} />} color={tokens.color?.['accent-primary']}
                    subtitle={handedOver.length ? 'Each entry is saved in the knowledge base' : 'Nothing recorded yet in this session'} />
            </div>
            <div style={{ gridColumn: 'span 8' }}>
                <DataCard title="Why this matters"
                    value="Knowledge transfer"
                    icon={<Archive size={15} />} color={tokens.color?.['accent-secondary']}
                    subtitle="What you write here is what your team keeps after you leave. One entry per area you own works best: a system, a process, a relationship." />
            </div>

            <div style={{ ...ui.panel, gridColumn: 'span 5' }}>
                <h3 style={ui.h3}>Hand something over</h3>
                <p style={ui.hint}>One entry per thing you own. Say what it is, how it works, and who should take it on.</p>

                <form onSubmit={handleSubmit} style={{ marginTop: tokens.spacing?.md }}>
                    <div style={ui.field}>
                        <label style={ui.label} htmlFor="off-area">What you own</label>
                        <input id="off-area" style={ui.input}
                            placeholder="For example the monthly payroll reconciliation"
                            value={form.area} onChange={set('area')} />
                    </div>
                    <div style={ui.field}>
                        <label style={ui.label} htmlFor="off-notes">Handover notes</label>
                        <textarea id="off-notes" style={{ ...ui.input, minHeight: 140, resize: 'vertical' }}
                            placeholder="How it works, where things live, what goes wrong and how you fix it, who to talk to"
                            value={form.notes} onChange={set('notes')} />
                    </div>
                    <div style={ui.field}>
                        <label style={ui.label} htmlFor="off-successor">Who should take this on</label>
                        <input id="off-successor" style={ui.input}
                            placeholder="Name of a colleague, or leave blank if you are not sure"
                            value={form.successor} onChange={set('successor')} />
                    </div>

                    <Btn type="submit" tone="success" icon={Send} loading={isSubmitting} disabled={!valid}>
                        Record this handover
                    </Btn>
                </form>
            </div>

            <div style={{ ...ui.panel, gridColumn: 'span 7' }}>
                <h3 style={ui.h3}>Handed over in this session</h3>
                <p style={ui.hint}>
                    <Info size={12} style={{ verticalAlign: '-2px', marginRight: 4 }} />
                    Entries go straight into the offboarding knowledge base. There is no endpoint to read them back yet,
                    so this list only shows what you recorded since opening this page.
                </p>

                {handedOver.length === 0 ? (
                    <EmptyState icon={UserRoundCheck} title="Nothing handed over yet"
                        action="Record your first entry on the left. The saved record, including its reference number, appears here." />
                ) : (
                    <div className="emp-scroll" style={{ ...ui.scroller('360px'), marginTop: tokens.spacing?.sm }}>
                        {handedOver.map((h) => (
                            <div key={h.entry_id || h.area} style={ui.listRow}>
                                <div style={ui.rowMain}>
                                    <span style={ui.rowTitle}>{h.area}</span>
                                    <span style={ui.rowMeta}>
                                        {h.successor ? `Suggested successor ${h.successor}` : 'No successor suggested'}
                                        {h.entry_id ? `, reference ${h.entry_id}` : ''}
                                    </span>
                                </div>
                                <StatusPill status={h.status} />
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
});

OffboardingModule.displayName = 'OffboardingModule';
export default OffboardingModule;
