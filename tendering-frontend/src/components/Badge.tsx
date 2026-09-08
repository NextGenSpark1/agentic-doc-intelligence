import type {
  WorkspaceStage,
  BidDecision,
  RequirementStatus,
  RequirementCategory,
  DocCategory,
  VerificationStatus,
} from '../types';

// ─── Workspace stage ──────────────────────────────────────────────────────────

const STAGE_STYLES: Record<WorkspaceStage, string> = {
  new: 'bg-panel-3 text-text-mute',
  analysing: 'bg-amber-bg text-amber',
  preparing: 'bg-teal/10 text-teal',
  submitted: 'bg-green-bg text-green',
  awarded: 'bg-green-bg text-green font-semibold',
  lost: 'bg-panel-3 text-text-mute',
  no_bid: 'bg-red-bg text-red',
};

const STAGE_LABELS: Record<WorkspaceStage, string> = {
  new: 'New', analysing: 'Analysing', preparing: 'Preparing',
  submitted: 'Submitted', awarded: 'Awarded', lost: 'Lost', no_bid: 'No Bid',
};

export function StageBadge({ stage }: { stage: WorkspaceStage }) {
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${STAGE_STYLES[stage]}`}>
      {STAGE_LABELS[stage]}
    </span>
  );
}

// ─── Bid decision ─────────────────────────────────────────────────────────────

const BID_STYLES: Record<BidDecision, string> = {
  pending: 'bg-amber-bg text-amber',
  bid: 'bg-green-bg text-green',
  no_bid: 'bg-red-bg text-red',
};

const BID_LABELS: Record<BidDecision, string> = {
  pending: 'Decision Pending', bid: 'Bid', no_bid: 'No Bid',
};

export function BidDecisionBadge({ decision }: { decision: BidDecision }) {
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${BID_STYLES[decision]}`}>
      {BID_LABELS[decision]}
    </span>
  );
}

// ─── Requirement status ───────────────────────────────────────────────────────

const REQ_STATUS_STYLES: Record<RequirementStatus, string> = {
  met: 'bg-green-bg text-green',
  partial: 'bg-amber-bg text-amber',
  gap: 'bg-red-bg text-red',
  unchecked: 'bg-panel-3 text-text-mute',
};

const REQ_STATUS_ICONS: Record<RequirementStatus, string> = {
  met: '✓', partial: '◐', gap: '✗', unchecked: '○',
};

export function RequirementStatusBadge({ status }: { status: RequirementStatus }) {
  const labels: Record<RequirementStatus, string> = {
    met: 'Met', partial: 'Partial', gap: 'Gap', unchecked: 'Unchecked',
  };
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${REQ_STATUS_STYLES[status]}`}>
      <span>{REQ_STATUS_ICONS[status]}</span>
      {labels[status]}
    </span>
  );
}

// ─── Requirement category ─────────────────────────────────────────────────────

const REQ_CAT_STYLES: Record<RequirementCategory, string> = {
  technical: 'bg-teal/10 text-teal',
  financial: 'bg-green-bg text-green',
  legal: 'bg-red-bg text-red',
  experience: 'bg-amber-bg text-amber',
  personnel: 'bg-panel-3 text-text-mid',
  certification: 'bg-teal/10 text-teal',
  other: 'bg-panel-3 text-text-mute',
};

export function RequirementCategoryBadge({ category }: { category: RequirementCategory }) {
  const labels: Record<RequirementCategory, string> = {
    technical: 'Technical', financial: 'Financial', legal: 'Legal',
    experience: 'Experience', personnel: 'Personnel', certification: 'Certification', other: 'Other',
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${REQ_CAT_STYLES[category]}`}>
      {labels[category]}
    </span>
  );
}

// ─── Document category ────────────────────────────────────────────────────────

const DOC_CAT_STYLES: Record<DocCategory, string> = {
  registration: 'bg-teal/10 text-teal',
  certification: 'bg-amber-bg text-amber',
  financial: 'bg-green-bg text-green',
  technical: 'bg-panel-3 text-text-mid',
  personnel: 'bg-panel-3 text-text-mid',
  other: 'bg-panel-3 text-text-mute',
};

export function DocCategoryBadge({ category }: { category: DocCategory }) {
  const labels: Record<DocCategory, string> = {
    registration: 'Registration', certification: 'Certification', financial: 'Financial',
    technical: 'Technical', personnel: 'Personnel', other: 'Other',
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${DOC_CAT_STYLES[category]}`}>
      {labels[category]}
    </span>
  );
}

// ─── Verification status ──────────────────────────────────────────────────────

const VERIFY_STYLES: Record<VerificationStatus, string> = {
  verified: 'bg-green-bg text-green',
  pending: 'bg-amber-bg text-amber',
  expired: 'bg-red-bg text-red',
  missing: 'bg-panel-3 text-text-mute',
};

const VERIFY_ICONS: Record<VerificationStatus, string> = {
  verified: '✓', pending: '⋯', expired: '!', missing: '○',
};

export function VerificationBadge({ status }: { status: VerificationStatus }) {
  const labels: Record<VerificationStatus, string> = {
    verified: 'Verified', pending: 'Pending', expired: 'Expired', missing: 'Missing',
  };
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${VERIFY_STYLES[status]}`}>
      <span className="text-[10px]">{VERIFY_ICONS[status]}</span>
      {labels[status]}
    </span>
  );
}
