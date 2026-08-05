import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, FileText, CheckSquare, AlertCircle } from 'lucide-react';
import { getTender, runComplianceCheck } from '../api/tenders';
import { StatusBadge, ComplianceBadge } from '../components/Badge';
import type { Tender, ComplianceCheck } from '../types';
import toast from 'react-hot-toast';

export function TenderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [tender, setTender] = useState<Tender | null>(null);
  const [compliance, setCompliance] = useState<ComplianceCheck | null>(null);
  const [checkingCompliance, setCheckingCompliance] = useState(false);

  useEffect(() => {
    if (id) getTender(id).then(setTender);
  }, [id]);

  async function handleComplianceCheck() {
    if (!id) return;
    setCheckingCompliance(true);
    try {
      const result = await runComplianceCheck(id);
      setCompliance(result);
      toast.success('Compliance check complete');
    } catch {
      toast.error('Failed to run compliance check');
    } finally {
      setCheckingCompliance(false);
    }
  }

  if (!tender) {
    return (
      <div className="pt-[6.5rem] px-6 text-center text-sm text-text-mute py-16">Loading...</div>
    );
  }

  return (
    <div className="pt-[6.5rem] px-6 pb-10 max-w-4xl mx-auto">
      {/* Back button */}
      <button
        onClick={() => navigate('/tenders')}
        className="flex items-center gap-1.5 text-sm text-text-mute hover:text-teal transition-colors mb-5"
      >
        <ArrowLeft size={15} />
        Back to Tender Library
      </button>

      {/* Header */}
      <div className="bg-panel border border-border rounded-lg p-6 mb-5">
        <div className="flex items-start justify-between gap-4 mb-4">
          <h1 className="text-lg font-bold text-text">{tender.title}</h1>
          <StatusBadge status={tender.status} />
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm mb-5">
          <div>
            <p className="text-xs text-text-mute mb-0.5">Issuer</p>
            <p className="font-medium text-text">{tender.issuer}</p>
          </div>
          <div>
            <p className="text-xs text-text-mute mb-0.5">Category</p>
            <p className="font-medium text-text">{tender.category}</p>
          </div>
          <div>
            <p className="text-xs text-text-mute mb-0.5">Deadline</p>
            <p className="font-medium text-text">{new Date(tender.deadline).toLocaleDateString()}</p>
          </div>
          <div>
            <p className="text-xs text-text-mute mb-0.5">Budget</p>
            <p className="font-medium text-text">
              {tender.budget_max ? `${tender.currency} ${(tender.budget_max / 1_000_000).toFixed(1)}M` : 'N/A'}
            </p>
          </div>
        </div>

        <p className="text-sm text-text-mid leading-relaxed">{tender.description}</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* Requirements */}
        <div className="bg-panel border border-border rounded-lg p-5">
          <div className="flex items-center gap-2 mb-4">
            <CheckSquare size={16} className="text-teal" />
            <h2 className="text-sm font-semibold text-text">Requirements</h2>
          </div>
          <ul className="space-y-2">
            {tender.requirements.map((req, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-text-mid">
                <span className="w-1.5 h-1.5 rounded-full bg-teal mt-1.5 flex-shrink-0" />
                {req}
              </li>
            ))}
          </ul>
        </div>

        {/* Documents */}
        <div className="bg-panel border border-border rounded-lg p-5">
          <div className="flex items-center gap-2 mb-4">
            <FileText size={16} className="text-teal" />
            <h2 className="text-sm font-semibold text-text">Documents</h2>
          </div>
          {tender.documents.length === 0 ? (
            <p className="text-sm text-text-mute">No documents attached.</p>
          ) : (
            <ul className="space-y-2">
              {tender.documents.map((doc) => (
                <li key={doc.id} className="flex items-center justify-between text-sm">
                  <a href={doc.url} className="text-teal hover:underline truncate">{doc.name}</a>
                  <span className="text-xs text-text-mute ml-2 flex-shrink-0">
                    {(doc.size_bytes / 1_000_000).toFixed(1)} MB
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* Compliance section */}
      <div className="bg-panel border border-border rounded-lg p-5 mt-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <AlertCircle size={16} className="text-teal" />
            <h2 className="text-sm font-semibold text-text">Compliance Check</h2>
          </div>
          <button
            onClick={handleComplianceCheck}
            disabled={checkingCompliance || tender.status !== 'open'}
            className="px-4 py-1.5 rounded text-xs font-medium bg-teal text-white hover:bg-teal-soft disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {checkingCompliance ? 'Checking…' : 'Run Check'}
          </button>
        </div>

        {compliance ? (
          <>
            <div className="flex items-center gap-3 mb-4">
              <ComplianceBadge result={compliance.result} />
              <span className="text-sm font-semibold text-text">{compliance.overall_score}% overall</span>
              <span className="text-xs text-text-mute ml-auto">
                {new Date(compliance.checked_at).toLocaleString()}
              </span>
            </div>
            <div className="space-y-2">
              {compliance.items.map((item, i) => (
                <div key={i} className="flex items-start gap-3 text-sm p-3 rounded-lg bg-panel-2">
                  <ComplianceBadge result={item.result} />
                  <div className="min-w-0">
                    <p className="font-medium text-text text-xs">{item.requirement}</p>
                    <p className="text-xs text-text-mute mt-0.5">{item.note}</p>
                  </div>
                </div>
              ))}
            </div>
          </>
        ) : (
          <p className="text-sm text-text-mute">Run a compliance check to see how well your organization meets the tender requirements.</p>
        )}
      </div>
    </div>
  );
}
