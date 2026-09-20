"""Fill in embeddings for chunks that were indexed while the embedding provider was failing.

Those chunks hold their text but no vector, so the document looks complete while part of it
cannot be found by search or cited by the AI. Nothing retries them on its own.

    python scripts/backfill_embeddings.py              # up to 1000 chunks per table
    python scripts/backfill_embeddings.py --limit 200

Safe to re-run: it only touches rows whose embedding is still empty. It does NOT fix documents
indexed under a different embedding model — re-extract those.
"""
from __future__ import annotations

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=1000,
                        help="maximum chunks to fill per table (default: 1000)")
    parser.add_argument("--batch-size", type=int, default=100,
                        help="chunks per embedding call (default: 100)")
    args = parser.parse_args()

    from backend.core.reindex import backfill_missing_embeddings

    summary = backfill_missing_embeddings(limit=args.limit, batch_size=args.batch_size)
    print(f"case/workspace chunks filled: {summary['chunks_filled']}")
    print(f"vault chunks filled:          {summary['vault_chunks_filled']}")
    for error in summary.get("errors", []):
        print(f"  stopped early — {error}")
    return 1 if summary.get("errors") else 0


if __name__ == "__main__":
    sys.exit(main())
