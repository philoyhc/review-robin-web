# Segment 17B — Reviewer surface refinements

**Status:** Stub.

A polish + ergonomics pass on the reviewer response surface
(`/reviewer/sessions/{id}/{instrument_position}`). The headline
change vs the original stub: 17B now **also owns the
large-table ergonomics** that `spec/visual_style_rrw.md` pins
as first-class — auto-save, return-to-place, visible progress,
sticky headers, filter-to-incomplete. These were once bundled
into the AG Grid segment; that segment has been taken off the
roadmap (AG Grid is judged overkill — see
`guide/future_possibilities.md`), so the ergonomics are pursued
here as **targeted progressive enhancement**, the project's
actual stack (`CLAUDE.md`: inline JS for progressive
enhancement is fine; a framework / build pipeline is not).

## Chrome / layout polish

- To v2 chrome.
- Button order; status-card location.
- Row height can be decreased slightly (denser table).

## Large-table ergonomics (no JS framework)

Each item is independent and small; land them as separate PRs.
None needs a JS bundle or a build step.

- **Cell-level autosave.** A debounced `fetch` to the existing
  `POST /save` endpoint on cell blur / change, replacing (or
  sitting alongside) the per-page form Save. Per-cell status
  indicator — in-flight / saved / failed. Conflict handling is
  unchanged: last-write-wins, gated by the existing
  `Response.version` column (so no schema change — see
  `guide/segment_13F_more_db_prep.md`).
- **Sticky column headers.** CSS `position: sticky` on the
  `<th>` row so headers stay visible while scrolling a long
  reviewee list. Pure CSS.
- **Return-to-place + visible progress.** Preserve scroll
  position across save / reload; a small "N of M complete"
  progress indicator.
- **Filter-to-incomplete.** A client-side toggle that hides
  rows already complete, so a reviewer can find what is left.

The reviewer-surface view-shape payload (`_surface_context`'s
list-of-dicts, with field metadata shipped alongside) is
already stable, so none of the above needs a route or
view-adapter change — the work is template + inline JS + CSS.

## Reviewer-facing timezone clarity

Since the Segment 18B follow-up, display timestamps render
bare (`YYYY-MM-DD HH:MM`, no zone token). Operators see the
session's zone named on the `/operator/settings` and Session
Edit cards, but reviewers have no equivalent surface — an
emailed deadline or a reviewer-surface timestamp is zone-less.
In practice a review usually happens within one timezone, so
this is low-priority; flagged here in case the reviewer
surface should name the session zone (e.g. a small "Times
shown in <zone>" note near the deadline).

## Out of scope

- A JS data-grid framework (AG Grid or equivalent) — moved to
  `guide/future_possibilities.md`. 17B deliberately gets the
  *ergonomics* without the *framework*.
- Reviewer self-service profile — not an MVP requirement.

## Related context

- `spec/reviewer-surface.md` — the reviewer-surface contract,
  including the large-table-ergonomics note.
- `spec/visual_style_rrw.md` — pins auto-save / sticky headers
  / progress as first-class requirements.
- `guide/future_possibilities.md` — why the JS-grid route is
  off the roadmap.
