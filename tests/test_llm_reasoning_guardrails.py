"""Guardrails on the LLM case-reasoning passes.

Every LLM pass (entity alias-merge, relationships, timeline flags, findings) must ground its
output in data we actually sent — a document_id, event, or entity name it invents rather than
cites gets dropped before it is ever treated as real. `llm_reasoning.ask` is monkeypatched so
these tests need no network access or API key.
"""
from unittest.mock import patch

from backend.apps.investigation.pipeline import build_relationships, detect_anomalies, reconstruct_timeline, resolve_entities

_ASK = "backend.core.llm_reasoning.ask"


def test_relationship_citing_unknown_document_is_dropped(sample_extractions):
    fake = {"relationships": [
        {"source_name": "Nova Build", "target_name": "Apex Supplies",
         "relationship_type": "introduced_by", "evidence_quote": "made up",
         "document_id": "not-a-real-doc", "confidence": 0.8},
    ]}
    with patch(_ASK, return_value=fake):
        edges = build_relationships._llm_relationships(sample_extractions, "case-1")
    assert edges == []


def test_relationship_grounded_in_real_document_is_kept(sample_extractions):
    fake = {"relationships": [
        {"source_name": "Nova Build", "target_name": "Apex Supplies",
         "relationship_type": "introduced_by", "evidence_quote": "quote", "document_id": "d1",
         "confidence": 0.8},
    ]}
    with patch(_ASK, return_value=fake):
        edges = build_relationships._llm_relationships(sample_extractions, "case-1")
    assert len(edges) == 1
    assert edges[0]["source"] == "llm"
    assert edges[0]["evidence"]["confidence"] == 0.8


def test_timeline_flag_citing_unknown_event_is_dropped():
    events = [
        {"event_date": "2024-01-01", "label": "Payment", "document_id": "d1"},
        {"event_date": "2024-01-05", "label": "Approval", "document_id": "d2"},
    ]
    fake = {"flags": [{"event_date": "1999-01-01", "document_id": "d1", "reasoning": "made up"}]}
    with patch(_ASK, return_value=fake):
        flags = reconstruct_timeline._llm_timeline_flags(events, "case-1")
    assert flags == []


def test_timeline_flag_grounded_in_real_event_is_kept():
    events = [
        {"event_date": "2024-01-01", "label": "Payment", "document_id": "d1"},
        {"event_date": "2024-01-05", "label": "Approval", "document_id": "d2"},
    ]
    fake = {"flags": [
        {"event_date": "2024-01-01", "document_id": "d1", "reasoning": "predates the approval"},
    ]}
    with patch(_ASK, return_value=fake):
        flags = reconstruct_timeline._llm_timeline_flags(events, "case-1")
    assert len(flags) == 1
    assert flags[0]["source"] == "llm"


def test_entity_merge_with_unknown_member_does_not_merge():
    seen = {
        "person:jane tan": {"type": "person", "display": "Jane Tan", "docs": {"d1"}},
        "person:john lee": {"type": "person", "display": "John Lee", "docs": {"d2"}},
    }
    fake = {"clusters": [
        {"canonical_name": "Jane Tan", "entity_type": "person",
         "members": ["Jane Tan", "Someone We Never Sent"], "confidence": 0.9},
    ]}
    with patch(_ASK, return_value=fake):
        merged = resolve_entities._apply_llm_merge(seen, "case-1")
    assert len(merged) == 2  # only one grounded member — not enough to justify a merge


def test_entity_merge_with_two_grounded_members_merges():
    seen = {
        "person:jane tan": {"type": "person", "display": "Jane Tan", "docs": {"d1"}},
        "person:j tan": {"type": "person", "display": "J. Tan", "docs": {"d2"}},
    }
    fake = {"clusters": [
        {"canonical_name": "Jane Tan", "entity_type": "person",
         "members": ["Jane Tan", "J. Tan"], "confidence": 0.9},
    ]}
    with patch(_ASK, return_value=fake):
        merged = resolve_entities._apply_llm_merge(seen, "case-1")
    assert len(merged) == 1
    rec = next(iter(merged.values()))
    assert rec["display"] == "Jane Tan"
    assert rec["aliases"] == ["J. Tan"]
    assert rec["docs"] == {"d1", "d2"}
    assert rec["source"] == "llm"


def test_finding_citing_unknown_document_is_dropped(sample_extractions):
    fake = {"findings": [
        {"finding_type": "circular_payment", "severity": "high", "confidence": 0.8,
         "statement": "made up finding", "supporting_document_ids": ["not-a-real-doc"]},
    ]}
    with patch(_ASK, return_value=fake), \
         patch("backend.apps.investigation.db.list_entities", return_value=[]), \
         patch("backend.apps.investigation.db.list_relationships", return_value=[]), \
         patch("backend.apps.investigation.db.get_client") as mock_client:
        mock_client.return_value.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
        findings = detect_anomalies._llm_findings("case-1", sample_extractions)
    assert findings == []


def test_finding_grounded_in_real_document_is_kept(sample_extractions):
    fake = {"findings": [
        {"finding_type": "circular_payment", "severity": "high", "confidence": 0.8,
         "statement": "real finding", "supporting_document_ids": ["d1", "not-a-real-doc"]},
    ]}
    with patch(_ASK, return_value=fake), \
         patch("backend.apps.investigation.db.list_entities", return_value=[]), \
         patch("backend.apps.investigation.db.list_relationships", return_value=[]), \
         patch("backend.apps.investigation.db.get_client") as mock_client:
        mock_client.return_value.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
        findings = detect_anomalies._llm_findings("case-1", sample_extractions)
    assert len(findings) == 1
    assert findings[0]["source"] == "llm"
    assert findings[0]["supporting_document_ids"] == ["d1"]  # the invented doc id is stripped


# --------------------------- ask() failure contract ---------------------------
# The tests above monkeypatch `ask` itself, so they never exercise its own failure path.
# These do. `ask` is documented to never raise: every LLM-augmented stage relies on that to
# fall back to its rule-only results, so a raise here takes down a whole analysis run instead
# of degrading it. (Regression: the core/apps split left a `from .. import db` behind, which
# raised ImportError out of `ask` on every LLM failure.)
def test_ask_returns_none_instead_of_raising_when_the_llm_fails():
    from backend.core import llm_reasoning

    with patch("backend.core.llm.complete", side_effect=RuntimeError("provider down")), \
         patch("backend.core.db_core.write_audit"):
        assert llm_reasoning.ask("system prompt", {"a": 1}, "case-1") is None


def test_ask_audits_the_failure_so_a_dead_tier_is_diagnosable():
    from backend.core import llm_reasoning

    with patch("backend.core.llm.complete", side_effect=RuntimeError("provider down")), \
         patch("backend.core.db_core.write_audit") as audit:
        llm_reasoning.ask("system prompt", {}, "case-1")

    assert audit.called, "a failing LLM tier must be visible in the audit log"
    case_id, actor, action = audit.call_args[0][:3]
    assert (case_id, action) == ("case-1", "case_reasoning_failed")


def test_ask_still_returns_none_when_audit_logging_itself_fails():
    from backend.core import llm_reasoning

    with patch("backend.core.llm.complete", side_effect=RuntimeError("provider down")), \
         patch("backend.core.db_core.write_audit", side_effect=RuntimeError("db down")):
        assert llm_reasoning.ask("system prompt", {}, "case-1") is None


def test_ask_returns_none_on_unparseable_json():
    from backend.core import llm_reasoning

    with patch("backend.core.llm.complete", return_value="not json at all"), \
         patch("backend.core.db_core.write_audit"):
        assert llm_reasoning.ask("system prompt", {}, "case-1") is None
