"""Golden-set schema and loader.

A golden set is a YAML file of questions with human-verified ground truth: which chunks
*should* come back, and what the answer must (or must not) contain. It is the only thing
that turns "retrieval feels better" into a number.

**Validation is load-bearing, not paperwork.** A question whose `validated_by` is empty has
not been checked by a human, so its ground truth may be wrong — scoring against it measures
nothing. `run_eval` reports validated and unvalidated questions separately and only the
validated headline number is quotable (to a client, in a security review, in court).
See `goldens/README.md` for the authoring workflow.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

# Question kinds drive both scoring and reporting — a harness average that mixes simple
# lookups with multi-hop synthesis hides exactly the regressions worth catching.
QuestionKind = Literal["lookup", "multi_hop", "aggregation", "negative"]

_KINDS: set[str] = {"lookup", "multi_hop", "aggregation", "negative"}

GOLDENS_DIR = Path(__file__).parent / "goldens"


class GoldenSetError(ValueError):
    """Raised when a golden set is malformed — fail loudly rather than score against junk."""


@dataclass(frozen=True)
class GoldenQuestion:
    """One evaluated question with its human-verified ground truth."""

    id: str
    question: str
    case_id: str
    kind: QuestionKind = "lookup"

    # Ground truth for retrieval scoring. Chunk-level is precise; document-level is the
    # coarser fallback for when a human can point at the right PDF but not the exact chunk.
    relevant_chunk_ids: tuple[str, ...] = ()
    relevant_document_ids: tuple[str, ...] = ()

    # Ground truth for answer scoring (optional — retrieval metrics work without these).
    expected_answer: str = ""
    must_include: tuple[str, ...] = ()
    must_not_include: tuple[str, ...] = ()

    # Provenance. Empty `validated_by` means nobody has checked this — see module docstring.
    validated_by: str = ""
    validated_at: str = ""
    notes: str = ""

    @property
    def is_validated(self) -> bool:
        return bool(self.validated_by.strip())

    @property
    def has_ground_truth(self) -> bool:
        """Negative questions are scored on abstention, so they need no relevant chunks."""
        if self.kind == "negative":
            return True
        return bool(self.relevant_chunk_ids or self.relevant_document_ids)

    def relevant_ids(self, level: Literal["chunk", "document"]) -> frozenset[str]:
        if level == "chunk":
            return frozenset(self.relevant_chunk_ids)
        return frozenset(self.relevant_document_ids)


@dataclass
class GoldenSet:
    """All golden questions for one workspace type."""

    workspace_type: str
    questions: list[GoldenQuestion] = field(default_factory=list)
    source_path: Path | None = None

    def __len__(self) -> int:
        return len(self.questions)

    @property
    def validated(self) -> list[GoldenQuestion]:
        return [q for q in self.questions if q.is_validated]

    @property
    def unvalidated(self) -> list[GoldenQuestion]:
        return [q for q in self.questions if not q.is_validated]

    def by_kind(self, kind: str) -> list[GoldenQuestion]:
        return [q for q in self.questions if q.kind == kind]

    def filter(
        self,
        *,
        kinds: set[str] | None = None,
        validated_only: bool = False,
        case_id: str | None = None,
    ) -> GoldenSet:
        qs = self.questions
        if kinds:
            qs = [q for q in qs if q.kind in kinds]
        if validated_only:
            qs = [q for q in qs if q.is_validated]
        if case_id:
            qs = [q for q in qs if q.case_id == case_id]
        return GoldenSet(self.workspace_type, qs, self.source_path)


def _as_tuple(value: Any, field_name: str, qid: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (list, tuple)):
        return tuple(str(v) for v in value)
    raise GoldenSetError(f"question {qid!r}: {field_name} must be a string or list, got {type(value).__name__}")


def _parse_question(raw: Any, index: int, seen: set[str]) -> GoldenQuestion:
    if not isinstance(raw, dict):
        raise GoldenSetError(f"question #{index} must be a mapping, got {type(raw).__name__}")

    qid = str(raw.get("id") or "").strip()
    if not qid:
        raise GoldenSetError(f"question #{index} is missing an `id`")
    if qid in seen:
        raise GoldenSetError(f"duplicate question id {qid!r}")
    seen.add(qid)

    question = str(raw.get("question") or "").strip()
    if not question:
        raise GoldenSetError(f"question {qid!r} is missing `question` text")

    case_id = str(raw.get("case_id") or "").strip()
    if not case_id:
        raise GoldenSetError(f"question {qid!r} is missing `case_id`")

    kind = str(raw.get("kind") or "lookup").strip()
    if kind not in _KINDS:
        raise GoldenSetError(f"question {qid!r}: unknown kind {kind!r} (expected one of {sorted(_KINDS)})")

    parsed = GoldenQuestion(
        id=qid,
        question=question,
        case_id=case_id,
        kind=kind,  # type: ignore[arg-type]
        relevant_chunk_ids=_as_tuple(raw.get("relevant_chunk_ids"), "relevant_chunk_ids", qid),
        relevant_document_ids=_as_tuple(raw.get("relevant_document_ids"), "relevant_document_ids", qid),
        expected_answer=str(raw.get("expected_answer") or ""),
        must_include=_as_tuple(raw.get("must_include"), "must_include", qid),
        must_not_include=_as_tuple(raw.get("must_not_include"), "must_not_include", qid),
        validated_by=str(raw.get("validated_by") or ""),
        validated_at=str(raw.get("validated_at") or ""),
        notes=str(raw.get("notes") or ""),
    )

    # A non-negative question with no relevant ids can never score above zero — that is a
    # malformed entry, not a failing retriever, so refuse it at load time.
    if not parsed.has_ground_truth:
        raise GoldenSetError(
            f"question {qid!r} (kind={kind}) has no relevant_chunk_ids or relevant_document_ids; "
            "add ground truth or mark it kind: negative"
        )
    return parsed


def load_golden_set(path: str | Path) -> GoldenSet:
    """Parse and validate a golden-set YAML file."""
    path = Path(path)
    if not path.exists():
        raise GoldenSetError(f"golden set not found: {path}")

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise GoldenSetError(f"{path}: invalid YAML — {exc}") from exc

    if not isinstance(raw, dict):
        raise GoldenSetError(f"{path}: top level must be a mapping")

    workspace_type = str(raw.get("workspace_type") or "").strip()
    if not workspace_type:
        raise GoldenSetError(f"{path}: missing `workspace_type`")

    raw_questions = raw.get("questions") or []
    if not isinstance(raw_questions, list):
        raise GoldenSetError(f"{path}: `questions` must be a list")

    seen: set[str] = set()
    questions = [_parse_question(rq, i, seen) for i, rq in enumerate(raw_questions)]
    return GoldenSet(workspace_type=workspace_type, questions=questions, source_path=path)


def load_all(directory: str | Path = GOLDENS_DIR) -> dict[str, GoldenSet]:
    """Load every `*.yaml` golden set in a directory, keyed by workspace type."""
    directory = Path(directory)
    sets: dict[str, GoldenSet] = {}
    for path in sorted(directory.glob("*.yaml")):
        gs = load_golden_set(path)
        if gs.workspace_type in sets:
            raise GoldenSetError(f"two golden sets declare workspace_type {gs.workspace_type!r}")
        sets[gs.workspace_type] = gs
    return sets
