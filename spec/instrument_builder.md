# Instrument Builder

Surface specification for the **Instrument Builder** concept-test
card, surfaced on the operator Instruments page
(`/operator/sessions/{id}/instruments`) as the **New-model
instrument** flavour. The design intent — vertical-bands layout
collecting every per-instrument decision in one screen — is
sketched in `guide/instrument_builder.md`; this file documents
what's currently rendered on the page.

This file describes **what is on the page**. It does not describe
the route, service, or schema layers that wire up the bands to
persistence — most of those are deferred. When a behaviour below
reads as placeholder ("Inactive button", "Clicking does nothing"),
the slice that wires it lands those pieces later.

> **Status.** The new-model card top section and Band 1 are
> functionally laid out. Band 2 and Band 3 are not yet specified.
> See `guide/instrument_builder.md` for the parts plan.

## Page placement

The Instruments page renders one full-width per-instrument card
per instrument in `Instrument.order` (see
`spec/instruments.md`). Each card's action row carries a
**`+Instrument`** button (renamed from `+New model` in PR
#1443) that creates a new instrument flagged
`is_new_model=True` and slotted immediately after the source.
The pre-Wave-4 `Add instrument` / `Add group instrument`
buttons retired in the same PR, so `+Instrument` is the sole
"create new instrument" affordance on the action row. New-model
instruments render with the vertical-bands layout described
below instead of the standard Display / Response Fields tables;
the rest of the per-instrument actions (Save / Cancel /
Replicate / Delete / Lock / Unlock / Open / Close / Show when
closed) work identically across the flavours that remain.

The `+Instrument` button uses the `btn primary-outline`
canonical style and sits between `Delete` and the
`Lock` / `Unlock` toggle on the bottom action row (per the
Wave 4 PR 4c restructure documented in `spec/instruments.md`).

## Card layout

One full-width `.card` per new-model instrument, painted with the
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
4. **Band 3** — not yet specified. Currently a horizontal rule
   followed by a placeholder `Band 3` heading.
5. **Action row + delete-confirm checkbox** — identical to the
   ordinary per-instrument card's bottom row. Carries the
   `+Instrument` button between `Delete` and the `Lock` /
   `Unlock` toggle (Wave 4 PR 4c).

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
  #{N}` followed by status pills, in order: `New model`
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

### Mode-toggle pill (next to heading)

A `pill pill-info` styled as a button, sized at `font-size:
0.7em`. Toggles between the column's **off** state (default;
builder greyed out + inert) and **on** state (builder active).

| Link | Off label | On label |
|---|---|---|
| Pool of reviewers | `All` | `Filter using reviewer attributes` |
| Pool of those reviewed | `All` | `Filter using reviewee attributes` |
| Unit of review | `Individual` | `Group using reviewee attributes` |

Clicking the pill flips the label and applies `opacity: 1; pointer-events: auto;` (or `opacity: 0.5; pointer-events: none;`)
to the builder element directly below the heading.

**Disabled state.** When the column has zero **usable tags** in
the session (see "Usable tags" below), the pill renders with
`opacity: 0.5; cursor: not-allowed` and `disabled aria-disabled="true"`,
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
shared `new_model_rule_list` Jinja macro.

**Left portion** (fixed at 20% of column width). Centered both
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

**Left portion** (fixed at 40% of column width). Two `btn
secondary` buttons inline, centered:

- `+` — adds a new boundary-tag cell to the right portion.
- `THE SAME` — always rendered disabled. Acts as a
  group-identity marker between the operator and the boundary
  tags they pick.

**Right portion** (remaining width). Vertical stack of cells,
8px gap. Each cell is a single row (`display: flex;
align-items: center; gap: 4px`):

- Tag picker `<select>` (2/3 of cell width) listing Link 3's
  usable tags.
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

## Usable tags

Each column's dropdowns are populated from the **usable** tag
slots for the session — the slots that have at least one
non-empty value in the relevant population:

| Namespace | Slot | Source rows |
|---|---|---|
| `reviewer.tag1-3` | Reviewer tag columns | All reviewers in the session. |
| `reviewee.tag1-3` | Reviewee tag columns | All reviewees in the session. |
| `pair_context.tag1-3` | Relationship tag columns | Relationships with `status == "active"`. |

The lookup is centralised in
`views._instruments._new_model_usable_tags`. A slot only becomes
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

This means renaming a tag on the Reviewers / Reviewees /
Relationships Setup pages immediately surfaces in the new-model
card's dropdowns.

## Cross-cutting behaviour

### Inactive / greyed-out states

A column is **inactive** when it has no usable tags. Its
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

Nothing on Band 1 is wired to persistence yet. The placeholder
add / remove / toggle behaviour lives in three inline
`window.newModel*` helpers (`newModelAddRule` / `newModelRemoveRule` /
`newModelCycleOperator` / `newModelToggleRuleMode` / `newModelAddUnitCell`
/ `newModelRemoveUnitCell` / `newModelRefreshUnitButtons` /
`newModelToggleUnitMode`) defined once on the page; clicks
manipulate the DOM but no request is sent. The full wiring plan
sits in `guide/instrument_builder.md`.

## Related specs

- `guide/instrument_builder.md` — design plan + parts roadmap
  for the full builder. The "what comes next" doc this spec
  hangs from.
- `spec/instruments.md` — the per-instrument card the new-model card
  lives alongside (and will eventually replace).
- `spec/setup_pages.md` — Reviewers / Reviewees / Relationships
  Setup pages where friendly labels are authored.
- `spec/settings_inventory.md` — the 12 friendly-label slots
  Review Robin Web persists.
- `spec/rule_based_assignment.md` — the rule engine that Band 1
  will eventually persist into.
- `spec/group_scoped_instruments.md` — the underlying behaviour
  Link 3 (Unit of review) drives.
