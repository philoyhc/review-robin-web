# Pair-context tags: one meaning, the pair

**Opened:** 2026-10-18 · **Theme:** making a relationship tag on Band 1
mean one thing wherever it appears · **Related:** `spec/instruments.md`
(Band 1, Link 1 / Link 2), `spec/assignments.md` (Predicate vocabulary),
`guide/archive/assignment_rule_clarify.md` (Item 2, the mapping this
replaces)

A standalone plan at the author's naming, not a `segment_*.md`, in the
shape of `guide/archive/assignment_rule_clarify.md`: the item carries
its own `### Doc impact` and `### Status`, checked by hand at close
(`tools/close_check.py` reads only `segment_*` files).

---

## Item 1 — A relationship tag judges the pair, in Link 2 only

### Opportunity

Since `guide/archive/assignment_rule_clarify.md` Item 2 (#3088–#3091),
one "Pair: …" option means two different things, depending on the Link
and the operator (`spec/instruments.md`, Band 1):

| Where | Operators | Judges |
|---|---|---|
| Link 1 field | all four | the reviewer: any of their active pairs carries it |
| Link 2 field | `IS` / `IS NOT` | the pair being judged |
| Link 2 field | `IS THE SAME AS` / `IS DIFFERENT FROM` / `IS FILLED` / `IS EMPTY` | the reviewee: any of their active pairs carries it |
| Link 2 operand | `IS THE SAME AS` / `IS DIFFERENT FROM` | the reviewer, the same way |

The card shows the difference only by a caption ("Pairwise tag" against
"Reviewer's tag" / "Reviewee's tag"). The author (2026-10-18): a
relationship tag's intended use is to impose a pair, as an assignment or
an exclusion, and the card should make that the only reading.

The same review found a use the card cannot express: imposing a pair
because the tag holds **any** value, without naming the value. Today
`IS FILLED` / `IS EMPTY` on a Link 2 relationship tag judge the reviewee,
not the pair.

### Decision

A relationship tag is offered **in Link 2 only**, and every operator on
it judges the pair (`pair_context.tagN`):

| Operator | Keeps | Use |
|---|---|---|
| `IS` *v* | exactly the pairs tagged *v* | assign by value (unchanged) |
| `IS NOT` *v* | every pair except those tagged *v* | exclude by value (unchanged) |
| `IS FILLED` | exactly the pairs carrying any value | assign by any value (new) |
| `IS EMPTY` | every pair except those carrying a value | exclude by any value (new) |

- `IS THE SAME AS` / `IS DIFFERENT FROM` leave a relationship-tag cell's
  cycle, and a relationship tag stops being offered as their operand.
  The cross-side operators then compare roster tags only.
- **Link 1 offers no relationship tag** (author, 2026-10-18). Link 2
  already decides which reviewer–reviewee pairs exist, and Links 1 and 2
  intersect, so a person-level Link 1 rule adds nothing a pair rule
  cannot say. It only reintroduces the second reading.
- The caption reads "Pairwise tag" for all four operators.
- The engine needs no new logic: `is_not_empty` / `is_empty` on
  `pair_context.tagN` already pass on some value / no value
  (`spec/assignments.md`, "Values and empty values").

Rejected: keeping the person-level readings and relabelling them more
loudly. The author's point is that the reading should not depend on the
operator at all. A caption the operator has to notice is the problem
being removed, not a fix for it.

### Semantics

- **`IS FILLED` keeps pairs one by one**, like `IS`, so it joins `IS` in
  the Group guard. While Link 2 holds either, Link 3 skips Group, and
  Save and the Settings import refuse a Group with one
  (`keeps_pairs_by_pair_tag` gains `is_not_empty`). `IS EMPTY`, like
  `IS NOT`, leaves Group available and drops only the ruled-out member's
  row.
- **A pair with no relationship row** has no value, so it fails `IS` and
  `IS FILLED` and passes `IS NOT` and `IS EMPTY`, as today. An inactive
  relationship counts as no row.
- **Stored rules the card no longer offers.** These are a Link 1
  relationship tag, a `reviewer.pair_tagN` / `reviewee.pair_tagN` field,
  and a relationship-tag operand. Each shows as its stored tag, the way
  a stored-only option shows today. Save refuses the instrument with
  its banner until the rule is removed, and a Settings import refuses it
  too (Open question 1). A rewrite would silently change who reviews
  whom. Pre-Azure sessions are disposable (author, 2026-10-17), so there
  is no migration.

### Judgment calls — decided

- No migration of stored rules (author, 2026-10-17, pre-Azure).
- Link 2 cycle order for a relationship-tag cell: `IS` → `IS NOT` →
  `IS FILLED` → `IS EMPTY`, opening on `IS`, the value use.

### Blast radius (measured)

Taken 2026-10-18 at `928dbc15`.

- Files under `app/` naming `pair_tag`: 8
  (`git grep -l pair_tag -- app/`). In scope are the four that are rules:
  - `app/services/instruments/_band1.py` (`_engine_field`, `_card_key`,
    `keeps_pairs_by_pair_tag`);
  - `app/services/rules/fields.py`;
  - `app/services/rules/predicates.py`;
  - `app/schemas/rules.py`.

  The Assignments page's `pair_tag_N` sort keys
  (`_assignments.py`, `_coverage.py`, `session_assignments.html`) are a
  different thing and untouched.
- Card: `app/web/templates/operator/instruments_index.html`, where the
  Link 1 options, the Link 2 cycle and operand list, and the caption
  live. `grep -n pair_context app/web/templates/operator/instruments_index.html`
  lists them.
- Settings import: `app/services/session_config_io/_apply_parse.py`.
- Tests naming `pair_tag`: 8 files (`git grep -l pair_tag -- tests/`).
- Live specs: `spec/instruments.md`, `spec/assignments.md`,
  `spec/setup_pages.md` (the Relationships row names Link 1 and Link 2)
  and `spec/csv_contracts.md` (the grouped-import refusal names `IS`
  only). The search: `git grep -l -i -e pair_tag -e "Pair: " -e "Pairwise tag" -e "relationship tag" -e "relationship-tag" -- 'spec/*.md' 'docs/*.md' ':!docs/archive' ':!spec/archive'`.
  It also matches `spec/settings_inventory.md`, for a browser
  preference only; that one is untouched.

### Status

- 2026-10-18: Open question 1 ruled **retire** (author). Rung 3 goes ahead.
- Rung 2 (card and Save): Save stores a relationship tag as is and
  refuses the three unoffered shapes through one helper,
  `unoffered_pair_rule` in `app/services/instruments/_band1.py`, which
  rung 3's import refusal reuses. A stored person-level rule shows as
  "Reviewer's pair tag: …" / "Reviewee's pair tag: …".

### PR ladder

1. **This plan** (prose).
2. **Card and Save.** Remove the Link 1 relationship tags and the
   cross-side operators and operand on a relationship-tag cell. Make
   `IS FILLED` / `IS EMPTY` store as `pair_context.tagN`. Extend the
   Group guard. Make Save refuse a stored rule the card no longer offers.
   Must not touch the rules engine.
3. **Engine and import**. Remove
   `reviewer.pair_tagN` / `reviewee.pair_tagN` from
   `ALLOWED_PREDICATE_FIELDS` and the resolvers, and make the Settings
   import refuse them. Update the specs and close.

### Definition of done

- `spec/instruments.md` Band 1 states one pair-level reading for a
  relationship tag, Link 2 only, with the four-operator table above.
- `spec/assignments.md` Predicate vocabulary matches (and, if retired,
  no longer lists the person-level fields).
- Tests pin `IS FILLED` / `IS EMPTY` as assign / exclude on a Link 2
  relationship tag, the Group guard on `IS FILLED`, and Save's refusal
  of a Link 1 relationship-tag rule.
- `### Doc impact` present and current; `### Status` compacted at close.

### Open questions

1. ~~Retire `reviewer.pair_tagN` / `reviewee.pair_tagN` from the
   engine, or keep them for Settings imports?~~ Retire (author,
   2026-10-18).

### Out of scope

- A group-scoped instrument that includes or excludes a whole group by
  a member's tag, pair tags included: a deferred idea in
  `guide/group_membership_rules.md`, whose Exceptions block could move
  relationship tags out of the Links altogether (its Open question 3).
- The Relationships page, and pair-tag display fields on the reviewer
  surface.

### Doc impact

- `spec/instruments.md` — Band 1: relationship tags in Link 2 only, the four pair-level operators, the caption, `IS FILLED` in the Group guard, stored-rule refusal (Item 1).
- `spec/assignments.md` — Predicate vocabulary: Band 1 stores a relationship tag only as `pair_context.tagN`; the person-level fields retired or marked import-only per Open question 1 (Item 1).
- `spec/setup_pages.md` — Relationships row: its tags are offered in Band 1's Link 2 only (Item 1).
- `spec/csv_contracts.md` — §3.3: the grouped-import refusal covers a relationship-tag `IS FILLED` as well as `IS`, and a person-level pair field if retired (Item 1).
