# Segment 13B — Sort by reviewee

Implementation plan for the reviewer-surface sort UX:
operator-side default sort + reviewer-side live override on the
per-instrument response table. Layers on top of the canonical
functional spec at [`spec/sort_by_reviewee.md`](../spec/sort_by_reviewee.md);
this plan handles sequencing, schema, audit wiring, and PR
slicing — the spec owns the user-visible model (display-fields-
only operator picker, click semantics, multi-key cascade,
reviewer live-only persistence).

> **Renamed 2026-05-07** from `segment_13B_instrument_enhance.md`.
> The "instrument-enhancements basket" framing collapsed once
> the second item — group-scoped instruments + duplicate-
> instrument — got its own plan at
> `guide/segment_13C_enhanced_instrument.md`. 13B is now
> single-purpose: sort.

## Status

Planning. Sized as **3 PRs** in dependency order:

1. **PR 1 — Schema + read path.** Add `Instrument.sort_display_fields`
   JSON column (`Mapped[list[dict] | None]`). Backfill helpers
   that return `[]` for `NULL`. Reviewer surface reads the
   column and passes a sort spec into the per-instrument render
   adapter (no UI change yet — operators have no way to populate
   the column).
2. **PR 2 — Operator UI: tri-state Sort column.** Adds the
   "Sort" column to the per-instrument Display Fields table
   (only — no equivalent on Response Fields, per the spec).
   Click-to-promote + click-to-reverse + click-to-demote, max 3
   keys, display fields only. Save persists to
   `Instrument.sort_display_fields`; emits the new
   `instrument.sort_fields_updated` audit event.
3. **PR 3 — Reviewer-side live override.** Clickable column
   headers on the reviewer surface (display + response columns).
   Live-only persistence (no localStorage, no per-reviewer
   server state). Refresh returns to the operator default.
   Header arrows reflect the live sort state.

Sequencing rationale:

- PR 1 is infrastructure-only: schema + read path + tests
  pinning the default-empty-array behaviour. No operator
  affordance, no reviewer-visible change. Lets the reviewer-
  surface render adapter ship its sort-aware code path against
  a `NULL` column without any operator able to break it.
- PR 2 is the operator-facing PR. Once it lands, sessions whose
  operators configure sort get a deliberate default order.
- PR 3 lights up the reviewer-side override on top of PR 2's
  default. Independent of PR 2 in code (a separate column-
  header set), but PR 2 ships first because the operator
  default is the load-bearing experience.

Each PR ships independently on top of `main`. PR 1 + PR 2 can
fold if the schema is small and the operator UI is ready; PR 3
is its own PR.

## Relationship to Segment 13A and 13C

13A, 13B, and 13C are siblings — independent of each other,
shippable in any order. Together they cover the original
"Segment 13 — rule-based assignment + sort UX" framing in the
master workplan, plus the group-scoped enhancement that surfaced
later.

- **13A** — rule-based assignment generation (Advanced mode +
  seed library + editor + retire Full Matrix card). Plan at
  [`segment_13A_rulebased_assignment_builder.md`](segment_13A_rulebased_assignment_builder.md).
- **13B** (this segment) — sort by reviewee.
- **13C** — group-scoped instruments + duplicate-instrument
  button. Plan at
  [`segment_13C_enhanced_instrument.md`](segment_13C_enhanced_instrument.md).

The three segments touch different surfaces:

- 13A — assignments page; new `RuleSet` schema.
- 13B — instrument card's Display Fields table + reviewer-
  surface table headers; new `Instrument.sort_display_fields`
  JSON column.
- 13C — instrument card's action-row buttons; new
  `Instrument.group_kind` column + `Assignment.context` keys
  (no `Response` schema change).

No cross-dependencies in either direction.

## Schema

One new JSON column on `Instrument`:

```python
sort_display_fields: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
```

Documented value shape (from `spec/sort_by_reviewee.md`):

```json
[
  {"display_field_id": 7, "dir": "asc"},
  {"display_field_id": 12, "dir": "desc"}
]
```

`NULL` and `[]` both mean "no operator-configured sort"
(insertion order — today's behaviour). Up to 3 entries.
Validator on save enforces:

- Length ≤ 3.
- Each `display_field_id` belongs to **this instrument's**
  display fields (cross-instrument display-field IDs rejected).
- No duplicate `display_field_id` within the list.
- `dir` ∈ `{"asc", "desc"}`.

Migration: pure additive nullable column; no backfill, no
default beyond the column default.

## Audit event

`instrument.sort_fields_updated` — emitted by PR 2's save path
when `sort_display_fields` changes. Detail follows the canonical
envelope from Segment 11K (the audit-event detail schema shipped
2026-05-07):

```python
audit.changes(
    {"sort_display_fields": [before, after]},
    session=review_session,
)
```

PR 2 registers the event_type in `audit_service.EVENT_SCHEMAS`
per the 11K convention.

## Out of scope

- **Sort by computed values** (cross-table joins, response
  aggregates) — not covered by the spec.
- **Cross-instrument session-wide sort** — each instrument has
  its own sort.
- **More than 3 sort keys** — keep the cognitive load low.
- **Persisted reviewer overrides** — live-only by spec.
- **An "apply sort to every instrument" bulk control** — not
  in the first cut.

## PR-by-PR sketch

### PR 1 — Schema + read path

- Alembic migration: add `instruments.sort_display_fields`
  (JSON, nullable). One-liner; no backfill.
- `Instrument.sort_display_fields` Mapped column.
- `views.build_reviewer_surface_context` (or wherever the per-
  instrument render adapter lives) reads
  `instrument.sort_display_fields or []` and passes a sort spec
  into the row-ordering helper.
- New row-ordering helper
  `views.order_assignments_by_sort_spec(assignments, sort_spec)`
  — pure function, sorts a list of assignment-shaped row tuples
  by the spec's keys (cascade by list order). NULLs sort last
  regardless of direction (per spec §"NULL handling").
- Tests:
  - Migration round-trip (SQLite + Postgres) pinning the new
    column persists.
  - Helper unit tests on cascade + NULL handling + asc/desc.
  - Reviewer-surface integration test: when
    `sort_display_fields` is `NULL` or `[]`, row order is
    unchanged from today (insertion order).

### PR 2 — Operator UI: tri-state Sort column

- New "Sort" column on the per-instrument Display Fields table
  (`spec/instruments.md` Section B). Display fields only —
  Response Fields rows do not get a Sort cell (per spec
  §"Scope on the operator side").
- Click semantics per spec §"Operator UI: tri-state Sort
  column": unsorted → asc → desc → unsorted; clicking a sorted
  column promotes / demotes within the cascade order (max 3).
- Operator state lives in `[(display_field_id, dir), ...]` —
  serialised in a hidden form field and submitted with the
  bulk-save round-trip the card already uses.
- Save validator (route layer) refuses lists > 3 / duplicates
  / cross-instrument IDs / unknown `dir` values.
- New audit event `instrument.sort_fields_updated` registered
  in `EVENT_SCHEMAS`.
- Tests:
  - Tri-state click cycle + promote/demote/swap.
  - Validator rejects each documented invalid input.
  - Audit event fires on diff; no emit on no-op save.
  - Reviewer-surface integration test confirms a configured
    sort propagates into the rendered row order.

### PR 3 — Reviewer-side live override

- Clickable column headers on the reviewer-surface table —
  display columns + response columns (per spec §"Reviewer UI:
  clickable column headers, live-only override"). Tri-state
  cycle, multi-key cascade with shift-click (or click-twice
  semantics if shift-click is awkward — pick at implementation
  time).
- Live-only: state lives in JS memory; refresh returns to
  operator default. No localStorage, no server-side per-
  reviewer state, no audit event (per spec §"Persistence: live
  only").
- Header arrows reflect the live state; the operator default
  arrows render server-side, the live overrides take effect on
  the first click.
- Tests:
  - JS unit test (or DOM-rendered integration) on cycle +
    cascade.
  - Server-side render unchanged when no override is in play
    (regression for PR 2's persistence contract).

## Doc impact

When 13B kicks off:

- Update `spec/operator_ui_concept.md` Display Fields section
  to describe the new Sort column.
- Update `spec/reviewer-surface.md` to describe the header-
  click override.
- Update `guide/todo_master.md` to move 13B from Upcoming to
  in-progress; move to Done when PR 3 lands.
- Migrate this file to `guide/archive/` when PR 3 merges.
- `spec/sort_by_reviewee.md` ticks off its "Implementation
  pointers" section.
