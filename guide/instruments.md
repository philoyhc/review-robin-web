# Instruments page

Specification for the per-session **Instruments** operator page at
`/operator/sessions/{id}/instruments`. Captures the desired surface
shape post-cleanup (PRs #205, #206) so the rebuild can land in
small slices.

This file describes **what should be on the page**. It does not
describe the routes, services, or schema that back it — those live
in `app/web/routes_operator.py`, `app/services/instruments.py`, and
`app/db/models/instrument*.py`. When a behaviour below is unwired
("Save writes to the database"), the rebuild slice that lands it
also wires the route + service + persistence.

## Page layout

Top to bottom:

1. **Page title** (H1) — `Instruments`.
2. **Full-width header card** combining session-wide instrument
   status with the 6-button setup nav. Layout in "Header card"
   below.
3. **Full-width "Actions for All Instruments" card**. Bulk
   visibility toggle + Preview reviewer surface action,
   left-aligned. See "Actions for All Instruments" below.
4. **Full-width yellow "session ongoing" lock card**, only when
   the session status is `ready`. See `spec/operator_map.md`
   "Session ongoing yellow lock card".
5. **One full-width per-instrument card per instrument**, in
   `Instrument.order`. Card layout in "Per-instrument card" below.
6. **Full-width "Response Type Definitions" card**. Catalog of
   response types (with validation rules) referenced by every
   instrument's Response Fields table. Layout in
   "Response Type Definitions card" below.

## Header card

A single full-width card. Same shape pattern as the other
session-scoped operator pages (e.g. `session_assignments.html`):
status text rows on the left, nav row right-aligned. Three rows,
top to bottom:

1. **Session deadline + instrument-count summary** (left-aligned).
   Format: `Session deadline (auto-close): {deadline pill} ·
   {N instrument(s)}: {N accepting} · {N not accepting}`. The
   deadline pill renders the ISO-formatted deadline if set, else
   `not set`. Pluralisation follows instrument count.
2. **Visibility-when-closed summary** (left-aligned). Format:
   `Visibility when closed: {N instrument(s) showing} · {N
   instrument(s) not showing}`. Pluralisation follows count.
3. **Setup nav** (right-aligned). The 6 setup-nav buttons
   (`Session`, `Reviewers`, `Reviewees`, `Assignments`,
   `Instruments`, `Email Invites`) inside `.setup-nav`. The
   `Instruments` button is rendered as Primary Outline; the
   rest are Primary. See `spec/operator_map.md` "Setup nav"
   for the canonical contract.

The standalone "All Instrument Status" card from earlier drafts
of the spec is **gone** — its status reporting moves into rows 1
and 2 of this header card. The bulk visibility / preview
buttons no longer sit on the header card either; they live in
the dedicated `Actions for All Instruments` card below (see
next section). The bulk `Open all instruments` / `Close all
instruments` buttons are **dropped** in this revision; operators
open and close instruments individually via the per-instrument
card's status sub-card.

## Actions for All Instruments

A full-width card immediately below the header. Title:
`Actions for All Instruments`. Buttons sit left-aligned, in this
order:

- `Show all when closed` / `Don't show any when closed` —
  Alert. Toggles the bulk visibility-when-closed flag across
  every instrument. Which of the two is shown follows the
  current state: when at least one instrument is hidden, show
  `Show all when closed`; when every instrument is showing,
  show `Don't show any when closed`.
- `Preview reviewer surface` — Alert. Opens the operator's
  preview of the reviewer surface for this session.

The card isolates session-wide bulk actions from the per-card
details so the header card can focus on at-a-glance instrument
status, and the per-instrument cards can focus on the
field-builder + RTD work.

## Per-instrument card

Five sections, top to bottom, inside one full-width card. Each
instrument card uses a distinct light-tinted background so the
operator can tell adjacent cards apart at a glance. The palette
cycles in `Instrument.order` order:

| `#N` | Background |
|---|---|
| 1 | light blue (`#f0f9ff`) |
| 2 | light green (`#d1fae5`) |
| 3 | light purple (`#ede9fe`) |
| 4 | light orange (`#ffedd5`) |
| 5 | light pink (`#ffe4e6`) |
| 6 | light yellow (`#fef3c7`) |

For sessions with more than six instruments the palette wraps —
`#7` reuses the `#1` background and so on. The inner sub-cards
(identity, status, field tables, preview) keep their own
backgrounds (white for status; transparent / invisible-borders
for the rest) so the per-instrument tint reads as a frame, not as
the body of the inner content.

### A. Identity + status (two half-width cards side by side)

Equal-height, top + bottom aligned (`.bottom-grid` with
`align-items: stretch`).

**Left card** — invisible borders, flex column.

- Header: `Instrument #{N}` rendered in a font size larger than
  normal card titles but smaller than the page H1.
- Friendly description (free text, operator-typed). In **locked**
  mode renders as plain text (`(no description)` when empty); in
  **edit** mode renders as a `<textarea form="dfsave-{iid}"
  name="description">` joined to the same bulk-save form as the
  Section B tables.
- Bottom-left **Edit / Save+Cancel** button pair, mirroring the
  pair in Section C below. The two pairs are interchangeable —
  the operator can flip into edit mode (or commit / discard) from
  either pair without scrolling. See "Section C — Action buttons"
  below for the canonical wiring.

**Right card** — `This Instrument's Status`.

- Instrument-specific status pills (accepting / not accepting,
  visibility-when-closed showing / not showing,
  deadline-closed-at if present).
- A `saved` / `not saved` pill summarising whether the operator
  has ever pressed Save on the field tables for this instrument.
- Action buttons for visibility-to-reviewers (open / close,
  show-when-closed / don't-show-when-closed).

### B. Display Fields + Response Fields + Response Fields Help

A two-half-width grid (Display Fields | Response Fields) followed
by a full-width Response Fields Help table below.

The two top cards are equal-height, top + bottom aligned
(`.bottom-grid`). Both cards have invisible borders. The Response
Fields Help card sits directly below the grid, full width, also
invisible borders.

#### Reordering convention

Both tables in this section let the operator reorder rows. Rather
than asking the operator to type integers, each row carries two
small arrow buttons (`▲` and `▼`) in its `Order` cell. Clicking
`▲` swaps this row with the row immediately above; `▼` swaps with
the row immediately below. The arrow is disabled at the boundary
(top row's `▲`, bottom row's `▼`). The integer to the left of the
arrows is informational — it always reflects the row's current
position post-swap and is not directly editable.

The swap is **client-side**: it reorders the DOM rows and
rewrites each row's hidden `order` input on the bulk-save form,
so the new positions only commit when the operator clicks Save.
Cancel discards them.

The arrows are also suppressed for rows whose position is fixed
by spec. Today that's the `RevieweeName` and `RevieweeEmail` rows
in Display Fields: they always sit at positions 1 and 2 (in that
order) and cannot be reordered. Every other row in either table
is freely reorderable.

#### Display Fields (left)

Title: `Display Fields`. Columns:

| Column | Behaviour |
|---|---|
| **Source** | System name. Read-only `<code>`. Eligible rows, in default order: `RevieweeName`, `RevieweeEmail`, then any reviewee data column with at least one populated value (`PhotoLink`, `RevieweeTag1/2/3`), then any pair-context slot with at least one populated value across the session's assignments (`PairContext1/2/3`). `AssignmentContext1/2/3` is deliberately **excluded** — it's logic-engaging and hidden from reviewers (see `spec/architecture.md` "Pair-level vs assignment-level context"). |
| **Friendly Label** | Operator-editable text. Save persists to the underlying database. |
| **Include** | Checkbox. `RevieweeName` and `RevieweeEmail` are mandatory-checked and the checkbox is locked (operator cannot uncheck). All other rows are operator-toggleable. |
| **Order** | Integer (1-based) plus the `▲` / `▼` arrow controls described above. The arrows are suppressed for the `RevieweeName` and `RevieweeEmail` rows — they're locked at positions 1 and 2 respectively. Initial seed: `RevieweeName=1`, `RevieweeEmail=2`, then the present rows in the order `PhotoLink`, `RevieweeTag1/2/3`, `PairContext1/2/3` (skipping any that have no data). |
| **Sort** | Empty for now. Placeholder for a future default row order on reviewer surface; will use the same `▲` / `▼` reorder convention when it lands. |

#### Response Fields (right)

Title: `Response Fields`. Columns:

| Column | Behaviour |
|---|---|
| **Key** | The system name for the row. Read-only `<code>`. |
| **Friendly Label** | Operator-editable text. Save persists. |
| **Type** | One of the response types defined by the Response Type definitions card. Read-only post-create. The Type carries its own validation rules (e.g. `1-to-5` implies `min=1, max=5`); the engine writes them to `instrument_response_fields.validation` on save and the operator does **not** see a validation cell in this table. |
| **Required** | Checkbox. When checked, the field is mandatory for reviewers and the column header in the Preview table is appended with an asterisk (e.g. `Rating*`). |
| **Order** | Integer (1-based) plus the `▲` / `▼` arrow controls described above. |
| **Action** | A delete cross icon (✗) and an add-row plus icon (➕). Both are **client-side** — same deferral pattern as the `▲` / `▼` arrows. ✗ hides the row and queues its id in a hidden `response_delete_ids` input on the bulk-save form (or just removes the row from the DOM if it was JS-added). ➕ clones a hidden `<template>` and inserts a new row with id `new_{N}` immediately below the clicked row; on Save the route allocates a real field via `add_default_response_field` and applies the operator-typed label / required / help. New rows seed with auto-generated `Rating{N}` label, `rating{N}` key, `Integer` type, `Required = ✓`. Cancel discards both add and delete. The matching Response Fields Help row follows along — added or hidden in lockstep with its parent response row. |

Default seed (two rows, applied to a freshly-created instrument):

| Key | Friendly Label | Type | Required | Order |
|---|---|---|---|---|
| `rating1` | `Rating` | `1-to-5` | ✓ | 1 |
| `comments1` | `Comments` | `Long_Text` |  | 2 |

#### Response Fields Help (full-width, below)

Title: `Response Fields Help`. Full-width card sitting directly
below the Display Fields + Response Fields grid, invisible
borders. One row per Response Fields row. Columns:

| Column | Behaviour |
|---|---|
| **Field** | Identifies which Response Fields row this help row attaches to. Read-only `<code>` (matches the row's `field_key`). |
| **Text** | Operator-typed help text for that Response Fields row. In edit mode renders as a 2-row textarea joined to the bulk-save form via `name="help_text"` + sibling `name="help_text_id"` parallel arrays. Persists to `instrument_response_fields.help_text` on Save. |
| **Show** | Checkbox — whether the help text should appear next to the field on the reviewer surface. In edit mode bound to the bulk-save form via `name="help_text_visible_ids"`. Persists to `instrument_response_fields.help_text_visible`. |

In locked mode the Text cell shows the help text (or `—` when
empty) and the Show checkbox is disabled.

### C. Action buttons (right-aligned)

Five buttons, in this order, using the canonical `.btn` modifier
classes from `spec/assumptions.md`:

| Button | Style | Behaviour |
|---|---|---|
| `Save` | Primary | Writes the current friendly description, Display Fields, Response Fields, and Response Fields Help to the database in one bulk-save round-trip. On success, the page **stays in place**, the description and both tables lock, and a `saved` pill on the per-instrument status sub-card replaces the `not saved` pill. The button is replaced by `Edit`. |
| `Cancel` | Alert Outline | Discards any unsaved edits across description + tables and locks them. The button is replaced by `Edit`. Only shown alongside `Save` (i.e. while the card is open for editing). |
| `Edit` | Alert | Re-opens the description textarea and both tables for editing. The button is replaced by the `Save` + `Cancel` pair. |
| `Add new instrument` | Alert | Adds a new Instrument card immediately below this one and persists the new instrument to the database. |
| `Delete this instrument` | Danger | Deletes this instrument. Triggers an on-screen warning + confirmation before the request fires. |

`Save` + `Cancel` and `Edit` are **mutually exclusive** — only
one of the two states is shown at a time. When the card is open
for editing, `Save` and `Cancel` are shown; when the card is
locked, only `Edit` is shown.

**Two avenues, same state.** The `Save` / `Cancel` / `Edit` set
appears in **two places** on the per-instrument card — bottom-
right of this row, and bottom-left of the Section A description
card. The pairs share the same underlying state machine
(`?editing={iid}` URL param + the shared `dfsave-{iid}` form), so
the operator can flip in or out of edit mode from either pair
without scrolling past the tables.

#### Initial state

- A **brand-new instrument** card (operator just clicked
  `Add new instrument`, or the session was just created and the
  default instrument was seeded) starts in the **editable** state
  — `Save` + `Cancel` shown, tables open.
- An **existing instrument** with previously-saved field rows
  starts in the **locked** state — `Edit` shown, tables read-only.

#### Locked when session is `ready`

While the session is `ready` (the yellow lock card at the top of
the page is visible), every per-instrument card stays in the
**locked** state regardless of saved-vs-new, and the `Save` /
`Cancel` / `Edit` buttons render greyed-out (disabled) so the
operator cannot toggle into edit mode. The operator must
`Revert to draft` (via the lock card) before any of the
field-table buttons become usable. The `Add new instrument` and
`Delete this instrument` buttons follow the same lock — both are
disabled while `ready`.

## Add / Delete semantics

The Add / Delete semantics in this section apply to **instrument
cards** only. The Response Type Definitions card itself is
permanent — it cannot be added or removed.

**Add new instrument** appends a new instrument card below the
current one. The underlying database row is created immediately
(no draft / unsaved state). The new card seeds with the default
Display Fields and Response Fields rows defined above.

**Delete this instrument** removes the instrument and all its
dependent rows (display fields, response fields, assignments,
responses) via cascade. The on-screen confirmation must mention
the cascade so the operator isn't surprised.

After a deletion, the surviving instruments are **promoted** —
their `Instrument #N` numbering reflects their post-deletion
position. Example: if `Instrument #2` is deleted and `Instrument
#3` exists, `Instrument #3` becomes `Instrument #2` (both in the
database `Instrument.order` and in the on-screen `#N` header).
This matches the existing service-layer repack in
`delete_instrument` (`app/services/instruments.py`).

## Response Type Definitions card

Full-width card. Title: `Response Type Definitions`. Catalog of
response types referenced by every instrument's Response Fields
table; the Response Fields `Type` column is a dropdown over this
card's `Response Type` column. The card itself cannot be deleted
— it's a permanent fixture of the page.

Columns:

| Column | Behaviour |
|---|---|
| **Response Type** | Operator-typed name. The value referenced by Response Fields rows. Operator-editable for non-seeded rows; the seeded rows below are name-locked. |
| **Data Type** | One of `String`, `Decimal`, `Integer`, `List`. Drives which of the trailing columns apply. **Locked once set** — operator cannot change Data Type after a row is saved (seeded or operator-added). To change a row's Data Type, delete it (if operator-added) and re-add. |
| **Min** | Applies when Data Type is `Decimal`, `Integer`, or `String`. For `Decimal` / `Integer`: minimum value. For `String`: minimum number of characters. Rendered as `NA` and read-only when not applicable. |
| **Max** | Applies when Data Type is `Decimal`, `Integer`, or `String`. For `Decimal` / `Integer`: maximum value. For `String`: maximum number of characters. Rendered as `NA` and read-only when not applicable. |
| **Step** | Applies when Data Type is `Decimal` or `Integer`. The allowed increment between Min and Max. Rendered as `NA` and read-only when not applicable. |
| **List** | Applies when Data Type is `List`. Comma-separated list of allowed items. Rendered as `NA` and read-only when not applicable. |
| **Action** | Inline buttons depending on row state. Seeded rows render an empty cell (no buttons). Saved operator-defined rows render an `Edit` button (Alert). Clicking `Edit` flips that row into the unlocked state — its Action cell swaps to `Save` (Primary), `Cancel` (Alert outline), and `Delete` (Danger). While one row is unlocked, every other operator-defined row's `Edit` greys out. Delete on an in-use row routes through the cascade-confirm flow ("Cascade-on-delete" below); delete on a not-in-use row is gated by a JS `confirm()` warning before the immediate drop. Adding a new operator-defined row goes through the separate `Add a Response Type` block below the table. |

#### Locked vs. operator-added rows

The seeded rows below are **fully locked**: name is locked, Data
Type is locked, all Min / Max / Step / List parameters are
locked, and the row cannot be deleted. They are read-only
catalogs; operators reference them from Response Fields and
nothing else.

For operator-added rows:

- **Name** is locked once set (see "Editing flow" below for the
  gated commit). Renaming would shift the contract on every
  Response Fields row that references it.
- **Data Type** is locked once set, per the column note above.
- **Min / Max / Step / List** stay editable. Edits propagate to
  every Response Fields row that references this Response Type:
  on the next bulk-save round-trip the engine re-derives the
  validation block from the (updated) RTD row and writes it to
  `instrument_response_fields.validation`.

#### Default seed (ten rows; cannot be deleted, edited, or renamed)

| Response Type | Data Type | Min | Max | Step | List |
|---|---|---|---|---|---|
| `Long_text` | `String` | 0 | 200 | NA | NA |
| `Short_text` | `String` | 0 | 50 | NA | NA |
| `Yes_no` | `List` | NA | NA | NA | `Yes, No` |
| `Grade` | `List` | NA | NA | NA | `A+, A, A-, B+, B, B-, C+, C, D+, D, F` |
| `Likert5` | `List` | NA | NA | NA | `Strongly Disagree, Disagree, Neutral, Agree, Strongly Agree` |
| `100int` | `Integer` | 0 | 100 | 1 | NA |
| `0-to-2int` | `Integer` | 0 | 2 | 1 | NA |
| `1-to-5int` | `Integer` | 1 | 5 | 1 | NA |
| `1-to-5half` | `Decimal` | 1 | 5 | 0.5 | NA |
| `1-to-5dec` | `Decimal` | 1 | 5 | 0.1 | NA |

#### Cascade-on-delete

Deleting an **operator-added** Response Type that is referenced
by at least one Response Fields row triggers a confirmation
dialog before the request fires. The dialog states the cascade
in plain language — `Deleting "{name}" will drop N response
field row(s) on M instrument(s) and X recorded response(s)
across Y reviewer assignment(s). Continue?` — and only commits
on confirm. The cascade itself runs through the
`instrument_response_fields.response_type_id` foreign key with
`ON DELETE CASCADE`, which propagates to `responses` via the
existing FK. Seeded rows can never be deleted (no cascade ever
fires from a seeded row).

### Validation derivation

Each row's Data Type + applicable cells map unambiguously to the
JSON `validation` block written to `instrument_response_fields.validation`
when an instrument's Response Fields row references this Response Type:

| Data Type | `validation` JSON shape |
|---|---|
| `Integer` | `{"min": <int>, "max": <int>, "step": <int>}` |
| `Decimal` | `{"min": <float>, "max": <float>, "step": <float>}` |
| `String` | `{"min_length": <int>, "max_length": <int>}` |
| `List` | `{"choices": [<str>, ...]}` (CSV split, each item trimmed of leading / trailing whitespace) |

Worked examples for the seeded rows:

- `Long_text` → `{"min_length": 0, "max_length": 200}`
- `Short_text` → `{"min_length": 0, "max_length": 50}`
- `Yes_no` → `{"choices": ["Yes", "No"]}`
- `Grade` → `{"choices": ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "D+", "D", "F"]}`
- `Likert5` → `{"choices": ["Strongly Disagree", "Disagree", "Neutral", "Agree", "Strongly Agree"]}`
- `100int` → `{"min": 0, "max": 100, "step": 1}`
- `0-to-2int` → `{"min": 0, "max": 2, "step": 1}`
- `1-to-5int` → `{"min": 1, "max": 5, "step": 1}`
- `1-to-5half` → `{"min": 1, "max": 5, "step": 0.5}`
- `1-to-5dec` → `{"min": 1, "max": 5, "step": 0.1}`

#### Save-time validation rules

The Definitions card rejects a row at save time if any of the
following hold (operator must fix before the row commits):

- **List with zero items** when Data Type is `List`.
- **Min > Max** when Data Type is `Integer`, `Decimal`, or `String`.
- **Step does not evenly divide (Max − Min)** when Data Type is
  `Integer` or `Decimal`. (E.g. `Min=1, Max=5, Step=0.3` is
  rejected — the operator is expected to do the math.)
- **Decimal `Min` / `Max` / `Step` carries more than one decimal
  place** when Data Type is `Decimal`. (E.g. `Step=0.05` is
  rejected; `Step=0.1` is accepted. The display is also pinned to
  one decimal place — see "Display formatting" below.)
- **Integer `Min` / `Max` / `Step` is non-integer** when Data Type
  is `Integer`. The cell rejects any value with a fractional
  component on save.

#### Display formatting

`Min`, `Max`, and `Step` cells in the Response Type Definitions
card render numerically by Data Type:

- `Integer` and `String` (where applicable) — plain integer with
  no decimal point. E.g. `100int` → `Min=0`, `Max=100`, `Step=1`.
- `Decimal` — exactly one decimal place. E.g. `1-to-5half` →
  `Min=1.0`, `Max=5.0`, `Step=0.5`.

### Editing flow

The card has two states:

- **Locked (default).** Each operator-defined row's Action
  column carries an `Edit` button (Alert style). Seeded rows
  have an empty Action cell — they are read-only catalog
  entries.
- **Unlocked.** Clicking `Edit` on an operator-defined row
  opens that row for editing: Min / Max / Step / List become
  text inputs; the Action column shows `Save` (Primary),
  `Cancel` (Alert outline), and `Delete` (Danger) inline.
  While one row is unlocked, **every other operator-defined
  row's `Edit` button greys out** — the operator must
  Save / Cancel / Delete the unlocked row before unlocking
  another. The `Add a Response Type` form below the table
  also disables.

A new operator-defined row enters via a separate
`Add a Response Type` block (right-aligned, below the table).
The block takes only the **Name** and **Data Type**. Clicking
**Add** clones a draft row into the main table — applicable
parameter cells become text inputs, with `Save` and `Cancel`
inline. The draft row is **not persisted** until Save commits
it; Cancel removes it from the DOM with no DB write.

Per Data Type, the applicable parameter cells (those that
become text inputs in the draft / edit row) are:

| Data Type | Applicable cells | NA / read-only |
|---|---|---|
| `Integer` | `Min`, `Max`, `Step` | `List` |
| `Decimal` | `Min`, `Max`, `Step` | `List` |
| `String` | `Min`, `Max` | `Step`, `List` |
| `List` | `List` | `Min`, `Max`, `Step` |

Once a row is saved, the **Response Type name** and
**Data Type** are locked — both render as plain text. Min /
Max / Step / List remain editable on subsequent unlocks, and
edits propagate to every Response Fields row that references
this Response Type by re-deriving the validation block on save.

**Server-side enforcement is the source of truth.** Save
rejects an incomplete or invalid payload (per "Save-time
validation rules" above) and the page redirects back with an
inline error banner; the operator's typed values stay in the
inputs to be fixed.

## Open / deferred

- **Response Type Definitions persistence** — the card is now
  spec'd but unwired. The rebuild slice that lands it (Slice 4 of
  Segment 10D) introduces a new `response_type_definitions` table
  keyed by session, with the ten seeded rows above guaranteed
  present, fully locked (name + Data Type + parameters), and
  un-deletable. `instrument_response_fields.response_type`
  becomes `response_type_id` — a foreign key into the new table
  with `ON DELETE CASCADE`. See `guide/segment_10D.md` Slice 4
  for the 4a (schema + read-only render) / 4b (gated editing +
  cascade-on-delete UX) split.
- **Multi-instrument support** — `Add new instrument` ships
  **disabled** in the first rebuild slice (with the same
  "Multi-instrument support is still in progress" tooltip the
  current `main` carries) and gets enabled in a follow-up. Per
  `unfinished_business.md` item #18.
- **Display Fields persistence** — the table was stripped in
  #206. The rebuild slice that wires this is the first that
  consumes `InstrumentDisplayField` rows again from the operator
  UI; it also extends `_VALID_DISPLAY_SOURCES` in
  `app/services/instruments.py` with `(reviewee, name)` and
  `(reviewee, email_or_identifier)` so the two mandatory rows
  can persist as ordinary display-field rows.
- **Sort column** — placeholder; the *default row order on
  reviewer surface* UX is open.
- **Per-instrument preview integration** — earlier drafts of
  this spec carried a Section D `Preview Instrument #{N}` card
  (a per-instrument inline preview). The shared
  `Preview reviewer surface` page at
  `/operator/sessions/{id}/preview` already renders the reviewer
  surface for the whole session, so the per-instrument card no
  longer renders a preview placeholder. How the two integrate is
  open: should each card carry a `Preview this instrument` action
  that links into the appropriate section of `/preview`? Should
  `/preview` extend to render help text alongside response
  fields? Should the per-instrument card host a no-mock-data
  inline summary instead? Revisit in a follow-up segment.
