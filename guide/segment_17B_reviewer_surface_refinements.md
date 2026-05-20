# Segment 17B — Reviewer surface refinements

**Status:** Partly shipped (2026-05-16). PR 1 (`routes_reviewer`
packaging, commit `801af2f`), the action-row reorder, keyboard
navigation, and the progress pills have landed (PRs #1076 / #1077).
Cell autosave and filter-to-incomplete are deferred to
`guide/deferred_until_pilot_feedback.md`; return-to-place and the
remaining chrome polish are still open. The reviewer-facing
timezone-clarity item is covered incidentally by the 18B
follow-ups (the deadline carries a zone label).

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

## Out of scope

- A JS data-grid framework (AG Grid or equivalent) — moved to
  `guide/future_possibilities.md`. 17B deliberately gets the
  *ergonomics* without the *framework*.
- Reviewer self-service profile — not an MVP requirement.
- Version-gated optimistic concurrency on `Response.version` —
  optional follow-on, not a 17B commitment (see the autosave
  note above).

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
