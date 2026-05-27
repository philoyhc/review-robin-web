# Segment 18L — Multi-page reviewer surface (operator-defined)

> **Status: PRs 1a + 1b + replan + 1b-revised + 1c + 1d shipped
> (2026-05-27).** Only PR 2 (per-instrument heading-state card)
> remains. The reviewer surface paginates by
> operator-defined pages, each rendered at its own URL.
> Initial decisions were locked 2026-05-27 around a
> single-page-all-instruments model; mid-implementation the
> user clarified that 18M's strategic vision called for true
> multi-page navigation with operator-defined boundaries.
> Decisions 5 + 8 below were reversed in the replan; the
> "Goal" + "What changes" sections were rewritten. The work
> shipped in PR 1b (single-page-render-of-multiple-
> instruments-within-a-page) is reused as the intra-page
> render; cross-page navigation goes back to real URL changes
> (PR #1522).
>
> **Predecessors.** Segment 17B Phase 2 wired the participation-
> summary capstone page; Segment 18J shipped column widths and
> per-cell visibility; Segment 18K closed the reviewer-side
> per-field visibility filter on the summary HTML + CSV. The
> reviewer-side visibility audit (`guide/visibility_audit.md`)
> stays the reference for what each route renders in each
> lifecycle state.

## Strategic vision (locked 2026-05-27)

Today's instrument editing surface is rigid in two ways that
shape every downstream decision in this segment:

1. **Append-only ordering.** New instruments are created
   one after another in creation order. Deleting an
   instrument shifts every later instrument up by one slot;
   there is no operator-driven way to put instrument B
   ahead of instrument A once both exist.
2. **One instrument = one page.** The reviewer surface
   paginates per instrument with no operator choice — every
   instrument carries its own URL, its own action row, and
   its own scroll context, regardless of whether two short
   instruments would read better stacked.

Segment 18L unblocks both by establishing two strategic
capabilities the operator gains over the instrument layout:

- **A. Arbitrary reordering.** The operator can move any
  instrument to any position in the Setup → Instruments
  list. Deletes still shift later instruments up; the new
  primitive is *explicit* reordering (drag, up/down
  buttons, or position input — UI mechanism deferred to
  the implementation decision in PR scope).
- **B. Operator-controlled page breaks.** Each instrument
  carries a flag determining whether it starts a new page
  on the reviewer surface or stacks onto the previous
  instrument's page. The default is "stack" — every new
  instrument lives on the same page as its predecessor
  unless the operator opts into a break. The 18L baseline
  ("single-page-all-instruments") is the natural state
  when no operator has set any breaks; multi-page sessions
  emerge from explicit break flags.

Together these capabilities turn the instrument list from
a fixed-order append-only stack into an arrangeable layout
the operator owns. The reviewer surface inherits whatever
page structure the operator chose: zero breaks → one long
page (the 18L default); breaks → operator-defined groups
of instruments per page.

### Why both belong in the same vision

Reordering without page breaks would still leave every
instrument on its own page, with operator choice limited to
"which order do reviewers see them in". Page breaks without
reordering would let operators carve pages but not arrange
their contents. Together they cover the full surface
("what's on each page, in what order"); separately each
solves half the problem.

### What 18L locks vs. defers

- **Locks (this segment).** The data model carrying the
  page-break flag; the reviewer surface rendering that
  honours it; the canonical single-page URL contract
  (`/reviewer/sessions/{id}` when there's one page;
  `/reviewer/sessions/{id}/{page_position}` when there's
  more than one — exact shape pending the URL decision in
  the next round); the action row + #N anchor nav inside
  whichever page is currently rendering.
- **Defers (follow-up segment).** The operator UI for
  setting / clearing the page-break flag and reordering
  instruments. 18L's reviewer-side work stands on its own
  even when the only way to set the break flag is
  programmatically (test fixtures, future seed scripts);
  the operator UI is its own slice of work and can ship
  without forcing the reviewer surface to wait.

This split is deliberate. The reviewer-side refactor (this
segment's body) is mostly self-contained: routing,
templating, view-shape, audit, test sweep. The operator-
side reordering + page-break controls are a sibling effort
that touches a different surface (Setup → Instruments),
has its own affordances (drag-and-drop, per-card toggles),
and is best reviewed on its own merits.

## Goal

Replace the per-instrument pagination
(`GET /reviewer/sessions/{id}/{position}` where each
instrument was its own page) with **operator-defined
pagination** — each page is a group of one or more
instruments that the operator chose to keep together
(carved by Segment 18M's `Instrument.starts_new_page`
flag). URL shape stays positional:
`GET /reviewer/sessions/{id}/{N}`, N is the 1-based page
number. Bare `/reviewer/sessions/{id}` 303s to `/{id}/1`.

Within a page, instruments stack vertically without an
inter-instrument separator. The action row (Save / Submit
| #1 short_label, #2 …) renders above every instrument
heading on the current page plus once at the bottom with
the danger zone (Clear / Recall). The `#N` buttons remain
in-page anchor TOC — they jump within the current page,
**not** across pages. Cross-page navigation lives in a
separate Prev / Next row at the top + bottom of each page.

Mid-implementation note (2026-05-27): an initial draft
locked this segment around a single-page-all-instruments
view (no pagination of any kind). The user clarified that
18M's strategic vision (locked 2026-05-27, see below)
intended true multi-page navigation with operator-defined
boundaries. The "Goal" + "Decisions 5 + 8" + "What changes"
sections were rewritten around that intent; PR 1b's work
shipped + got reshaped as the intra-page render, and PR
#1522 layered URL pagination on top.

The reviewer-summary page (`/sessions/{id}/summary`) is
unaffected — it already aggregates across instruments. This
segment is exclusively about the editable surface.

## Decisions (locked 2026-05-27)

1. **Perf — not gated.** Pagination was originally an escape
   valve for large rosters × many instruments. The pilot
   ceiling is ~100 rows per instrument with typical
   instruments at 5–10 rows; no review should ever ship with
   3000 required entries even if paginated. We don't need
   pagination as a perf control.
2. **No sticky action row.** The action row above each
   instrument heading + at the bottom gives enough density.
   A sticky bar is overkill at this stage; revisit only if
   pilot feedback flags scroll fatigue.
3. **Per-instrument heading-row state goes into a half-width
   card to the right of the per-instrument title card.** The
   existing `.rs-intro-grid` already has a 2-column shape
   with column 1 carrying the title and column 2 empty —
   column 2 becomes the new home for the heading-row pills /
   "Not accepting" banner that today renders page-wide above
   the table. Each instrument carries its own state pair
   side-by-side with its own heading. **Column 2 stays empty
   when an instrument is fully open (accepting=True, no
   closed-with-hidden case)** — no neutral pill, no extra
   chrome on the common path.
4. **Consolidated Save emits one `responses.saved` audit row
   per call**, mirroring the Submit envelope:
   `detail.counts.assignments_touched` +
   `detail.counts.responses_saved`. Update `EVENT_SCHEMAS` in
   the same PR that lands the endpoint, or the strict-mode
   test gate will reject the new shape.
5. **Submit / Recall / Clear redirect to the bare URL**
   `/reviewer/sessions/{id}` (which 303s on to `/1`). The
   rollup pill at the top of `.rs-status-panel` is the
   session-level result confirmation. The original lock
   here said "stop reading `current_position` from the
   form payload"; the multi-page replan brought it back —
   Save POSTs to `/sessions/{id}/{N}/save` (the URL slot
   carries the page number, no form field needed).
6. **Each instrument emits `id="instrument-{id}"`** so the
   intra-page anchor TOC + future summary "Edit"
   affordances can deep-link. Combined with the wrapper
   div from PR #1520, the anchor jump lands above the
   per-instrument action row so the operator's Save /
   Submit controls are visible at the top of the
   viewport on arrival.
7. **Legacy positional URLs are the canonical URLs again
   post-replan.** The original lock here was about
   retiring shims that translated `/sessions/{id}/{N}` →
   `/sessions/{id}#instrument-{id}`. The multi-page replan
   makes `/sessions/{id}/{N}` the canonical render again,
   just indexed by page number instead of instrument
   position. No shims, no retirement.
8. **`PageButton` is repurposed as an in-page anchor TOC
   scoped to the current page** (revised in replan). The
   dataclass + helper stay; semantics:
   - `href` is `#instrument-{id}` (matching Decision 6's
     anchor ids).
   - Label format is `#N short_label` (e.g. `#2 Reviewers`).
     `"Page"` retired — `#N` carries the positional cue.
   - `is_current` drops from the dataclass; no button
     renders disabled.
   - **Replan correction:** the original lock placed every
     instrument's `#N` button in the action row regardless
     of which page was rendered. The multi-page replan
     filters `page_buttons` server-side to instruments on
     the **current page only**. Cross-page navigation
     lives in a separate **Prev / Next row** at the top +
     bottom of each page, not in the action row.
   - Placement: every action row carries
     `Save / Discard / Submit | #1 short_label,
     #2 short_label, …` for the CURRENT PAGE's
     instruments, and the row interleaves above every
     instrument heading. The bottom action row (flush-
     right, under the last instrument's table) carries the
     same set of buttons, followed by the Danger Zone on
     the next row.
9. **Multi-page navigation (post-replan).** Cross-page
   navigation is a separate row with three slots:
   `< Previous page` (only when `current_page_n > 1`) |
   `Page N of M` counter (centred) |
   `Next page >` (only when `current_page_n < page_count`).
   Rendered at the top + bottom of the form when
   `page_count > 1`; suppressed entirely on single-page
   sessions. Real `<a href="/sessions/{id}/{N±1}">`
   navigation — server-side render of the targeted page.
   Unsaved typing on the current page is **lost
   silently** when the operator clicks Prev/Next without
   saving first (matching pre-18L behaviour minus the
   client-side preservation JS that we deleted).

## Where pagination lives today (the diff surface)

- **URL.** `GET /reviewer/sessions/{id}/{position}` is the
  only render endpoint; `/sessions/{id}` 303s to `/1`
  (`routes_reviewer/_surface.py:782`).
- **Per-page form state.** The form's `action` is
  `/{position}/save` with a `current_position` hidden input;
  the template wraps every instrument in
  `.rs-instrument-group` inside `.rs-paginated`, and the
  base-CSS rule `.rs-paginated > .rs-instrument-group:not(.rs-active)`
  hides every non-current group.
- **Pagination JS.** ~70 lines of inline JS in
  `review_surface.html` handle Page-#N click toggling
  `.rs-active`, `history.pushState` URL sync, popstate
  handling, and dirty-confirm before page switch.
- **Save granularity.** Each `/{position}/save` POST writes
  that instrument's responses only. Submit / Recall / Clear
  already act session-wide.
- **Heading-row banner.** The "no longer accepting
  responses" banner sits in the page-wide
  `.rs-status-panel` (`review_surface.html:47-58`) and fires
  once per page load when `not any_accepting`. With multiple
  instruments visible simultaneously, accepting-state is
  per-instrument; the banner needs to move per-instrument
  too — which is Decision 3.

## What changes

> **Post-replan note (2026-05-27, PR #1522).** This whole
> section was originally written around the single-page-
> all-instruments model. PR #1522 reversed that into the
> multi-page model described in the Goal above. The
> subsections below are the original locked plan kept for
> historical context — read the "Sequencing" section
> below for what actually shipped + what remains.

### Routes

- **New canonical render route.** `GET /reviewer/sessions/{id}`
  takes over as the surface URL. Renders every instrument
  the reviewer has assignments on, in
  `Instrument.order, Instrument.id` order — matching the
  summary page and the page-button order today.
- **Legacy positional route shimmed.** Keep
  `GET /reviewer/sessions/{id}/{position}` for one release as
  a 303 forward to the new canonical URL plus a
  `#instrument-{id}` scroll anchor derived from the original
  position. Invitation tokens already in the wild + bookmarked
  URLs survive transparently. Retire the shim in PR 2 once
  tests + dashboards point at the new URL.
- **Save endpoint.** New `POST /reviewer/sessions/{id}/save`
  that walks every assignment in the form payload. The
  positional `POST /{position}/save` stays as a shim for
  one release for the same reason as the GET shim; it
  re-routes the payload to the same service call.
- **Submit / Recall / Clear** unchanged — already session-
  wide.

### View shape

- `_surface_context` drops the `current_position` argument
  and the `is_current` flag on `InstrumentGroup` — every
  group is always visible.
- `PageButton` dataclass + `page_button_label` helper stay
  (Decision 8). The list is rebuilt with `href` pointing at
  `#instrument-{anchor_id}` and the label relabelled to
  `#N short_label`. `is_current` drops; no button renders
  disabled.
- The per-instrument heading-state pair lands as a new
  dataclass `InstrumentHeadingState` on each group: carries
  the "not accepting" banner text + the closed-with-hidden /
  closed-with-visible flag the current page-wide banner
  shows.

### Template

- `review_surface.html` loops over `instrument_groups` with
  every group always rendered (no `.rs-paginated` /
  `.rs-active` toggling).
- `<hr class="rs-instrument-separator">` (new class — line
  + `margin: var(--space-6) 0`) sits between adjacent
  instruments.
- Action row renders **above every instrument** + once at
  the bottom with the danger zone. The action row is
  already a Jinja `{% include %}` partial; rendering it
  inside the `{% for group in instrument_groups %}` loop is
  a small change.
- `.rs-intro-grid` keeps its 2-column shape; column 2 now
  carries the heading-row state card (Decision 3) instead
  of being empty. Inside the card:
  - The "no longer accepting" / "showing when closed" pill
    pair scoped to this instrument's
    `accepting_responses` + `responses_visible_when_closed`
    flags.
  - Optional second line spelling out the implication
    ("Your saved values remain visible below" vs. "are
    hidden by the operator").
- Page-#N button row stays in the action row, with hrefs
  now pointing at `#instrument-{anchor_id}` (Decision 8).
  The disabled-when-current branch in the action row partial
  drops with `is_current`.
- The session-level "no longer accepting" / status panel
  (`review_surface.html:47-58`) drops the
  `not any_accepting` banner — its content moves per-
  instrument. The session-level pills (Submitted /
  Saved-not-submitted / Draft rollup) stay; their content
  is still session-wide.

### JS

- The Page-#N pagination JS retires entirely. Dirty-tracker
  + `history.pushState` for URL sync go with it.
- The remaining JS is the small-form sniffer the inline
  Save button uses to disable/enable on dirty — unaffected.

### Dashboard + summary cross-refs

- Reviewer dashboard's "Session" column link points at
  `/sessions/{id}` instead of `/sessions/{id}/1` when the
  reviewer's pill is `not started` / `in progress`. (When
  `submitted`, the dashboard already points at `/summary`.)
- The summary page's per-section anchor pattern
  (`<section id="instrument-{id}">`?) can mirror the
  surface's so the summary's "Edit this instrument"
  affordance (if added later) deep-links into the surface
  with the right scroll position. Not in scope for this
  segment; flagged for future polish.

### Tests

- ~126 test lines POST to `/{position}/save` /
  `/{position}/submit-equivalent` endpoints. Two-PR
  migration: PR 1 lands the new endpoints + redirects
  (existing tests pass against the shims); PR 2 migrates
  the suite to the new URLs and drops the shims.
- New integration tests:
  - Single-instrument session renders as before (no
    `<hr>`, one action row top + bottom).
  - Multi-instrument session renders every instrument
    visible with `<hr>` between, action row above each
    heading, action row + danger zone at the bottom.
  - Per-instrument heading-state card carries the right
    pill pair per accepting / visibility combo.
  - Save POST with a payload spanning multiple instruments
    persists every assignment's response in one round-trip.
  - Closed-but-visible instruments still render their
    saved values inline alongside open instruments.

## Out of scope

- Sticky action row (Decision 2).
- Server-driven pagination of any flavour — the segment
  retires pagination, doesn't soft-replace it (Decision 1).
- Edits to the summary page beyond cross-ref polish (the
  surface change should not regress what the summary
  shows).
- Operator-side surfaces. The operator preview
  (`routes_reviewer/_preview.py`) reuses `_surface_context`
  + the same template; it inherits the change for free.
  No new operator UI ships in this segment.

## Risk notes

- **Save-endpoint audit shape locked.** One
  `responses.saved` row per call with
  `detail.counts.assignments_touched` +
  `detail.counts.responses_saved` (Decision 4). Register
  the new shape in `EVENT_SCHEMAS` in the same commit or
  strict-mode tests fail.
- **Legacy URL shims (PR 1 → PR 3).** Invitation tokens
  already 303 to `/sessions/{id}`; positional URLs only
  live in our own dashboard, which PR 1 cuts over. Shim
  coverage tests in PR 1; shims retired in PR 3
  alongside the test sweep (Decision 7).
- **`page_statuses` retirement (PR 1).** The per-page
  pills (`Page #1: in progress`, etc.) in the session
  status panel become redundant once every instrument is
  on the page. Drop them in PR 1; the rollup pill stays.
- **`current_position` cleanup (PR 1 → PR 3).** PR 1
  removes the form-payload read on Submit / Recall /
  Clear (Decision 5) and the GET handler's positional
  branch. PR 3 finishes the cleanup by removing the
  helper + any remaining references when the shims
  retire.
- **Multi-table sort scope (PR 1).** Sort JS already
  scopes by `data-rrw-sortable` keyed on instrument id, so
  N visible tables sort independently. PR 1 adds a smoke
  test asserting the keys differ across instruments — the
  contract was unobservable while only one table rendered.

## Sequencing (as shipped, post-replan)

The segment landed across five PRs in two phases. The
first phase (PR 1a + PR 1b + small follow-ups) shipped
the single-page-all-instruments model from the original
lock. Mid-flight the user clarified that 18M's strategic
vision called for true multi-page navigation; the replan
PR (#1522) reshaped PR 1b's work into the multi-page
model described in the Goal above. PR 1c followed with
the helper / hidden-field cleanup. PR 1d (test sweep) +
PR 2 (per-instrument heading-state card) remain.

### Shipped

1. **PR 1a (#1518) — consolidated save endpoint + audit-
   key rename.** Additive `POST /reviewer/sessions/{id}/save`
   that walks every upsert in the form payload; `save_draft`
   emits `audit.counts(assignments_touched=N,
   responses_saved=W)` cleanly replacing the legacy
   `saved` + `validation_errors` keys.

2. **PR 1b (#1519) — initial render switch (single
   page).** Reshaped `_surface_context` to drop
   `current_position` / `is_current`, added `anchor_id`
   per group, rebuilt `PageButton` as anchor TOC,
   deleted the `.rs-paginated` wrapper + ~250 lines of
   pagination JS, added `<hr class="rs-instrument-
   separator">` between adjacent instruments, moved the
   action row inside the loop. **This shipped the
   single-page model**; PR #1522 below reshaped it into
   the multi-page model.

3. **PR 1b polish (#1520) — anchor lands above the per-
   instrument action row.** Wrapped each (action row +
   section) in a `<div id="instrument-{id}">` so
   `#instrument-{N}` scrolls to the action row instead
   of the heading.

4. **PR 1b page-break wiring (#1521) — reviewer surface
   honours `starts_new_page`.** `<hr>` separator
   conditioned on `group.starts_new_page` — visible only
   between operator-defined pages, not between every
   adjacent instrument. End-to-end visibility of 18M's
   break flag in single-page-render world.

5. **PR 1b replan (#1522) — multi-page surface
   (operator-defined).** Reshaped the entire PR-1b layer
   into URL-paginated by page: `GET /sessions/{id}` 303s
   to `/1`; `GET /sessions/{id}/{N}` is the canonical
   render, scoped to the operator-defined page's
   instruments; `POST /sessions/{id}/{N}/save` saves +
   303s back to `/{N}`. New `_pages_for_session` helper
   groups instruments by `starts_new_page`. Prev/Next
   nav row at top + bottom of each page when
   `page_count > 1`. `<hr>` separator within a page
   retired (intra-page instruments stack without
   separator). 10 legacy tests `@pytest.mark.skip`'d
   pending migration in PR 1d.

6. **PR 1c — cleanup.** Dropped `_read_current_position`
   helper (the URL slot carries page number, no form
   field needed). Dropped `current_position` hidden input
   from the Clear form + Cancel-link templating. Submit /
   Clear now redirect to the bare session URL (which 303s
   to `/1`); `submit_redirect_url` lost its `position`
   parameter. Spec patches: `spec/reviewer-surface.md`
   URL contract section + `guide/visibility_audit.md`
   route column rewritten around `{page_n}`. 2 legacy
   tests `@pytest.mark.skip`'d (Bare-URL hidden-input
   assertion + Clear-redirect-honours-position) pending
   migration in PR 1d.

7. **PR 1d — test sweep.** Migrated 11 tests and deleted 8
   covering reviewer-surface flows that the PR 1b replan
   had broken. Migrations swapped `/{instrument_position}`
   URL slots for `/{page_n}` — most collapsed to `/1`
   under the single-page-default session shape, with two
   per-page filter tests using
   `instruments_service.create_page_break_after` to carve
   a real two-page session. Deletions covered Category A
   chrome that the multi-page replan retired (Page-N
   button data attributes, `.rs-action-divider` layout
   counts, `rs-paginated` / `rs-active` JS hooks,
   `Previous` / `Next` buttons). The cross-cutting
   `current_position` hidden-form-field reads were
   purged from every still-active test. PR 2 (per-
   instrument heading-state card) is now the only
   remaining piece of the segment.

### Remaining

8. **PR 2 — per-instrument heading-state card
   (Decision 3).** Move the "no longer accepting" banner
   from page-wide `.rs-status-panel` to per-instrument
   `.rs-intro-grid` column 2. Each instrument carries
   its own state pair side-by-side with its own heading.
   Card omitted when `accepting=True, visible=True` (the
   common path). ~150 LOC. Independent of PR 1c/d but
   conceptually the second "movement" of the segment.

After PR 1d the only reviewer surface URLs are
`/reviewer/sessions/{id}` (303 to /1) and
`/reviewer/sessions/{id}/{N}` (page render).

## Cross-refs

- `app/web/routes_reviewer/_surface.py` — every route in
  scope (`review_surface_default_position`,
  `review_surface`, `reviewer_save`, `reviewer_submit`,
  `reviewer_recall`, `reviewer_clear`).
- `app/web/templates/reviewer/review_surface.html` — the
  template the segment rewrites (single-page layout,
  retired pagination JS, per-instrument heading-state
  card).
- `app/web/views/_instruments.py` —
  `instrument_heading` / `PageButton` / `page_button_label`.
  Both helpers stay; `PageButton` is repurposed as anchor
  nav (Decision 8) — `href` flips to `#instrument-{id}`,
  label format flips to `#N short_label`, `is_current`
  drops.
- `app/services/responses.py` —
  `save_responses` / `submit` paths; the new consolidated
  save endpoint calls the existing service helper across
  every instrument.
- `guide/visibility_audit.md` — reference for what each
  reviewer route renders in each lifecycle. Update the
  route column once the single-page URL replaces the
  positional ones.
- `spec/reviewer-surface.md` (if it exists) — patch the
  URL contract + pagination retirement.
