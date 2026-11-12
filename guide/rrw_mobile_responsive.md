# Review Robin on a phone: what it would take

**Assessment, 2026-11-12, against RRW `main` at `3e47ce9d`.** Written in
Cordware's `guide/` (Cordware #208) and moved here the same day (author),
since all of it is RRW work. No RRW
code was changed: RRW was read, and its pages were rendered from a
scratch copy. **Verdict: feasible, and cheap for participants.** The
participant pages are already close. One missing line keeps every page
desktop-sized on a phone, and the rest is a CSS layer over tables that
already scroll safely. The operator pages are a different order of work
and are best left desktop-first.

## 1. The finding that matters

**RRW's `app/web/templates/base.html` has no viewport meta tag.**
Without `<meta name="viewport" content="width=device-width,
initial-scale=1">`, a phone browser lays every page out at about 980 CSS
px and shrinks it to fit. On a 390 px phone that is about 40% scale:
body text near 6 px, buttons too small to tap, and everything needing a
pinch-zoom.

- **Every other application has the tag:** Residential
  (`residentialapps/web/templates/residential/base.html`), Utilities,
  ApplyDesk and the Cordware landing page. Within RRW, only `error.html`
  has it.
- **The narrow-screen CSS RRW already has never fires on a phone.**
  `base.html` holds 23 `@media` rules, breaking at 500, 560, 600, 639,
  720, 800, 860, 900 and 959 px, plus one `pointer: coarse`. A layout
  viewport of 980 px is wider than every one of those breakpoints.

## 2. Measured: each participant page at 390 px

**Method.** I ran RRW's participant integration tests (48 files, 800
tests) in a scratch copy, with a hook that saved every HTML page they
fetched: 510 pages. I loaded the largest page of each type into Chromium
emulating a 390 × 844 phone (`is_mobile`, touch), once as it is and once
with the viewport tag added.

**Caveat on the data.** Test fixtures are small, often one to three
reviewees and two fields. A real session with more fields makes the
across-layout tables wider than measured here.

| Page | As it is | With the tag: page fits? | Widest table (scrolls inside its card) | Targets < 32 px tall |
|---|---|---|---|---|
| `/me` dashboard | 980 px layout | yes | 532 px, 6 columns | 8 |
| `/me/sessions/{id}`, one instrument | 980 | yes | 616 px response table, plus the 3-column visibility grid | 5 |
| `/me/sessions/{id}`, several instruments | 980 | yes | 525 px per instrument | 10 |
| `/me/sessions/{id}/summary` | 980 | yes | 501 px | 0 |
| `/me/sessions/{id}/results` (reviewee) | 980 | yes | fits (274 px) | 1 |
| `/me/sessions/{id}/collation` (observer) | 980 | yes | 498 px | 0 |
| About, Guide | 980 | yes | fits | 2 / 10 |

- **Nothing breaks the page.** Every participant table sits in a
  `.table-scroll` wrapper (`overflow-x: auto`), so a wide table scrolls
  sideways inside its card while the page stays 390 px wide.
- **What hurts is the reviewer surface, the page that matters most.**
  - In the default *Responses across* layout, a reviewee's answers sit
    to the right of their name. At 390 px the first answer box is
    already half off-screen. The reviewer scrolls each table sideways
    to answer, and the reviewee's name scrolls away as they do.
  - With several instruments, each one repeats a *Who can see what you
    wrote* grid whose last column is clipped.
  - Addresses wrap mid-word in the identity column
    (`rae@example.ed` / `u`).
- **No text input is under 16 px**, so iOS does not zoom when a field
  takes focus. Several links, sort headers and chips are under 32 px
  tall, below the usual 44 px touch guidance.
- **Operator-set column widths are pixel widths.** On the review
  surface, summary and results, a `<colgroup>` carries the operator's
  dragged widths under `table-layout: fixed`
  (`app/web/templates/reviewer/review_surface.html` ~line 336). A
  desktop-sized set of widths forces the sideways scroll however much
  room a phone needs.

**For contrast, the operator pages.** With the tag, Session Home lays
out 621 px wide: both tab strips overflow. Instruments lays out 458 px
wide: Band 1's grid has `min-width: 1216px` and the field-builder
table has `min-width: 1056px`. The Reviewers table is 614 px wide. Real
work here is a redesign of the dense setup surfaces, not CSS.

## 3. What makes it feasible

- **One stylesheet.** All CSS is inline in `base.html`, with no build
  step and no framework, and RRW already writes `@media` rules there.
- **Tables are already wrapped.** Every participant table has its
  scroller, so no page breaks while the work is in progress.
- **20K already has the phone layout's core.** It shipped *Responses
  stacked* (`guide/archive/segment_20K_stacked_response_layout.md`): one row per reviewee and one *Responses* cell holding a
  label-and-input line per field. That is the shape a phone needs. What
  remains is to stack the row's cells vertically under a narrow
  breakpoint.
- **Interaction is plain HTML.** The participant pages' scripts are
  small progressive enhancements: column sort with a cookie, answer
  boxes that grow, role-chip layout. None depends on hover or drag;
  column dragging exists only on operator pages.
- **The browser-test harness is there.** `tests/browser/` drives a live
  server in Chromium. Residential already tests touch targets in
  `residentialapps/tests/test_touch_targets_browser.py`, a pattern to
  copy.

## 4. What needs doing, in order

Participants first. Each rung is one RRW PR, built here once ApplyDesk's
run allows, then imported into Cordware as usual. Nothing is done in
Cordware.

1. **Viewport tag, participant pages only.** Add a `{% block viewport %}`
   to `base.html`'s `<head>`, empty by default. Fill it in the seven
   page templates under `reviewer/` (dashboard, review surface, summary,
   results, collation, pre-open, invite mismatch) and in `about.html`
   and `guide.html`. `error.html` stands alone and has the tag already.
   - **Why opt-in:** operator pages keep today's zoomed-out desktop
     rendering, rather than laying out at 390 px with overflowing tab
     strips and a 1,216 px builder.
   - **Size:** about 10 lines. This alone makes every participant page
     legible.
2. **Phone layout for the response table, under 640 px.** Turn each
   reviewee row into a card:
   - `tr` and `td` become blocks;
   - identity and display fields sit at the top;
   - each answer becomes a label-over-input line, labelled from a
     `data-label` on each `td`, or by the stacked cell 20K already
     renders.
   - At that width, ignore the operator's `<col>` pixel widths
     (`table-layout: auto`, `col { width: auto }`).
   - Applies to **both** layouts. *Responses stacked* needs only the
     cell stacking; *Responses across* needs the labels.
   - Group mode (`rs-group-table`) gets the same treatment.
   - **Size:** CSS in `base.html`, `data-label` attributes in
     `review_surface.html` and `_response_control.html`.
3. **The rest of the reviewer surface.**
   - The *Who can see what you wrote* grid stacks: audience as a
     heading, with its two phases below.
   - The status and progress chips wrap.
   - The Save / Cancel / Submit row goes full width, optionally fixed
     to the bottom of the screen while the page scrolls.
   - Addresses break at `@` and `.` rather than mid-word.
4. **Dashboard, summary, results, collation as cards under 640 px.**
   - **Dashboard:** six columns become a session card with its dates
     and status on two lines.
   - **Summary, results and collation:** these use the same table
     template pattern, so they reuse rung 2's CSS, with the same
     `<col>` override.
5. **Touch targets.** Under `(pointer: coarse)`, make links, sort
   headers, chips, checkboxes and the action buttons at least 44 px
   tall, as Residential does. Consolidate the nine breakpoints to two
   (640 and 900) while there.
6. **A guard.** A browser test at 390 × 844 (`is_mobile`) for each
   participant page, checking three things:
   - the page does not scroll sideways;
   - no response table needs a sideways scroll in either layout;
   - no tappable element is under 44 px.

   The test uses a session seeded with at least eight fields, so it is
   wider than the fixtures in §2. Like the other browser tests, it is
   required in CI.

**Operator pages, later or never.** One cheap step makes them tolerable
for an emergency look on a phone: `overflow-x: auto` on the two tab
strips, and the viewport tag on the read-mostly pages (lobby, Session
Home, Invitations). The setup pages (Instruments' builder, Band 1, the
roster editors) should stay desktop-only, with a one-line *best on a
larger screen* note under 640 px. Making them responsive is a redesign
and is not recommended.

## 5. Effort and risk

- **Effort:** rungs 1–6 are six RRW PRs, about a segment's worth,
  mostly CSS. Rung 1 is under an hour. Rung 2 is the substantive one.
- **Risk:**
  - **Low for desktop.** Every rule sits under a narrow media query, and
    rung 1 is opt-in per template.
  - **The real risk is the reviewer surface's many variants:** across
    or stacked, group mode, branching fields, required markers,
    locked or submitted states, several instruments. Rung 6 is the
    net. RRW's existing browser tests for the surface run at 1,400 px
    and keep desktop covered.
- **Not covered here:**
  - The invitation emails' own HTML: phone mail clients render that.
  - The Cordware landing page and the other applications, which
    already have the tag.
  - Real-device checks: iOS Safari's bottom bar against a fixed action
    row, and Android's keyboard resize. Those need a phone on the
    Azure deployment once rung 3 is in.
