# Golden sets

A golden set is a list of questions with **human-verified** ground truth: which chunks should
come back, and what the answer must or must not contain. It is what turns "retrieval feels
better" into a number we can defend.

This directory is empty of real golden sets on purpose. There is a worked example in
`examples/investigation.example.yaml` showing the question shapes worth covering, but the
ground truth in it is placeholder. **Only `*.yaml` files directly in this directory are
loaded** — the `examples/` subdirectory is ignored by `load_all()`.

## Why a human has to write these

The harness will happily score against invented ground truth and print a confident number.
That number would be worthless, and worse than worthless in a forensic context: it looks like
evidence. If the same process invents both the question and the correct answer, it is grading
its own homework.

So every question carries a `validated_by` field:

- **Empty** → the question is scored, but only into the *provisional* bucket. Never quotable.
- **Filled** → a named person has opened the source documents and confirmed the ground truth.
  These are the only questions in the headline number.

`python -m backend.eval lint --golden <file>` reports the split.

## Authoring workflow

1. **Pick a real case** with documents already ingested and chunked. Note its `case_id`.
2. **Write questions an investigator would actually ask.** Not questions crafted to be easy
   to retrieve — the point is to find where retrieval fails.
3. **Find the ground truth by hand.** Open the documents, locate the passage that answers the
   question, and record its `chunk_id`. Query the `chunks` table for the case to get ids:

   ```sql
   select chunk_id, document_id, page, left(text, 120)
   from chunks where case_id = '<case_id>' order by document_id, page;
   ```

   If you can name the right document but not the exact chunk, use `relevant_document_ids`
   and score with `--level document`. Coarser, still useful.
4. **Set `validated_by` and `validated_at`** once you have actually checked it.
5. **Lint, then run.**

## Question kinds

Mix them. A single average over one kind hides the failures that matter.

| Kind | What it tests | Aim for |
|---|---|---|
| `lookup` | Single-passage factual retrieval. Heavy on exact tokens — invoice numbers, account numbers, names, dates. **This is where pure dense search is weakest**, so it is where hybrid retrieval should show its gain. | ~40% |
| `multi_hop` | Answer requires joining two or more passages, often across documents. | ~25% |
| `aggregation` | Totals, counts, "all payments to X". Retrieval must return *every* relevant chunk, so recall matters more than rank. | ~15% |
| `negative` | The corpus genuinely does not contain the answer. Scored on whether the system **declines** rather than invents. | ~20% |

Do not skimp on `negative`. For investigation work, a confident wrong answer is the failure
mode that ends up in a courtroom. These questions are the only ones that measure it.

## Target size

Roughly **50 questions per workspace type** across at least two or three different cases.
Fewer than ~30 and a single question swings the average by more than a real regression does.

Spread across cases matters as much as count: 50 questions on one case measures that case,
not the system.

## Fields

```yaml
workspace_type: investigation      # matches the workspace-type registry
questions:
  - id: inv-lookup-001             # stable, unique; referenced in reports and regressions
    question: "..."                # what the investigator asks
    case_id: "..."                 # real case with ingested documents
    kind: lookup                   # lookup | multi_hop | aggregation | negative
    relevant_chunk_ids: [...]      # ground truth — chunk-level, preferred
    relevant_document_ids: [...]   # ground truth — document-level fallback
    expected_answer: "..."         # reference answer, for human reading (not auto-scored)
    must_include: ["ACC-4471"]     # substrings the answer must contain
    must_not_include: [...]        # hallucination traps
    validated_by: "..."            # WHO checked this. Empty = unverified.
    validated_at: "2026-08-19"
    notes: "..."                   # why this question is here / what it probes
```

`negative` questions need no relevant ids. Every other kind must have at least one, or the
loader rejects the file — a question with no ground truth scores zero forever and looks like
a retrieval bug rather than the authoring gap it is.

## Running

```bash
# validate the file and see validation coverage
python -m backend.eval lint --golden backend/eval/goldens/investigation.yaml

# score the current dense retriever (needs DB + embedding credentials)
python -m backend.eval run --golden backend/eval/goldens/investigation.yaml

# freeze a run so CI can replay it with no DB and no API keys
python -m backend.eval run --golden ... --record backend/eval/fixtures/dense-baseline.json

# after changing retrieval, compare against that frozen baseline
python -m backend.eval compare --golden ... \
    --baseline backend/eval/fixtures/dense-baseline.json \
    --candidate hybrid --fail-on-regression
```

## What to do with the numbers

`recall@k` is the headline. A chunk that never comes back can never be cited, so recall caps
everything downstream — no prompt change fixes a retrieval miss.

When you change retrieval, always `compare` rather than re-reading the absolute number, and
read the **regressions** list before shipping. An average can improve while the exact-token
lookups that investigators rely on quietly get worse.
