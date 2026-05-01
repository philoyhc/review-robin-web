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
2. **Full-width info card** containing the 6-button setup nav
   (`Session`, `Reviewers`, `Reviewees`, `Assignments`,
   `Instruments`, `Email Invites`). The Instruments button is
   rendered as Primary Outline; the rest are Primary. See
   `spec/operator_map.md` "Setup nav" for the canonical contract.
3. **Full-width yellow "session ongoing" lock card**, only when
   the session status is `ready`. See `spec/operator_map.md`
   "Session ongoing yellow lock card".
4. **Full-width "All Instrument Status" card** with summary pills
   and bulk action buttons. Subject to revision in a later slice.
5. **One full-width per-instrument card per instrument**, in
   `Instrument.order`. Card layout in the next section.
6. **Full-width "Response Type Definitions" card**. Catalog of
   response types (with validation rules) referenced by every
   instrument's Response Fields table. Layout in
   "Response Type Definitions card" below.

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

Equal-height, top + bottom aligned (`.bottom-grid`).

**Left card** — invisible borders.

- Header: `Instrument #{N}` rendered in a font size larger than
  normal card titles but smaller than the page H1.
- Friendly description (free text, operator-typed).
- `Edit` button → opens an inline form for editing the description.

**Right card** — `This Instrument's Status`.

- Instrument-specific status pills (accepting / not accepting,
  visibility-when-closed showing / not showing,
  deadline-closed-at if present).
- Action buttons for visibility-to-reviewers (open / close,
  show-when-closed / don't-show-when-closed).

### B. Display Fields + Response Fields (two half-width cards side by side)

Equal-height, top + bottom aligned (`.bottom-grid`). Both cards
have invisible borders.

#### Reordering convention

Both tables in this section let the operator reorder rows. Rather
than asking the operator to type integers, each row carries two
small arrow buttons (`▲` and `▼`) in its `Order` cell. Clicking
`▲` swaps this row with the row immediately above; `▼` swaps with
the row immediately below. The arrow is disabled at the boundary
(top row's `▲`, bottom row's `▼`). The integer to the left of the
arrows is informational — it always reflects the row's current
position post-swap and is not directly editable.

#### Display Fields (left)

Title: `Display Fields`. Columns:

| Column | Behaviour |
|---|---|
| **Source** | System name. Read-only `<code>`. Eligible rows, in default order: `RevieweeName`, `RevieweeEmail`, then any reviewee data column with at least one populated value (`PhotoLink`, `RevieweeTag1/2/3`), then any pair-context slot with at least one populated value across the session's assignments (`PairContext1/2/3`). `AssignmentContext1/2/3` is deliberately **excluded** — it's logic-engaging and hidden from reviewers (see `spec/architecture.md` "Pair-level vs assignment-level context"). |
| **Friendly Label** | Operator-editable text. Save persists to the underlying database. |
| **Include** | Checkbox. `RevieweeName` and `RevieweeEmail` are mandatory-checked and the checkbox is locked (operator cannot uncheck). All other rows are operator-toggleable. |
| **Order** | Integer (1-based) plus the `▲` / `▼` arrow controls described above. Initial seed: `RevieweeName=1`, `RevieweeEmail=2`, then the present rows in the order `PhotoLink`, `RevieweeTag1/2/3`, `PairContext1/2/3` (skipping any that have no data). |
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
| **Action** | A delete cross icon (✗) and an add-row plus icon (➕). Both fire immediately — no on-screen warning or confirmation. The delete removes this row; the add inserts a new default row immediately below. New rows seed with auto-generated `Rating{N}` label, `rating{N}` key, `Integer` type, `Required = ✓`. |

Default seed (two rows, applied to a freshly-created instrument):

| Key | Friendly Label | Type | Required | Order |
|---|---|---|---|---|
| `rating1` | `Rating` | `1-to-5` | ✓ | 1 |
| `comments1` | `Comments` | `Long_Text` |  | 2 |

### C. Horizontal rule

A single `<hr>` separating the field-builder from the preview.

### D. Preview Instrument #{N}

Full-width card, invisible borders. Title: `Preview Instrument #{N}`.
Renders a table populated with **three rows of preview data** so
the operator can see how the configured columns will look on the
reviewer surface. Source of those three rows:

- If the session has three or more reviewees imported, use the
  first three reviewees (matching their real `name` /
  `email_or_identifier` and any populated tag / profile / pair-
  context values).
- If the session has fewer than three reviewees, show the real
  ones first (in import order) and pad with mock rows up to three
  total. The mock rows use plausible-looking placeholder values
  (`Sample Reviewee 1` / `sample1@example.edu`, etc.).
- If the session has zero reviewees, show three mock rows.

Columns:

1. **Name / Email** — name on top, email as subtitle beneath
   (matches the Reviewer / Reviewee preview rendering elsewhere).
2. **One column per included Display Fields row**, ordered by the
   row's `Order` value, header rendered as the row's
   `Friendly Label`. (`RevieweeName` / `RevieweeEmail` are folded
   into the Name / Email column above and not duplicated here.)
3. **One column per Response Fields row**, ordered by the row's
   `Order` value, header rendered as the row's `Friendly Label`.
   When the row's `Required` checkbox is checked, the column
   header is appended with an asterisk (e.g. `Rating*`) to signal
   to the operator that the field will be mandatory for reviewers.

### E. Action buttons (right-aligned)

Five buttons, in this order, using the canonical `.btn` modifier
classes from `spec/assumptions.md`:

| Button | Style | Behaviour |
|---|---|---|
| `Save` | Primary | Writes the current Display Fields and Response Fields tables to the database. On success, the page **stays in place**, both tables lock, and a flash message confirms the save. The button is replaced by `Edit`. |
| `Cancel` | Alert Outline | Discards any unsaved edits in the two tables, reverts them to the last-saved state, and locks them. The button is replaced by `Edit`. Only shown alongside `Save` (i.e. while the tables are open for editing). |
| `Edit` | Alert | Re-opens both tables for editing. The button is replaced by the `Save` + `Cancel` pair. |
| `Add new instrument` | Alert | Adds a new Instrument card immediately below this one and persists the new instrument to the database. |
| `Delete this instrument` | Danger | Deletes this instrument. Triggers an on-screen warning + confirmation before the request fires. |

`Save` + `Cancel` and `Edit` are **mutually exclusive** — only
one of the two states is shown at a time. When the two tables are
open for editing, `Save` and `Cancel` are shown; when the two
tables are locked, only `Edit` is shown.

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
| **Data Type** | One of `String`, `Decimal`, `Integer`, `List`. Drives which of the trailing columns apply. |
| **Min** | Applies when Data Type is `Decimal`, `Integer`, or `String`. For `Decimal` / `Integer`: minimum value. For `String`: minimum number of characters. Rendered as `NA` and read-only when not applicable. |
| **Max** | Applies when Data Type is `Decimal`, `Integer`, or `String`. For `Decimal` / `Integer`: maximum value. For `String`: maximum number of characters. Rendered as `NA` and read-only when not applicable. |
| **Step** | Applies when Data Type is `Decimal` or `Integer`. The allowed increment between Min and Max. Rendered as `NA` and read-only when not applicable. |
| **List** | Applies when Data Type is `List`. Comma-separated list of allowed items. Rendered as `NA` and read-only when not applicable. |
| **Action** | A delete cross icon (✗) and an add-row plus icon (➕). Same pattern as the Response Fields Action column — both fire immediately, no confirmation. The delete is **suppressed for seeded rows** (operator can't remove a seeded type); the add inserts a new row immediately below. |

Default seed (six rows; cannot be deleted):

| Response Type | Data Type | Min | Max | Step | List |
|---|---|---|---|---|---|
| `Long_text` | `String` | 0 | 500 | NA | NA |
| `Short_text` | `String` | 0 | 59 | NA | NA |
| `Grade` | `List` | NA | NA | NA | `A+, A, A-, B+, B, B-, C+, C, D+, D, F` |
| `1-to-5int` | `Integer` | 1 | 5 | 1 | NA |
| `1-to-5half` | `Decimal` | 1 | 5 | 0.5 | NA |
| `1-to-5dec` | `Decimal` | 1 | 5 | 0.1 | NA |

Operator-added rows are deletable. Editing a Response Type that's
in use by an instrument's Response Fields row propagates the new
validation to that row on save (the engine writes the resulting
constraints to `instrument_response_fields.validation`).

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

- `Long_text` → `{"min_length": 0, "max_length": 500}`
- `Short_text` → `{"min_length": 0, "max_length": 59}`
- `Grade` → `{"choices": ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "D+", "D", "F"]}`
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

### Editing flow (gated, left-to-right)

Cells must be filled in column order. A cell is locked (not
editable) until the cell(s) to its left are filled validly:

1. **`Response Type`** — free text. Must be non-empty before
   `Data Type` unlocks.
2. **`Data Type`** — picker (`String` / `Decimal` / `Integer` /
   `List`). Picking a Data Type immediately determines which of
   the trailing columns become editable; the others render as
   `NA` and are read-only:

   | Data Type | Editable trailing columns (in order) | NA / read-only |
   |---|---|---|
   | `Integer` | `Min` → `Max` → `Step` | `List` |
   | `Decimal` | `Min` → `Max` → `Step` | `List` |
   | `String` | `Min` → `Max` | `Step`, `List` |
   | `List` | `List` | `Min`, `Max`, `Step` |

3. Within the editable trailing columns, each cell is locked
   until the previous one in that order is filled validly.

A row is **incomplete** until all applicable cells are filled. An
incomplete row is not committed to the underlying database; the
operator either completes the row or removes it via the Action
column ✗.

If an operator changes a previously-saved row's Data Type, the
trailing cells reset (per the new Data Type's editable list) and
the row re-enters the gated flow. The save-time validation rules
above re-apply on commit.

## Open / deferred

- **All Instrument Status card** — content and action buttons
  subject to revision; the current shape (deadline pill, accepting
  count, visibility count, bulk action buttons) carries over until
  that revision lands.
- **Response Type Definitions persistence** — the card is now
  spec'd but unwired. The rebuild slice that lands it needs a new
  `response_type_definitions` table (or equivalent) keyed by
  session, with the seeded six rows guaranteed present and
  un-deletable.
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
- **Help text** — `instrument_response_fields.help_text` and
  `help_text_visible` exist per row but the spec doesn't yet
  surface them in the Response Fields table; placement is open.
