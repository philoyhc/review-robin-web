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
5. **Submit / Recall / Clear redirect to the top of
   `/reviewer/sessions/{id}`** with no anchor — the rollup
   pill at the top of `.rs-status-panel` is the
   session-level result confirmation. `current_position`
   stops being read from the form payload.
6. **Each instrument group emits `id="instrument-{id}"`** so
   the shim 303s can scroll-restore from a positional URL
   and future summary "Edit" affordances can deep-link.
7. **Shim retirement is immediate.** The test-sweep PR drops
   the legacy positional GET + POST shims in the same change
   that migrates the tests off them. Reviewer-facing
   invitation links already 303 to `/sessions/{id}`; no
   positional URLs are exposed outside our own dashboard.
8. **`PageButton` retires entirely in PR 1.** Grep + delete
   the dataclass, helper, and view-shape export — no no-op
   stub, no soft-deprecation. The operator preview reuses
   the same template and inherits the change.

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

## Sequencing

Three-PR landing. PR 1 carries the surface refactor + new
endpoints + shims (the bulk of the segment), PR 2 isolates
the per-instrument heading-state card so its layout move is
reviewable on its own, and PR 3 sweeps tests + retires shims.

### PR 1 — single-page render + new endpoints + shims (~350 LOC)

The unit-of-work: replace the positional rendering surface
with a single-page surface that renders every instrument,
without yet moving the closed-banner per-instrument. The
session-wide "no longer accepting" banner stays where it is
today (`.rs-status-panel`) so this PR's diff is contained to
the rendering / routing / view-shape layer.

- **Routes.**
  - New `GET /reviewer/sessions/{id}` renders every
    instrument in `Instrument.order, Instrument.id` order.
  - New `POST /reviewer/sessions/{id}/save` walks every
    assignment in the form payload via the existing
    `responses_service.save_draft` helper; emits one
    `responses.saved` audit row per call (Decision 4).
    Register the new event-shape in `EVENT_SCHEMAS` in the
    same commit.
  - Legacy `GET /reviewer/sessions/{id}/{position}` 303s to
    `/reviewer/sessions/{id}#instrument-{id}` (instrument id
    looked up by sorted-position).
  - Legacy `POST /reviewer/sessions/{id}/{position}/save`
    303s to the new save endpoint (or rebuilds the payload
    and re-dispatches — pick whichever keeps the shim
    smaller; redirect is simpler).
  - `reviewer_submit` / `reviewer_recall` / `reviewer_clear`
    drop the `current_position` form read; all three
    redirect to `/reviewer/sessions/{id}` (Decision 5).
  - The bare `/reviewer/sessions/{id}` handler that today
    303s to `/1` becomes the canonical render handler.
- **View shape.**
  - `_surface_context` drops `current_position` and
    `is_current`. Every group is always visible.
  - Add `anchor_id = f"instrument-{inst.id}"` on each
    `InstrumentGroup` (Decision 6).
  - Retire `PageButton` dataclass + `page_button_label`
    helper + the `page_buttons` context key. Grep
    `app/` + `tests/` + `spec/` + `guide/` for references
    and delete them (Decision 8).
  - `page_statuses` retires — drop both the dataclass build
    + the template loop. The rollup pill
    (Submitted / Saved-not-submitted / Draft) stays in
    `.rs-status-panel`.
- **Template (`review_surface.html`).**
  - `<form>` action becomes `/reviewer/sessions/{id}/save`;
    `current_position` hidden input deleted.
  - `.rs-paginated` wrapper deleted; the `for group in
    instrument_groups` loop renders every group as
    `<section id="instrument-{{ group.anchor_id }}"
     class="rs-instrument-group">`.
  - `<hr class="rs-instrument-separator">` between adjacent
    groups (new class — `margin: var(--space-6) 0;
    border: 0; border-top: 1px solid var(--border)` in
    `base.html`).
  - Action row include moves *inside* the loop, rendering
    above every instrument heading; the bottom instance
    (with the danger zone) stays outside the loop.
  - `.rs-status-panel` heading banner stays page-wide for
    this PR — it's still session-level here. PR 2 splits it
    per-instrument.
  - Page-#N button row markup + the per-page status pills
    list deleted.
  - Inline pagination JS (~70 lines around lines 484-755 —
    `rs-paginated` toggling, `pushState`, `popstate`,
    page-button click handler, dirty-confirm on page
    switch) deleted. The small dirty-tracker + Save-enable
    sniffer stay (now scoped to the whole form).
- **Dashboard.** `app/web/routes_reviewer/_dashboard.py`
  link for `not started` / `in progress` pills points at
  `/reviewer/sessions/{id}` instead of `/{id}/1`.
- **Tests (new integration coverage).**
  - Single-instrument session: one action row top + one
    bottom; no `<hr>`; saved values render.
  - Two-instrument session: every instrument visible,
    `<hr>` between, action row above each heading, action
    row + danger zone at the bottom.
  - `POST /sessions/{id}/save` with a payload spanning both
    instruments persists every assignment's response and
    emits a single `responses.saved` audit row with the
    right `detail.counts`.
  - Closed-but-visible instruments render saved values
    inline.
  - Each instrument group renders with an
    `id="instrument-{id}"` attribute matching its database
    id.
  - Legacy `GET /sessions/{id}/1` 303s to
    `/sessions/{id}#instrument-{id}`.
  - Legacy `POST /sessions/{id}/1/save` succeeds via the
    shim path.
  - Per-table sort smoke: a two-instrument render emits two
    `data-rrw-sortable` keys that differ (the keys already
    embed the instrument id; this just locks the contract).
- **Spec patches.**
  - `spec/reviewer-surface.md` — URL contract section
    (single canonical URL, shims pending) + retirement of
    the Page-#N pattern.
  - `guide/visibility_audit.md` — route column on the
    surface row updated.

### PR 2 — per-instrument heading-state card (~150 LOC)

The unit-of-work: move the heading-row banner state from
page-wide (`.rs-status-panel`) to per-instrument
(`.rs-intro-grid` column 2). Decision 3 in isolation.

- **View shape.**
  - New `InstrumentHeadingState` dataclass on each
    `InstrumentGroup` carrying
    `accepting: bool`,
    `responses_visible_when_closed: bool`, and pre-rendered
    pill / banner-line strings.
- **Template.**
  - `.rs-status-panel` drops the `not any_accepting`
    banner block (`review_surface.html:47-58`). The session
    description + rollup pill stay; the panel renders only
    when there's still something to say.
  - `.rs-intro-grid` column 2 carries a new
    `.card.rs-instrument-state-card` showing the
    accepting-state pill pair + the implication line
    ("Your saved values remain visible below" vs. "are
    hidden by the operator"). Card omitted entirely when
    Decision 3's empty-on-open case applies.
- **Tests.**
  - Per-instrument card combos:
    - accepting=True, visible=True → no card.
    - accepting=False, visible=True → "no longer accepting"
      pill + "saved values remain visible" line.
    - accepting=False, visible=False → "no longer
      accepting" pill + "saved values hidden" line.
  - Page-wide banner from PR 1's `.rs-status-panel` no
    longer fires on `not any_accepting`.

### PR 3 — test sweep + shim retirement (~250 LOC, mostly tests)

- Migrate the ~126 existing test lines that POST / GET
  positional URLs (`/{position}` / `/{position}/save`) to
  the new single-URL endpoints.
- Delete the legacy positional GET + POST shims from
  `_surface.py`.
- Delete `_read_current_position` and any remaining
  `current_position` references in routes / tests / spec.
- Final spec patch: `spec/reviewer-surface.md` URL
  contract section drops the "shims pending" note.

After PR 3 the only reviewer surface URL is
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
