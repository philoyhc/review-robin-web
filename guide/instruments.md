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
6. **Half-width "Response Type definitions" card** on the left.
   Content TBD; placeholder for a static reference of the four
   response types (`Integer`, `Short Text`, `Long Text`, `Yes/No`).

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
| **Sort** | Empty for now. Placeholder for a future row-reorder control. |

#### Response Fields (right)

Title: `Response Fields`. Columns:

| Column | Behaviour |
|---|---|
| **Key** | The system name for the row. Read-only `<code>`. |
| **Friendly Label** | Operator-editable text. Save persists. |
| **Type** | One of the four response types. Read-only post-create. |
| **Order** | Integer (1-based, contiguous). |
| **Action** | A delete cross icon (✗) and an add-row plus icon (➕). Both fire immediately — no on-screen warning or confirmation. The delete removes this row; the add inserts a new default row immediately below. |

Default seed (two rows, applied to a freshly-created instrument):

| Key | Friendly Label | Type | Order |
|---|---|---|---|
| `rating1` | `Rating` | `1-to-5` | 1 |
| `comments1` | `Comments` | `Long_Text` | 2 |

### C. Horizontal rule

A single `<hr>` separating the field-builder from the preview.

### D. Preview Instrument #{N}

Full-width card, invisible borders. Title: `Preview Instrument #{N}`.
Renders a table with one synthetic row per sample reviewee. Columns:

1. **Name / Email** — name on top, email as subtitle beneath
   (matches the Reviewer / Reviewee preview rendering elsewhere).
2. **One column per included Reviewee Fields row**, ordered by the
   row's `Order` value, header rendered as the row's
   `Friendly Label`. (`RevieweeName` / `RevieweeEmail` are folded
   into the Name / Email column above and not duplicated here.)
3. **One column per Response Fields row**, ordered by the row's
   `Order` value, header rendered as the row's `Friendly Label`.

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
- **Response Type definitions card** — content TBD; layout
  question (does the half-width card sit alone with empty space on
  the right, or pair with something else?).
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
