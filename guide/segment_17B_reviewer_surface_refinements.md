# Segment 17B — Reviewer surface refinements

**Status:** Stub — revised 2026-05-16 against the codebase.

A polish + ergonomics pass on the reviewer response surface
(`GET /reviewer/sessions/{id}/{instrument_position}`, rendered
by `review_surface` in `app/web/routes_reviewer.py`). The
headline change vs the original stub: 17B now **also owns the
large-table ergonomics** that `spec/visual_style_rrw.md` pins
as first-class — auto-save, return-to-place, visible progress,
sticky headers, filter-to-incomplete, keyboard navigation. These
were once bundled into the AG Grid segment; that segment has
been taken off the roadmap (AG Grid is judged overkill — see
`guide/future_possibilities.md`), so the ergonomics are pursued
here as **targeted progressive enhancement**, the project's
actual stack (`CLAUDE.md`: inline JS for progressive
enhancement is fine; a framework / build pipeline is not).

## PR 1 — package `routes_reviewer.py` first

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

- Button order in the unified action row; status-card location.
- Row height — the table can go slightly denser.

These are screenshot-driven tweaks; land them as one small PR
once the shape is agreed.

## Large-table ergonomics (no JS framework)

Each item is independent and small; land them as separate PRs.
None needs a JS bundle or a build step. The reviewer-surface
view-shape payload (the `_surface_context` list-of-dicts, with
field metadata shipped alongside) is **already stable and
explicitly pinned stable** for exactly this work
(`spec/reviewer-surface.md` §"Large-table ergonomics"), so none
of the items below needs a route or view-adapter change — the
work is template + inline JS + CSS.

- **Cell-level autosave.** A debounced `fetch` to the existing
  `POST /reviewer/sessions/{id}/{position}/save` endpoint on
  cell blur / change, replacing (or sitting alongside) the
  per-page form Save. Per-cell status indicator — in-flight /
  saved / failed. **Concurrency note:** the `Response.version`
  column exists (added inert by the 13F DB-prep — *no migration
  needed*) but is **not currently wired** into the save path;
  `responses.save_draft` does not read or bump it. Plain cell
  autosave is therefore last-write-wins, exactly like today's
  per-page Save — acceptable, since one reviewer owns their own
  rows. If genuine version-gated optimistic concurrency is
  wanted, wiring `Response.version` is *additional* optional
  work (a small service change, still no schema change); treat
  it as a separate decision, not a freebie.
- **Sticky column headers.** CSS `position: sticky` on the
  `<th>` row so headers stay visible while scrolling a long
  reviewee list. Pure CSS.
- **Return-to-place + visible progress.** Preserve scroll
  position across save / reload; a small "N of M complete"
  progress indicator. (`_surface_context` already computes
  per-row completion state for the incomplete-marks render, so
  the count is in the payload.)
- **Filter-to-incomplete.** A client-side toggle that hides
  rows already complete, so a reviewer can find what is left.
- **Keyboard navigation + column-type ergonomics.**
  `spec/visual_style_rrw.md` also pins tab / arrow movement
  between cells and per-column-type input affordances as
  first-class. Lower priority than the four items above; land
  only if the surface still feels heavy after them.

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
- `spec/visual_style_rrw.md` — pins auto-save / sticky headers
  / progress / return-to-place / filter-to-incomplete /
  keyboard navigation as first-class requirements.
- `guide/codebase_assessment_16may.md` — §5 weakness 4 names
  the `routes_reviewer.py` packaging as 17B's opening step.
- `guide/future_possibilities.md` — why the JS-grid route is
  off the roadmap.
