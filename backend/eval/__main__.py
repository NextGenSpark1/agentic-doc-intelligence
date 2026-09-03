"""CLI for the retrieval eval harness.

    # score the current dense retriever against the investigation golden set
    python -m backend.eval run --golden backend/eval/goldens/investigation.yaml

    # capture a live run so CI can replay it without a DB or API keys
    python -m backend.eval run --golden ... --record backend/eval/fixtures/dense-run.json

    # compare a candidate retriever against a recorded baseline
    python -m backend.eval compare --golden ... --baseline fixtures/dense-run.json --candidate hybrid

    # check a golden set parses and report how much of it a human has validated
    python -m backend.eval lint --golden backend/eval/goldens/investigation.yaml
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from backend.eval.goldens import GoldenSet, GoldenSetError, load_golden_set
from backend.eval.report import format_comparison, format_console, format_markdown
from backend.eval.retrievers import FixtureRetriever, build_retriever
from backend.eval.runner import compare, record_fixture, run_eval


def _load(args) -> GoldenSet:
    gs = load_golden_set(args.golden)
    kinds = set(args.kinds.split(",")) if args.kinds else None
    return gs.filter(kinds=kinds, validated_only=args.validated_only, case_id=args.case_id)


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--golden", required=True, help="path to a golden-set YAML file")
    p.add_argument("-k", type=int, default=8, help="top-k to retrieve (default 8, matches rag_top_k)")
    p.add_argument("--level", choices=["chunk", "document"], default="chunk",
                   help="score against chunk ids or document ids (default chunk)")
    p.add_argument("--kinds", default="", help="comma-separated kinds to include, e.g. lookup,multi_hop")
    p.add_argument("--case-id", default="", help="only score questions for this case")
    p.add_argument("--validated-only", action="store_true", help="skip unvalidated questions entirely")


def cmd_run(args) -> int:
    golden_set = _load(args)
    if not golden_set.questions:
        print("No questions matched the given filters.", file=sys.stderr)
        return 1

    if args.retriever == "fixture":
        if not args.fixture:
            print("--fixture is required when --retriever fixture", file=sys.stderr)
            return 2
        retriever = FixtureRetriever(args.fixture)
    else:
        retriever = build_retriever(args.retriever)

    report = run_eval(golden_set, retriever, k=args.k, level=args.level)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    elif args.markdown:
        print(format_markdown(report))
    else:
        print(format_console(report))

    if args.record:
        path = record_fixture(report, args.record)
        print(f"Recorded {len(report.results)} retrievals to {path}", file=sys.stderr)

    # Non-zero exit when a threshold is set and missed, so this can gate CI.
    if args.min_recall is not None:
        actual = report.headline.recall_at_k
        if not report.validated_results:
            print("--min-recall was set but no validated questions exist; failing.", file=sys.stderr)
            return 1
        if actual < args.min_recall:
            print(f"FAIL: validated recall@{args.k} {actual:.3f} < threshold {args.min_recall:.3f}", file=sys.stderr)
            return 1
    return 0


def cmd_compare(args) -> int:
    golden_set = _load(args)
    baseline = run_eval(golden_set, FixtureRetriever(args.baseline, name="baseline"), k=args.k, level=args.level)
    candidate_retriever = (
        FixtureRetriever(args.candidate, name="candidate")
        if Path(args.candidate).exists()
        else build_retriever(args.candidate)
    )
    candidate = run_eval(golden_set, candidate_retriever, k=args.k, level=args.level)

    cmp_result = compare(baseline, candidate)
    print(format_comparison(cmp_result))

    if args.fail_on_regression and cmp_result.regressions:
        print(f"FAIL: {len(cmp_result.regressions)} questions regressed", file=sys.stderr)
        return 1
    return 0


def cmd_lint(args) -> int:
    try:
        gs = load_golden_set(args.golden)
    except GoldenSetError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1

    n_val = len(gs.validated)
    print(f"{gs.source_path}: OK - {len(gs)} questions, workspace_type={gs.workspace_type}")
    for kind in ("lookup", "multi_hop", "aggregation", "negative"):
        n = len(gs.by_kind(kind))
        if n:
            print(f"  {kind:<12} {n}")
    print(f"  validated    {n_val}/{len(gs)}")

    if n_val < len(gs):
        print(
            f"\n  {len(gs) - n_val} question(s) have no `validated_by`. Their ground truth is unverified,\n"
            "  so they are excluded from the headline number. See goldens/README.md.",
            file=sys.stderr,
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m backend.eval", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="score a golden set through a retriever")
    _add_common(p_run)
    p_run.add_argument("--retriever", default="dense",
                       choices=["dense", "hybrid", "keyword", "fixture"])
    p_run.add_argument("--fixture", default="", help="fixture JSON path (with --retriever fixture)")
    p_run.add_argument("--record", default="", help="save this run's retrievals to a fixture file")
    p_run.add_argument("--json", action="store_true", help="emit JSON instead of a console table")
    p_run.add_argument("--markdown", action="store_true", help="emit markdown instead of a console table")
    p_run.add_argument("--min-recall", type=float, default=None,
                       help="exit non-zero if validated recall@k falls below this (for CI)")
    p_run.set_defaults(func=cmd_run)

    p_cmp = sub.add_parser("compare", help="compare a candidate retriever against a recorded baseline")
    _add_common(p_cmp)
    p_cmp.add_argument("--baseline", required=True, help="fixture JSON of the baseline run")
    p_cmp.add_argument("--candidate", required=True, help="retriever name, or a fixture JSON path")
    p_cmp.add_argument("--fail-on-regression", action="store_true")
    p_cmp.set_defaults(func=cmd_compare)

    p_lint = sub.add_parser("lint", help="validate a golden set and report validation coverage")
    p_lint.add_argument("--golden", required=True)
    p_lint.set_defaults(func=cmd_lint)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except GoldenSetError as exc:
        print(f"Golden set error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
