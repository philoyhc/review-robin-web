# Segment 15B — Per-instrument assignments

**Status:** Plan stub (2026-05-09).
**Sizing:** ~1 segment-sized chunk (5-7 PRs).
**Depends on:** none strictly required, but **15A first** is
recommended so the per-instrument assignment UI can consume the
session-level friendly-label resolver without re-introducing
hardcoded literals.

---

## Goal

Let each `Instrument` have its own assignment set, so that (for
example) "the Manager survey" can collect different reviewer →
reviewee pairings than "the Peer survey" within the same session.
Today, every instrument shares the session's single assignment list.

---

## Why now

The schema **already supports** per-instrument assignments. From
`app/db/models/assignment.py:22-43`:

```
__table_args__ = (UniqueConstraint(
    "session_id", "reviewer_id", "reviewee_id", "instrument_id",
    name="uq_assignment_unique",
),)
```

`Assignment` carries `instrument_id` as a non-null FK, and the
unique constraint includes it — so the same `(reviewer, reviewee)`
pair coexists across instruments by design. The reviewer surface
already iterates Assignment rows per instrument
(Segment 11D follow-on shipped this multi-instrument render).

What blocks per-instrument assignments today is the **service
layer**, not the schema:
`app/services/assignments.py::replace_assignments` (around line
574-583) takes a single `pairs` list and **fans out across every
instrument in the session** with the same `context` and `include`
replicated identically per fan-out. That uniform fan-out is a
policy choice that made sense when every session had one
instrument; it's now the only thing standing between the schema
and the feature.

---

## Approach

### Slice 1 — Service-layer scope (1 PR, ~200 LOC)

Replace the single fan-out in `replace_assignments` with a
per-instrument scope. Two API options:

- **A (recommended).** Add an `instrument_id` parameter; default
  `None` keeps current behaviour (apply to every instrument).
  Callers that want per-instrument behaviour pass an explicit id
  and call once per instrument.
- **B.** Replace the `pairs` parameter with
  `pairs_by_instrument: dict[int, list[…]]`; backfill an
  "all instruments" key for the existing call site.

Recommend A — smaller blast radius, every existing call site stays
behaviour-compatible without touching the parameter shape.

Also touch:
- `assignments.existing_count`,
  `assignments.delete_session_assignments`,
  `csv_imports.parse_manual_csv` — gain optional `instrument_id`
  filters.
- `monitoring.per_reviewer_coverage` — already iterates Assignment
  rows; just confirm the instrument-scope is honoured in the
  pivot.

Audit envelope stays unchanged; the existing `instrument_id` field
inside `assignments.replaced` payload (already part of 11K's
canonical schema for this event family) starts carrying
real per-instrument variation.

### Slice 2 — Persist the per-instrument RuleSet selection (1 PR, ~150 LOC)

**Today.** RuleSets are owned at the user-library level
(`rule_sets.scope ∈ {seed, personal}` + `owner_user_id`) and
visible across all of an operator's sessions. There is **no
stored "current RuleSet" pointer** — the operator picks a
RuleSet in the Rule Builder UI, hits Generate, and the choice is
used inline for one-shot generation but not persisted.

**Goal.** Make the selection persistent and per-instrument: each
instrument records the RuleSet currently in effect for it.

**Schema dependency.** `instruments.rule_set_id` (nullable FK,
`ON DELETE SET NULL`) is pre-positioned by **Segment 13D PR 2**
(see `segment_13D_db_prep.md` for the FK-direction rationale).
This slice is pure service / route work — no migration in 15B.

**Service-layer change.** `replace_assignments` (touched in Slice
1) accepts `instrument_id` and writes the chosen
`rule_set_id` onto that instrument row alongside the new
Assignment rows. The Rule Builder POST handlers
(`app/web/routes_operator/_rule_builder.py`) thread the
`instrument_id` from the URL through into the persistence call.

**Resolution semantics.** No "session default + per-instrument
override" inheritance — the column is the single source of
truth per instrument. NULL = "no RuleSet currently applied to
this instrument" (initial state for every existing instrument
post-13D PR 2; also the state after a reset-assignments action).
A future **session-level default** (e.g. a
`sessions.default_rule_set_id` column to seed new instruments
from) is left out of this segment; revisit if operator feedback
asks for it. Most teams will set the same RuleSet on every
instrument, which works fine without inheritance.

**FK behaviour wired through to the UX:**

- **Delete instrument** (existing 10D action): the instrument's
  pointer dies with the row; the RuleSet is untouched. No UX
  warning needed beyond what 10D already shows.
- **Delete RuleSet** (operator removes from their library, 13A
  action): SQL `SET NULL` on every `instruments.rule_set_id`
  pointing at it. **UX gate to add in this slice:** the existing
  Rule-Builder delete-confirm dialog grows a line listing every
  instrument across every session that currently applies the
  RuleSet ("Deleting will clear this rule from N instrument(s):
  [list]. Their next assignment generation will require choosing
  a new rule.").
- **Reset an instrument's assignments** (a new 15B affordance):
  `UPDATE instruments SET rule_set_id = NULL WHERE id = ?` plus
  the existing assignment-row delete. RuleSet untouched.

### Slice 3 — Manual-assignment CSV column (1 PR, ~100 LOC)

`parse_manual_csv` today reads `(ReviewerEmail, RevieweeEmail,
PairContext1, PairContext2, PairContext3)`. Add an optional
`Instrument` column (matched against `Instrument.short_label` first,
then `Instrument.name`). Empty value → "all instruments" (current
behaviour, preserves backwards compatibility for existing files).

Validation: unknown instrument label → row-level
`ValidationIssue` from the existing CSV-import error pipeline,
same shape as unknown-reviewer / unknown-reviewee errors.

### Slice 4 — Assignments page UI (2 PRs, ~600 LOC total)

The Assignments page becomes per-instrument. Two PR sub-slices:

- **4a — Per-instrument tabs / cards.** A tab strip per instrument
  (consume `Instrument.short_label` via `views.page_button_label`)
  + an "All Instruments" tab showing the union (read-only) when
  multiple instruments diverge.
- **4b — Per-instrument Rule Based card + Manual upload.** Each
  per-instrument tab gets its own Rule Based card (the picker
  writes through to `instruments.rule_set_id` per Slice 2) and
  its own manual CSV upload.

Operators who don't care about per-instrument differences keep an
"apply to all" affordance — a button at the top of the All
Instruments tab that promotes the current selection to a session
default.

### Slice 5 — Quick Setup card (1 PR, ~100 LOC)

`/operator/sessions/{id}` Quick Setup Assignments slot grows the
same instrument selector as a `<select>` in front of the file
input + Generate button. Default = "All instruments" (current
behaviour). Audit/lifecycle wiring is already in place from
Segment 11J.

### Slice 6 — Validation + reviewer-surface confirmation (1 PR, ~100 LOC)

`validate_session_setup` already checks "every reviewer has ≥1
assignment". That generalises naturally — no schema change, but
the per-instrument breakdown should surface in the Validate page
(e.g. "Alice is missing assignments for the Peer survey"). Add a
new `ValidationRule` keyed
`assignments.reviewer_missing_for_instrument`.

The reviewer surface is already multi-instrument-aware (Segment
11D follow-on shipped this); it'll naturally show empty pages for
instruments where the reviewer has no assignments. Confirm via a
manual smoke test on the dev slot — there's no template change
needed, but the empty-state copy may want polish.

### Slice 7 (deferred — only on real use case) — `AssignmentContext1-3`

**Out of 13D scope by design.** 13D's DB-prep segment explicitly
*does not* pre-position columns for AssignmentContext (see
`segment_13D_db_prep.md` scope-sweep table); this slice owns the
schema + service + UI work end-to-end if it ever lands.

**Semantics (locked 2026-05-09).** AssignmentContext is logic-
bearing per-assignment information (e.g. "this assignment is for
Award X category") that drives downstream filtering, reporting,
or rule evaluation. Distinct from `PairContext1-3` which is
display-only info about a (reviewer, reviewee) pairing (e.g.
"she was your student in NN1101"). The two have categorically
different infrastructure needs — labels for PairContext (handled
in 15A); rule-engine integration for AssignmentContext.

**Why deferred.** Most use cases for logic-bearing per-assignment
fields are derivable from existing reviewer + reviewee tags
evaluated through the rule engine. This slice should only land
when a real use case surfaces that **cannot** be expressed via
tags + rules.

**If it lands, it needs (in one PR-sized slice):**

1. **Schema.** Add `assignment_context_1 / _2 / _3 VARCHAR(255)`
   columns on `Assignment` (mirrors the tag pattern, plays well
   with CSV) **or** reserve well-known keys
   `assignment_context_1/2/3` inside the existing
   `Assignment.context` JSON dict (cheaper but harder to type and
   to import / export). Recommendation at write time: named
   columns.
2. **Rule-engine integration.** New predicate operands so RuleSets
   can filter / quota / order on AssignmentContext values. Touches
   `app/services/rules/engine.py` + the Rule Builder UI.
3. **CSV import column.** Manual-assignment CSV grows
   `AssignmentContext1` / `2` / `3` columns alongside the existing
   `PairContext1-3`.
4. **Friendly labelling.** Once the columns exist, plumb them into
   the 15A resolver (add `assignment_context` to the `source_type`
   enum). The Settings editor subsection picks them up
   automatically.

**Triggering criterion.** Surface a concrete operator request
that fails the "can this be expressed via reviewer + reviewee tags
plus rules?" sniff test before authoring the slice.

---

## Risks + open questions

- **Existing data migration.** Sessions with multiple instruments
  today have N copies of every Assignment (one per instrument)
  with identical context / include. After Slice 1, those copies
  remain identical until an operator divergent-edits them — no
  migration needed, but the audit log will show "no-op" assignment
  replays from the first divergent edit. Acceptable.
- **Seeded RuleSets stay shared.** Seeded RuleSets (Full Matrix
  etc.) live in the workspace-level library — no migration
  needed. They're applied to instruments by setting
  `instruments.rule_set_id` to the seed's id, same mechanism as
  any Personal RuleSet. Multiple instruments (across multiple
  sessions, even) can point at the same seed; deleting a seed is
  not an operator-facing action so the `SET NULL` cascade only
  fires for Personal RuleSet deletes.
- **Email invitations.** Reviewer-scoped, not instrument-scoped.
  No change needed — reviewers receive one invitation per session
  regardless of how their assignments break down by instrument.
- **CSV export.** When Segment 12A export ships, the manual-CSV
  shape gains the `Instrument` column for sessions where it's
  populated. Pin that in the 12A spec when this segment lands.

---

## Critical files

- Touched: `app/services/assignments.py`,
  `app/services/csv_imports.py`,
  `app/services/rules/library.py`,
  `app/services/rules/engine.py`,
  `app/services/validation.py`,
  `app/web/routes_operator/_assignments.py`,
  `app/web/routes_operator/_rule_builder.py`,
  `app/web/routes_operator/_quick_setup.py`,
  `app/web/views/_rule_builder.py` + `_quick_setup.py`,
  `app/web/templates/operator/session_assignments.html`.
- Schema dependency only: `instruments.rule_set_id` is
  pre-positioned by Segment 13D PR 2 (`SET NULL` on RuleSet
  delete). No migration in this segment.
- Possibly touched in Slice 6: `app/web/views/_validate.py`,
  `app/web/templates/operator/session_validate.html`.

---

## Verification

- `pytest -q` green on SQLite + `ci-postgres` after each slice.
- `ruff check .` green.
- New tests per slice:
  - Slice 1: `test_assignments_service.py` regression tests for the
    `instrument_id=None` (apply to all) vs. per-instrument paths;
    audit-event payload assertions.
  - Slice 2: `test_instrument_rule_set_persistence.py` — choosing
    a RuleSet writes `instruments.rule_set_id`; Reset clears it
    back to NULL; deleting the RuleSet clears every pointer to it
    via SQL `SET NULL` (the schema-level cascade is covered by
    13D PR 2's schema test, but the route-level UX warning copy
    also lands here).
  - Slice 3: `test_manual_csv_per_instrument_column.py` — happy
    path + unknown-instrument error.
  - Slice 4 / 5: existing assignment-page integration tests
    parameterised over single-instrument vs. multi-instrument
    sessions.
  - Slice 6: new `assignments.reviewer_missing_for_instrument`
    `ValidationRule` covered in `test_session_validate_page.py`.
- Manual smoke on the dev slot for Slice 4-6 (per-instrument tabs
  render, divergent assignments persist correctly, reviewer
  surface honours the per-instrument scope).
