# Instrument builder

> **Stub created 2026-05-22.** Sketch-level scope only. Detailed
> PR breakdowns get drafted when this work is picked up.

A second take on the per-instrument editor's UI shape, sibling
to [`guide/instrument_chain_builder.md`](instrument_chain_builder.md).
The underlying conceptual model is identical — the same six
links the chain builder describes (Reviewers / Reviewee pool /
Unit of review / Visibility / Read shape / Release timing).
The data model, audit footprint, validation surface, and
sequencing carry over without change.

What differs is **how the operator interacts with the editor**.
The chain builder spends the operator's *horizontal* attention
on three (or six) side-by-side sub-cards. The instrument
builder spends the operator's *vertical* attention on a
top-middle-bottom stack:

- **Top row** — Links 1, 2, 3 across (the per-instrument *who*
  decisions: who reviews, who they review, in what unit).
- **Middle** — the instrument itself. Display fields +
  response fields, rendered **as a live preview of one
  reviewer-surface row**, not as a selector table.
- **Bottom row** — Links 4, 5, 6 across (the *who-sees-what-
  when* decisions).

The middle row is the key idea. Today (and in the chain
builder doc) the operator chooses display fields and response
fields by ticking checkboxes in selector tables — a table per
list, one row per slot, with the *effect* of the choices
invisible until the operator clicks Preview. The instrument
builder inverts that: the editor *is* a sample reviewer row,
the operator manipulates it directly, and the table-of-checkboxes
shape disappears.

---

## Why vertical

The horizontal six-card chain has one weakness: the chain reads
left-to-right, but the *thing the operator is configuring* — the
instrument's review-form shape — has nowhere of its own to
live. The chain builder folds it into the per-instrument card's
existing Display Fields and Response Fields tables, sitting
below the chain row. So the operator scans:

1. Chain row (horizontal, top).
2. Display Fields selector table.
3. Response Fields selector table.
4. (No preview unless the operator opens Previews.)

This is fine when the operator already knows the shape they
want. It is poor when they don't — when authoring an instrument
they need to *see and adjust* simultaneously, the chain builder
makes them assemble the picture in their head from two
tabular editors.

The instrument builder addresses this by:

1. Putting the **review-row preview itself** in the centre of
   the editor, full width, as the unit of authoring.
2. Bracketing it with the chain links above and below — Links 1
   to 3 *prepare* the row (who, who, in what unit); Links 4 to
   6 *gate* the row (who sees the row, in what shape, when).
3. Letting the operator add, remove, reorder, rename, and
   retype every cell of the preview row in place. The selector
   tables collapse into inline cell affordances.

This is a closer fit to how operators think — "I'm building a
review form, here's what one row of it will look like" — at
the cost of a taller layout that the operator scrolls through
top to bottom.

---

## Layout

One **full-width card** per instrument, replacing the existing
per-instrument card on the Instruments page. Inside, three
stacked sections, each its own visual band within the same
parent card frame:

```
┌─ Instrument #2 — "Peer skill assessment"  [accepting]  [showing] ────────┐
│                                                                          │
│  ┌── 1. Who reviews ────┐ ┌── 2. Who they review ─┐ ┌── 3. Unit ──────┐ │
│  │  reviewer.tag2 = Lead │ │ reviewee.tag1 same_as │ │ Individual       │ │
│  │                       │ │ reviewer.tag1         │ │                  │ │
│  │              [Edit ▸] │ │              [Edit ▸] │ │      [Edit ▸]    │ │
│  └───────────────────────┘ └───────────────────────┘ └──────────────────┘ │
│                                                                          │
│  ─────────────────── one reviewer-surface row ──────────────────────     │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────────┐│
│  │ Reviewee     │ Team    │ Photo │ Skill rating │ Strengths            ││
│  │ Jane Doe     │ Alpha   │  🧑    │     [4 ▾]    │ [textarea text…]     ││
│  │              │         │       │              │                      ││
│  │ ⊕ Add column                                  │                      ││
│  └──────────────────────────────────────────────────────────────────────┘│
│                                                                          │
│  ─────────────────── per-audience access ───────────────────────────     │
│                                                                          │
│  ┌── 4. Visibility ─────┐ ┌── 5. Read shape ─────┐ ┌── 6. Release ─────┐│
│  │ Operators            │ │ Operators: raw       │ │ Operators: always ││
│  │ Reviewees            │ │ Reviewees: anonymise │ │ Reviewees: on rel ││
│  │ (Observers: none)    │ │                      │ │   — not yet       ││
│  │              [Edit ▸]│ │              [Edit ▸]│ │             [Edit ▸]││
│  └──────────────────────┘ └──────────────────────┘ └───────────────────┘│
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

The three bands separate visually with thin horizontal rules,
not with card borders — the bands are sections of one card, not
sub-cards. The instrument identity (number, name, status pills)
sits in the card header above the top band.

### Band 1 — Links 1, 2, 3 (top)

Three equal-width inline summary blocks. Each shows:

- The link's name (`1. Who reviews`, `2. Who they review`,
  `3. Unit`).
- A one-line summary of the current configuration (the rules
  that filter reviewers, the rules that pair them with
  reviewees, the unit choice + boundary tags).
- An **Edit** button bottom-right.

Clicking Edit opens the link's full editor either inline below
the band or in a child page (same options as the chain
builder; see [`guide/instrument_chain_builder.md`](instrument_chain_builder.md)
§UI shape).

Links 1 and 2 may be presented as one combined "Assignment
rule" summary if the implementation adopts the chain builder
doc's recommended sub-card collapse (Link 1 + Link 2 share one
RuleSet). In that case the top band has two summary blocks
instead of three.

### Band 2 — Live preview row (middle)

The instrument's review form, rendered as a **single sample
row** in the same DOM shape the reviewer surface uses. The
sample reviewee is the first active reviewee that satisfies the
Link 1 + Link 2 rule — picked by the editor each time the row
re-renders so the operator always sees realistic content.

Columns left to right:

- **Reviewee identity** — always present, not editable as a
  column (it is the row's anchor). Renders the sample
  reviewee's name + email_or_identifier per the existing
  reviewer-surface contract.
- **Display field columns** — one per display field the
  operator has added. Renders the sample reviewee's value for
  that source (tag value, pair-context tag value, photo, etc.).
  Per-column header shows the friendly label; clicking the
  header opens an inline editor for label / source choice /
  visibility / sort priority / delete.
- **Response field columns** — one per response field the
  operator has added. Renders the field's actual input control
  (`<input>`, `<textarea>`, `<select>`) bound to the field's
  RTD. The cell shows a *placeholder* value, not a real
  response (the editor reads "what would a reviewer see when
  this cell is empty"). Per-column header shows the friendly
  label, RTD type pill, required pill; clicking the header
  opens an inline editor for label / key / RTD / required /
  help text / delete.
- **`⊕ Add column`** — last cell. Opens a small chooser that
  asks "Display column or Response column?". Picking display
  surfaces the seven D6 sources (filtered to those not already
  added); picking response surfaces the session's RTD catalog
  + a "New RTD" affordance.

The preview row is **interactive** — the operator can:

- **Reorder columns** by dragging headers (or with ▲/▼ arrows
  on each header for keyboard / accessibility).
- **Rename** a column inline by clicking its header label.
- **Retype** a response column by changing its RTD picker.
- **Toggle visibility** (display columns only) — a column
  marked invisible greys out, retaining its slot in the row
  for layout context but indicating it will not render to
  reviewers.
- **Delete** a column with confirmation; response columns with
  saved responses trigger the existing cascade-confirm flow.

The preview row is **never** a real response. The operator's
inputs into response cells are ignored — they exist only to
demonstrate the input control's shape. A small caption
underneath the row reads: *"Live preview — reviewers see one
row like this per reviewee in their assignment universe.
Sample reviewee: Jane Doe."*

A toggle on the band header switches the sample reviewee, so
the operator can sanity-check the row against several roster
members.

### Band 3 — Links 4, 5, 6 (bottom)

Three equal-width inline summary blocks, mirror image of the
top band. Each shows:

- The link's name.
- A one-line summary of the current per-audience
  configuration.
- An **Edit** button bottom-right.

If the implementation adopts the chain builder doc's
recommended three-sub-card collapse, the bottom band can
present as **one** "Per-audience access" summary listing the
enabled audiences with their `(read shape, release timing)`
inline — same data, denser presentation.

---

## What changes vs the chain builder doc

The instrument builder and the chain builder are
**alternative UI surfaces on the same data model**. Everything
in the chain builder doc downstream of UI shape — the data
deltas, sequencing, validation surface, audit footprint,
cross-cutting concerns, open questions — applies identically
here. The only behavioural delta is the band 2 live-preview
row vs the chain builder's separate Display Fields /
Response Fields selector tables below the chain row.

| Concern | Chain builder | Instrument builder |
|---|---|---|
| Horizontal vs vertical | Chain reads left to right; preview is opt-in | Three vertical bands; preview is the centrepiece |
| Editing the form shape | Display Fields + Response Fields selector tables | Inline column-header editing on the preview row |
| Sample data | Hidden until operator opens Previews | Visible the moment the editor opens |
| Vertical space | ~6 rows per instrument card | ~10-12 rows per instrument card |
| Discoverability of columns | Operator scans two tables | Operator scans one row, left to right |
| Cell-level affordance density | Tables can fit many rows of metadata per column | Each column header is the only affordance — limits per-column controls |

Pick the chain builder when the operator's primary mental
model is *policy decisions over a session*. Pick the instrument
builder when the operator's primary mental model is *I am
designing a review form*. The two surfaces can coexist (one as
the default, the other as an "expert view" toggle, or one per
session-template) — but the working assumption is that one
ships at a time, picked after pilot feedback.

---

## Sequencing

Identical to the chain builder's sequencing
(`guide/instrument_chain_builder.md` §Sequencing) for Parts 0,
2-9. Part 1 (UI shell) is the only delta:

| Part | Scope | Depends on |
|---|---|---|
| **0 — Schema pre-positioning** | Same as chain builder Part 0. | nothing |
| **1 — UI shell (vertical bands)** | Replace the per-instrument card with a three-band layout. Band 1 shows summary blocks for Links 1-3 (Edit buttons inert). Band 2 renders the existing Display Fields + Response Fields tables in a transitional state — not yet collapsed into the preview row, but visually centered between the bands. Band 3 shows summary blocks for Links 4-6 (Edit buttons inert). | Part 0 |
| **1b — Live-preview row** | Replace Band 2's tables with the live-preview row described above. Inline column-header editing for both display and response columns. Sample-reviewee selector. | Part 1 |
| **2-9** | Same as chain builder Parts 2-9 — each link's editor lights up under the same per-link Edit button. | per chain builder |

Splitting Part 1 / 1b decouples the vertical-bands layout
shift from the live-preview row's authoring affordance. Part 1
gets the operator into the new top-middle-bottom shape with no
authoring-mechanic change; Part 1b is the deeper rewrite of
how the operator manipulates display + response fields.

---

## Open questions

1. **Sample reviewee picking.** Band 2's live preview needs a
   sample reviewee. Three policies are plausible:
   (a) the first active reviewee that satisfies the Link 1 +
   Link 2 rule (deterministic, may be a regular reviewee the
   operator does not want spotlighted);
   (b) operator-selectable from a small dropdown of eligible
   reviewees (best discoverability, more clicks);
   (c) a synthetic "John Sample" reviewee with placeholder
   values for every D6 source (no real-name exposure, but
   makes the preview feel less authentic).
   Default proposal: (b), with (a) as fallback when the
   operator hasn't picked. Decision deferred to Part 1b.

2. **Multiple sample rows.** Band 2 renders one row by default.
   Should the editor optionally show *N* sample rows (the
   first N reviewees in the assignment universe)? Helps the
   operator sanity-check display-field values across reviewees
   with different tag combinations, at the cost of vertical
   space. Default proposal: one row + a sample-reviewee
   selector (see Q1); multi-row mode behind a toggle.

3. **Group-scoped preview.** When the instrument is Grouped
   (Link 3), the live preview should render *one group row*
   instead of one reviewee row — composed group identity
   column on the left, fan-out implications visible. The
   sample group is the first group the boundary tags
   partition the universe into. Deferred to Part 1b.

4. **Sort defaults in the preview.** Today's per-instrument
   sort defaults are configured on the Display Fields table
   via the tri-state sort-priority widget
   (`spec/sort_by_reviewee.md`). In the live-preview model
   that surface goes away — sort priority becomes an inline
   header-context-menu choice. Decision deferred.

5. **Discoverability of unused columns.** A selector table
   shows every available D6 source as a checkbox row, even
   the unchecked ones. The preview row shows only the
   *included* columns — the operator must click `⊕ Add
   column` to discover what else is available. Trade-off:
   denser canvas vs. potentially missed affordances.
   Mitigation: the `⊕ Add column` chooser lists every D6
   source with a checkmark next to the ones already present,
   so adding multiple in one pass is fast.

6. **Coexistence with the chain builder.** If both UI shapes
   ship, where does the operator switch between them? A
   session-level setting? A per-instrument toggle? Or a
   workspace-default with a per-operator override? The MVP
   answer is "pick one and ship it"; coexistence is a
   later decision.

---

## Related specs

- [`guide/instrument_chain_builder.md`](instrument_chain_builder.md) — the sibling UI shape (horizontal chain). The data model + links + audit footprint + sequencing (sans Part 1) carry over identically.
- [`spec/instruments.md`](../spec/instruments.md) — the per-instrument card the instrument builder lives inside.
- [`spec/reviewer-surface.md`](../spec/reviewer-surface.md) — the row shape Band 2 is mirroring; the preview row must match it cell-for-cell so the operator's mental model of "what the reviewer sees" is correct.
- [`spec/rule_based_assignment.md`](../spec/rule_based_assignment.md) — Links 1 + 2's underlying engine.
- [`spec/group_scoped_instruments.md`](../spec/group_scoped_instruments.md) — Link 3's underlying behaviour and what Band 2's group-mode preview must collapse into.
- [`spec/sort_by_reviewee.md`](../spec/sort_by_reviewee.md) — sort-priority semantics that need a new home in the inline column-header affordance.
