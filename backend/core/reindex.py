"""Backfill embeddings for chunks that were stored without one.

Indexing deliberately degrades to text-only when the embedding provider fails: losing the whole
document because one batch timed out would be worse. The cost is that the document then looks
finished — status `done`, text readable, citations working — while part of it is invisible to
every vector search, with nothing on the row to say so. Nothing retried those chunks, so a
provider outage during an upload left a permanent hole in retrieval.

This is the retry. It is deliberately a separate pass rather than something the pipeline does
inline: by the time it is worth running, the provider is working again.

It does NOT re-embed chunks that already have a vector, so it cannot repair the other failure
mode — switching embedding model, which leaves every old vector meaningless rather than missing.
Re-extract those documents instead.
"""
from __future__ import annotations

import traceback
from typing import Callable

_DEFAULT_BATCH = 100


def _fill(fetch: Callable[[int], list[dict]], write: Callable[[object, list[float]], None],
          key: str, embed: Callable[[list[str]], list[list[float]]],
          limit: int, batch_size: int) -> tuple[int, str | None]:
    """Embed and store, batch by batch, until nothing new comes back or `limit` is reached.

    Rows already seen are tracked so a write that does not take (or a row with no text to embed)
    ends the loop instead of fetching the same rows for ever.
    """
    filled = 0
    seen: set = set()
    while filled < limit:
        try:
            rows = fetch(min(batch_size, limit - filled))
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            return filled, f"{type(exc).__name__}: {exc}"[:300]

        fresh = [row for row in rows if row.get(key) not in seen]
        if not fresh:
            return filled, None
        seen.update(row.get(key) for row in fresh)

        embeddable = [row for row in fresh if (row.get("text") or "").strip()]
        if not embeddable:
            continue

        try:
            vectors = embed([row["text"] for row in embeddable])
        except Exception as exc:  # noqa: BLE001
            # The provider is still down. Stopping beats hammering it for every remaining batch.
            traceback.print_exc()
            return filled, f"{type(exc).__name__}: {exc}"[:300]

        for row, vector in zip(embeddable, vectors):
            if vector is None:
                continue
            try:
                write(row[key], vector)
                filled += 1
            except Exception as exc:  # noqa: BLE001
                traceback.print_exc()
                return filled, f"{type(exc).__name__}: {exc}"[:300]
    return filled, None


def backfill_missing_embeddings(limit: int = 1000, batch_size: int = _DEFAULT_BATCH) -> dict:
    """Fill in missing vectors across both chunk tables. Returns what it managed."""
    from backend.apps.tendering import db as tendering_db
    from backend.core import db_core, llm

    summary: dict = {"chunks_filled": 0, "vault_chunks_filled": 0}
    errors: list[str] = []

    filled, error = _fill(db_core.list_chunks_missing_embeddings, db_core.set_chunk_embedding,
                          "id", llm.embed, limit, batch_size)
    summary["chunks_filled"] = filled
    if error:
        errors.append(f"chunks: {error}")

    filled, error = _fill(tendering_db.list_supplier_chunks_missing_embeddings,
                          tendering_db.set_supplier_chunk_embedding,
                          "chunk_id", llm.embed, limit, batch_size)
    summary["vault_chunks_filled"] = filled
    if error:
        errors.append(f"vault chunks: {error}")

    if errors:
        summary["errors"] = errors
    return summary
