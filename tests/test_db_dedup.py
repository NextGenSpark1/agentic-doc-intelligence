"""Dedup key used by insert_finding / insert_relationship / insert_timeline_events.

`_content_hash` MUST produce the exact same string as the SQL `md5(... || chr(0) || ...)`
expression in schema.sql, or a Python-inserted row and a SQL-backfilled row won't collide and
the unique index stops deduping. These tests pin the byte-for-byte formula so a future edit to
either side can't silently drift.
"""
import hashlib

from backend.core.db_core import _content_hash


def test_matches_sql_md5_formula_for_a_finding():
    # SQL: md5(lower(coalesce(finding_type,'')) || chr(0) || coalesce(statement,''))
    # caller lower-cases finding_type before hashing (see insert_finding)
    got = _content_hash("duplicate_invoice", "Invoice INV-1 appears on 2 documents.")
    expected = hashlib.md5(
        b"duplicate_invoice\x00Invoice INV-1 appears on 2 documents."
    ).hexdigest()
    assert got == expected


def test_is_stable_and_order_sensitive():
    assert _content_hash("a", "b") == _content_hash("a", "b")
    assert _content_hash("a", "b") != _content_hash("b", "a")


def test_treats_none_like_empty_string():
    # mirrors SQL coalesce(x, '')
    assert _content_hash(None, "x") == _content_hash("", "x")


def test_uses_nul_separator_so_parts_cannot_run_together():
    # ("ab", "c") and ("a", "bc") must not collide
    assert _content_hash("ab", "c") != _content_hash("a", "bc")
