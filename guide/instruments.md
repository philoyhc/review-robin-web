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

Five sections, top to bottom, inside one full-width card:

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

### B. Reviewee Fields + Response Fields (two half-width cards side by side)

Equal-height, top + bottom aligned (`.bottom-grid`). Both cards
have invisible borders.

#### Reviewee Fields (left)

Title: `Reviewee Fields`. Columns:

| Column | Behaviour |
|---|---|
| **Source** | System name. Read-only `<code>`. Rows are `RevieweeName`, `RevieweeEmail`, plus every reviewee data column that has at least one populated value (`PhotoLink`, `RevieweeTag1/2/3`). |
| **Friendly Label** | Operator-editable text. Save persists to the underlying database. |
| **Include** | Checkbox. `RevieweeName` and `RevieweeEmail` are mandatory-checked and the checkbox is locked (operator cannot uncheck). All other rows are operator-toggleable. |
| **Order** | Integer. Initial seed: `RevieweeName=0`, `RevieweeEmail=1`, then the present reviewee columns in the order `PhotoLink`, `RevieweeTag1`, `RevieweeTag2`, `RevieweeTag3`. |
| **Sort** | Empty for now. Placeholder for a future default row order on reviewer surface. |

#### Response Fields (right)

Title: `Response Fields`. Columns:

| Column | Behaviour |
|---|---|
| **Key** | The system name for the row. Read-only `<code>`. |
| **Friendly Label** | Operator-editable text. Save persists. |
| **Type** | One of the response types defined by the Response Type definitions card. Read-only post-create. |
| **Required** | Checkbox. When checked, the field is mandatory for reviewers and the column header in the Preview table is appended with an asterisk (e.g. `Rating*`). |
| **Order** | Integer (1-based, contiguous). |
| **Action** | A delete cross icon (✗) and an add-row plus icon (➕). Both fire immediately — no on-screen warning or confirmation. The delete removes this row; the add inserts a new default row immediately below. |

Default seed (two rows, applied to a freshly-created instrument):

| Key | Friendly Label | Type | Required | Order |
|---|---|---|---|---|
| `rating1` | `Rating` | `1-to-5` | ✓ | 1 |
| `comments1` | `Comments` | `Long_Text` |  | 2 |

### C. Horizontal rule

A single `<hr>` separating the field-builder from the preview.

### D. Preview Instrument #{N}

Full-width card, invisible borders. Title: `Preview Instrument #{N}`.
Renders a table populated with **three rows of mock data** so the
operator can see how the configured columns will look on the
reviewer surface without needing real reviewees imported. Columns:

1. **Name / Email** — name on top, email as subtitle beneath
   (matches the Reviewer / Reviewee preview rendering elsewhere).
2. **One column per included Reviewee Fields row**, ordered by the
   row's `Order` value, header rendered as the row's
   `Friendly Label`. (`RevieweeName` / `RevieweeEmail` are folded
   into the Name / Email column above and not duplicated here.)
3. **One column per Response Fields row**, ordered by the row's
   `Order` value, header rendered as the row's `Friendly Label`.
   When the row's `Required` checkbox is checked, the column
   header is appended with an asterisk (e.g. `Rating*`) to signal
   to the operator that the field will be mandatory for reviewers.

### E. Action buttons (right-aligned)

Four buttons, in this order, using the canonical `.btn` modifier
classes from `spec/assumptions.md`:

| Button | Style | Behaviour |
|---|---|---|
| `Save` | Primary | Writes the current Reviewee Fields and Response Fields tables to the database, then locks both tables for editing. The button is replaced by `Edit`. |
| `Edit` | Alert | Re-opens both tables for editing. The button is replaced by `Save`. |
| `Add new instrument` | Alert | Adds a new Instrument card immediately below this one and persists the new instrument to the database. |
| `Delete this instrument` | Danger | Deletes this instrument. Triggers an on-screen warning + confirmation before the request fires. |

`Save` and `Edit` are **mutually exclusive** — only one is visible
at a time. When the two tables are open for editing, `Save` is
shown; when the two tables are locked, `Edit` is shown.

## Response Type Definitions card

Full-width card. Title: `Response Type Definitions`. Catalog of
response types referenced by every instrument's Response Fields
table; the Response Fields `Type` column is a dropdown over this
card's `Response Type` column.

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

## Add / Delete semantics

**Add new instrument** appends a new instrument card below the
current one. The underlying database row is created immediately
(no draft / unsaved state). The new card seeds with the default
Reviewee Fields and Response Fields rows defined above.

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
- **Multi-instrument support** — `Add new instrument` is disabled
  on `main` today (per `unfinished_business.md` item #18). The
  decision to enable / delete is the next P0 unblock.
- **Reviewee Fields persistence** — the table is currently a
  static placeholder (PR #205 → stripped in #206). The rebuild
  slice that wires this is the first that consumes
  `InstrumentDisplayField` rows again from the operator UI.
- **Sort column** — placeholder; the row-reorder UX is open. The
  service-layer `bulk_save_fields` already supports per-table
  rank changes, so when the UI lands it can use the existing
  endpoint.
