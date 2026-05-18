# Segment 13C — Enhanced instruments

> **Re-scoped 2026-05-18 — rule-based group model.** Earlier
> drafts of 13C defined a group by clustering reviewees on their
> tag values (composite `group_kind`, derived tag-tuple
> `group_id`, multiple groups per instrument) and shipped zero
> migrations. That design is **superseded** by the canonical
> spec rewrite of the same date. A group is now defined by the
> instrument's **pinned rule**: each reviewer's eligible-reviewee
> set *is* their group, exactly one group per reviewer per
> group-scoped instrument. The PR ladder and schema section below
> were rewritten to match. See
> [`spec/group_scoped_instruments.md`](../spec/group_scoped_instruments.md)
> for the canonical design.

> **Revised 2026-05-18 — tag-composed identity.** A later
> iteration dropped the free-text "Group Description" — and its
> `reviewee_group_description` / `Instrument.group_description`
> columns and the Rule Builder box. The group's on-screen
> identity is now **composed from the reviewee / pair-context
> tags the operator marks Include** on the Display Fields table
> (plus optionally the member Name list). **13C ships no
> migration** — the existing `InstrumentDisplayField.visible`
> flag is the Include checkbox. The PR ladder, schema, and
> progress log below are re-cut to match.

Implementation plan for two additions to the per-instrument
operator card on `/operator/sessions/{id}/instruments`:

1. **Group-scoped instruments** — a second instrument flavour
   where one reviewer answer covers a group of reviewees rather
   than one. Layered on top of the canonical functional spec at
   [`spec/group_scoped_instruments.md`](../spec/group_scoped_instruments.md).
2. **Replicate instrument** — a small button on each instrument
   card that creates a near-copy of the instrument (description,
   display / response fields, response-fields-help, `group_kind`,
   sort spec). A convenience for operators who want a near-copy
   with a few tweaks.

Both additions converge on the same surface — the action row at
the bottom of each instrument card — so they ship together as
one segment.

## Status

In progress — re-scoped twice on 2026-05-18 (rule-based model,
then tag-composed identity). The operator-facing surfaces were
built first as **visual placeholders**; the remaining work is
**persistence wiring**, in three PRs. **Zero migrations.**

## Progress log

### Placeholders landed (2026-05-18)

Built deliberately as small slices — onscreen placeholders ahead
of the wiring:

- **Spec.** `spec/group_scoped_instruments.md` rewritten to the
  rule-based, then tag-composed model (#1161, #1172).
  `spec/rule_based_assignment.md` §7.2 specs the predicate-editor
  field-selector ordering (reviewee tags, then pair-context tags,
  reviewer tags omitted).
- **Rule Builder.** The editable "Friendly Description" box was
  renamed "Rule Description (optional)" (#1164-#1166). An interim
  "Reviewee Group Description" box was added, then removed when
  the free-text design was dropped (#1172).
- **Instruments page.** The per-instrument action row was revised
  to `Edit / (Save, Cancel)`, `Add instrument`, `Add group
  instrument`, `Replicate` (#1167). `Add group instrument`
  creates a real instrument with `group_kind="both"` (an inert
  marker — non-null = group-scoped). Its card was built out as a
  full visual placeholder (#1167-#1171): Section A (identity card
  with status pills in the heading + the Assignment Rule card),
  Section B (a Display Fields table, Response Fields, Response
  Fields Help), and Section E (Danger Zone + action row). The
  card is not editable yet. `Replicate` is a pure placeholder.
- **Plan.** A follow-on section was added to harmonize the
  ordinary instrument card with the group card's layout (#1171).

> **Placeholder drift.** The group card's Display Fields
> placeholder still shows the interim Group Description cell +
> two include-checkboxes. PR 1 reshapes it to the tag-composed
> form — an **Include** checkbox column over the tag rows + a
> Name row.

### Remaining work — three PRs, no migration

The PRs below wire persistence onto the placeholders. PR 1 is the
prerequisite for PR 2; PR 3 is independent.

**Related (separate matter).** The Rule Builder predicate-editor
field-selector reordering — reviewee tags, then pair-context
tags, reviewer tags omitted — and the `pair.*` predicate
vocabulary it implies are specced in `spec/rule_based_assignment.md`
§4.4 / §7.2. The `pair.*` address space is a new engine
capability, scoped separately; confirm before implementing.

### PR 1 — Group-scoped instrument editor

Make the group-scoped card editable — today it is a read-only
placeholder. One bulk-save round-trip, mirroring the ordinary
instrument card's Edit / Save / Cancel state machine.

- **Display Fields table.** Reshape the placeholder to the
  per-reviewee table restricted to the eligible **tag rows**
  (reviewee + pair-context tags) plus a single **Name** row.
  Columns: Friendly Label (read-only), **Include** (a checkbox
  per row, persisted to the existing `InstrumentDisplayField.visible`
  flag), and **Sort** (the 13B sort spec,
  `Instrument.sort_display_fields`). This replaces the interim
  Group Description cell + two checkboxes.
  - **RevieweeName is not a locked row here.** On a per-reviewee
    instrument Name (and Email) are locked `visible=True` —
    `bulk_save_fields` (`_response_fields.py`) force-sets them and
    `update_display_field` rejects hiding them. On a *group-scoped*
    instrument the Name row's Include is operator-choosable
    (unticking it drops the member-name list from the composed
    identity). PR 1 must make the locked-row `visible` force
    conditional on `instrument.group_kind is None` so a group
    instrument can store Name's Include state.
  - **Row set (locked).** The table shows only the **populated**
    reviewee + pair-context tag rows — the same eligibility rule
    as a per-reviewee instrument's Display Fields — followed by
    the Name row. No fixed seven-row scaffold: every offered row
    is an existing `InstrumentDisplayField` (seeded on import,
    pruned when its data goes away), so Include always has a real
    row to write `visible` to.
- **Response Fields + Response Fields Help** become editable,
  reusing the ordinary instrument card's response-field save
  path.
- **Rule-required gate.** A group-scoped instrument's
  `accepting_responses` cannot be turned on while `rule_set_id`
  is `NULL` — the service layer rejects the open with an inline
  banner pointing at the Assignments page. The rule is pinned
  through the existing Segment 15B per-instrument flow;
  `Full Matrix` is a valid pin.
- Mode is set at creation and is not toggleable (operators delete
  + recreate). Group creation continues to emit `instrument.created`
  (the placeholder `add-group` route already does); `group_kind`
  non-null distinguishes it — no new event type, no migration.

After PR 1 a group-scoped instrument is fully authorable and
generates ordinary `Assignment` rows; the reviewer surface still
renders them per-reviewee until PR 2. The `accepting_responses`
toggle (default `False`, plus the rule-required gate) keeps
reviewers from premature exposure in that interim.

### PR 2 — Reviewer surface: group block + write fan-out + aggregation sweep

The end-to-end reviewer-facing feature, landed as one PR so there
is never a window where group responses exist but aggregators
over-count them.

- A service helper collapses a reviewer's assignments for a
  group-scoped instrument into one logical group row.
- The reviewer surface renders a group-scoped instrument as a
  self-contained block — one group row, one **group-identity
  column** composed from the Display Fields rows the operator
  marked Include (reviewee tags, then pair-context tags, then
  member names — each comma-separated on its own line), one set
  of response inputs. The preview hub renders the same block.
- A selected tag that varies across the group's members renders
  its distinct values comma-separated (see the spec's "Composing
  the group identity").
- Submit fans the reviewer's single answer across all N
  assignments' response rows for the group.
- `responses.collapse_group_duplicates(rows)` + the mandatory
  sweep migrating every aggregator — Manage Invitations Review
  Progress, Responses page coverage, Extract Data exports — see
  "Aggregation contract" below.
- Extract Data: collapse per-member rows to one row per group;
  surface the composed group identity (Included tag values /
  member names) in place of per-reviewee identity columns.

No rule-engine change — the rule emits ordinary
`(reviewer, reviewee)` assignments; the surface does the collapse
on read and the submit path fans on write.

> **Sizing note.** PR 2 is the largest PR. Split into 2a
> (render + write fan-out) / 2b (aggregation sweep) **only** if
> the diff is unwieldy *and* group-scoped instruments are kept
> un-openable to reviewers until 2b lands — otherwise the
> over-count window opens. Default: one PR.

### PR 3 — Replicate instrument button

Wire the placeholder `Replicate` action-row button. A
server-side endpoint copies the instrument's description /
display fields (including each row's `visible` Include flag) /
response fields / response-fields-help / `group_kind` /
`sort_display_fields` into a new instrument inserted immediately
after the source. The new instrument's name is auto-generated
(`{source.name} (copy)`; operator renames if needed).
`accepting_responses` defaults to `False` on the copy regardless
of the source's state. The copy does **not** carry the source's
`rule_set_id` — a replicated group-scoped instrument starts
rule-less and the operator pins a rule before opening it. Audit
event `instrument.replicated` carries the source + new
instrument IDs.

Independent of PRs 1-2 — can land in any order relative to them.

## Action row

Every instrument card's action row carries this fixed button set
(shipped as placeholders, #1167):

| Button | When visible |
|---|---|
| `Edit` | Card is locked (no pending edits). |
| `Save` | Card is open for editing. |
| `Cancel` | Card is open for editing. Adjacent to Save. |
| `Add instrument` | Always visible. Creates a per-reviewee instrument inserted immediately after this one. |
| `Add group instrument` | Always visible. Creates a group-scoped instrument inserted immediately after this one. |
| `Replicate` | Always visible. Clones this instrument's content into a new card inserted immediately after the source. Wired in PR 3. |

`Edit` / `Save` / `Cancel` remain mutually exclusive; the three
create-flavour buttons are always present and never contend with
the editing-state machine. `Delete this instrument` lives in the
Danger Zone card.

## Follow-on — harmonize the normal instrument card

Once the group-scoped instrument card is fully implemented, the
**ordinary per-reviewee instrument card is reorganized to match
its layout** — a separate, self-contained follow-on step, landed
after the group-card work is done (not bundled into PRs 1-3).

The group-scoped card's placeholder build (Segment 13C, the
2026-05-18 slices) established a tidier card layout that the
ordinary card should converge on:

- **Status pills move into the card heading**, beside the
  instrument number — `accepting responses` / `not accepting`
  and `showing when closed` / `not showing when closed`.
- **The separate "This Instrument's Status" card is retired.**
  Its open / close and show / don't-show-when-closed buttons
  move next to `Edit` near the title.
- **The Assignment Rule card moves up into Section A**, taking
  the slot the status card vacated.
- **Section E pairs the Danger Zone (half-width, left) with the
  action-button row (right)** in one bottom grid.

Net effect: one card layout for both instrument flavours, the
difference being only the group-scoped card's reshaped Display
Fields table and `Group-scoped` chip. The shared Jinja macros
introduced during the group-card build (`instrument_action_row`,
`assignment_rule_card`, and the identity-card macros) already
make this convergence mostly a matter of pointing the ordinary
card at the same macros.

This follow-on touches only the operator Instruments page
template; no schema, route, or service change. Update
`spec/instruments.md` (the per-instrument card layout, Sections
A / C) when it lands.

## Schema

13C ships **zero migrations.** Every column it needs already
exists:

- **`Instrument.group_kind`** (`String(32) | NULL`) — exists,
  shipped inert in 13D PR 6. `NULL` = per-reviewee instrument;
  **any non-null value** flags the instrument group-scoped. The
  placeholder `add-group` route already writes the inert marker
  `"both"`; the string is not interpreted. PR 1 updates the
  model docstring.
- **`InstrumentDisplayField.visible`** (`Boolean`) — the
  existing per-row flag. On a group-scoped instrument it is the
  **Include** checkbox: which tag / Name rows compose the group
  identity. PR 1 wires the group editor to it.
- **`Instrument.rule_set_id`** (`ForeignKey | NULL`, Segment 15B)
  — the pinned rule. PR 1 adds the group-scoped rule-required
  gate on top; it does not change the column.
- **`Instrument.sort_display_fields`** (`JSON | NULL`, Segment
  13B) — the per-instrument sort spec; the group editor reuses
  it for the tag-row and member-name order.
- **No `Assignment` change.** The rule emits ordinary
  `(reviewer, reviewee)` rows.
- **No `Response` change.** `Response.assignment_id` stays
  strictly single-reviewee; the write path fans one answer to N
  ordinary single-assignment `Response` rows.
- **No RuleSet change.** The free-text Group Description (and its
  `reviewee_group_description` / `Instrument.group_description`
  columns) was dropped — see the top revision note.

## How a group is defined

A group-scoped instrument's group, for any reviewer, is **that
reviewer's `Assignment` rows for the instrument** — the set the
pinned rule made eligible. Exactly one group per reviewer per
group-scoped instrument. Nothing is stored or derived from tags:

- The reviewer surface collapses the reviewer's assignment set
  into one logical group row on read.
- The submit path fans the single answer to one `Response` row
  per member assignment on write.
- `collapse_group_duplicates` collapses those member rows back to
  one keyed on `(reviewer_id, instrument_id, response_field_id)`.

`Full Matrix` makes every reviewer's group every reviewee; a
predicate / quota rule narrows it. Either way the rule is the
sole definition of membership.

## Audit events

- **Group-scoped creation reuses `instrument.created`** — the
  placeholder `add-group` route already emits it; `group_kind`
  on the instrument distinguishes the flavour. No new event
  type, so no `EVENT_SCHEMAS` change for creation.
- `instrument.replicated` — emitted on the "Replicate" path
  (PR 3). Detail carries the source + new instrument ids + the
  field set copied, via the Segment 11K `audit.refs(...)`
  envelope. **New event type — register it in `EVENT_SCHEMAS`**
  or the strict-mode test gate rejects it.

## Aggregation contract for group-scoped responses

PR 2 introduces `responses.collapse_group_duplicates(rows)` per
the spec. It collapses the N group-duplicate response rows to
one, keyed on `(reviewer_id, instrument_id, response_field_id)`.
Every consumer that aggregates by reviewee or reports
"completion" routes through the helper:

- `views.build_invitations_rows` — Review Progress column.
- `views.build_responses_rows` — Responses page coverage.
- Extract Data exports (the per-entity + unified exporters).

The contract: a single group response counts as **one
completion** at the group-scoped-instrument level, not N. The
test suite gains a shared fixture (a group-scoped instrument with
N assignments and one rendered response) + assertions against
each consumer's output. The sweep over every aggregator is
**mandatory** — missing one means an export over-counts group
responses by the group size. Pin this note in the PR 2
description.

## Out of scope

- **Per-question group scope** — a whole instrument is one mode.
- **Tag-cluster grouping** — the superseded mechanism; do not
  reintroduce composite `group_kind` / derived tag tuples /
  multiple groups per instrument.
- **Mode-flipping after creation** — operators delete and
  recreate.
- **Manual CSV assignment mode for group-scoped instruments** —
  the rule is required, so assignment is always rule-driven.
- **A separate `Group` entity** — the group is a reviewer's
  assignment set.
- **A free-text group-description field** — dropped in favour of
  the tag-composed identity; the instrument's own friendly
  description carries any prose.
- **Cross-session instrument duplication / templates** — the
  Replicate button copies within a session only.

## Relationship to Segment 13A and 13B

13A (rule-based assignments — shipped), 13B (sort by reviewee),
and 13C are siblings. 13C now **depends on** 13B's
`sort_display_fields` mechanism (the group-scoped editor reuses
it) and on 15B's per-instrument `rule_set_id` (the pinned rule);
both have shipped.

## Doc impact

- Update `spec/instruments.md` Section C "Action row" for the
  three create-flavour buttons, and the Display Fields section
  for the group-scoped variant (the tag-rows + Name-row table
  with the Include column).
- Update `spec/reviewer-surface.md` for the group-block
  treatment (PR 2).
- `spec/rule_based_assignment.md` §7.2 already specs the
  predicate-editor field-selector ordering ahead of 13C; the
  `pair.*` predicate vocabulary (§4.4) is a flagged, separately
  scoped dependency.
- 13C adds **no columns**, so no `spec/settings_inventory.md`
  change is needed.
- Update `guide/todo_master.md` — move 13C to Done when PR 3
  lands.
- Migrate this file to `guide/archive/` when PR 3 merges.

## Ride-along — Segment 18D Part 3

Segment 18D handed its **Part 3** to 13C: once group-scoped
instruments exist, the analysis-facing Responses extract
(`extracts/responses_extract.py`) gains a derived `Instrument`
*flavour* column (per-reviewee vs group-scoped) so downstream
analysis can split the two without re-deriving from the schema.
Land it as a small ride-along in PR 2.
