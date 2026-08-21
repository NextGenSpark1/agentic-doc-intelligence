"""Case summary/risk scoring — the part that decides which findings 'count'."""
from backend.apps.investigation.pipeline.summarise import _risk_score, active_findings


def _f(status, severity="high"):
    return {"human_review_status": status, "severity": severity}


def test_active_findings_drops_dismissed_only():
    findings = [_f("pending"), _f("confirmed"), _f("dismissed")]
    kept = active_findings(findings)
    statuses = [f["human_review_status"] for f in kept]
    assert statuses == ["pending", "confirmed"]  # dismissed removed, order preserved


def test_dismissed_findings_do_not_inflate_risk():
    live = [_f("pending", "high"), _f("confirmed", "high")]
    with_dismissed = live + [_f("dismissed", "high"), _f("dismissed", "high")]
    assert _risk_score(active_findings(with_dismissed)) == _risk_score(live)


def test_missing_status_is_treated_as_active():
    # A finding with no review status yet still counts (only an explicit dismissal drops it).
    assert active_findings([{"severity": "low"}]) == [{"severity": "low"}]
