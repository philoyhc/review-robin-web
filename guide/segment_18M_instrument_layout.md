# Segment 18M — Operator-side instrument ordering + page breaks

> **Status: PRs 0 + 1 shipped (2026-05-27); PR 2 in
> flight.** Decisions 1–9 locked. PR 0 shipped the
> collapsible-card chrome (native `<details>` /
> `<summary>`, all-collapsed default, bulk Expand/Collapse,
> drag-handle placeholder, short-label on summary). PR 1
> shipped the data-model + service-layer half: Alembic
> migration `e5c1a3b9d472` adds `Instrument.starts_new_page`
> (backfill TRUE on existing rows, default FALSE for new
> rows); service helpers `reorder_instruments` /
> `create_page_break_after` / `clear_page_break` enforce
> the three reorder invariants and emit three new audit
> event types (`instruments.reordered`,
> `instrument.page_break_set`, `instrument.page_break_cleared`).
> PR 2 (operator UI — drag-and-drop reorder + page-break
> cards + per-card +Instrument / +Page break buttons) is
> the current focus.
>
> **Predecessors.** Segment 13D / Wave 5 collapsed the
> instrument card model into a single new-model card; Segment
> 13B PR 5 wired drag-to-reorder for *display fields* inside
> an instrument (the JSON ``ordered_ids`` POST pattern lives
> in `app/web/routes_operator/_instruments.py:974`+). 18L's
> strategic vision (this file's sibling) locks the reviewer-
> side defaults that this segment's operator UX feeds into.
>
> **Sibling.** 18L owns the **reviewer-side** rendering work:
> single-page default, anchor nav, audit. 18M owns the
> **operator-side** affordances: reordering instruments and
> setting / clearing page breaks. The two segments can ship
> independently — 18L's reviewer surface honours the
> page-break flag even when the only way to set it is
> programmatic fixtures, and 18M's UX can land first against
> the legacy paginated surface if scheduling demands it.

## Goal

Give the operator two new capabilities on the Setup →
Instruments page that today's append-only model lacks:

1. **Arbitrary reordering.** Move any instrument to any
   position in the session's instrument list. Today the
   only order primitive is creation order; deletes shift
   later instruments up by one, but operators can't promote
   instrument C ahead of A and B once all three exist.
2. **Page break control.** Mark whether each instrument
   starts a new page on the reviewer surface, or stacks
   onto the previous instrument's page. Default for new
   instruments is **stack** (matching 18L's single-page
   baseline); operators opt into a break per instrument.

These are the two operator-side primitives 18L's strategic
vision named. The reviewer surface inherits whatever layout
the operator chose: zero breaks → one long page; breaks →
operator-defined groups.

## Why now (and why a separate segment from 18L)

The reviewer-side refactor (18L) and the operator-side
affordances (18M) touch different surfaces, different code
seams, and different user flows:

- 18L: `app/web/routes_reviewer/_surface.py`,
  `templates/reviewer/review_surface.html`,
  view-shape adapters in `app/web/views/_instruments.py`,
  audit-event schema.
- 18M: `app/web/routes_operator/_instruments.py`,
  `templates/operator/instruments_index.html`,
  `app/services/instruments/_instrument_crud.py`,
  Alembic migration for the new column(s), and possibly a
  service-layer reorder helper alongside the existing
  `reorder_display_fields`.

Bundling them would land one PR with reviewer-side template
edits, operator-side template edits, a migration, two
service helpers, and tests across both surfaces — too wide
to review in a single sitting. Splitting at the segment
boundary keeps each PR set focused.

## Where the surface lives today

- **Operator Instruments page.** `routes_operator/_instruments.py`
  + `templates/operator/instruments_index.html`. The current
  add-instrument flow accepts an `after_instrument_id` form
  field that positions the new instrument after a specific
  predecessor (line 711, 734), so the underlying
  `instruments_service.create_instrument` already supports
  insertion at a non-tail position — what's missing is the
  UX surface that drives it from the operator's intent
  (drag, up/down buttons, position input).
- **Reorder precedent.** `instruments_service.reorder_display_fields`
  + the matching JSON `ordered_ids` route at
  `_instruments.py:974` show the pattern this segment will
  mirror for *instruments themselves*. The display-field
  reorder JS lives inline in `instruments_index.html`; a
  similar handler would drive the instrument-level reorder.
- **Order column.** `Instrument.order` already exists
  (`app/db/models/instrument.py:31` — `Integer, default=0,
  nullable=False`), and queries already sort
  `Instrument.order, Instrument.id`. So the reorder
  primitive can land without a new column — just a service
  helper that updates `order` values plus the operator-side
  drag handler.
- **No page-break column yet.** Adding the page-break
  primitive is the only schema change in 18M's scope; the
  exact column shape is in "Open decisions" below.

## Locked decisions

1. **Collapsible instrument cards on the Setup →
   Instruments page** (locked 2026-05-27). Drag-and-drop
   reordering is much more usable when every card can be
   shrunk to a header-only handle, and collapsing pays its
   own way on the page even before reorder / page-breaks
   land — so collapse ships as **PR 0** of this segment
   (independent of every other piece of 18M).
   - **Mechanism: native `<details>` / `<summary>`.** No
     localStorage, no DB column. Free keyboard +
     screen-reader behaviour. Card chrome (border, padding,
     spacing) comes from CSS in `base.html`; the
     `<summary>` carries the per-card affordances. The full
     per-instrument editor card body lives inside the
     `<details>` and collapses on `<summary>` click.
   - **What renders in the collapsed `<summary>`:**
     - **Title:** `Instrument #{loop.index}` — same string
       `spec/instruments.md:169` already specifies for the
       Identity heading. Numeric index, not DB id; shifts on
       replicate / delete (and post-PR-2, on reorder).
     - **Status pills:** the existing
       `accepting responses` / `not accepting responses`
       pill and the
       `showing when closed` / `not showing when closed`
       pill (per `spec/instruments.md:172-176`).
       Both visible without expanding the card.
     - **Per-card expand/collapse affordance:** a small
       button in the **top-right corner** of the
       `<summary>`. With native `<details>`, clicking
       anywhere on `<summary>` toggles open; the explicit
       button is a discoverability + visual cue, not a
       second mechanism. CSS rotates the chevron / flips
       the icon based on the parent `<details>[open]`
       selector — no JS for the per-card toggle.
   - **Default state: all collapsed.** Encourages a
     reorder-first / edit-second workflow and keeps the
     page from being a vertical wall when an operator has
     5+ instruments. Single-instrument sessions still feel
     fine — one click to open.
   - **Bulk controls: "Expand all instruments" /
     "Collapse all instruments" in the existing
     Status + bulk-actions card** — inline, immediately
     before the existing "Show / hide all when closed"
     toggle (per `spec/instruments.md:113-126`). ~5 lines
     of inline JS that iterates the `<details>` elements
     and toggles `open`; per-card toggle stays pure HTML.
     No state persistence across refresh — a refresh
     restores the all-collapsed default.
   - **Drag interaction (future PR 2, not PR 0).** A
     collapsed card drags by its `<summary>` header
     (smaller target = less scroll-while-dragging pain).
     The drag handle lands inside `<summary>` alongside
     the title + pills + per-card toggle button. PR 0
     reserves a stable position for the drag handle in
     the `<summary>` markup so PR 2 only adds JS + a
     handle icon, not a layout shuffle.

## Open decisions

_(none — all locked below; see decisions 2–9.)_

2. **Page-break persistence: boolean `starts_new_page` on
   `instruments`** (locked 2026-05-27). Cheapest migration
   (one boolean column); the constraints from decision 4
   below fall out as schema invariants without extra
   validation code. Considered + rejected:
   - Integer `page_index` per instrument — heavier
     re-grouping cost on reorder, no real benefit at this
     scale.
   - Separate `pages` table with FK from
     `instruments.page_id` — most normalised but the only
     thing it buys (per-page metadata: title, description)
     is explicitly out of scope (see "Out of scope" below);
     premature.

   The flag carries the meaning *"this instrument starts a
   new page"* — i.e. a page break exists between this
   instrument and the one before it. At render time the
   flag is **meaningful only for instruments at position
   ≥ 2**; the value on the first instrument is ignored.

3. **Backfill direction: preserve today's behaviour**
   (locked 2026-05-27). The migration sets
   `starts_new_page = true` on every existing instrument so
   today's one-instrument-per-page reviewer surface is
   visually unchanged on deploy. Operators who later want a
   single-page layout can delete breaks individually.
   Existing live sessions don't change layout under the
   operator's feet on rollout.

4. **Page break = list-item model + three reorder
   invariants** (locked 2026-05-27). The operator's mental
   model and the drag-handler algorithm treat the page
   break card as a real item in an ordered list of mixed
   instrument-and-break items. Persistence stays the flag
   from decision 2; the algorithm reconciles the two
   views.

   - **Non-movable breaks.** Page break cards can be
     created and deleted only — they don't drag. Creating
     a break is a single button click (set the flag to
     true); deleting one is an inline `×` on the break
     card (set the flag to false). Dragging an instrument
     across a break works fine (see "Reorder algorithm"
     below) but the break itself stays put visually.

   - **Three invariants on every reorder.** Reordering an
     instrument is forbidden if the resulting arrangement
     would violate any of:
     - (a) **No leading page break** — a break before all
       instruments.
     - (b) **No trailing page break** — a break after all
       instruments.
     - (c) **No double-stacked breaks** — two breaks
       adjacent in the rendered list.

     The user-facing rule "the first instrument is
     immovable when followed by a page break" is just
     (a) — moving it would leave the break with nothing
     before it.

     The drag handler simulates the post-drop arrangement
     before applying it; invalid drops snap back. UI
     hints (greyed drop-targets, inline reasons) are an
     implementation choice for the operator-UI PR.

   - **Reorder algorithm** (canonical, applied on every
     reorder + every delete):
     1. Compute the new rendered list (mixed instruments
        and breaks) per the drag result.
     2. Validate (a) + (b) + (c). Reject if any fail.
     3. **Re-derive flags from the new list order**:
        walk the list; the instrument *after* each break
        gets `starts_new_page = true`; every other
        instrument gets `false`.
     4. Persist the new instrument `order` values + the
        re-derived flags in one transaction.

     This guarantees the DB never holds a flag that means
     a leading break (position-1 flag never set), because
     step 3 derives flags from a list that already passed
     step 2.

   - **Per-card add buttons + their disabled states.**
     Each per-instrument card carries two buttons in its
     body footer (inside the `<details>`, not the
     `<summary>`):
     - `+ Instrument` — creates a new instrument
       immediately after this card. Always enabled.
     - `+ Page break` — creates a break immediately after
       this card (sets `starts_new_page = true` on the
       next instrument). **Disabled** when:
       - This is the last instrument (no successor to
         flag — would create a trailing break, invariant
         (b)).
       - The next instrument already has
         `starts_new_page = true` (would double-stack,
         invariant (c)).
     Disabled buttons keep their position so the layout
     doesn't shuffle; a tooltip / `title` attribute
     explains why.

   - **Global `+ Instrument` button at the bottom of the
     list.** Retained — per-card buttons live inside the
     collapsed `<details>` bodies (from locked decision
     1) and aren't visible until the card is expanded.
     The global button is the no-expand-required
     append-to-end affordance. Per-card buttons handle
     "insert next to this specific instrument".

   - **First-instrument seed.** Existing Setup flow
     already seeds one instrument by default on session
     creation, so the operator never sees a zero-
     instrument state. No additional bootstrap UI is
     needed; the global `+ Instrument` button + per-card
     buttons cover every flow from one instrument onward.

   - **Delete behaviour.** Deleting an instrument removes
     it + its `starts_new_page` flag. Run the reorder
     algorithm's step 3 (re-derive flags) afterward so
     that an instrument elevated to position 1 by the
     delete doesn't keep a now-meaningless flag.
     Invariants stay enforced.

5. **Setup UI affordances** (locked 2026-05-27, building
   on decisions 1 + 4):
   - **Reorder:** drag-and-drop on the per-instrument
     card `<summary>` handle, mirroring the
     `reorder_display_fields` pattern. JSON POST endpoint
     accepts the new ordered list of (instrument-id |
     break-marker) items; the service runs the reorder
     algorithm (decision 4).
   - **Page-break creation / deletion:** `+ Page break`
     button in the per-instrument card body (decision 4);
     `×` button inline on each rendered break card.
     No drag, no per-card toggle pill in the `<summary>`.
   - **Page break card visual:** rendered as a thin
     horizontal divider with `Page break` text centred
     and a small `×` on the right (delete-in-place).
     Sits between the cards it separates in document
     order; visually distinct from instrument cards.
   - **Add-instrument flow:** per-card `+ Instrument`
     button creates an instrument immediately after the
     card it sits on; global `+ Instrument` at the
     bottom of the list appends to the end. No
     `+ Instrument on new page` button — operators add
     an instrument and a page break separately.

6. **Operator preview renders page breaks** (locked
   2026-05-27). The operator-side preview at
   `app/web/routes_reviewer/_preview.py` honours the same
   break flag the reviewer surface does — the preview's
   value is showing what reviewers see; suppressing
   breaks defeats that.

7. **Lifecycle gate: same as today's instrument edits**
   (locked 2026-05-27). Reorder + page-break create /
   delete operations join `_require_instrument_editable`
   and 403 once the session is activated, matching adds /
   deletes / display-field edits today.

8. **Audit events** (event_types locked; envelope shapes
   deferred to implementation PR):
   - `instruments.reordered` — emitted once per reorder
     transaction, after step 4 of the algorithm. Detail
     payload mirrors the shape of the closest existing
     reorder emitter (likely `display_fields.reordered`).
   - `instrument.page_break_set` / `instrument.page_break_cleared`
     (two event types, or a single
     `instrument.page_break_changed` carrying the
     before / after values — implementation PR picks).
     Emitted on every flag flip, including the implicit
     flips inside step 3 of the reorder algorithm.

   Both must register in `EVENT_SCHEMAS` in the same PR
   that adds the emitter or the strict-mode test gate
   rejects them.

9. **Edit-locked instrument carve-out** (locked
   2026-05-27). An instrument the operator has locked
   for editing (Wave 4 Save / Lock state) participates
   in reorder + create-break operations on the surface
   but the lock card stays inside the per-instrument
   `<details>` body and is the only writeable surface
   for that instrument's own contents. Reorder /
   break-create move the card around; they don't open
   it. Symmetrical with how display-field reorder
   behaves on a locked instrument today.

## Out of scope

- **Per-page metadata** (title, description, custom page
  ordering separate from instrument ordering). 18M keeps
  pages as derived state: page N = the run of instruments
  between break N and break N+1. If operators later want
  named pages, that's a follow-up that moves to model (c).
- **Reviewer-side URL contract.** 18L owns the URL shape.
  18M just persists the break flag; how the reviewer
  surface routes by page is 18L's call.
- **Migration of legacy URLs.** Any positional URL shim
  decisions belong in 18L. 18M's reviewer-preview reads
  the break flag and renders; it doesn't define routes.
- **Bulk reorder import.** No "paste an order list" CSV /
  JSON import. Drag + click are enough.

## Cross-refs

- `app/db/models/instrument.py` — already carries the
  `order` column. Page-break column to be added; exact
  shape pending decision 1.
- `app/web/routes_operator/_instruments.py` — host file
  for the new POST endpoints (instrument reorder, page-
  break flip).
- `app/web/templates/operator/instruments_index.html` —
  host template for the new affordances (per-card toggle,
  drag handle).
- `app/services/instruments/_instrument_crud.py` — host
  module for `reorder_instruments` + `set_page_break`
  helpers; mirror the shape of
  `instruments.reorder_display_fields`.
- `app/services/instruments/_state.py` — likely host for
  the helper that walks instruments in order and returns
  page groupings, since 18L's reviewer-side renderer will
  consume it.
- `guide/segment_18L_single_page_surface.md` — strategic
  vision section is the joint reference for both
  segments. 18L's reviewer-side rendering depends on the
  break-flag column 18M ships.
- `spec/instruments.md` — patch once the data model
  lands. Add the page-break section.
- `spec/operator_ui_concept.md` — patch once the Setup
  UI lands. Add the per-card toggle + drag handle to the
  Instruments operator-page surface description.

## Sequencing

0. **PR 0 — Collapsible instrument cards (shipped
   2026-05-27).** Wrapped each per-instrument card body in
   `<details class="instrument-card-collapsible">` /
   `<summary class="instrument-card-summary">` (#1498). The
   `<summary>` carries: drag-handle placeholder (left
   edge), `Instrument #{loop.index}`, optional
   `<short_label>`, the two status pills, and the chevron
   toggle icon. CSS rotates the chevron via
   `details[open] summary .instrument-card-toggle-icon`
   (no JS for the per-card toggle). Default state
   collapsed; auto-opens when `is_editing` or `was_saved`
   so an active edit / fresh save never lands hidden.
   Bulk Expand all / Collapse all buttons inline before
   the existing "Show / hide all when closed" toggle in
   the Status + bulk-actions card; a single inline IIFE
   iterates `details.instrument-card-collapsible` and
   flips `.open`. The same IIFE wires `#instrument-{id}`
   deep-link auto-open on initial load + `hashchange`.

   Shipped over PRs #1496 (placeholders), #1498 (wiring),
   #1499 (short_label + chevron polish), #1500 (drag-
   handle placeholder), #1501–#1503 (vertical alignment
   passes), #1504 (smoke tests at
   `tests/integration/test_instruments_index_collapsible.py`
   that lock the structural contract).

1. **PR 1 — data model + service helpers (shipped
   2026-05-27).** Alembic revision `e5c1a3b9d472` added
   `instruments.starts_new_page Boolean NOT NULL`,
   backfilled every existing instrument to TRUE (locked
   decision 3) then flipped DB-level `server_default` to
   FALSE so post-migration inserts default to "continue
   current page". Model carries `default=False`. Service
   helpers in `app/services/instruments/_instrument_crud.py`:
   - `reorder_instruments(db, *, review_session, items:
     list[int | None], actor)` — items is the mixed
     visual list (None marks page break). Validates the
     three invariants + id membership, re-derives flags
     from list position, persists order + flags + emits
     one combined `instruments.reordered` audit event,
     short-circuits on no-op.
   - `create_page_break_after(db, *, instrument, actor)`
     — flips successor's flag to True; rejects trailing /
     double-stack. Emits `instrument.page_break_set` with
     `anchor_instrument_id` ref.
   - `clear_page_break(db, *, instrument, actor)` —
     rejects if no break. Emits
     `instrument.page_break_cleared`.

   All three call `lifecycle.invalidate_if_validated`.
   Three event types registered in `EVENT_SCHEMAS`.
   18-case integration tests at
   `tests/integration/test_instrument_reorder_and_breaks.py`.
   Shipped in PR #1505.
2. **PR 2 — operator UI: reorder + page-break cards.**
   Drag-and-drop on the per-instrument `<summary>`
   handle (the slot PR 0 reserved inside `<summary>`),
   mirroring `reorder_display_fields` JS shape. Renders
   page break cards between instruments. Wires per-card
   `+ Instrument` / `+ Page break` buttons (with their
   disabled states from decision 4) and the inline `×`
   on each break card.
3. **PR 3 — wire the collapse machinery + reviewer
   preview.** Wraps each instrument card in
   `<details>` / `<summary>` (the markup PR 0 placeholder
   buttons live in) so the all-collapsed default kicks
   in; activates the bulk Expand / Collapse buttons via
   the inline JS from decision 1. Operator preview at
   `app/web/routes_reviewer/_preview.py` honours the
   break flag (decision 6) so the operator sees the
   reviewer layout.

Sizes TBD for PRs 1-3; aim for ~200–300 LOC per PR. PR 0
shipped at ~50 LOC (template-only placeholders, no
behaviour). PR 1 is the largest of the four (migration +
three service helpers + invariant tests).

### Sequencing notes

- **PR 1 can land independently of PR 2 and PR 3.** The
  reviewer surface for 18L can read `starts_new_page`
  from PR 1 even without operator UI, using test
  fixtures or programmatic flag setting. Don't block
  18L on 18M PR 2.
- **PR 2 depends on PR 1.** No reorder UI without the
  service helpers + audit emitter.
- **PR 3 depends on PR 0 (already shipped) and PR 2.**
  The placeholder buttons need wiring + the operator
  preview needs the break-flag column to read from.
