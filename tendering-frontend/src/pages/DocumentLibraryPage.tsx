import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Library, Upload, Search, AlertCircle, CheckCircle2, Clock,
  FileText, Download, Calendar, Plus, FolderOpen, X, CloudUpload, Trash2, Cpu, Loader2,
} from 'lucide-react';
import { getLibraryDocuments, addLibraryDocument, deleteLibraryDocument, replaceLibraryDocument, extractLibraryDocument, getLibraryDocumentExtraction, verifyLibraryDocument } from '../api/tenders';
import { supabase } from '../lib/supabase';
import { DocCategoryBadge, VerificationBadge } from '../components/Badge';
import type { LibraryDocument, DocCategory, VerificationStatus } from '../types';
import toast from 'react-hot-toast';

const CATEGORY_FILTERS: { label: string; value: DocCategory | 'all' }[] = [
  { label: 'All', value: 'all' },
  { label: 'Registration', value: 'registration' },
  { label: 'Certification', value: 'certification' },
  { label: 'Financial', value: 'financial' },
  { label: 'Technical', value: 'technical' },
  { label: 'Personnel', value: 'personnel' },
];

function daysUntilExpiry(dateStr: string): number {
  return Math.ceil((new Date(dateStr).getTime() - Date.now()) / (1000 * 60 * 60 * 24));
}

function ExpiryTag({ expiry_date }: { expiry_date?: string }) {
  if (!expiry_date) return <span className="text-xs text-text-mute">No expiry</span>;

  const days = daysUntilExpiry(expiry_date);
  const expired = days < 0;
  const critical = !expired && days <= 90;
  const warning = !expired && days <= 180 && !critical;

  if (expired) return (
    <div className="flex items-center gap-1.5 text-xs text-red">
      <AlertCircle size={12} />
      Expired {new Date(expiry_date).toLocaleDateString('en-GB', { month: 'short', year: 'numeric' })}
    </div>
  );
  if (critical) return (
    <div className="flex items-center gap-1.5 text-xs text-amber font-medium">
      <Clock size={12} />
      Expires in {days} days
    </div>
  );
  if (warning) return (
    <div className="flex items-center gap-1.5 text-xs text-text-mute">
      <Calendar size={12} />
      Expires {new Date(expiry_date).toLocaleDateString('en-GB', { month: 'short', year: 'numeric' })}
    </div>
  );
  return (
    <div className="flex items-center gap-1.5 text-xs text-text-mute">
      <Calendar size={12} />
      Valid until {new Date(expiry_date).toLocaleDateString('en-GB', { month: 'short', year: 'numeric' })}
    </div>
  );
}

// ─── File viewer modal ────────────────────────────────────────────────────────

function FileViewerModal({
  doc,
  onClose,
  onVerified,
}: {
  doc: LibraryDocument;
  onClose: () => void;
  onVerified: () => void;
}) {
  const isPdf = (doc.filename ?? '').toLowerCase().endsWith('.pdf') || (doc.url ?? '').includes('.pdf');
  const isDone = doc.extraction_status === 'done';
  const [activeTab, setActiveTab] = useState<'preview' | 'extracted'>('preview');
  const [loadingText, setLoadingText] = useState(false);
  const [extractedText, setExtractedText] = useState<string | null>(null);
  const [verifying, setVerifying] = useState(false);
  const isVerified = doc.verification_status === 'verified';

  useEffect(() => {
    if (activeTab !== 'extracted' || extractedText !== null || !isDone) return;
    setLoadingText(true);
    getLibraryDocumentExtraction(doc.doc_id)
      .then((result) => setExtractedText(result.text || '(No text extracted)'))
      .catch(() => setExtractedText('(Failed to load extracted text)'))
      .finally(() => setLoadingText(false));
  }, [activeTab, extractedText, isDone, doc.doc_id]);

  async function handleVerify() {
    setVerifying(true);
    try {
      await verifyLibraryDocument(doc.doc_id);
      onVerified();
      toast.success('Document marked as verified');
    } catch {
      toast.error('Failed to verify document');
    } finally {
      setVerifying(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center px-4 py-6">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-panel rounded-xl border border-border shadow-2xl w-full max-w-4xl flex flex-col" style={{ height: '85vh' }}>
        {/* Header */}
        <div className="flex items-center gap-3 px-5 py-4 border-b border-border flex-shrink-0">
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-text truncate">{doc.title}</p>
            <p className="text-xs text-text-mute mt-0.5 truncate">{doc.filename}</p>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <DocCategoryBadge category={doc.category} />
            {!isVerified && (
              <button
                onClick={handleVerify}
                disabled={verifying}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-green/10 hover:bg-green/20 text-green border border-green/30 rounded-lg transition-colors disabled:opacity-50"
              >
                {verifying ? <Loader2 size={11} className="animate-spin" /> : <CheckCircle2 size={11} />}
                Mark as Verified
              </button>
            )}
            {isVerified && (
              <span className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-green">
                <CheckCircle2 size={11} /> Verified
              </span>
            )}
            <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-panel-2 text-text-mute hover:text-text transition-colors">
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-border flex-shrink-0">
          <button
            onClick={() => setActiveTab('preview')}
            className={`px-5 py-2.5 text-xs font-medium transition-colors border-b-2 -mb-px ${activeTab === 'preview' ? 'border-teal text-teal' : 'border-transparent text-text-mute hover:text-text'}`}
          >
            Preview
          </button>
          <button
            onClick={() => setActiveTab('extracted')}
            className={`px-5 py-2.5 text-xs font-medium transition-colors border-b-2 -mb-px ${activeTab === 'extracted' ? 'border-teal text-teal' : 'border-transparent text-text-mute hover:text-text'}`}
          >
            Extracted Text
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-hidden">
          {activeTab === 'preview' ? (
            <div className="relative w-full h-full">
              {doc.url && isPdf && <iframe src={doc.url} className="w-full h-full rounded-b-xl" title={doc.title} />}
              {doc.url && !isPdf && (
                <div className="h-full flex flex-col items-center justify-center gap-3">
                  <FileText size={32} className="text-text-mute" />
                  <p className="text-sm text-text-mute">Preview not available for this file type.</p>
                </div>
              )}
              {!doc.url && (
                <div className="h-full flex items-center justify-center">
                  <p className="text-sm text-text-mute">No file URL available.</p>
                </div>
              )}
              {doc.url && (
                <div className="absolute bottom-3 right-3">
                  <a href={doc.url} target="_blank" rel="noopener noreferrer"
                    className="flex items-center gap-2 px-4 py-2 bg-navy hover:bg-navy-soft text-white text-xs font-medium rounded-lg shadow transition-colors">
                    <FileText size={12} /> Open in new tab
                  </a>
                </div>
              )}
            </div>
          ) : (
            <div className="h-full overflow-y-auto p-5 bg-canvas-deep rounded-b-xl">
              {!isDone ? (
                <div className="flex flex-col items-center justify-center gap-3 pt-16">
                  <p className="text-xs text-text-mute">
                    {doc.extraction_status === 'failed' ? 'Extraction failed — retry from the library.' : 'Extract this document first to see its text.'}
                  </p>
                </div>
              ) : loadingText ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 size={16} className="animate-spin text-teal" />
                </div>
              ) : (
                <pre className="text-xs text-text-mid font-mono whitespace-pre-wrap leading-relaxed">{extractedText}</pre>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Replace modal ────────────────────────────────────────────────────────────

function ReplaceModal({
  doc,
  onReplaced,
  onClose,
}: {
  doc: LibraryDocument;
  onReplaced: () => void;
  onClose: () => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) { toast.error('Select a replacement file'); return; }
    setSubmitting(true);
    try {
      const path = `general/${Date.now()}-${file.name}`;
      const { error: storageError } = await supabase.storage
        .from('library-documents')
        .upload(path, file, { contentType: file.type, upsert: false });
      if (storageError) throw storageError;
      const { data: { publicUrl } } = supabase.storage.from('library-documents').getPublicUrl(path);
      await replaceLibraryDocument(doc.doc_id, { url: publicUrl, filename: file.name });
      onReplaced();
      toast.success('Document replaced');
      onClose();
    } catch {
      toast.error('Replace failed');
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-panel rounded-xl border border-border shadow-2xl w-full max-w-sm">
        <div className="px-6 py-5 border-b border-border">
          <h2 className="text-base font-semibold text-text">Replace Document</h2>
          <p className="text-xs text-text-mute mt-0.5 truncate">{doc.title}</p>
        </div>
        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
          {file ? (
            <div className="flex items-center gap-3 px-3 py-2.5 bg-panel-2 rounded-lg border border-border">
              <FileText size={16} className="text-teal flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-text truncate">{file.name}</p>
                <p className="text-[11px] text-text-mute">{(file.size / 1_000_000).toFixed(1)} MB</p>
              </div>
              <button type="button" onClick={() => setFile(null)} className="text-text-mute hover:text-red"><X size={13} /></button>
            </div>
          ) : (
            <div
              onClick={() => inputRef.current?.click()}
              onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => { e.preventDefault(); setDragging(false); setFile(e.dataTransfer.files[0] ?? null); }}
              className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors ${dragging ? 'border-teal bg-teal/5' : 'border-border hover:border-teal/50'}`}
            >
              <CloudUpload size={24} className="text-text-mute mx-auto mb-2" />
              <p className="text-sm text-text-mid">Drop new file or <span className="text-teal font-medium">browse</span></p>
              <input ref={inputRef} type="file" accept=".pdf,.docx,.xlsx" className="hidden" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
            </div>
          )}
          <div className="flex items-center justify-end gap-3 pt-1">
            <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-text-mid hover:text-text transition-colors">Cancel</button>
            <button
              type="submit"
              disabled={!file || submitting}
              className="px-5 py-2 bg-navy hover:bg-navy-soft disabled:opacity-50 text-white text-sm font-semibold rounded-lg transition-colors flex items-center gap-2"
            >
              {submitting ? <><div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />Uploading…</> : 'Replace'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ─── Document card ────────────────────────────────────────────────────────────

function ExtractionStatusBadge({ status }: { status?: string | null }) {
  if (!status || status === 'uploaded') return (
    <span className="flex items-center gap-1 text-[11px] text-text-mute">
      <Cpu size={11} /> Not indexed
    </span>
  );
  if (status === 'queued' || status === 'processing') return (
    <span className="flex items-center gap-1 text-[11px] text-amber font-medium">
      <div className="w-2.5 h-2.5 border border-amber/60 border-t-amber rounded-full animate-spin" />
      Indexing…
    </span>
  );
  if (status === 'done') return (
    <span className="flex items-center gap-1 text-[11px] text-green font-medium">
      <CheckCircle2 size={11} /> Indexed
    </span>
  );
  if (status === 'failed') return (
    <span className="flex items-center gap-1 text-[11px] text-red font-medium">
      <AlertCircle size={11} /> Index failed
    </span>
  );
  return null;
}

function DocCard({
  doc,
  onDeleted,
  onReplaced,
  onExtracted,
  onVerified,
}: {
  doc: LibraryDocument;
  onDeleted: () => void;
  onReplaced: () => void;
  onExtracted: () => void;
  onVerified: () => void;
}) {
  const [showReplace, setShowReplace] = useState(false);
  const [showViewer, setShowViewer] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const dateExpired = !!doc.expiry_date && new Date(doc.expiry_date) < new Date();
  const expired = doc.verification_status === 'expired' || dateExpired;
  const pending = !expired && doc.verification_status === 'pending';
  const canExtract = !doc.extraction_status || doc.extraction_status === 'uploaded' || doc.extraction_status === 'failed';
  const isIndexing = doc.extraction_status === 'queued' || doc.extraction_status === 'processing';

  async function handleDelete() {
    if (!confirm(`Delete "${doc.title}"? This cannot be undone.`)) return;
    setDeleting(true);
    try {
      await deleteLibraryDocument(doc.doc_id);
      onDeleted();
      toast.success('Document deleted');
    } catch {
      toast.error('Delete failed');
      setDeleting(false);
    }
  }

  async function handleExtract() {
    setExtracting(true);
    try {
      await extractLibraryDocument(doc.doc_id);
      toast.success('Extraction queued — document will be indexed shortly');
      onExtracted();
    } catch {
      toast.error('Could not start extraction');
      setExtracting(false);
    }
  }

  return (
    <>
      <div className={`bg-panel border rounded-xl p-5 flex flex-col transition-all hover:shadow-sm group cursor-pointer ${
        expired ? 'border-red/30 hover:border-red/50' :
        pending ? 'border-amber/30 hover:border-amber/50' :
        'border-border hover:border-teal/40'
      }`} onClick={() => setShowViewer(true)}>
        {/* Header */}
        <div className="flex items-start gap-3 mb-3">
          <div className={`w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 ${
            expired ? 'bg-red-bg' : pending ? 'bg-amber-bg' : 'bg-green-bg'
          }`}>
            <FileText size={16} className={expired ? 'text-red' : pending ? 'text-amber' : 'text-green'} />
          </div>
          <div className="min-w-0 flex-1">
            <h3 className="text-sm font-semibold text-text leading-snug line-clamp-2 group-hover:text-teal transition-colors">
              {doc.title}
            </h3>
            <p className="text-[11px] text-text-mute mt-0.5 truncate">{doc.filename}</p>
          </div>
          <button
            onClick={(e) => { e.stopPropagation(); handleDelete(); }}
            disabled={deleting}
            className="opacity-0 group-hover:opacity-100 p-1.5 rounded-lg text-text-mute hover:text-red hover:bg-red-bg transition-all"
            title="Delete"
          >
            {deleting ? <div className="w-3.5 h-3.5 border-2 border-red/30 border-t-red rounded-full animate-spin" /> : <Trash2 size={13} />}
          </button>
        </div>

        {/* Badges */}
        <div className="flex items-center gap-2 mb-3 flex-wrap">
          <DocCategoryBadge category={doc.category} />
          <VerificationBadge status={doc.verification_status} />
        </div>

        {/* Expiry */}
        <div className="mb-3">
          <ExpiryTag expiry_date={doc.expiry_date} />
        </div>

        {/* Used in tenders */}
        {doc.used_in_tenders !== undefined && doc.used_in_tenders > 0 && (
          <div className="flex items-center gap-1.5 text-xs text-text-mute mb-3">
            <FolderOpen size={12} />
            Used in {doc.used_in_tenders} tender{doc.used_in_tenders !== 1 ? 's' : ''}
          </div>
        )}

        {/* Tags */}
        {(doc.tags ?? []).length > 0 && (
          <div className="flex flex-wrap gap-1 mb-4">
            {(doc.tags ?? []).slice(0, 3).map((tag) => (
              <span key={tag} className="px-1.5 py-0.5 bg-panel-3 text-text-mute text-[11px] rounded">{tag}</span>
            ))}
            {(doc.tags ?? []).length > 3 && (
              <span className="px-1.5 py-0.5 bg-panel-3 text-text-mute text-[11px] rounded">+{(doc.tags ?? []).length - 3}</span>
            )}
          </div>
        )}

        {/* Extraction status */}
        <div className="mb-3">
          <ExtractionStatusBadge status={doc.extraction_status} />
        </div>

        {/* Actions */}
        <div className="flex gap-2 mt-auto flex-wrap" onClick={(e) => e.stopPropagation()}>
          {doc.url ? (
            <a
              href={doc.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex-1 flex items-center justify-center gap-1.5 py-2 text-xs font-medium text-text-mid border border-border rounded-lg hover:border-teal hover:text-teal transition-colors"
            >
              <Download size={12} />
              Download
            </a>
          ) : (
            <button disabled className="flex-1 flex items-center justify-center gap-1.5 py-2 text-xs font-medium text-text-mute border border-border rounded-lg opacity-40 cursor-not-allowed">
              <Download size={12} />
              Download
            </button>
          )}
          {(expired || pending) && (
            <button
              onClick={() => setShowReplace(true)}
              className="flex-1 flex items-center justify-center gap-1.5 py-2 text-xs font-medium text-teal border border-teal rounded-lg hover:bg-teal hover:text-white transition-colors"
            >
              <Upload size={12} />
              Replace
            </button>
          )}
          {(canExtract || isIndexing) && (
            <button
              onClick={handleExtract}
              disabled={extracting || isIndexing}
              className="flex-1 flex items-center justify-center gap-1.5 py-2 text-xs font-medium border rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed border-navy text-navy hover:bg-navy hover:text-white"
            >
              {extracting || isIndexing
                ? <><div className="w-2.5 h-2.5 border border-current/40 border-t-current rounded-full animate-spin" />Indexing…</>
                : <><Cpu size={12} />{doc.extraction_status === 'failed' ? 'Retry' : 'Extract'}</>
              }
            </button>
          )}
        </div>
      </div>

      {showViewer && <FileViewerModal doc={doc} onClose={() => setShowViewer(false)} onVerified={() => { onVerified(); setShowViewer(false); }} />}
      {showReplace && (
        <ReplaceModal
          doc={doc}
          onReplaced={() => { onReplaced(); setShowReplace(false); }}
          onClose={() => setShowReplace(false)}
        />
      )}
    </>
  );
}

// ─── Upload modal ─────────────────────────────────────────────────────────────

function UploadModal({ onAdded, onClose }: { onAdded: () => void; onClose: () => void }) {
  const [form, setForm] = useState({ title: '', category: 'certification' as DocCategory, expiry_date: '' });
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  function pickFile(picked: File | null) {
    if (!picked) return;
    setFile(picked);
    if (!form.title) setForm((previous) => ({ ...previous, title: picked.name.replace(/\.[^.]+$/, '') }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) { toast.error('Please select a file'); return; }
    setSubmitting(true);
    try {
      const path = `general/${Date.now()}-${file.name}`;
      const { error: storageError } = await supabase.storage
        .from('library-documents')
        .upload(path, file, { contentType: file.type, upsert: false });
      if (storageError) throw storageError;
      const { data: { publicUrl } } = supabase.storage.from('library-documents').getPublicUrl(path);
      await addLibraryDocument({
        title: form.title,
        filename: file.name,
        category: form.category,
        file_type: file.name.split('.').pop()?.toLowerCase() ?? '',
        expiry_date: form.expiry_date || undefined,
        url: publicUrl,
        storage_path: path,
      });
      onAdded();
      toast.success('Document added to library');
      onClose();
    } catch {
      toast.error('Upload failed — check that the library-documents storage bucket exists');
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-panel rounded-xl border border-border shadow-2xl w-full max-w-md">
        <div className="px-6 py-5 border-b border-border">
          <h2 className="text-base font-semibold text-text">Add to Document Library</h2>
          <p className="text-xs text-text-mute mt-0.5">
            Documents here are checked automatically against all new requirements
          </p>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
          {/* Drop zone / file picker */}
          {file ? (
            <div className="flex items-center gap-3 px-3 py-2.5 bg-panel-2 rounded-lg border border-border">
              <FileText size={16} className="text-teal flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-text truncate">{file.name}</p>
                <p className="text-[11px] text-text-mute">{(file.size / 1_000_000).toFixed(1)} MB</p>
              </div>
              <button type="button" onClick={() => setFile(null)} className="text-text-mute hover:text-red">
                <X size={13} />
              </button>
            </div>
          ) : (
            <div
              onClick={() => inputRef.current?.click()}
              onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => { e.preventDefault(); setDragging(false); pickFile(e.dataTransfer.files[0] ?? null); }}
              className={`border-2 border-dashed rounded-xl p-6 text-center transition-colors cursor-pointer ${
                dragging ? 'border-teal bg-teal/5' : 'border-border hover:border-teal/50'
              }`}
            >
              <CloudUpload size={24} className="text-text-mute mx-auto mb-2" />
              <p className="text-sm text-text-mid">Drop file here or <span className="text-teal font-medium">browse</span></p>
              <p className="text-xs text-text-mute mt-1">PDF, DOCX, XLSX — up to 50MB</p>
              <input ref={inputRef} type="file" accept=".pdf,.docx,.xlsx" className="hidden" onChange={(e) => pickFile(e.target.files?.[0] ?? null)} />
            </div>
          )}

          {/* Title */}
          <div>
            <label className="block text-xs font-semibold text-text-mute uppercase tracking-wide mb-1.5">
              Document Title <span className="text-red">*</span>
            </label>
            <input
              value={form.title}
              onChange={(e) => setForm((previous) => ({ ...previous, title: e.target.value }))}
              placeholder="e.g. ISO 9001:2015 Quality Certificate"
              required
              className="w-full px-3 py-2 text-sm bg-canvas border border-border rounded-lg outline-none focus:border-teal focus:ring-2 focus:ring-teal/15 transition-colors"
            />
          </div>

          {/* Category + Expiry */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-text-mute uppercase tracking-wide mb-1.5">Category</label>
              <select
                value={form.category}
                onChange={(e) => setForm((previous) => ({ ...previous, category: e.target.value as DocCategory }))}
                className="w-full px-3 py-2 text-sm bg-canvas border border-border rounded-lg outline-none focus:border-teal transition-colors"
              >
                <option value="registration">Registration</option>
                <option value="certification">Certification</option>
                <option value="financial">Financial</option>
                <option value="technical">Technical</option>
                <option value="personnel">Personnel</option>
                <option value="other">Other</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-text-mute uppercase tracking-wide mb-1.5">Expiry Date</label>
              <input
                type="date"
                value={form.expiry_date}
                onChange={(e) => setForm((previous) => ({ ...previous, expiry_date: e.target.value }))}
                className="w-full px-3 py-2 text-sm bg-canvas border border-border rounded-lg outline-none focus:border-teal transition-colors"
              />
            </div>
          </div>

          <div className="pt-2 bg-panel-2 -mx-6 px-6 py-4 -mb-5 rounded-b-xl border-t border-border flex items-center justify-end gap-3">
            <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-text-mid hover:text-text transition-colors">Cancel</button>
            <button
              type="submit"
              disabled={!form.title.trim() || !file || submitting}
              className="px-5 py-2 bg-navy hover:bg-navy-soft disabled:opacity-50 text-white text-sm font-semibold rounded-lg transition-colors flex items-center gap-2"
            >
              {submitting
                ? <><div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />Uploading…</>
                : 'Add Document'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export function DocumentLibraryPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<DocCategory | 'all'>('all');
  const [statusFilter, setStatusFilter] = useState<VerificationStatus | 'all'>('all');
  const [showUpload, setShowUpload] = useState(false);

  const { data: docs = [], isLoading: loading } = useQuery({
    queryKey: ['library-docs'],
    queryFn: getLibraryDocuments,
    refetchInterval: (query) => {
      const data = query.state.data ?? [];
      const hasInProgress = data.some(
        (doc) => doc.extraction_status === 'queued' || doc.extraction_status === 'processing',
      );
      return hasInProgress ? 4000 : false;
    },
  });

  const isExpired = (document: (typeof docs)[0]) =>
    document.verification_status === 'expired' ||
    (!!document.expiry_date && new Date(document.expiry_date) < new Date());

  const filtered = docs.filter((document) => {
    const searchQuery = search.toLowerCase();
    const matchSearch =
      document.title.toLowerCase().includes(searchQuery) ||
      (document.filename ?? '').toLowerCase().includes(searchQuery) ||
      (document.tags ?? []).some((tag) => tag.toLowerCase().includes(searchQuery));
    const matchCat = categoryFilter === 'all' || document.category === categoryFilter;
    const effectiveStatus = isExpired(document) ? 'expired' : document.verification_status;
    const matchStatus = statusFilter === 'all' || effectiveStatus === statusFilter;
    return matchSearch && matchCat && matchStatus;
  });

  const expired = docs.filter(isExpired).length;
  const expiringSoon = docs.filter((document) => {
    if (!document.expiry_date || isExpired(document)) return false;
    const days = daysUntilExpiry(document.expiry_date);
    return days >= 0 && days <= 90;
  }).length;
  const verified = docs.filter((document) => document.verification_status === 'verified').length;

  const statusButtons: { label: string; value: VerificationStatus | 'all' }[] = [
    { label: 'All', value: 'all' },
    { label: 'Verified', value: 'verified' },
    { label: 'Pending', value: 'pending' as VerificationStatus },
    { label: 'Expired', value: 'expired' },
  ];

  return (
    <div className="pt-[6.5rem] px-6 pb-12 max-w-6xl mx-auto">

      {/* Header */}
      <div className="mb-6 flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Library size={18} className="text-teal" />
            <h1 className="text-xl font-bold text-text">Document Library</h1>
          </div>
          <p className="text-sm text-text-mute max-w-lg">
            Your company's documents — uploaded once, checked automatically against every new set of requirements.
          </p>
        </div>
        <button
          onClick={() => setShowUpload(true)}
          className="flex items-center gap-2 px-4 py-2.5 bg-navy hover:bg-navy-soft text-white text-sm font-semibold rounded-lg transition-colors self-start"
        >
          <Plus size={15} />
          Add Document
        </button>
      </div>

      {/* Alert banners */}
      {!loading && (expired > 0 || expiringSoon > 0) && (
        <div className="space-y-2 mb-6">
          {expired > 0 && (
            <div className="flex items-center gap-3 px-4 py-3 bg-red-bg border border-red/20 rounded-xl text-sm">
              <AlertCircle size={15} className="text-red flex-shrink-0" />
              <span className="text-red">
                <strong>{expired}</strong> document{expired !== 1 ? 's have' : ' has'} expired
                — renew before the AI can use {expired !== 1 ? 'them' : 'it'} for compliance checks.
              </span>
            </div>
          )}
          {expiringSoon > 0 && (
            <div className="flex items-center gap-3 px-4 py-3 bg-amber-bg border border-amber/30 rounded-xl text-sm">
              <Clock size={15} className="text-amber flex-shrink-0" />
              <span className="text-amber">
                <strong>{expiringSoon}</strong> document{expiringSoon !== 1 ? 's expire' : ' expires'} within 90 days
                — schedule renewal now.
              </span>
            </div>
          )}
        </div>
      )}

      {/* Stats strip */}
      {!loading && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
          {[
            { label: 'Total Documents', value: docs.length, cls: 'text-text', icon: Library },
            { label: 'Verified', value: verified, cls: 'text-green', icon: CheckCircle2 },
            { label: 'Expiring Soon', value: expiringSoon, cls: expiringSoon > 0 ? 'text-amber' : 'text-text-mute', icon: Clock },
            { label: 'Expired', value: expired, cls: expired > 0 ? 'text-red' : 'text-text-mute', icon: AlertCircle },
          ].map(({ label, value, cls, icon: Icon }) => (
            <div key={label} className="bg-panel border border-border rounded-xl p-4 flex items-center gap-3">
              <Icon size={18} className={cls} />
              <div>
                <p className={`text-xl font-bold ${cls}`}>{value}</p>
                <p className="text-xs text-text-mute">{label}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3 mb-6">
        <div className="relative max-w-xs w-full">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-mute" />
          <input
            type="text"
            placeholder="Search documents…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 text-sm bg-panel border border-border rounded-lg outline-none focus:border-teal transition-colors"
          />
        </div>

        <div className="flex gap-1.5 flex-wrap">
          {CATEGORY_FILTERS.map(({ label, value }) => (
            <button
              key={value}
              onClick={() => setCategoryFilter(value as DocCategory | 'all')}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                categoryFilter === value ? 'bg-navy text-white' : 'bg-panel border border-border text-text-mid hover:bg-panel-2'
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="flex gap-1.5 flex-wrap sm:ml-auto">
          {statusButtons.map(({ label, value }) => (
            <button
              key={value}
              onClick={() => setStatusFilter(value as VerificationStatus | 'all')}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                statusFilter === value ? 'bg-navy text-white' : 'bg-panel border border-border text-text-mid hover:bg-panel-2'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Grid */}
      {loading ? (
        <div className="text-center text-sm text-text-mute py-16">Loading documents...</div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16">
          <Library size={28} className="text-text-mute mx-auto mb-3" />
          <p className="text-sm text-text-mute mb-2">No documents match your filters.</p>
          <button onClick={() => setShowUpload(true)} className="text-sm text-teal hover:underline font-medium">
            Upload your first document →
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((document) => (
            <DocCard
              key={document.doc_id}
              doc={document}
              onDeleted={() => queryClient.invalidateQueries({ queryKey: ['library-docs'] })}
              onReplaced={() => queryClient.invalidateQueries({ queryKey: ['library-docs'] })}
              onExtracted={() => queryClient.invalidateQueries({ queryKey: ['library-docs'] })}
              onVerified={() => queryClient.invalidateQueries({ queryKey: ['library-docs'] })}
            />
          ))}
        </div>
      )}

      {showUpload && (
        <UploadModal
          onAdded={() => queryClient.invalidateQueries({ queryKey: ['library-docs'] })}
          onClose={() => setShowUpload(false)}
        />
      )}
    </div>
  );
}
