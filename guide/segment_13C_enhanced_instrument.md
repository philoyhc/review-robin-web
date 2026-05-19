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
> interacts with); a new **Group by** checkbox column on the
> Display Fields table marks the reviewee / pair-context tags
> whose shared values **partition** that universe into the groups
> the reviewer actually rates (additive — members share every
> ticked tag's value). A constrained **Include** column governs
> what shows: boundary tags are locked Included, non-boundary
> tags are not Includable, only the Name row is free. The boundary spec is stored in the existing
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
needs a group-key-aware follow-up (PR 2 slice B below). PR 2
slice A — the Group-boundary editor column — shipped 2026-05-19.
Slice B — the boundary-scoped write fan-out — shipped 2026-05-19.
Slice C — the partition-aware reviewer surface render — shipped
2026-05-19. Slice D — the aggregation sweep (D1 reviewer-state
rollup + D2 Extract Data collapse) — shipped 2026-05-19, closing
the over-count window. PR 3 (Replicate) — shipped 2026-05-19.
The "harmonize the normal instrument card" follow-on remains.
**Zero migrations.**

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

**Slice A — Group-boundary editor (operator-only) — done.** The
group-scoped Display Fields table gained a **Group by** checkbox
column (tag rows only; the Name row shows an em-dash). The
**Include** column is now *constrained by Group by*: tag-row
Include is derived from — and live-mirrors — the Group-by tick
(disabled), only the Name row's Include stays a free checkbox. On
save the Group-by ticks' key-codes (`r1`-`r3`, `p1`-`p3`) are
encoded — ordered by display-field order — into the `group_kind`
column; a group instrument with no boundary tag keeps `"both"`
as the no-partition sentinel. What shipped:

- `encode_group_kind` / `decode_group_kind` / `group_boundary_pairs`
  pure helpers + `set_group_boundary` mutator (audit
  `instrument.group_boundary_updated`, registered in `EVENT_SCHEMAS`)
  in `app/services/instruments/_instrument_crud.py`.
- The bulk-save route folds `group_by_ids` into `visible_ids` for
  group instruments (tag-row Include == Group-by) and calls
  `set_group_boundary`.
- `build_instruments_context` now `expire_all()`s after the
  lazy-seed commit so a group instrument created after the
  reviewee import renders its freshly-seeded tag rows on the same
  request (the session runs `expire_on_commit=False`).

No reviewer-visible change.

**Slice B — write fan-out re-scope — done (2026-05-19).**
`_expand_group_upserts` (shipped in slice 1) fanned across the
reviewer's whole universe; it now fans only within the
boundary-defined group. New `_group_key_by_assignment` helper in
`responses.py` computes each assignment's group key — the tuple
of boundary-tag values for its `(reviewer, reviewee)` pair
(reviewee tags off the reviewee, pair-context tags off the active
`Relationship`) — and the fan-out / dedup are keyed on
`(instrument, group_key, field_key)`. A group instrument with no
boundary tag still yields one group (empty key), so the
no-boundary case is unchanged.

**Slice C — reviewer surface render — done (2026-05-19).** The
reviewer surface collapses a group-scoped instrument's
per-assignment rows into **one row per boundary-defined group**.
`responses.group_keys` (public wrapper over the slice-B group-key
helper) partitions a reviewer's rows; `_collapse_group_rows` in
`_surface.py` keeps the lowest-id member as the representative
(response inputs key off it; the slice-B fan-out spreads the
answer) and builds a `group_identity` block — boundary tag values
plus, when the RevieweeName Display Field is Included, the member
names (first `GROUP_MEMBER_NAME_LIMIT` = 10, then `+N more`). The
template branches on `is_group`: a `Group` identity column
replaces `Reviewee` + display columns. Validation now runs on the
raw upserts before the fan-out so a bad group answer yields one
error, and `_compute_missing_required` reports one entry per
group. The operator preview builder still renders group
instruments per-reviewee — a noted follow-up.

> **Over-count window — closed (2026-05-19).** Slice C shipped
> ahead of D; slice D (D1 + D2 below) closed the window the same
> day.

**Slice D — aggregation sweep — done (2026-05-19).** Split in two:

- **D1 — reviewer-state rollup — done (2026-05-19).**
  `_state_from_assignments` (responses.py) collapses each
  group-scoped instrument's member assignments to one
  representative per `(instrument, group_key)`, so a group
  response counts once — not once per member — in
  `reviewer_session_state`, `reviewer_session_state_per_instrument`,
  the reviewer dashboard pill, `monitoring.per_reviewer_progress`,
  `summary_counts`, and the Manage Invitations Review Progress
  column. *Note:* `monitoring.per_reviewee_coverage` (Responses
  page) needs no change — it already counts per
  `(reviewer, reviewee)`, which is not over-counted by the
  fan-out.
- **D2 — Extract Data — done (2026-05-19).** `serialize_responses`
  collapses a group-scoped instrument's fanned-out per-member
  `Response` rows to one row per `(reviewer, instrument,
  group_key, field)`, with the composed group identity in
  `RevieweeName` (the other reviewee columns empty, per the
  operator's call) and `SelfReview=FALSE`. `session_response_count`
  (the Extract Data card's row tally) dedups the same way. The
  18D Part 3 instrument-flavour column rode along: an
  `InstrumentFlavour` column (`per-reviewee` / `group-scoped`)
  appended to the CSV — appended, not grouped with the other
  instrument columns, so existing 20-column analyst pipelines
  keep their indices.

No rule-engine change — the rule emits ordinary
`(reviewer, reviewee)` assignments; the surface partitions and
collapses on read and the submit path fans within a group on
write.

> **Over-count window.** Slices B-D must land together (or
> group-scoped instruments stay un-openable to reviewers until D
> lands). Slice A is operator-only and lands independently first.

### PR 3 — Replicate instrument button — done (2026-05-19)

Wired the placeholder `Replicate` action-row button:
`POST /sessions/{id}/instruments/{instrument_id}/replicate` →
`instruments.replicate_instrument`, which clones the source's
description, response fields (+ help), display fields (+ each
row's `visible` flag), `group_kind`, `sort_display_fields`, and
its assignment rows into a new `{name} (copy)` instrument slotted
immediately after the source — `accepting_responses=False`, no
`rule_set_id`. Audit event `instrument.replicated`.

Original plan:

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

### PR 4 — reviewer-group pair count on the rule card

*Planned 2026-05-19.* Resolves the "eligible-pair count" open
question in `spec/group_scoped_instruments.md`. The Instruments
page rule card shows "Number of eligible pairs found: N" — the
raw `(reviewer, reviewee)` count from
`evaluate_session_rule_eligibility`. For a **group-scoped**
instrument, append a secondary count in parentheses:
`Number of eligible pairs found: 240 (32 reviewer-group pairs)`.

- **Count.** `M` = number of distinct `(reviewer, group_key)`
  over the rule's eligible `result.pairs`, where `group_key` is
  the boundary-tag tuple decoded from the instrument's
  `group_kind`. It is **per-instrument** (boundary tags are an
  `Instrument` setting), so it cannot live in the per-rule
  `session_rule_sets` cache.
- **Resolution logic.** Reuse the boundary decode
  (`instruments.decode_group_kind`) and the per-pair tag
  resolution from `responses._group_key_by_assignment`
  (reviewee tags off the reviewee; pair-context tags off the
  active relationship). Factor the per-pair resolution into a
  shared helper if it reads cleanly. `evaluate_session_rule_eligibility`
  already has `reviewees` + `pair_context_lookup` in scope when
  it runs the engine.
- **Slice 4a — compute + display, no cache — done
  (2026-05-19).** `session_library.evaluate_instrument_group_pair_counts`
  returns `{instrument_id: group_pair_count}` for group-scoped
  pinned instruments — distinct `(reviewer, group_key)` over the
  rule's `result.pairs`, the boundary resolved by the shared
  `responses.group_key_for_pair` helper. Runs the engine for
  those rules (like 18E Part 2 PR 1's pinned-only state; the
  engine call is now factored into `_evaluate_rule_row`).
  `views/_instruments.py` rule-picker context carries
  `selected_group_pair_count: int | None`;
  `instruments_index.html` renders `(N reviewer-group pairs)`
  after the raw count, and the inline JS clears it while the
  dropdown is off the pinned rule.
- **Slice 4b — per-instrument persisted cache — done
  (2026-05-19).** Mirrors 18E Part 2 PR 2. Migration
  `c3a9f1d7b2e8` adds `cached_group_pair_count` +
  `cached_group_pair_stamp` to `instruments`; the stamp is a
  content-hash of roster + pinned-rule definition + `group_kind`
  (so a roster, rule, or boundary-tag edit invalidates it).
  `evaluate_instrument_group_pair_counts` returns the stored
  count on a stamp match with no engine run, and computes the
  engine result lazily once per pinned rule on a miss.

### PR 5 — grouping-tag-change defunct safeguard — done (2026-05-19)

Implements the safeguard decided in
`spec/group_scoped_instruments.md` Open Questions. When a
reviewee's grouping-tag value changes, the answer copies fanned
onto assignments that *point at them* become mis-attributed to
whatever group those rows re-derive into.

- **Trigger.** An **inline** reviewee edit
  (`reviewees.update_reviewee`) that changes a `tag_N` value.
  CSV reimport needs no safeguard — `csv_imports._save` is a
  full delete-and-replace, so a reimport already cascade-clears
  every assignment and response; only the in-place edit path
  leaves stale copies.
- **Action.** `responses.defunct_group_responses_for_tag_change`
  deletes the `Response` rows where the tag-changed reviewee is
  the reviewee, on the group-scoped instruments whose decoded
  `group_kind` boundary actually uses one of the changed tags.
  Lossless for reviewers — the answer survives redundantly on
  the group's other member rows. The defunct count rides on the
  triggering `reviewee.updated` audit event's `context`
  (`defuncted_group_responses`), mirroring how roster imports
  record `cascaded_assignments`.
- **Pair-context variant.** `relationships.update_relationship`
  gets the symmetric hook —
  `responses.defunct_group_responses_for_relationship_tag_change`
  deletes the group-scoped `Response` rows for the one
  `(reviewer, reviewee)` pair the relationship describes, on
  instruments whose boundary uses the changed pair-context tag.

Order: PR 4 first (4a, then 4b), then PR 5.

### Assignments-page refinement cards (planned 2026-05-19)

Two titleless half-width cards below the Per-instrument status
card, in a `.bottom-grid`, plus main-table changes — mirroring
the Reviewers / Reviewees / Relationships Setup-page info card
and operator-actions card.

- **Slice 1 — Card A, column-visibility card (left).** Replaces
  the inline field-selecting checkboxes
  (`.assignment-col-toggles`). Two rows like the Setup-page info
  card: "Fields with data:" friendly-label pills for the
  populated tag columns, then "Show columns:" pill chips
  (`tag-chip is-selected` / `is-disabled` for empty) toggling
  each of the nine tag columns (rt1-3 / et1-3 / p1-3). Reuses
  the existing `rrw-assignment-col-visibility` localStorage +
  `col-hidden-{slot}` CSS; only the chrome changes from
  checkboxes to chips, with the Setup pages' chip-click JS.
- **Slice 2 — Card B bulk actions (right) + row-select column.**
  A left-most checkbox column on the main table (+ select-all)
  feeding a hidden bulk form; Card B carries a "{n} selected"
  pill and Inactivate / Activate buttons. New
  `assignments.bulk_set_assignment_include` service flips
  `Assignment.include` on the selected rows (audit event); POST
  routes `assignments/bulk-inactivate` + `bulk-activate`.
- **Slice 3 — Card B search.** A single free-text "Search:"
  input matching reviewer **or** reviewee name / email
  (server-side), with "Showing X of M" + Clear / Apply —
  mirroring the Setup operator-actions filter row. `?filter_q=`
  preserved across reloads / bulk actions; the 200-row preview
  cap stays as a perf guard, applied after the filter.

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
  existing per-row flag, the **Include** checkbox. On a
  group-scoped instrument a tag row's `visible` follows its
  Group-by tick (locked on for boundary tags, off otherwise);
  the Name row's `visible` is the freely-chosen "list members"
  toggle. PR 1 wired Include; PR 2 slice A adds the Group-by
  constraint.
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
  with the **Group by**, Include, and Sort columns).
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
