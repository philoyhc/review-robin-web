# Assignment rule: pair-context tags as a person's tags

**Opened:** 2026-10-16 · **Theme:** making Band 1's Link 1 and Link 2
mean what the operator reads · **Related:** `spec/instruments.md`
(Link 1 / Link 2), `spec/assignments.md` (Predicate vocabulary)

A standalone plan at the author's naming, not a `segment_*.md`, in the
shape of `guide/import_error_reporting.md`: items close independently,
each with its own `### Doc impact` and `### Status`, checked by hand at
close (`tools/close_check.py` reads only `segment_*` files).

**Status (2026-10-17).** Item 1 stage 1 shipped in #3086; its
person-level reading is superseded by Item 2, which the author ruled on
2026-10-17. Item 2 is unbuilt.

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

Opened 2026-10-16 after #3085. Stage 1 shipped in #3086 (rung 1). The
person-level reading in the Decision above is superseded by Item 2
(author, 2026-10-17): a pair tag is a person's tag except under Link 2
`IS` / `IS NOT`, which read the pair itself.

---

## Item 2 — Pair-context tags: whose tag, by operator

### Opportunity

Item 1's stage 1 took pair-context tags off the card while the author
settled their meaning. The ruling (author, 2026-10-17): reviewer and
reviewee tags are attributes of a person, but a pair-context tag joins
two people. A pair tagged `Friend` or `COI` is a specific pair, not a
claim that everyone in such a pair is a friend. So a relationship pair
works like a hand-made assignment pair, or a hand-made exclusion.

### Decision

The card offers pair-context tags again, each under its friendly label
(`Pair: Office`, …), and what one means depends on where it is used:

| Where | Operators | A pair-context tag means |
|---|---|---|
| Link 1 field | `IS` / `IS NOT` / `IS FILLED` / `IS EMPTY` | the reviewer's: any of their active pairs carries it |
| Link 2 field | `IS THE SAME AS` / `IS DIFFERENT FROM` / `IS FILLED` / `IS EMPTY` | the reviewee's, read the same way |
| Link 2 operand | `IS THE SAME AS` / `IS DIFFERENT FROM` | the reviewer's, read the same way |
| Link 2 field | `IS` / `IS NOT` | the pair itself: `IS` keeps only pairs carrying the value; `IS NOT` rules them out |

- Captions: "Reviewer's tag" (Link 1 field, Link 2 operand) and
  "Reviewee's tag" (Link 2 field).
- **Link 3 offers no Group** while any Link 2 rule is a pair-tag `IS`,
  `AND` or `OR` alike; a stored Group with one is refused at Save.
  Pair tags stay out of the Link 3 boundary list (Item 1).
- On a Group instrument a pair-tag `IS NOT` drops only that member's
  row. A relationship pair is a unique pair of individuals, unlike
  "my own group" (the whole-group self-review rule).
- Engine shape: two new person-level fields, `reviewer.pair_tagN` and
  `reviewee.pair_tagN`, each the set of values the person holds in slot
  N across their active pairs; `pair_context.tagN` stays the per-pair
  field. Save picks the field from the Link and operator, so the
  population check stays a plain reviewer-versus-reviewee one.

Rejected: one person-level reading everywhere (Item 1's Decision). It
cannot say "each mentor reviews their own mentees", which Link 2
`pair tag IS Mentor` now does.

### Semantics

- **Empty values, every tag** (author, 2026-10-17): `IS NOT` passes an
  empty value. `IS THE SAME AS` passes when both sides hold the same
  value, empty included; `IS DIFFERENT FROM` passes when they differ,
  empty counting as a value (`Friend` and empty pass; empty and empty
  fail). For a person-level pair tag, "the same" means the two sets
  share a value, and an empty set is the empty value.
- **Observer cohort rule** follows the same empty-value rule (author,
  2026-10-17). Its `IS NOT` already passes an empty value; its
  cross-side operators return false on an empty observer side today
  (`app/services/observer_cohort.py`).
- **Inactive relationships** give no one a pair tag, as the engine's
  skip-at-lookup already does.
- **Existing sessions are disposable** (author, 2026-10-17: pre-Azure
  sessions are nukable). Stored rules change meaning without migration
  or notice: reviewer and reviewee `IS NOT`, Link 1 pair tags (pair →
  reviewer), and Link 2 cross-side pair tags (pair → reviewee).

### Blast radius (measured)

Taken 2026-10-17 at `9dc78ae3`.

- Predicates: `_not_equals`, `_not_in`, `_same_as`, `_different_from`
  in `app/services/rules/predicates.py`; field resolution in
  `app/services/rules/fields.py`; `ALLOWED_PREDICATE_FIELDS` named in 6
  tracked files under `app/` and `tests/`
  (`git grep -l ALLOWED_PREDICATE_FIELDS -- app tests | wc -l`).
- Band 1: `app/services/instruments/_band1.py` (field mapping on build
  and decode), the `new_model_rule_list` macro and the Link 3 pill in
  `app/web/templates/operator/instruments_index.html`.
- Observer cohort: `app/services/observer_cohort.py` (one predicate).

### PR ladder

1. **Engine.** The empty-value rule for every tag; the two person-level
   fields; Band 1 cross-side operands checked reviewer-versus-reviewee.
   Unit tests per operator and per empty case.
2. **Save and the card, with the Link 3 guard.** Pair tags back in the
   Link 1 and Link 2 lists with the `Pair:` prefix and the new captions;
   Save maps each to its field; decode maps back; the stored-only option
   retires for pair tags. Group is hidden and refused at Save alongside a
   pair-tag `IS` in this same rung, so no merged state can store the
   combination (Codex on #3087).
3. **The observer rule.** The observer cohort's empty-value rule.
4. **Close.** Specs, Guide card wording if any, browser checks.

### Definition of done

- The table above holds in tests: Link 2 `Office IS Friend` yields
  exactly the tagged pairs, and `IS NOT COI` keeps every untagged pair.
- `spec/assignments.md` (Predicate vocabulary, Operators) and
  `spec/instruments.md` (Band 1) state the table and the empty-value
  rule; `spec/setup_pages.md` (Observers, cohort rule) states the
  cohort rule's.
- `### Doc impact` honored; `### Status` compacted at close.

### Open questions

None open (author, 2026-10-17).

### Out of scope

Pair tags as Link 3 boundaries (Item 1). Pair-context display fields on
the reviewer surface.

### Doc impact

- `spec/assignments.md` — Predicate vocabulary: person-level pair-tag fields; Operators: the empty-value rule.
- `spec/instruments.md` — Band 1: pair tags by Link and operator, captions, Link 3 Group rule.
- `spec/setup_pages.md` — Relationships row: Band 1 offers pair tags again; Observers cohort rule: the empty-value rule.

### Status

Opened 2026-10-17 from the author's rulings. Item base for the
cumulative diff read: `cc7e1ac0` (main before rung 1).

- **Rung 1 (engine), 2026-10-17.** Predicates read every field as a set
  of values; the empty-value rule applies to every tag; the six
  person-level fields join `FIELD_MAP` under their own sides
  (`reviewer_pairs` / `reviewee_pairs`), so the staleness stamp, which
  reads roster sides only, is unchanged. `spec/assignments.md` gains the
  fields and the rule in this rung, not at close, since the behavior
  ships here.
- **Rung 2 (Save, card, Link 3 guard), 2026-10-17.** The card offers
  relationship tags as "Pair: …" in Link 1 and Link 2 under the captions
  "Reviewer's tag" / "Reviewee's tag"; Save maps each by Link and
  operator (`_band1._engine_field`) and decode maps back. A Link 2
  pair-tag `IS` refuses a grouped Link 3 at Save and the Link 3 pill
  skips Group while one is on the card. The stored-only option stays,
  now for emptied slots and relationship-tag boundaries.
  `spec/instruments.md` and `spec/setup_pages.md` updated in this rung.
- **Rung 3 (observer rule), 2026-10-17.** The cohort rule's cross-
  attribute operators treat no value as a value; `IS NOT` already passed
  one. Last build rung: the cumulative diff read covers `cc7e1ac0..` here.
- **Cumulative read (`diff-reviewer`, `cc7e1ac0..`), 2026-10-17.** One
  read for the item; six findings, all acted on in #3090:
  - per-pair predicate cost rose 29–59% at 1000 × 1000 (one rule, the
    reader's benchmark). Values now read as tuples with a single-value
    fast path and one field parse, back to parity for `IS` and +7–18%
    for `IS THE SAME AS`;
  - rung 1's "stamp unchanged" held for its inputs, not its verdicts:
    `STAMP_VERSION` goes to `v2`, so no cached verdict made under the
    old empty-value reading survives;
  - a Settings import could store Group beside a Link 2 pair-tag `IS`;
    it now refuses the combination as Save does;
  - `spec/instruments.md` now names the legacy Link 2 field rewrite
    (pair → reviewee) and the Group `IS NOT` per-member ruling, the
    latter pinned through Generate on real relationship rows
    (`tests/integration/test_pair_tags_generate.py`);
  - the cohort rule strips the typed value as well as the tag.
  The `spec-writer` verify on rung 3 found the cohort paragraph silent on
  `IS` / `CONTAINS` on no value; stated and pinned.
- **Follow-up, 2026-10-17 (author, after the browser checks passed).**
  Link 2's caption reads "Pairwise tag", not "Reviewee's tag", while a
  cell holds a relationship tag under `IS` / `IS NOT`, so the pair-level
  reading is visible on the card (`newModelSyncFieldHelper`). It
  reopens `app/` after the read, so it takes its own read.
