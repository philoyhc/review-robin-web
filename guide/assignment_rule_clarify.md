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

To be cut after the rulings. A likely first rung is the engine change
behind the Band 1 predicates, with its tests. The specs and the lifting
of the #3085 refusal would follow.

### Definition of done

- `spec/instruments.md` Link 1 / Link 2 and `spec/assignments.md`
  Predicate vocabulary state the person-level reading.
- Tests pin the Rana–Carol–Dan example for Link 1 and Link 2.
- `## Doc impact` present and current; `### Status` compacted at close.

### Open questions

1. **Is the per-pair reading lost on purpose?** Today, "pair tag IS
   `Mentor`" in Link 2 assigns each reviewer their own mentees only. Under
   the person-level reading the card can no longer say that. *Author.*
2. **How `IS THE SAME AS` / `IS DIFFERENT FROM` work on sets.** For
   example, "shares at least one value" and "shares none". *Author.*
3. **Whether `IS NOT` passes a person with no value.** *Author.*
4. **Scope.** Which of these follow the change: Link 3 grouping by a
   pair tag, and the operator-authored rules outside Band 1? *Author.*

### Out of scope

Pair-context display fields on the reviewer surface, which show the
pair's own value. The Relationships page itself.

### Doc impact

- `spec/instruments.md` — Link 1 / Link 2: a pair-context tag is the person's, across their pairs.
- `spec/assignments.md` — Predicate vocabulary: person-level resolution for Band 1 pair-context predicates.

### Status

Opened 2026-10-16 after #3085. Unbuilt, awaiting Open questions 1–4.
