import { useState, useRef } from 'react';
import { FileText, Users, Upload, X, CheckCircle2, FileCode, Loader2, CloudUpload } from 'lucide-react';
import type { WorkspaceStage } from '../../types';
import toast from 'react-hot-toast';
import { StageBadge } from '../Badge';
import { daysUntil, formatCurrency, formatDate, readinessColour } from '../../lib/utils';
import type { TenderWorkspace, WorkspaceDocument } from '../../types';

// ─── Mock extracted text per document ─────────────────────────────────────────

const MOCK_EXTRACTED: Record<string, { pages: number; text: string }> = {
  d1: {
    pages: 47,
    text: `REQUEST FOR PROPOSALS
National Broadband Infrastructure — Phase 3
Reference: ICT/INFRA/2026/047
Ministry of ICT & Digital Economy

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 4 — ELIGIBILITY AND QUALIFICATION CRITERIA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

4.1  Regulatory Compliance                                    [Page 22]
─────────────────────────────────────────────────────────────────────
4.1.3  The Tenderer SHALL hold a valid Class 1 Telecommunications
       Operator License issued by the Telecommunications Regulatory
       Commission (TRC). The license must be current at the time of
       submission and remain valid throughout the contract period.

       Documentary evidence: Certified copy of TRC license certificate.

4.2  Quality and Management Systems                           [Page 23]
─────────────────────────────────────────────────────────────────────
4.2.1  The Tenderer SHALL hold a current ISO 9001:2015 Quality
       Management System (QMS) certification issued by an accredited
       certification body. The certificate must not have expired as of
       the bid closing date.

4.3  Technical Experience                                     [Page 25]
─────────────────────────────────────────────────────────────────────
4.3.1  The Tenderer SHALL demonstrate a minimum of ten (10) years of
       continuous experience in the design, supply, installation, and
       commissioning of large-scale telecommunications infrastructure
       projects. Experience shall be documented through a project
       portfolio listing comparable projects, clients, and completion
       dates.

4.3.2  At least three (3) of the documented projects shall have a
       contract value of USD 5,000,000 or greater.

4.4  Key Personnel Requirements                               [Page 26]
─────────────────────────────────────────────────────────────────────
4.4.1  Project Manager
       • PMP® certification from the Project Management Institute (PMI)
         or equivalent, currently valid
       • Minimum eight (8) years of experience managing telecoms
         infrastructure projects
       • Curriculum vitae and certification copies to be submitted
         with the bid

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 5 — SOCIAL AND LEGAL REQUIREMENTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

5.1  Local Content Requirements                               [Page 28]
─────────────────────────────────────────────────────────────────────
5.1.a  The Successful Tenderer SHALL ensure that a minimum of forty
       percent (40%) of total project headcount consists of nationals
       or permanent residents. The workforce composition plan must be
       submitted with the bid and updated quarterly during execution.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 6 — FINANCIAL REQUIREMENTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

6.1  Financial Capacity                                       [Page 30]
─────────────────────────────────────────────────────────────────────
       The Tenderer SHALL demonstrate annual turnover of no less than
       USD 25,000,000 (twenty-five million US dollars) for each of the
       three (3) preceding financial years. Audited financial statements
       for each year must be submitted.

6.2  Performance Security                                     [Page 31]
─────────────────────────────────────────────────────────────────────
       The Successful Tenderer shall furnish a Performance Bond equal
       to five percent (5%) of the total contract value within fourteen
       (14) days of contract signing. The bond shall be issued by a
       reputable bank and remain valid until project completion.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 7 — TECHNICAL REQUIREMENTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

7.1  Network Operations Centre (NOC)                          [Page 34]
─────────────────────────────────────────────────────────────────────
       The Tenderer SHALL operate or have direct access to a 24/7
       Network Operations Centre (NOC) with:
       • SLA-backed fault response time of ≤15 minutes
       • Real-time monitoring of all network nodes
       • Escalation procedures and dedicated NOC hotline

7.3  Information Security                                     [Page 35]
─────────────────────────────────────────────────────────────────────
       The Tenderer SHALL hold a current ISO/IEC 27001 Information
       Security Management System (ISMS) certification, or an
       equivalent standard acceptable to the Ministry. The certificate
       shall be valid at bid closing and throughout the contract.

8.4  Equipment Warranty                                       [Page 38]
─────────────────────────────────────────────────────────────────────
       [DESIRABLE] All supplied equipment shall carry a minimum five
       (5) year manufacturer's warranty. The Tenderer shall maintain
       an in-country spare parts inventory sufficient for at least
       thirty (30) days of uninterrupted operations.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
END OF EXTRACTED TEXT — Page 47 of 47
Extracted by LandingAI ADE · Confidence: 99.2%
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`,
  },
  d2: {
    pages: 24,
    text: `TECHNICAL SPECIFICATIONS ANNEX
ICT/INFRA/2026/047 — National Broadband Infrastructure Phase 3

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PART A — FIBRE OPTIC BACKBONE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

A.1  Cable Specifications
─────────────────────────────────────────────────────────────────────
     Fibre type:     Single-mode G.652D compliant (ITU-T)
     Capacity:       Minimum 96 fibre strands per duct
     Route length:   Approximately 2,400 km across 47 districts
     Burial depth:   ≥1.2 m in agricultural zones; ≥1.5 m at road crossings

A.2  Transmission Equipment
─────────────────────────────────────────────────────────────────────
     Technology:     DWDM (Dense Wavelength Division Multiplexing)
     Capacity:       100 Gbps per wavelength, minimum 80 wavelengths
     Latency:        ≤5 ms end-to-end across national backbone

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PART B — LAST-MILE CONNECTIVITY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

B.1  District Connection Points
─────────────────────────────────────────────────────────────────────
     ┌─────────────────────┬───────────────┬──────────────────────┐
     │ Zone                │ Districts     │ Min. Bandwidth (Gbps)│
     ├─────────────────────┼───────────────┼──────────────────────┤
     │ Northern Region     │ 12            │ 10                   │
     │ Central Region      │ 18            │ 20                   │
     │ Southern Region     │ 17            │ 10                   │
     └─────────────────────┴───────────────┴──────────────────────┘

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
END OF EXTRACTED TEXT — Page 24 of 24
Extracted by LandingAI ADE · Confidence: 98.7%
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`,
  },
  d3: {
    pages: 8,
    text: `BILL OF QUANTITIES — ANNEX C
ICT/INFRA/2026/047

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 1 — CIVIL WORKS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌──────┬────────────────────────────────────┬──────┬─────────┬──────────────┐
│ Item │ Description                        │ Unit │  Qty    │ Unit Rate    │
├──────┼────────────────────────────────────┼──────┼─────────┼──────────────┤
│ 1.1  │ Trench excavation (soft soil)      │ km   │   800   │ [Tenderer]   │
│ 1.2  │ Trench excavation (rocky terrain)  │ km   │   200   │ [Tenderer]   │
│ 1.3  │ HDPE duct installation (100mm)     │ km   │ 2,400   │ [Tenderer]   │
│ 1.4  │ Cable jointing chambers            │ No.  │   960   │ [Tenderer]   │
│ 1.5  │ Road crossing (directional drill)  │ No.  │   340   │ [Tenderer]   │
└──────┴────────────────────────────────────┴──────┴─────────┴──────────────┘

SECTION 2 — FIBRE CABLE SUPPLY & INSTALLATION

┌──────┬────────────────────────────────────┬──────┬─────────┬──────────────┐
│ 2.1  │ 96-core single-mode fibre cable    │ km   │ 2,400   │ [Tenderer]   │
│ 2.2  │ Fibre splicing (fusion)            │ No.  │  4,800  │ [Tenderer]   │
│ 2.3  │ OTDR acceptance testing            │ km   │ 2,400   │ [Tenderer]   │
└──────┴────────────────────────────────────┴──────┴─────────┴──────────────┘

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
END OF EXTRACTED TEXT — Page 8 of 8
Extracted by LandingAI ADE · Confidence: 97.4%
(Tables reconstructed from Excel — 3 worksheets merged)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`,
  },
  d4: {
    pages: 38,
    text: `REQUEST FOR PROPOSALS
Hospital Management Information System — 12 Facilities
Reference: MOH/IT/2026/031
Ministry of Health

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 2 — TECHNICAL REQUIREMENTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

2.1  Interoperability Standards                               [Page 4]
─────────────────────────────────────────────────────────────────────
     The HMIS SHALL implement HL7 FHIR Release 4 (R4) compliant APIs
     for all clinical data exchange. Non-compliant systems will not be
     considered. Evidence of FHIR R4 certification or successful
     third-party conformance testing must be included in the bid.

2.3  Implementation References                                [Page 9]
─────────────────────────────────────────────────────────────────────
     The Tenderer SHALL provide a minimum of three (3) reference
     letters from public health sector clients for whom comparable
     HMIS implementations have been completed within the last five (5)
     years.

SECTION 3 — DATA GOVERNANCE                                  [Page 12]
─────────────────────────────────────────────────────────────────────
3.4  Data Residency
     All patient records and personal health information SHALL be
     stored exclusively within the national data centre infrastructure
     approved by the Ministry. Storage on overseas or unregulated
     cloud platforms is prohibited.

SECTION 5 — SERVICE LEVELS                                   [Page 18]
─────────────────────────────────────────────────────────────────────
5.2  Support and Maintenance
     The Tenderer SHALL provide 24/7 technical support with a maximum
     four (4) hour on-site response time for Priority 1 incidents
     at any of the twelve (12) facilities.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
END OF EXTRACTED TEXT — Page 38 of 38
Extracted by LandingAI ADE · Confidence: 98.1%
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`,
  },
};

const FALLBACK_EXTRACTED = {
  pages: 12,
  text: `Document content extracted successfully.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXTRACTED TEXT PREVIEW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

This document has been processed by LandingAI ADE.
All text, tables, and structured content have been
preserved for AI analysis.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Extracted by LandingAI ADE · Confidence: 96.8%
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`,
};

// ─── Upload Modal ─────────────────────────────────────────────────────────────

const ACCEPTED = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'];
const ACCEPTED_EXT = '.pdf,.docx,.xlsx';

type UploadStage = 'idle' | 'uploading' | 'extracting' | 'done';

function UploadModal({ workspaceId, onClose }: { workspaceId: string; onClose: () => void }) {
  const [files, setFiles] = useState<File[]>([]);
  const [dragging, setDragging] = useState(false);
  const [stage, setStage] = useState<UploadStage>('idle');
  const inputRef = useRef<HTMLInputElement>(null);

  void workspaceId; // will be used when wiring real API

  function addFiles(incoming: FileList | null) {
    if (!incoming) return;
    const valid = Array.from(incoming).filter((f) => ACCEPTED.includes(f.type) || f.name.match(/\.(pdf|docx|xlsx)$/i));
    setFiles((prev) => {
      const names = new Set(prev.map((f) => f.name));
      return [...prev, ...valid.filter((f) => !names.has(f.name))];
    });
  }

  function removeFile(name: string) {
    setFiles((prev) => prev.filter((f) => f.name !== name));
  }

  async function handleUpload() {
    if (!files.length) return;
    setStage('uploading');
    await new Promise((r) => setTimeout(r, 1200));
    setStage('extracting');
    await new Promise((r) => setTimeout(r, 2000));
    setStage('done');
    await new Promise((r) => setTimeout(r, 600));
    toast.success(`${files.length} document${files.length > 1 ? 's' : ''} uploaded — AI analysis running`);
    onClose();
  }

  const ext = (name: string) => name.split('.').pop()?.toUpperCase() ?? 'FILE';
  const extColour = (e: string) =>
    e === 'PDF' ? 'bg-red-bg text-red' :
    e === 'XLSX' ? 'bg-green-bg text-green' : 'bg-teal/10 text-teal';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={stage === 'idle' ? onClose : undefined} />

      <div className="relative bg-panel rounded-xl border border-border shadow-2xl w-full max-w-lg">
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <div>
            <h2 className="text-sm font-semibold text-text">Upload Tender Documents</h2>
            <p className="text-xs text-text-mute mt-0.5">PDF, DOCX, XLSX — ADE will extract text automatically</p>
          </div>
          {stage === 'idle' && (
            <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-panel-2 text-text-mute hover:text-text transition-colors">
              <X size={15} />
            </button>
          )}
        </div>

        <div className="px-6 py-5 space-y-4">
          {stage === 'idle' ? (
            <>
              {/* Drop zone */}
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
                <input ref={inputRef} type="file" multiple accept={ACCEPTED_EXT} className="hidden" onChange={(e) => addFiles(e.target.files)} />
              </div>

              {/* File list */}
              {files.length > 0 && (
                <div className="space-y-2 max-h-40 overflow-y-auto">
                  {files.map((f) => (
                    <div key={f.name} className="flex items-center gap-3 px-3 py-2 bg-panel-2 rounded-lg border border-border">
                      <div className={`w-7 h-7 rounded flex items-center justify-center text-[9px] font-bold flex-shrink-0 ${extColour(ext(f.name))}`}>
                        {ext(f.name)}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-medium text-text truncate">{f.name}</p>
                        <p className="text-[11px] text-text-mute">{(f.size / 1_000_000).toFixed(1)} MB</p>
                      </div>
                      <button onClick={() => removeFile(f.name)} className="text-text-mute hover:text-red transition-colors">
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
                  <Upload size={13} />
                  Upload & Analyse
                </button>
              </div>
            </>
          ) : (
            <div className="py-8 text-center space-y-3">
              {stage === 'done' ? (
                <CheckCircle2 size={32} className="text-green mx-auto" />
              ) : (
                <Loader2 size={32} className="text-teal mx-auto animate-spin" />
              )}
              <p className="text-sm font-semibold text-text">
                {stage === 'uploading' && 'Uploading to Supabase Storage…'}
                {stage === 'extracting' && 'LandingAI ADE extracting text & structure…'}
                {stage === 'done' && 'Complete — queuing AI analysis'}
              </p>
              <p className="text-xs text-text-mute">
                {stage === 'extracting' && 'Tables, clause numbers, and nested content are being preserved'}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Document Viewer Modal ─────────────────────────────────────────────────────

function DocumentViewerModal({ doc, onClose }: { doc: WorkspaceDocument; onClose: () => void }) {
  const extracted = MOCK_EXTRACTED[doc.id] ?? FALLBACK_EXTRACTED;
  const ext = doc.name.split('.').pop()?.toUpperCase() ?? 'FILE';
  const extColour =
    ext === 'PDF' ? 'bg-red-bg text-red' :
    ext === 'XLSX' ? 'bg-green-bg text-green' :
    ext === 'DOCX' ? 'bg-teal/10 text-teal' : 'bg-panel-3 text-text-mute';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center px-4 py-6">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />

      <div className="relative bg-panel rounded-xl border border-border shadow-2xl w-full max-w-3xl flex flex-col max-h-[85vh]">

        {/* Header */}
        <div className="flex items-start gap-3 px-5 py-4 border-b border-border flex-shrink-0">
          <div className={`w-9 h-9 rounded-lg flex items-center justify-center text-[10px] font-bold flex-shrink-0 ${extColour}`}>
            {ext}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-text truncate">{doc.name}</p>
            <p className="text-xs text-text-mute mt-0.5">
              {((doc.size_bytes ?? 0) / 1_000_000).toFixed(1)} MB · {extracted.pages} pages ·
              Uploaded {formatDate(doc.uploaded_at ?? '', { day: 'numeric', month: 'short', year: 'numeric' })}
            </p>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <span className="flex items-center gap-1 text-[11px] text-green font-medium">
              <CheckCircle2 size={12} />
              ADE Extracted
            </span>
            <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-panel-2 text-text-mute hover:text-text transition-colors">
              <X size={16} />
            </button>
          </div>
        </div>

        {/* ADE badge */}
        <div className="px-5 py-2.5 border-b border-border bg-teal/5 flex items-center gap-2 flex-shrink-0">
          <FileCode size={13} className="text-teal" />
          <p className="text-xs text-teal font-medium">
            Extracted by LandingAI ADE — structure, tables, and clause numbering preserved
          </p>
        </div>

        {/* Extracted text */}
        <div className="flex-1 overflow-y-auto p-5">
          <pre className="text-[12px] font-mono text-text-mid leading-relaxed whitespace-pre-wrap bg-canvas-deep rounded-lg p-4 border border-border">
            {extracted.text}
          </pre>
        </div>
      </div>
    </div>
  );
}

// ─── Summary Tab ──────────────────────────────────────────────────────────────

const STAGE_FLOW: { value: WorkspaceStage; label: string }[] = [
  { value: 'new', label: 'New' },
  { value: 'analysing', label: 'Analysing' },
  { value: 'preparing', label: 'Preparing' },
  { value: 'submitted', label: 'Submitted' },
  { value: 'awarded', label: 'Awarded' },
  { value: 'lost', label: 'Lost' },
  { value: 'no_bid', label: 'No Bid' },
];

export function SummaryTab({ workspace }: { workspace: TenderWorkspace }) {
  const [viewingDoc, setViewingDoc] = useState<WorkspaceDocument | null>(null);
  const [showUpload, setShowUpload] = useState(false);
  const [currentStage, setCurrentStage] = useState(workspace.stage);
  const [updatingStage, setUpdatingStage] = useState(false);
  const days = daysUntil(workspace.closing_date);
  const isActive = ['new', 'analysing', 'preparing'].includes(workspace.stage);

  async function handleStageChange(newStage: TenderWorkspace['stage']) {
    if (newStage === currentStage) return;
    setUpdatingStage(true);
    // TODO: PATCH /tendering/workspaces/{workspace.id} when backend ready
    await new Promise((r) => setTimeout(r, 500));
    setCurrentStage(newStage);
    setUpdatingStage(false);
    toast.success(`Stage updated to ${newStage}`);
  }
  const { bar, text } = readinessColour(workspace.readiness_score);

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

        {/* Left — details + documents */}
        <div className="lg:col-span-2 space-y-5">

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

          <div className="bg-panel border border-border rounded-xl p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-text">Tender Documents</h3>
              <button
                onClick={() => setShowUpload(true)}
                className="flex items-center gap-1.5 text-xs text-teal hover:text-teal-soft font-medium transition-colors"
              >
                <Upload size={12} /> Upload
              </button>
            </div>
            {(workspace.documents ?? []).length === 0 ? (
              <div className="border-2 border-dashed border-border rounded-lg p-6 text-center">
                <Upload size={20} className="text-text-mute mx-auto mb-2" />
                <p className="text-sm text-text-mute">Drop tender documents here</p>
                <p className="text-xs text-text-mute mt-0.5">PDF, DOCX, XLSX supported</p>
              </div>
            ) : (
              <div className="space-y-2">
                {(workspace.documents ?? []).map((doc) => {
                  const ext = doc.name.split('.').pop()?.toUpperCase() ?? '';
                  const extColour =
                    ext === 'PDF' ? 'bg-red-bg text-red' :
                    ext === 'XLSX' ? 'bg-green-bg text-green' :
                    ext === 'DOCX' ? 'bg-teal/10 text-teal' : 'bg-panel-3 text-text-mute';
                  return (
                    <div
                      key={doc.id}
                      onClick={() => setViewingDoc(doc)}
                      className="flex items-center justify-between py-2.5 px-3 bg-panel-2 rounded-lg border border-border hover:border-teal cursor-pointer transition-all group"
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <div className={`w-7 h-7 rounded-md flex items-center justify-center flex-shrink-0 text-[9px] font-bold ${extColour}`}>
                          {ext}
                        </div>
                        <div className="min-w-0">
                          <p className="text-xs font-medium text-text truncate group-hover:text-teal transition-colors">{doc.name}</p>
                          <p className="text-[11px] text-text-mute">
                            {((doc.size_bytes ?? 0) / 1_000_000).toFixed(1)} MB · {formatDate(doc.uploaded_at ?? '', { day: 'numeric', month: 'short' })}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 ml-3 flex-shrink-0">
                        <span className="text-[10px] text-green font-medium hidden group-hover:flex items-center gap-1">
                          <CheckCircle2 size={10} /> ADE extracted
                        </span>
                        <FileText size={14} className="text-text-mute group-hover:text-teal transition-colors" />
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

          <div className="bg-panel border border-border rounded-xl p-5">
            <h3 className="text-sm font-semibold text-text mb-4">Readiness Score</h3>
            <div className="flex items-end gap-3 mb-4">
              <span className={`text-5xl font-bold leading-none ${text}`}>{workspace.readiness_score}</span>
              <span className="text-xl text-text-mute mb-1">/ 100</span>
            </div>
            <div className="w-full h-3 bg-canvas-deep rounded-full overflow-hidden mb-4">
              <div className={`h-full rounded-full ${bar}`} style={{ width: `${workspace.readiness_score}%` }} />
            </div>
            <div className="grid grid-cols-3 gap-2 text-center">
              <div className="bg-green-bg rounded-lg py-2">
                <p className="text-lg font-bold text-green">{workspace.requirements_met}</p>
                <p className="text-[11px] text-text-mute">Met</p>
              </div>
              <div className="bg-amber-bg rounded-lg py-2">
                <p className="text-lg font-bold text-amber">{workspace.requirements_partial}</p>
                <p className="text-[11px] text-text-mute">Partial</p>
              </div>
              <div className="bg-red-bg rounded-lg py-2">
                <p className="text-lg font-bold text-red">{workspace.requirements_gap}</p>
                <p className="text-[11px] text-text-mute">Gap</p>
              </div>
            </div>
          </div>

          <div className="bg-panel border border-border rounded-xl p-5">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Users size={15} className="text-teal" />
                <h3 className="text-sm font-semibold text-text">Team</h3>
              </div>
              <button className="text-xs text-teal hover:text-teal-soft font-medium">Add</button>
            </div>
            <div className="space-y-2">
              {(workspace.team_members ?? []).map((member, i) => {
                const initials = member.split(' ').map((n) => n[0]).join('').toUpperCase().slice(0, 2);
                return (
                  <div key={member} className="flex items-center gap-3">
                    <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 ${memberColours[i % memberColours.length]}`}>
                      {initials}
                    </div>
                    <span className="text-sm text-text-mid">{member}</span>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="bg-panel border border-border rounded-xl p-5">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-text">Stage</h3>
              {updatingStage && <Loader2 size={13} className="animate-spin text-text-mute" />}
            </div>
            <StageBadge stage={currentStage} />
            <p className="text-xs text-text-mute mt-2 mb-4 leading-relaxed">
              {currentStage === 'new' && 'Upload tender documents to begin AI analysis.'}
              {currentStage === 'analysing' && 'AI is extracting and categorising requirements.'}
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
                  disabled={updatingStage}
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

      {viewingDoc && (
        <DocumentViewerModal doc={viewingDoc} onClose={() => setViewingDoc(null)} />
      )}
      {showUpload && (
        <UploadModal workspaceId={workspace.id} onClose={() => setShowUpload(false)} />
      )}
    </>
  );
}
