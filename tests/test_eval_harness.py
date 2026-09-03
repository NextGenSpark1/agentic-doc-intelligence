"""Tests for the retrieval eval harness.

The harness is the instrument every later retrieval claim rests on, so its arithmetic is
tested directly against hand-computed values. A quietly wrong metric would be worse than no
metric — it would make a regression look like an improvement.
"""
import json

import pytest

from backend.eval.goldens import GoldenQuestion, GoldenSet, GoldenSetError, load_golden_set
from backend.eval.metrics import (
    aggregate,
    is_abstention,
    score_answer,
    score_retrieval,
)
from backend.eval.report import format_console
from backend.eval.retrievers import FixtureRetriever, RetrievedChunk
from backend.eval.runner import compare, record_fixture, run_eval


def _q(qid="q1", kind="lookup", relevant=("c1",), validated=True, **kw):
    return GoldenQuestion(
        id=qid,
        question=kw.pop("question", "who paid whom?"),
        case_id="case-1",
        kind=kind,
        relevant_chunk_ids=tuple(relevant),
        validated_by="Investigator A" if validated else "",
        **kw,
    )


# ------------------------------- retrieval metrics -------------------------------
def test_perfect_retrieval_scores_one():
    m = score_retrieval(["c1", "c2"], ["c1", "c2"], k=8)
    assert m.recall_at_k == 1.0
    assert m.hit_at_k == 1.0
    assert m.mrr == 1.0
    assert m.ndcg_at_k == pytest.approx(1.0)
    assert m.first_relevant_rank == 1


def test_complete_miss_scores_zero():
    m = score_retrieval(["c9", "c8"], ["c1"], k=8)
    assert m.recall_at_k == 0.0
    assert m.hit_at_k == 0.0
    assert m.mrr == 0.0
    assert m.first_relevant_rank is None


def test_partial_recall_and_precision():
    # 1 of 2 relevant found, in a list of 4 retrieved.
    m = score_retrieval(["c9", "c1", "c8", "c7"], ["c1", "c2"], k=8)
    assert m.recall_at_k == 0.5
    assert m.precision_at_k == 0.25
    assert m.mrr == 0.5  # first relevant at rank 2
    assert m.first_relevant_rank == 2


def test_k_truncates_the_ranked_list():
    # The relevant chunk sits at rank 5, outside k=3.
    m = score_retrieval(["a", "b", "c", "d", "c1"], ["c1"], k=3)
    assert m.recall_at_k == 0.0
    assert m.n_retrieved == 3


def test_mrr_rewards_higher_rank():
    high = score_retrieval(["c1", "x", "y"], ["c1"], k=8)
    low = score_retrieval(["x", "y", "c1"], ["c1"], k=8)
    assert high.mrr > low.mrr
    # Recall is blind to ordering; MRR is the metric that sees a reranker working.
    assert high.recall_at_k == low.recall_at_k


def test_ndcg_rewards_higher_rank():
    high = score_retrieval(["c1", "x", "y"], ["c1"], k=8)
    low = score_retrieval(["x", "y", "c1"], ["c1"], k=8)
    assert high.ndcg_at_k > low.ndcg_at_k


def test_duplicate_retrievals_count_once():
    m = score_retrieval(["c1", "c1", "c1"], ["c1", "c2"], k=8)
    assert m.recall_at_k == 0.5
    assert m.n_retrieved == 1


def test_no_relevant_ids_yields_empty_metrics():
    m = score_retrieval(["c1"], [], k=8)
    assert m.n_relevant == 0
    assert m.recall_at_k == 0.0


# --------------------------------- abstention ---------------------------------
@pytest.mark.parametrize("answer", [
    "I couldn't find anything relevant in this case's documents.",
    "That information is not present in the provided documents.",
    "There is no mention of a court outcome in these files.",
    "The documents do not state who approved the payment.",
    "I don't know based on the evidence provided.",
])
def test_abstention_phrases_are_detected(answer):
    assert is_abstention(answer)


@pytest.mark.parametrize("answer", [
    "The payment was approved by Jane Tan on 1 June 2024 [1].",
    "Nova Build received MYR 9,000 into account ACC-111 [2].",
])
def test_confident_answers_are_not_abstentions(answer):
    assert not is_abstention(answer)


# ------------------------------- answer scoring -------------------------------
def test_missing_required_substring_is_flagged():
    q = _q(must_include=("ACC-111",))
    m = score_answer(q, "The payment went to an account held by Nova Build.", n_citations=3)
    assert m.missing_required == ("ACC-111",)
    assert not m.passed


def test_forbidden_substring_is_flagged():
    q = _q(kind="negative", relevant=(), must_not_include=("Cayman",))
    m = score_answer(q, "The funds were routed to a Cayman Islands account.", n_citations=2)
    assert m.present_forbidden == ("Cayman",)
    assert not m.passed


def test_citation_beyond_retrieved_range_is_caught():
    # Only 2 chunks were supplied, so [5] cannot refer to anything real.
    q = _q()
    m = score_answer(q, "The payment was approved [1] and later reversed [5].", n_citations=2)
    assert m.cited_unretrieved == ("5",)
    assert not m.passed


def test_valid_citations_pass():
    q = _q()
    m = score_answer(q, "Approved by Jane Tan [1], paid on 1 June [2].", n_citations=2)
    assert m.cited_unretrieved == ()
    assert m.passed


# -------------------------------- aggregation --------------------------------
def test_negative_questions_are_excluded_from_retrieval_averages():
    lookup = _q("q1", relevant=("c1",))
    negative = _q("q2", kind="negative", relevant=())

    scored = [
        (lookup, score_retrieval(["c1"], ["c1"], k=8), None),
        (negative, score_retrieval([], [], k=8), score_answer(negative, "I couldn't find that.", 0)),
    ]
    agg = aggregate(scored)

    # A zero-recall negative question must not drag the retrieval mean down.
    assert agg.recall_at_k == 1.0
    # ...nor be counted in the n reported alongside the retrieval metrics.
    assert agg.n_questions == 2
    assert agg.n_scored == 1
    assert agg.n_negative == 1
    assert agg.correct_abstentions == 1
    assert agg.abstention_rate == 1.0


def test_unanswered_negatives_are_unmeasured_not_failed():
    """A retrieval-only run must not report abstention as 0% — nothing was tested."""
    negative = _q("q1", kind="negative", relevant=())
    agg = aggregate([(negative, score_retrieval([], [], k=8), None)])

    assert agg.n_negative == 1
    assert agg.n_negative_answered == 0
    assert agg.abstention_measured is False
    assert agg.abstention_rate == 0.0

    console = format_console(run_eval(GoldenSet("investigation", [negative]), _StubRetriever({}), k=8))
    assert "not measured" in console
    # The misleading phrasing must not appear.
    assert "0/1 negative questions correctly declined" not in console


def test_answered_negatives_are_scored_on_abstention():
    negative = _q("q1", kind="negative", relevant=())
    good = score_answer(negative, "I couldn't find that in these documents.", 0)
    bad = score_answer(negative, "The court imposed a five year sentence.", 0)

    assert aggregate([(negative, score_retrieval([], [], k=8), good)]).abstention_rate == 1.0
    assert aggregate([(negative, score_retrieval([], [], k=8), bad)]).abstention_rate == 0.0


def test_negative_kind_is_absent_from_retrieval_breakdown():
    """A `negative` row showing recall 0% reads as failure when it means not-applicable."""
    gs = GoldenSet("investigation", [
        _q("q1", question="a", kind="lookup", relevant=("c1",)),
        _q("q2", question="b", kind="negative", relevant=()),
    ])
    console = format_console(run_eval(gs, _StubRetriever({"a": ["c1"]}), k=8))

    kind_rows = [ln for ln in console.splitlines() if "recall" in ln and ln.startswith("    ")]
    assert any("lookup" in ln for ln in kind_rows)
    assert not any("negative" in ln for ln in kind_rows)


def test_per_kind_breakdown_is_produced():
    scored = [
        (_q("q1", kind="lookup"), score_retrieval(["c1"], ["c1"], k=8), None),
        (_q("q2", kind="multi_hop"), score_retrieval(["x"], ["c1"], k=8), None),
    ]
    agg = aggregate(scored)
    assert agg.per_kind["lookup"].recall_at_k == 1.0
    assert agg.per_kind["multi_hop"].recall_at_k == 0.0


# ------------------------------ golden set loading ------------------------------
def _write(tmp_path, body):
    path = tmp_path / "g.yaml"
    path.write_text(body, encoding="utf-8")
    return path


def test_loads_a_valid_golden_set(tmp_path):
    gs = load_golden_set(_write(tmp_path, """
workspace_type: investigation
questions:
  - id: a1
    question: Who approved it?
    case_id: case-1
    relevant_chunk_ids: [c1]
    validated_by: Investigator A
  - id: a2
    question: What was the sentence?
    case_id: case-1
    kind: negative
"""))
    assert len(gs) == 2
    assert len(gs.validated) == 1
    assert len(gs.unvalidated) == 1


def test_question_without_ground_truth_is_rejected(tmp_path):
    # Would score zero forever and read as a retrieval bug rather than an authoring gap.
    with pytest.raises(GoldenSetError, match="no relevant_chunk_ids"):
        load_golden_set(_write(tmp_path, """
workspace_type: investigation
questions:
  - id: a1
    question: Who approved it?
    case_id: case-1
"""))


def test_duplicate_ids_are_rejected(tmp_path):
    with pytest.raises(GoldenSetError, match="duplicate question id"):
        load_golden_set(_write(tmp_path, """
workspace_type: investigation
questions:
  - id: a1
    question: Q
    case_id: c
    relevant_chunk_ids: [c1]
  - id: a1
    question: Q
    case_id: c
    relevant_chunk_ids: [c2]
"""))


def test_unknown_kind_is_rejected(tmp_path):
    with pytest.raises(GoldenSetError, match="unknown kind"):
        load_golden_set(_write(tmp_path, """
workspace_type: investigation
questions:
  - id: a1
    question: Q
    case_id: c
    kind: freeform
    relevant_chunk_ids: [c1]
"""))


def test_missing_workspace_type_is_rejected(tmp_path):
    with pytest.raises(GoldenSetError, match="workspace_type"):
        load_golden_set(_write(tmp_path, "questions: []"))


def test_shipped_example_golden_set_parses():
    """The example in goldens/examples/ must stay loadable — it is the authoring template."""
    from pathlib import Path

    import backend.eval as eval_pkg

    example = Path(eval_pkg.__file__).parent / "goldens" / "examples" / "investigation.example.yaml"
    gs = load_golden_set(example)
    assert len(gs) >= 10
    # Placeholder ground truth must never be quotable.
    assert gs.validated == [], "example golden set must ship with no validated questions"
    assert {q.kind for q in gs.questions} == {"lookup", "multi_hop", "aggregation", "negative"}


# ---------------------------------- the runner ----------------------------------
class _StubRetriever:
    """Returns a fixed ranking, so runner behaviour is tested without a DB."""

    name = "stub"

    def __init__(self, by_question):
        self._by_question = by_question

    def retrieve(self, question, case_id, k):
        return [RetrievedChunk(chunk_id=c) for c in self._by_question.get(question, [])][:k]


def test_run_eval_splits_validated_from_unvalidated():
    gs = GoldenSet("investigation", [
        _q("q1", question="validated one", relevant=("c1",), validated=True),
        _q("q2", question="unvalidated one", relevant=("c2",), validated=False),
    ])
    retriever = _StubRetriever({"validated one": ["c1"], "unvalidated one": ["zzz"]})

    report = run_eval(gs, retriever, k=8)

    # The headline sees only the validated question, which retrieved correctly.
    assert report.headline.recall_at_k == 1.0
    assert report.headline.n_questions == 1
    # The unvalidated miss is reported, but kept out of the quotable number.
    assert report.provisional.recall_at_k == 0.0
    assert len(report.results) == 2


def test_retriever_failure_is_captured_not_raised():
    class _Broken:
        name = "broken"

        def retrieve(self, question, case_id, k):
            raise RuntimeError("supabase unreachable")

    report = run_eval(GoldenSet("investigation", [_q("q1")]), _Broken(), k=8)

    assert len(report.errors) == 1
    assert "supabase unreachable" in report.errors[0].error
    assert report.results[0].retrieval.recall_at_k == 0.0


def test_document_level_scoring():
    gs = GoldenSet("investigation", [
        GoldenQuestion(id="q1", question="Q", case_id="c", relevant_document_ids=("d1",),
                       validated_by="A"),
    ])

    class _DocRetriever:
        name = "doc"

        def retrieve(self, question, case_id, k):
            return [RetrievedChunk(chunk_id="c9", document_id="d1")]

    report = run_eval(gs, _DocRetriever(), k=8, level="document")
    assert report.headline.recall_at_k == 1.0


def test_record_and_replay_fixture_reproduces_scores(tmp_path):
    gs = GoldenSet("investigation", [_q("q1", question="who paid?", relevant=("c1",))])
    live = run_eval(gs, _StubRetriever({"who paid?": ["c1", "c2"]}), k=8)

    path = record_fixture(live, tmp_path / "fx.json")
    replayed = run_eval(gs, FixtureRetriever(path), k=8)

    assert replayed.headline.recall_at_k == live.headline.recall_at_k
    assert replayed.results[0].retrieved_chunk_ids == ["c1", "c2"]


def test_comparison_lists_regressions_and_improvements():
    gs = GoldenSet("investigation", [
        _q("q1", question="a", relevant=("c1",)),
        _q("q2", question="b", relevant=("c2",)),
    ])
    baseline = run_eval(gs, _StubRetriever({"a": ["c1"], "b": ["zzz"]}), k=8)
    candidate = run_eval(gs, _StubRetriever({"a": ["zzz"], "b": ["c2"]}), k=8)

    cmp_result = compare(baseline, candidate)
    assert cmp_result.regressions == ["q1"]
    assert cmp_result.improvements == ["q2"]
    assert cmp_result.deltas["recall_at_k"] == 0.0  # one gained, one lost


def test_report_serialises_to_json():
    gs = GoldenSet("investigation", [_q("q1", question="a", relevant=("c1",))])
    report = run_eval(gs, _StubRetriever({"a": ["c1"]}), k=8)

    payload = json.loads(json.dumps(report.to_dict()))
    assert payload["n_validated"] == 1
    assert payload["headline_validated"]["recall_at_k"] == 1.0
    assert payload["per_question"][0]["id"] == "q1"
