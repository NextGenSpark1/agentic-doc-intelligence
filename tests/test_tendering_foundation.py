"""Tendering foundation — schemas, classify labels, dedup, and the core product dispatch.

Pure logic only: no Supabase, no ADE, no LLM. The Rule 2 and Rule 3 tests matter most —
they check that grounding and human-review are structural properties rather than prompt
instructions the model could ignore.
"""
import pytest
from pydantic import ValidationError

from backend.apps.tendering import classify as tender_classify
from backend.apps.tendering.schemas import (
    REQUIREMENT_CATEGORIES,
    BillOfQuantities,
    RequirementRecord,
    TenderNotice,
    schema_for_case_type,
)


# ------------------------- extraction schemas -------------------------
def test_tender_case_type_resolves_to_tender_notice():
    assert schema_for_case_type("tender") is TenderNotice


@pytest.mark.parametrize("case_type,expected", [
    ("boq", BillOfQuantities),
    ("BOQ", BillOfQuantities),
    ("bill of quantities", BillOfQuantities),
    ("bill-of-quantities", BillOfQuantities),
])
def test_schema_resolution_normalises_case_type(case_type, expected):
    assert schema_for_case_type(case_type) is expected


def test_unknown_case_type_falls_back_to_tender_notice():
    assert schema_for_case_type("something_unmapped") is TenderNotice
    assert schema_for_case_type("") is TenderNotice
    assert schema_for_case_type(None) is TenderNotice


def test_tender_notice_tolerates_missing_fields():
    """ADE routinely returns partial extractions; the schema must not reject them."""
    notice = TenderNotice(tender_title="Supply of Network Equipment")
    assert notice.tender_title == "Supply of Network Equipment"
    assert notice.eligibility_criteria == []
    assert notice.closing_date is None


def test_schema_field_descriptions_are_ascii():
    """Descriptions are sent to ADE as extraction instructions — stray non-English text
    would silently steer the model."""
    for model in (TenderNotice, BillOfQuantities):
        for name, field in model.model_fields.items():
            desc = field.description or ""
            assert desc.isascii(), f"{model.__name__}.{name} description is not ASCII: {desc!r}"


# ------------------------- classification labels -------------------------
def test_tender_labels_do_not_collide_with_investigation_labels():
    """Both products feed their own label set into the same core engine. A shared label
    would make a document's type ambiguous across products."""
    from backend.apps.investigation import classify as inv_classify

    overlap = set(tender_classify.KNOWN_TYPES) & set(inv_classify.KNOWN_TYPES)
    assert overlap == {"other"}, f"unexpected label overlap: {overlap}"


def test_every_heuristic_maps_to_a_known_type():
    unknown = set(tender_classify._HEURISTICS) - set(tender_classify.KNOWN_TYPES)
    assert not unknown, f"heuristics reference undeclared labels: {unknown}"


@pytest.mark.parametrize("text,expected", [
    ("INVITATION TO TENDER for road resurfacing works", "tender_notice"),
    ("BILL OF QUANTITIES\nItem  Description  Quantity  Unit Rate", "bill_of_quantities"),
    ("ADDENDUM NO. 2 — the closing date is extended", "addendum"),
    ("TERMS OF REFERENCE\n1. Scope of work", "terms_of_reference"),
])
def test_heuristic_classifies_common_tender_documents(text, expected):
    assert tender_classify.heuristic(text) == expected


# --------------------- Rule 2: grounding is structural ---------------------
def test_llm_requirement_without_source_document_is_rejected():
    with pytest.raises(ValidationError, match="source_document_id"):
        RequirementRecord(description="Bidder must hold a valid CIDB G7 licence", source="llm")


def test_llm_requirement_without_page_is_rejected():
    with pytest.raises(ValidationError, match="source_page"):
        RequirementRecord(
            description="Bid bond of 2.5% required",
            source="llm",
            source_document_id="doc-1",
        )


def test_grounded_llm_requirement_is_accepted():
    req = RequirementRecord(
        description="Bid bond of 2.5% of tender sum required",
        category="financial",
        is_mandatory=True,
        source="llm",
        source_document_id="doc-1",
        source_page=12,
        source_clause="4.3.1",
        source_text="A bid bond equal to 2.5% of the tender sum shall be submitted.",
        confidence=0.88,
    )
    assert req.is_mandatory
    assert req.source_page == 12


def test_manual_requirement_is_exempt_from_grounding():
    """A human is the provenance, so there is no document to cite."""
    req = RequirementRecord(description="Confirm insurance renewal before submission", source="manual")
    assert req.source == "manual"
    assert req.source_document_id is None


def test_empty_description_is_rejected():
    with pytest.raises(ValidationError, match="description must not be empty"):
        RequirementRecord(description="   ", source="manual")


def test_confidence_outside_zero_to_one_is_rejected():
    with pytest.raises(ValidationError, match="confidence"):
        RequirementRecord(
            description="Valid requirement", source="llm",
            source_document_id="doc-1", source_page=3, confidence=1.7,
        )


def test_unknown_category_is_rejected():
    with pytest.raises(ValidationError):
        RequirementRecord(
            description="Valid requirement", category="invented_category",
            source="llm", source_document_id="doc-1", source_page=3,
        )


def test_declared_categories_match_the_literal_type():
    """REQUIREMENT_CATEGORIES drives prompts and the compliance matrix; the Literal drives
    validation. They must not drift apart."""
    for category in REQUIREMENT_CATEGORIES:
        req = RequirementRecord(description="x", category=category, source="manual")
        assert req.category == category


# ------------------------- requirement dedup -------------------------
def test_requirement_hash_is_stable_and_case_insensitive():
    from backend.apps.tendering.db import requirement_hash

    a = {"description": "Bid bond of 2.5% required", "category": "financial", "source_document_id": "d1"}
    b = {"description": "  BID BOND OF 2.5% REQUIRED  ", "category": "Financial", "source_document_id": "d1"}
    assert requirement_hash(a) == requirement_hash(b)


def test_same_text_in_different_categories_is_not_deduped():
    """The same sentence can be both a submission instruction and a technical obligation."""
    from backend.apps.tendering.db import requirement_hash

    base = {"description": "Submit three signed copies", "source_document_id": "d1"}
    assert (
        requirement_hash({**base, "category": "submission_instruction"})
        != requirement_hash({**base, "category": "technical"})
    )


def test_same_text_from_different_documents_is_not_deduped():
    from backend.apps.tendering.db import requirement_hash

    base = {"description": "Provide audited accounts", "category": "financial"}
    assert (
        requirement_hash({**base, "source_document_id": "d1"})
        != requirement_hash({**base, "source_document_id": "d2"})
    )


# ------------------- core stays product-agnostic -------------------
def test_only_main_imports_tendering_and_only_to_mount_its_router():
    """Tenders are not cases: no core *logic* module may reach into the tender app.

    `main.py` is the one exception, and only to mount the product router at the bottom — the
    same way it mounts investigation's. The earlier draft had core dispatch on case_type inside
    the extract route; the settled model gives tenders their own router and document routes, so
    that coupling is gone and must not creep back.
    """
    import ast
    from pathlib import Path

    import backend.core as core_pkg

    # Parse rather than grep: core.access legitimately *mentions* the tender guard in a
    # docstring to explain why the access rules are workspace-generic. A docstring is not a
    # dependency; an import is.
    for path in Path(core_pkg.__file__).parent.glob("*.py"):
        imported: list[str] = []
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("backend.apps.tendering"):
                imported.append(node.module or "")
            elif isinstance(node, ast.Import):
                imported += [a.name for a in node.names if a.name.startswith("backend.apps.tendering")]

        if path.name == "main.py":
            assert imported == ["backend.apps.tendering.routes"], (
                f"main.py may only import the tender router, got {imported}")
        else:
            assert not imported, f"{path.name} imports the tendering app: {imported}"


def test_investigation_pipeline_is_still_wired_into_core():
    from pathlib import Path

    import backend.core as core_pkg

    main = (Path(core_pkg.__file__).parent / "main.py").read_text(encoding="utf-8")
    assert "apps.investigation" in main


# ------------------------- router wiring -------------------------
def _mounted_paths() -> set[str]:
    """Paths the app actually serves.

    Read from the OpenAPI schema rather than `app.routes` — newer FastAPI wraps included
    routers in objects that carry no `.path`, so walking `app.routes` silently misses every
    route mounted from a product router.
    """
    from backend.core.main import app

    return set(app.openapi()["paths"])


def test_tender_routes_are_mounted_on_the_core_app():
    paths = _mounted_paths()
    assert "/tenders" in paths
    assert "/tenders/{tender_id}/requirements" in paths
    assert "/tenders/{tender_id}/compliance-matrix" in paths
    # Tenders own their document routes — they do not borrow core's /cases/* ones.
    assert "/tenders/{tender_id}/documents" in paths
    assert "/tenders/{tender_id}/documents/{document_id}/extract" in paths
    # The org-level vault.
    assert "/vault/documents" in paths
    # Rule 3: bid decision and evidence review are human-only endpoints.
    assert "/tenders/{tender_id}/bid-decision" in paths
    assert "/evidence/{evidence_link_id}/review" in paths


def test_investigation_routes_still_mounted():
    """The tender work must not disturb the existing product."""
    paths = _mounted_paths()
    assert "/cases/{case_id}/chat" in paths
    assert "/cases/{case_id}/analysis" in paths
