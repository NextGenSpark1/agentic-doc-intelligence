"""What survives a re-run of analysis.

Adding a document and clicking Run Analysis again is the normal workflow, so re-running must
never throw away work a person did: an evidence decision, an owner, notes, or a reviewed
requirement. These tests use a small in-memory stand-in for the Supabase client that really
applies filters, so they assert on what ends up stored rather than on which calls were made.
"""
from unittest.mock import MagicMock

import pytest

from backend.apps.tendering import db
from backend.apps.tendering.pipeline import evidence_matching
from backend.apps.tendering.pipeline.extract_requirements import drop_already_present


# ------------------------------ in-memory client ------------------------------
class _DbError(Exception):
    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code


class _Query:
    def __init__(self, store, table):
        self.store, self.table = store, table
        self.op, self.payload, self.filters, self._limit = "select", None, [], None

    def select(self, *_a, **_k):
        self.op = "select"
        return self

    def insert(self, row):
        self.op, self.payload = "insert", row
        return self

    def update(self, patch):
        self.op, self.payload = "update", patch
        return self

    def upsert(self, row, on_conflict=None):
        # Modelled on Postgres INSERT ... ON CONFLICT DO UPDATE: a clash on the conflict
        # columns overwrites the existing row. Without this, code that upserts would fail
        # against the fake, and a test could pass only because nothing got written.
        self.op, self.payload = "upsert", row
        self.conflict_keys = [k.strip() for k in (on_conflict or "").split(",") if k.strip()]
        return self

    def delete(self):
        self.op = "delete"
        return self

    def eq(self, column, value):
        self.filters.append(lambda r: str(r.get(column)) == str(value))
        return self

    def in_(self, column, values):
        allowed = {str(v) for v in values}
        self.filters.append(lambda r: str(r.get(column)) in allowed)
        return self

    def limit(self, n):
        self._limit = n
        return self

    def execute(self):
        failure = self.store.failures.get((self.table, self.op))
        if failure:
            message, code = failure
            raise _DbError(message, code=code)
        rows = self.store.rows(self.table)
        if self.op == "upsert":
            row = dict(self.payload)
            for existing in rows:
                if self.conflict_keys and all(
                    str(existing.get(k)) == str(row.get(k)) for k in self.conflict_keys
                ):
                    existing.update(row)
                    return MagicMock(data=[dict(existing)])
            row.setdefault("id", f"row-{len(rows) + 1}")
            rows.append(row)
            return MagicMock(data=[dict(row)])
        if self.op == "insert":
            row = dict(self.payload)
            if self.table == "evidence_links" and any(
                r["req_id"] == row["req_id"] and r["doc_id"] == row["doc_id"] for r in rows
            ):
                raise _DbError("duplicate key value violates unique constraint", code="23505")
            row.setdefault("id", f"row-{len(rows) + 1}")
            rows.append(row)
            return MagicMock(data=[dict(row)])
        matched = [r for r in rows if all(f(r) for f in self.filters)]
        if self.op == "select":
            return MagicMock(data=[dict(r) for r in matched[: self._limit or None]])
        if self.op == "update":
            for r in matched:
                r.update(self.payload)
            return MagicMock(data=[dict(r) for r in matched])
        gone = {id(r) for r in matched}
        self.store.tables[self.table] = [r for r in rows if id(r) not in gone]
        return MagicMock(data=[dict(r) for r in matched])


class _Store:
    def __init__(self, **tables):
        self.tables = {name: [dict(r) for r in rows] for name, rows in tables.items()}
        # (table, op) -> (message, postgres error code): makes that operation raise.
        self.failures: dict[tuple[str, str], tuple[str, str]] = {}

    def rows(self, table):
        return self.tables.setdefault(table, [])

    def table(self, name):
        return _Query(self, name)


@pytest.fixture
def store(monkeypatch):
    holder = {}

    def use(**tables):
        holder["store"] = _Store(**tables)
        monkeypatch.setattr(db, "get_client", lambda: holder["store"])
        return holder["store"]

    return use


def _link(status="pending", score=0.5, rationale="old reason", **extra):
    return {"id": "L1", "req_id": "R1", "doc_id": "D1", "score": score,
            "rationale": rationale, "matched_chunk_id": "c-old",
            "human_review_status": status, **extra}


def _proposal(**extra):
    return {"req_id": "R1", "doc_id": "D1", "workspace_id": "W1", "org_id": "org-1",
            "score": 0.9, "rationale": "new reason", "matched_chunk_id": "c-new",
            "source": "llm", "human_review_status": "pending", **extra}


# ------------------------- saving AI evidence proposals -------------------------
def test_a_new_proposal_is_saved(store):
    s = store(evidence_links=[])

    assert db.upsert_evidence_link(_proposal()) is not None
    assert len(s.rows("evidence_links")) == 1


@pytest.mark.parametrize("decision", ["confirmed", "dismissed"])
def test_a_persons_decision_survives_re_running_analysis(store, decision):
    """The core fix: re-proposing a link must not reset a person's confirm or dismiss."""
    s = store(evidence_links=[_link(status=decision)])

    assert db.upsert_evidence_link(_proposal()) is None

    row = s.rows("evidence_links")[0]
    assert row["human_review_status"] == decision
    assert row["score"] == 0.5 and row["rationale"] == "old reason"


def test_a_still_pending_proposal_gets_the_fresh_ai_reasoning(store):
    s = store(evidence_links=[_link(status="pending")])

    assert db.upsert_evidence_link(_proposal()) is not None

    row = s.rows("evidence_links")[0]
    assert (row["score"], row["rationale"], row["matched_chunk_id"]) == (0.9, "new reason", "c-new")
    assert row["human_review_status"] == "pending"
    assert len(s.rows("evidence_links")) == 1


def test_a_database_error_is_raised_not_hidden(store):
    """Previously every exception became None and was counted as "skipped", so a broken
    insert looked exactly like "no matches found"."""
    s = store(evidence_links=[])
    s.failures[("evidence_links", "insert")] = ("connection reset by peer", "08006")

    with pytest.raises(_DbError, match="connection reset"):
        db.upsert_evidence_link(_proposal())


def test_losing_an_insert_race_is_not_an_error(store):
    """Two runs can check, find nothing, and both insert. The second insert hits the unique
    constraint; that is the normal end of a race and the first run's row stands."""
    s = store(evidence_links=[])
    s.failures[("evidence_links", "insert")] = (
        "duplicate key value violates unique constraint", "23505")

    assert db.upsert_evidence_link(_proposal()) is None


# ----------------------- which requirements a re-run deletes -----------------------
def _req(req_id, status="unchecked", owner="", notes="", workspace="W1"):
    return {"req_id": req_id, "workspace_id": workspace, "status": status,
            "owner": owner, "notes": notes}


def _remaining(s):
    return {r["req_id"] for r in s.rows("workspace_requirements")}


def test_untouched_requirements_are_refreshed(store):
    s = store(workspace_requirements=[_req("R1")], evidence_links=[])

    db.delete_workspace_requirements("W1", pending_only=True)

    assert _remaining(s) == set()


@pytest.mark.parametrize("status", ["met", "gap", "partial"])
def test_reviewed_requirements_are_kept(store, status):
    s = store(workspace_requirements=[_req("R1", status=status)], evidence_links=[])

    db.delete_workspace_requirements("W1", pending_only=True)

    assert _remaining(s) == {"R1"}


@pytest.mark.parametrize("field", ["owner", "notes"])
def test_an_unchecked_requirement_with_a_persons_input_is_kept(store, field):
    """Assigning an owner or writing notes is work; re-running used to delete it."""
    s = store(workspace_requirements=[_req("R1", **{field: "Aisha"})], evidence_links=[])

    db.delete_workspace_requirements("W1", pending_only=True)

    assert _remaining(s) == {"R1"}


@pytest.mark.parametrize("decision", ["confirmed", "dismissed"])
def test_an_unchecked_requirement_with_reviewed_evidence_is_kept(store, decision):
    """Evidence links cascade on delete, so deleting the requirement would erase the
    person's evidence decision along with it."""
    s = store(workspace_requirements=[_req("R1")],
              evidence_links=[_link(status=decision, workspace_id="W1")])

    db.delete_workspace_requirements("W1", pending_only=True)

    assert _remaining(s) == {"R1"}


def test_only_pending_evidence_does_not_protect_a_requirement(store):
    """A pending AI proposal is not a person's work, so the requirement can be refreshed."""
    s = store(workspace_requirements=[_req("R1")],
              evidence_links=[_link(status="pending", workspace_id="W1")])

    db.delete_workspace_requirements("W1", pending_only=True)

    assert _remaining(s) == set()


def test_whitespace_owner_or_notes_counts_as_empty(store):
    s = store(workspace_requirements=[_req("R1", owner="  ", notes="\n")], evidence_links=[])

    db.delete_workspace_requirements("W1", pending_only=True)

    assert _remaining(s) == set()


def test_other_workspaces_are_never_touched(store):
    s = store(workspace_requirements=[_req("R1"), _req("R2", workspace="W2")], evidence_links=[])

    db.delete_workspace_requirements("W1", pending_only=True)

    assert _remaining(s) == {"R2"}


def test_a_mixed_workspace_keeps_exactly_the_worked_on_requirements(store):
    s = store(
        workspace_requirements=[
            _req("fresh"),
            _req("reviewed", status="met"),
            _req("owned", owner="Aisha"),
            _req("evidenced"),
        ],
        evidence_links=[{**_link(status="confirmed", workspace_id="W1"), "req_id": "evidenced"}],
    )

    db.delete_workspace_requirements("W1", pending_only=True)

    assert _remaining(s) == {"reviewed", "owned", "evidenced"}


def test_deletes_are_batched_for_large_workspaces(store):
    """Hundreds of ids in one IN (...) can exceed PostgREST's URL-length limit."""
    s = store(workspace_requirements=[_req(f"R{i}") for i in range(250)], evidence_links=[])

    db.delete_workspace_requirements("W1", pending_only=True)

    assert _remaining(s) == set()


def test_pending_only_false_still_clears_the_whole_workspace(store):
    s = store(workspace_requirements=[_req("R1", status="met"), _req("R2", owner="Aisha")],
              evidence_links=[])

    db.delete_workspace_requirements("W1", pending_only=False)

    assert _remaining(s) == set()


# ------------------------ not re-adding existing requirements ------------------------
def _extracted(description, doc="DOC-1", page=3):
    return {"description": description, "source_doc": doc, "source_page": page}


def test_a_requirement_already_in_the_workspace_is_not_inserted_again():
    """The duplication bug: kept requirements were inserted again on every run."""
    stored = {"req_id": "R1", "description": "Bidder shall hold a CIDB G7 licence",
              "source_doc": "DOC-1", "source_page": 3, "status": "met"}
    present = {db.requirement_hash(stored)}

    fresh, dropped = drop_already_present(
        [_extracted("Bidder shall hold a CIDB G7 licence")], present)

    assert fresh == [] and dropped == 1


def test_matching_ignores_case_and_surrounding_whitespace():
    present = {db.requirement_hash(_extracted("Bidder shall hold a CIDB G7 licence"))}

    fresh, dropped = drop_already_present(
        [_extracted("  BIDDER SHALL HOLD A CIDB G7 LICENCE  ")], present)

    assert fresh == [] and dropped == 1


def test_the_same_text_on_a_different_page_is_a_different_requirement():
    present = {db.requirement_hash(_extracted("Submit three copies", page=3))}

    fresh, dropped = drop_already_present([_extracted("Submit three copies", page=9)], present)

    assert len(fresh) == 1 and dropped == 0


def test_a_new_requirement_is_kept_and_remembered():
    present: set[str] = set()

    fresh, dropped = drop_already_present(
        [_extracted("Submit a bid bond"), _extracted("Submit a bid bond")], present)

    assert len(fresh) == 1 and dropped == 1
    assert db.requirement_hash(_extracted("Submit a bid bond")) in present


# ------------------------- matching reports what happened -------------------------
def _run_match(monkeypatch, upsert):
    from backend.core import llm, llm_reasoning

    audits: list[dict] = []
    requirements = [{"req_id": f"R{i}", "description": f"requirement {i}"} for i in (1, 2)]
    monkeypatch.setattr(db, "get_tendering_workspace", lambda wid: {"id": wid, "org_id": "org-1"})
    monkeypatch.setattr(db, "list_workspace_requirements_raw", lambda wid: requirements)
    monkeypatch.setattr(llm, "embed", lambda texts: [[0.1, 0.2]])
    monkeypatch.setattr(db, "match_supplier_docs", lambda *a, **k: [
        {"supplier_document_id": "SUP-1", "library_doc_id": "D1", "chunk_id": "c1",
         "similarity": 0.9, "title": "CIDB certificate", "text": "Grade G7"}])
    monkeypatch.setattr(llm_reasoning, "ask", lambda *a, **k: {"matches": [
        {"supplier_document_id": "SUP-1", "match_score": 0.9, "rationale": "Grade G7 matches"}]})
    monkeypatch.setattr(db, "upsert_evidence_link", upsert)
    monkeypatch.setattr(db, "write_workspace_audit",
                        lambda wid, actor, action, detail=None: audits.append(detail))
    return evidence_matching.match("W1"), audits


def test_a_save_error_is_reported_and_the_run_continues(monkeypatch):
    calls = []

    def upsert(data):
        calls.append(data["req_id"])
        if data["req_id"] == "R1":
            raise RuntimeError("column \"score\" does not exist")
        return {"id": "L2"}

    result, audits = _run_match(monkeypatch, upsert)

    assert calls == ["R1", "R2"], "one failed save must not stop the others"
    assert result["save_errors"] == 1
    assert result["proposed"] == 1
    assert "score" in result["first_save_error"]
    assert audits[-1]["save_errors"] == 1


def test_a_persons_decision_is_counted_as_left_unchanged_not_skipped(monkeypatch):
    result, _ = _run_match(monkeypatch, lambda data: None)

    assert result["left_unchanged"] == 2
    assert result["skipped"] == 0
    assert result["save_errors"] == 0


# ---------------------------- a full re-run, end to end ----------------------------
SENTENCE = "The bidder shall hold a valid CIDB G7 licence."


def _rerun(monkeypatch, store, existing_requirements):
    """Run extract() against the in-memory store with the LLM unavailable (rule pass only)."""
    from backend.core import llm_reasoning
    from backend.apps.tendering.pipeline import extract_requirements

    s = store(workspace_requirements=existing_requirements, evidence_links=[])
    monkeypatch.setattr(db, "get_tendering_workspace", lambda wid: {"id": wid, "org_id": "org-1"})
    monkeypatch.setattr(db, "list_core_documents_for_workspace", lambda wid: [
        {"document_id": "DOC-1", "extraction_status": "done", "filename": "itt.pdf"}])
    monkeypatch.setattr(db, "list_chunks", lambda doc_id: [
        {"chunk_id": "c1", "text": SENTENCE, "page": 1}])
    monkeypatch.setattr(db, "write_workspace_audit", lambda *a, **k: None)
    monkeypatch.setattr(llm_reasoning, "ask", lambda *a, **k: None)
    return extract_requirements.extract("W1"), s


def _stored(description=SENTENCE, **fields):
    return {"req_id": "R-old", "workspace_id": "W1", "description": description,
            "source_doc": "DOC-1", "source_page": 1, "owner": "", "notes": "",
            "status": "unchecked", **fields}


def test_rerun_does_not_duplicate_a_reviewed_requirement(monkeypatch, store):
    """The live bug: a requirement someone marked met was inserted again on every run."""
    result, s = _rerun(monkeypatch, store, [_stored(status="met")])

    requirements = s.rows("workspace_requirements")
    assert len(requirements) == 1, "the reviewed requirement was duplicated"
    assert requirements[0]["req_id"] == "R-old"
    assert requirements[0]["status"] == "met"
    assert result["already_present"] == 1 and result["requirements_inserted"] == 0


def test_rerun_keeps_an_owner_on_an_unchecked_requirement(monkeypatch, store):
    result, s = _rerun(monkeypatch, store, [_stored(owner="Aisha")])

    requirements = s.rows("workspace_requirements")
    assert [r["req_id"] for r in requirements] == ["R-old"]
    assert requirements[0]["owner"] == "Aisha"


def test_rerun_refreshes_an_untouched_requirement_rather_than_losing_it(monkeypatch, store):
    """Guards the ordering inside extract(): the existing-requirement list must be read AFTER
    the cleanup. Read before it, the refreshed requirement would count as already present,
    be skipped on insert, and silently vanish."""
    result, s = _rerun(monkeypatch, store, [_stored()])

    requirements = s.rows("workspace_requirements")
    assert len(requirements) == 1, "an untouched requirement disappeared on re-run"
    assert requirements[0]["req_id"] != "R-old"      # replaced by a fresh extraction
    assert result["requirements_inserted"] == 1 and result["already_present"] == 0
