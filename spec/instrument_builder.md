# Instrument Builder

Surface specification for the **Instrument Builder** concept-test
card, surfaced on the operator Instruments page
(`/operator/sessions/{id}/instruments`) as the **Pilot
instrument** flavour. The design intent — vertical-bands layout
collecting every per-instrument decision in one screen — is
sketched in `guide/instrument_builder.md`; this file documents
what's currently rendered on the page.

This file describes **what is on the page**. It does not describe
the route, service, or schema layers that wire up the bands to
persistence — most of those are deferred. When a behaviour below
reads as placeholder ("Inactive button", "Clicking does nothing"),
the slice that wires it lands those pieces later.

> **Status.** The pilot card top section, Band 1, and Band 3
> Visibility table are functionally laid out. Band 2 is not yet
> specified. None of the bands are wired to persistence — every
> interaction lives in inline `window.pilot*` helpers that
> manipulate the DOM only. See `guide/instrument_builder.md` for
> the parts plan.

## Page placement

The Instruments page renders one full-width per-instrument card
per instrument in `Instrument.order` (see
`spec/instruments.md`). Each card's action row carries a
**`+Pilot`** button that creates a new instrument flagged
`is_pilot=True` and slotted immediately after the source — same
pattern as Add instrument / Add group instrument. Pilot
instruments render with the vertical-bands layout described
below instead of the standard Display / Response Fields tables;
the rest of the per-instrument actions (Edit / Save / Cancel /
Delete / Replicate / Open / Close / Show when closed) work
identically across all three flavours.

The `+Pilot` button uses the `btn primary-outline` canonical
style and sits to the right of the Delete button on the action
row.

## Card layout

One full-width `.card` per pilot instrument, painted with the
same cycling lightened palette tint as ordinary instrument
cards. Inside, vertically stacked:

1. **Identity section** — two-column grid, identity + buttons on
   the left, short label + description on the right. Layout in
   "Identity section" below.
2. **Band 1 — Assignment + Unit** — three columns of equal
   width (1/3 each) carrying the per-link UI for **Pool of
   reviewers** (Link 1), **Pool of those reviewed** (Link 2),
   and **Unit of review** (Link 3). Vertical 1px rules between
   columns. Layout in "Band 1" below.
3. **Band 2** — not yet specified. Currently a horizontal rule
   followed by a placeholder `Band 2` heading.
4. **Band 3 — Visibility** — two equal-width columns. Left holds
   the Visibility audience-policy table; the right column is
   reserved for a future detail surface (currently empty).
   Layout in "Band 3" below.
5. **Action row + delete-confirm checkbox** — identical to the
   ordinary per-instrument card's bottom row. Carries the
   `+Pilot` button as the rightmost action.

The four horizontal rules use 1px `var(--border-muted, #cbd5e1)`
and 20px vertical margins.

## Identity section

A `.bottom-grid` with `align-items: stretch` and `margin-bottom: 0`
so the two columns stretch to equal heights and the gap above
the first horizontal rule is governed by the rule's own 20px
margin alone.

### Left column

Invisible `.card` wrapper (`border-color: transparent`,
`background: transparent`, `padding: 0`), explicitly stretched
via `height: 100%; box-sizing: border-box` to match the right
column's outer dimensions. Internally laid out as
`display: flex; flex-direction: column`:

- **Heading** (`<h2>` at `font-size: 1.5rem`) — `Instrument
  #{N}` followed by status pills, in order: `Pilot`
  (`pill-info`), accepting / not accepting (`pill-count` /
  `pill-empty`), showing / not showing when closed (`pill-count`
  / `pill-empty`).
- **Short-label `<input>`** (32-char limit) — visible only while
  editing.
- **Buttons row** at the bottom of the column (`margin-top:
  auto`): Edit (or Save / Cancel while editing), Open / Close
  (when `is_ready`), Show / Don't show when closed. All `btn
  secondary`. The row's bottom edge aligns with the right
  column's outer card border.

### Right column

When **not editing**, a real `.card` (visible border + 20px
padding) carrying:

- **Short label** (`<h3>`, `margin: 0 0 8px 0`) — rendered as
  the card's title, omitted when the instrument has no short
  label.
- **Description** (`<p class="description-text">`) — the
  instrument's description, falling back to `(no description)`.

When **editing**, the right column is the transparent wrapper
holding a `<textarea>` (`min-height: 8em`) for the description,
matching the existing instrument-card edit shape.

## Chip vocabulary

Bands 1 and 3 share a single chip vocabulary modelled on the
Reviewers / Reviewees / Relationships Setup-page **Show
columns** chips:

- **Toggle chip — on (or static "always on")** — `pill
  pill-count tag-chip is-selected` → solid `--accent-blue`
  background + white text (high contrast).
- **Toggle chip — off** — `pill pill-count tag-chip` (without
  `is-selected`) → light-blue background, default-coloured text.
- **Cycle chip** (e.g. the operator toggle, What / When pickers)
  — always `is-selected`; the chip's text is the current value.
- **Disabled chip** (e.g. mode pill when no usable tags) —
  `pill pill-empty tag-chip is-disabled` plus `aria-disabled="true"`
  → amber background + struck-through.
- **Static chip** (the fixed Band 3 Operator + Reviewers cells)
  — same `is-selected` look but rendered as a plain `<span>` with
  no `role="button"` (not focusable, doesn't respond to clicks).

Clickable chips are `<span class="pill … tag-chip" role="button"
tabindex="0" aria-pressed="…">` so they match the existing
Setup-page pattern byte-for-byte. The toggle helpers
(`pilotToggleAudience` / `pilotToggleRuleMode` /
`pilotToggleUnitMode`) flip `aria-pressed` alongside the
`is-selected` class.

Mode-toggle pills (the All / Filter… and Individual / Group…
pills next to each Band-1 column heading) carry `is-selected`
in **both** states — the off state isn't "unselected", it's
just "All" or "Individual" as the current choice. The chip text
flips on click; the `is-selected` class stays.

## Band 1

A CSS grid (`display: grid; grid-template-columns: 1fr 1fr 1fr;
gap: 0;`) with 1px `var(--border-muted)` left-border separators
between the second and third columns. Each column has horizontal
inner padding (`0 16px 0 0` on the first, `0 16px` on the second,
`0 0 0 16px` on the third) so content sits clear of the rules.

The three columns are functionally similar but visually
parameterised:

- **Pool of reviewers** (Link 1)
- **Pool of those reviewed** (Link 2)
- **Unit of review** (Link 3)

Each column has a heading with a mode-toggle pill, then a
two-portion builder body.

The whole Band-1 grid is gated by the instrument's edit mode —
see "Edit-mode gating" below.

### Mode-toggle pill (next to heading)

Toggles between the column's **off** state (default; builder
greyed out + inert) and **on** state (builder active). Uses the
"Cycle chip" treatment from the chip vocabulary — always
`is-selected` so the operator can read the current mode at full
contrast in either state.

| Link | Off label | On label |
|---|---|---|
| Pool of reviewers | `All` | `Filter using reviewer attributes` |
| Pool of those reviewed | `All` | `Filter using reviewee attributes` |
| Unit of review | `Individual` | `Group using reviewee attributes` |

Clicking the pill flips the label and applies `opacity: 1;
pointer-events: auto;` (or `opacity: 0.5; pointer-events: none;`)
to the builder element directly below the heading.

**Disabled state.** When the column has zero **usable tags** in
the session (see "Usable tags" below), the pill renders with the
"Disabled chip" treatment (`pill-empty tag-chip is-disabled`),
stuck in the off state. Tooltip: `No usable tags for this link`.
The builder underneath stays greyed out and inert.

### Builder body

Below the heading, a horizontal flex container
(`align-items: stretch; gap: 8px`) carrying:

- **Left portion** — narrow, holds the add-rule / combinator
  controls.
- **Thick vertical separator** — `width: 3px;
  background: var(--border-muted, #94a3b8); flex-shrink: 0`.
- **Right portion** — wider, holds a vertical stack of rule
  cells.

The default state (off pill) renders the builder at
`opacity: 0.5; pointer-events: none;`. Flipping the pill to the
on state restores `opacity: 1; pointer-events: auto;`.

#### Pool of reviewers (Link 1) and Pool of those reviewed (Link 2)

These two columns share the rule-list shape. Implemented as a
shared `pilot_rule_list` Jinja macro.

**Left portion** (fixed at `flex: 0 0 20%`). Centered both
horizontally and vertically. Two `btn secondary` buttons on the
same row, separated by 4px gap:

- `+` — adds a new rule cell to the right portion. Reset
  defaults are applied to the cloned cell.
- `AND` / `OR` — combinator toggle. Clicking flips the label
  between `AND` and `OR`.

**Right portion** (remaining width). Vertical stack of rule
cells, 12px gap between them. Each rule cell is a two-row layout
(`display: flex; flex-direction: column; gap: 4px`):

- **Row 1**: tag picker `<select>` (50% of cell width) listing
  the link's usable tags (see "Usable tags" below) followed by
  an operator-toggle button (`btn secondary`).
- **Row 2**: an operand picker followed by a trailing action
  button (`btn destructive`, content `X`).

Operator-toggle cycle (and the matching row-2 operand shape):

| Link | Operator cycle | Row-2 operand |
|---|---|---|
| Pool of reviewers | `IS` → `IS NOT` | Plain `<input type="text" placeholder="value">` filling the remaining width. |
| Pool of those reviewed | `IS` → `IS NOT` → `IS THE SAME AS` → `IS DIFFERENT FROM` | Two variants in the DOM: a 50% tag dropdown (`reviewer` + `pair_context` tags) **and** a value `<input>`. `IS` / `IS NOT` show the input; `IS THE SAME AS` / `IS DIFFERENT FROM` show the dropdown. The cycle drops the `SAME AS` / `DIFFERENT FROM` half when the operand-side tag list is empty so the operator can't land on an empty picker. |

The trailing `X` button removes its cell. The first cell's `X`
is disabled (`aria-disabled="true"`) — the first rule cell can
never be removed.

#### Unit of review (Link 3)

A separate builder shape with its own structure.

**Left portion** (fixed at `flex: 0 0 30%`). Two `btn secondary`
buttons inline, centered:

- `+` — adds a new boundary-tag cell to the right portion.
- `THE SAME` — always rendered disabled. Acts as a
  group-identity marker between the operator and the boundary
  tags they pick.

**Right portion** (remaining width). Vertical stack of cells,
8px gap. Each cell is a single row (`display: flex;
align-items: center; gap: 4px`):

- Tag picker `<select>` at `flex: 0 0 57.14%` (4/7 of the
  right portion) listing Link 3's usable tags.
- Trailing action button.

The trailing action button is **position-aware**:

- On the **last** cell — `X` (`btn destructive`), removes the
  cell. Disabled when it's the only cell.
- On every **earlier** cell — `AND` (`btn secondary`, disabled).
  Visual combinator marker between consecutive boundary tags;
  not interactive.

Adding a cell flips the previous last cell's `X` to `AND` and
gives the new cell the active `X`. Removing the last cell
restores the previous cell's `X`.

## Band 3

A CSS grid (`display: grid; grid-template-columns: 1fr 1fr;
gap: 16px; align-items: start;`) with two equal-width columns.

- **Left column** — a `Visibility` table laying out the
  audience-policy choices (who can read responses, what they
  read, when they read them).
- **Right column** — reserved for a future detail surface;
  currently empty.

The whole Band-3 grid is gated by the instrument's edit mode —
see "Edit-mode gating" below.

### Visibility table

A `<table>` with `table-layout: fixed; width: 100%` and three
column widths fixed at 30% / 35% / 35%. Headers spell out the
prompts:

- **Who can view the responses** (30%)
- **What can they see the responses** (35%)
- **When can they see the responses** (35%)

One row per audience, in order:

| Audience | Who cell | What cell | When cell |
|---|---|---|---|
| Operator | Static chip `Operator`. | Static chip `Raw responses`. | Static chip `Always`. |
| Reviewers | Static chip `Reviewers`. | Static chip `Raw responses`. | Static chip `While session ongoing`. |
| Reviewees | Toggle chip `Reviewees` (default unselected). | Cycle chip stepping `Raw responses` → `Summarized responses` → `Anonymized responses` (default `Anonymized responses`). | Cycle chip stepping `While review ongoing` → `After release` (default `After release`). |
| Observers | Toggle chip `Observers` (default unselected). | Same cycle + default as Reviewees. | Same cycle + default as Reviewees. |

When a toggleable audience (Reviewees or Observers) is in the
off state, the row's What and When cells render at `opacity: 0.4;
pointer-events: none;` so their cycle chips can't be flipped
until the audience is re-enabled. Clicking the audience chip
toggles its `is-selected` class + `aria-pressed` and flips the
greyed state on the row's What / When cells; the helper finds
row-mates by the `data-pilot-audience="<key>"` attribute on each
`<tr>`.

## Usable tags

Each Band-1 column's dropdowns are populated from the **usable**
tag slots for the session — the slots that have at least one
non-empty value in the relevant population:

| Namespace | Slot | Source rows |
|---|---|---|
| `reviewer.tag1-3` | Reviewer tag columns | All reviewers in the session. |
| `reviewee.tag1-3` | Reviewee tag columns | All reviewees in the session. |
| `pair_context.tag1-3` | Relationship tag columns | Relationships with `status == "active"`. |

The lookup is centralised in
`views._instruments._pilot_usable_tags`. A slot only becomes
"usable" when at least one row in its source population carries
a non-empty value for it. Dropdowns omit any slot that isn't
usable; if a column's combined dropdown set is empty, its
mode-toggle pill renders disabled (see "Disabled state" above).

Per-link dropdown composition:

| Column | Row-1 picker | Row-2 operand (where applicable) |
|---|---|---|
| Pool of reviewers | `reviewer.tag*` + `pair_context.tag*` | n/a (value `<input>` only). |
| Pool of those reviewed | `reviewee.tag*` + `pair_context.tag*` | `reviewer.tag*` + `pair_context.tag*` (only when the cycle includes `IS THE SAME AS` / `IS DIFFERENT FROM`). |
| Unit of review | `reviewee.tag*` + `pair_context.tag*` | n/a. |

### Friendly labels

The `<option>` text on every dropdown is the operator-set
**friendly label** for the slot, resolved through
`app.services.field_labels.resolve(session, namespace, slot)`.
The chain falls back to the canonical default (`Tag 1` etc.)
when no override exists. The `<option value="...">` attribute
carries the canonical machine key (`reviewer.tag1` etc.) so
downstream wiring can read the rule predicate without lookup.

Labels are namespace-prefixed so the operator can tell which
side of a relationship a tag belongs to when a dropdown mixes
namespaces (notably Pool of those reviewed's
`IS THE SAME AS` / `IS DIFFERENT FROM` operand picker):

| Namespace | Prefix |
|---|---|
| `reviewer` | `R-` |
| `reviewee` | `E-` |
| `pair_context` | (none — already inherently relationship-level) |

E.g. a reviewer slot renamed to `Department` renders as
`R-Department` in every Band-1 dropdown.

Friendly labels read fresh on every page render. After saving a
rename on the Reviewers / Reviewees / Relationships Setup page,
reload the Instruments page (the pilot card is server-rendered,
not live).

## Cross-cutting behaviour

### Edit-mode gating

The Band-1 three-column grid and the Band-3 two-column grid both
carry the `inert aria-hidden="true"` attributes and an
`opacity: 0.75` overlay whenever `is_editing` is false — i.e.
whenever the operator hasn't clicked the pilot card's `Edit`
button. `inert` blocks all pointer / keyboard interaction even
on inner elements that re-enable `pointer-events: auto` for
their own sub-state; the partial fade is just a soft visual cue
that the bands are read-only. In edit mode, the fade and `inert`
both lift and the bands become live.

The intrinsic sub-state fades (a Band-1 builder body in `All`
mode, a Band-3 audience row that's off) are independent and
still apply while editing.

### Inactive / greyed-out states

A Band-1 column is **inactive** when it has no usable tags. Its
mode-toggle pill is disabled and locked in the off state; the
builder body below stays at `opacity: 0.5; pointer-events: none;`.
The operator cannot engage filtering / grouping for a link
that has no data to filter / group on.

### Add / remove behaviour

- **Add (`+`)** clones the column's first rule cell, resets all
  inputs and selects to their defaults, re-runs the
  position-aware action-button refresh (for Unit of review), and
  appends the clone to the cell stack.
- **Remove (`X`)** removes the cell containing the clicked
  button, then re-runs the position-aware refresh. The first
  cell can never be removed; for Link 1 / Link 2 its `X` is
  always disabled, and for Link 3 the `X` is disabled when it's
  the only cell.

### Wiring

Nothing on Bands 1 or 3 is wired to persistence yet. The
placeholder behaviour lives in inline `window.pilot*` helpers
(`pilotAddRule` / `pilotRemoveRule` / `pilotCycleOperator` /
`pilotToggleRuleMode` / `pilotAddUnitCell` / `pilotRemoveUnitCell` /
`pilotRefreshUnitButtons` / `pilotToggleUnitMode` /
`pilotToggleAudience` / `pilotCycleButton`) defined once on the
page; clicks manipulate the DOM but no request is sent. The full
wiring plan sits in `guide/instrument_builder.md`.

## Related specs

- `guide/instrument_builder.md` — design plan + parts roadmap
  for the full builder. The "what comes next" doc this spec
  hangs from.
- `spec/instruments.md` — the per-instrument card the pilot card
  lives alongside (and will eventually replace).
- `spec/setup_pages.md` — Reviewers / Reviewees / Relationships
  Setup pages where friendly labels are authored.
- `spec/settings_inventory.md` — the 12 friendly-label slots
  Review Robin Web persists.
- `spec/rule_based_assignment.md` — the rule engine that Band 1
  will eventually persist into.
- `spec/group_scoped_instruments.md` — the underlying behaviour
  Link 3 (Unit of review) drives.
- `spec/audience_and_identity_model.md` — the audience model
  Band 3 (Visibility) will eventually operationalise.
