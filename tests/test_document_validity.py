"""Reading expiry dates off documents, and showing them where evidence is approved.

Expiry dates only ever came from the upload form, so a certificate uploaded without one looked
permanent and every expiry rule in the platform quietly did nothing. These tests use the real
lines from the NexaGrid test pack's certificates.

The second half covers the other end of the same problem: the matcher works out whether a
document has lapsed and then drops that before saving, so the evidence card — the one screen
where a person approves evidence — could not say "this expired in August".
"""
from datetime import date

import pytest

from backend.apps.tendering.db import annotate_link_validity
from backend.apps.tendering.validity import (
    SOURCE_DOCUMENT,
    expires_before,
    extract_dates,
    is_expired,
    parse_date,
)

TODAY = date(2026, 9, 25)
CLOSING = "2026-11-30"

CIDB_TEXT = """Company: NexaGrid Systems Sdn. Bhd.
Mock CIDB Registration No.: CIDB-G7-WP-26-TEST-0147
Grade: G7
Effective Date: 21 November 2025
Expiry Date: 20 November 2026
Status as at 10 September 2026: ACTIVE"""

ISO_TEXT = """Certificate Number: NG-QMS-2024-0017-TEST
Initial Certification Date: 15 January 2024
Issue Date: 15 January 2024
Expiry Date: 14 January 2027"""

INSURANCE_TEXT = """Policy Number: PL-TEST-2025-88721
Limit of Indemnity: RM 5,000,000 per occurrence
Policy Period: 1 September 2025 to 31 August 2026
Status as at 10 September 2026: EXPIRED"""

CV_TEXT = """Name: Farah Nadhirah Ismail
Education: Bachelor of Engineering (Mechatronics), 2015
Professional Experience: 9 years relevant experience
2019-Present - NexaGrid Systems Sdn. Bhd."""


# ── reading the dates ──────────────────────────────────────────────────────────

def test_the_cidb_certificate_gives_up_both_its_dates():
    assert extract_dates(CIDB_TEXT) == {"issue_date": "2025-11-21", "expiry_date": "2026-11-20"}


def test_an_assessment_date_is_not_mistaken_for_the_expiry():
    """The ISO certificate carries three dates; only the labelled expiry is the expiry."""
    assert extract_dates(ISO_TEXT)["expiry_date"] == "2027-01-14"


def test_a_policy_period_ends_at_the_expiry():
    """The insurance certificate states a range rather than an "Expiry Date:" line."""
    assert extract_dates(INSURANCE_TEXT)["expiry_date"] == "2026-08-31"


def test_a_cv_full_of_years_yields_nothing():
    """Unlabelled dates are not evidence of anything — guessing here invents blockers."""
    assert extract_dates(CV_TEXT) == {}


@pytest.mark.parametrize("line,expected", [
    ("Expiry Date: 2026-11-20", "2026-11-20"),
    ("Valid until 14 January 2027", "2027-01-14"),
    ("Expires on November 20, 2026", "2026-11-20"),
    ("Expiry date: 20/11/2026", "2026-11-20"),
])
def test_the_common_ways_a_date_is_written(line, expected):
    assert extract_dates(line)["expiry_date"] == expected


@pytest.mark.parametrize("text", ["", "   ", "Expiry Date: not stated", "Expiry Date: 31/02/2026"])
def test_nothing_readable_yields_nothing(text):
    """Including 31 February — a date that parses as digits but is not a date."""
    assert extract_dates(text) == {}


# ── has it lapsed ──────────────────────────────────────────────────────────────

def test_expiry_is_judged_against_today_and_the_closing_date():
    cidb = {"expiry_date": "2026-11-20"}

    assert is_expired(cidb, TODAY) is False                       # still valid now
    assert expires_before(cidb, parse_date(CLOSING)) is True       # but not at submission


def test_a_document_with_no_expiry_never_reads_as_lapsed():
    assert is_expired({"expiry_date": None}, TODAY) is False
    assert expires_before({"expiry_date": None}, parse_date(CLOSING)) is False


def test_no_closing_date_means_nothing_expires_early():
    assert expires_before({"expiry_date": "2026-11-20"}, None) is False


# ── the evidence card ──────────────────────────────────────────────────────────

def _links():
    return [{"id": "L1", "req_id": "E2", "doc_id": "CIDB", "human_review_status": "pending"},
            {"id": "L2", "req_id": "E9", "doc_id": "INS", "human_review_status": "pending"}]


def _library():
    return [
        {"doc_id": "CIDB", "title": "CIDB G7 certificate", "expiry_date": "2026-11-20",
         "expiry_source": SOURCE_DOCUMENT},
        {"doc_id": "INS", "title": "Public liability insurance", "expiry_date": "2026-08-31",
         "expiry_source": "manual"},
    ]


def test_a_reviewer_can_see_the_certificate_lapses_before_submission():
    cidb, insurance = annotate_link_validity(_links(), _library(), CLOSING, TODAY)

    assert cidb["document_title"] == "CIDB G7 certificate"
    assert cidb["expires_before_closing"] is True
    assert cidb["is_expired"] is False


def test_an_already_expired_document_is_marked_expired_not_expiring():
    _cidb, insurance = annotate_link_validity(_links(), _library(), CLOSING, TODAY)

    assert insurance["is_expired"] is True
    assert insurance["expires_before_closing"] is False


def test_the_card_says_whether_the_date_was_read_or_typed():
    """A date the platform read off the document still needs a person to ratify it."""
    cidb, insurance = annotate_link_validity(_links(), _library(), CLOSING, TODAY)

    assert cidb["expiry_source"] == SOURCE_DOCUMENT
    assert insurance["expiry_source"] == "manual"


def test_a_link_whose_document_is_missing_is_left_untouched():
    links = annotate_link_validity(
        [{"id": "L9", "doc_id": "GONE", "human_review_status": "pending"}], _library(), CLOSING,
        TODAY)

    assert "is_expired" not in links[0]


def test_a_document_with_no_expiry_reports_as_neither():
    library = [{"doc_id": "CIDB", "title": "CIDB G7 certificate", "expiry_date": None}]
    cidb = annotate_link_validity(_links()[:1], library, CLOSING, TODAY)[0]

    assert (cidb["is_expired"], cidb["expires_before_closing"]) == (False, False)
    assert cidb["expiry_date"] is None


# ── the vault step that fills the blanks ───────────────────────────────────────

@pytest.fixture
def backfill(monkeypatch):
    """Run the vault date backfill against fakes, capturing what it would write."""
    from backend.apps.tendering import db
    from backend.apps.tendering.pipeline import vault
    from backend.core import db_core

    writes: list[tuple] = []
    monkeypatch.setattr(db, "update_supplier_document",
                        lambda sid, patch: writes.append(("vault", sid, patch)))
    monkeypatch.setattr(db, "update_library_document",
                        lambda doc_id, patch: writes.append(("library", doc_id, patch)))
    monkeypatch.setattr(db_core, "write_audit",
                        lambda case_id, actor, action, detail=None: writes.append(("audit", action, detail)))
    return vault, writes


def _document(**overrides):
    document = {"supplier_document_id": "SUP-1", "org_id": "org-1", "library_doc_id": "LIB-1",
                "title": "CIDB G7 certificate", "expiry_date": None, "issue_date": None}
    document.update(overrides)
    return document


def test_a_blank_expiry_is_filled_from_the_document(backfill):
    vault, writes = backfill

    vault._backfill_dates(_document(), {"markdown": CIDB_TEXT}, "SUP-1", "org-1")

    vault_write = next(w for w in writes if w[0] == "vault")
    assert vault_write[2]["expiry_date"] == "2026-11-20"
    assert vault_write[2]["expiry_source"] == SOURCE_DOCUMENT


def test_both_tables_are_kept_in_step(backfill):
    """Matching reads the vault row, the library page and readiness read the library row."""
    vault, writes = backfill

    vault._backfill_dates(_document(), {"markdown": CIDB_TEXT}, "SUP-1", "org-1")

    assert {w[0] for w in writes} == {"vault", "library", "audit"}
    assert next(w for w in writes if w[0] == "library")[2]["expiry_date"] == "2026-11-20"


def test_a_date_a_person_entered_is_never_overwritten(backfill):
    vault, writes = backfill

    vault._backfill_dates(_document(expiry_date="2027-01-01"), {"markdown": CIDB_TEXT},
                          "SUP-1", "org-1")

    vault_write = next(w for w in writes if w[0] == "vault")
    assert "expiry_date" not in vault_write[2]      # only the blank issue_date was filled
    assert vault_write[2]["issue_date"] == "2025-11-21"


def test_a_document_with_no_readable_dates_writes_nothing(backfill):
    vault, writes = backfill

    vault._backfill_dates(_document(), {"markdown": CV_TEXT}, "SUP-1", "org-1")

    assert writes == []


def test_the_chunks_are_used_when_there_is_no_markdown(backfill):
    vault, writes = backfill

    vault._backfill_dates(_document(), {"chunks": [{"text": CIDB_TEXT}]}, "SUP-1", "org-1")

    assert next(w for w in writes if w[0] == "vault")[2]["expiry_date"] == "2026-11-20"


def test_what_was_read_is_audited(backfill):
    """Someone has to be able to see where a date came from."""
    vault, writes = backfill

    vault._backfill_dates(_document(), {"markdown": CIDB_TEXT}, "SUP-1", "org-1")

    action, detail = next((w[1], w[2]) for w in writes if w[0] == "audit")
    assert action == "vault_dates_read_from_document"
    assert detail["expiry_date"] == "2026-11-20"
    assert detail["title"] == "CIDB G7 certificate"


def test_extraction_actually_runs_the_backfill(monkeypatch):
    """The wiring, not just the helper: a vault document being extracted must come out with its
    dates filled. Tested through process_supplier_document because the step is one line in it,
    and a one-line step is exactly what gets dropped in a refactor."""
    from backend.apps.tendering import db
    from backend.apps.tendering.pipeline import vault
    from backend.core import ade_client, db_core

    written: list[dict] = []
    monkeypatch.setattr(db, "get_supplier_document",
                        lambda sid: _document(storage_path="general/1726-cidb.pdf"))
    monkeypatch.setattr(db, "update_supplier_document",
                        lambda sid, patch: written.append(patch))
    monkeypatch.setattr(db, "update_library_document", lambda doc_id, patch: None)
    monkeypatch.setattr(db_core, "write_audit", lambda *a, **k: None)
    monkeypatch.setattr(vault, "_index_vault_chunks", lambda *a, **k: None)
    monkeypatch.setattr(ade_client, "parse_document",
                        lambda content: {"markdown": CIDB_TEXT, "chunks": [], "page_count": 2})

    class _Bucket:
        def download(self, _path):
            return b"%PDF-fake"

    class _Storage:
        def from_(self, _bucket):
            return _Bucket()

    monkeypatch.setattr(db_core, "get_client",
                        lambda: type("C", (), {"storage": _Storage()})())

    vault.process_supplier_document("SUP-1")

    dates = next(patch for patch in written if "expiry_date" in patch)
    assert dates["expiry_date"] == "2026-11-20"
    assert dates["expiry_source"] == SOURCE_DOCUMENT


# ── layouts the parser actually produces ───────────────────────────────────────
# The CIDB certificate's expiry was missed in a real run while the insurance policy's was read.
# The parser reads a key-value block as a table and returns HTML with one cell per line, so the
# label and its date arrive on separate lines.

CIDB_AS_HTML_CELLS = (
    "<tr>\n<td>Effective Date:</td>\n<td>21 November 2025</td>\n</tr>\n"
    "<tr>\n<td>Expiry Date:</td>\n<td>20 November 2026</td>\n</tr>\n"
    "<tr>\n<td>Status as at 10 September 2026:</td>\n<td>ACTIVE</td>\n</tr>"
)


@pytest.mark.parametrize("text", [
    CIDB_AS_HTML_CELLS,
    "<table><tr><td>Expiry Date:</td><td>20 November 2026</td></tr></table>",
    "| Expiry Date | 20 November 2026 |",
    "Expiry Date:\n20 November 2026",
    "**Expiry Date:** 20 November 2026",
    "Expiry&nbsp;Date: 20&nbsp;November&nbsp;2026",
])
def test_the_expiry_is_read_however_the_parser_lays_it_out(text):
    assert extract_dates(text)["expiry_date"] == "2026-11-20"


def test_the_cidb_table_gives_up_both_dates():
    assert extract_dates(CIDB_AS_HTML_CELLS) == {"issue_date": "2025-11-21",
                                                 "expiry_date": "2026-11-20"}


def test_a_bare_label_does_not_borrow_a_date_from_a_labelled_row():
    """'Issue Date' standing alone must not take the expiry printed on the next row."""
    assert extract_dates("Issue Date\nExpiry Date: 20 November 2026") == {
        "expiry_date": "2026-11-20"}


def test_a_bare_label_does_not_borrow_a_status_date():
    assert extract_dates("Expiry Date\nStatus as at 10 September 2026: ACTIVE") == {}
