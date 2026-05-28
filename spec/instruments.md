# Instruments

**The Instrument entity and the operator surface that configures it.**

An **Instrument** is a per-session evaluation surface: one
reviewer-facing form that reviewers fill out, materialised as
zero or more `Assignment` rows (one per reviewer–reviewee pair
the operator chose to include). Every session has at least one
instrument; the default instrument is created when the session
is created and ships ready-to-use with one Rating + one
Comments response field. Operators add more instruments when a
session needs multiple parallel evaluation forms (e.g. peer
review + self review + manager review of the same reviewees).

This spec covers the per-session Instruments page at
`/operator/sessions/{session_id}/instruments`, including the
per-instrument card (Bands 1+2+3), the Response Type
Definitions catalogue, the lifecycle gates the page honours,
and the editing / save / lock model.

For the assignment side — how (reviewer, reviewee, instrument)
triples actually get materialised from the Band 1 rule — see
`spec/assignments.md`.

> **Status.** Implemented through Wave 5 (the post-collapse
> world). Every instrument is a (former) new-model card; the
> legacy individual + group flavours retired in Wave 5 PR 5.3
> (PR #1448). The RuleSet library tier retired in Wave 5 PR 5.2
> (PR #1447). Historical doc set: `spec/archive/instruments.md`,
> `spec/archive/instrument_builder.md`,
> `spec/archive/group_scoped_instruments.md`.

## Contents

- [Concept](#concept)
- [Page layout](#page-layout)
- [Status + bulk-actions card](#status--bulk-actions-card)
- [Per-instrument card](#per-instrument-card)
  - [Identity](#identity)
  - [Band 1 — Assignment rule + Unit of review](#band-1--assignment-rule--unit-of-review)
  - [Band 2 — Display fields + preview row](#band-2--display-fields--preview-row)
  - [Band 3 — Response fields](#band-3--response-fields)
  - [Action row](#action-row)
- [Add / Replicate / Delete](#add--replicate--delete)
- [Editing flow](#editing-flow)
- [Validation surfaces](#validation-surfaces)
- [Open / deferred](#open--deferred)

## Concept

An Instrument has three intertwined facets:

1. **The reviewer's experience.** A page the reviewer lands on
   that lists the reviewees they're assigned and renders an
   answer surface (Band 3 response fields) per row.
2. **The operator's authoring surface.** This page. The
   operator picks who reviews whom (Band 1), what reviewee
   context is shown to the reviewer (Band 2), and what answers
   to collect (Band 3).
3. **The assignment unit.** Each row materialised at generate
   time is one `Assignment` row tying a reviewer to either a
   single reviewee (Individual unit-of-review) or a group of
   reviewees that share a boundary tag (Group unit-of-review).

The on-page model maps onto these:

- **Identity.** `name` / `short_label` / `description` /
  visibility flags.
- **Band 1.** Three "Links" — Link 1: Pool of reviewers,
  Link 2: Pool of those reviewed, Link 3: Unit of review (Individual
  vs Group). Together these define **the assignment rule** for
  this instrument (`SessionRuleSet` row materialised lazily on
  first non-empty filter).
- **Band 2.** Display fields the reviewer sees alongside each
  row (Name + Email are always rendered; the operator picks
  additional reviewee / pair-context tag fields by clicking
  chips). A preview row renders inline so the operator sees
  what the reviewer will see.
- **Band 3.** Response fields — typed input controls the
  reviewer fills in. Each row carries its own inline
  `data_type` + `min` / `max` / `step` / `list_options` (the
  per-session RTD catalogue retired 2026-05-26).

The Wave 5 collapse fused the legacy "individual" and "group"
card flavours into one uniform card; Group vs Individual is now
just Link 3's binary state on every instrument.

## Page layout

Top → bottom, full width:

1. **Page title** — "Instruments — {session name}" + the standard
   operator session chrome (Workflow card, breadcrumbs).
2. **Status + bulk-actions card** — one-line summary of the
   session's instruments + a small set of bulk affordances.
3. **Per-instrument cards** — one card per instrument, ordered
   by `instruments.order` (the operator's preferred display
   order; insertion order by default, mutable via Replicate +
   `+Instrument` which spawn immediately after a chosen anchor).

The bottom-of-page **Response Type Definitions card** retired
2026-05-26 together with the `response_type_definitions` table
— each Band 3 row now carries its own inline `data_type` +
bounds + list options, with a small set of pre-filled List
presets (Boolean / Agreement / Grades) baked into the Band 3
type picker.

Each card is wrapped in `<div class="card">`; the per-instrument
card has `id="instrument-{id}"` so deep-links from other surfaces
(Validate page Fix-on-X links, deep-link anchors) land on the
right card.

## Status + bulk-actions card

One-line status row, left-aligned:

> *N instruments — M accepting responses · K showing when closed.*

Right-aligned bulk-action toggle stack (Segment 18M PR 0
added the Expand/Collapse pair above the existing
visibility row):

- **Expand all instruments / Collapse all instruments**:
  flip every per-instrument `<details>` open or closed.
  No state persistence across refresh — operators get a
  fresh all-collapsed default on each page load.
- **Open / close all** (when `session.is_ready`): bulk-flip
  `accepting_responses` on every instrument. Lifecycle-aware —
  greyed out before activation.
- **Show / hide all when closed**: bulk-flip
  `responses_visible_when_closed`. Available in any lifecycle
  state. The per-card mirror retired in Segment 18M
  follow-up; this is the sole surface for the
  visibility-when-closed toggle.

Historic context: the Status + bulk-actions card was once a
two-card row (one card per facet); the bulk toggle was small
enough to absorb into Status without losing affordance, so the
right-hand "Visibility-when-closed" card retired (Segment 13C
harmonisation).

## Instrument data model

Beyond the standard rows (id / session_id / name /
short_label / description / order /
accepting_responses / responses_visible_when_closed)
Segment 18M added a single boolean for the
operator-controlled page-break layout:

- **`starts_new_page: Boolean NOT NULL`** (Alembic
  revision `e5c1a3b9d472`). `true` means "this instrument
  starts a new page on the reviewer surface" — i.e. a
  page break sits between this instrument and the one
  before it. **Meaningful only for instruments at position
  ≥ 2;** the value on the position-1 instrument is
  ignored at render time.

  The migration backfilled `true` on every existing
  instrument so today's one-per-page reviewer behaviour
  was preserved on rollout (locked decision 3 in
  `guide/segment_18M_instrument_layout.md`); the DB-level
  `server_default` was then flipped to `false` so new
  instruments default to "continue current page". The
  Mapped column declares `default=False` so ORM creates
  match.

  Mutated only by the three service helpers in
  `app.services.instruments`:
  - `reorder_instruments(db, *, review_session,
    items: list[int | None], actor)` — items is a mixed
    visual list (`None` = page break). Validates the
    three reorder invariants (no leading / no trailing
    / no double-stack) + id membership, re-derives flags
    from list position, persists order + flags + emits
    one combined `instruments.reordered` audit event.
  - `create_page_break_after(db, *, instrument, actor)`
    — flips the flag on the successor; rejects trailing
    / double-stack. Emits `instrument.page_break_set`.
  - `clear_page_break(db, *, instrument, actor)` —
    flips the flag back to false on an instrument that
    currently carries it. Emits
    `instrument.page_break_cleared`.

  All three call `session_lifecycle.invalidate_if_validated`
  at entry. Routes that call them apply
  `_require_instrument_editable` so the operations 409
  once the session is `is_ready`.

## Per-instrument card

Order of stripes (each separated by a horizontal rule):

```
┌────────────────────────────────────────────────────────────────┐
│ Identity (heading + pills + per-instrument open/close /        │
│           visibility forms)                                     │
├────────────────────────────────────────────────────────────────┤
│ Band 1 — Pool of reviewers │ Pool of those reviewed │ Unit of  │
│                            │                        │ review   │
│  (three columns, vertical rules between)                       │
├────────────────────────────────────────────────────────────────┤
│ Band 2 — display-field chips + preview row                     │
├────────────────────────────────────────────────────────────────┤
│ Band 3 — response-field table                                  │
├────────────────────────────────────────────────────────────────┤
│ Action row (Save / Cancel / Replicate / Delete / +Instrument / │
│             Lock-Unlock) + delete-confirm checkbox             │
└────────────────────────────────────────────────────────────────┘
```

The whole card body is wrapped in a `<form id="dfsave-{id}">`
that the Save button submits; every editable input on Bands 1+3
binds to that form via `form="dfsave-{id}"`. Band 2's display
chips and short_label / description use their own inline ✎/✓
forms (separate POSTs to `/identity` etc.) — the bulk Save
doesn't carry them.

### Identity

The whole per-instrument card is wrapped in a native
`<details class="instrument-card-collapsible">` (Segment
18M PR 0). The `<summary>` is the only thing rendered when
collapsed; expanding reveals the Band 1 / Band 2 / Band 3
stripes below it. Default state on first render of the
page is **all collapsed**; cards auto-open when
`is_editing` or `was_saved` is true so an active edit or a
fresh save never lands hidden. After a drag-and-drop
reorder the sessionStorage-based restore overrides the
auto-open so each card preserves its pre-drag collapse
state exactly.

The `<summary>` carries, in document order:

- **Drag handle.** A small grip-dot icon
  (`<span class="instrument-card-drag-handle"
  draggable="true">⋮⋮</span>`) on the left edge. `cursor:
  grab` on hover, `grabbing` while held. Click on the
  handle is `preventDefault`-ed in capture phase so it
  doesn't co-fire the parent `<summary>`'s native toggle.
- **Title (operator-facing short label).** Renders
  `{instrument.short_label}` when the operator has set
  one, else the ugly fallback `"Instrument_{instrument.id}"`
  in muted italic so it reads as a placeholder rather than
  a chosen name. Per the 2026-05-28 operator-identifier
  policy: the `#` prefix is reserved for the reviewer-
  facing `#{N}: {short_label}` heading inside Band 2's
  "Preview reviewer instrument" card; operator-facing UI
  uses `short_label` with the `Instrument_{id}` fallback.
  The fallback is generated by
  `app/services/instruments/_state.py::_instrument_label`
  (also drives audit-event copy + validation messages).
- **Inline edit affordance.** A ✎ icon to the right of
  the title; clicking it (with `event.preventDefault()` +
  `stopPropagation()` so the card doesn't toggle open)
  swaps the title for a 32-char `<input>` pre-populated
  with the current `short_label` (empty when not set —
  the `Instrument_{id}` placeholder lives only on the
  view span). The ✓ button POSTs to the existing
  `/operator/sessions/{sid}/instruments/{iid}/identity`
  endpoint with `{short_label: ...}` and swaps the title
  back in place — no full page reload, so the card's
  expand/collapse state and scroll position survive the
  save. Empty save clears the label and reverts the view
  to the muted `Instrument_{id}` fallback.
- **Status pills:**
  - **Set up / Not set up** — mirrors the workflow
    card's `instruments_service.is_configured(db,
    instrument)` predicate. `pill-info` for set up;
    `pill-warning` for not set up. Computed in
    `views.build_instruments_context` as
    `is_configured_by_instrument[instrument.id]`.
  - **Locked / Unlocked** — mirrors `is_editing`. The
    "Unlock" button enters edit mode (pill says
    "Unlocked", `pill-warning`); "Lock" exits (pill
    says "Locked", `pill-info`). Makes a card's edit
    mode visible at a glance without expanding it.
- **Toggle chevron.** A large `▾` icon on the right edge
  that rotates 180° via the `details[open] summary
  .instrument-card-toggle-icon` CSS selector — no JS for
  the per-card toggle.

The previous two-pill row (`accepting responses` /
`not accepting responses` + `showing when closed` /
`not showing when closed`) retired in the Segment 18M
follow-up: both states are already discoverable at the
session level via the Status + bulk-actions card, so the
per-card mirror is redundant.

Beneath the `<summary>` (only visible when the card is
expanded):

- **Per-instrument flip forms** (only render in lifecycle
  states where they're meaningful — `is_ready` for the
  open/close form):
  - **Open this Instrument** / **Close this instrument**
    (`POST /sessions/{sid}/instruments/{iid}/open|close`).

The per-card **Show when closed** /
**Don't show when closed** flip form retired in the
Segment 18M follow-up — visibility-when-closed is now an
exclusively session-level toggle via the bulk
"Show / hide all when closed" button in the Status +
bulk-actions card. The route
`POST /sessions/{sid}/instruments/{iid}/visibility` lives
on for fixture / programmatic use.

`short_label` and `description` are **not** rendered in
the Identity heading — they moved into Band 2's intro
card (the inline ✎/✓ pair, separate POST to `/identity`)
so the heading row stays compact. The intro card's
title prefix reads `#{N}:` where N is the on-page
position (Segment 18M follow-up dropped the leading
"Page " word; the reviewer surface keeps `Page #N:` so
the operator's preview matches what the reviewer sees).

#### Card background colour

Each instrument card's background pulls from a 6-colour
pastel palette keyed by `(instrument.id - 1) % 6`. The
palette is in `instruments_index.html` (`instrument_palette`
list). The colour rides with the instrument across
reorders / replicates / deletes — pre-Segment 18M the
palette was keyed off `loop.index0` and the colours
shuffled on every reorder, which proved confusing once
drag-to-reorder landed.

#### Page break card

A page break renders as a thin horizontal divider with the
words `Page break` centred and a small `×` delete button
on the right (`class="page-break-card"` in
`instruments_index.html`). The `×` POSTs to
`/instruments/{iid}/page-break/delete` via `fetch` (not a
form submit) so the delete removes the divider in place
without reloading the page — preserving every other
card's collapse state. The previous instrument's
`+ Page break` button is re-enabled in place when the
break is cleared.

A break sits between adjacent instrument cards in
document order; the loop renders the divider just before
the per-instrument card whose `starts_new_page=true`.
Locked decisions (see `guide/segment_18M_instrument_layout.md`):

- Page breaks are **non-movable** — create + delete only.
  Dragging an instrument across a break naturally
  relocates which two instruments the break sits between
  (the break is a list item in the operator's mental
  model, and flags are re-derived from the new list
  order server-side).
- Three reorder invariants:
  - **(a)** No leading page break (no `null` at the start
    of the items list).
  - **(b)** No trailing page break (no `null` at the end).
  - **(c)** No double-stacked breaks (no two consecutive
    `null` entries).
  Any reorder that would violate any of (a)-(c) is
  rejected with a 409 + inline toast.

#### Per-instrument action-row buttons

The bottom action row hosts (in order):
Save (edit only) | Cancel (edit only) | Replicate |
Delete | **+Instrument** | **+Page break** | Lock /
Unlock. The new buttons:

- **+Instrument** — creates a new instrument
  immediately after this one (existing button; sole
  add-affordance since Wave 5 retired the legacy add
  buttons).
- **+Page break** — sets `starts_new_page=true` on the
  successor. Disabled (with explanatory tooltip) when:
  - This is the last instrument (would create a
    trailing break — invariant (b)).
  - The successor already carries the flag (would
    double-stack — invariant (c)).
  - The session is past the editable lifecycle.

`POST /sessions/{sid}/instruments/{iid}/page-break/create`
maps the service's `ValueError`s to 409; the
`+Instrument` form to `/instruments/add-new-model`
includes the current instrument's id as `after` so the
new instrument lands immediately below.

### Band 1 — Assignment rule + Unit of review

Band 1 owns the **assignment rule** for this instrument. Three
columns of equal width with a 1px vertical rule between them.
Each column ("Link") is a self-contained sub-builder.

| Column | Link | Vocabulary |
|---|---|---|
| Left | Link 1 — Pool of reviewers | `reviewer.tag1 / 2 / 3` + `pair_context.tag1 / 2 / 3` |
| Centre | Link 2 — Pool of those reviewed | `reviewee.tag1 / 2 / 3` + `pair_context.tag1 / 2 / 3` (with cross-side operands) |
| Right | Link 3 — Unit of review | Individual vs Group; if Group, picks reviewee + pair-context boundary tags |

#### Pill-driven state machine

Each Link has a mode-toggle pill in its heading row that cycles
through three states. The pill carries `data-new-model-rule-mode`
for Links 1 + 2 (`not_set | all | filter`) and
`data-new-model-unit-mode` for Link 3
(`not_set | individual | group`).

| Pill state | Label | Builder body | `aria-pressed` |
|---|---|---|---|
| `not_set` | "Not set" | dimmed, `pointer-events: none` | `mixed` |
| `all` / `individual` | "All" / "Individual" | dimmed | `false` |
| `filter` / `group` | "Filter using tags" (Link 1 + Link 2) / "Group using tags" (Link 3) | active | `true` |

**Cycle.** Each click advances one step and wraps:
`not_set → all → filter → not_set → all → filter → …` (and the
equivalent for Link 3). The cycle wrap was added 2026-05-26
(PR #1450) so the operator can return a Link to `Not set` and
surface the instrument as unconfigured on the workflow card
again.

**Disabled state.** When the session has no usable tags for a
Link's namespace, the pill is permanently stuck on `Not set`
with `aria-disabled="true"` and the title "No usable tags for
this link". Saving the instrument in that state is fine — the
service treats an empty filter as "no constraint on this Link"
and the workflow card still surfaces it as unconfigured until
the operator clicks the pill (which on a disabled pill is a
no-op, so these sessions need at least one tag column on the
relevant roster before Band 1 can be touched).

#### "Not set" pill safety gate

`Instrument.band1_touched_links` is a JSON column storing the
subset of `{"link1", "link2", "link3"}` the operator has clicked
into a non-`Not set` state. The bulk-save form carries one
`{link}_touched` hidden input per Link; the pill click handler
flips it to `"true"` (and back to `"false"` on cycle-back).

The workflow card's "Empty Setup" state keys off
`is_configured(db, instrument)`, which requires:

- at least one `visible=True` `InstrumentResponseField`, AND
- all three Link ids present in `band1_touched_links`.

This is the **safety gate** added 2026-05-26 (PR #1449) so the
implicit Full Matrix default (synthesised when `rule_set_id`
is NULL — see `spec/assignments.md`) can't ship silently. The
operator has to make a deliberate choice on each Link before
the instrument reads as configured.

Writers respect ownership when updating the touched set:

- `set_band1_assignment_rules` (Links 1 + 2) replaces the
  `{link1, link2}` slice with the form's view; `link3` is
  preserved.
- `set_unit_of_review` (Link 3) replaces only `link3`.

#### Link 1 / Link 2 — filter rule list

When the pill is in `filter`, the column renders a vertically
stacked list of MATCH-rule cells. Each cell has:

- A field dropdown — the column's tag namespace (e.g.
  Link 1: `reviewer.tag1 / tag2 / tag3 + pair_context.tag1 / tag2 / tag3`).
  Only namespaces with at least one populated row in the
  session appear — the dropdown's options come from
  `views._instruments._new_model_usable_tags`.
- An operator-cycle button. Link 1 cycles through `IS | IS NOT`;
  Link 2 cycles through `IS | IS NOT | IS THE SAME AS | IS DIFFERENT FROM`
  (the cross-side operators take a reviewer-side tag as operand
  for "same as the reviewer's role" semantics).
- An operand input. Either a free-text value (for `IS` / `IS NOT`)
  or a tag dropdown (for the cross-side operators). The JS
  toggles which is visible based on the current operator.
- An X (remove) button. Disabled on the first cell.

Above the cells, a `+` button adds another cell and a combinator
toggle (`AND` / `OR`) sets how the cells combine within the Link.
Each Link contributes its own Composite to the materialised
`SessionRuleSet`; the outer `ALL_OF` combinator wraps both Links
so they intersect (Link 1 ∩ Link 2).

#### Link 3 — Unit of review

When the pill is in `group`, the column renders the same
vertical builder shape — `+` button + boundary-tag cells. Each
cell is a single dropdown picking one of the session's usable
reviewee or pair-context tags. The cells additively define the
**group boundary**: reviewees sharing the same values across
every picked tag form one group.

The "AND" / "THE SAME" disabled buttons inside the builder are
visual markers: they communicate that boundary tags compose
additively (every tag matters) and that group membership is
"the reviewees agreeing on all of these".

The boundary cells encode into `Instrument.group_kind` (a
`String(32)`) via `encode_group_kind / decode_group_kind` in
`app.services.instruments._instrument_crud`:

- `NULL` — Individual instrument. `group_kind=NULL`.
- `"both"` — Group instrument with no boundary tag (sentinel
  that keeps the column non-null without committing to a tag;
  every active reviewee forms one global group).
- Comma-separated codes — e.g. `"r1"` (reviewee.tag_1),
  `"r1,p2"` (reviewee.tag_1 AND pair_context.tag_2), `"p1,p2,p3"`.
  Code mapping: `r1/r2/r3 → reviewee.tag_1/2/3`,
  `p1/p2/p3 → pair_context.tag_1/2/3`.

Six codes + commas = 17 characters, well under the 32-char limit.
Order of codes is the operator's preferred display order, not
significant for grouping semantics.

#### Materialisation

Band 1 saves through `app/services/instruments/_band1.py:set_band1_assignment_rules`
+ `app/services/instruments/_instrument_crud.py:set_unit_of_review`:

- Links 1 + 2 in `all` mode contribute no rules. If both Links
  are `all` and `Instrument.rule_set_id is NULL`, no
  `SessionRuleSet` row is materialised — generate uses the
  synthetic Full Matrix instead (see `spec/assignments.md`).
- The moment either Link's `filter` mode carries a non-empty
  rule list, a `SessionRuleSet` row is materialised in
  `_create_band1_rule_set`. Stored shape:
  - `combinator="ALL_OF"` (the outer wrap that intersects Links).
  - `exclude_self_reviews=False` — aligned with the synthetic
    Full Matrix default; the per-instrument Self review toggle
    on the Assignments page is the sole include/exclude surface
    (PR #1452, 2026-05-26).
  - `rules_json` carries one COMPOSITE per Link with the
    operator's MATCH rules inside.
  - `name` follows the pattern `"New-model instrument #{id} Band 1"`
    (with a numeric suffix on collision).
- Link 3's `group_kind` is written by `set_unit_of_review`
  directly on the instrument row.

Hydration (re-rendering the saved state on edit) reads
`session_rule_sets.rules_json` back into the same shape via
`decode_band1_state` + `decode_group_kind`. The view layer
wraps both into the `new_model_band1_state` and
`new_model_link3_state` dicts the template iterates.

### Band 2 — Display fields + preview row

Band 2 declares **what reviewee context** the reviewer sees
alongside each row of their answer surface, and renders a
live preview of one sample row inline.

> **Self-review policy.** The preview's sample-picker engine runs
> with `excludeSelfReviews=False` — same project-wide rule as
> assignments generation. The preview shows the team's actual
> composition; if the sample reviewer is themselves a team member,
> they appear in their own group. See `spec/assignments.md`
> "Self-review policy" for the rationale and the supported ways to
> suppress self-reviews (Link rule, or the Self-review toggle on
> the Assignments page).

#### Intro card (left of Band 2's preview row)

Top-of-band intro card carrying:

- **Heading.** Read-only reviewer preview of the per-
  instrument heading: `#{N}: {short_label}` when the
  short label is set, just `#{N}` when not — matching the
  `views.instrument_heading` contract the reviewer surface
  consumes. Per the 2026-05-28 operator-identifier policy
  the short label is **edited from the card title** in
  the `<summary>` above (`Setup → Instruments` card), not
  from this preview surface.
- **Description** textarea (inline ✎/✓ pair, POSTs to
  `/sessions/{sid}/instruments/{iid}/identity` as
  `description=...`).

Identity edits don't ride the bulk-save form — they're
independent so an operator can rename without touching Band 1
state.

#### Chip row

Below the intro card, a horizontal scrollable row of chip
buttons — one per populated display-field option in the
session's roster:

- Per-side prefix tag: `Reviewee.Name`, `Reviewee.Email`,
  `Reviewee.tag1 / 2 / 3` (when populated),
  `Pair.tag1 / 2 / 3` (when populated).
- Clicking a chip toggles whether its column appears in the
  preview row below. Toggling is local DOM only; the bulk Save
  picks up the new selection set from `selected_display_keys`
  in the form payload and `set_instrument_display_fields`
  reconciles on the server.

The chip row gates on `is_editing`. View mode renders the chips
as static "selected" pills (no toggle affordance).

#### Preview row

Renders one sample reviewee inline, using the operator's
currently-selected display fields. The sample is picked by the
server (first surviving reviewee under current Link 1 + Link 2
+ Link 3 rules — see `find_sample_in_scope_reviewee` in
`_band1.py`); the operator clicks **↻ Refresh sample** to pick
a new one after editing the rules. In view mode the preview
re-renders from the saved state without a refresh button.

Column widths are drag-resizable. Widths persist as integer
pixels per column key into `Instrument.column_widths` (JSON):

- `identity` — the always-rendered Reviewee / Group identity cell.
- `df_<display_field_id>` — each operator-chosen display field.

The bulk Save mirrors the live widths through a hidden
`column_widths_snapshot` input (JSON) so a fast Save click
can't lose widths to an in-flight async POST to
`/column-widths`.

#### Group-flavor preview

When Link 3 is `group`, the preview row's identity cell
composes **group identity**: bold comma-joined boundary-tag
values on top, then up to `GROUP_MEMBER_NAME_LIMIT` (10) member
names below. Reviewees in the rule-surviving subset that share
the sample's boundary key form the group; if more than 10
qualify, the trailing `... + N more` collapses the overflow.

### Band 3 — Response fields

Band 3 is a stack of inline editor rows — one per Response
Field, plus a trailing empty starter row so the operator can
keep typing without first clicking `+`. Each row defines one
typed input control the reviewer fills in on the surface form.

Each row is a single horizontal flex strip with the following
controls (left → right):

| Control | Bound to | Notes |
|---|---|---|
| Name (text input) | `InstrumentResponseField.label` | The string the reviewer sees as the field's prompt. Drives the paired Band 2 pill's label on save. |
| Type (`<select>`) | `_inline_data_type` | `String / Integer / Decimal / List`, plus a `Quick fill (List)` `<optgroup>` of pre-filled presets (Boolean / Agreement / Grades) — see [Type presets](#type-presets) below. Disabled when the row has saved responses; the inline title pins the reason ("Cannot change — this field has saved responses. Clear them first."). |
| Bounds (inline inputs) | `_inline_min` / `_inline_max` / `_inline_step` / `_inline_list_options` | For `Integer` / `Decimal`: a 3-cell grid of `min` / `max` / `step`. For `List`: a single comma-separated `list_options` input spanning the grid. For `String`: bounds default to length min / max (same `min` / `max` fields). Disabled when the row has saved responses (same reason / title as Type). |
| **R** button | `required` | Toggle. Active = required for reviewers to submit (enforced from Wave 3). |
| **≡** button | `help_text_visible` | Toggle. Active = render a tinted help-text card for this field above the reviewer-surface preview table. The actual help-text *text* is edited on the help card itself (the ✎ → textarea + ✓ flow next to the card title), not on the Band 3 row. |
| **✓** button | — | Saves *this row's* current values back into the paired Band 2 pill (creating the pill on first save, updating its label / metadata on subsequent saves). Pure UX — nothing persists across reload until the card-wide bulk Save runs. |
| **X** button | — | Drops this row and its paired pill. Disabled when the row has saved responses; the title pins the reason. |

Below the row stack, a `+` button spawns another empty row.
The whole card's bulk Save form
(`POST /sessions/{sid}/instruments/{iid}/fields/save`,
form id `dfsave-{iid}`) persists every row in its current
order; row order on save mirrors the **Band 2 pill order**, so
drag-reordering the response pills in Band 2 is the
operator-facing reorder affordance (there is no per-row drag
handle on Band 3 itself).

#### Per-field visibility lives on the Band 2 pill

`InstrumentResponseField.visible` — the flag that decides
whether the field renders on the reviewer surface — is
**toggled from the paired Band 2 pill**, not from Band 3. A
response field's pill in the Band 2 chip row carries
`data-source-type="response"`; clicking the pill flips its
`aria-pressed` / `is-selected` state, and on bulk Save
`bulk_save_fields` writes the new selected state through to
`InstrumentResponseField.visible`
(`app/services/instruments/_instrument_crud.py:1422`).

The reviewer surface form, the reviewer summary HTML, and the
reviewer-record CSV all filter response fields by
`visible.is_(True)` — un-pinning a chip drops the column from
every reviewer-facing render in one step. The Response Field
row in Band 3 stays present (so its bounds / help text remain
editable); only the chip + the reviewer-side renders react.

#### Inline bounds

Bounds are inline on each row (Wave 3 PR i, 2026-05). The
service-side validator (`bulk_save_fields` in
`app/services/instruments/_response_fields.py`) enforces:

- `Number`: `min <= max`, `step <= max - min` (when both
  bounds are set), `step >= smallest representable unit`
  (`Decimal` → 0.1; `Integer` → 1).
- `Rating`: same numeric rules; UI typically constrains `min=1, max=5, step=1`.
- `SingleSelect` / `MultiSelect`: at least one list option, no
  duplicates, options trimmed.

A row that doesn't satisfy its type's contract fails the bulk
save with a 422 and an inline banner pinning the per-row error.
The page re-renders with the operator's edits intact.

#### Type presets

The Band 3 row's "Type" picker is a plain `data_type` dropdown
with four canonical values (`String / Integer / Decimal /
List`) plus a `<optgroup>` of pre-filled List presets:

| Preset | Stored `data_type` | Stored `list_options` |
|---|---|---|
| Boolean (Yes / No) | `list` | `Yes, No` |
| Agreement (Likert 5) | `list` | `Strongly agree, Agree, Neutral, Disagree, Strongly disagree` |
| Grades | `list` | `A+, A, A-, B+, B, B-, C+, C, D+, D, F` |

Picking a preset writes `data_type=list` and pre-fills the
`list_options` input from the option's `data-preset-options`
attribute, then snaps the select back to `List`. The preset's
identity is not stored — only the resulting `data_type` +
`list_options`. The operator can edit either after picking.

Adding a preset: append a `(key, label, list_options)` tuple to
`LIST_PRESETS` in `app/services/instruments/_field_presets.py`.
No DB migration, no template macro changes.

### Action row

Bottom row of the card, right-aligned, in this order:

```
[Save] [Cancel] [Replicate] [Delete] [+Instrument] [Lock / Unlock]
```

- **Save** — only in edit mode. Starts disabled; the
  `newModelInitSaveDirtyTracking` JS helper enables it on the
  first dirty event (any Band 1 input change or Band 3 row
  edit / X / + click). The server-side redirect after a
  successful save re-renders with Save disabled again.
- **Cancel** — only in edit mode. Reloads the same edit-mode
  URL to discard unsaved edits. Same dirty-aware enable
  contract as Save.
- **Replicate** — clones this instrument's contents into a new
  card slotted immediately after it. POSTs to
  `/sessions/{sid}/instruments/{iid}/replicate`. Disabled when
  another instrument is being edited.
- **Delete** — destructive. Form-submit button gated on a
  delete-confirm checkbox rendered just below the row:
  *"Yes, delete **Instrument #N** and its associated assignments
  and reviewer responses."* Disabled when:
  - this is the only instrument in the session, or
  - another instrument is being edited.
- **+Instrument** — spawns a new instrument with default
  Identity + empty Bands 1+2+3 immediately after this card.
  POSTs to `/sessions/{sid}/instruments/add-new-model` with
  `after={iid}`. Same disable conditions as Replicate. The
  legacy `+ instrument` (no `after`) and `+ Group instrument`
  buttons retired in Wave 4 PR 4c — `+Instrument` is the sole
  create affordance.
- **Lock / Unlock** — flips between view and edit mode by
  adding / removing `?editing={iid}` from the URL. Save +
  Lock are independent: Save doesn't lock, so the operator can
  keep editing after a Save. Both disabled past activation
  (`is_ready`).

#### Save / Lock interaction

- An "edit lock" is enforced page-wide: at most one instrument
  may be unlocked at any time. `editing_instrument_id` (resolved
  by the view layer) names the currently unlocked card; if the URL
  asks for an instrument that fails the page-wide check, it
  silently falls back to view mode.
- **Lock-with-unsaved-edits.** When the Lock button is clicked
  on a dirty card, a `confirm()` prompt asks the operator to
  acknowledge that unsaved edits will be discarded. Declining
  cancels the navigation.
- **Save-when-dirty.** Both Save and Cancel start disabled.
  Every editable input on the card is bound to a dirty-tracker
  that enables them on first change. After Save, the
  full-page redirect resets the tracker.

## Add / Replicate / Delete

### `+Instrument` semantics

- Body: `after=<instrument_id>` (optional — defaults to "append
  to end" when omitted).
- Side effects: creates a new `Instrument` row with default
  `name="Instrument #N"` (zero-padded sequence), no display
  fields, no response fields, NULL `rule_set_id`, NULL
  `group_kind`. Lifecycle-aware:
  - `is_draft` → succeeds, no invalidation.
  - `is_validated` → succeeds, invalidates the session back to
    `draft` (`invalidate_if_validated` emits an audit event).
  - `is_ready` → 400 "Cannot add instruments to an active
    session" (defensive — the button is disabled in this
    state).

### `Replicate` semantics

Clones every field of the source instrument except the surrogate
key + the `order` slot:

- Identity (`name` gets a `" copy"` suffix; `short_label` /
  `description` carried as-is).
- Display fields (cloned in order).
- Response fields (cloned in order — including the inline
  bounds and the help text).
- Band 1's `rule_set_id` — **shared, not deep-cloned.** The
  clone points at the same `SessionRuleSet` row. Operator edits
  on the clone's Band 1 will materialise a new `SessionRuleSet`
  on first non-empty save.
- `group_kind` — copied as-is.
- `band1_touched_links` — copied as-is. The clone inherits the
  source's touched state; the operator doesn't have to re-click
  pills.
- `column_widths`, `sort_display_fields` — copied as-is.
- `accepting_responses` / `responses_visible_when_closed` —
  copied as-is.

### `Delete` semantics

Cascade delete. Drops the `Instrument` row plus all
`InstrumentDisplayField` rows, `InstrumentResponseField` rows,
and `Assignment` rows that reference it (which in turn cascade
into `Response` rows). The cascade is ORM-level; the operator's
confirm-checkbox guard is the only friction.

The session's `SessionRuleSet` row referenced by
`Instrument.rule_set_id` is **not** deleted on instrument
delete (the FK is `ON DELETE SET NULL`). Other instruments may
share the row; orphaned rows are left behind without harm — a
future GC pass may reclaim them.

The route guards against deleting the **only** instrument
(returns 400); the UI mirrors this with a disabled Delete
button + the title "Cannot delete the only instrument on this
session."

## Editing flow

The page-wide invariants the lock model enforces:

1. **At most one card unlocked at a time.** Either zero (view
   mode) or exactly one instrument is unlocked.
2. **Past-activation lock.** When the session is `is_ready`
   (activated), every edit affordance disables. The lifecycle
   spec spells out the revert-to-draft path
   (`spec/lifecycle.md`).
3. **Save invalidates validation.** Any successful Save on
   Bands 1 / 3 calls `lifecycle.invalidate_if_validated`. If
   the session was `validated`, it flips back to `draft` and
   the workflow card surfaces the next-action stepper from
   State 2. Audit emits `instrument.band1_rules_updated` etc.
4. **Save and Lock are independent.** Save persists. Lock toggles
   view mode. Lock-with-dirty fires the `confirm()` prompt.

## Validation surfaces

The Validate page (`spec/validate_page.md`) registers a number
of rules against instruments. Active ones that surface here
(see `app/services/validation.py:REGISTERED_RULES`):

- **`instruments.no_fields`** (warning) — instrument has zero
  response fields.
- **`instruments.no_visible_response_fields`** (warning) — every
  response field has `visible=False`. Reviewer page would render
  empty; toggle a row's Visible checkbox.
- **`instruments.no_display_fields`** (info) — instrument has
  zero display fields. Reviewer surface still works (Name + Email
  always render) but is sparse.
- **`instruments.stale_generated`** (warning) — assignment rows
  exist but the engine pass on the current rule + roster would
  produce a different set. The Assignments-page status pill
  shows `stale`.
- **`instruments.zero_included`** (error) — every assignment row
  is excluded (`include=False`). The reviewer page would render
  zero rows even though Generate ran.
- **`instruments.no_rule_pinned`** — *retired in spirit;* still
  registered for legacy-data compatibility but returns no
  findings on post-Wave-5 instruments (the synthetic Full Matrix
  covers NULL `rule_set_id`).

Note: the Wave 5 follow-up "Not set" pill safety gate (see
[Band 1](#band-1--assignment-rule--unit-of-review)) is enforced
**off-validate** — it drives the workflow card's `is_setup_empty`
state directly via `is_configured` / `has_unconfigured` rather
than emitting a `ValidationRule`. The signal surface is the
Workflow card's Setup checklist on the Workflow card right-column
status aside.

## Open / deferred

- **Drag-reorder of cards.** Card order today is mutable via
  `+Instrument after=…` and Replicate but not by drag. Out of
  scope for now; the current affordances cover the dominant
  use cases.
- **Bulk Band-1 templating.** Operators occasionally want
  "apply this Band 1 to every instrument in the session." Not
  surfaced; the workaround is Replicate then trim.
