# Segment 17 — AG Grid replacement of the reviewer-surface table

**Status:** Stub. Carved out 2026-05-10 from the original
`guide/archive/segment_15_operator_polish_and_documentation.md` once it
became clear AG Grid is a focused infrastructure replacement
that deserves its own segment rather than being bundled with
the documentation pass (now Segment 20).

## Goal

Replace the plain HTML `<input>` / `<textarea>` / `<select>`
reviewer-surface table at
`/reviewer/sessions/{id}/{instrument_position}` with an AG
Grid instance backed by the existing render adapter +
`POST /save` endpoint. The replacement unlocks:

- **Cell-level autosave.** Live cell edits hit `/save`
  on blur (or debounced). The plain-table UX today uses
  form-based Save (per-page batch).
- **Large-table ergonomics.** Sticky headers, column
  resize / freeze, virtualised row rendering — useful for
  long reviewee lists.
- **Spec-compatible column-defs source.** Today's render
  adapter builds row dicts keyed by Display + Response
  field metadata; that dict shape becomes the implicit AG
  Grid column-defs source (per
  `spec/reviewer-surface.md` "AG Grid table + large-table
  ergonomics").

## Why a separate segment

- **Scope.** AG Grid is a substantial JS infrastructure
  change — bundle adoption, build pipeline, license posture
  for AG Grid Enterprise features. Folding it into Segment
  20 (documentation) would muddle two unrelated tracks.
- **Sequencing.** No other segment depends on AG Grid; AG
  Grid doesn't depend on any other not-yet-shipped segment.
  Can ship at any reasonable cadence.
- **Decision provenance.** Decided 2026-05-03 from
  Segment 11 Tier 2 §2.1 as still on the roadmap; carved
  into its own segment 2026-05-10.

## Likely scope (sketchy)

> Detail settles during PR scoping.

### Bundle adoption

- Today: no JS build pipeline; templates carry inline
  progressive-enhancement scripts.
- AG Grid: JS bundle + CSS file(s). Decide between AG Grid
  Community (free) and AG Grid Enterprise (license fee,
  grouping / pivots / row-master-detail). Community covers
  the cell-edit + autosave story; Enterprise may light up
  better grouping for multi-instrument grids.

### Reviewer-surface integration

- Reviewer-surface template (`reviewer/review_surface.html`)
  gains a `<div id="rs-grid">` per instrument; inline JS
  loads AG Grid + mounts each grid against a JSON payload
  built from today's row dicts.
- `views.build_reviewer_surface_context` returns the same
  shape it does today; the template chooses between the
  HTML `<table>` (legacy) and the AG Grid mount (new) via
  feature-flag.

### Autosave wiring

- Cell `valueChanged` handler debounces (e.g. 500ms) then
  posts to the existing `POST /save` route.
- Per-cell status indicator: in-flight / saved / failed.
  Spec at `spec/reviewer-surface.md` covers the UX shape.
- Conflict resolution: same as today — last write wins;
  the `responses.value_version` column gates concurrent
  saves.

### Multi-instrument grouping

- Each instrument's page renders its own AG Grid mount.
  Multi-instrument navigation (Page #N buttons, server-
  rendered per-instrument groups) stays — AG Grid mounts
  one grid per page, not one grand grid spanning pages.
- AG Grid Enterprise row-master-detail could collapse all
  instruments into a single grid; defer to a follow-on
  segment if the spec demands it.

### Spec absorption

- `spec/reviewer-surface.md` already has "AG Grid table +
  large-table ergonomics" sketched; Segment 17 promotes
  that section to a locked spec contract as part of the
  rollout.

## Out of scope

- **Operator-side AG Grid.** Setup-page Manage tables stay
  HTML `<table>` for now — 15F's inline-edit machinery is
  the operator-side approach. AG Grid on the operator side
  is a separate future segment if pilot feedback demands it.
- **Print / PDF export of the grid.** Not a current ask;
  defer.
- **Custom cell renderers beyond the existing Display +
  Response field types.** AG Grid supports rich renderers
  but Segment 17 sticks to the field-type vocabulary the
  spec already covers (`String`, `Integer`, `Decimal`,
  `List`).

## Working notes / open questions

- _(placeholder)_
- AG Grid Community vs Enterprise — license-fee posture
  needs a deployment-side conversation before scoping.
- Feature-flag rollout: behind an env var? Per-session
  toggle? Probably env var (off by default) until the
  pilot validates the UX.
- The vanilla-JS autosave originally tracked alongside AG
  Grid bundles into this segment's cell-edit lifecycle —
  cell autosave is just AG Grid autosave with the same
  endpoint.

## Related context

- **`spec/reviewer-surface.md`** — covers the reviewer-
  surface contract; AG Grid section is sketched and
  Segment 17 promotes it to locked spec.
- **Workplan §11 / archived Segment 8 plan** — original
  AG Grid framing that never landed.
- **Segment 11 Tier 2 §2.1** (2026-05-03 decision log) —
  recorded AG Grid as still-on-roadmap.
