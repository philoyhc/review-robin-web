# Assignment rule: pair-context tags as a person's tags

**Opened:** 2026-10-16 · **Theme:** making Band 1's Link 1 and Link 2
mean what the operator reads · **Related:** `spec/instruments.md`
(Link 1 / Link 2), `spec/assignments.md` (Predicate vocabulary)

A standalone plan at the author's naming, not a `segment_*.md`, in the
shape of `guide/import_error_reporting.md`: items close independently,
each with its own `### Doc impact` and `### Status`, checked by hand at
close (`tools/close_check.py` reads only `segment_*` files).

**Opened, unbuilt.** It logs the change. Nothing is queued until the
open questions are ruled.

---

## Item 1 — A pair-context tag belongs to the person who holds it

### Opportunity

The author's model of the card (2026-10-16):

- **Link 1** is *who does the review*;
- **Link 2** is *who, among the reviewees, they review*.

Under that model, a pair-context tag counts as a person's tag: a
reviewer has a pair-context tag if they hold it in any of their pairs,
and so does a reviewee.

The engine instead reads a pair-context tag off the one pair it is
judging (`_resolve_pair_context` in `app/services/rules/fields.py`).
The two readings give different assignments.

Example: Rana reviews Carol and Dan, and only the Rana–Carol pair is
tagged `Pod`. Link 1 is "pair tag IS `Pod`".

- **The author reads:** Rana holds `Pod`, so she is a reviewer, and
  Link 2 decides whether she gets Carol, Dan or both.
- **The engine does:** it keeps Rana–Carol only. Dan is dropped by
  Link 1, which is a statement about who does the review, not about
  whom.

The labels and dropdowns already match the author's model (Link 1
"Reviewer tag" plus pair-context tags; Link 2 "Reviewee tag" plus
pair-context tags, with "Reviewer tag" as the operand). Only the
evaluation is wrong.

### Decision

**Pending** (Open questions 1–4). The proposed change: for a Band 1
predicate, `pair_context.tagN` resolves to the **set** of values the
person holds across their active pairs.

- In Link 1 it means the reviewer's set.
- In a Link 2 field it means the reviewee's set.
- In a Link 2 operand it means the reviewer's set.

`IS` / `IS NOT` test membership. `IS THE SAME AS` / `IS DIFFERENT FROM`
compare the two sides' values.

Rejected alternative: keep per-pair evaluation and reword the card so
it says "this pair's tag". That contradicts the two questions the card
exists to ask.

### Semantics

To settle before the build:

- **A person with no pairs**, or only inactive ones, has an empty set.
  Today a missing value fails every operator except `is_empty`.
- **Pair context against pair context** becomes meaningful: "reviewee's
  `Pod` is the same as the reviewer's `Pod`". So #3085's refusal and
  the editing-view narrowing would lift for Band 1.
- **Stored rules change meaning** without being edited. A Link 2 rule
  "pair tag IS `Mentor`" stops meaning *the reviewer's own mentees* and
  starts meaning *anyone who is someone's mentee*.

### Blast radius (measured)

Taken 2026-10-16 at `c863dfa8`.

- Resolution point: one function, `_resolve_pair_context`. Every
  `evaluate()` caller binds `pair_context_lookup` (12 lines in
  `app/services/assignments/_generate.py`).
  Command: `grep -n pair_context_lookup app/services/assignments/_generate.py`.
- `pair_context` appears in 34 tracked files under `app/` and 40 under
  `tests/` (`git grep -l pair_context -- app/ | wc -l`, and the same for
  `tests/`).
- Live specs naming pair context: 15 (`git grep -l -e pair_context -e
  pair-context -- 'spec/*.md' ':!spec/archive' | wc -l`).

### PR ladder

1. **Stage 1 (author, 2026-10-16).** The card stops offering
   pair-context tags in all four lists (Link 1 field, Link 2 field and
   operand, Link 3 boundary) and gains `IS FILLED` / `IS EMPTY` in Links
   1 and 2, with the value box inactive for them. A stored pair-context
   selection keeps its option. No engine change.
2. Further stages to be cut once the author has settled how pair-context
   tags are to be used.

### Definition of done

- `spec/instruments.md` Link 1 / Link 2 and `spec/assignments.md`
  Predicate vocabulary state the person-level reading.
- Tests pin the Rana–Carol–Dan example for Link 1 and Link 2.
- `## Doc impact` present and current; `### Status` compacted at close.

### Open questions

Answered 2026-10-16, then reopened: the author is rethinking how
pair-context tags are used, and stage 1 takes them off the card
meanwhile.

1. **Is the per-pair reading lost on purpose?** Yes. Link 1 "Reviewer's
   pair tag IS `Mentor`" with Link 2 "Reviewee's pair tag IS `Mentor`".
2. **Matching.** `IS` / `IS NOT` fully match a value; `IS THE SAME AS`
   / `IS DIFFERENT FROM` fully match another tag's value. Open: which of
   a person's several pair values counts.
3. **`IS NOT` passes an empty value.** Open: for every tag, or pair tags
   only, which would change existing reviewer and reviewee rules.
4. **No pair-context grouping in Link 3.** Done in stage 1.

### Out of scope

Pair-context display fields on the reviewer surface, which show the
pair's own value. The Relationships page itself.

### Doc impact

Stage 1 (done):

- `spec/instruments.md` — Band 1: no pair-context tags offered; `IS FILLED` / `IS EMPTY`; stored rules keep their option and a live pill (stage 1).
- `spec/assignments.md` — Operators table: `IS FILLED` / `IS EMPTY`; reviewer-tag operands (stage 1).
- `spec/setup_pages.md` — Relationships row: Band 1 does not offer pair-context tags (stage 1).

The person-level reading (on hold):

- `spec/instruments.md` — Link 1 / Link 2: a pair-context tag is the person's, across their pairs.
- `spec/assignments.md` — Predicate vocabulary: person-level resolution for Band 1 pair-context predicates.

### Status

Opened 2026-10-16 after #3085. Stage 1 built 2026-10-16 (rung 1).
The person-level reading is on hold pending the author's rethink.
