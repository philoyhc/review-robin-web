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

Implementation plan for two additions to the per-instrument
operator card on `/operator/sessions/{id}/instruments`:

1. **Group-scoped instruments** — a second instrument flavour
   where one reviewer answer covers a group of reviewees rather
   than one. Layered on top of the canonical functional spec at
   [`spec/group_scoped_instruments.md`](../spec/group_scoped_instruments.md).
2. **Duplicate instrument** — a small button on each instrument
   card that creates a new instrument with the same description /
   display fields / response fields / response-fields-help /
   `group_kind`. A convenience for operators who want a near-copy
   with a few tweaks.

Both additions converge on the same surface — the action row at
the bottom of each instrument card — so they ship together as
one segment.

## Status

Planning — re-scoped 2026-05-18 to the rule-based group model.
**3 PRs, one migration.** The migration (PR 1) adds
`reviewee_group_description` to the two RuleSet tables; everything
else reuses columns that already exist (`Instrument.group_kind`,
`Instrument.rule_set_id`, `Instrument.sort_display_fields`).

### PR 1 — Operator editor: "Add a group-scoped instrument"

New action-row button alongside the existing "Add an instrument".
Creates a group-scoped instrument with `group_kind` set to the
default display choice (`both` — rule summary followed by the
member list); inserted immediately after the current card.

- **Schema.** One migration: nullable `reviewee_group_description`
  (`Text`) on `operator_rule_sets` **and** `session_rule_sets`.
  Update the `Instrument.group_kind` model docstring to record
  the repurposed meaning (display-content choice, not tag keys).
- **Seeded rulesets.** Add a `reviewee_group_description` to each
  of the five seeded RuleSets in `app/services/rules/seeds.py`
  (and the `RuleSetSchema` it deserialises into), using the
  seeded values tabled in `spec/rule_based_assignment.md` §5.4 —
  e.g. *Full Matrix* → "All reviewees", *Intra-group peer review*
  → "All reviewees with the same tag1 as reviewer". The
  `materialise_seed_rule_sets` writer carries the value onto each
  new `session_rule_sets` row.
- **Editor.** For a group-scoped instrument the Display Fields
  table is replaced by a single **Group display** control —
  `members` / `summary` / `both`, persisted to `group_kind`. The
  standard sort spec (`Instrument.sort_display_fields`, the 13B
  mechanism) is kept and editable. A "Group-scoped" chip renders
  near the card heading.
- **Rule-required gate.** A group-scoped instrument's
  `accepting_responses` cannot be turned on while `rule_set_id`
  is `NULL` — the service layer rejects the open with an inline
  banner pointing at the Assignments page. The rule itself is
  pinned through the existing Segment 15B per-instrument flow;
  `Full Matrix` is a valid pin.
- **Rule Builder.** The Rule Builder page
  (`spec/rule_based_assignment.md` §7.2) gains a
  `reviewee_group_description` field alongside the RuleSet name /
  description.
- Mode is set at creation and is not toggleable (operators delete
  + recreate).
- Audit event `instrument.created_group_scoped`.

After PR 1, group-scoped instruments can be authored and generate
ordinary `Assignment` rows; the reviewer surface still renders
them per-reviewee until PR 2. The `accepting_responses` toggle
(default `False`, plus the rule-required gate) keeps reviewers
from premature exposure in that interim.

### PR 2 — Reviewer surface: group block + write fan-out + aggregation sweep

The end-to-end reviewer-facing feature, landed as one PR so there
is never a window where group responses exist but aggregators
over-count them.

- A service helper collapses a reviewer's assignments for a
  group-scoped instrument into one logical group row.
- The reviewer surface renders a group-scoped instrument as a
  self-contained block — one group row, one group column
  (member names / rule summary / both per `group_kind`), one set
  of response inputs. The preview hub renders the same block.
- The `summary` / `both` content resolves the group summary as
  `reviewee_group_description`, falling back to the RuleSet's
  `description` when that is blank.
- Submit fans the reviewer's single answer across all N
  assignments' response rows for the group.
- `responses.collapse_group_duplicates(rows)` + the mandatory
  sweep migrating every aggregator — Manage Invitations Review
  Progress, Responses page coverage, Extract Data exports — see
  "Aggregation contract" below.
- Extract Data: collapse per-member rows to one row per group;
  surface the group (member list / rule summary) as a column in
  place of per-reviewee identity columns.

No rule-engine change — the rule emits ordinary
`(reviewer, reviewee)` assignments; the surface does the collapse
on read and the submit path fans on write.

> **Sizing note.** PR 2 is the largest PR. Split into 2a
> (render + write fan-out) / 2b (aggregation sweep) **only** if
> the diff is unwieldy *and* group-scoped instruments are kept
> un-openable to reviewers until 2b lands — otherwise the
> over-count window opens. Default: one PR.

### PR 3 — Duplicate instrument button

New "Duplicate instrument" action-row button. A server-side
endpoint copies the instrument's description / display fields /
response fields / response-fields-help / `group_kind` /
`sort_display_fields` into a new instrument inserted immediately
after the source. The new instrument's name is auto-generated
(`{source.name} (copy)`; operator renames if needed).
`accepting_responses` defaults to `False` on the copy regardless
of the source's state. The copy does **not** carry the source's
`rule_set_id` — a duplicated group-scoped instrument starts
rule-less and the operator pins a rule before opening it. Audit
event `instrument.duplicated` carries the source + new instrument
IDs.

Independent of PRs 1-2 — can land in any order relative to them.

## Action row at the end of 13C

By the time PR 3 ships, every instrument card's action row
carries this fixed button set (left card, per `spec/instruments.md`
Section C):

| Button | When visible |
|---|---|
| `Edit` | Card is locked (no pending edits). |
| `Save` | Card is open for editing. |
| `Cancel` | Card is open for editing. Adjacent to Save. |
| `Add new instrument` | Always visible. Existing today. Creates a per-reviewee instrument inserted immediately after this one. |
| `Add group-scoped instrument` | Always visible. **New (PR 1).** Creates a group-scoped instrument inserted immediately after this one. |
| `Duplicate instrument` | Always visible. **New (PR 3).** Clones this instrument's content; new card inserted immediately after the source. |

`Edit` / `Save` / `Cancel` remain mutually exclusive per the
existing spec; the three create-flavour buttons are always
present and never contend with the editing-state machine.
`Delete this instrument` continues to live in the right-hand
Danger Zone card.

## Schema

13C ships **one migration** (PR 1):

- **`reviewee_group_description`** — new nullable `Text` column on
  `operator_rule_sets` *and* `session_rule_sets`. Operator-authored
  plain-English description of the group the rule forms; the
  `summary` display content, with a name / description fallback.
  Lives on both tables, mirroring how `description` is carried on
  both the library row and the per-session copy.

Columns reused as-is (no migration):

- **`Instrument.group_kind`** (`String(32) | NULL`) — exists,
  shipped inert in 13D PR 6. **Repurposed:** `NULL` =
  per-reviewee instrument; a non-null value flags the instrument
  group-scoped and stores the display-content choice
  (`members` / `summary` / `both`). PR 1 is the first writer and
  updates the model docstring.
- **`Instrument.rule_set_id`** (`ForeignKey | NULL`, Segment 15B)
  — the pinned rule. PR 1 adds the group-scoped rule-required
  gate on top; it does not change the column.
- **`Instrument.sort_display_fields`** (`JSON | NULL`, Segment
  13B) — the per-instrument sort spec; a group-scoped instrument
  reuses it unchanged for both member-name order and group-row
  order.
- **No `Assignment` change.** The rule emits ordinary
  `(reviewer, reviewee)` rows.
- **No `Response` change.** `Response.assignment_id` stays
  strictly single-reviewee; the write path fans one answer to N
  ordinary single-assignment `Response` rows.

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

- `instrument.created_group_scoped` — emitted on the "Add a
  group-scoped instrument" path. Mirrors today's
  `instrument.created` shape; detail carries the initial
  `group_kind` display choice.
- `instrument.duplicated` — emitted on the "Duplicate instrument"
  path. Detail carries the source + new instrument ids + the
  field set copied, via the Segment 11K `audit.refs(...)`
  envelope.

`instrument.created` (today's event for Add-new) stays unchanged
on the per-reviewee path. Register every new event_type in
`EVENT_SCHEMAS` or the strict-mode test gate rejects it.

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
- **A rule-tree → English renderer** — the `summary` content is
  the operator-authored `reviewee_group_description` with a name /
  description fallback.
- **Cross-session instrument duplication / templates** — the
  duplicate button copies within a session only.

## Relationship to Segment 13A and 13B

13A (rule-based assignments — shipped), 13B (sort by reviewee),
and 13C are siblings. 13C now **depends on** 13B's
`sort_display_fields` mechanism (the group-scoped editor reuses
it) and on 15B's per-instrument `rule_set_id` (the pinned rule);
both have shipped.

## Doc impact

When 13C kicks off:

- Update `spec/instruments.md` Section C "Action row" for the two
  new buttons, and the Display Fields section for the
  group-scoped variant (the Group display control).
- Update `spec/reviewer-surface.md` for the group-block
  treatment.
- Update `spec/rule_based_assignment.md` §7.2 for the
  `reviewee_group_description` text box on the Rule Builder page.
  (§5.4's seeded-RuleSet table already carries the seeded
  `reviewee_group_description` values — done ahead of 13C.)
- Update `spec/settings_inventory.md` for the new column.
- Update `guide/todo_master.md` — move 13C to in-progress, then
  Done when PR 3 lands.
- Migrate this file to `guide/archive/` when PR 3 merges.

## Ride-along — Segment 18D Part 3

Segment 18D handed its **Part 3** to 13C: once group-scoped
instruments exist, the analysis-facing Responses extract
(`extracts/responses_extract.py`) gains a derived `Instrument`
*flavour* column (per-reviewee vs group-scoped) so downstream
analysis can split the two without re-deriving from the schema.
Land it as a small ride-along in PR 2.
