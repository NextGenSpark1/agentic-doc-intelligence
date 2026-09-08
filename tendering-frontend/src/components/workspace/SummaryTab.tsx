import { useState, useRef, useEffect, useCallback } from 'react';
import {
  FileText, Users, Upload, X, CheckCircle2, FileCode, Loader2,
  CloudUpload, UserPlus, Zap, Trash2, AlertCircle, Clock, Play,
} from 'lucide-react';
import type { WorkspaceStage, OrgMember, ExtractionStatus } from '../../types';
import toast from 'react-hot-toast';
import { StageBadge } from '../Badge';
import { daysUntil, formatCurrency, formatDate, readinessColour } from '../../lib/utils';
import {
  updateWorkspace, addWorkspaceDocument, fetchMyTeam,
  extractWorkspaceDocument, deleteWorkspaceDocument, analyseWorkspace,
  getWorkspace,
} from '../../api/tenders';
import { supabase } from '../../lib/supabase';
import type { TenderWorkspace, WorkspaceDocument } from '../../types';
import { useAuth } from '../../context/AuthContext';

// ─── Helpers ──────────────────────────────────────────────────────────────────

const ACCEPTED = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
];
const ACCEPTED_EXT = '.pdf,.docx,.xlsx';

function extLabel(name: string) {
  return name.split('.').pop()?.toUpperCase() ?? 'FILE';
}

function extColour(ext: string) {
  return ext === 'PDF' ? 'bg-red-bg text-red' :
    ext === 'XLSX' ? 'bg-green-bg text-green' :
    ext === 'DOCX' ? 'bg-teal/10 text-teal' : 'bg-panel-3 text-text-mute';
}

// ─── Extraction status badge ───────────────────────────────────────────────────

function ExtractionBadge({ status }: { status?: ExtractionStatus }) {
  if (!status || status === 'uploaded') {
    return <span className="text-[10px] text-text-mute font-medium">Not extracted</span>;
  }
  if (status === 'queued') {
    return <span className="flex items-center gap-1 text-[10px] text-amber font-medium"><Clock size={9} />Queued</span>;
  }
  if (status === 'processing') {
    return <span className="flex items-center gap-1 text-[10px] text-teal font-medium"><Loader2 size={9} className="animate-spin" />Extracting…</span>;
  }
  if (status === 'done') {
    return <span className="flex items-center gap-1 text-[10px] text-green font-medium"><CheckCircle2 size={9} />Extracted</span>;
  }
  return <span className="flex items-center gap-1 text-[10px] text-red font-medium"><AlertCircle size={9} />Failed</span>;
}

// ─── Upload Modal ─────────────────────────────────────────────────────────────

function UploadModal({
  workspaceId,
  onUploaded,
  onClose,
}: {
  workspaceId: string;
  onUploaded: (docs: WorkspaceDocument[]) => void;
  onClose: () => void;
}) {
  const [files, setFiles] = useState<File[]>([]);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  function addFiles(incoming: FileList | null) {
    if (!incoming) return;
    const valid = Array.from(incoming).filter(
      (file) => ACCEPTED.includes(file.type) || file.name.match(/\.(pdf|docx|xlsx)$/i),
    );
    setFiles((previous) => {
      const names = new Set(previous.map((file) => file.name));
      return [...previous, ...valid.filter((file) => !names.has(file.name))];
    });
  }

  async function handleUpload() {
    if (!files.length) return;
    setUploading(true);
    const uploaded: WorkspaceDocument[] = [];
    for (const file of files) {
      const storagePath = `${workspaceId}/${Date.now()}-${file.name}`;
      const { error: storageError } = await supabase.storage
        .from('tender-documents')
        .upload(storagePath, file, { contentType: file.type, upsert: false });
      if (storageError) { toast.error(`Failed to upload ${file.name}`); continue; }
      const { data: { publicUrl } } = supabase.storage.from('tender-documents').getPublicUrl(storagePath);
      try {
        const doc = await addWorkspaceDocument(workspaceId, {
          name: file.name,
          category: 'supporting',
          file_type: file.name.split('.').pop()?.toLowerCase() ?? '',
          size_bytes: file.size,
          url: publicUrl,
          storage_path: storagePath,
        });
        uploaded.push(doc);
      } catch { toast.error(`Failed to register ${file.name}`); }
    }
    setUploading(false);
    if (uploaded.length) {
      onUploaded(uploaded);
      toast.success(`${uploaded.length} document${uploaded.length > 1 ? 's' : ''} uploaded — click Extract to process`);
    }
    onClose();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={uploading ? undefined : onClose} />
      <div className="relative bg-panel rounded-xl border border-border shadow-2xl w-full max-w-lg">
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <div>
            <h2 className="text-sm font-semibold text-text">Upload Tender Documents</h2>
            <p className="text-xs text-text-mute mt-0.5">PDF, DOCX, XLSX — click Extract after upload to run ADE</p>
          </div>
          {!uploading && (
            <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-panel-2 text-text-mute hover:text-text transition-colors">
              <X size={15} />
            </button>
          )}
        </div>

        <div className="px-6 py-5 space-y-4">
          {uploading ? (
            <div className="py-8 text-center space-y-3">
              <Loader2 size={32} className="text-teal mx-auto animate-spin" />
              <p className="text-sm font-semibold text-text">Uploading to Supabase Storage…</p>
            </div>
          ) : (
            <>
              <div
                onClick={() => inputRef.current?.click()}
                onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
                onDragLeave={() => setDragging(false)}
                onDrop={(e) => { e.preventDefault(); setDragging(false); addFiles(e.dataTransfer.files); }}
                className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all ${
                  dragging ? 'border-teal bg-teal/5' : 'border-border hover:border-teal/50 hover:bg-panel-2'
                }`}
              >
                <CloudUpload size={28} className={`mx-auto mb-2 ${dragging ? 'text-teal' : 'text-text-mute'}`} />
                <p className="text-sm font-medium text-text">Drop files here or click to browse</p>
                <p className="text-xs text-text-mute mt-1">PDF, DOCX, XLSX supported</p>
                <input ref={inputRef} type="file" multiple accept={ACCEPTED_EXT} className="hidden"
                  onChange={(e) => addFiles(e.target.files)} />
              </div>

              {files.length > 0 && (
                <div className="space-y-2 max-h-40 overflow-y-auto">
                  {files.map((file) => (
                    <div key={file.name} className="flex items-center gap-3 px-3 py-2 bg-panel-2 rounded-lg border border-border">
                      <div className={`w-7 h-7 rounded flex items-center justify-center text-[9px] font-bold flex-shrink-0 ${extColour(extLabel(file.name))}`}>
                        {extLabel(file.name)}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-medium text-text truncate">{file.name}</p>
                        <p className="text-[11px] text-text-mute">{(file.size / 1_000_000).toFixed(1)} MB</p>
                      </div>
                      <button onClick={() => setFiles((prev) => prev.filter((f) => f.name !== file.name))}
                        className="text-text-mute hover:text-red transition-colors">
                        <X size={13} />
                      </button>
                    </div>
                  ))}
                </div>
              )}

              <div className="flex items-center justify-end gap-3 pt-1">
                <button onClick={onClose} className="px-4 py-2 text-sm text-text-mid hover:text-text transition-colors">Cancel</button>
                <button
                  onClick={handleUpload}
                  disabled={!files.length}
                  className="px-5 py-2 bg-navy hover:bg-navy-soft disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-semibold rounded-lg transition-colors flex items-center gap-2"
                >
                  <Upload size={13} /> Upload
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Document viewer ───────────────────────────────────────────────────────────

function DocumentViewerModal({ doc, onClose }: { doc: WorkspaceDocument; onClose: () => void }) {
  const ext = extLabel(doc.name);
  const colour = extColour(ext);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center px-4 py-6">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-panel rounded-xl border border-border shadow-2xl w-full max-w-lg">
        <div className="flex items-start gap-3 px-5 py-4 border-b border-border">
          <div className={`w-9 h-9 rounded-lg flex items-center justify-center text-[10px] font-bold flex-shrink-0 ${colour}`}>
            {ext}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-text truncate">{doc.name}</p>
            <p className="text-xs text-text-mute mt-0.5">
              {((doc.size_bytes ?? 0) / 1_000_000).toFixed(1)} MB
              {doc.page_count ? ` · ${doc.page_count} pages` : ''}
              {doc.uploaded_at ? ` · ${formatDate(doc.uploaded_at, { day: 'numeric', month: 'short', year: 'numeric' })}` : ''}
            </p>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-panel-2 text-text-mute hover:text-text transition-colors">
            <X size={16} />
          </button>
        </div>

        <div className="px-5 py-5 space-y-3">
          <div className="flex items-center gap-2 py-2.5 px-3 rounded-lg bg-panel-2 border border-border">
            <FileCode size={13} className="text-teal flex-shrink-0" />
            <ExtractionBadge status={doc.extraction_status} />
          </div>

          {doc.extraction_status === 'done' && doc.url ? (
            <a
              href={doc.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-center gap-2 w-full py-2.5 bg-teal/10 hover:bg-teal/15 text-teal text-sm font-medium rounded-lg transition-colors"
            >
              <FileText size={14} /> Open document
            </a>
          ) : doc.extraction_status !== 'done' ? (
            <p className="text-xs text-text-mute text-center py-4">
              {doc.extraction_status === 'processing' || doc.extraction_status === 'queued'
                ? 'Extraction in progress — check back shortly.'
                : 'Extract this document to view its content.'}
            </p>
          ) : null}
        </div>
      </div>
    </div>
  );
}

// ─── Stage flow ───────────────────────────────────────────────────────────────

const STAGE_FLOW: { value: WorkspaceStage; label: string }[] = [
  { value: 'new', label: 'New' },
  { value: 'analysing', label: 'Analysing' },
  { value: 'preparing', label: 'Preparing' },
  { value: 'submitted', label: 'Submitted' },
  { value: 'awarded', label: 'Awarded' },
  { value: 'lost', label: 'Lost' },
  { value: 'no_bid', label: 'No Bid' },
];

// ─── Summary Tab ──────────────────────────────────────────────────────────────

export function SummaryTab({
  workspace,
  onWorkspaceChange,
}: {
  workspace: TenderWorkspace;
  onWorkspaceChange?: (patch: Partial<TenderWorkspace>) => void;
}) {
  const { orgCtx } = useAuth();
  const role = orgCtx?.role;
  const canManageTeam = role === 'org_admin' || role === 'supervisor';

  const [viewingDoc, setViewingDoc] = useState<WorkspaceDocument | null>(null);
  const [showUpload, setShowUpload] = useState(false);
  const [currentStage, setCurrentStage] = useState(workspace.stage);
  const [updatingStage, setUpdatingStage] = useState(false);
  const [documents, setDocuments] = useState<WorkspaceDocument[]>(workspace.documents ?? []);
  const [currentTeamIds, setCurrentTeamIds] = useState<string[]>(workspace.team_members ?? []);
  const [assignableMembers, setAssignableMembers] = useState<OrgMember[]>([]);
  const [showAddDropdown, setShowAddDropdown] = useState(false);
  const [addingMember, setAddingMember] = useState(false);
  const [extractingIds, setExtractingIds] = useState<Set<string>>(new Set());
  const [deletingIds, setDeletingIds] = useState<Set<string>>(new Set());
  const [runningAnalysis, setRunningAnalysis] = useState(false);

  const days = daysUntil(workspace.closing_date);
  const isActive = ['new', 'analysing', 'preparing'].includes(workspace.stage);

  // Poll for doc extraction status and workspace stage when anything is in-flight.
  const hasInFlight = documents.some((doc) =>
    doc.extraction_status === 'queued' || doc.extraction_status === 'processing',
  );
  const isAnalysing = currentStage === 'analysing';

  const refreshWorkspace = useCallback(async () => {
    try {
      const updated = await getWorkspace(workspace.id);
      setDocuments(updated.documents ?? []);
      if (updated.stage !== currentStage) {
        setCurrentStage(updated.stage);
        onWorkspaceChange?.({ stage: updated.stage, ai_summary: updated.ai_summary });
        if (updated.stage === 'preparing') {
          toast.success('Analysis complete — requirements extracted');
          setRunningAnalysis(false);
        }
      }
    } catch { /* silent — next poll will retry */ }
  }, [workspace.id, currentStage, onWorkspaceChange]);

  useEffect(() => {
    if (!hasInFlight && !isAnalysing) return;
    const interval = setInterval(refreshWorkspace, 4000);
    return () => clearInterval(interval);
  }, [hasInFlight, isAnalysing, refreshWorkspace]);

  useEffect(() => {
    if (!canManageTeam) return;
    fetchMyTeam().then(setAssignableMembers).catch(() => {});
  }, [canManageTeam]);

  function resolveName(userId: string): string {
    const found = assignableMembers.find((member) => member.user_id === userId);
    if (found) return found.full_name ?? found.email;
    return userId.includes(' ') ? userId : userId.slice(0, 8) + '…';
  }

  function getInitials(displayName: string): string {
    return displayName.split(' ').map((part) => part[0]).join('').toUpperCase().slice(0, 2);
  }

  async function handleExtract(doc: WorkspaceDocument) {
    if (!doc.document_id) {
      toast.error('This document has no storage path — re-upload it');
      return;
    }
    setExtractingIds((prev) => new Set(prev).add(doc.id));
    setDocuments((prev) => prev.map((d) => d.id === doc.id ? { ...d, extraction_status: 'queued' } : d));
    try {
      await extractWorkspaceDocument(workspace.id, doc.id);
    } catch {
      toast.error(`Failed to queue extraction for ${doc.name}`);
      setDocuments((prev) => prev.map((d) => d.id === doc.id ? { ...d, extraction_status: 'uploaded' } : d));
    } finally {
      setExtractingIds((prev) => { const next = new Set(prev); next.delete(doc.id); return next; });
    }
  }

  async function handleDelete(doc: WorkspaceDocument, event: React.MouseEvent) {
    event.stopPropagation();
    setDeletingIds((prev) => new Set(prev).add(doc.id));
    try {
      await deleteWorkspaceDocument(workspace.id, doc.id);
      setDocuments((prev) => prev.filter((d) => d.id !== doc.id));
    } catch {
      toast.error(`Failed to delete ${doc.name}`);
    } finally {
      setDeletingIds((prev) => { const next = new Set(prev); next.delete(doc.id); return next; });
    }
  }

  async function handleRunAnalysis() {
    const hasDone = documents.some((doc) => doc.extraction_status === 'done');
    if (!hasDone) { toast.error('Extract at least one document first'); return; }
    setRunningAnalysis(true);
    try {
      await analyseWorkspace(workspace.id);
      setCurrentStage('analysing');
      onWorkspaceChange?.({ stage: 'analysing' });
      toast.success('Analysis started — requirements will appear shortly');
    } catch {
      toast.error('Failed to start analysis');
      setRunningAnalysis(false);
    }
  }

  async function handleAddMember(memberId: string) {
    setAddingMember(true);
    setShowAddDropdown(false);
    try {
      const newIds = [...currentTeamIds, memberId];
      await updateWorkspace(workspace.id, { team_members: newIds });
      setCurrentTeamIds(newIds);
    } catch {
      toast.error('Failed to add team member');
    } finally {
      setAddingMember(false);
    }
  }

  async function handleRemoveMember(memberId: string) {
    try {
      const newIds = currentTeamIds.filter((id) => id !== memberId);
      await updateWorkspace(workspace.id, { team_members: newIds });
      setCurrentTeamIds(newIds);
    } catch {
      toast.error('Failed to remove team member');
    }
  }

  async function handleStageChange(newStage: TenderWorkspace['stage']) {
    if (newStage === currentStage) return;
    setUpdatingStage(true);
    try {
      await updateWorkspace(workspace.id, { stage: newStage });
      setCurrentStage(newStage);
      onWorkspaceChange?.({ stage: newStage });
    } catch {
      toast.error('Failed to update stage');
    } finally {
      setUpdatingStage(false);
    }
  }

  const availableToAdd = assignableMembers.filter((member) => !currentTeamIds.includes(member.user_id));
  const { bar, text: scoreText } = readinessColour(workspace.readiness_score);
  const canRunAnalysis = documents.some((doc) => doc.extraction_status === 'done') && !isAnalysing && !runningAnalysis;

  const details = [
    { label: 'Reference', value: workspace.reference || '—' },
    { label: 'Issuing Body', value: workspace.buyer },
    { label: 'Category', value: workspace.category || '—' },
    { label: 'Contract Value', value: formatCurrency(workspace.contract_value, workspace.currency) },
    { label: 'Closing Date', value: formatDate(workspace.closing_date, { day: 'numeric', month: 'long', year: 'numeric' }) },
    { label: 'Time Remaining', value: days < 0 ? 'Closed' : `${days} days`, urgent: isActive && days <= 14 },
  ];

  const memberColours = ['bg-teal/20 text-teal', 'bg-amber-bg text-amber', 'bg-green-bg text-green', 'bg-red-bg text-red'];

  return (
    <>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">

        {/* Left — details + summary + documents */}
        <div className="lg:col-span-2 space-y-5">

          {/* Tender details */}
          <div className="bg-panel border border-border rounded-xl p-5">
            <h3 className="text-sm font-semibold text-text mb-4">Tender Details</h3>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
              {details.map(({ label, value, urgent }) => (
                <div key={label}>
                  <p className="text-xs text-text-mute mb-0.5">{label}</p>
                  <p className={`text-sm font-semibold ${urgent ? 'text-amber' : 'text-text'}`}>{value}</p>
                </div>
              ))}
            </div>
            {workspace.description && (
              <div className="mt-4 pt-4 border-t border-border">
                <p className="text-xs text-text-mute mb-1">Description</p>
                <p className="text-sm text-text-mid leading-relaxed">{workspace.description}</p>
              </div>
            )}
          </div>

          {/* AI Summary */}
          {workspace.ai_summary && (
            <div className="bg-panel border border-border rounded-xl p-5">
              <div className="flex items-center gap-2 mb-3">
                <FileCode size={14} className="text-teal" />
                <h3 className="text-sm font-semibold text-text">AI Summary</h3>
              </div>
              <p className="text-sm text-text-mid leading-relaxed whitespace-pre-line">{workspace.ai_summary}</p>
            </div>
          )}

          {/* Tender Documents */}
          <div className="bg-panel border border-border rounded-xl p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-text">Tender Documents</h3>
              <div className="flex items-center gap-3">
                {/* Run Analysis */}
                <button
                  onClick={handleRunAnalysis}
                  disabled={!canRunAnalysis}
                  title={canRunAnalysis ? 'Extract requirements, summarise, and score readiness' : 'Extract at least one document first'}
                  className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed bg-navy hover:bg-navy-soft text-white"
                >
                  {runningAnalysis || isAnalysing
                    ? <><Loader2 size={11} className="animate-spin" /> Analysing…</>
                    : <><Play size={11} /> Run Analysis</>}
                </button>
                <button
                  onClick={() => setShowUpload(true)}
                  className="flex items-center gap-1.5 text-xs text-teal hover:text-teal-soft font-medium transition-colors"
                >
                  <Upload size={12} /> Upload
                </button>
              </div>
            </div>

            {documents.length === 0 ? (
              <div className="border-2 border-dashed border-border rounded-lg p-6 text-center">
                <Upload size={20} className="text-text-mute mx-auto mb-2" />
                <p className="text-sm text-text-mute">Upload tender documents to get started</p>
                <p className="text-xs text-text-mute mt-0.5">PDF, DOCX, XLSX supported</p>
              </div>
            ) : (
              <div className="space-y-2">
                {documents.map((doc) => {
                  const ext = extLabel(doc.name);
                  const colour = extColour(ext);
                  const isExtracting = extractingIds.has(doc.id);
                  const isDeleting = deletingIds.has(doc.id);
                  const canExtract = doc.document_id && (doc.extraction_status === 'uploaded' || doc.extraction_status === 'failed');

                  return (
                    <div
                      key={doc.id}
                      className="flex items-center justify-between py-2.5 px-3 bg-panel-2 rounded-lg border border-border hover:border-teal/40 transition-all group"
                    >
                      {/* Left: icon + name + status */}
                      <div
                        className="flex items-center gap-3 min-w-0 flex-1 cursor-pointer"
                        onClick={() => setViewingDoc(doc)}
                      >
                        <div className={`w-7 h-7 rounded-md flex items-center justify-center flex-shrink-0 text-[9px] font-bold ${colour}`}>
                          {ext}
                        </div>
                        <div className="min-w-0">
                          <p className="text-xs font-medium text-text truncate group-hover:text-teal transition-colors">{doc.name}</p>
                          <div className="flex items-center gap-2 mt-0.5">
                            <ExtractionBadge status={doc.extraction_status} />
                            {doc.page_count ? <span className="text-[10px] text-text-mute">{doc.page_count}pp</span> : null}
                            <span className="text-[10px] text-text-mute">
                              {((doc.size_bytes ?? 0) / 1_000_000).toFixed(1)} MB
                            </span>
                          </div>
                        </div>
                      </div>

                      {/* Right: actions */}
                      <div className="flex items-center gap-1.5 ml-3 flex-shrink-0">
                        {canExtract && (
                          <button
                            onClick={(e) => { e.stopPropagation(); handleExtract(doc); }}
                            disabled={isExtracting}
                            title="Extract text with LandingAI ADE"
                            className="flex items-center gap-1 px-2.5 py-1 text-[11px] font-medium text-teal hover:bg-teal/10 rounded-lg transition-colors disabled:opacity-50"
                          >
                            {isExtracting
                              ? <Loader2 size={10} className="animate-spin" />
                              : <Zap size={10} />}
                            Extract
                          </button>
                        )}
                        {(doc.extraction_status === 'queued' || doc.extraction_status === 'processing') && (
                          <Loader2 size={12} className="text-teal animate-spin" />
                        )}
                        <button
                          onClick={(e) => handleDelete(doc, e)}
                          disabled={isDeleting}
                          title="Delete document"
                          className="p-1.5 text-text-mute hover:text-red opacity-0 group-hover:opacity-100 transition-all rounded-lg hover:bg-red-bg disabled:opacity-30"
                        >
                          {isDeleting ? <Loader2 size={12} className="animate-spin" /> : <Trash2 size={12} />}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Right — readiness + team + stage */}
        <div className="space-y-5">

          {/* Readiness */}
          <div className="bg-panel border border-border rounded-xl p-5">
            <h3 className="text-sm font-semibold text-text mb-4">Readiness Score</h3>
            <div className="flex items-end gap-3 mb-4">
              <span className={`text-5xl font-bold leading-none ${scoreText}`}>{workspace.readiness_score}</span>
              <span className="text-xl text-text-mute mb-1">/ 100</span>
            </div>
            <div className="w-full h-3 bg-canvas-deep rounded-full overflow-hidden mb-4">
              <div className={`h-full rounded-full ${bar}`} style={{ width: `${workspace.readiness_score}%` }} />
            </div>
            <div className="grid grid-cols-3 gap-2 text-center">
              <div className="bg-green-bg rounded-lg py-2">
                <p className="text-lg font-bold text-green">{workspace.requirements_met ?? 0}</p>
                <p className="text-[11px] text-text-mute">Met</p>
              </div>
              <div className="bg-amber-bg rounded-lg py-2">
                <p className="text-lg font-bold text-amber">{workspace.requirements_partial ?? 0}</p>
                <p className="text-[11px] text-text-mute">Partial</p>
              </div>
              <div className="bg-red-bg rounded-lg py-2">
                <p className="text-lg font-bold text-red">{workspace.requirements_gap ?? 0}</p>
                <p className="text-[11px] text-text-mute">Gap</p>
              </div>
            </div>
          </div>

          {/* Team */}
          <div className="bg-panel border border-border rounded-xl p-5">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Users size={15} className="text-teal" />
                <h3 className="text-sm font-semibold text-text">Team</h3>
              </div>
              {canManageTeam && (
                <div className="relative">
                  <button
                    onClick={() => setShowAddDropdown(!showAddDropdown)}
                    disabled={addingMember || availableToAdd.length === 0}
                    className="flex items-center gap-1 text-xs text-teal hover:text-teal-soft font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    <UserPlus size={12} /> Add
                  </button>
                  {showAddDropdown && availableToAdd.length > 0 && (
                    <div className="absolute right-0 top-full mt-1 bg-panel border border-border rounded-lg shadow-xl z-10 min-w-[168px]">
                      {availableToAdd.map((member) => {
                        const displayName = member.full_name ?? member.email;
                        return (
                          <button
                            key={member.user_id}
                            onClick={() => handleAddMember(member.user_id)}
                            className="w-full flex items-center gap-2 px-3 py-2 text-xs text-text-mid hover:bg-panel-2 transition-colors first:rounded-t-lg last:rounded-b-lg"
                          >
                            <div className="w-5 h-5 rounded-full bg-teal/20 text-teal flex items-center justify-center text-[9px] font-bold flex-shrink-0">
                              {displayName.split(' ').map((p: string) => p[0]).join('').toUpperCase().slice(0, 2)}
                            </div>
                            <span className="truncate">{displayName}</span>
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}
            </div>
            {currentTeamIds.length === 0 ? (
              <p className="text-xs text-text-mute italic">No team members assigned</p>
            ) : (
              <div className="space-y-2">
                {currentTeamIds.map((memberId, index) => {
                  const displayName = resolveName(memberId);
                  return (
                    <div key={memberId} className="flex items-center gap-3 group">
                      <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 ${memberColours[index % memberColours.length]}`}>
                        {getInitials(displayName)}
                      </div>
                      <span className="text-sm text-text-mid flex-1 truncate">{displayName}</span>
                      {canManageTeam && (
                        <button
                          onClick={() => handleRemoveMember(memberId)}
                          className="opacity-0 group-hover:opacity-100 transition-opacity text-text-mute hover:text-red p-0.5"
                        >
                          <X size={12} />
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Stage */}
          <div className="bg-panel border border-border rounded-xl p-5">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-text">Stage</h3>
              {(updatingStage || isAnalysing) && <Loader2 size={13} className="animate-spin text-text-mute" />}
            </div>
            <StageBadge stage={currentStage} />
            <p className="text-xs text-text-mute mt-2 mb-4 leading-relaxed">
              {currentStage === 'new' && 'Upload and extract documents, then run analysis.'}
              {currentStage === 'analysing' && 'AI is extracting and categorising requirements…'}
              {currentStage === 'preparing' && 'Requirements mapped. Preparing bid response.'}
              {currentStage === 'submitted' && 'Bid submitted. Awaiting evaluation.'}
              {currentStage === 'awarded' && 'Bid was awarded.'}
              {currentStage === 'lost' && 'Bid was not awarded in this round.'}
              {currentStage === 'no_bid' && 'Decision taken not to bid on this tender.'}
            </p>
            <div className="space-y-1.5">
              {STAGE_FLOW.map(({ value, label }) => (
                <button
                  key={value}
                  onClick={() => handleStageChange(value)}
                  disabled={updatingStage || isAnalysing}
                  className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-colors text-left ${
                    value === currentStage
                      ? 'bg-navy text-white'
                      : 'bg-panel-2 text-text-mid hover:bg-panel-3 border border-border'
                  }`}
                >
                  <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${value === currentStage ? 'bg-white' : 'bg-border'}`} />
                  {label}
                </button>
              ))}
            </div>
          </div>

        </div>
      </div>

      {viewingDoc && <DocumentViewerModal doc={viewingDoc} onClose={() => setViewingDoc(null)} />}
      {showUpload && (
        <UploadModal
          workspaceId={workspace.id}
          onUploaded={(newDocs) => setDocuments((prev) => [...prev, ...newDocs])}
          onClose={() => setShowUpload(false)}
        />
      )}
    </>
  );
}
