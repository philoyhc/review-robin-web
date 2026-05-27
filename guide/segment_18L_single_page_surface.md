# Segment 18L — Single-page reviewer surface

> **Status: drafting (stub created 2026-05-27).** Decisions
> locked with the human author 2026-05-27 (see "Decisions"
> below); no PRs yet.
>
> **Predecessors.** Segment 17B Phase 2 wired the participation-
> summary capstone page; Segment 18J shipped column widths and
> per-cell visibility; Segment 18K closed the reviewer-side
> per-field visibility filter on the summary HTML + CSV. The
> reviewer-side visibility audit (`guide/visibility_audit.md`)
> stays the reference for what each route renders in each
> lifecycle state.

## Goal

Collapse the reviewer response surface from per-instrument
pages (`GET /reviewer/sessions/{id}/{position}`) into a
single-page-all-instruments view at
`GET /reviewer/sessions/{id}`. Each instrument stacks
vertically with a horizontal separator between adjacent
instruments. The existing action row (Save / Submit / Clear)
renders above **every** instrument heading; the final
instance at the bottom also carries the danger zone (Clear /
Recall). The Page-#N navigation row retires.

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
   side-by-side with its own heading.

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
- Page-button list retired (`PageButton` dataclass can stay
  as a no-op return for one release if any operator-preview
  path still imports it; retire in PR 2).
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
- Page-#N button row retired (the markup block around
  `views.PageButton` references).
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

- **Save-endpoint behaviour change.** A consolidated save
  endpoint changes the audit shape — today each
  `/{position}/save` emits one `responses.saved` event
  scoped to that instrument. The new endpoint emits one
  per submitted assignment or one per call; pick
  consistently and document. The simplest is one event
  with the full counts in `detail.counts`; mirrors the
  Submit-event shape.
- **Legacy URL shims.** Invitation tokens 303 to
  `/sessions/{id}` and forget which page the operator
  meant. We never expose `/{position}` URLs to reviewers
  outside our own dashboard, so the blast radius is small;
  still worth a one-line shim coverage test.
- **`page_statuses` retirement.** The per-page pills
  (`Page #1: in progress`, etc.) in the session status
  panel become redundant once every instrument is on the
  page (the reviewer can just see the state). Drop them
  in PR 1; the rollup pill stays.

## Sequencing

Two-PR landing, each small enough for a careful sitting:

1. **PR 1 — single-page surface + new endpoints.**
   - New `GET /sessions/{id}` + `POST /sessions/{id}/save`.
   - Template + view-shape refactor (every group visible,
     action row interleaved, per-instrument heading state
     card in `.rs-intro-grid` column 2).
   - Pagination JS retired.
   - Legacy positional routes shimmed to 303-forward.
   - Dashboard link updated.
   - New integration tests covering the visible / save /
     accepting-state branches.
   - ~400 LOC delta.
2. **PR 2 — test sweep + shim retirement.**
   - Migrate the ~126 existing test lines off `/{position}`
     URLs.
   - Retire the legacy positional GET + POST shims.
   - ~300 LOC test delta + small route cleanup.

After PR 2 the only reviewer surface URL is
`/reviewer/sessions/{id}`.

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
  `instrument_heading` / `PageButton`. The heading helper
  stays; `PageButton` retires.
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
