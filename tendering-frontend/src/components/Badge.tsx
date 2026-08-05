import type { TenderStatus, ComplianceResult, ReferenceCategory } from '../types';

// ─── Tender status badge ──────────────────────────────────────────────────────

const STATUS_STYLES: Record<TenderStatus, string> = {
  open: 'bg-green-bg text-green',
  closed: 'bg-panel-3 text-text-mute',
  draft: 'bg-amber-bg text-amber',
  awarded: 'bg-teal/10 text-teal',
};

const STATUS_LABELS: Record<TenderStatus, string> = {
  open: 'Open',
  closed: 'Closed',
  draft: 'Draft',
  awarded: 'Awarded',
};

export function StatusBadge({ status }: { status: TenderStatus }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${STATUS_STYLES[status]}`}>
      {STATUS_LABELS[status]}
    </span>
  );
}

// ─── Compliance result badge ──────────────────────────────────────────────────

const COMPLIANCE_STYLES: Record<ComplianceResult, string> = {
  pass: 'bg-green-bg text-green',
  partial: 'bg-amber-bg text-amber',
  fail: 'bg-red-bg text-red',
};

const COMPLIANCE_LABELS: Record<ComplianceResult, string> = {
  pass: 'Pass',
  partial: 'Partial',
  fail: 'Fail',
};

export function ComplianceBadge({ result }: { result: ComplianceResult }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${COMPLIANCE_STYLES[result]}`}>
      {COMPLIANCE_LABELS[result]}
    </span>
  );
}

// ─── Reference category badge ─────────────────────────────────────────────────

const CATEGORY_STYLES: Record<ReferenceCategory, string> = {
  legal: 'bg-red-bg text-red',
  financial: 'bg-green-bg text-green',
  technical: 'bg-teal/10 text-teal',
  template: 'bg-amber-bg text-amber',
  other: 'bg-panel-3 text-text-mute',
};

export function CategoryBadge({ category }: { category: ReferenceCategory }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium capitalize ${CATEGORY_STYLES[category]}`}>
      {category}
    </span>
  );
}
