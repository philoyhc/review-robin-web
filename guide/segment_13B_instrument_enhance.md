# Segment 13B — Instrument enhancements

Stub. Implementation plan for a basket of small instrument-card
improvements. Currently scoped to one item:

1. **Sort by reviewee** — operator-side default sort + reviewer-
   side live override. Functional spec at
   [`spec/sort_by_reviewee.md`](sort_by_reviewee.md).

Future instrument-card enhancements slot in here as additional
items rather than spawning new segments — the segment frames
"things that improve the per-instrument operator card or the
reviewer-surface table for that instrument."

> **Renamed 2026-05-07** from "Segment 13B — Sort by reviewee" to
> "Segment 13B — Instrument enhancements" so the segment can
> absorb additional instrument-card improvements as they surface.
> Sort is the first item; future items slot in as separate PRs
> within this same segment.

## Status

Planning. Sized as TBD PRs — concrete sequencing lands when 13B
kicks off. The sort item already has rough implementation pointers
in `sort_by_reviewee.md` §"Implementation pointers (for
Segment 13)"; promote those into a PR-by-PR breakdown at start.

## Relationship to Segment 13A

13A and 13B are siblings, independent of each other and shippable
in either order. Together they cover what the original Segment 13
framing called "rule-based assignment builder + sort UX" in the
master workplan.

- **13A** — rule-based assignment generation (Advanced mode + seed
  library + editor + retire Full Matrix card). Plan at
  [`segment_13A_rulebased_assignment_builder.md`](segment_13A_rulebased_assignment_builder.md).
- **13B** (this segment) — instrument-card enhancements; sort is
  the first item.

The two segments touch different surfaces (assignments page vs
instruments page) and different data shapes (RuleSets vs
`Instrument.sort_display_fields`); no cross-dependencies.

## In scope (today)

### Sort by reviewee

Operator-side: tri-state Sort column on the per-instrument
Display Fields table — priority + direction, max 3 keys, display
fields only (no response fields, since no response data exists at
form-render time). Reviewer-side: clickable column headers for
live override across both display and response columns, live-only
persistence (no localStorage, no server-side per-reviewer state).

New `Instrument.sort_display_fields` JSON column with NULL default
— zero behaviour change for any existing session until an operator
explicitly configures sort. Audit event
`instrument.sort_fields_updated` mirrors the existing D11 diff
shape on `instrument.display_fields_saved`.

See [`sort_by_reviewee.md`](sort_by_reviewee.md) for the full
contract: storage shape, click semantics, cascade behaviour,
lifecycle gating, multi-instrument behaviour, audit detail, and
implementation pointers.

## Out of scope (today)

- **Anything not currently spec'd.** When a second
  instrument-enhancement candidate surfaces (a new column on the
  Display Fields table, a new Response Fields affordance, a new
  per-instrument knob), add it here as a separate item and size
  it as its own PR within 13B.
- **Sort spec extensions** beyond what `sort_by_reviewee.md` calls
  out (sort by computed values, cross-instrument session-wide sort,
  >3 sort keys, persisted reviewer overrides, mass "apply sort to
  every instrument"). Those are explicit out-of-scope items in the
  functional spec; revisit only if a real session needs them.

## Doc impact

When 13B kicks off:

- Promote the In-scope sort material into a PR-by-PR plan in this
  file (sized like the 12A / 13A plans).
- Update `spec/operator_ui_concept.md` Display Fields section to
  describe the Sort column.
- Update `spec/reviewer-surface.md` to describe the header-click
  override.
- Update `guide/todo_master.md` to move 13B from Upcoming to
  in-progress; move to Done when the last PR lands.
- Migrate this file to `guide/archive/` when 13B's last PR merges.
