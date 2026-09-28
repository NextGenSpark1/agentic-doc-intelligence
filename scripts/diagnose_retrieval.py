"""Why did a requirement not find the document that proves it?

Runs the real retrieval path for a workspace's requirements and prints what came back, so a
missing match can be traced to the stage that lost it rather than guessed at:

  * the vault has no chunks for that document      -> it was never extracted
  * the chunks have no embedding                   -> embedding failed; run backfill_embeddings
  * every score is low and the ranking looks random -> the vectors were made by a different
                                                      embedding model; re-extract those documents
  * the right document scores well but ranks low    -> a genuine ranking problem worth tuning

Read-only: it embeds each requirement (a few cents at most) and reads the vault. It writes
nothing.

    python scripts/diagnose_retrieval.py --workspace <workspace-id>
    python scripts/diagnose_retrieval.py --workspace <workspace-id> --limit 5 --top 5
"""
from __future__ import annotations

import argparse

# Run from anywhere: `python scripts/<name>.py` puts scripts/ on the path, not the repo root,
# so `backend` would not import.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


# A cosine similarity below this is dropped before the adjudicator ever sees the candidate.
FLOOR = 0.35


def _vault_health(db, org_id: str) -> None:
    documents = db.list_library_documents(org_id) or []
    print(f"vault: {len(documents)} library documents")

    missing = db.list_supplier_chunks_missing_embeddings(limit=1000)
    if missing:
        by_document: dict[str, int] = {}
        for chunk in missing:
            by_document[str(chunk.get("supplier_document_id"))] = (
                by_document.get(str(chunk.get("supplier_document_id")), 0) + 1
            )
        print(f"  WARNING: {len(missing)} chunk(s) stored with no embedding, across "
              f"{len(by_document)} document(s) — those documents cannot be found by search.")
        print("           fix with: python scripts/backfill_embeddings.py")

    print()
    print(f"  {'document':44} {'extracted':10} {'chunks':>6}")
    print("  " + "-" * 64)
    for document in documents:
        supplier = db.get_supplier_document_by_library_doc(document["doc_id"])
        if not supplier:
            print(f"  {str(document.get('title'))[:44]:44} {'NO VAULT':10} {'-':>6}")
            continue
        chunks = db.list_supplier_chunks(supplier["supplier_document_id"]) or []
        status = supplier.get("extraction_status") or "?"
        flag = "" if chunks else "   <-- nothing indexed; Extract has not run or it failed"
        print(f"  {str(document.get('title'))[:44]:44} {status:10} {len(chunks):>6}{flag}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--workspace", required=True, help="workspace id to diagnose")
    parser.add_argument("--limit", type=int, default=0,
                        help="only the first N requirements (default: all)")
    parser.add_argument("--top", type=int, default=5, help="documents to show per requirement")
    args = parser.parse_args()

    from backend.apps.tendering import db
    from backend.apps.tendering.pipeline.evidence_matching import (
        _CANDIDATE_POOL, _match_query, extract_keywords, merge_candidates,
    )
    from backend.core import llm

    workspace = db.get_tendering_workspace(args.workspace)
    if not workspace:
        print(f"no workspace {args.workspace}")
        return 1
    org_id = workspace.get("org_id")
    print(f"workspace : {workspace.get('title')}")
    print(f"closing   : {workspace.get('closing_date') or 'NOT SET — expiry rules cannot apply'}")
    print()
    _vault_health(db, org_id)

    requirements = db.list_workspace_requirements_raw(args.workspace) or []
    if args.limit:
        requirements = requirements[:args.limit]
    print()
    print(f"retrieval for {len(requirements)} requirement(s)")

    for requirement in requirements:
        description = (requirement.get("description") or "").strip()
        if not description:
            continue
        print()
        print("=" * 92)
        print(f"{requirement.get('status', '?'):9} | {description[:78]}")
        query = _match_query(requirement)
        if query.strip() != description:
            # What is embedded is required_evidence + description, not the clause verbatim.
            print(f"  searched for: {query[:86]}")

        try:
            vector_rows = db.match_supplier_docs(org_id, llm.embed([query])[0], _CANDIDATE_POOL)
        except Exception as exc:  # noqa: BLE001
            print(f"  retrieval failed: {type(exc).__name__}: {exc}")
            continue

        keywords = extract_keywords(requirement)
        keyword_rows = []
        if keywords:
            try:
                keyword_rows = db.match_supplier_docs_by_keyword(org_id, keywords, args.top)
            except Exception as exc:  # noqa: BLE001
                print(f"  keyword pass failed: {type(exc).__name__}: {exc}")
        print(f"  keywords: {', '.join(keywords) if keywords else '(none)'}")

        rows = merge_candidates(vector_rows, keyword_rows)
        if not rows:
            print("  NOTHING RETRIEVED — the vault returned no candidates at all")
            continue
        for row in sorted(rows, key=lambda r: float(r.get("similarity") or 0.0),
                          reverse=True)[:args.top]:
            score = float(row.get("similarity") or 0.0)
            sources = "+".join(sorted(row.get("_sources") or {"vector"}))
            if not score >= FLOOR and "keyword" not in sources:
                note = "   <-- below the floor, dropped"
            elif not row.get("library_doc_id"):
                # Retrieved, adjudicated, and then discarded: the evidence link needs a library
                # document to point at, and this vault row has none. From the compliance matrix
                # that is indistinguishable from the document never being found. It shows up in
                # the analysis audit row as `skipped`.
                note = "   <-- NO library_doc_id: match cannot be saved as evidence"
            else:
                note = ""
            print(f"    {score:.3f}  {sources:14} {str(row.get('title'))[:44]:44}{note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
