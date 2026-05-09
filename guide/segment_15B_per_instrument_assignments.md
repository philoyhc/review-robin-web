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

### Slice 2 — RuleSet scope decision (1 PR, ~150 LOC)

`RuleSet` is currently session-scoped (`rule_sets.session_id`). Two
options:

- **Per-instrument override on top of a session default.** Add
  nullable `instrument_id` to `rule_sets`; resolution reads the
  instrument override first, falls back to the session-level
  RuleSet. Mirrors the email-template-overrides pattern.
- **Strictly per-instrument.** Replace `rule_sets.session_id` with
  `rule_sets.instrument_id`. Simpler, but every existing seeded
  RuleSet needs to be either duplicated per instrument or
  retrofitted to "applies to all instruments" with a sentinel.

Recommend the override pattern — preserves the "apply once to all
instruments" affordance for operators who don't care about
per-instrument differences, while keeping the per-instrument escape
hatch for operators who do.

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
  per-instrument tab gets its own Rule Based card (consuming the
  Slice 2 RuleSet override) and its own manual CSV upload.

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

---

## Risks + open questions

- **Existing data migration.** Sessions with multiple instruments
  today have N copies of every Assignment (one per instrument)
  with identical context / include. After Slice 1, those copies
  remain identical until an operator divergent-edits them — no
  migration needed, but the audit log will show "no-op" assignment
  replays from the first divergent edit. Acceptable.
- **RuleSet seed migration.** Slice 2's seeded RuleSets (Full
  Matrix etc.) need to either stay session-level or be cloned
  per-instrument on `ensure_default_instrument`. Recommend keeping
  them session-level (the most common case is operators wanting
  the same rules everywhere), and let per-instrument overrides be
  the explicit opt-in.
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
  `app/db/models/rule_set.py` (gain optional `instrument_id`),
  `app/web/routes_operator/_assignments.py`,
  `app/web/routes_operator/_quick_setup.py`,
  `app/web/views/_rule_builder.py` + `_quick_setup.py`,
  `app/web/templates/operator/session_assignments.html`,
  Alembic migration (one column add to `rule_sets`).
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
  - Slice 2: `test_rule_set_instrument_override.py` — resolution
    order (instrument override → session default).
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
