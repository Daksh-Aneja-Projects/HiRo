// Employee portal: Documents module.
// Real endpoints: GET /api/hr/doc/employee-documents, POST /api/hr/doc/ingestion/{id}/{type},
// DELETE /api/hr/doc/delete/{id}. The list and upload routes are gated to manager and
// HR roles on the backend, so a plain employee sees an honest permission notice.
import React, { memo, useCallback, useMemo, useState } from 'react';
import { theme as tokens } from '../../theme';
import { useApi } from '../../hooks/useApi';
import { useToast } from '../../hooks/use-toast';
import { useAuth } from '../../contexts/AuthContext';
import { getEmployeeDocuments, uploadEmployeeDocument, deleteEmployeeDocument, getPersonalInfo } from '../../config/api';
import DataCard from '../DataCard';
import PieChartWidget from '../charts/PieChartWidget';
import { CountUp } from '../live/LivePrimitives';
import { ui, Btn, Loading, EmptyState, ErrorNote, fmtDate, DOC_LIBRARY_ROLES, EmployeeStyles } from './shared';
import { FileText, Upload, Trash2, Paperclip, FolderOpen, Lock } from 'lucide-react';

const DOC_TYPES = ['contract', 'id_proof', 'certification', 'payroll', 'other'];
const readableType = (t) => String(t || 'other').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
const readableSize = (bytes) => {
    const n = Number(bytes) || 0;
    if (n < 1024) return `${n} bytes`;
    if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
    return `${(n / 1048576).toFixed(1)} MB`;
};

const DocumentsModule = memo(() => {
    const { toast } = useToast();
    const { userRole } = useAuth();

    // The library routes are gated to HR and manager roles on the backend. Rather than
    // firing a request we know will be refused, say so plainly and skip the call.
    const canUseLibrary = DOC_LIBRARY_ROLES.includes(String(userRole || '').toLowerCase());

    const { data: profile } = useApi(getPersonalInfo, [], true);
    const { data: rawDocs, isLoading, error, refetch } = useApi(getEmployeeDocuments, [], canUseLibrary);

    const [file, setFile] = useState(null);
    const [docType, setDocType] = useState(DOC_TYPES[0]);
    const [isUploading, setIsUploading] = useState(false);
    const [removing, setRemoving] = useState(null);

    const docs = useMemo(() => (Array.isArray(rawDocs) ? rawDocs : []), [rawDocs]);
    const employeeId = profile?.employee_uuid;

    const byType = useMemo(() => {
        const counts = docs.reduce((acc, d) => {
            const k = readableType(d.doc_type);
            acc[k] = (acc[k] || 0) + 1;
            return acc;
        }, {});
        return Object.entries(counts).map(([name, value]) => ({ name, value }));
    }, [docs]);

    const handleUpload = useCallback(async (e) => {
        e.preventDefault();
        if (!file) {
            toast({ title: 'Choose a file first', description: 'Attach a document before uploading.', variant: 'destructive' });
            return;
        }
        if (!employeeId) {
            toast({ title: 'Profile not loaded yet', description: 'Your employee record is still loading. Try again in a moment.', variant: 'destructive' });
            return;
        }
        setIsUploading(true);
        try {
            await uploadEmployeeDocument(employeeId, docType, file);
            toast({ title: 'Document uploaded', description: `${file.name} was filed under ${readableType(docType)}.`, variant: 'success' });
            setFile(null);
            refetch();
        } catch (err) {
            toast({ title: 'Upload failed', description: err.response?.data?.detail || err.message, variant: 'destructive' });
        } finally {
            setIsUploading(false);
        }
    }, [file, employeeId, docType, toast, refetch]);

    const handleDelete = useCallback(async (doc) => {
        if (!window.confirm(`Remove ${doc.filename}? This cannot be undone.`)) return;
        setRemoving(doc.document_id);
        try {
            await deleteEmployeeDocument(doc.document_id);
            toast({ title: 'Document removed', description: `${doc.filename} is no longer on file.`, variant: 'success' });
            refetch();
        } catch (err) {
            toast({ title: 'Could not remove that document', description: err.response?.data?.detail || err.message, variant: 'destructive' });
        } finally {
            setRemoving(null);
        }
    }, [toast, refetch]);

    if (!canUseLibrary) {
        return (
            <div style={ui.grid} className="portal-grid">
                <EmployeeStyles />
                <div style={{ ...ui.panel, gridColumn: 'span 12' }}>
                    <h3 style={ui.h3}>My documents</h3>
                    <EmptyState icon={Lock} title="The document library is managed by HR"
                        action="Contracts, identity proofs and certifications held against your record can only be listed and uploaded by HR or your manager. Raise a case with HR to add a document or ask for a copy of one." />
                </div>
            </div>
        );
    }

    return (
        <div style={ui.grid} className="portal-grid">
            <EmployeeStyles />

            <div style={{ gridColumn: 'span 4' }}>
                <DataCard title="Documents on file" value={<CountUp value={docs.length} />} unit="files"
                    icon={<FolderOpen size={15} />} color={tokens.color?.['accent-primary']}
                    subtitle={docs[0] ? `Most recent uploaded ${fmtDate(docs[0].uploaded_at)}` : 'Nothing uploaded yet'} />
            </div>
            <div style={{ gridColumn: 'span 8' }}>
                <DataCard title="Documents by type" isChart minHeight="220px">
                    <PieChartWidget data={byType} minHeight="180px" label="Every file currently held against employee records." />
                </DataCard>
            </div>

            <div style={{ ...ui.panel, gridColumn: 'span 5' }}>
                <h3 style={ui.h3}>Upload a document</h3>
                <p style={ui.hint}>Contracts, identity proofs and certifications are stored against your employee record.</p>
                <form onSubmit={handleUpload} style={{ marginTop: tokens.spacing?.md }}>
                    <div style={ui.field}>
                        <label style={ui.label} htmlFor="doc-type">Document type</label>
                        <select id="doc-type" style={ui.input} value={docType} onChange={(e) => setDocType(e.target.value)}>
                            {DOC_TYPES.map((t) => <option key={t} value={t}>{readableType(t)}</option>)}
                        </select>
                    </div>
                    <div style={ui.field}>
                        <label htmlFor="doc-file" style={{
                            display: 'inline-flex', alignItems: 'center', gap: 7, cursor: 'pointer',
                            padding: '9px 15px', borderRadius: tokens.border?.radius?.button,
                            border: `1px dashed ${tokens.color?.['border-700']}`,
                            color: tokens.color?.['muted-500'], fontSize: tokens.typography?.button?.fontSize,
                        }}>
                            <Paperclip size={15} /> {file ? file.name : 'Choose a file'}
                        </label>
                        <input id="doc-file" type="file" style={{ display: 'none' }}
                            onChange={(e) => setFile(e.target.files?.[0] || null)} />
                    </div>
                    <Btn type="submit" icon={Upload} loading={isUploading} disabled={!file}>Upload document</Btn>
                </form>
            </div>

            <div style={{ ...ui.panel, gridColumn: 'span 7' }}>
                <h3 style={ui.h3}>Document library</h3>
                {isLoading && <Loading label="Loading your documents" />}
                <ErrorNote error={error} context="the document library" />
                {!isLoading && !error && docs.length === 0 && (
                    <EmptyState icon={FileText} title="No documents on file"
                        action="Upload a contract, identity proof or certification on the left and it will be listed here." />
                )}
                {docs.length > 0 && (
                    <div className="emp-scroll" style={{ ...ui.scroller('300px'), marginTop: tokens.spacing?.sm }}>
                        {docs.map((d) => (
                            <div key={d.document_id} style={ui.listRow}>
                                <div style={ui.rowMain}>
                                    <span style={ui.rowTitle}>{d.filename}</span>
                                    <span style={ui.rowMeta}>
                                        {readableType(d.doc_type)}, {readableSize(d.size_bytes)}, uploaded {fmtDate(d.uploaded_at)}
                                    </span>
                                </div>
                                <Btn tone="ghost" icon={Trash2} loading={removing === d.document_id}
                                    disabled={!!removing} onClick={() => handleDelete(d)}>
                                    Remove
                                </Btn>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
});

DocumentsModule.displayName = 'DocumentsModule';
export default DocumentsModule;
