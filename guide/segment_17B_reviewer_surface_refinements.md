# Segment 17B — Reviewer surface refinements

**Status:** Partly shipped (2026-05-16). PR 1 (`routes_reviewer`
packaging, commit `801af2f`), the action-row reorder, keyboard
navigation, and the progress pills have landed (PRs #1076 / #1077).
Cell autosave and filter-to-incomplete are deferred to
`guide/deferred_until_pilot_feedback.md`; return-to-place and the
remaining chrome polish are still open. The reviewer-facing
timezone-clarity item is covered incidentally by the 18B
follow-ups (the deadline carries a zone label).

**Added 2026-05-20.** Two new PRs (A + B) scoped at pickup
generalise the reviewer landing toward the future Participants
model (`guide/participant_model_upgrade.md`) without committing
to a URL rename. The reviewer lobby gains Start / End / Status
columns and a "not opened" state for sessions the reviewer is
rostered on but that have not yet activated; a new per-session
participation-summary page renders on whole-session completion
with a CSV download for the reviewer's own responses.

A polish + ergonomics pass on the reviewer response surface
(`GET /reviewer/sessions/{id}/{instrument_position}`, rendered
by `review_surface` in `app/web/routes_reviewer.py`). The
headline change vs the original stub: 17B now **also owns the
large-table ergonomics** that `spec/visual_style_rrw.md` pins
as first-class — auto-save, return-to-place, visible progress,
filter-to-incomplete, keyboard navigation (sticky headers were
investigated and dropped — see below). These
were once bundled into the AG Grid segment; that segment has
been taken off the roadmap (AG Grid is judged overkill — see
`guide/future_possibilities.md`), so the ergonomics are pursued
here as **targeted progressive enhancement**, the project's
actual stack (`CLAUDE.md`: inline JS for progressive
enhancement is fine; a framework / build pipeline is not).

## PR 1 — package `routes_reviewer.py` first

**Shipped — commit `801af2f`.** `routes_reviewer/` is now a package
(`_dashboard.py` / `_surface.py` / `_preview.py` / `_invite.py` /
`_shared.py`). The rest of this section is the original rationale.

`app/web/routes_reviewer.py` is **1,362 LOC** — the one
operator-or-reviewer route file still a single module rather
than a package (the operator side was sliced by the major
refactor; 17A finished the operator splits). The 2026-05-16
codebase assessment §5 flags converting it as the natural
opening step of 17B, *before* the ergonomics work grows it
further.

Convert it to a `routes_reviewer/` package split by concern,
mirroring the 17A precedent — roughly: the dashboard route, the
review-surface routes (`review_surface` / `reviewer_save` /
`reviewer_submit` / `reviewer_clear` + the shared
`_surface_context` builder), the operator-preview helpers
(`build_preview_context` / `_make_synthetic_row`), and the
invite-token route. `__init__.py` re-exports the public surface
— `router` (imported by `app/main.py`) **and**
`build_preview_context` (imported by `app/web/views/_previews.py`
via a deferred local import to dodge the existing
`routes_reviewer ↔ views` cycle). Pure structure, no behaviour
change, test suite passes unchanged.

## Chrome / layout polish

The reviewer surface is **already on v2 chrome** — the Segment
11D v2 sweep (2026-05-04) gave it the `ui-v2` body class, the
reviewer `_top_bar.html` variant, and the `rs-page-header` H1 +
deadline header. So "move it to v2" is *done*; what remains is
small judgement-call polish:

- Button order in the unified action row — **shipped (#1076)**:
  the row now reads Save / Discard / Submit / divider / Page #N.
- Status-card location; row height — the table can go slightly
  denser. Still open; screenshot-driven tweaks.

These remaining tweaks are screenshot-driven; land them once the
shape is agreed.

## Large-table ergonomics (no JS framework)

Each item is independent and small; land them as separate PRs.
None needs a JS bundle or a build step. The reviewer-surface
view-shape payload (the `_surface_context` list-of-dicts, with
field metadata shipped alongside) is **already stable and
explicitly pinned stable** for exactly this work
(`spec/reviewer-surface.md` §"Large-table ergonomics"), so none
of the items below needs a route or view-adapter change — the
work is template + inline JS + CSS.

- **Cell-level autosave — deferred (2026-05-16)** to
  `guide/deferred_until_pilot_feedback.md`. The per-page form
  Save already persists a page's edits in one click; per-cell
  autosave (debounced `fetch` to the existing `/save` route,
  per-cell status indicator) is built only if pilot feedback
  asks. The full design + the `Response.version` concurrency
  note live in the deferred-items doc.
- **Sticky column headers — investigated and dropped
  (2026-05-16).** `position: sticky` on the `<th>` row does
  nothing useful here: the reviewer table's `.table-scroll`
  wrapper has `overflow-x: auto`, which forces an `overflow-y`
  scroll context, so the header sticks relative to that wrapper
  (which has no height and never scrolls internally) rather than
  the window. The only working fix is to give the table its own
  vertical scroll viewport (a `max-height` box) — turning a long
  reviewee list into an internal scroll region. That scroll-model
  change was judged not worth a header that stays put, so the
  surface keeps whole-page scroll and a non-sticky header. Not a
  17B PR.
- **Return-to-place + visible progress.** *Visible progress —
  shipped (#1077):* a session-wide status pill (Submitted / Saved
  but not submitted / Draft) and per-instrument
  `Required / All items completed` pills. *Return-to-place*
  (preserve scroll position across save / reload) remains open.
- **Filter-to-incomplete — deferred (2026-05-16)** to
  `guide/deferred_until_pilot_feedback.md`. A client-side toggle
  that hides already-complete rows; the per-instrument progress
  pills already surface what is left, so a table filter waits on
  pilot feedback.
- **Keyboard navigation — shipped (#1076).** Tab walks cells
  across a row natively; Enter / Shift+Enter move focus down / up
  a column (per `spec/visual_style_rrw.md`, which pins Tab +
  Enter — arrow keys were ruled out as they conflict with in-cell
  editing). Per-column-type input affordances remain open.

## Reviewer-facing timezone clarity

Since the Segment 18B follow-up, display timestamps render
bare (`YYYY-MM-DD HH:MM`, no zone token). Operators see the
session's zone named on the `/operator/settings` and Session
Edit cards, but reviewers have no equivalent surface — an
emailed deadline or a reviewer-surface timestamp is zone-less.
In practice a review usually happens within one timezone, so
this is low-priority; flagged here in case the reviewer
surface should name the session zone (e.g. a small "Times
shown in <zone>" note near the deadline). `resolve_session_timezone`
already gives the zone, and the operator cards show the CLDR
long display name via `timezone_label` — a reviewer note would
reuse the same helper.

## Participant-model alignment

The reviewer lobby already plays the same role for reviewers
that the Sessions lobby plays for operators. Generalising it
now — Session / Start / End / Status columns, a "not opened"
state — gets the reviewer landing within reach of a future
*unified* Participants landing that resolves every role across
every session (reviewer forms to complete, reviewee results to
read, observer collations to watch). The audience-local
*surfaces* (`/reviewer/...`, future `/reviewee/...`,
`/observer/...`) stay separate per
`guide/participant_model_upgrade.md`; only the landing
converges, and its URL is deliberately unspecified there until
the auth refactor settles. So 17B widens the lobby's shape and
query, but does not rename `/reviewer/` (see the decision
callout below).

### PR A — Lobby expansion + "not opened" status

The reviewer dashboard (`GET /reviewer`, rendered by
`reviewer_dashboard` in `app/web/routes_reviewer/_dashboard.py`)
currently shows one row per session the reviewer can open
(Session / Deadline / Status, statuses `submitted` / `in progress`
/ `not started`). Widen the table to **Session / Start / End /
Status** and extend coverage to sessions the reviewer is rostered
on but that have not yet activated, rendered as a fourth status
**`not opened`** with the session name unlinked.

Concretely:

- **Schema — add `sessions.activated_at: DateTime(timezone=True),
  nullable=True`.** Set in the `draft|validated → ready`
  lifecycle transition (`app/services/session_lifecycle.py`).
  One Alembic migration + a backfill that resolves each
  already-`ready` session's stamp from its earliest
  `session.activated` audit row (the audit event already exists
  per `EVENT_SCHEMAS`); sessions with no audit history keep
  `NULL` and render Start as `—`. Mirrors the existing
  `display_timezone` column placement on `ReviewSession`.
- **Lobby query.** Today the query restricts to sessions in
  `ready`; widen to "every session this reviewer has a roster
  row on, regardless of lifecycle state." For pre-ready
  sessions the dashboard view-shape carries `link_enabled=False`
  + `status="not opened"` and the row renders the session name
  as plain text (no anchor). Reviewers reach the lobby only
  through Easy Auth + roster, so widening doesn't expose
  sessions they shouldn't see.
- **Columns.** Rename the existing **Deadline** header to
  **End** (still backed by `session.deadline`; empty cell when
  no deadline). New **Start** column between Session and End
  shows `activated_at` formatted in the session zone (same
  `date_formatting.format_datetime` helper as End); blank for
  pre-ready rows. Order stays `(status priority, name)` so
  active rows lead.
- **Status vocabulary.** Extend
  `responses_service.session_pill_for_reviewer` (or a thin
  wrapper at the dashboard view-shape seam) with a `not opened`
  pill that takes precedence over response-derived states when
  `session.lifecycle_state != "ready"`. Style: muted info pill
  to distinguish from active `not started`.
- **Tests.** `tests/integration/test_reviewer_dashboard*.py` —
  add a pre-ready-session case (rostered + `validated`) asserting
  the row renders with `not opened`, unlinked, and blank Start.
  Existing assertions update for the renamed column header.

`activated_at` slides into the same Start column once Segment
18G adds *scheduled* activation: pre-activation rows show the
scheduled time, post-activation rows show the actual stamp. No
re-plumbing.

### PR B — Per-session participation summary + CSV

A capstone summary that fires when a reviewer has submitted
**every** instrument they were assigned on a session. One
summary per session (not per instrument) — when the last
instrument's submit completes, redirect the reviewer to the
summary instead of back to the review surface. The summary
itself stays reachable later from the dashboard row (the
session name on a `submitted` row links here, not the surface).

Concretely:

- **New route — `GET /reviewer/sessions/{id}/summary`** in a
  new `routes_reviewer/_summary.py` slice (matches the existing
  per-concern split). Gate: every active assignment for
  (this reviewer, this session) has all rows submitted; if not,
  redirect to the dashboard with a flash. Reviewers reach this
  through the new submit-time redirect *and* through the
  dashboard once the session is in `submitted` state.
- **Template.** One `<section>` per instrument, in the same
  order the surface walks them. Inside each section: a small
  per-instrument heading + the same table shape the surface
  renders read-only (reviewee identity rows × field values),
  reusing the existing `_surface_context` view shape rendered
  in summary mode. No edit affordances. One **Download my
  responses (CSV)** button at the top.
- **Submit-flow change.** `submit_redirect_url`
  (`routes_reviewer/_surface.py`, called from `reviewer_submit`
  on success) currently returns the surface URL; change it to
  return the summary URL when the submit transitions the
  session to fully-submitted. Per-instrument submits that don't
  close out the session keep the existing "redirect back to
  surface" behaviour.
- **CSV download — `GET /reviewer/sessions/{id}/summary.csv`.**
  Filename `{code}_my_responses.csv`. Reuses the per-instrument
  extract infrastructure from Segment 18H Part 2: a thin
  `serialize_reviewer_session_summary(db, session, reviewer)`
  helper loops the reviewer's instruments and yields each one's
  preamble + header + the reviewer-filtered data rows — same
  21-column shape as `responses.csv` so the file pastes
  alongside an operator's bundle download with no schema drift.
  The reviewer filter is the only new query gate; the row-tuple
  builder factored out in 18H Part 2 (`_response_row_tuple`)
  carries the rest unchanged.
- **Tests.** New `tests/integration/test_reviewer_summary*.py`
  — gate (incomplete session redirects), submit-time redirect
  to summary, CSV download row shape + reviewer-only filter,
  multi-instrument grouping.

Screenshot-as-record is the user's intentional fallback; the
CSV is the canonical record. PDF export is **not** in scope.

### URL space — defer `/reviewer/` → `/user/`

Open question at scoping: should the lobby move from
`/reviewer` to `/user` (or similar) now, in anticipation of the
Participants model? **Decision: defer.**
`guide/participant_model_upgrade.md` keeps audience-local
surfaces (`/reviewer/`, future `/reviewee/`, `/observer/`); only
the *unified landing* converges, and its URL is deliberately
unspecified there until the auth refactor settles. The rename
itself is cheap, but the timing has real friction — outstanding
invitation links and bookmarks break — and gains us nothing
toward the participants migration. Revisit when reviewee /
observer surfaces actually exist and the unified-landing URL is
chosen.

## Out of scope

- A JS data-grid framework (AG Grid or equivalent) — moved to
  `guide/future_possibilities.md`. 17B deliberately gets the
  *ergonomics* without the *framework*.
- Reviewer self-service profile — not an MVP requirement.
- Version-gated optimistic concurrency on `Response.version` —
  optional follow-on, not a 17B commitment (see the autosave
  note above).
- Rename of the `/reviewer/` URL space (see the PR A / B
  participant-model-alignment decision above) — deferred until
  the unified-landing URL is chosen.
- PDF export of the per-session summary — deferred; the CSV in
  PR B is the canonical participation record, with browser
  print-screen as the user's intentional fallback.
- Scheduled *activation* time (`activate_at` planned-open) —
  Segment 18G's scope; PR A's `activated_at` records the
  actual transition only, and the same Start column shows the
  scheduled time once 18G ships.

## Related context

- `spec/reviewer-surface.md` — the reviewer-surface contract;
  §"Large-table ergonomics" assigns these items to 17B and
  pins the `_surface_context` dict shape stable.
- `spec/visual_style_rrw.md` — pins auto-save / progress /
  return-to-place / filter-to-incomplete / keyboard navigation
  as first-class requirements (its sticky-column-headers item
  carries the 17B "investigated and dropped" annotation).
- `guide/archive/codebase_assessment_16may.md` — §5 weakness 4 names
  the `routes_reviewer.py` packaging as 17B's opening step.
- `guide/future_possibilities.md` — why the JS-grid route is
  off the roadmap.
- `guide/participant_model_upgrade.md` — the post-MVP arc the
  PR A lobby shape and PR B summary route generalise toward;
  source of the "audience-local surfaces, unified landing"
  principle behind the URL-rename deferral.
- `guide/segment_18H_post_assessment_update.md` Part 2 — the
  per-instrument response extract whose `_response_row_tuple`
  helper and per-instrument serializer PR B reuses, scoped to
  one reviewer.
- `guide/segment_18G_scheduled_events.md` — where the
  *scheduled* activation time lands; PR A's `activated_at`
  column slides into the same Start column without re-plumbing.
