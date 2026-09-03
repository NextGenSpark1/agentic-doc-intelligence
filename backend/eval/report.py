"""Formats eval results for the terminal and for markdown.

The validated/unvalidated split is preserved everywhere on purpose: a reader should never
be able to quote a number without also seeing how much of it a human has actually checked.
"""
from __future__ import annotations

from backend.eval.metrics import AggregateMetrics
from backend.eval.runner import Comparison, EvalReport


def _pct(x: float) -> str:
    return f"{x * 100:5.1f}%"


def _agg_line(label: str, a: AggregateMetrics) -> str:
    return (
        f"  {label:<14} recall {_pct(a.recall_at_k)}  |  prec {_pct(a.precision_at_k)}  |  "
        f"hit {_pct(a.hit_at_k)}  |  mrr {a.mrr:.3f}  |  ndcg {a.ndcg_at_k:.3f}   (n={a.n_scored})"
    )


def _abstention_lines(a: AggregateMetrics) -> list[str]:
    """Report abstention only when answers were actually generated.

    A retrieval-only run generates no answers, so abstention is unmeasured. Printing
    "0/3 declined" there would read as a total failure of the single most important
    safety property, when in fact nothing was tested.
    """
    if not a.n_negative:
        return []
    if not a.abstention_measured:
        return [
            f"  {'abstention':<14} not measured - {a.n_negative} negative question(s) present, "
            "but this run generated no answers (retrieval-only)"
        ]
    return [
        f"  {'abstention':<14} {a.correct_abstentions}/{a.n_negative_answered} "
        f"negative questions correctly declined ({_pct(a.abstention_rate)})"
    ]


def format_console(report: EvalReport) -> str:
    """Human-readable summary for a terminal run."""
    lines: list[str] = []
    lines.append("")
    lines.append(f"Retrieval eval - {report.workspace_type} - retriever={report.retriever_name} k={report.k} level={report.level}")
    lines.append("=" * 96)

    n_val, n_unval = len(report.validated_results), len(report.unvalidated_results)

    if n_val:
        lines.append("")
        lines.append("HEADLINE (human-validated ground truth - the quotable number)")
        lines.append(_agg_line("all", report.headline))
        # `negative` is deliberately absent here: those questions have no relevant chunks,
        # so a retrieval row for them would read as 0% failure rather than "not applicable".
        for kind, agg in report.headline.per_kind.items():
            if kind == "negative":
                continue
            lines.append(_agg_line(f"  {kind}", agg))
        lines.extend(_abstention_lines(report.headline))
    else:
        lines.append("")
        lines.append("HEADLINE: none - no question in this golden set has been human-validated yet.")
        lines.append("  Numbers below are provisional and must not be quoted. See goldens/README.md.")

    if n_unval:
        lines.append("")
        lines.append(f"PROVISIONAL (unvalidated ground truth - directional only)")
        lines.append(_agg_line("all", report.provisional))

    if report.errors:
        lines.append("")
        lines.append(f"ERRORS ({len(report.errors)})")
        for r in report.errors[:10]:
            lines.append(f"  {r.question.id}: {r.error}")

    # Worst performers are the actionable part of the report — they name the questions to
    # look at next, which is how a golden set turns into a fix.
    scorable = [r for r in report.results if r.question.kind != "negative" and not r.error]
    misses = sorted(scorable, key=lambda r: (r.retrieval.recall_at_k, r.retrieval.mrr))[:5]
    if misses and any(r.retrieval.recall_at_k < 1.0 for r in misses):
        lines.append("")
        lines.append("WEAKEST QUESTIONS")
        for r in misses:
            if r.retrieval.recall_at_k >= 1.0:
                continue
            rank = r.retrieval.first_relevant_rank
            where = f"first hit at rank {rank}" if rank else "no relevant chunk retrieved"
            flag = "" if r.question.is_validated else "  [unvalidated]"
            lines.append(f"  {r.question.id:<22} recall {_pct(r.retrieval.recall_at_k)}  {where}{flag}")
            lines.append(f"    {r.question.question[:88]}")

    lines.append("")
    lines.append(
        f"{len(report.results)} questions  |  {n_val} validated  |  {n_unval} unvalidated  |  "
        f"{len(report.errors)} errors  |  median latency {report.median_latency_ms:.0f}ms"
    )
    lines.append("")
    return "\n".join(lines)


def format_markdown(report: EvalReport) -> str:
    """Markdown summary, for pasting into a PR or a review doc."""
    a = report.headline
    lines = [
        f"# Retrieval eval — {report.workspace_type}",
        "",
        f"**Retriever:** `{report.retriever_name}` · **k:** {report.k} · **level:** {report.level}",
        f"**Questions:** {len(report.results)} ({len(report.validated_results)} validated, "
        f"{len(report.unvalidated_results)} unvalidated)",
        "",
    ]

    if not report.validated_results:
        lines += [
            "> **No validated ground truth.** Every number below is provisional and must not be "
            "quoted externally until a domain expert has verified the golden set.",
            "",
        ]

    lines += [
        "## Headline (validated only)",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| recall@{report.k} | {_pct(a.recall_at_k).strip()} |",
        f"| precision@{report.k} | {_pct(a.precision_at_k).strip()} |",
        f"| hit@{report.k} | {_pct(a.hit_at_k).strip()} |",
        f"| MRR | {a.mrr:.3f} |",
        f"| nDCG@{report.k} | {a.ndcg_at_k:.3f} |",
        f"| questions scored | {a.n_questions} |",
        "",
    ]

    if a.n_negative:
        if a.abstention_measured:
            lines += [
                f"**Abstention:** {a.correct_abstentions}/{a.n_negative_answered} negative questions "
                f"correctly declined ({_pct(a.abstention_rate).strip()}).",
                "",
            ]
        else:
            lines += [
                f"**Abstention:** not measured — {a.n_negative} negative question(s) present, but this "
                "run generated no answers (retrieval-only).",
                "",
            ]

    retrieval_kinds = {k: v for k, v in a.per_kind.items() if k != "negative"}
    if retrieval_kinds:
        lines += ["## By question kind", "", "| Kind | n | recall | MRR | nDCG |", "|---|---|---|---|---|"]
        for kind, sub in retrieval_kinds.items():
            lines.append(
                f"| {kind} | {sub.n_questions} | {_pct(sub.recall_at_k).strip()} | "
                f"{sub.mrr:.3f} | {sub.ndcg_at_k:.3f} |"
            )
        lines.append("")

    return "\n".join(lines)


def format_comparison(cmp: Comparison) -> str:
    """Side-by-side of two retrievers, with the regression list called out."""
    b, c = cmp.baseline, cmp.candidate
    deltas = cmp.deltas

    def row(name: str, key: str, bv: float, cv: float) -> str:
        d = deltas[key]
        arrow = "+" if d > 0 else ""
        return f"  {name:<14} {_pct(bv)}  ->  {_pct(cv)}   ({arrow}{d * 100:.1f}pp)"

    lines = [
        "",
        f"Comparison - {b.workspace_type} - baseline={b.retriever_name} vs candidate={c.retriever_name}",
        "=" * 96,
        "",
        "Validated questions only:",
        row("recall", "recall_at_k", b.headline.recall_at_k, c.headline.recall_at_k),
        row("precision", "precision_at_k", b.headline.precision_at_k, c.headline.precision_at_k),
        row("hit", "hit_at_k", b.headline.hit_at_k, c.headline.hit_at_k),
        f"  {'mrr':<14} {b.headline.mrr:.3f}  ->  {c.headline.mrr:.3f}   ({deltas['mrr']:+.3f})",
        f"  {'ndcg':<14} {b.headline.ndcg_at_k:.3f}  ->  {c.headline.ndcg_at_k:.3f}   ({deltas['ndcg_at_k']:+.3f})",
        "",
        f"  improved: {len(cmp.improvements)} questions    regressed: {len(cmp.regressions)} questions",
    ]

    if cmp.regressions:
        lines += ["", "  REGRESSIONS (read these before shipping):"]
        lines += [f"    {qid}" for qid in cmp.regressions[:15]]

    lines.append("")
    return "\n".join(lines)
