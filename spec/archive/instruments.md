> **Archived 2026-05-26.** Consolidated into the rewritten
> `spec/instruments.md` together with `instrument_builder.md` and
> the operator-card / model-side half of `group_scoped_instruments.md`.
> Kept here for historical reference; the current spec is the
> authoritative source.

# Instruments page

Specification for the per-session **Instruments** operator page at
`/operator/sessions/{id}/instruments`. Captures the desired surface
shape post-cleanup (PRs #205, #206) so the rebuild can land in
small slices.

This file describes **what should be on the page**. It does not
describe the routes, services, or schema that back it — those live
in `app/web/routes_operator/_instruments.py`,
`app/services/instruments/` (split by concern: `_rtds.py`,
`_display_fields.py`, `_response_fields.py`, `_instrument_crud.py`,
`_state.py`), and `app/db/models/instrument*.py`.
When a behaviour below is unwired
("Save writes to the database"), the rebuild slice that lands it
also wires the route + service + persistence.

## Page layout

Top to bottom:

1. **Chrome** (`session-nav-card` partial) — wraps the two-row
   top nav (Manage row + Setup row) and the per-entity status
   strip. The Setup-row `Instruments` tab renders active.
2. **Full-width status + bulk-actions card** carrying session-wide
   instrument status (deadline, accepting / not accepting,
   visibility-when-closed counts) plus the bulk
   visibility-when-closed toggle right-aligned at the bottom.
   Layout in "Status + bulk-actions card" below.
3. **Full-width yellow "session ongoing" lock card**, only when
   the session status is `ready`. See `spec/visual_style_rrw.md`
   "Warning surfaces — shared brown framing > Lock card uses".
4. **One full-width per-instrument card per instrument**, in
   `Instrument.order`. Card layout in "Per-instrument card" below.
5. **Full-width "Response Type Definitions" card**. Catalog of
   response types (with validation rules) referenced by every
   instrument's Response Fields table. Layout in
   "Response Type Definitions card" below.

## Status + bulk-actions card

Below the chrome (`session-nav-card` partial, which itself wraps
the Setup-row navigation tabs and the per-entity status strip),
the page renders a single full-width info card carrying both the
status counts and the page-wide bulk-visibility toggle. The card
has two rows:

1. **Status row** (left-aligned, all on one line). Format:
   `Session deadline (auto-close): {deadline pill} · {N accepting} ·
   {N not accepting} · Visibility when closed: {N showing} ·
   {N not showing}`. The deadline pill renders the ISO-formatted
   deadline (or `not set`); the four counts render as count /
   empty pills. Pluralisation on the visibility-when-closed pills
   follows the count.
2. **Bulk visibility-toggle row** (right-aligned). A single
   `btn secondary` POST: `Show all when closed` when at least
   one instrument is currently hidden, otherwise
   `Don't show any when closed`. Clicking it bulk-flips
   `responses_visible_when_closed` across every instrument in
   the session.

Earlier drafts of this spec called for a separate
`Actions for All Instruments` card below the header to host the
bulk visibility toggle plus a `Preview reviewer surface` button.
That split is **retired**. The bulk toggle was small enough to
co-locate with status; the preview affordance lives in the
chrome's Operations row → Previews tab (see
`spec/preview_hub.md`) rather than on Instruments. The bulk
`Open all instruments` / `Close all instruments` actions stay
**dropped** — operators open and close instruments individually
via the per-instrument card's status sub-card.

The Setup-row nav itself (which highlights the `Instruments`
tab when active) is owned by the shared
`session_top_nav.html` partial and styled via the `.nav-tab`
classes in `spec/visual_style_rrw.md` "Operator session chrome
> Navigation chrome (two-row layout)" — *not* the canonical
`.btn` modifier classes catalogued in `spec/ui_elements.md` §6.

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

### A. Identity + Assignment Rule (two half-width cards side by side)

Equal-height, top + bottom aligned (`.bottom-grid` with
`align-items: stretch`). The card layout is the same for an
ordinary per-reviewee instrument and a group-scoped one — both
render through the shared `instrument_identity` macro; the only
group-scoped difference is Section B's reshaped Display Fields
table and a `Group-scoped` chip in the heading (Segment 13C
harmonization, 2026-05-19).

**Left card** — invisible borders, flex column.

- Header: `Instrument #{N}` rendered in a font size larger than
  normal card titles but smaller than the page H1, followed by
  the instrument-status pills inline — `accepting responses` /
  `not accepting responses` and `showing when closed` /
  `not showing when closed` — and, on a group-scoped instrument,
  a `Group-scoped` chip.
- **Short label** (Segment 11L) — operator-typed friendly handle
  used wherever the instrument needs a short name (multi-instrument
  page tabs, reviewer-surface page anchors). In **locked** mode
  renders as a bold one-line caption above the description (or is
  hidden entirely when empty); in **edit** mode renders as a
  small `<input form="dfsave-{iid}" name="short_label">` text
  field above the description textarea, joined to the same bulk-
  save form. Optional, capped at the column width of the
  underlying `Instrument.short_label` field.
- Friendly description (free text, operator-typed). In **locked**
  mode renders as plain text (`(no description)` when empty); in
  **edit** mode renders as a `<textarea form="dfsave-{iid}"
  name="description">` joined to the same bulk-save form as the
  Section B tables.
- Bottom-left button row: **Edit / Save+Cancel** plus, on a
  ready session, the visibility-to-reviewers buttons (open /
  close, show-when-closed / don't-show-when-closed). The
  separate "This Instrument's Status" sub-card was retired in
  the Segment 13C harmonization — its status pills moved into
  the heading and its open/close + visibility buttons moved here
  beside `Edit`. The `saved` / `not saved` pill and the
  deadline-closed note were retired outright.

**Right card** — the **Assignment Rule** sub-card (Segment 15B).
A `RuleSet` picker pinning `instruments.rule_set_id`, the
`Number of eligible pairs found` count, and — on a group-scoped
instrument — the secondary `(Number of reviewer-group pairs: M)`
figure.

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
| **Source** | System name. Read-only `<code>`. Eligible rows, in default order: `RevieweeName`, `RevieweeEmail`, then any reviewee data column with at least one populated value (`PhotoLink`, `RevieweeTag1/2/3`), then any pair-context slot with at least one populated value across the session's relationships (`PairContextTag1/2/3`, per the post-15D `relationships` table — see `spec/architecture.md` "Pair-level context"). |
| **Friendly Label** | **Read-only** since Segment 15A Slice 2 — auto-populates from the session-wide friendly-label resolver (`app/services/field_labels.py`). Operators rename a slot once per session on the **Reviewers / Reviewees / Relationships Setup page**, and the change flows through every Display Field cell that points at that source slot. The per-instrument `InstrumentDisplayField.label` column stays in the schema as dead data pending a follow-on cleanup segment. |
| **Include** | Checkbox. `RevieweeName` and `RevieweeEmail` are mandatory-checked and the checkbox is locked (operator cannot uncheck). All other rows are operator-toggleable. |
| **Order** | Integer (1-based) plus the `▲` / `▼` arrow controls described above. The arrows are suppressed for the `RevieweeName` and `RevieweeEmail` rows — they're locked at positions 1 and 2 respectively. Initial seed: `RevieweeName=1`, `RevieweeEmail=2`, then the present rows in the order `PhotoLink`, `RevieweeTag1/2/3`, `PairContext1/2/3` (skipping any that have no data). |
| **Sort** | Empty for now. Placeholder for a future default row order on reviewer surface; will use the same `▲` / `▼` reorder convention when it lands. |

#### Response Fields (right)

Title: `Response Fields`. Columns:

| Column | Behaviour |
|---|---|
| **Key** | The system name for the row. Read-only `<code>`. |
| **Friendly Label** | Operator-editable text. Save persists. |
| **Type** | One of the response types defined by the Response Type Definitions card. Read-only post-create. For newly-added rows (the JS-deferred draft pattern from Slice 2 / 4c) the Type is operator-picked from the session's RTD catalog — the `<select>` is enabled until Save commits the row, then locks. The Type carries its own validation rules (e.g. `1-to-5int` implies `min=1, max=5, step=1`); the engine derives them from the chosen RTD via `validation_block_for_rtd` and writes the JSON block to `instrument_response_fields.validation` on save. The operator does **not** see a validation cell in this table — edits to the underlying RTD's parameters propagate to every dependent RF row's `validation` on the next bulk-save round-trip. |
| **Required** | Checkbox. When checked, the field is mandatory for reviewers and the column header in the Preview table is appended with an asterisk (e.g. `Rating*`). |
| **Order** | Integer (1-based) plus the `▲` / `▼` arrow controls described above. |
| **Action** | A delete cross icon (✗) and an add-row plus icon (➕). Both are **client-side** — same deferral pattern as the `▲` / `▼` arrows. ✗ hides the row and queues its id in a hidden `response_delete_ids` input on the bulk-save form (or just removes the row from the DOM if it was JS-added). ➕ clones a hidden `<template>` and inserts a new row with id `new_{N}` immediately below the clicked row; on Save the route allocates a real field via `add_default_response_field` and applies the operator-typed label / required / help. New rows seed with auto-generated `Rating{N}` label, `rating{N}` key, `Integer` type, `Required = ✓`. Cancel discards both add and delete. The matching Response Fields Help row follows along — added or hidden in lockstep with its parent response row. |

Default seed (two rows, applied to a freshly-created instrument):

| Key | Friendly Label | Type | Required | Order |
|---|---|---|---|---|
| `rating1` | `Rating` | `1-to-5` | ✓ | 1 |
| `comments1` | `Comments` | `Long_Text` |  | 2 |

**Save-time guard (Slice 4d).** The bulk-save handler refuses to
commit an instrument with **zero** Response Fields rows. If the
operator's pending edits would leave the table empty, Save
redirects back to the page with an inline error banner —
*"An instrument must have at least one response field. Add one,
or undo the delete."* — and the editing context stays open so
the operator can fix the row set without losing their other
edits. This is symmetric with the cascade-side guard on the
Response Type Definitions card (see "Cascade-on-delete").

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

### C. Action row (two half-width cards)

The per-instrument card's bottom action row is a single
right-flushed row (no cards). Wave 4 (2026-05-25) restructured
both the buttons present and their state model. Left-to-right
at the right edge:

`Save` | `Cancel` | `Replicate` | `Delete` | `+Instrument` |
`Lock` / `Unlock`

`Save` and `Cancel` only render when the card is unlocked
(edit mode); the other four are always present. The separate
Danger Zone card was retired in the Segment 13C harmonization
(2026-05-19); `Delete` is now a `btn destructive` flush-right
in the row, and its confirm checkbox + message sit on a line
just below the row: *"Yes, delete {Group }Instrument #N and its
associated assignments and reviewer responses."*

`Delete` follows the **checkbox-gates-button** standard — it
renders `disabled` and is enabled only while the confirm
checkbox is ticked (`data-delete-confirm` / `data-delete-btn`
pairing). It is permanently disabled, regardless of the
checkbox, when this is the only instrument on the session, the
session is ongoing, or another card / RTD edit is open.

Buttons use the canonical `.btn` modifier classes catalogued in
`spec/ui_elements.md` §6:

| Button | Style | Behaviour |
|---|---|---|
| `Save` | Primary Outline (`btn secondary`) | Writes the current Band 1 form fields, Band 3 row state, and bulk-save batch to the database in one round-trip. Starts `disabled`; activates on the first dirty event (Band 1 input change or Band 3 row tick/X/+ click). Save **preserves** `?editing=<id>` on redirect so the card stays unlocked after Save — the operator keeps editing without re-unlocking (Wave 4 PR 2). |
| `Cancel` | Primary Outline (`btn secondary`) | Discards any unsaved client-side edits by reloading the page in edit mode (the form re-renders from persisted state). Confirms first (`confirm('Discard unsaved changes?')`). Mirrors Save's `disabled` state — when nothing is dirty there's nothing to discard. (Wave 4 PR 4c, PR #1443.) |
| `Replicate` | Primary Outline (`btn secondary`) | Clones this instrument's content into a new card slotted immediately after it (Segment 13C PR 3). |
| `Delete` | Danger (`btn destructive`) | Deletes this instrument; gated by the confirm checkbox below the row (checkbox-gates-button standard). |
| `+Instrument` | Primary Outline-Primary (`btn primary-outline`) | Spawns a new instrument immediately after this one. With every new instrument now created as a new-model one (post-Wave-3), this is the sole "create new instrument" affordance — the legacy `Add instrument` / `Add group instrument` buttons retired in Wave 4 PR 4c (PR #1443). |
| `Lock` / `Unlock` | Primary Outline (`btn secondary`) | The gating toggle. **Unlocked** = `?editing=<id>` in the URL (card is in edit mode); **Locked** = no editing param (view mode). Button label flips between the two states. Clicking `Lock` while Save is active (dirty) prompts a `confirm()` dialog before navigating away (Wave 4 PR 3). Modelled on the Quick Setup card's footer (`_quick_setup_card.html`). Replaces the pre-Wave-4 per-card `Edit` button. |

The Instruments page leans on Primary Outline (`btn secondary`)
across the per-instrument action surface so the visual
difference between Save / Cancel / Replicate / Lock stays
minimal — the role each button plays is conveyed by its label
and position, not by colour. The `Delete` (Danger) button is
the single exception; `+Instrument` uses `btn primary-outline`
to signal the create-something action.

**Lock owns gating; Save owns persistence.** Pre-Wave-4 the
`Save` action also implicitly re-locked the card (Save flipped
the URL back to view mode). Wave 4 PR 2 split these concerns —
Save persists and stays in edit mode; only `Lock` flips the
URL back to view mode. The mental model is consistent across
the page: lock state is visible, persistence is action-driven.

**Save dirty-tracking.** Save and Cancel both render `disabled`
on entry to edit mode (operator unlocks the card → URL adds
`?editing=<id>` → page re-renders with both buttons disabled).
The first dirty event flips both to enabled. After a successful
Save the server-side redirect re-renders fresh, returning both
buttons to disabled. **Per-row pending visual.** Band 3 rows
whose inputs the operator has typed into but not yet committed
via the ✓ button get a subtle amber-accent visual
(`[data-row-pending="true"]`); clicking ✓ clears it (Wave 4
PR 3, base.html inline CSS).

**One editing context at a time (Slice 4d).** The per-instrument
card's editing state and the Response Type Definitions card's
editing state are **mutually exclusive** — only one editing
context can be open on the page at a time. While any
per-instrument card is unlocked, every operator-defined RTD
row's `Edit` and `Delete` buttons + the `Add a Response Type`
block all render disabled (with a tooltip pointing back to the
open instrument). The reverse holds too: while an RTD row is
unlocked, every per-instrument card's `Unlock` toggle renders
as a disabled `<button>` with the explanatory tooltip
("Save or cancel the Response Type Definitions edit before
unlocking an instrument."). This stops the cross-table
cascade-edits problem (operator deletes an in-use RTD
mid-instrument-edit; the cascade rewrites RF rows the browser
still has open in inputs).

#### Initial state

- A **brand-new instrument** card (operator just clicked
  `+Instrument`, or the session was just created and the
  default instrument was seeded) starts **locked** in view
  mode. The operator clicks `Unlock` to enter edit mode. Save
  and Cancel start `disabled` until the first dirty event.
- An **existing instrument** with previously-saved field rows
  starts **locked** — `Unlock` shown, fields read-only.

#### Locked when session is `ready`

While the session is `ready` (the yellow lock card at the top of
the page is visible), every per-instrument card stays in the
**locked** state regardless of saved-vs-new, and the `Lock` /
`Unlock` toggle renders greyed-out (disabled) so the operator
cannot enter edit mode. The operator must `Revert to draft`
(via the lock card) before any of the field-table buttons
become usable. The `+Instrument` and `Delete this instrument`
buttons follow the same lock — both are disabled while `ready`.

## Add / Delete semantics

The Add / Delete semantics in this section apply to **instrument
cards** only. The Response Type Definitions card itself is
permanent — it cannot be added or removed.

**+Instrument** appends a new instrument card below the
current one. The underlying database row is created immediately
(no draft / unsaved state). The new card seeds with the default
Display Fields and Response Fields rows defined above. (The
pre-Wave-4 `Add new instrument` button was renamed to
`+Instrument` in PR #1443 — the only "create new instrument"
affordance left after the legacy `Add instrument` / `Add group
instrument` buttons retired in the same PR.)

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
`delete_instrument` (`app/services/instruments/_instrument_crud.py`).

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
| `Long_text` | `String` | 0 | 2000 | NA | NA |
| `Short_text` | `String` | 0 | 100 | NA | NA |
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

**Hard-block exception (Slice 4d): would-empty instrument.** If
the cascade would leave any instrument with **zero** Response
Fields rows (because the row referencing this RTD is that
instrument's only RF row), the delete is **blocked outright**
— the operator sees a banner naming the affected instrument(s)
in plain language: *"Cannot delete Response Type 'Foo': it is
the only Response Field on Instrument #2. Add or change a row
on that instrument first, then come back."* The banner has no
Continue button; the operator must either add a non-ODT row to
the affected instrument first or pick a different ODT to
delete. This guard is symmetric with the bulk-save side guard
that blocks "Save with zero RF rows" on direct deletes.

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

- `Long_text` → `{"min_length": 0, "max_length": 2000}`
- `Short_text` → `{"min_length": 0, "max_length": 100}`
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
`Add a Response Type` card (half-width `.card .card-half`,
flushed right inside the Response Type Definitions card; same
rounded-corners + border styling as other operator cards).
The card has a `<h2>` title, a muted helper paragraph (*"Click
Add to start a new row in the table above after choosing a name
and selecting the data type. Note that the data type of an
added row cannot be changed, though the row can be deleted."*),
and a single right-flushed inline row carrying the **Name**
input, the **Data Type** dropdown, and the **Add** button.
Clicking **Add** clones a draft row into the main table —
applicable parameter cells become text inputs, with `Save` and
`Cancel` inline. The draft row is **not persisted** until Save
commits it; Cancel removes it from the DOM with no DB write.

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
  with `ON DELETE CASCADE`. See `guide/archive/segment_10D.md` Slice 4
  for the 4a (schema + read-only render) / 4b (gated editing +
  cascade-on-delete UX) split.
- **Multi-instrument support** — `Add new instrument` ships
  **disabled** in the first rebuild slice (with the same
  "Multi-instrument support is still in progress" tooltip the
  current `main` carries) and gets enabled in a follow-up.
  (Shipped in Segment 10D Slice 5, 2026-05-02.)
- **Display Fields persistence** — the table was stripped in
  #206. The rebuild slice that wires this is the first that
  consumes `InstrumentDisplayField` rows again from the operator
  UI; it also extends `_VALID_DISPLAY_SOURCES` in
  `app/services/instruments/_display_fields.py` with `(reviewee, name)` and
  `(reviewee, email_or_identifier)` so the two mandatory rows
  can persist as ordinary display-field rows.
- **Sort column** — placeholder; the *default row order on
  reviewer surface* UX is open.
- **Per-instrument preview integration** — earlier drafts of
  this spec carried a Section D `Preview Instrument #{N}` card
  (a per-instrument inline preview). The shared Previews hub at
  `/operator/sessions/{id}/previews` (Segment 11F) renders the
  reviewer surface for the whole session inside its surface card,
  so the per-instrument card no longer renders a preview
  placeholder. How the two integrate is open: should each card
  carry a `Preview this instrument` action that links into the
  appropriate section of the hub's surface card? Should the hub
  extend to render help text alongside response fields? Should
  the per-instrument card host a no-mock-data inline summary
  instead? Revisit in a follow-up segment.
