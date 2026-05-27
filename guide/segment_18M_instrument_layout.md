# Segment 18M — Operator-side instrument ordering + page breaks

> **Status: drafting (stub created 2026-05-27).** No decisions
> locked yet; no PRs yet. This stub captures the goal and the
> open decisions that need answering before the implementation
> plan can be written. Coming out of the strategic-vision
> section in `guide/segment_18L_single_page_surface.md`
> (locked 2026-05-27).
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

Lock these in the next decision round before the
implementation plan is written:

1. **Page-break persistence.** Three candidates:
   - **(a) Boolean `starts_new_page` on `instruments`.**
     First instrument's flag is ignored / forced True.
     Cheap migration (backfill False on every existing
     instrument so 18M's single-page default applies, or
     backfill True so today's one-page-per-instrument
     behaviour is preserved — see decision 2). Page N
     membership = walk in instrument order and accumulate
     until the next break.
   - **(b) Integer `page_index` on `instruments`.** Page N
     membership = all instruments with `page_index = N`.
     More rigid; re-grouping touches every later
     instrument's `page_index`.
   - **(c) Separate `pages` table** with FK from
     `instruments.page_id`. Most normalised; supports
     per-page metadata later (title, description). Heaviest
     migration.

   Recommendation: **(a)**. The break flag is a single bit
   of operator intent ("does this start a new page?") and
   the order column already orders instruments globally;
   anything heavier is premature.

2. **Backfill direction for the new column.** When the
   migration ships, existing sessions need their break flag
   set:
   - **Preserve today's behaviour** — backfill so every
     existing instrument starts a new page (matches the
     one-instrument-per-page status quo). 18L's single-page
     surface then renders existing sessions exactly as
     today's positional surface did.
   - **Match 18L's new default** — backfill so no
     instrument starts a new page (every existing session
     collapses to one long page). Operators with multi-
     instrument sessions would need to re-mark their
     breaks if they wanted today's pagination back.

   Recommendation: **preserve today's behaviour**. Existing
   live sessions shouldn't change layout under the
   operator's feet on deploy.

3. **Setup UI affordances.** Locked decision 1 fixes the
   chrome (collapsible `<details>` cards, all-collapsed
   default, bulk Expand/Collapse). Still to lock inside
   that chrome:
   - **Reorder mechanism.** Drag-and-drop on the
     `<summary>` handle (mirrors the display-field
     pattern) vs. up/down buttons as a low-JS fallback
     vs. both.
   - **Page-break flag UI.** Per-card toggle in the
     `<summary>` (visible even when the card is
     collapsed, so the operator can see page structure at
     a glance) vs. inside the `<details>` body (cleaner
     summary, but invisible until expanded).
   - **Add-instrument flow.** Single "+ Instrument" at
     the list footer (defaults to continues-current-page,
     operator flips the break on the freshly created
     card) vs. two buttons ("+ Instrument" /
     "+ Instrument on new page") for one-click intent
     capture.

   Recommendation: drag-and-drop (consistent with display
   fields), break toggle in the `<summary>` so page
   structure is legible without expanding cards, and a
   single "+ Instrument" button (the toggle on the new
   card is one extra click and avoids two-button
   explanation). Open to override.

4. **Page break UI on the reviewer-side preview.** The
   operator preview at
   `app/web/routes_reviewer/_preview.py` reuses the same
   template as the reviewer surface. Does the operator
   preview also render page breaks (i.e. 18L's
   single-page-with-`<hr>` layout), or does it always
   render every instrument stacked regardless of breaks?

   Recommendation: render breaks. The preview's value is
   showing what reviewers see; suppressing breaks defeats
   that.

5. **Lifecycle gate.** Reordering + break-flag edits join
   the existing instrument-edit lock surface
   (`_require_instrument_editable`). Confirm both new
   operations 403 once the session is activated, same as
   today's instrument adds / deletes / display-field
   edits.

   Recommendation: yes — same lifecycle as today's
   instrument edits.

6. **Audit events.** Two new mutating operations need
   audit-event registration in `EVENT_SCHEMAS`:
   - `instruments.reordered` — `detail.changes` with the
     ordered id list before / after, or
     `detail.set_changes` per-instrument-position. Match
     the shape of `display_fields.reordered` if one
     exists; otherwise pick the closest existing reorder
     emitter and mirror it.
   - `instrument.page_break_set` (or `.cleared`) — one
     event per flip; `detail.changes` with the boolean.

   Recommendation: defer the exact envelope choice to the
   implementation PR; just earmark both event_types here
   so the strict-mode test gate isn't a surprise.

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

0. **PR 0 — Collapsible instrument cards (standalone).**
   Wrap each `<section class="instrument-card">` (or the
   equivalent host element) in
   `<details class="instrument-card" open>` / `<summary>`,
   with the `<summary>` carrying `Instrument #{loop.index}`
   + the two existing status pills + a top-right corner
   per-card toggle button (chevron / caret icon, rotates
   via the `details[open] summary .toggle-icon` CSS
   selector — no JS). Server-render every card with
   `<details>` **without** the `open` attribute so the
   default state is all-collapsed; a single inline
   `<noscript>`-friendly toggle is enough. Add the bulk
   "Expand all instruments" / "Collapse all instruments"
   buttons in the existing Status + bulk-actions card,
   inline immediately before the "Show / hide all when
   closed" toggle; ~5 lines of inline JS iterate
   `document.querySelectorAll('details.instrument-card')`
   and set `.open = true | false`.

   No data-model change, no migration, no route change, no
   service helper, no reviewer-side touch. CSS additions
   live in `base.html`. Tests: integration smoke that
   asserts the rendered page contains `<details
   class="instrument-card">` per instrument with the
   summary holding the title + both pills, and that the
   bulk-action buttons render with the right labels.

   This PR is **independent** of the rest of 18M — if PRs
   1-3 below get postponed indefinitely, PR 0 still pays
   its own way on the page.

1. **PR 1 — data model + service helpers.** Alembic
   migration for the page-break column (per decision 1);
   `reorder_instruments` + `set_page_break` service
   helpers with audit-event emission; tests at the service
   layer (no UI yet). Pending the persistence decision.
2. **PR 2 — operator UI: reorder.** Drag-and-drop on the
   Instruments page, mirroring the display-field pattern.
   Inline JS handler, JSON POST endpoint. Drag handle
   lands in the slot PR 0 reserved inside `<summary>`.
3. **PR 3 — operator UI: page-break toggle.** Per-card
   toggle in the instrument `<summary>` (so page
   structure is legible without expanding cards);
   operator preview renders the resulting layout.

Sizes TBD for PRs 1-3; aim for ~200–300 LOC per PR. PR 0
is the smallest of the four (template + CSS + ~5 lines of
JS + a smoke test — probably <150 LOC).
