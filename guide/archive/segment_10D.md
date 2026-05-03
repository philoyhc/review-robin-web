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

## Dependency map

```
        ┌──────────┐
        │ Slice 1  │  Display Fields + state machine ✅
        └────┬─────┘
             │
             ▼
        ┌──────────┐
        │ Slice 2  │  Response Fields (hardcoded 4 types) ✅
        └────┬─────┘
             │
             ▼
        ┌──────────┐
        │ Slice 3  │  Response Fields Help (textarea + Show) ✅
        └────┬─────┘    [retroactively numbered — shipped via #232]
             │
             ▼
        ┌──────────┐
        │ Slice 4a │  RTD schema + 10 seeds + FK migration ✅
        └────┬─────┘    (RF Type renders as RTD dropdown, read-only)
             │
             ▼
        ┌──────────┐
        │ Slice 4b │  RTD operator-add / -edit / -delete ✅
        └────┬─────┘    (cascade-on-delete UX)
             │
             ▼
        ┌──────────┐
        │ Slice 4c │  Wire RF↔RTD on add (operator-pickable Type) ✅
        └────┬─────┘
             │
             ▼
        ┌──────────┐
        │ Slice 4d │  Cross-cutting consistency guards ✅
        └────┬─────┘    (mutual-edit lock + zero-RF block + would-empty block)
             │
             ▼
        ┌──────────┐
        │ Slice 5  │  Multi-instrument enable (P0 #18)
        └──────────┘
```

Slice 4 splits into 4a (schema, seed, FK migration of the
existing `response_type` column, read-only render of the RTD
catalog + Response Fields `Type` rendered as a dropdown over RTD
names) and 4b (operator-add / -edit / -delete on the RTD card,
including the gated left-to-right editing flow and the
cascade-on-delete confirmation UX). The split lets the schema
change ship before the largest blob of UI logic. Slice 5 (multi-
instrument) is small enough to ride at any point after Slice 1
but sits at the end so the multi-instrument promotion behaviour
can be observed against a fully-wired single-instrument card
first.

The original Slice 3 ("Preview Instrument #N rendering" — a
per-instrument inline preview table with mock-data padding)
**dropped from the plan** when the spec rethought the preview
surface (see `guide/instruments.md` Section D placeholder). The
shared `/operator/sessions/{id}/preview` page already renders the
reviewer surface for the whole session; how that integrates with
the per-instrument card is open and explicitly out of scope for
this segment. Section D of the spec stays as a placeholder until
that integration is decided.

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

A four-PR **state-machine completion polish** sequence then
closed the Save / Cancel contract on the per-instrument card:

- [#235](https://github.com/philoyhc/review-robin-web/pull/235)
  — Order ``▲`` / ``▼`` on both tables now reorder rows
  client-side and rewrite the bulk-save form's hidden ``order``
  inputs, so the new order only commits on Save (Cancel
  discards).
- [#236](https://github.com/philoyhc/review-robin-web/pull/236)
  — Response Fields ``✗`` / ``➕`` defer to the same bulk-save
  form: ``✗`` queues a ``response_delete_ids`` hidden input, ``➕``
  clones a hidden ``<template>`` with id ``new_{N}`` that the
  route resolves to a real field on Save via
  ``add_default_response_field``. Help rows follow along.
- [#237](https://github.com/philoyhc/review-robin-web/pull/237)
  — Section A's separate ``<details>`` Edit toggle for the
  description is gone; description rides along with the
  bulk-save form via a textarea joined to ``dfsave-{iid}``. The
  ``<hr>`` and ``Preview Instrument #N`` placeholder block from
  Sections C / D are removed.
- [#238](https://github.com/philoyhc/review-robin-web/pull/238)
  — Mirrored Edit / Save+Cancel pair anchored bottom-left of
  the Section A description card so the operator has a second
  affordance without scrolling past the tables. Both pairs
  share the same ``?editing={iid}`` state machine.

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

## Slice 3 — Response Fields Help

**Status:** ✅ shipped in
[PR #232](https://github.com/philoyhc/review-robin-web/pull/232)
(retroactively numbered — landed alongside the Slice 2 polish
sequence).

The `Response Fields Help` card had been spec'd
([#231](https://github.com/philoyhc/review-robin-web/pull/231))
as a deferred placeholder and then wired up the same day:
each row in the card hosts a 2-row textarea (`name="help_text"`)
+ a Show checkbox (`name="help_text_visible_ids"`), bound to the
shared `dfsave-{iid}` bulk-save form. The bulk-save route reads
parallel `help_text_id` / `help_text` arrays plus the visible-ids
set, builds a per-id lookup, and passes `help_text` +
`help_text_visible` into the response rows handed to
`bulk_save_fields`. The service applies them with the existing
dict-of-changes pattern; the audit event
`instrument.response_fields_saved` carries the diff.

Recording it as Slice 3 keeps the chronological history clear —
useful when the next reader is tracing how each piece of the
field-builder came together.

---

## Slice 4 — Response Type Definitions card

**Estimated effort:** ~5-6 hrs total. **Split into 4a + 4b** so
the schema change ships before the largest blob of UI logic, and
each PR can be reviewed against a smaller surface area.

### Slice 4a — Schema, seed, FK migration, read-only render

**Status:** ✅ shipped in
[PR #242](https://github.com/philoyhc/review-robin-web/pull/242).
The migration backfilled the **ten** seeded rows on every existing
session and rewrote `instrument_response_fields.response_type`
(text) into `response_type_id` (FK with `ON DELETE CASCADE`).
``passive_deletes=True`` on the RTD → RF relationship lets the
database FK cascade fire instead of having SQLAlchemy NULL the
column first; ``app/db/session.py`` flips on
``PRAGMA foreign_keys = ON`` for SQLite engines so dev + test
behave like the Postgres production setup.

A precision-rules polish PR landed on top:
[PR #243](https://github.com/philoyhc/review-robin-web/pull/243)
formats Min / Max / Step display by Data Type (Integer + String →
plain int; Decimal → exactly one decimal place) and ships an
``assert_rtd_precision`` helper Slice 4b's editor wires in.

**Estimated effort:** ~3-4 hrs.

In: New table + seed + FK migration of existing
`instrument_response_fields.response_type` data; new
`Response Type Definitions` card on the Instruments page rendered
as a **read-only catalog** of the ten seeded rows; Response
Fields `Type` cell rendered as a `<select disabled>` over the
session's RTD names (still read-only post-create per spec).

Out (deferred to 4b): operator-add / -edit / -delete on RTD
rows; gated left-to-right editing flow; cascade-on-delete
confirmation UX.

**Schema / migration:**

- New table `response_type_definitions`:

  | Column | Type | Notes |
  |---|---|---|
  | `id` | int PK | autoincrement |
  | `session_id` | int FK | `sessions.id`, ON DELETE CASCADE, indexed |
  | `response_type` | str(64) | unique per session |
  | `data_type` | str(16) | one of `String` / `Decimal` / `Integer` / `List` |
  | `min` | float (nullable) | meaning depends on `data_type` |
  | `max` | float (nullable) | meaning depends on `data_type` |
  | `step` | float (nullable) | applies to Decimal / Integer only |
  | `list_csv` | text (nullable) | comma-separated for List |
  | `is_seeded` | bool | true for the ten baseline rows; un-deletable |

- Alembic migration backfills the **ten** seeded rows
  (`Long_text`, `Short_text`, `Yes_no`, `Grade`, `Likert5`,
  `100int`, `0-to-2int`, `1-to-5int`, `1-to-5half`, `1-to-5dec`,
  in that order) into every existing session via
  `op.execute(...)` over each `sessions.id`. See
  [`guide/instruments.md`](./instruments.md) "Default seed" for
  the full row contents (Min / Max / Step / List values).

- Same migration replaces the `instrument_response_fields.response_type`
  text column with `response_type_id`, a FK into
  `response_type_definitions.id` with **`ON DELETE CASCADE`**.
  The column starts NULL-able, the migration backfills via the
  per-session map below, and a follow-up `ALTER COLUMN ... NOT
  NULL` makes it required:

  | Old `response_type` value | New RTD row referenced |
  |---|---|
  | `integer` | `1-to-5int` (canonical default for ambiguous integer rows) |
  | `short_text` | `Short_text` |
  | `long_text` | `Long_text` |
  | `yes_no` | `Yes_no` |

  After backfill the old column drops. The cascade through the
  `responses → instrument_response_fields → response_type_definitions`
  FK chain is the natural way to drop dependent rows when an
  operator-defined RTD is deleted in 4b — no application-level
  cascade code needed.

**Service:**

- Seed-on-session-create: `ensure_default_response_type_definitions(session)`
  runs alongside `ensure_default_instrument(session)` inside
  `create_session`, idempotent so reruns are safe.
- `validation_block_for_rtd(rtd_row) -> dict` maps an RTD row to
  the JSON shape that `instrument_response_fields.validation`
  expects:
  - `Integer` / `Decimal` → `{"min": …, "max": …, "step": …}`
  - `String` → `{"min_length": …, "max_length": …}`
  - `List` → `{"choices": [...]}`
- `ensure_default_instrument` updated: the two seeded Response
  Fields rows now reference RTD rows by `response_type_id`
  instead of literal strings — `rating1` → `1-to-5int`, `comments1`
  → `Long_text`. (Matches the spec table in
  [`guide/instruments.md`](./instruments.md) Slice 2.)

**Routes / template:**

- Full-width `Response Type Definitions` card rendered below the
  per-instrument cards. Read-only table over the session's RTD
  rows (sorted: seeded rows first in spec order, operator-added
  rows after by `id`). Every cell in the row renders `disabled` /
  muted; no Action column yet (4b).
- Response Fields `Type` column switches from the hardcoded
  four-value `<select>` to a `<select disabled>` over the
  session's RTD names. The selected option is the row's current
  `response_type_id`. Type stays read-only post-create per spec.
- Bulk-save form's payload now writes `response_type_id` instead
  of `response_type`. Newly-added Response Fields rows
  (`id="new_N"` from the JS-deferred ➕) carry the operator's
  selected RTD id from the dropdown; bulk-save resolves it on
  Save.

**Tests:**

- Migration round-trip (SQLite + Postgres CI smoke):
  pre-migration mock data with all four legacy `response_type`
  values gets mapped to the right RTD rows; the post-migration
  `response_type_id` is non-NULL for every RF row.
- `ensure_default_response_type_definitions` is idempotent
  (re-running on a session already seeded is a no-op).
- `ensure_default_instrument` seeds `rating1 → 1-to-5int` and
  `comments1 → Long_text` on a fresh session.
- Response Fields render carries the seeded RTD name in the
  `<select disabled>` for both default rows.
- The cascade chain works: SQL-level delete of an RTD row drops
  dependent RF rows and their Response children. (Tested
  service-side; the operator UX wraps this in 4b.)

### Slice 4b — RTD editing + cascade-on-delete UX

**Status:** ✅ shipped in
[PR #244](https://github.com/philoyhc/review-robin-web/pull/244).
Operator-add / -edit / -delete on the Response Type Definitions
card landed alongside the cascade-confirm UX. Six iterative UX
polish PRs followed on top:

- [#245](https://github.com/philoyhc/review-robin-web/pull/245) —
  Three-state per-row UX (saved / editing / drafting). The
  ``Add a Response Type`` footer is now Name + Data Type only;
  the actual draft row gets cloned client-side from a hidden
  ``<template>`` so an incomplete row never persists.
- [#246](https://github.com/philoyhc/review-robin-web/pull/246) —
  Fix draft-row Cancel button (the ``__DRAFT_ID__`` placeholder
  was substituted unquoted, treating ``d1`` as a JS identifier);
  lock the Add button + inputs while any row is unsaved.
- [#247](https://github.com/philoyhc/review-robin-web/pull/247) —
  One operator-defined row unlocked at a time. Locked state
  shows only ``Edit`` (Alert); unlocked state shows
  ``Save`` + ``Cancel`` (Alert outline) + ``Delete`` (Danger).
  Other rows' ``Edit`` greys out while one is unlocked. ``Delete``
  goes through a JS ``confirm`` warning before posting; in-use
  rows still surface the cascade banner. Seeded rows render an
  empty Action cell (no buttons).
- [#248](https://github.com/philoyhc/review-robin-web/pull/248)
  / [#249](https://github.com/philoyhc/review-robin-web/pull/249)
  / [#250](https://github.com/philoyhc/review-robin-web/pull/250)
  — Inline button width tightened to ``6em`` and applied uniformly
  (incl. ``Add``); Add card pushed right-aligned and stacked into
  a tidier four-row block; Action TDs right-aligned; intro
  paragraph rewritten.

The original Slice 4b plan called for a fully gated left-to-
right editing flow (cells unlock as the operator fills the
preceding ones). The shipped UI takes a simpler tack: the draft
row exposes every applicable cell up front, validation runs
server-side on Save, and incomplete / invalid payloads bounce
back with an inline error banner. Same correctness contract,
materially less JS surface area.

**Estimated effort:** ~2-3 hrs (shipped over a longer iteration
arc due to the polish PRs above).

- Operator-add (➕) on RTD rows: the JS-deferred draft pattern
  (cloned ``<template>`` row + ``<form>`` linked via HTML5
  ``form="..."``) writes only on Save. Cancel removes the row.
  Server-side enforcement is the source of truth (Save rejects
  incomplete or invalid rows); the disabled / locked Add button
  prevents starting another row while one is unsaved.
- Edits to operator-defined rows: name + Data Type lock once
  saved (rendered as plain text). Min / Max / Step / List stay
  editable; Save propagates the new validation block to every
  Response Fields row that references this RTD
  (``update_response_type_definition`` re-derives the validation
  block when the row's parameters change).
- Operator-delete on operator-defined RTD rows in use:
  confirmation dialog showing cascade preview (`N response field
  row(s) on M instrument(s), X response(s) across Y reviewer
  assignment(s)`). On confirm, the FK `ON DELETE CASCADE` from
  4a takes care of the actual cascade. Operator-delete on
  operator-defined RTD rows not in use: a JS ``confirm()``
  warning (added in #247) before the immediate drop. Seeded
  rows: Delete suppressed entirely.
- Save-time rejection on RTD save: empty list when Data Type is
  `List`; Min > Max for Integer / Decimal / String; Step doesn't
  evenly divide (Max − Min) for Integer / Decimal; Decimal
  Min / Max / Step with more than one decimal place; Integer
  Min / Max / Step with a fractional component.

**Tests shipped:** unit coverage in
[`tests/unit/test_response_type_definitions.py`](../tests/unit/test_response_type_definitions.py)
(add / update / delete service + cascade-count helper +
precision rules); route + render coverage in
[`tests/integration/test_display_field_routes.py`](../tests/integration/test_display_field_routes.py)
(add route, add-error banner, edit-route 409 on seeded, delete
blocked → confirmed → cascade, ready-session lock, per-row
edit form rendered when ``editing_rtd_id`` matches, draft
templates render, Add disabled while editing).

---

## Slice 4c — Wire Response Fields ↔ RTD on add (operator-pickable Type)

**Status:** ✅ shipped in
[PR #256](https://github.com/philoyhc/review-robin-web/pull/256).
``add_default_response_field`` extended with optional ``rtd_id``
/ ``label`` / ``field_key`` / ``required`` kwargs (default
behaviour preserves the Slice 2 contract verbatim). The bulk-
save handler reads parallel ``new_rtd_target`` / ``new_rtd_id``
form arrays to map each ``new_*`` draft id to its operator-
chosen RTD; saved rows ignore any ``new_rtd_*`` inputs (Type
stays read-only post-create per spec, server-side defence
against forged forms). The draft row's ``Type`` ``<select>`` is
now enabled until Save commits the row.

The slice plan below documents the audit + decisions made on
the way to that PR.

Discovered post-Slice-4b: the
``Response Fields`` ``Type`` cell renders as ``<select disabled>``
for *both* saved rows (correct, per spec — read-only post-create)
*and* JS-added draft rows (a gap — operators can't actually pick
the Type for a new field). Today every JS-added row gets
hardcoded to ``1-to-5int`` server-side via
``add_default_response_field``, and the ``field_key`` stays
``rating{N}`` regardless of what the operator types as the
label. This slice closes both gaps before Slice 5 lands.

**Estimated effort:** ~1.5-2 hrs.

### Audit — what's wired vs. not, post-Slice-4b

✅ Wired correctly:

- ``response_type_definitions`` schema + the 10 seeded rows on
  every session.
- ``instrument_response_fields.response_type_id`` FK with
  ``ON DELETE CASCADE`` (database + ``passive_deletes=True``).
- Read-only RTD catalog card on the Instruments page.
- Operator add / edit / delete on the RTD card with cascade-
  preview confirmation.
- ``update_response_type_definition`` propagates a re-derived
  validation block to every dependent ``InstrumentResponseField``
  on save.
- Reviewer surface renders inputs from ``data_type`` + the
  RTD-derived validation block (``min`` / ``max`` / ``step`` /
  ``choices`` / ``min_length`` / ``max_length``).
- ``ensure_default_instrument`` seeds new instruments with
  ``rating1 → 1-to-5int`` and ``comments1 → Long_text``.

⚠ Gaps:

- **Response Fields ``Type`` cell on JS-added new rows is
  ``<select disabled>``** — same render as saved rows. The
  operator sees the full RTD list but can't pick from it. (The
  comment on the template even says "the operator sees the full
  RTD dropdown but cannot change the selection".)
- **Bulk-save route always calls ``add_default_response_field``
  for ``new_*`` ids**, which hardcodes ``response_type_id`` to
  ``1-to-5int`` and seeds a ``Rating{N}`` label.
- **``field_key`` for operator-typed labels** stays
  ``rating{N}`` because the route doesn't re-slugify after the
  bulk-save loop applies the label. Operator picks "Decision" as
  label → key remains ``rating1``.

### What lands

**Template (`instruments_index.html`):**

- The new-row ``rf-template-{iid}`` cell for Type renders the
  ``<select>`` **enabled** (drop the ``disabled`` attribute).
  Add the field-attribute wiring so the picker submits along the
  bulk-save form: ``form="dfsave-{iid}" name="response_type_id"``.
  Saved rows keep their existing ``<select disabled>`` render.

**Route (`bulk_save_fields` handler):**

- Read parallel ``new_response_type_ids`` array (or a
  ``response_type_id_for_new[<draft_id>]`` map) from the form,
  per ``new_*`` id.
- Replace the hardcoded ``add_default_response_field`` call for
  ``new_*`` ids with a path that:
  1. Resolves the operator-chosen RTD via ``_rtd_by_id``,
     defaulting to ``1-to-5int`` if missing.
  2. Slugifies the operator-typed label (also submitted in the
     bulk payload) into a non-conflicting field_key — fall back
     to ``rating{N}``-style auto-numbering when label is blank.
  3. Calls a new ``add_response_field_with_rtd`` helper (or
     extends ``add_default_response_field`` with optional
     ``rtd_id`` + ``label`` + ``field_key`` arguments) that
     returns a row already pointing at the chosen RTD with the
     derived validation block.

**Service (`app/services/instruments.py`):**

- Either:
  - **(a)** Extend ``add_default_response_field`` to accept
    optional ``rtd_id`` + ``label`` + ``field_key``; default
    behaviour (no overrides) stays today's contract so existing
    callers don't move.
  - **(b)** Land a new ``add_operator_response_field(...)``
    helper alongside ``add_default_response_field`` and route
    the bulk-save path through it.

  Recommend (a) — smaller surface area; avoid splitting the
  audit-event emission.

- Rules preserved per spec:
  - ``Type`` stays read-only post-create on saved rows
    (server-side defence: 4c never accepts a ``response_type_id``
    for a non-``new_*`` row in the bulk-save payload).
  - Validation block on the new row derived from
    ``validation_block_for_rtd`` of the chosen RTD.
  - The new RF row's ``field_key`` is unique within the
    instrument (existing ``FieldKeyError`` path).

**Tests:**

- Service: ``add_default_response_field(rtd_id=..., label=...)``
  honours the RTD; validation block matches; field_key derives
  from label and falls back when blank.
- Route: bulk-save POST with a ``new_*`` row carrying a
  non-default ``response_type_id`` persists the new RF row
  pointing at the chosen RTD.
- Server-side defence: forged form POSTing
  ``response_type_id`` for a non-``new_*`` row is silently
  ignored (Type is locked post-create).
- Render: the new-row ``Type`` ``<select>`` is rendered enabled
  (no ``disabled`` attribute) when the row id is a ``new_*``
  draft; saved rows still render disabled.

### Out of scope (deferred)

- **Type-change on saved rows** — explicitly locked by spec
  (`guide/instruments.md` Response Fields ``Type`` row).
  Editing Type post-create would need data-migration UX and is a
  separate decision.
- **Smart label/key defaults per Data Type** — e.g. swap the
  ``Rating{N}`` JS-side default to ``Decision{N}`` for ``Yes_no``
  picks. Not strictly necessary; the operator can type whatever
  label they want before Save.

### Spec touch-up

`guide/instruments.md` Response Fields ``Type`` row already says
"Read-only post-create". Add one sentence: *"For newly-added rows
the Type is operator-picked from the session's RTD catalog (the
``<select>`` is enabled until Save commits the row)."*

---

## Slice 4d — Cross-cutting consistency guards before Slice 5

**Status:** ✅ shipped in
[PR #257](https://github.com/philoyhc/review-robin-web/pull/257).
All three gaps closed: per-instrument and RTD card editing
state machines mutually exclusive; bulk-save refuses to commit
an instrument with zero RF rows; cascade-delete that would
empty an instrument is hard-blocked with a banner naming the
affected instrument(s). The original plan called for a server-
side defence on top of the UI lock for Gap 1 — the shipped UI
lock plus the route-level resilience to stale data already in
the codebase covers that scenario, so the additional defence
was deferred.

Two banner-polish PRs followed on top:
[#258](https://github.com/philoyhc/review-robin-web/pull/258)
adds a Cancel button to the new error banners and writes the
convention into ``spec/assumptions.md``.
[#259](https://github.com/philoyhc/review-robin-web/pull/259)
extends the convention with auto-scroll-to-banner on display
and Cancel-returns-to-source-row.

Three coordination gaps surfaced while
reviewing the Slice 4 surface end-to-end. None block existing
flows, but all let the operator land the system in a confusing
or invalid state without a clear diagnosis. Slice 4d closes
them before multi-instrument support lands.

**Estimated effort:** ~2 hrs.

### Gap 1 — Both editing state machines can be active at once

Today the per-instrument card uses `?editing={iid}` and the
RTD card uses `?editing_rtd_id={rtd_id}`. The two are
independent — an operator can be mid-edit on instrument #1 *and*
mid-edit on an in-use ODT row, then delete the ODT and have the
cascade silently rewrite the rows their browser still has open
in inputs. The mutating bulk-save / RTD-save handlers don't
notice the conflict.

**What lands:**

- Mutual-exclusion between the two state machines on the GET
  handler. When `editing` is set on one, the other's edit
  affordances render disabled with a tooltip pointing at the
  open editing context (e.g. *"Save or cancel the edits on
  Instrument #1 before editing the Response Type Definitions."*).
- The disabled state covers: every instrument card's Section A
  Edit button + Section C Edit button (when an RTD row is
  unlocked); every operator-defined RTD row's Edit + Delete
  buttons + the `Add a Response Type` block (when an instrument
  card is unlocked).
- Server-side defence — the bulk-save and RTD-save / -delete
  routes refuse if the *other* state machine's editing context
  is non-empty in the form's `Referer` or in the DB-side state.
  (Pure-UI lock is the front line; this is the second line in
  case of forged form posts.)

We're explicitly not greying out Edit / Delete on in-use ODTs —
the propagation pattern (RTD parameter edit → dependent RF
validation re-derived) is the value-add of operator-defined
types, and forcing the operator to remove every reference
before editing defeats it.

### Gap 2 — Bulk-save accepts an instrument with zero Response Fields

Today the bulk-save handler will happily commit an instrument
with zero RF rows (e.g. operator deletes every RF row, hits
Save). The session-level validation at activation time blocks
the session from going `ready`, but until then the operator
sees an empty Response Fields table on the per-instrument card
without a clear "this is broken" indication.

**What lands:**

- Bulk-save handler counts post-save RF rows per instrument. If
  zero, it raises an inline error and redirects back to the
  page with a banner: *"An instrument must have at least one
  response field. Add one, or undo the delete."* The
  ``editing_instrument_id`` query param stays set so the
  operator's edits don't vanish on the redirect.
- Symmetric with the existing RTD save-time validation — both
  paths use a blocking banner instead of "save first, validate
  later".

### Gap 3 — Cascade-delete on an in-use ODT can empty an instrument

The cascade-confirm banner today previews "N response field
rows on M instruments". If a particular instrument's *only*
remaining RF row references the ODT being deleted, the cascade
would leave it with zero rows — same broken-instrument state
as Gap 2, but reached indirectly.

**What lands:**

- Extend `count_rtd_dependents` to also return a list of
  `instruments_would_be_emptied: list[(int, str)]` — `(id,
  display_name)` for every instrument whose RF row count after
  the cascade would be zero.
- New service-layer error `RTDDeleteWouldEmptyInstrumentError`
  preempting `RTDInUseError` when the list is non-empty.
- Route translates this into a banner naming the affected
  instrument(s) by `Instrument #N`: *"Cannot delete Response
  Type 'Foo': it is the only Response Field on Instrument #2.
  Add or change a row on that instrument first, then come
  back."* Operator can't confirm-cascade past this — the banner
  has no Continue button, only a Cancel-style anchor back to
  the locked state.
- If the cascade would *not* empty any instrument, the existing
  cascade-confirm banner (with the four counts +
  Continue / Cancel buttons) still fires.

### Tests

- Mutual exclusion (Gap 1):
  - GET ``?editing=1`` renders RTD card Edit + Add greyed.
  - GET ``?editing_rtd_id=N`` renders instrument card Edit
    buttons greyed.
  - POST RTD edit while ``?editing=1`` 409s (server defence).
  - POST bulk-save while another card is open 409s (server
    defence).
- Zero-RF block (Gap 2):
  - Bulk-save POST that empties an instrument's RF set
    redirects with the new banner; row count unchanged in DB.
- Would-empty-instrument block (Gap 3):
  - Service: `count_rtd_dependents` returns the would-empty
    list correctly.
  - Service: `delete_response_type_definition` raises
    `RTDDeleteWouldEmptyInstrumentError` when applicable, even
    with `confirm=True`.
  - Route: cascade-confirm banner is replaced with the would-
    empty banner; no Continue button.

### Spec touch-ups

- `guide/instruments.md` Response Type Definitions card —
  "Cascade-on-delete" subsection: add the would-empty-instrument
  exception ("if cascade would leave any instrument with 0
  response fields, the delete is blocked outright; operator must
  add a non-ODT row to that instrument first").
- `guide/instruments.md` Per-instrument card "Section C / Action
  buttons" — add a sentence about the mutual-exclusion lock with
  the RTD card.

### Out of scope (deferred)

- Auto-re-seeding the default RF rows when the last row is
  deleted. The blocking-error pattern is preferred over magical
  recovery (decided post-Slice-4c review).
- Greying out Edit / Delete on in-use ODTs. The propagation
  pattern is the feature, not a bug.
- Cross-page edit lock for Reviewers / Reviewees / Assignments
  pages — those don't share editing state with Instruments
  today; if that changes a future slice can extend.

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
- [`guide/archive/segment_10C.md`](./segment_10C.md) — first-round operator
  UI clean-up (the slice that 10D builds on).
- [`guide/unfinished_business.md`](./unfinished_business.md) item
  #18 — multi-instrument enable (Slice 5).
- [`guide/todo_master.md`](./todo_master.md) — sequenced master
  list; this segment ticks the multi-instrument item.
