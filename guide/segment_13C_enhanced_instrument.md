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

> **Revised 2026-05-19 — group-boundary tags.** A reviewer's
> group is no longer their *whole* rule-eligible set. The pinned
> rule selects the **universe** (which reviewees a reviewer
> interacts with); a new **Group** checkbox column on the Display
> Fields table marks the reviewee / pair-context tags whose
> shared values **partition** that universe into the groups the
> reviewer actually rates (additive — members share every ticked
> tag's value). The boundary spec is stored in the existing
> `group_kind` column (still **no migration**). This re-cuts the
> PR ladder below: a Group-column editor slice lands before the
> reviewer surface, and the surface / fan-out / aggregation are
> all group-key-aware. See
> [`spec/group_scoped_instruments.md`](../spec/group_scoped_instruments.md)
> for the canonical design.

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

In progress. **PR 1 — the operator-side group-scoped instrument
editor — shipped 2026-05-18** (#1176-#1181, atop the placeholder
slices #1161-#1175). PR 2 slice 1 — the reviewer write fan-out —
shipped 2026-05-18 (#1183); it pre-dates the group-boundary
revision and fans across the reviewer's whole universe, so it
needs a group-key-aware follow-up (PR 2 slice B below). The
Group-column editor, the partition-aware reviewer surface, and
PR 3 (Replicate) remain. **Zero migrations.**

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

### PR 1 — landed (2026-05-18)

The operator-side group-scoped instrument editor shipped across
small slices:

- Row-set locked to the populated tag rows + Name (#1176).
- Rule-required gate — a group instrument can't accept responses
  without a pinned rule (#1177).
- RevieweeName locked-row relaxation in `bulk_save_fields` (#1178).
- Editable Display Fields — Include checkboxes (#1179) and the
  Sort tri-state control (#1180).
- Editable Response Fields + Response Fields Help, via shared
  `response_fields_table` / `_help_table` / `_templates` macros
  reused from the ordinary card (#1181).

### PR 2 slice 1 — write fan-out — landed (2026-05-18)

`responses._expand_group_upserts` / `_group_instrument_ids`
(#1183) fan a reviewer's saved answer to one `Response` row per
member assignment. **Pre-dates the group-boundary revision** — it
fans across every assignment the reviewer has for the instrument
(the whole universe). Correct only while no instrument sets a
boundary tag; PR 2 slice B re-scopes it to the boundary-defined
group.

### Remaining work — two PRs, no migration

The PRs below are the reviewer-facing feature (PR 2) and the
Replicate button (PR 3, independent).

**Related (separate matter).** The Rule Builder predicate-editor
field-selector reordering — reviewee tags, then pair-context
tags, reviewer tags omitted — and the `pair.*` predicate
vocabulary it implies are specced in `spec/rule_based_assignment.md`
§4.4 / §7.2. The `pair.*` address space is a new engine
capability, scoped separately; confirm before implementing.

### PR 1 — Group-scoped instrument editor — **done** (#1176-#1181)

The group-scoped card is editable: one bulk-save round-trip,
mirroring the ordinary instrument card's Edit / Save / Cancel
state machine. What shipped:

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
    identity). `bulk_save_fields` skips the locked-row `visible`
    force when `instrument.group_kind` is set, so a group
    instrument stores Name's Include state.
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

### PR 2 — Reviewer surface: group-boundary editor + group blocks + aggregation

The reviewer-facing feature, re-cut into slices by the
2026-05-19 group-boundary revision. Slice 1 (write fan-out) has
landed; the remaining slices are below.

**Slice A — Group-boundary editor (operator-only).** Add the
**Group** checkbox column to the group-scoped Display Fields
table, between Include and Sort. Ticking it on a tag row marks
that tag a boundary key; the Name row has no Group cell. On save,
the ticked tags' key-codes (`r1`-`r3`, `p1`-`p3`) are encoded —
ordered by the Sort spec — into the `group_kind` column,
replacing the inert `"both"` marker; a group instrument with no
boundary tag keeps `"both"` as the no-partition sentinel. Add the
encode/decode helper and a helper line under the table. No
reviewer-visible change — safe to land alone.

**Slice B — write fan-out re-scope.** `_expand_group_upserts`
(shipped in slice 1) fans across the reviewer's whole universe;
re-scope it to fan only within the boundary-defined group the
answer was submitted for. Coupled to slice C (which supplies the
per-group input grouping).

**Slice C — reviewer surface render.** Render a group-scoped
instrument as a self-contained block — **one row per group**, the
universe partitioned by the boundary tags (one row when no
boundary tag is set). Each row carries a **group-identity
column** composed from the Included Display Fields rows (reviewee
tags, then pair-context tags, then member names — each
comma-separated on its own line) and one set of response inputs.
A boundary tag always renders a single crisp value; a varying
non-boundary Included tag renders its distinct values
comma-separated. The preview hub renders the same block.

**Slice D — aggregation sweep.** `responses.collapse_group_duplicates(rows)`
keyed on `(reviewer_id, instrument_id, group_key, response_field_id)`
+ the mandatory sweep migrating every aggregator — Manage
Invitations Review Progress, Responses page coverage, Extract
Data exports — see "Aggregation contract" below. Extract Data
collapses per-member rows to one row per group and surfaces the
composed group identity in place of per-reviewee identity
columns.

No rule-engine change — the rule emits ordinary
`(reviewer, reviewee)` assignments; the surface partitions and
collapses on read and the submit path fans within a group on
write.

> **Over-count window.** Slices B-D must land together (or
> group-scoped instruments stay un-openable to reviewers until D
> lands). Slice A is operator-only and lands independently first.

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
  **any non-null value** flags the instrument group-scoped. PR 2
  slice A starts **interpreting** the value: it encodes the
  group-boundary spec — an ordered, comma-separated list of
  boundary tag-key codes (`r1`-`r3`, `p1`-`p3`), e.g. `r1,p2`. A
  group instrument with no boundary tag keeps the `"both"`
  sentinel so the column stays non-null. Six codes + commas = 17
  chars, inside `String(32)`. No migration.
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

The pinned rule selects a reviewer's **universe** — their
`Assignment` rows for the instrument, exactly as for a
per-reviewee instrument. The instrument's **boundary tags** (the
Group column, encoded in `group_kind`) then partition that
universe into the **groups** the reviewer rates: two reviewees
share a group iff they share a value for every boundary tag
(additive). With no boundary tag the universe is one group.

- The reviewer surface partitions the reviewer's assignment set
  by the boundary-tag values into one row per group on read.
- The submit path fans the single answer to one `Response` row
  per member assignment **of that group** on write.
- `collapse_group_duplicates` collapses those member rows back to
  one per group, keyed on `(reviewer_id, instrument_id,
  group_key, response_field_id)`.

`Full Matrix` with no boundary tag makes every reviewer's group
every reviewee; a boundary tag splits it. The rule defines the
universe; the boundary tags define the cut.

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

PR 2 slice D introduces `responses.collapse_group_duplicates(rows)`
per the spec. It collapses the N group-duplicate response rows to
one **per group**, keyed on `(reviewer_id, instrument_id,
group_key, response_field_id)` — `group_key` being the
boundary-tag value tuple (empty when the instrument has no
boundary tag). Every consumer that aggregates by reviewee or
reports "completion" routes through the helper:

- `views.build_invitations_rows` — Review Progress column.
- `views.build_responses_rows` — Responses page coverage.
- Extract Data exports (the per-entity + unified exporters).

The contract: a single group response counts as **one completion
per group**, not N per member, and an instrument with K
boundary-defined groups counts K completions. The test suite
gains a shared fixture (a group-scoped instrument with a boundary
tag, multiple groups, and one rendered response per group) +
assertions against each consumer's output. The sweep over every aggregator is
**mandatory** — missing one means an export over-counts group
responses by the group size. Pin this note in the PR 2
description.

## Out of scope

- **Per-question group scope** — a whole instrument is one mode.
- **Tags as membership** — boundary tags only *partition* a
  rule-selected universe; they never add or remove reviewees.
  Membership is always the rule's job. The superseded
  pre-2026-05-18 design used a composite `group_kind` of tag keys
  *as the membership mechanism with no rule* — that conflation
  stays out of scope, not the use of tags to draw a boundary.
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
  with the Include, **Group**, and Sort columns).
- Update `spec/reviewer-surface.md` for the group-block
  treatment — one row per boundary-defined group (PR 2).
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
