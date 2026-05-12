# Segment 13C — Enhanced instruments

Implementation plan for two additions to the per-instrument
operator card on `/operator/sessions/{id}/instruments`:

1. **Group-scoped instruments** — a second instrument flavour
   where one reviewer answer covers a group of reviewees rather
   than one. Layered on top of the canonical functional spec at
   [`spec/group_scoped_instruments.md`](../spec/group_scoped_instruments.md).
2. **Duplicate instrument** — a small button on each instrument
   card that creates a new instrument with the same description
   / display fields / response fields / response-fields-help /
   `group_kind`. A convenience for operators who want a near-
   copy with a few tweaks (e.g. to author the per-reviewee twin
   of a group-scoped instrument, or to reuse an existing
   question set against a different scope).

Both additions converge on the same surface — the action row at
the bottom of each instrument card — so they ship together as
one segment.

## Status

Planning. Sized as **5 PRs** in dependency order:

1. **PR 1 — Schema + render path for group_kind.**
   `Instrument.group_kind` (`String(32) | NULL`) column +
   migration. Reviewer-surface render adapter reads it but
   nothing else changes yet (no creation flow, no per-card
   chip). Tests pin that today's per-reviewee instruments stay
   `group_kind=NULL` and render identically.
2. **PR 2 — Operator editor: "Add a group-scoped instrument".**
   New action-row button alongside the existing "Add new
   instrument". Inline dialog asks which reviewee tag (Tag 1 /
   Tag 2 / Tag 3) identifies the group; sets
   `group_kind="tag_1"` / etc. on creation. Group-scoped editor
   restricts display fields to the three reviewee tags; locks
   the chosen tag into position 0. Per-card chip reads
   "Group-scoped (by Tag 1)".
3. **PR 3 — Rule-engine fanout for group-scoped instruments.**
   FullMatrix (and any other rule that processes group-scoped
   instruments) clusters reviewees by their `tag_N` value and
   emits one `Assignment` per `(reviewer, group_member)` with
   `context = {"group_id": "team-alpha", "group_kind": "tag_1",
   "group_size": 5}` stamped on every row. Manual mode is
   disallowed for group-scoped instruments (rule mode only).
4. **PR 4 — Reviewer surface: group block + write fanout.**
   Group-scoped instrument renders as a self-contained block
   per group on the reviewer surface (group identity row
   showing the source-tag value + member names). Single set of
   response inputs; submit fans the same value across all N
   `Assignment`'s response rows that share `context.group_id`.
   New aggregation helper
   `responses.collapse_group_duplicates(rows)` and migration of
   every aggregator that reads response data (Manage
   Invitations, Responses page, Extract Data exports) through
   it.
5. **PR 5 — Duplicate instrument button.** New "Duplicate
   instrument" action-row button. Server-side endpoint copies
   the instrument's description / display fields / response
   fields / response-fields-help / `group_kind` /
   `sort_display_fields` (if 13B has shipped) into a new
   instrument inserted immediately after the source. The new
   instrument's name is auto-generated (`{source.name} (copy)`
   or similar; operator renames if needed). `accepting_responses`
   defaults to `False` on the copy regardless of the source's
   state. New audit event `instrument.duplicated` carries the
   source + new instrument IDs.

PRs 1-4 ship the group-scoped feature end-to-end; PR 5 is
independent and can land in any order relative to PRs 1-4 (it
doesn't depend on `group_kind`, but it does need to copy the
column once 13C PR 1 lands). For dependency safety, PR 5 lands
after PR 1.

## Action row at the end of 13C

By the time PR 5 ships, every instrument card's action row
carries this fixed button set (left card, per
`spec/instruments.md` Section C):

| Button | Modifier | When visible |
|---|---|---|
| `Edit` | Alert | Card is locked (no pending edits). |
| `Save` | Primary | Card is open for editing. |
| `Cancel` | Alert Outline | Card is open for editing. Adjacent to Save. |
| `Add new instrument` | Secondary | Always visible. Existing today. Creates a per-reviewee instrument inserted immediately after this one. |
| `Add group-scoped instrument` | Secondary | Always visible. **New (PR 2).** Creates a group-scoped instrument inserted immediately after this one. |
| `Duplicate instrument` | Secondary | Always visible. **New (PR 5).** Clones this instrument's content; new card inserted immediately after the source. |

`Edit` / `Save` / `Cancel` remain mutually exclusive per the
existing spec; the three create-flavour buttons (`Add new`,
`Add group-scoped`, `Duplicate`) are always present and never
contend with the editing-state machine.

`Delete this instrument` continues to live in the right-hand
Danger Zone card per `spec/instruments.md` Section C.

## Schema additions

| Field | Where | Type | Notes |
|---|---|---|---|
| `group_kind` | `Instrument` | `String(32) | NULL` | `NULL` = today's per-reviewee instrument. Non-null = group-scoped. Stored value is the source-field key (`tag_1` / `tag_2` / `tag_3`); the operator-facing display label ("Group-scoped (by Tag 1)") lives in template copy. |
| `Assignment.context` (existing) | `Assignment` | `JSON | NULL` | Already on the model. New documented keys for group-scoped assignments: `group_id` (string, typically the source-tag's value), `group_kind` (mirror of the instrument's), `group_size` (int). |

No `Response` schema change. The duplicate-and-stamp trick on
`Assignment.context` carries the whole feature without touching
`Response.assignment_id`'s single-reviewee shape.

## Audit events

- `instrument.created_group_scoped` — emitted on the "Add a
  group-scoped instrument" path. Mirrors today's
  `instrument.created` shape; detail carries the chosen
  `group_kind`.
- `instrument.duplicated` — emitted on the "Duplicate
  instrument" path. Detail carries the source instrument id +
  the new instrument id + the field set copied. Uses the
  Segment 11K `audit.refs(...)` envelope for the cross-entity
  link.

`instrument.created` (today's event for Add-new) stays
unchanged on the per-reviewee path.

## Out of scope

- **Per-question group scope** — rejected by the spec.
- **Multi-level grouping in one instrument** — `group_kind`
  stays a scalar.
- **Mode-flipping after creation** — operators delete and
  recreate.
- **Manual CSV mode for group-scoped instruments** — rule mode
  only first cut.
- **A separate `Group` entity** — the group identifier is just
  a tag value.
- **Cross-session instrument duplication / templates** — the
  duplicate button copies *within a session* only. A "save
  this instrument as a template" feature is a separate concern
  if it ever surfaces.

## Aggregation contract for group-scoped responses

PR 4 introduces `responses.collapse_group_duplicates(rows)` per
the spec. Every consumer that aggregates by reviewee or reports
"completion" routes through the helper:

- `views.build_invitations_rows` — Review Progress column.
- `views.build_responses_rows` — Responses page coverage.
- Extract Data exports (whichever per-entity / unified
  exporters land in 12A).

The contract: a single group response counts as **one
completion** at the group-scoped-instrument level, not N. The
test suite gains a single shared fixture (a group-scoped
instrument with N assignments and one rendered response) +
assertions against each consumer's output.

The work in PR 4 includes a sweep over every aggregator
identified above; missing one means an export over-counts
group responses by `group_size`. Reviewer's note pinned in the
PR description: this sweep is mandatory.

## Relationship to Segment 13A and 13B

13A, 13B, and 13C are siblings — independent of each other,
shippable in any order. See
[`segment_13B_sort_tables.md`](segment_13B_sort_tables.md)
"Relationship to Segment 13A and 13C" for the per-segment
surface map.

## Doc impact

When 13C kicks off:

- Promote each PR's scope into per-PR descriptions in this
  file (sized like the 13A / 13B plans).
- Update `spec/instruments.md` Section C "Action row" to
  describe the two new buttons (Add group-scoped instrument,
  Duplicate instrument) and the post-13C button set.
- Update `spec/reviewer-surface.md` to describe the group-block
  treatment for group-scoped instruments.
- Update `guide/todo_master.md` to move 13C from Upcoming to
  in-progress; move to Done when PR 5 lands.
- Migrate this file to `guide/archive/` when PR 5 merges.
- `spec/group_scoped_instruments.md` ticks off when each
  Open question / Out-of-scope item from its design spec
  resolves.
