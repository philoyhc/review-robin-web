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

3. **Setup UI affordances.** How does the operator (a) set
   / clear the break flag, and (b) reorder instruments?
   Three approaches that can be picked independently:
   - **Per-instrument toggle in the card header.**
     A small "Starts new page" / "Continues page N" pill
     or checkbox near the instrument title. Click-to-flip.
   - **Two add buttons at the list footer.**
     "+ Instrument" (default, continues current page) and
     "+ Instrument on new page". Doesn't help adjust
     existing instruments — needs (a) too.
   - **Drag-and-drop reordering** mirroring the display-
     field pattern (`reorder_display_fields`). Card grabs
     a handle, drops between any two siblings, JSON POST
     persists the new order. The break flag is independent
     and rides on each card.
   - **Up/down buttons or position input** as a low-JS
     fallback.

   Recommendation: drag-and-drop for reorder (consistent
   with display fields), per-instrument card toggle for
   the break flag, and **no** separate
   "+ Instrument on new page" button (the toggle on the
   freshly created card is enough; one fewer button to
   explain). Open to override.

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

## Sequencing (skeleton — fill in once decisions lock)

Tentative split, pending decisions 1 + 3:

1. **PR 1 — data model + service helpers.** Alembic
   migration for the page-break column (per decision 1);
   `reorder_instruments` + `set_page_break` service
   helpers with audit-event emission; tests at the service
   layer (no UI yet).
2. **PR 2 — operator UI: reorder.** Drag-and-drop on the
   Instruments page, mirroring the display-field pattern.
   Inline JS handler, JSON POST endpoint.
3. **PR 3 — operator UI: page-break toggle.** Per-card
   toggle in the instrument header; operator preview
   renders the resulting layout.

Sizes TBD; aim for ~200–300 LOC per PR.
