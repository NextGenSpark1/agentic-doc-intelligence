"""Tendering Compliance — a supplier-side product built on the shared core.

Reads a tender document set and turns it into a structured, trackable compliance plan:
requirements -> evidence -> readiness. Reuses core's upload, OCR, chunking, embedding,
vector search, auth, orgs, and audit wholesale; adds only tender schemas, prompts, labels,
tables, and the stages that are genuinely new.

Tenders are NOT cases. They live in their own `tenders` table with their own access guard
(`access.load_tender_or_403`) and their own document routes, because the tender model —
buyers, references, bid decisions, readiness scores, requirements — is too different from an
investigation case to share a row shape.

What IS shared is the machinery: tender documents reuse the `documents` and `chunks` tables
via a nullable `tender_id`, so the whole upload -> parse -> chunk -> embed pipeline is reused
rather than reimplemented, and investigation rows are untouched.

The supplier vault is org-level (shared across a company's tenders) with its own vector table,
so vault evidence and case evidence can never surface in each other's retrieval.
"""
