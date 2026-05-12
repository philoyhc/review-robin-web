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

Planning — refreshed 2026-05-12 against the as-shipped 13D
scaffolding. **Schema already in place** since Segment 13D
PR 5 (`instruments.sort_display_fields` JSON column, NULL by
default), so PR 1 of this plan no longer needs to author the
migration. Settings CSV import/export round-trips the column
already (`app/services/session_config_io.py` lines 330-331 +
1020-1021), so the porting story is also covered.

Sized as **3 PRs** in dependency order:

1. **PR 1 — Reviewer-surface read path + service writer
   (sort spec consumption + validator).** Schema column
   already exists; the work here is:
   - Update the column's docstring to match the canonical
     spec shape (currently drifted — says `source_type` /
     `source_field` / `direction`, should say
     `display_field_id` / `dir`).
   - New service helper
     `instruments.set_sort_display_fields(db, *, instrument,
     fields, user, correlation_id)` with the validator
     (length ≤ 3, IDs belong to this instrument, no
     duplicates, `dir ∈ {"asc", "desc"}`), lifecycle-
     invalidation hook, and emit of the new
     `instrument.sort_fields_updated` audit event.
   - Register `instrument.sort_fields_updated` in
     `EVENT_SCHEMAS`.
   - Reviewer-surface render adapter reads
     `instrument.sort_display_fields or []` and passes a sort
     spec into the row-ordering helper.
   - New pure-function helper
     `views.order_assignments_by_sort_spec(rows, sort_spec)`
     ordering assignment-shaped row tuples by the spec's keys
     (cascade by list order; NULLs sort last regardless of
     direction per spec §"NULL handling"; unknown-id entries
     skip with a fallback to insertion order per
     spec §"Render-time defense").
   - Tests pin: NULL/empty render unchanged (insertion order);
     single-key asc/desc; cascade; NULL handling; unknown-id
     defense; service validator rejects each documented
     invalid input; audit event fires on diff; no emit on
     no-op save; lifecycle-invalidates.
2. **PR 2 — Operator UI: tri-state Sort column.** Adds the
   "Sort" column to the per-instrument Display Fields table
   (only — no equivalent on Response Fields, per the spec).
   Click-to-promote + click-to-reverse + click-to-demote, max
   3 keys, display fields only. Save passes the operator's
   `[(display_field_id, dir), ...]` list into PR 1's
   `set_sort_display_fields` service writer.
3. **PR 3 — Reviewer-side live override.** Clickable column
   headers on the reviewer surface (display + response
   columns). Live-only persistence (no localStorage, no
   per-reviewer server state). Refresh returns to the operator
   default. Header arrows reflect the live sort state.

Sequencing rationale:

- PR 1 ships infrastructure end-to-end: validator + service
  writer + reviewer-surface render-path consumer + audit
  event. No operator UI yet — the column populates only
  through Settings CSV import or direct DB edits during PR 1,
  but the render path is ready to honour whatever value lands
  in the column.
- PR 2 is the operator-facing PR. Once it lands, sessions
  whose operators configure sort get a deliberate default
  order.
- PR 3 lights up the reviewer-side override on top of PR 2's
  default. Independent of PR 2 in code (a separate column-
  header set), but PR 2 ships first because the operator
  default is the load-bearing experience.

Each PR ships independently on top of `main`. PR 1 + PR 2 can
fold if the validator + render path is small and the operator
UI is ready; PR 3 is its own PR.

## Relationship to Segment 13A and 13C

13A, 13B, and 13C are siblings — independent of each other,
shippable in any order. Together they cover the original
"Segment 13 — rule-based assignment + sort UX" framing in the
master workplan, plus the group-scoped enhancement that surfaced
later.

- **13A** — rule-based assignment generation (Advanced mode +
  seed library + editor + retire Full Matrix card). Plan at
  [`archive/segment_13A_rulebased_assignment_builder.md`](archive/segment_13A_rulebased_assignment_builder.md).
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

**Already shipped.** Segment 13D PR 5 (#701, 2026-05-09)
added the JSON column on `Instrument`:

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
PR 1's service-layer validator on save enforces:

- Length ≤ 3.
- Each `display_field_id` belongs to **this instrument's**
  display fields (cross-instrument display-field IDs rejected).
- No duplicate `display_field_id` within the list.
- `dir` ∈ `{"asc", "desc"}`.

> **Docstring drift to fix in PR 1.** The column docstring in
> `app/db/models/instrument.py` was written against an earlier
> design (`source_type` / `source_field` / `direction` keys).
> The canonical shape is `display_field_id` / `dir` per the
> functional spec; PR 1 updates the docstring.

CSV round-trip already covered: `session_config_io.py`
serialises the column as the `Instruments.sort_display_fields`
key in Settings CSV (lines 330-331 export, 1020-1021 import).
No additional porting work needed in 13B.

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

### PR 1 — Reviewer-surface read path + service writer

Schema column already in place since 13D PR 5. Round-trip
tests already pin NULL / empty / populated persistence at
`tests/integration/test_instrument_sort_display_fields_schema.py`.
This PR adds the consumer (render path) + writer (service
validator) so the column stops being inert.

- **Docstring fix.** Update `Instrument.sort_display_fields`
  docstring to match the canonical
  `{"display_field_id": N, "dir": "asc|desc"}` shape (drifted
  from a prior design pass — calls out
  `source_type` / `source_field` / `direction` today).
- **Service writer.** New
  `instruments.set_sort_display_fields(db, *, instrument,
  fields, user, correlation_id)` in
  `app/services/instruments/_instrument_crud.py` (or a sibling
  module if scope fits cleaner — decide at scoping):
  - Accepts `fields: list[tuple[int, str]]` (display_field_id,
    dir) pairs.
  - Validator: length ≤ 3, each id ∈ this instrument's
    display fields, no duplicates, `dir ∈ {"asc", "desc"}`.
  - Idempotent: returns early on no-op (same fields). PR 1
    tests pin "no emit on no-op save."
  - Lifecycle-invalidation hook (per
    `invalidate_if_validated` convention).
  - Emits `instrument.sort_fields_updated` audit event with
    canonical envelope:
    `audit.changes({"sort_display_fields": [before, after]},
    session=review_session)`.
- **Audit registration.** New event_type
  `instrument.sort_fields_updated` in
  `audit.EVENT_SCHEMAS` (`_IDENTITY | {"changes"}`).
- **Reviewer-surface render-path consumer.** Wherever the
  per-instrument render adapter loops rows
  (`app/web/views/_responses.py` or the analogous reviewer-
  side helper), thread the sort spec from
  `instrument.sort_display_fields or []` through the row
  ordering. PR 1 confirms the threading on a fixture; PR 2's
  operator UI provides the live operator-set values.
- **Row-ordering helper.** New pure function
  `views.order_assignments_by_sort_spec(rows, sort_spec)` in
  `app/web/views/_audit_log.py`'s sibling module (TBD at
  scoping — likely `app/web/views/_reviewer_surface.py` if
  it exists, otherwise a new `_sort.py`):
  - Cascade by list order (first entry primary, second
    secondary, etc.).
  - NULLs sort last regardless of direction
    (per spec §"NULL handling").
  - Unknown-id entries (referenced display field no longer
    exists) skip with a fallback to the next-priority slot,
    then insertion order
    (per spec §"Render-time defense").
- **Tests.**
  - **Unit (helper).** NULL/empty input → unchanged order;
    single-key asc/desc; multi-key cascade; NULL value
    handling regardless of direction; unknown-id entry
    skipped + falls to next slot.
  - **Unit (service writer).** Validator rejects each
    documented invalid input (length 4, duplicate id,
    cross-instrument id, unknown dir); audit event fires on
    diff; no emit on no-op save; lifecycle-invalidates when
    the session was previously validated.
  - **Integration (reviewer surface).** When
    `sort_display_fields` is `NULL` or `[]`, row order is
    unchanged from today (insertion order). When populated,
    rows render in the spec's order.

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
- Save route passes the parsed list straight into PR 1's
  `instruments.set_sort_display_fields` service writer (which
  owns the validator + lifecycle hook + audit emission).
  Validation errors bubble up as banner errors on the page.
- Tests:
  - Tri-state click cycle + promote/demote/swap.
  - Route layer surfaces the service writer's validation
    errors as banners (rejection cases pin against the PR 1
    error codes / messages).
  - Reviewer-surface integration test confirms a configured
    sort propagates into the rendered row order via PR 1's
    render-path consumer.

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
