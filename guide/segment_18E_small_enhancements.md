# Segment 18E — Small enhancements

> **Stub created 2026-05-17** as part of the Segment 18
> (Session lifecycle adjacencies) family. Siblings: **18A**
> (Sessions lobby enhancements — cloning / tagging /
> archiving, `guide/segment_18A_sessions_lobby_enhancements.md`),
> **18C** (Retention / deletion workflow,
> `guide/segment_18C_retention_deletion.md`), and **18D**
> (Export and import update,
> `guide/segment_18D_export_and_import_update.md`).

**Stub. Sketch-level scope only.** Detailed PR breakdowns
get drafted when this segment is picked up.

## Goal

A holding pen for small, self-contained operator-surface
enhancements that don't warrant a segment of their own —
each one a single small PR, landed independently. Items
accumulate here as they surface during other work; the
segment is "picked up" by draining whatever is in the list
at the time, not by building a fixed scope.

## Scope (sketch)

### Part 1 — Reuse the tag-filter chip mechanism on the Setup pages

**Context.** Segment 18A Part 2 introduces a tag-filter
strip on the Sessions lobby: clickable chips that show /
hide table rows by tag membership. The mechanism is a pure
client-side JS toggle over already-rendered rows — chips
stamped with a selector, rows stamped with `data-` markers,
no schema and no server round-trip.

The **Reviewers / Reviewees / Relationships** Setup pages
already have info cards that report **which columns hold
data**. The same chip mechanism applies cleanly there, with
one shape difference: the lobby filters *rows* by tag
membership, whereas the Setup pages would toggle *column*
visibility — clicking a column-name chip shows / hides that
column of the already-rendered preview table.

**Goal.** Let the operator collapse empty / uninteresting
columns on the preview tables by clicking the column chips
the info card already renders, so a wide roster table can
be narrowed to the columns that matter.

Likely shape:

- Generalise the 18A tag-filter script into a small generic
  helper — "chip toggles the elements matching its
  selector" — rather than one bespoke filter function. The
  lobby uses it for row visibility; the Setup pages use it
  for column visibility.
- The Setup-page info cards make their existing
  column-presence readout the clickable chip set. A column
  with no data starts hidden (or starts shown — decide at
  scoping); a `Clear all` / `Select all` chip mirrors the
  lobby's toggle.
- No schema: column-presence is already computed for the
  current info cards; visibility is CSS class toggling on
  `<col>` / `<td>` / `<th>` elements.
- Tradeoff to settle at scoping: client-side only covers
  rows / columns already rendered (fine while these tables
  aren't paginated) and state resets on reload unless
  mirrored into a query param.

## Hard dependencies

- **Part 1** wants the 18A Part 2 tag-filter script as the
  generalisation base. It can also ship standalone (the
  generic helper written first, the lobby refactored onto
  it second) if 18E is picked up before 18A Part 2.

## Out of scope

- Anything that needs a schema change — those belong with
  their data-owning segment.
- Large multi-PR features — if an item grows past a single
  small PR it graduates to its own segment.

## Doc impact

When parts ship:

- `docs/status.md` timeline entry per Part.
- `guide/todo_master.md` updated.
- `spec/setup_pages.md` — column-toggle behaviour on the
  preview tables, if Part 1 ships.
- `spec/sessions_overview.md` — cross-reference to the
  shared chip-toggle helper if the lobby is refactored
  onto it.

## Working notes

- _(placeholder for decisions during PR scoping)_
- **Item intake.** New small-enhancement ideas land here as
  additional Parts as they surface, rather than spawning
  one-off segment stubs.
