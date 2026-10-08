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

> **One card shape, one place a rule lives.** Every instrument
> renders the same card — Group versus Individual is Link 3's
> binary state, not a separate flavour — and there is no
> cross-session RuleSet library: each rule lives on its own
> instrument's Band 1. Superseded designs are kept as records at
> `spec/archive/instruments.md`,
> `spec/archive/instrument_builder.md` and
> `spec/archive/group_scoped_instruments.md`.

## Contents

- [Concept](#concept)
- [Page layout](#page-layout)
- [Session status card](#session-status-card)
- [Per-instrument card](#per-instrument-card)
  - [Identity](#identity)
  - [Instrument assignment rule + Unit of review](#instrument-assignment-rule--unit-of-review)
  - [Preview review instrument](#preview-review-instrument)
  - [Response fields](#response-fields)
  - [Branching between response fields](#branching-between-response-fields)
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
- **Instrument assignment rule** (the operator-facing card title; **Band 1**
  internally — "Instrument" disambiguates it from the Operations-row
  Assignments page). Three "Links" — Link 1: Who does the review,
  Link 2: Who is being reviewed, Link 3: Unit of review (Individual
  vs Group). Together these define **the assignment rule** for
  this instrument (`SessionRuleSet` row materialised lazily on
  first non-empty filter).
- **Band 2.** What the reviewer sees: an intro (the name card over
  the visibility card on the left, the help cards on the right) above
  a preview row of the display fields (Name and Email on an Individual
  instrument, plus the reviewee / pair-context tag fields the operator
  picks in Band 3's display-field table) and the response fields.
- **Band 3.** Two tables side by side. On the left, **display
  fields** — which roster and pair-context fields the reviewer sees
  (Name and Email fixed on an Individual instrument), in order (see
  "Display-field table"). On the right, **response fields** — typed
  input controls the reviewer fills in. Each response-field row carries its own inline
  `data_type` + `min` / `max` / `step` / `list_options`; there is
  no per-session response-type catalogue to point at.

Group vs Individual is Link 3's binary state on every
instrument, not a card flavour of its own.

## Page layout

Top → bottom:

1. **Page title** — "Instruments — {session name}" + the standard
   operator session chrome (Workflow card, breadcrumbs).
2. **Guidance card and session status card**, side by side in a
   `.card-columns` pair — so the status card is **half-width**, not
   full.
3. **Per-instrument cards** — one card per instrument, ordered
   by `instruments.order` (the operator's preferred display
   order; insertion order by default, mutable via Replicate +
   `+Instrument` which spawn immediately after a chosen anchor).

There is **no page-level response-type catalogue**: each Band 3
row carries its own inline `data_type` + bounds + list options,
with a small set of pre-filled List presets (Boolean /
Agreement / Grades) baked into the Band 3 type picker.

Each card is wrapped in `<div class="card">`; the per-instrument
card has `id="instrument-{id}"` so deep-links from other surfaces
(Validate page Fix-on-X links, deep-link anchors) land on the
right card.

## Session status card

The card holds no bulk actions (see "No session-level bulk flip"
below).

One-line pill row, left-aligned:

> *Session deadline (auto-close): `<deadline>` · `N accepting` ·
> `M not accepting`*

There is no instrument count and no showing-when-closed count: what
shows once an instrument closes is its visibility policy's call
(below), not a page-level state.

Below it, left-aligned under the pill row:

- **Expand all instruments / Collapse all instruments**:
  flip every per-instrument `<details>` open or closed.
  No state persistence across refresh — operators get a
  fresh all-collapsed default on each page load.

**No session-level bulk flip of `accepting_responses`, and none per
instrument either.** Accepting is session-wide: Activate opens every
instrument, and the deadline, Close session or Revert closes them
all (`spec/lifecycle.md`). What shows once an instrument closes is
governed by the per-instrument **visibility policy**
(`spec/visibility_policy.md`).

## Instrument data model

Beyond the standard rows (id / session_id / name /
short_label / description / order /
accepting_responses) one
boolean carries the operator-controlled page-break layout:

- **`starts_new_page: Boolean NOT NULL`** (Alembic
  revision `e5c1a3b9d472`). `true` means "this instrument
  starts a new page on the reviewer surface" — i.e. a
  page break sits between this instrument and the one
  before it. **Meaningful only for instruments at position
  ≥ 2;** the value on the position-1 instrument is
  ignored at render time.

  The DB `server_default` is `false` and the Mapped
  column declares `default=False`, so a new instrument
  continues the current page and ORM creates match the
  DB.

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
  `_require_instrument_editable`, so the operations 409
  unless the session is **editable** — `draft` or
  `validated`.

## Per-instrument card

**Band 1 / 2 / 3 are shorthand, kept because the code uses them.** The
sections below are named for the headers the card actually shows; the
band numbers survive in prose and in identifiers (`band2_state`,
`band1_touched_links`), which are names and do not change. The mapping:

| Shorthand | What the card heads it |
|---|---|
| Band 1 | Instrument assignment rule (+ Unit of review) |
| Band 2 | Preview review instrument |
| Band 3 | Display fields · Response fields |

Order of stripes (each separated by a horizontal rule):

```
┌────────────────────────────────────────────────────────────────┐
│ Identity (heading + pills)                                     │
│                                                                 │
├────────────────────────────────────────────────────────────────┤
│ Instrument assignment rule                                     │
│ Who does the review │ Who is being reviewed │ Unit of review   │
│  (three columns, vertical rules between)                       │
├────────────────────────────────────────────────────────────────┤
│ Band 2 — intro (name, visibility │ help cards), preview row    │
├────────────────────────────────────────────────────────────────┤
│ Band 3 — display-field table │ response-field table            │
├────────────────────────────────────────────────────────────────┤
│ Action row (Save / Cancel / Replicate / Delete / +Instrument / │
│             +Page break / Lock-Unlock) + delete-confirm cbox   │
└────────────────────────────────────────────────────────────────┘
```

The card carries an empty `<form id="dfsave-{id}">` that the
Save button submits; every editable input on Bands 1+3 sits
outside it and binds to it via `form="dfsave-{id}"`. The identity fields
ride the same form: the card-title `short_label` input, Band 2's
`description` textarea, and each field's `help_text` textarea all
carry `form="dfsave-{id}"`, so one bulk Save commits identity,
Band 1, and Band 3 together through the consolidated `/save`
endpoint. The page drives no per-field ✎/✓ mini-form and no
immediate `/identity` POST.

### Identity

The whole per-instrument card is wrapped in a native
`<details class="instrument-card-collapsible">`. The
`<summary>` is the only thing rendered when
collapsed; expanding reveals the Band 1 / Band 2 / Band 3
stripes below it. Default state on first render of the
page is **all collapsed**; cards auto-open when
`is_editing` or `was_saved` is true so an active edit or a
fresh save never lands hidden. After a drag-and-drop
reorder the sessionStorage-based restore overrides the
auto-open so each card preserves its pre-drag collapse
state exactly.

**Collapse ⇒ lock invariant.** There is no
unlocked-but-collapsed state. Collapsing an **unlocked**
card first triggers a Lock (running the usual dirty-change
confirm, and its discard on accept); if the
operator declines the confirm the collapse is cancelled and the
card stays open and unlocked. Expanding a card
never changes its lock state. Because a rename / description /
help-text edit is only ever visible while the card is open and
unlocked, this keeps a collapsed card's rendered title and body
in sync with what would be saved. To avoid a stray Space keypress
in the rename input collapsing the card, the `<summary>` no
longer toggles on the Space key — collapse/expand is via click on
the summary or the chevron only.

The `<summary>` carries, in document order:

- **Drag handle.** A small grip-dot icon
  (`<span class="instrument-card-drag-handle"
  draggable="true">⋮⋮</span>`) on the left edge. `cursor:
  grab` on hover, `grabbing` while held. Click on the
  handle is `preventDefault`-ed in capture phase so it
  doesn't co-fire the parent `<summary>`'s native toggle.
- **Title (operator-facing short label).** Renders
  `{instrument.short_label}` when the operator has set
  one, else the ugly fallback `"Instrument_{session_seq}"`
  in muted italic so it reads as a placeholder rather than
  a chosen name. Per the operator-identifier policy: the
  `#` prefix is reserved for the reviewer-
  facing `#{N}: {short_label}` heading inside Band 2's
  "Preview reviewer instrument" card; operator-facing UI
  uses `short_label` with the `Instrument_{session_seq}` fallback.
  The fallback is generated by
  `app/services/instruments/_state.py::_instrument_label`
  (also drives audit-event copy + validation messages).
- **Title edit (lock-driven).** The title is a view/edit
  swap keyed on the card's lock state — there is no
  per-title ✎/✓ button. When the card
  is **locked** a read-only `data-card-title-view` span
  renders `short_label` (or the muted `Instrument_{session_seq}`
  fallback). When **unlocked** a 32-char
  `data-card-title-input` `<input>` (bound to the card's
  `dfsave-{id}` form, `name="short_label"`) takes its
  place. Editing stages into that form input; the bulk
  Save commits it through the consolidated `/save`
  endpoint — no separate `/identity` POST. `newModelSetLock`
  syncs the view span from the input's live value when the
  card locks, so the collapsed title matches the input the
  card was showing. A *dirty* card cannot reach that path —
  it discards and reloads instead — so the sync only ever
  copies persisted values. An empty
  value clears the label and reverts the view to the muted
  `Instrument_{session_seq}` fallback.
- **Status pills:**
  - **Set up / Not set up** — mirrors the workflow
    card's `instruments_service.is_configured(db,
    instrument)` predicate. `pill-info` for set up;
    `pill-warning` for not set up. Computed in
    `views.build_instruments_context` as
    `is_configured_by_instrument[instrument.id]`, and
    **repainted on Save without a reload**: the
    consolidated `/save` returns the freshly computed
    `is_configured` for the saved instrument alongside
    `ok`, and the client swaps this pill's text and tint
    from it (`data-instrument-setup-pill`). The same
    response carries `instruments_configured` and
    `instrument_count` (the session's `configured_counts`
    tuple, unpacked into two top-level JSON keys), which
    repaints the setup status row's aggregate
    Instruments pill (`data-instruments-configured-pill`)
    — one card's save can flip that too, and the two
    disagreeing on one screen would be worse than both
    being stale. The predicate itself stays server-side;
    the client picks text and tint only, never re-deriving
    whether an instrument is set up. A failed (422) save
    moves neither pill. The no-JS `/fields/save` fallback
    redirects, so both pills are correct there by reload.
  - **Locked / Unlocked** — mirrors `is_editing`. The
    "Unlock" button enters edit mode (pill says
    "Unlocked", `pill-warning`); "Lock" exits (pill
    says "Locked", `pill-info`). Makes a card's edit
    mode visible at a glance without expanding it.
- **Toggle chevron.** A large `▾` icon on the right edge
  that rotates 180° via the `details[open] summary
  .instrument-card-toggle-icon` CSS selector — no JS for
  the per-card toggle.

**Top button row.** Directly under the `<summary>`, left-aligned, an
expanded card repeats the bottom action row's lock controls so a long
card need not be scrolled to change mode: **Lock**, **Save** and
**Cancel** while unlocked, **Unlock** while locked. They are the same
controls as the bottom row's (see "Action row" below): Lock and Unlock
carry the same toggle hooks, so a dirty card's confirm fires from
either, and Save and Cancel start disabled and are enabled by the same
dirty tracker in lockstep with the bottom-row copies. Lock and Unlock
are disabled when the session is not editable.

**No per-card `accepting responses` pill.** The session status
card's one-line summary already reports how
many instruments are accepting, so a per-card mirror would
duplicate it — and visibility-when-closed carries no
operator control to mirror at all (below).

Beneath the `<summary>` (only visible when the card is
expanded):

- **No per-instrument open / close.** Accepting is session-wide,
  so the card carries no flip form in any state.

**Visibility when closed has no operator control** — neither
per-card nor session-wide. It is governed by the per-instrument
**visibility policy** (`spec/visibility_policy.md`). An older
Settings CSV that still carries a `responses_visible_when_closed` row
imports with the value dropped.

`short_label` and `description` are **not** rendered in
the Identity heading — `short_label` is edited from the
card-title swap in the `<summary>` (see "Title edit"
above) and `description` lives in Band 2's intro card as
a lock-driven view/edit swap; both ride the `dfsave-{id}`
bulk-Save form rather than a separate `/identity` POST, so
the heading row stays compact. The intro card's
heading is the one `views.instrument_heading` gives the
reviewer — `#{N}:` with N the on-page position, and no
prefix in a one-instrument session — so the preview matches.

#### The per-session ordinal

`Instrument.session_seq` is the instrument's operator-facing number:
assigned once at creation, never updated, unique to its session. It is
what the `Instrument_{session_seq}` fallback label, the delete
confirmation and the card tint all read, and it is deliberately **not**
`Instrument.id` (workspace-wide) or `Instrument.order` (display
position, which drag-and-drop moves).

- **Creation order, not display order.** `POST .../instruments/order`
  ships, so a position-keyed number would move under the operator's
  drag. `session_seq` does not.
- **Gaps are the contract.** Delete the second of three and the
  labels read 1, 3. Closing the gap would be renumbering, which is what
  a stable handle must not do.
- **A trailing delete hands the number back.** It is `max + 1` over the
  session's live rows, so deleting the *newest* of 1, 2, 3 frees 3 for
  the next instrument created. Interior deletes are safe; this one case
  is not, and a monotonic sequence would need a high-water mark the
  column does not keep. **Accepted**: a trailing
  slot has no successor, so recycling there disturbs no ordering the
  operator can see. Pinned as it behaves by
  `test_a_trailing_delete_hands_the_number_back`.
- **A clone preserves the source's values** — `session_clone` copies
  every mapped column, so a source reading 1, 3, 2 reproduces as
  1, 3, 2. A config import mints fresh, because the payload keys
  instruments by `short_label` and carries no ordinal.
- **Allocation is a context-sensitive column default**
  (`app/db/models/instrument.py::_next_session_seq`), so no creation
  path supplies it and none can forget it. There is no *server*
  default: a row inserted outside SQLAlchemy fails loudly rather than
  minting `Instrument_0`. **Two rows inserted in one flush would both
  take the same number** — nothing constrains duplicates, and no
  unique index exists on `(session_id, session_seq)`. Latent today:
  every creation path flushes immediately.
- **Older audit summaries embed `Instrument_{id}` labels** rather
  than the ordinal, so the number they name may match a different
  card.

#### Card background colour

Each instrument card's background pulls from a 6-colour
pastel palette keyed by `(instrument.session_seq - 1) % 6`. The
palette is in `instruments_index.html` (`instrument_palette`
list). Keyed by the **per-session ordinal — the same number the
card title shows** — so the tint means something the operator can
read rather than being a fourth fact about the instrument, and it
still rides with the instrument across reorders, replicates and
deletes: a drag moves the card, not its colour. Not `instrument.id`,
which is workspace-wide and would tint by insertion date, and not the
loop index, which would reshuffle every colour on every drag.

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
The rules a break obeys (rationale recorded in
`guide/archive/segment_18M_instrument_layout.md`):

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
Unlock. The two add buttons:

- **+Instrument** — creates a new instrument
  immediately after this one. The only affordance that
  adds an instrument.
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

### Instrument assignment rule + Unit of review

The **Instrument assignment rule** card (titled "Instrument assignment rule"
for the operator — the "Instrument" prefix disambiguates it from the
Operations-row Assignments page; **Band 1** internally, and the `band1` /
`link1`–`link3` ids are retained in code) owns the **assignment rule** for
this instrument. Three columns
of equal width with a 1px vertical rule between them. Each column ("Link")
is a self-contained sub-builder. The card title is bold (matching the
other card names); the three Link labels below are unbold. The columns
(`.band1-grid`) keep a `76rem` floor, which holds the rules' selects at
a usable width, and scroll in a `.table-scroll` below it rather than
spilling past their dividers, locked or not: the grid is the lock
region, never its scroller. A rule's tag select shrinks from half its
row to make room for a wider operator, so "IS DIFFERENT FROM" never
spills either.

| Column | Link (operator label) | Vocabulary |
|---|---|---|
| Left | Link 1 — Who does the review | `reviewer.tag1 / 2 / 3` + `pair_context.tag1 / 2 / 3` |
| Centre | Link 2 — Who is being reviewed | `reviewee.tag1 / 2 / 3` + `pair_context.tag1 / 2 / 3` (with cross-side operands) |
| Right | Link 3 — Unit of review | Individual vs Group; if Group, picks reviewee + pair-context boundary tags |

#### Self-review exclusion (Link 3 column, below the rule)

The Link 3 column carries one control that is **not** a unit-of-review
setting. It sits here for space alone, and says so twice: a horizontal
`.col-divider` rule — the sibling of the 1px vertical rules between the
three columns — separates it from the unit-of-review controls above, and
its own heading **Self reviews** names it, so it does not read as a third
Link 3 state. The heading takes the unbold weight of the three Link
labels; bold belongs to the card title.

**The checkbox copy follows the Link 3 pill, live.** Two whole
sentences, not one with a swapped noun:

| Link 3 mode | Label |
|---|---|
| Individual, or `Not set` | *Exclude if the individual reviewed is the reviewer* |
| Group using tags | *Exclude if the reviewer is in the group being reviewed* |

`Not set` takes the individual sentence because that is the `link3_mode`
value it submits.

**The control is hidden while any of the three Links is `Not set`** —
rule, heading and checkbox together, since a lone divider under nothing
reads as a rendering fault. An instrument with an unset Link has no
settled rule to except self-reviews *from*. Visibility follows the pills
live, from one function both pill handlers call.

**Two transitions clear the stored flag**, so what is hidden or
re-scoped is also false:

| Transition | Why |
|---|---|
| Any Link → `Not set` | A flag left ticked would sit in the rule set, invisible on the page and live at the next Generate. |
| Link 3 `Individual` → `Group using tags` | The two modes except different things. A tick agreed against *the individual reviewed is the reviewer* must not carry into *the reviewer is in the group being reviewed*, which drops every member row of that group. |

Both are enforced **server-side on save** (`resolve_exclude_self_reviews`),
with the client clearing the box at the same moment so the page and the
store agree. **Session-config import is held to the first rule too**
(`clear_unsettled_exclude_self_reviews`, run once both the rule-set rows
and the instrument rows have landed): a bundle pairs those halves
independently, so without it an import could store a flag the UI then
hides — invisible and in force at once.

There is no third rule for `Group using tags` → `Individual` because the
pill cannot make that move directly: the cycle is `Not set` → `Individual`
→ `Group using tags` → `Not set`, so the reverse passes through `Not set`,
which hides the control and clears the box on the way. **The cycle's shape
is therefore load-bearing** — changing it to allow the direct move requires
a rule for it. Both spellings ride on the element as `data-copy-*`
attributes and `newModelToggleUnitMode` swaps them as the pill cycles —
the handler that already owns every other live consequence of the pill,
so the control cannot describe the opposite of what the operator has
just selected while the card is unsaved.

It reads and writes `session_rule_sets.exclude_self_reviews` for the
instrument's pinned rule set. **Default off.** An instrument whose Band 1
is untouched has no rule set row; turning the flag *on* materializes an
empty (Full Matrix) one, which is output-identical to the synthetic
schema the engine substitutes for a null `rule_set_id`. Turning it *off*
with no row is a no-op — `False` is the default, so no empty row is left
behind. Writes emit
`session_rule_set.exclude_self_reviews_set` and invalidate a validated
session.

The checkbox is inert with the rest of the Band 1 grid while the card is
locked.

**It takes effect at the next Generate**, not on save — the generator
honors it at the `pair_include` branch, after the engine's pair
fan-out, so a group-scoped instrument drops the reviewer's whole group
rather than one `(R, R)` pair. On an instrument that has already
generated, this **deletes** the self-review rows and their saved
responses; the reconcile dry-run counts them and the Prepare card
confirms before anything is written. See `spec/assignments.md`
§ *Self-review policy* for why the exclusion is honored there rather
than at the rule engine's desugar stage, which still never drops a
self-pair.

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
equivalent for Link 3). **The cycle wraps rather than
terminating** so the operator can put a Link back to `Not set`
and surface the instrument as unconfigured on the workflow card
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

This is the **safety gate** that stops the implicit Full Matrix
default (synthesised when `rule_set_id` is NULL — see
`spec/assignments.md`) shipping silently. The
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
  `views._instruments.new_model_usable_tags`.
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

The builder's disabled buttons are visual markers: "THE SAME"
beside the + button, and an "AND" on every boundary cell but the
last. They say that boundary tags compose additively (every tag
matters) and that group membership is "the reviewees agreeing on all
of these". Only the last cell carries the X, so cells come off from
the end; a lone cell's X is disabled. The page renders this, and the
add and remove buttons keep it.

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
    Full Matrix default; the Link 3 column's **Self reviews**
    checkbox (§ *Self-review exclusion* above) is the control
    that sets it.
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

### Preview review instrument

Band 2 declares **what reviewee context** the reviewer sees
alongside each row of their answer surface, and renders a
live preview of one sample row inline.

> **Self-review policy.** The preview's sample-picker engine runs
> with `excludeSelfReviews=False`, the same desugar-stage rule
> assignments generation follows. The preview shows the team's
> actual composition; if the sample reviewer is themselves a team
> member, they appear in their own group.
>
> **The preview follows the instrument's self-review rule.** When
> the Link 3 checkbox is set, the picker drops self-reviews from the
> engine's **output** before choosing a sample — never by flipping
> `excludeSelfReviews`, which would drop pairs before group
> composition is known. On a grouped instrument the whole group
> goes, so a reviewer who is one of their own group's reviewees
> takes that group out of the preview entirely; if no group
> survives, the preview renders empty rather than showing a row
> Generate would not produce. Same rule, same placement **and the
> same keying** as `assignments._diff_one_instrument`: the group key
> comes from `group_key_for_pair` over the full decoded boundary,
> pair-context tags included. That is deliberately *not* the
> reviewee-only field list this function uses for the member-id
> partition — a pair-context-only boundary would leave that list
> empty and silently drop the test to pair level while the generator
> still grouped.
>
> It reads the **persisted** flag: the checkbox is not among the
> fields the Refresh handler posts, so an unsaved tick shows after
> the card is saved. The preview already blends live Link 1 / Link 2
> edits with persisted Link 3 state.
>
> See `spec/assignments.md` § *Self-review policy* for the two
> supported ways to suppress self-reviews.

#### Intro card (top of the left column)

Top-of-band intro card carrying:

- **Heading.** Read-only reviewer preview of the per-instrument
  heading, composed by the reviewer surface's own rule
  (`views.instrument_heading`, served as
  `band2_intro_heading_by_instrument`): `#{N}: {short_label}`, or
  `#{N}` with no short label; in a one-instrument session the short
  label alone, or the description in its place, and no heading at all
  when there is neither — locked, such a card (`data-intro-empty`) is
  not drawn, as the reviewer surface draws none. On Lock,
  `newModelIntroHeading` recomposes it from the saved values (a node
  test holds it to the Python rule). Per the operator-identifier
  policy the short label is **edited from the card title** in the
  `<summary>` above (`Setup → Instruments` card), not from this
  preview surface.
- **Description** — a lock-driven view/edit swap: a read-only
  paragraph when the card is locked (`data-intro-description-view`),
  the reviewer's subtitle spaced as the surface spaces it and hidden
  when the heading has none, so no blank line;
  a `data-intro-description-input` textarea when unlocked. The
  textarea binds to the card's `dfsave-{id}` form
  (`name="description"`), so its value commits with the bulk Save
  through the consolidated `/save` endpoint. When the card locks,
  `newModelSetLock` recomposes the heading and subtitle from the
  label and textarea (the same `newModelSyncTextViews` call the card
  title uses — see that bullet above). A *dirty* card cannot reach
  that path — it discards and reloads instead — so this sync, like
  the title's, only ever reads persisted values.

Identity edits ride the bulk-save form: one Save commits identity
together with Band 1 and Band 3, and the page issues no separate
`/identity` POST.

#### Visibility card (under the intro card)

The "Who can see what you wrote (other than admin)" card sits under the
intro card in the left column of Band 2's intro, laid out as the
reviewer surface's are (`spec/reviewer-surface.md`, "Intro and help
cards"), and is both the reviewer-surface preview and
the visibility editor — the same locked / unlocked swap as the
description box above it. **Locked**, it renders the
reviewer's own two-row table (`data-lock-only`), each mode as a
display-only pill (`pill pill-count`, carrying
`data-new-model-vp-preview-cell`) rather than plain text — see
"Reviewer-surface transparency card" in `spec/visibility_policy.md` §6.
**Unlocked**, it is
the editor (`data-unlock-only`, `data-new-model-vp-editor`
`data-new-model-vp-form`): three rows, "You (reviewer)", "Reviewees" and,
below a `row-group-start` divider (`spec/ui_elements.md` §10),
"Observers", with the note "Observers are shown here for setup only;
reviewers don't see this row."

The four cells that can change are cycle chips (`b3_mode_cycle`), each
rotating through the modes `spec/visibility_policy.md` §3.1 allows for
its `(audience, window)` cell; the cycle sets themselves are not restated
here. The two cells that can't — Reviewer / Session-ongoing (pinned to
Raw) and Reviewees / Session-ongoing (pinned to off) — stay plain
`b3_static_pill` labels. Both macros keep the `b3_` prefix from when the
editor lived in Band 3's table, which this card retires.

The six `*_mode` hidden inputs ride the card's `dfsave-{id}` form and
render unconditionally, whatever the lock state, so Save always carries
them. A cycle also repaints the locked table's matching pill
(`data-new-model-vp-preview-cell`), since Save is a fetch and never
reloads.

Locked, the card is not inside a lock region: Band 2's are the intro
card, this card's editor, the preview and each help card, so the locked
table, which holds no control, keeps a `.table-scroll` that scrolls. The
card fades with the intro card above it.

The help cards, JS-built by `rebuildPreview`, fill the right column in
field order, as on the reviewer surface. Nothing is measured, so they
stay put as the operator types into their textareas, locks or unlocks
the card, or resizes the window.

#### Display-field table

Band 3's left column (`data-new-model-band3-left`) is a headerless,
compact (`table-compact`, `spec/ui_elements.md` §10) table
(`data-new-model-df-table`), one row per display field
(`data-new-model-df-row`), in display order. **The row is the
display-field model**: order is display order, and the row's checkbox is
its selection — both read live by Band 2's preview and persisted only
through the card's Save (`dfRows` in
`app/web/templates/operator/instruments_index.html`). An edit shows in
the preview at once.

Each row holds:

- an **Active** checkbox (`data-new-model-df-active`) — the field's
  selection;
- the field's session-wide label as a display-only pill (`pill
  pill-count`, no click handler);
- ▲ / ▼ `btn secondary btn-short` move buttons (not `.btn-icon` —
  `spec/ui_elements.md` §10), absent on a locked row. An unticked row
  can still be moved.

**Name and Email are locked**: every instrument is created with these
two rows (`ensure_locked_display_fields`, called by
`ensure_default_instrument` and `create_instrument`, and by the page
render's `repair_display_fields` while setup is editable), and each renders
a ticked, disabled checkbox, no move buttons, and a tooltip naming the
pinned slot — "Always shown — pinned first" (Name) / "Always shown — pinned second" (Email). **On a
group-scoped instrument**, a field a group row can't show — Email
included — renders unticked and disabled, tooltip "Not shown on group
rows"; Name stays locked and ticked in group mode, so member names
always show (author's ruling, 2026-10-07; see "Group-flavor preview"
below). Every other row's tooltip is "Show this
column". These disabled checkboxes are the locked-field affordance
(`spec/ui_elements.md` "Label or control").

#### Preview row

Renders one sample reviewee inline, using the operator's
currently-selected display fields. The sample is picked by the
server (first surviving reviewee under current Link 1 + Link 2
+ Link 3 rules — see `find_sample_in_scope_reviewee` in
`_band1.py`); the operator clicks **↻ Refresh sample** to pick
a new one after editing the rules. In view mode the preview
re-renders from the saved state without a refresh button.

Column widths are drag-resizable (in the unlocked card). Widths
persist as integer pixels per column key into
`Instrument.column_widths` (JSON):

- `identity` — the always-rendered Reviewee / Group identity cell.
- `df_<display_field_id>` — each operator-chosen display field.
- `rf_<response_field_id>` — each Band 3 response-field column
  (keyed by name for a not-yet-saved field, re-keyed to id on
  save; carried on the row's `data-width` and folded in by
  `set_band2_state`).

**The preview lays its table out as the reviewer surface does**
(`spec/reviewer-surface.md`), so its columns start at the surface's
widths. A per-reviewee table is automatic until a column width is set
(a hidden column's counting, as the surface's `has_custom_widths`
does), then `table-layout: fixed`; its cells take the surface's padding
and its inputs their own size; its headers and cells carry the surface's
width classes (`rs-narrow` on a profile-link or number column,
`rs-textlong` on a String over 100 characters, `th.rrw-sortable`) and,
wherever the preview shows no sort control of its own, an inert copy
of the surface's ↕ sort button, since a narrow column is as wide as its
header. Under the fixed layout an unsized profile-link column starts
at `views.profile_column_ch_width` (mirrored as `profileColumnCh`: its
label plus room for the sort button, never narrower than "View") and a
number column at `views.numeric_column_ch_width` (mirrored as
`numericColumnCh`: its header or its min / max digit span), not
`rs-narrow`'s 1% of the table. While automatic, each `<col>` keeps that
start in `data-start-style`; a drag applies them as it turns the table
fixed, as saving a width will turn the surface's. A group-flavor
preview is always fixed, as the surface's group table is, its number
columns starting the same way. A dragged width wins.

Widths never POST on their own. A resize stages the live widths
into a hidden `column_widths_snapshot` input (JSON); the bulk
Save reads that snapshot and commits it through the consolidated
`/save` endpoint. Staging (not an async `/column-widths` POST)
is what keeps a fast Save click from losing an in-flight width
change.

#### Group-flavor preview

When Link 3 is `group`, the preview row's identity cell
composes **group identity**: the sample's values for the selected
`reviewee.tag_*` display fields, bold and comma-joined, on top, then
up to `GROUP_MEMBER_NAME_LIMIT` (10) member names below (Name is
locked in group mode). The reviewer surface composes its line the same way
(`spec/reviewer-surface.md` "Group-scoped instruments"). Reviewees in the rule-surviving subset that share
the sample's boundary key form the group; if more than 10
qualify, a trailing `, +N more` collapses the overflow. A
pair-context tag lives on a reviewer's relationships, so the preview
does not partition on one: a mixed boundary partitions on its reviewee
tags only, and a pair-context-only boundary lists the sample reviewer's
rule-surviving reviewees as the group. The rule-surviving subset is the
one the last Refresh computed; before any Refresh there is none, and the
group is the boundary partition of the whole active roster.

### Response fields

Band 3 (`.band3-grid`) splits `grid-template-columns: minmax(0, 3fr) minmax(0, 17fr)` — 15%
display fields, 85% response fields. Both tracks' `0` minimum lets each table scroll
inside its `.table-scroll` on a narrow card rather than widening its
column past its share; the response-field table keeps a `66rem` floor so
its boxes stay usable while it scrolls. A locked card
scrolls too: its lock regions are the two tables, not the band, since an
inert `.table-scroll` couldn't scroll. Bands 1 and
2 follow the same rule: Band 2's preview is the lock region, its
`.table-scroll` a plain wrapper directly around it. The left column holds
the display-field table above; the right column, below, is the
response-field table.

**The right column is a table** (`rf-table`, `spec/ui_elements.md`
§10): one `<tbody data-new-model-rf-group>` per group, ruled under the
group and not inside it — a field on its own, or a parent with its
condition row and the fields it governs (branching,
["Branching between response fields"](#branching-between-response-fields)
below). **The row is the response-field model**, the same
contract the display-field table's row carries (see "Display-field
table" above): its state — selection, the name and shape last
committed, column width, help text, response count — lives on the
`<tr>`, read everywhere (the preview, the stager, Save) through one
function, `rfRows`. **No standing blank row**: a card with no saved
fields renders one blank, unlabelled placeholder row instead — not a
field until the operator types into it — so there is always a "+" to
press; deleting down to one row leaves that row rather than none.

Each row holds, left to right (a governed row shifts these one column
right per level, behind a bar per branch it sits in; two slots after
join, `td.rf-slot`, keep six leading columns on every row — see
["Branching between response fields"](#branching-between-response-fields)):

| Control | Bound to | Notes |
|---|---|---|
| **Active** checkbox | `InstrumentResponseField.visible` | The field's selection — whether it renders on the participant surfaces and their CSVs (see below). Unticking a field with saved responses asks to confirm first — "Hide … from the reviewer surface?", naming the response count and that the data is preserved for audit. An inactive row is not dimmed. |
| **+** button | — | Inserts a new row (its own `<tbody>` group) directly after this one's, seeded with the next default label (see "A field's default label" below). On a governed row it adds a field to the same branch instead, directly after the row's unit — the row, its condition row and every deeper row (see ["Branching between response fields"](#branching-between-response-fields)). |
| **⑂** / **↰** / **↳** | `branch_parent_id` / `branch_op` / `branch_value` / `branch_mode` | Fork, join and detach — see ["Branching between response fields"](#branching-between-response-fields) below. |
| Name (text input) | `InstrumentResponseField.label` | The string the reviewer sees as the field's prompt. Empty until typed — see "A field's default label" below. |
| Type (`<select>`) | `_inline_data_type` | `String / Integer / Decimal / List`, plus a `Quick fill (List)` `<optgroup>` of pre-filled presets (Boolean / Agreement / Grades) — see [Type presets](#type-presets) below. Disabled when the row has saved responses; the inline title pins the reason ("Cannot change — this field has saved responses. Clear them first."). |
| Bounds (inline inputs) | `_inline_min` / `_inline_max` / `_inline_step` / `_inline_list_csv` | For `Integer` / `Decimal`: a 3-cell grid of `min` / `max` / `step`. For `List`: a single comma-separated `list_options` input spanning the grid. For `String`: bounds default to length min / max (same `min` / `max` fields). Disabled when the row has saved responses (same reason / title as Type). |
| **R** button | `required` | Toggle. Active = required for reviewers to submit; the reviewer surface blocks submission and names the missing fields. Stages Band 2 state directly, so Save alone persists a toggle. Grayed out on a row a Require branch governs, where the condition decides (see ["Branching between response fields"](#branching-between-response-fields)). |
| **≡** button | `help_text_visible` | Toggle. Active = render a tinted help-text card for this field in Band 2's intro columns, above the reviewer-surface preview table. The help-text *text* is a plain `help_text` textarea on that card (shown when the instrument card is unlocked, `data-lock-only` read view when locked), bound to the `dfsave-{id}` form, so it commits with the bulk Save. Stages Band 2 state directly, like R. |
| **▲ / ▼** | — | Full-size `btn secondary` buttons (not `btn-short` — that size is the display-field table's, see "Display-field table" above) that swap this row's `<tbody>` group with its neighbor. They move a **group**, not a row; a governed row moves its unit (itself, its condition row and any branch inside it) past the neighboring unit within its branch instead — see ["Branching between response fields"](#branching-between-response-fields). |
| **X** button (`.btn.destructive`) | — | Drops this row (its `<tbody>`), matching Band 1's rule/unit X. Disabled when the row has saved responses (title pins the reason), or when it is the only row left. In a branch, deletion runs bottom-up — see ["Branching between response fields"](#branching-between-response-fields). |

**A row commits to the preview by itself** whenever its live name and
shape are valid and differ from what it last committed — checked on
every keystroke and type change, so a half-typed bound never reaches
the preview. Committing writes the row's `data-label` /
`data-rf-data-type` / `-min` / `-max` / `-step` / `-list` attributes,
which the preview cell and the constraint line always read, never the
live inputs, so an unsaved edit never leaks into the reviewer-surface
preview. An invalid or not-yet-valid row keeps its last committed shape
and is marked with an amber left edge (`data-row-pending`); the reason
is the row's tooltip, which also names what the preview shows
meanwhile. A brand-new row starts selected.

**A field's default label** is the next "Field N" no row goes by, shown
muted as the empty name box's placeholder
(`table.rf-table td.rf-name input::placeholder`,
`spec/ui_elements.md` §10) — the name the field goes by everywhere a
name is read (the preview, the pending marker, the auto-commit, and
what Save sends) while the box is empty, so Save never drops a field
for want of a name; only X deletes one. Clearing a typed name brings
the default back. → or Enter in an empty box, or typing into it, takes
the name as typed, shown in normal style thereafter. **A saved field's
default never moves** — editing another row's name can't rename it —
and a saved "Field N" reloads as a typed name in normal style, since
nothing records that it was ever a default.

**A "+" row lives only on the page until a successful Save**: it
commits to the preview at once, but the card turns unsaved, and
Cancel's discard reload drops it.

**Order follows the rows.** ▲ ▼ swap a row's `<tbody>` group with its
neighbor, or on a governed row its unit with the neighboring unit in
its branch; "+" inserts a new group directly after the pressed row's,
or on a governed row a new field in its branch directly after its unit;
the bulk Save serializes rows in row order (a named, uncommitted row
persists unselected, in place).

The whole card's bulk Save form (form id `dfsave-{iid}`)
POSTs to the consolidated
`POST /sessions/{sid}/instruments/{iid}/save` endpoint — one
request carries identity, Band 1, the Band 2/Band 3 state
snapshots, and column widths together (its JSON response is detailed
under "Save" in "Action row" below). The page drives no other save
endpoint except `/fields/save`, its no-JS fallback, and reads the
Band 2 preview row from `POST .../preview-sample`, which saves only
the sample it picks (`sample_reviewee_name` and
`sample_group_member_ids` in the instrument's Band 2 state, through
`set_band2_state`); the Band 1 form state it ran against stays
unsaved. The per-concern routes `/band2-state`, `/column-widths`,
`/display-fields/order`, `/identity` and `/edit` (description), and
the per-field routes `/fields`, `/fields/add-row`,
`/fields/{fid}/edit`, `/fields/{fid}/delete`, `/fields/{fid}/move`
and `/display-fields`, remain available to fixture and programmatic
callers only.

`InstrumentResponseField.visible` — read live off each row's Active
checkbox — is what the reviewer surface form, the reviewer summary
HTML, the reviewer-record CSV, the reviewee results page and the
observer collation page and its per-instrument CSV filter response
fields by it.
Unticking Active drops the column from every participant-facing render
in one step. The operator's own extracts keep it, and the row itself
stays present in Band 3 so its bounds and help text remain editable.

**The operator's reviewer-side counts filter it too**:
`monitoring.per_reviewer_progress` excludes an invisible `required`
field from the `Required Fields` column and from what makes an
assignment complete, since a reviewer who was never shown a field
cannot answer it. `per_reviewee_coverage` does **not** — the
asymmetry, and why, are in `spec/operations_pages.md`.

#### Inline bounds

Bounds are inline on each row. The service-side validator is
`_validate_response_field_shape` in
`app/services/instruments/_band2.py`, reached from
`_sync_response_fields_to_db` on every Save. It branches on the row's
`data_type` — the same four values the Bounds row above uses, not
response-type display names — and enforces:

- **Every type, checked first:** a non-finite Min, Max or Step
  (`nan`, `inf`, or an overflowing literal like `1e309` — all parse as
  a float but none is a usable bound) is refused as
  "<Min|Max|Step> must be a number." (`"Max length must be a number."`
  for a String row's Max).
- `Integer` / `Decimal`: `max >= min` when both are set; `step > 0`;
  and `step <= max - min` when all three are set and `max > min`, so
  the field has at least two valid values rather than only `min`.
  Equality is accepted (`min=0, max=1, step=1` is a useful Boolean-like
  field). A field with `min` equal to `max` is one fixed value, and its
  Step is not checked against the range (`step > 0` and the Integer
  whole-number rule still apply): a blank Integer Step saves as 1
  (below), so refusing it would block every later Save of the card.
- `Integer` only, checked after the rules above: Min, Max and Step
  must each be a whole number — "Integer fields take whole-number Min,
  Max and Step. Choose Decimal for steps like 0.5." A stored field is
  exempt when it has responses and its type and bounds are unchanged
  from what's stored, since those bounds are locked and refusing them
  would block every Save of the card; a stored field without
  responses meets the rule on its next Save. A Settings CSV import
  applies the same rule in its parse phase, with no exemption
  (`spec/csv_contracts.md` §3.3): Quick Setup's replace acknowledges
  the responses it deletes, and Rehydrate refuses such an extract
  (`spec/rehydrate.md` §6.2).
- `String`: the `max` slot is read as `max_length` and must be `> 0`
  when set.
- `List`: at least one option once blanks are trimmed.

Nothing else is enforced here: there is **no** minimum-step rule tied to
the type's precision, and **no** duplicate-option check.

**A blank Integer Step saves as 1.** After the rules above pass, the
card's Save (`_sync_response_fields_to_db`) stores an `Integer` field's
blank Step as 1, the step an Integer takes anyway, and the builder writes
the 1 into the row's Step box; until then the box shows its muted "Step"
placeholder. A blank Step stored earlier fills in on the next Save even
when the field has responses, since it already meant 1, so the shape
guard does not count it as a change. Two exceptions keep a Step blank: a
`Decimal`, and an `Integer` whose stored Min is not whole (kept by the
exemption above), since steps count from Min and 1 would make its whole
answers invalid. The default is the card Save's only: a Settings CSV
import stores a blank Step as blank, and the reviewer surface still
steps such an Integer by 1. Once stored, the Step shows in the reviewer's
constraint line ("1-5, steps of 1").

A row that doesn't satisfy its type's contract fails the bulk
save with a 422 and an inline banner pinning the per-row error.
The page re-renders with the operator's edits intact, and nothing
else on the card was saved either — the Save is all or nothing
(*Action row*, **Save**, below).

The client mirror, `newModelRfValidateShape`, gates a row's auto-commit
with the same messages in the same order — non-finite bounds, then the
Integer/Decimal rules, then the whole-number rule with its
has-responses exemption (read off the row's `data-has-responses`
attribute) — and the failing message is what the row's pending-marker
tooltip shows. **It checks only the bounds the row's type shows**:
Min, Max and Step for Integer / Decimal, Min and Max for String, none
for List. A type switch hides the other inputs without clearing them,
and the server checks them all, so a non-finite value typed and then
hidden still commits client-side and is refused at Save, naming the
field.

#### Type presets

The Band 3 row's "Type" picker is a plain `data_type` dropdown
with four canonical values (`String / Integer / Decimal /
List`) plus a `<optgroup>` of pre-filled List presets:

| Preset | Posted `data_type` | Stored `list_options` |
|---|---|---|
| Boolean (Yes / No) | `list` | `Yes, No` |
| Agreement (Likert 5) | `list` | `Strongly agree, Agree, Neutral, Disagree, Strongly disagree` |
| Grades | `list` | `A+, A, A-, B+, B, B-, C+, C, D+, D, F` |

Picking a preset snaps the select back to `List` (`data_type=list`,
stored as `List`) and then pre-fills the `list_options` input from the option's
`data-preset-options` attribute. The order matters for a branch
parent: filling the options recomputes the row, and it must already
read as a List, or a condition's "is not" is rebuilt as "is". The preset's
identity is not stored — only the resulting `data_type` +
`list_options`. The operator can edit either after picking.

Adding a preset: append a `(key, label, list_options)` tuple to
`LIST_PRESETS` in `app/services/instruments/_field_presets.py`.
No DB migration, no template macro changes.

#### Branching between response fields

A **parent** field (Integer, Decimal or List — never String)
carries a condition; the fields it **governs** can be answered only
while the condition holds for the assignment's answer to the parent
(`app/services/responses/_branching.py`). A branch is one ruled group:
the parent's `<tbody data-new-model-rf-group data-new-model-rf-branch>`
holds the parent's row, its condition row, and every field it governs,
directly following the parent in field order. **Two levels at most**: a
governed field may itself be a parent, and its branch sits inside its
parent's, directly after it; a field two levels down can't be one ("A
branch inside a branch can't have a branch of its own.", naming the
field at the third level, on Save and in the settings CSV), and a chain
that leads back to itself is refused ("Its branch leads back to
itself."). **One branch per parent.** A field applies only while every
branch above it is open or Require.

**⑂**, just after **+**, creates a branch: outline on an Integer,
Decimal or List field with none, selected (filled, like a pressed R) on
a parent, and inactive on a String field ("A String field can't have a
branch"). A governed row shifts one column right — the bar sits in the
checkbox column, its checkbox in the **+** column, its **+** in the ⑂
column, its ⑂ in the join column, and its ↰ and ↳ in the two empty
slots after join (`td.rf-slot`) — so every row has six leading columns
and aligns from the name onward, parent and governed alike. A level-1
row's ⑂ forks it one level down ("Add a branch inside this branch,
below this field"): its condition row and fields shift one more column
right, with their own bar. A level-2 row shifts two columns: two bars,
its checkbox in the ⑂ column, its **+** in the join column, no ⑂ or ↰
(the first slot stays empty) and its ↳ in the last slot, under a
level-1 row's. In an answered branch a level-1 row's ⑂ is off, like its "+".
**A branch inside a branch is ruled** above its parent and below its
last field, from the parent's checkbox column rightward, clear of the
outer branch's bar (`tr.rf-inner-top` / `tr.rf-inner-end`); a
top-level group's rule stays full width. The checkbox sits
centered in whichever column holds it (`td.rf-active-cell`).

**The condition row** reads "If the above [operator] [value] then
[mode]", the mode a select of **Show the below** (the default) and
**Require the below (else, optional)**, which Save sends as the
parent's `branch_mode`. The operator sits in the name column at the name box's width,
with "If the above" right-aligned before it, across the columns left of
the name — the join column and both slots for a top-level condition,
one fewer a level down
(`td.rf-condition-lead`, `td.rf-condition-op`); the first
value box starts at the type column's edge. A List's operator shrinks to
its label ("is not"), and its box, the List box's width, and "then
[mode]" follow it in the operator's cell, which spans the rest of the
row (`tr.rf-condition-list`; the last cell hides). The name column cuts long
text, so the operator's tooltip gives its full label (with its symbol,
for a single-value operator) and a name box's gives its full name;
neither shows while its row is amber, whose reason comes first, and a
locked branch's reason follows the operator's label. Its own "+" adds a governed field at the top of the branch;
it has no X — the branch goes with its last governed field's X ("Delete
this field and its branch"). The operators offered follow the parent's
type. A List parent picks from `is` / `is_not` (shown "is" / "is not"),
against one option or several comma-separated, read as *any of* / *none
of*. An Integer or Decimal parent picks from ten, spelled out in the
select in this order:

| Select label | Token | Symbol |
|---|---|---|
| is equal to | `eq` | `=` |
| is not equal to | `ne` | `≠` |
| is more than (inclusive) | `ge` | `≥` |
| is more than (exclusive) | `gt` | `>` |
| is less than (inclusive) | `le` | `≤` |
| is less than (exclusive) | `lt` | `<` |
| is within (inclusive) | `in_inc` | `≤` |
| is within (exclusive) | `in_exc` | `<` |
| is outside (inclusive) | `out_inc` | `≤` |
| is outside (exclusive) | `out_exc` | `<` |

The first six take **one box**, one number. The last four — a
**range** — take **two boxes with "to" between them**. A number's boxes
are as wide as the parent row's own Min box, measured by the row script
into `--rf-condition-box` and kept in sync by a `ResizeObserver` on that
box, so a later width change (a column drag, a window resize) still
matches it; a List's box is as wide as
the parent's List box. A range takes a low and a high
number, low strictly below high. The second box shows only while the
selected operator is one of the four; switching away from a range hides
the box and clears it, keeping the low box's value
(`newModelRfSyncConditionRange`). "Inclusive" on *is outside* counts the
ends as outside: `out_inc` is the complement of `in_exc` and `out_exc` of
`in_inc`.

Operators are stored as tokens, not symbols — a settings-CSV cell
starting with `=` or `>` reads as a formula to spreadsheet software; the
builder shows the symbols, joining a range's two boxes as `low to high`
(`branch_value`; `RANGE_SEPARATOR`, `app/services/responses/_branching.py`).
An unanswered parent, or an answer that doesn't parse against the
parent's type, closes the branch.

**A condition reaches the preview like a field row commits, without a
✓**: valid, it applies at once; invalid, the condition row carries the
same amber left-edge marker a field row does (`data-row-pending`), the
reason its tooltip, and Save refuses it, naming the field. A range's own
check (mirroring `range_error`) **names the end at fault** — "The
range's low end needs a number.", "…high end needs a number.", or "The
range's low end must be below its high end." — rather than a generic
shape complaint.

**Hints show symbols, not the select's spelled-out labels.** The
preview's governed-column hint ("Opens when …", `newModelRfBranchHint`)
reads as `condition_label` does, and each operator option carries its
symbol (`data-symbol`). A single-value condition reads e.g. "Rating ≥ 4"; a range reads
the field's name first, then both ends — "Rating ≥ 2 and ≤ 4", "Rating
< 2 or > 4" — never "2 ≤ Rating ≤ 4", so a negative low end can never
start a hint (or an extract cell, `spec/extract_data.md`) as a
spreadsheet formula.

**Join (↰) and detach (↳)** sit after ⑂, sharing its width (`.rf-glyph`).
Two empty slots of that width follow a plain row's join (`td.rf-slot`);
each level of branching shifts a row one column right into them. A
level-1 row has both, ↰ before ↳.
A plain row that isn't the first, has no saved responses and isn't
itself a parent can join the unit above: the deepest unlocked branch
that ends directly above it, at that branch's level, or, on a plain
Integer, Decimal or List field, a new branch with an empty condition
(a branch inside a branch is started with ⑂, not ↰). **A level-1 row's
↰** joins the branch of the field directly above it in its own branch,
at level 2, when that field has one; otherwise it is off ("No branch inside this branch ends
directly above"), and off, as ↳ is, on a parent or in a locked branch —
which a row with saved responses always is, its answers locking it. Joining keeps the
row's **R** — Save refuses the result if the row's R is
now required with no anchor elsewhere in the instrument. A governed row
in an unlocked branch can detach (↳) one level up, to directly below
its branch; detaching the only field of a branch ends that branch, as
X does. A governed row that is itself a parent keeps its branch where
it is: its ↳ is off ("A field with a branch can't leave its branch").

**Inside a branch:**

- **R is live** on a governed row: a required governed
  field is required, and missing when empty, only while its branch is
  open for that assignment. Save and both settings-CSV phases refuse a
  visible required governed field unless the instrument has an active
  (visible) required field outside any branch, naming the field
  (`REQUIRED_GOVERNED_NEEDS_ANCHOR_MESSAGE`,
  `app/services/responses/_branching.py`) — an active required
  ungoverned field is answered at every submit, so a submit always
  leaves a response row for the reviewer rollups to count. Under a
  require-mode parent (`branch_mode = require`) every visible governed
  field counts as required governed for this rule, and each is
  answerable whatever the parent's answer and required exactly while the
  condition holds, its own R ignored (kept, so Show restores it). The
  builder grays out those rows' R, titled "Required while the condition
  holds". A hidden governed field under Require is never required, nor
  marked "*", anywhere — the reviewer surface, summary and results
  headers, and both operator rollups (`spec/operations_pages.md`)
  included — since its R can't be unticked to stop it being owed. A hidden
  governed field needs no anchor, since a hidden field counts nowhere
  on the reviewer side.
- **String is disabled** in a parent's type select. Other type changes
  keep the condition, which turns amber and is refused by Save if it no
  longer fits.
- **Deletion runs bottom-up**, at each level. A parent's X is disabled
  while it has a branch ("Delete its branch first"); the last field of a
  branch deletes that row and the branch's condition together.
- **▲ ▼ move a unit within its branch**: a governed row swaps with its
  neighbor in the same branch, carrying any branch of its own.
- **The governed-answers lock.** Once any governed field has responses,
  the condition, its mode (Require → Show would strand answers on a
  now-closed branch) and the branch's membership lock, and so do those
  of every branch above it, since changing any of them could close the
  answered field's branch —
  every governed row's X and ↳, the "+"s inside the branch, ↰ on the row
  below it, and the condition's controls. Save refuses a changed mode
  with the condition's message, and audits a mode change as
  `instrument.field_updated`, like the condition's (`branch_mode` in its
  `changes`); Show is stored null, and a branch that ends loses its
  mode with its condition. Answers on
  the parent alone lock nothing about the branch; the parent's own type
  and bounds lock as they do today (`has_responses`).
- **Active cascades both ways**, through every level below. Unticking
  a parent's Active writes `visible = False` onto every field below it,
  a branch inside its branch included; re-ticking it re-ticks them all.
- **An answered field can't move into a branch.** ↰ is off on a row
  with saved responses, and Save refuses the move, since the field's
  answers could then sit in a closed branch. Nor can a parent with
  answers anywhere below it ("Its branch has saved responses, so it
  can't move into a branch."): it would carry them in.

**Storage:** `InstrumentResponseField.branch_parent_id` (a
self-referencing FK, `ON DELETE SET NULL`) on a governed field;
`branch_op` (`String(8)`, one of the tokens above) and `branch_value`
(the number, List options comma-separated, or a range's `low to high`)
on the parent (Alembic `63b1bb107eb0`; no migration for the four range
tokens — they fit `String(8)`), and `branch_mode` (`String(8)`,
nullable: `require`, or null for Show; Alembic `c4e9a1d27b58`) on the parent. The per-field routes (edit, delete, move, insert under
`/fields/…`) refuse a branched instrument outright — each acts on one
field and can't keep a branch's rules; its fields are edited on the
instrument card only.

**The stager** sends every row's `row_key`, so a branch can name a
parent the same Save creates, plus `branch_parent` (a governed row's
parent, by row key), `branch_op` and `branch_value` (a parent's
condition) and `branch_mode` (what it does; `show` is
stored null, and an unknown mode is refused by name). Each of the four
is **independently present**, as the
state's other top-level keys are: an entry that omits one keeps what's
stored, so a caller ignorant of branching can't clear it. A hidden
parent (Active off) hides its whole branch server-side too, a branch
inside it included, and every branch
change is audited as the field's `instrument.field_updated`.

**The preview** mutes a governed column — the reviewer surface's
closed-cell styling (`spec/reviewer-surface.md`), titled "Opens when
…" — since the sample reviewee is unanswered and every branch is
therefore closed. The item count above the preview (mirroring the
reviewer surface's "*All items completed*" pill) excludes governed
fields for the same reason, and so does the "*Required items
completed*" count (`rfRowRequiredNow`): a required
governed field isn't required while its branch is closed, and the
sample row closes every branch. A Require branch's fields
follow the surface instead: their columns aren't muted, they count as
items, and they are marked "*" as fields that may be required, but the
required count leaves them out, since the unanswered sample row fails
every condition. Inside a branch, that holds only while **every**
branch above the field is Require: a Require branch inside
a Show branch is closed with it on the sample row, so its fields are
muted and not counted (`item_now` in the view, `rfRowIsItemNow` in the
row script).

**Out of scope:** a third level of branching, more than one branch per
parent, and a String parent.

### Action row

Bottom row of the card, right-aligned, in this order:

```
[Save] [Cancel] [Replicate] [Delete] [+Instrument] [+Page break] [Lock / Unlock]
```

- **Save** — only in edit mode. Starts disabled; the
  `newModelInitSaveDirtyTracking` JS helper enables it on the
  first dirty event (any Band 1 input change or Band 3 row
  edit / X / + click). With JS the Save submit is intercepted
  and fetch-POSTs the consolidated JSON `/save`; on success the
  card stays unlocked with **no
  reload** and the dirty tracker resets in place, re-disabling
  Save. The success response also carries the state the two
  setup pills are drawn from — `is_configured` for this
  instrument, and `instruments_configured` / `instrument_count`
  for the session — which the client repaints (see **Status
  pills** above), and `response_field_ids`, the saved response
  fields' ids in row order, which the client keys onto the rows
  it sent so a new field's next Save updates it instead of
  recreating it under a fresh id (and losing its column width;
  see "Response fields" above). On a 422 the summary banner
  renders with edits intact and no pill moves. **The Save is all or
  nothing:** the steps run inside `unit_of_work.single_commit`, so no
  service commits on its own — not the sort, identity or visibility
  writers, not a Band 2 pill's `update_display_field`, not the
  `validated → draft` flip — the one commit follows the last step, and
  any refusal rolls the whole request back. A 422 leaves nothing of the
  card persisted, and a `validated` session stays `validated`. The
  `/fields/save` fallback does the same.
  The `/fields/save` 303-redirect form action stays as the
  no-JS fallback. A sort spec it rejects (misaligned arrays, a
  non-integer id, or a `SortSpecError`) redirects back with
  `sort_save_error` + `sort_save_error_instrument_id`, and the page
  renders a "Could not save the sort order" banner whose Cancel
  returns to that card in edit mode (`spec/ui_elements.md` §5a).
- **Cancel** — only in edit mode. Reloads the same edit-mode
  URL to discard unsaved edits. Same dirty-aware enable
  contract as Save.
- **Replicate** — clones this instrument's contents into a new
  card slotted immediately after it. POSTs to
  `/sessions/{sid}/instruments/{iid}/replicate`. Disabled only when
  the session is not editable.
- **Delete** — destructive. Form-submit button gated on a
  delete-confirm checkbox rendered just below the row:
  *"Yes, delete **{label}** and its associated assignments
  and reviewer responses."*, where `{label}` is the same
  operator-facing handle the card title shows — `short_label`, else
  the `Instrument_{session_seq}` fallback — never a display position,
  which moves under a drag, and never `#`, which is reserved for the
  reviewer-facing heading. Disabled when
  this is the only instrument in the session, or the session is not
  editable.
- **+Instrument** — spawns a new instrument with default
  Identity, an empty Band 1, and the default response and display
  fields (see "`+Instrument` semantics" below) immediately after
  this card.
  POSTs to `/sessions/{sid}/instruments/add-new-model` with
  `after={iid}`. Same disable conditions as Replicate, and the
  only affordance that creates an instrument.
- **Lock / Unlock** — flips between view and edit mode. The anchors'
  `?editing={iid}` hrefs are the no-JS fallback; the in-page toggle
  stays on the current URL, and an in-page **Lock** strips `?editing`
  from it via `history.replaceState`, so a reload lands locked rather
  than back in edit mode. Save + Lock are independent: Save doesn't
  lock, so the operator can keep editing after a Save. Both disabled
  whenever the session is not editable — `ready`, `expired` or
  `archived`.

#### Save / Lock interaction

- An "edit lock" is enforced page-wide: at most one instrument
  may be unlocked at any time. `editing_instrument_id` (resolved
  by the view layer) names the currently unlocked card; if the URL
  asks for an instrument that fails the page-wide check, it
  silently falls back to view mode.
- **Lock-with-unsaved-edits.** When the Lock button is clicked
  on a dirty card, a `confirm()` prompt asks the operator to
  acknowledge that unsaved edits will be discarded. Declining
  cancels the navigation. **Accepting discards them**: the page
  reloads with `?editing` dropped, so the card comes back
  **locked and showing persisted state**. The discard is
  Cancel's — one shared `newModelDiscardReload`, which differs
  between the two callers only in whether `?editing` survives,
  so there is no second copy of "what the server rendered" to
  drift. **A locked card therefore never displays unsaved
  values**, which is the whole point: a lock that instead copied
  the edited values into the read-only view would leave a
  collapsed, locked card asserting state the database does not
  have.
- **Save-when-dirty.** Both Save and Cancel start disabled.
  Every editable input on the card is bound to a dirty-tracker
  that enables them on first change. On a successful JSON
  `/save` the tracker resets in place with no reload (the
  full-page redirect only happens on the no-JS `/fields/save`
  fallback). The Delete confirm checkbox (`[data-delete-confirm]`)
  is excluded from the tracker: ticking it doesn't count as an
  edit, so it neither enables Save/Cancel nor trips the leave-page
  guard below on an otherwise-clean card.
- **Leaving with a dirty card.** A page-wide `beforeunload` guard
  warns before navigating away while any card is dirty — the reason
  Replicate, Delete, +Instrument and +Page break need no lock-driven
  disable of their own: a form post from one of them is a navigation
  the guard already catches.

## Add / Replicate / Delete

### `+Instrument` semantics

- Body: `after=<instrument_id>` (optional — defaults to "append
  to end" when omitted).
- Side effects: creates a new `Instrument` row with default
  `name="instrument_{n}"` (the count of existing instruments plus
  one — an internal handle, never rendered; **not** zero-padded and
  **not** `#`-prefixed), the two locked display fields (reviewee
  Name and Email, via `ensure_locked_display_fields`), the default
  response fields from `DEFAULT_RESPONSE_FIELDS` (a required 1–5
  Integer **Rating** and an optional **Comments** long text, as on a
  new session's default instrument), NULL `rule_set_id`, NULL
  `group_kind`. Lifecycle-aware:
  - `is_draft` → succeeds, no invalidation.
  - `is_validated` → succeeds, invalidates the session back to
    `draft` (`invalidate_if_validated` emits an audit event).
  - `ready` / `expired` / `archived` → **409** via
    `_require_instrument_editable`, detail `"Instrument
    structure is locked while the session is <status>"`
    (defensive — the button is disabled in these states).
- **No assignment rows.** A new instrument starts with none, in a
  generated session as much as an empty one, and gets its pairs from the
  next Generate — assignments are only ever written by the rule engine
  (`spec/assignments.md`). Until then the Assignments page reports it as
  **not generated**, and `assignments.instrument_empty` raises it on
  Validate. It does **not** read as *stale*: staleness means
  materialised rows that have fallen out of step, and a never-generated
  instrument has none — see `spec/assignments.md` "Staleness". Adding an
  instrument does not make its siblings stale either; their pairs depend
  on their own rule and the rosters, neither of which a new instrument
  changes.

### `Replicate` semantics

Clones every field of the source instrument except the surrogate
key, the `order` slot, `session_seq` (a fresh one), `starts_new_page`,
`deadline_closed_at` and the `cached_*` columns:

- Identity: `name` gets a `" (copy)"` suffix, the source name trimmed
  so the whole fits 255 characters; `short_label` gets a `Copy of `
  prefix, the source label trimmed so the whole fits 32 characters, so
  the two cards can be told apart. A
  source with no short label gives a copy with none. `description` is
  carried as-is.
- Display fields (cloned in order).
- Response fields (cloned in order — including the inline
  bounds and the help text, and a branch: the parent's condition
  is copied and a governed field re-pointed at its parent's copy).
- Band 1's rule set — **cloned, not shared**. The copy gets its own `SessionRuleSet` row with the
  source's rules, combinator and self-review setting. Three Band 1
  writers update the pinned row in place, so a shared row would carry
  an edit to either instrument into the other.
- `group_kind` — copied as-is.
- `band1_touched_links` — copied as-is. The clone inherits the
  source's touched state; the operator doesn't have to re-click
  pills.
- `band2_state` — copied as-is.
- `starts_new_page` — **not** copied. It marks a page break before the
  instrument, a fact about position; the copy, slotted straight after
  its source, continues the source's page like any new instrument.
- `sort_display_fields`, `column_widths` — copied, re-pointed at the
  copy's own display and response fields (both name fields by id).
- `accepting_responses` — copied as-is.
- Visibility policies — copied row for row: the copy shows its responses to the same audiences,
  in the same modes, as its source. Each row goes through
  `visibility_policies.upsert_policy`, so it is checked against the
  per-cell rule and emits its own `instrument.view_policy_set`
  (`spec/visibility_policy.md` §5); a stored cell the rule rejects (a
  row imported before the rule) falls back to off, or to the cell's one
  permitted mode. Duplicate session copies each instrument's grid the
  same way (`spec/roundtrip_coverage.md`).

**Not cloned: assignment rows.** The duplicate starts with no pairs and
gets them from the next Generate, exactly as `+Instrument` does. A
duplicate carrying the source's rows would be assignments written by
something other than the engine, which `spec/assignments.md` forbids —
and the pairs it copied could already be wrong for the duplicate, since
the two instruments may differ in `group_kind`.

### `Delete` semantics

Cascade delete. Drops the `Instrument` row plus all
`InstrumentDisplayField` rows, `InstrumentResponseField` rows,
and `Assignment` rows that reference it (which in turn cascade
into `Response` rows). The cascade is ORM-level; the operator's
confirm-checkbox guard is the only friction.

The session's `SessionRuleSet` row referenced by
`Instrument.rule_set_id` is **not** deleted on instrument
delete (the FK is `ON DELETE SET NULL`). Replicate gives each copy
its own row, but a Settings CSV import that names one rule set on
several instruments pins them all to it, so the row may still be in
use; an orphaned row is left behind without harm.

The route guards against deleting the **only** instrument
(returns 400); the UI mirrors this with a disabled Delete
button + the title "Cannot delete the only instrument on this
session."

## Editing flow

The page-wide invariants the lock model enforces:

1. **At most one card unlocked at a time.** Either zero (view
   mode) or exactly one instrument is unlocked.
2. **Not-editable lock.** Whenever the session is not `draft`
   or `validated` — `ready`, `expired` or `archived` — every
   edit affordance disables and the routes behind them 409. A
   **lock card** above the instrument
   cards says which state the page is in and names that state's
   way out: `ready` and `expired` carry an inline "Revert to
   draft" form, which `revert_session_to_draft` accepts from
   both; `archived` points at the Archived-sessions lobby's
   Unarchive and offers no control, because `/revert` answers
   409 from `archived`. The lifecycle spec carries the state
   machine (`spec/lifecycle.md` §2.5, §5).
3. **Save invalidates validation.** Any successful Save on
   Bands 1 / 3 calls `lifecycle.invalidate_if_validated`. If
   the session was `validated`, it flips back to `draft` and
   the workflow card surfaces the next-action stepper from
   State 2. Band 1 Saves emit `session_rule_set.created` /
   `session_rule_set.updated` and `instrument.group_boundary_updated`;
   the invalidation records why in its reason.
4. **Save and Lock are independent.** Save persists. Lock toggles
   view mode. Lock-with-dirty fires the `confirm()` prompt.

## Validation surfaces

The Validate page (`spec/validate_page.md`) registers a number
of rules against instruments. Active ones that surface here
(see `app/services/validation.py:REGISTERED_RULES`):

- **`instruments.no_fields`** (error) — instrument has zero
  response fields.
- **`instruments.no_visible_response_fields`** (warning) — every
  response field has `visible=False`. Reviewer page would render
  empty; toggle a row's Visible checkbox.
- **`instruments.no_display_fields`** (warning) — instrument has
  zero display fields. Reviewer surface still works (Name + Email
  always render) but is sparse.
- **`instruments.stale_generated`** (warning) — the instrument's
  materialized rows have fallen out of step with what the engine
  would produce now: the pinned rule changed, or the rosters or
  relationships moved after Generate. The verdict is the engine's
  own reconcile diff — it may be served from a
  stamped cache rather than recomputed, and it agrees with what
  Generate would do under the conditions `spec/assignments.md`
  § *Staleness* states. An instrument that has never generated is
  **not** flagged. `spec/validate_page.md` §3.2 carries the full
  rule, including why.
- **`instruments.zero_included`** (warning) — every assignment row
  is excluded (`include=False`). The reviewer page would render
  zero rows even though Generate ran.
- **`instruments.no_rule_pinned`** — raises no findings: the
  synthetic Full Matrix covers a NULL `rule_set_id`, so an
  unpinned instrument is never "not set up"
  (`spec/validate_page.md` §3.2).

Note: the "Not set" pill safety gate (see
[the assignment rule](#instrument-assignment-rule--unit-of-review)) is enforced
**off-validate** — it drives the workflow card's `is_setup_empty`
state directly via `is_configured` / `has_unconfigured` rather
than emitting a `ValidationRule`. The signal surface is the
Workflow card's Setup checklist on the Workflow card right-column
status aside.

## Open / deferred

- **Bulk Band-1 templating.** Operators occasionally want
  "apply this Band 1 to every instrument in the session." Not
  surfaced; the workaround is Replicate then trim.
