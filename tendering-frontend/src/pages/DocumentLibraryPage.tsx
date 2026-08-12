import { useEffect, useState } from 'react';
import {
  Library, Upload, Search, AlertCircle, CheckCircle2, Clock,
  FileText, Download, Calendar, Plus, FolderOpen,
} from 'lucide-react';
import { getLibraryDocuments } from '../api/tenders';
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

// ─── Document card ────────────────────────────────────────────────────────────

function DocCard({ doc }: { doc: LibraryDocument }) {
  const expired = doc.verification_status === 'expired';
  const pending = doc.verification_status === 'pending';

  return (
    <div className={`bg-panel border rounded-xl p-5 flex flex-col transition-all hover:shadow-sm group ${
      expired ? 'border-red/30 hover:border-red/50' :
      pending ? 'border-amber/30 hover:border-amber/50' :
      'border-border hover:border-teal/40'
    }`}>
      {/* Header */}
      <div className="flex items-start gap-3 mb-3">
        <div className={`w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 ${
          expired ? 'bg-red-bg' :
          pending ? 'bg-amber-bg' :
          'bg-green-bg'
        }`}>
          <FileText size={16} className={expired ? 'text-red' : pending ? 'text-amber' : 'text-green'} />
        </div>
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-semibold text-text leading-snug line-clamp-2 group-hover:text-teal transition-colors">
            {doc.title}
          </h3>
          <p className="text-[11px] text-text-mute mt-0.5 truncate">{doc.filename}</p>
        </div>
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
      {doc.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-4">
          {doc.tags.slice(0, 3).map((tag) => (
            <span key={tag} className="px-1.5 py-0.5 bg-panel-3 text-text-mute text-[11px] rounded">{tag}</span>
          ))}
          {doc.tags.length > 3 && (
            <span className="px-1.5 py-0.5 bg-panel-3 text-text-mute text-[11px] rounded">+{doc.tags.length - 3}</span>
          )}
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-2 mt-auto">
        <button className="flex-1 flex items-center justify-center gap-1.5 py-2 text-xs font-medium text-text-mid border border-border rounded-lg hover:border-teal hover:text-teal transition-colors">
          <Download size={12} />
          Download
        </button>
        {(expired || pending) && (
          <button
            onClick={() => toast('Upload new version coming soon')}
            className="flex-1 flex items-center justify-center gap-1.5 py-2 text-xs font-medium text-teal border border-teal rounded-lg hover:bg-teal hover:text-white transition-colors"
          >
            <Upload size={12} />
            Replace
          </button>
        )}
      </div>
    </div>
  );
}

// ─── Upload modal ─────────────────────────────────────────────────────────────

function UploadModal({ onClose }: { onClose: () => void }) {
  const [form, setForm] = useState({ title: '', category: 'certification' as DocCategory, expiry_date: '' });
  const [dragging, setDragging] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    await new Promise((r) => setTimeout(r, 800));
    toast.success('Document added to library');
    setSubmitting(false);
    onClose();
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
          {/* Drop zone */}
          <div
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => { e.preventDefault(); setDragging(false); }}
            className={`border-2 border-dashed rounded-xl p-6 text-center transition-colors cursor-pointer ${
              dragging ? 'border-teal bg-teal/5' : 'border-border hover:border-teal/50'
            }`}
          >
            <Upload size={24} className="text-text-mute mx-auto mb-2" />
            <p className="text-sm text-text-mid">
              Drop file here or <span className="text-teal font-medium">browse</span>
            </p>
            <p className="text-xs text-text-mute mt-1">PDF, DOCX, XLSX, JPG — up to 50MB</p>
          </div>

          {/* Title */}
          <div>
            <label className="block text-xs font-semibold text-text-mute uppercase tracking-wide mb-1.5">
              Document Title <span className="text-red">*</span>
            </label>
            <input
              value={form.title}
              onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
              placeholder="e.g. ISO 9001:2015 Quality Certificate"
              required
              className="w-full px-3 py-2 text-sm bg-canvas border border-border rounded-lg outline-none focus:border-teal focus:ring-2 focus:ring-teal/15 transition-colors"
            />
          </div>

          {/* Category + Expiry */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-text-mute uppercase tracking-wide mb-1.5">
                Category
              </label>
              <select
                value={form.category}
                onChange={(e) => setForm((f) => ({ ...f, category: e.target.value as DocCategory }))}
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
              <label className="block text-xs font-semibold text-text-mute uppercase tracking-wide mb-1.5">
                Expiry Date
              </label>
              <input
                type="date"
                value={form.expiry_date}
                onChange={(e) => setForm((f) => ({ ...f, expiry_date: e.target.value }))}
                className="w-full px-3 py-2 text-sm bg-canvas border border-border rounded-lg outline-none focus:border-teal transition-colors"
              />
            </div>
          </div>

          <div className="pt-2 bg-panel-2 -mx-6 px-6 py-4 -mb-5 rounded-b-xl border-t border-border flex items-center justify-end gap-3">
            <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-text-mid hover:text-text transition-colors">
              Cancel
            </button>
            <button
              type="submit"
              disabled={!form.title.trim() || submitting}
              className="px-5 py-2 bg-navy hover:bg-navy-soft disabled:opacity-50 text-white text-sm font-semibold rounded-lg transition-colors flex items-center gap-2"
            >
              {submitting
                ? <><div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />Adding…</>
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
  const [docs, setDocs] = useState<LibraryDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<DocCategory | 'all'>('all');
  const [statusFilter, setStatusFilter] = useState<VerificationStatus | 'all'>('all');
  const [showUpload, setShowUpload] = useState(false);

  useEffect(() => {
    getLibraryDocuments().then(setDocs).finally(() => setLoading(false));
  }, []);

  const filtered = docs.filter((d) => {
    const q = search.toLowerCase();
    const matchSearch =
      d.title.toLowerCase().includes(q) ||
      d.filename.toLowerCase().includes(q) ||
      d.tags.some((t) => t.toLowerCase().includes(q));
    const matchCat = categoryFilter === 'all' || d.category === categoryFilter;
    const matchStatus = statusFilter === 'all' || d.verification_status === statusFilter;
    return matchSearch && matchCat && matchStatus;
  });

  const expired = docs.filter((d) => d.verification_status === 'expired').length;
  const expiringSoon = docs.filter((d) => {
    if (!d.expiry_date || d.verification_status === 'expired') return false;
    const days = daysUntilExpiry(d.expiry_date);
    return days >= 0 && days <= 90;
  }).length;
  const verified = docs.filter((d) => d.verification_status === 'verified').length;

  const statusButtons: { label: string; value: VerificationStatus | 'all' }[] = [
    { label: 'All', value: 'all' },
    { label: 'Verified', value: 'verified' },
    { label: 'Pending', value: 'pending' },
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
          {filtered.map((doc) => (
            <DocCard key={doc.doc_id} doc={doc} />
          ))}
        </div>
      )}

      {showUpload && <UploadModal onClose={() => setShowUpload(false)} />}
    </div>
  );
}
