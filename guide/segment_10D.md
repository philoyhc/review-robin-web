# Segment 10D — Instruments Page Rebuild

**Status:** Forward-looking plan. Frames the slice-by-slice rebuild
of the per-session **Instruments** operator page following the
spec at [`guide/instruments.md`](./instruments.md).

The label `10D` was used briefly during the mid-Segment-10B health
review and then retired into
[`guide/unfinished_business.md`](./unfinished_business.md). It's
revived here for the rebuild because the work is too coordinated
to live as a flat catalog of items but too small to be its own
fresh segment number — it's the natural follow-up to 10A
(instrument schema), 10B (instrument builder MVP), 10C (operator
UI clean-up first round).

## Why this segment

The mid-Segment-10B audit (round 3, 2026-05-01) found that the
operator's per-instrument **Display Fields** card and the
underlying schema had drifted apart: the friendly-label edits
silently discarded user input, and unconditional `pair_context`
seeding rendered three blank columns to reviewers on full-matrix
sessions. P0 fixes #13 + #14 ([PR #203](https://github.com/philoyhc/review-robin-web/pull/203))
patched the data layer; subsequent PRs ([#204](https://github.com/philoyhc/review-robin-web/pull/204)
through [#218](https://github.com/philoyhc/review-robin-web/pull/218))
stripped the legacy surface, locked down the spec, and put up the
visible frame.

This segment carries the rebuild from frame to fully-functional.

## Scope

In:

- Display Fields table (read + write).
- Response Fields table (read + write).
- Response Type Definitions card (new, full table + persistence).
- Save / Cancel / Edit state machine on each per-instrument card.
- Preview Instrument #N rendering (real reviewees + mock fallback).
- Multi-instrument enable
  ([`unfinished_business.md`](./unfinished_business.md) item #18).

Out (deferred to later segments / follow-ups):

- **Sort column UX** — semantics ("default row order on reviewer
  surface") not yet decided. Will reuse the same `▲`/`▼` reorder
  convention once the rule is pinned down.
- **Help text placement** — `instrument_response_fields.help_text`
  / `help_text_visible` exist per row in the schema; the spec
  doesn't yet say where they go in the new UI.

## Dependency map

```
                ┌──────────┐
                │ Slice 1  │  Display Fields + state machine
                └────┬─────┘
                     │
                     ▼
                ┌──────────┐
                │ Slice 2  │  Response Fields (hardcoded 4 types)
                └────┬─────┘
                     │
                     ▼
                ┌──────────┐
                │ Slice 4  │  Response Type Definitions card
                └────┬─────┘    (swaps Type column to RTD dropdown)
                     │
                     ▼
                ┌──────────┐
                │ Slice 3  │  Preview Instrument #N
                └────┬─────┘
                     │
                     ▼
                ┌──────────┐
                │ Slice 5  │  Multi-instrument enable (P0 #18)
                └──────────┘
```

Slice 3 (preview) intentionally lands after Slice 4 even though
it could ship earlier — the preview is more useful once both
field tables can actually be configured against the RTD catalog.
Slice 5 is small enough to ride at any point after Slice 1 but
sits at the end so the multi-instrument promotion behaviour can
be observed against a fully-wired single-instrument card first.

---

## Slice 1 — Display Fields table + Save / Cancel / Edit state machine

**Status:** ✅ shipped in
[PR #220](https://github.com/philoyhc/review-robin-web/pull/220).
Polish PRs that landed on top: pill colour /
status-row / flash banner clean-up
([#221](https://github.com/philoyhc/review-robin-web/pull/221)),
``email_or_identifier`` source label abbreviation + locked-row
checkbox in edit mode
([#222](https://github.com/philoyhc/review-robin-web/pull/222)),
new ``pill-success`` green for the ``Required`` pill
([#223](https://github.com/philoyhc/review-robin-web/pull/223)),
header-card action row consolidation
([#224](https://github.com/philoyhc/review-robin-web/pull/224)),
and equal-height button + restore-Alert + nav-spacing
([#225](https://github.com/philoyhc/review-robin-web/pull/225)).

Two slice-plan items were intentionally **deferred** in #220:

- The "fresh instrument starts in editable state" UX nicety —
  Slice 1 ships always-locked-unless-`?editing` instead. Operator
  clicks Edit explicitly. Revisit if the UX becomes a problem.
- The post-save flash message — replaced by the ``saved /
  not saved`` pill on the per-instrument status sub-card (#221).

**Estimated effort:** ~3-4 hrs.

This slice fixes the original P0 bug (Friendly Label persistence)
end-to-end on the new surface, and lays the state-machine substrate
that Slices 2 / 4 will reuse.

**Service / schema:**

- Extend `_VALID_DISPLAY_SOURCES` and `_DEFAULT_DISPLAY_LABELS` in
  `app/services/instruments.py` with `("reviewee", "name")` and
  `("reviewee", "email_or_identifier")`. No migration needed —
  both already exist as columns on `reviewees`.
- Extend `display_field_value` to resolve the two new sources.
- Lazy-seed the two locked rows on session creation /
  `ensure_default_instrument`. Tag them as locked so the route
  can reject `visible=False` / delete posts later.

**Template:**

- Render `instrument.display_fields | sort(attribute='order')` in
  the Display Fields table per the spec column shape (Source /
  Friendly Label / Include / Order / Sort).
- `▲` / `▼` arrow buttons in `Order` cells, suppressed for the
  Name + Email rows (per
  [#214](https://github.com/philoyhc/review-robin-web/pull/214)).
- `Include` checkbox locked-checked for Name + Email; toggleable
  for the rest.
- Inline Friendly Label edit (each row a per-row form posting to
  the existing `/display-fields/{df_id}/edit` route). The
  `db.commit()` boundary fix from
  [PR #204](https://github.com/philoyhc/review-robin-web/pull/204)
  makes these persist correctly.
- `Sort` column stays empty (`<td></td>`) for now per spec.

**State machine (URL-driven):**

- A `?editing={instrument_id}` query param toggles the per-instrument
  card from locked → editable. `Edit` button → 303 to page with
  the param + buttons toggle. `Save` button → persists via the
  existing routes + 303 to page without param + flash message.
  `Cancel` → 303 to page without param (no save).
- Brand-new instruments (no operator-typed friendly labels yet)
  open editable by default; existing instruments open locked. The
  route distinguishes via "are any operator labels non-empty".
- Session = `ready` overrides everything: the `editing` param is
  ignored and all per-instrument card buttons render disabled +
  greyed-out. Operator must Revert to draft first.

**Tests:**

- The non-savepoint regression harness from
  [PR #204](https://github.com/philoyhc/review-robin-web/pull/204)
  already covers persistence; add cases for arrow reorder,
  Name/Email lock rules, state-machine transitions, session-active
  locking.
- Update existing display-field-route tests to expect the new
  template shape.

---

## Slice 2 — Response Fields table

**Status:** ✅ shipped in
[PR #227](https://github.com/philoyhc/review-robin-web/pull/227).
Polish PRs that landed on top: action-cell single-row layout
([#228](https://github.com/philoyhc/review-robin-web/pull/228)),
action button compression + lazy-seed backfill on every GET
([#229](https://github.com/philoyhc/review-robin-web/pull/229)),
prune unpopulated Display Fields rows + canonical
reviewee-before-pair_context order
([#230](https://github.com/philoyhc/review-robin-web/pull/230)),
spec for Response Fields Help placeholder card
([#231](https://github.com/philoyhc/review-robin-web/pull/231)),
and Display Fields.Include checkbox simplification + full
Response Fields Help wiring
([#232](https://github.com/philoyhc/review-robin-web/pull/232)).

PR #232 landed the **Response Fields Help** card — originally
spec'd as a deferred follow-up. The Help card renders below the
Section B grid with one row per Response Fields row; in edit
mode each row has a textarea for help text + a Show checkbox,
both bound to the same ``dfsave-{iid}`` bulk-save form via
``help_text_id`` / ``help_text`` parallel arrays and a
``help_text_visible_ids`` set. ``bulk_save_fields`` applies the
two fields on response rows when present in the payload, rolling
into the ``instrument.response_fields_saved`` audit detail.

Slice 2 also dropped the original spec point
"`Required` checkbox stays read-only post-create": the rebuilt
table makes Required toggleable in edit mode (spec wording
already allowed it). Type stays read-only.

**Estimated effort:** ~2-3 hrs.

Reuses the state machine from Slice 1. Type column ships with the
existing four hardcoded types; Slice 4 swaps it for the RTD
dropdown.

**Template:**

- Render `instrument.response_fields | sort(attribute='order')`
  per the spec columns: Key / Friendly Label / Type / Required /
  Order / Action.
- Inline Friendly Label edit, Required checkbox, Order
  `▲` / `▼` arrows.
- ✗ delete row (existing `delete_response_field` cascade
  behaviour preserved). ➕ add row using the spec'd defaults
  (`Rating{N}` label, `rating{N}` key, `Integer` type,
  `Required = ✓`).
- Type renders as a `<select>` over `["Integer", "Short Text",
  "Long Text", "Yes/No"]` for now. Read-only post-create.

**Tests:**

- Existing harness covers persistence. Add coverage for:
  - ➕ defaults and conflict-free key auto-generation.
  - ✗ delete + cascade (existing
    [`test_route_persistence.py`](../tests/integration/test_route_persistence.py)
    already covers commit behaviour).
  - Arrow reorder.
  - State-machine round-trip (Edit → typed Friendly Label →
    Save → reload reads back the typed label).

---

## Slice 3 — Preview Instrument #N rendering

**Estimated effort:** ~2 hrs. Lands **after** Slice 4 (preview is
more useful once both field tables are configurable against RTD).

**Service:**

- Reuse the preview-helper code from
  `app/web/routes_reviewer.py::build_preview_context` and adapt
  for in-page rendering: real reviewees up to three, padded with
  mock rows.

**Template:**

- Server-rendered preview table (no JS preview re-render needed).
  Re-renders on each Save (page reload via the state-machine
  transition).
- Display Fields columns by `Order` × `Include`; Response Fields
  columns by `Order`; `*` suffix on required Response Fields
  column headers.
- `RevieweeName` / `RevieweeEmail` Display Fields rows are folded
  into the Name / Email column (not duplicated).
- Profile-link cells render as `<a target="_blank">View</a>`
  (matching existing reviewer-surface convention).

**Tests:**

- Snapshot-style assertions on column order, presence of
  asterisks, profile-link rendering, the three-row guarantee.

---

## Slice 4 — Response Type Definitions card

**Estimated effort:** ~5-6 hrs (largest slice). Optionally split
into 4a (read-only render of seeded rows + Response Fields uses
RTD dropdown) and 4b (gated editing flow + save-time validation +
operator-add / -edit / -delete).

**Schema / migration:**

- New table `response_type_definitions`:

  | Column | Type | Notes |
  |---|---|---|
  | `id` | int PK | autoincrement |
  | `session_id` | int FK | `sessions.id`, indexed |
  | `response_type` | str(64) | unique per session |
  | `data_type` | str(16) | one of `String` / `Decimal` / `Integer` / `List` |
  | `min` | float (nullable) | meaning depends on `data_type` |
  | `max` | float (nullable) | meaning depends on `data_type` |
  | `step` | float (nullable) | applies to Decimal / Integer only |
  | `list_csv` | text (nullable) | comma-separated for List |
  | `is_seeded` | bool | true for the six baseline rows; un-deletable |

- Alembic migration backfills the six seeded rows
  (`Long_text`, `Short_text`, `Grade`, `1-to-5int`, `1-to-5half`,
  `1-to-5dec`) into every existing session.

**Service:**

- CRUD per the gated editing flow (cells unlock left-to-right).
- Seed-on-session-create alongside the existing
  `ensure_default_instrument` call in `create_session`.
- `validation_block_for_type(rtd_row) -> dict` maps an RTD row to
  the JSON shape that `instrument_response_fields.validation`
  expects:
  - `Integer` / `Decimal` → `{"min": …, "max": …, "step": …}`
  - `String` → `{"min_length": …, "max_length": …}`
  - `List` → `{"choices": […]}`
- Save-time rejection: empty list, Min > Max, Step doesn't divide
  evenly. (Per the spec — the operator's expected to do their
  math.)

**Routes / template:**

- Full table on the Instruments page below the per-instrument
  cards. Operator-add / -edit / -delete via per-row forms.
- Gated editing implemented as server-driven (the cell-by-cell
  unlock is a UI nicety; the server enforces the shape on save).
  Optionally enhance with disabled-state JS toggles to make the
  gating visible client-side too.
- Response Fields Type column switches from hardcoded `<select>`
  to a dropdown over
  `response_type_definitions.response_type` (per-session).
- On a Response Fields Save, the engine looks up the chosen
  Type's RTD row and writes the resulting validation block to
  `instrument_response_fields.validation`.

**Tests:**

- Schema + migration round-trip (seeded rows present on every
  session).
- Service-layer CRUD + save-time validation.
- Gated editing — server-side enforcement (incomplete row =
  reject; Data Type change resets trailing cells).
- Response Fields Type dropdown reflects the session's RTD rows.
- Type cascade — editing an in-use Type's parameters propagates
  to `instrument_response_fields.validation` on the next
  Response Fields Save.

---

## Slice 5 — Multi-instrument enable

**Estimated effort:** ~1 hr. Closes
[`unfinished_business.md`](./unfinished_business.md) item #18.

- Enable the `Add new instrument` button (currently disabled
  with the "Multi-instrument support is still in progress"
  tooltip). The route + service + cascade are already wired and
  tested; the button just needs to lose its `disabled` attribute
  + tooltip and add a confirm dialog on click.
- Re-promotion on delete already works (per
  [PR #210](https://github.com/philoyhc/review-robin-web/pull/210)
  / `delete_instrument` service).
- Update [`unfinished_business.md`](./unfinished_business.md) to
  tick #18, and update [`todo_master.md`](./todo_master.md)
  accordingly.

---

## Cross-cutting conventions reused

- **Six button styles** from
  [`spec/assumptions.md`](../spec/assumptions.md). Save = Primary,
  Cancel = Alert Outline, Edit = Alert, Add new instrument =
  Alert, Delete this instrument = Danger.
- **Yellow lock card** from [`spec/operator_map.md`](../spec/operator_map.md)
  — when session is `ready`, every per-instrument card stays
  locked and its buttons grey out. Already in place from PR #216.
- **Setup nav** in `.setup-nav` — already in place from PR #216.
- **Per-instrument palette** (`#f0f9ff` / `#d1fae5` / `#ede9fe` /
  `#ffedd5` / `#ffe4e6` / `#fef3c7` cycling) — already in place
  from PR #216.
- **`▲` / `▼` reorder convention** from
  [`guide/instruments.md`](./instruments.md) — Slices 1, 2, 4.
- **Service-boundary `db.commit()`** rule from
  [PR #204](https://github.com/philoyhc/review-robin-web/pull/204) —
  every mutating service method commits explicitly. The
  non-savepoint regression harness in
  [`tests/integration/test_route_persistence.py`](../tests/integration/test_route_persistence.py)
  catches drift.

## Working approach

- One slice = one PR. Land in dependency order; don't bundle.
- Each slice updates [`docs/status.md`](../docs/status.md)
  "Segments shipped" only on segment close (i.e. when Slice 5
  lands), not per-slice.
- Each slice's PR description explicitly states which
  spec-locked behaviour it implements (paragraph reference into
  [`guide/instruments.md`](./instruments.md)) so reviewers can
  cross-check against the spec.
- Tests gate every slice. The persistence regression harness from
  [PR #204](https://github.com/philoyhc/review-robin-web/pull/204)
  must stay green; new wiring slices add their own coverage on
  top.

## Cross-references

- [`guide/instruments.md`](./instruments.md) — the locked spec
  this segment implements.
- [`spec/operator_map.md`](../spec/operator_map.md) — page chrome
  conventions.
- [`spec/assumptions.md`](../spec/assumptions.md) — button styles.
- [`spec/architecture.md`](../spec/architecture.md) "Pair-level vs
  assignment-level context" + "Lazy display-field seeding" — the
  data-side rules the rebuild relies on.
- [`guide/segment_10C.md`](./segment_10C.md) — first-round operator
  UI clean-up (the slice that 10D builds on).
- [`guide/unfinished_business.md`](./unfinished_business.md) item
  #18 — multi-instrument enable (Slice 5).
- [`guide/todo_master.md`](./todo_master.md) — sequenced master
  list; this segment ticks the multi-instrument item.
