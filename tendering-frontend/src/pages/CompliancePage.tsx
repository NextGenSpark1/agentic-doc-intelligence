import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BarChart3, ExternalLink } from 'lucide-react';
import { getComplianceChecks } from '../api/tenders';
import { ComplianceBadge } from '../components/Badge';
import type { ComplianceCheck } from '../types';

function ScoreBar({ score }: { score: number }) {
  const color = score >= 80 ? 'bg-green' : score >= 50 ? 'bg-amber' : 'bg-red';
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 h-1.5 bg-canvas-deep rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${score}%` }} />
      </div>
      <span className="text-xs font-mono font-medium text-text w-8 text-right">{score}%</span>
    </div>
  );
}

export function CompliancePage() {
  const navigate = useNavigate();
  const [checks, setChecks] = useState<ComplianceCheck[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getComplianceChecks().then(setChecks).finally(() => setLoading(false));
  }, []);

  return (
    <div className="pt-[6.5rem] px-6 pb-10 max-w-6xl mx-auto">
      <div className="mb-6">
        <h1 className="text-xl font-bold text-text">Compliance</h1>
        <p className="text-sm text-text-mute mt-0.5">Track compliance check history across all tenders</p>
      </div>

      {loading ? (
        <div className="text-center text-sm text-text-mute py-16">Loading...</div>
      ) : checks.length === 0 ? (
        <div className="text-center text-sm text-text-mute py-16">
          No compliance checks yet.{' '}
          <button onClick={() => navigate('/tenders')} className="text-teal hover:underline">
            Browse tenders
          </button>{' '}
          to run your first check.
        </div>
      ) : (
        <div className="space-y-4">
          {checks.map((check) => (
            <div key={check.id} className="bg-panel border border-border rounded-lg p-5">
              <div className="flex items-start justify-between gap-4 mb-3">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <BarChart3 size={14} className="text-text-mute" />
                    <h3 className="text-sm font-semibold text-text">{check.tender_title}</h3>
                    <ComplianceBadge result={check.result} />
                  </div>
                  <p className="text-xs text-text-mute">
                    Checked {new Date(check.checked_at).toLocaleString()}
                  </p>
                </div>
                <button
                  onClick={() => navigate(`/tenders/${check.tender_id}`)}
                  className="flex items-center gap-1 text-xs text-teal hover:underline flex-shrink-0"
                >
                  View tender <ExternalLink size={12} />
                </button>
              </div>

              <ScoreBar score={check.overall_score} />

              <div className="mt-4 space-y-2">
                {check.items.map((item, i) => (
                  <div key={i} className="flex items-start gap-3 text-sm p-3 rounded-lg bg-panel-2">
                    <ComplianceBadge result={item.result} />
                    <div className="min-w-0">
                      <p className="font-medium text-text text-xs">{item.requirement}</p>
                      <p className="text-xs text-text-mute mt-0.5">{item.note}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
