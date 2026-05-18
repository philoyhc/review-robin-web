# Enhanced instruments — group-scoped review

**Status.** Forward-looking design spec. Not yet implemented.
Captures the design for a second kind of instrument — a
**group-scoped instrument** — alongside today's per-reviewee
instrument, so a reviewer records one rating / comment / etc.
about a *group* of reviewees rather than per-individual.

> **Rewritten 2026-05-18.** Earlier drafts of this spec defined a
> group by **clustering reviewees on their tag values** — a
> composite `group_kind` naming an ordered list of tag keys, a
> derived tag-tuple `group_id`, multiple groups per instrument.
> That mechanism is **superseded**. A group is now defined by the
> instrument's **pinned rule**: the set of reviewees the rule
> makes eligible for a given reviewer *is* that reviewer's group.
> There is exactly **one group per reviewer per group-scoped
> instrument**, and no tag clustering. The sections below carry
> the rule-based model end to end. The pre-2026-05-18 tag-cluster
> design is gone — do not reintroduce composite `group_kind`,
> derived tag tuples, or multi-group-per-instrument.

This file is the source of truth for the design. The
implementation plan lives at
**`guide/segment_13C_enhanced_instrument.md`**; 13C also picks up
the duplicate-instrument button on the same action-row sweep.

Subsequent edits to this design go here and propagate to the
implementation, not the other way around.

---

## Rationale

Today every reviewer response is keyed to a single
`(reviewer, reviewee)` assignment via `app/db/models/assignment.py`.
That works when the operator's question is "rate Alice on
collaboration." It does not work when the question is "rate the
*team's* collaboration" — a single answer that should apply to
the whole group, not be copy-pasted per individual.

A whole instrument is either **per-reviewee** (today's default)
or **group-scoped**. The reviewer surface renders distinct
sub-tables per instrument — the visual context shift is the
affordance, no per-row treatment needed. Operator authoring is a
label-level choice ("Add an instrument" vs "Add a group-scoped
instrument") rather than a per-field fork. The reviewer never
sees the same question wording twice in different contexts.

## The model — a group is what the rule selects

A group-scoped instrument behaves exactly like an ordinary
instrument with one shift in **presentation**:

- It carries a **pinned rule** (`instruments.rule_set_id`, the
  Segment 15B per-instrument RuleSet). The rule is **required**
  before the instrument may accept responses.
- Assignment generation is **unchanged** — the rule emits
  ordinary `(reviewer, reviewee, instrument)` `Assignment` rows,
  exactly as it does for a per-reviewee instrument. No
  rule-engine change, no fan-out step at generation time.
- The shift: for a group-scoped instrument, **all of a reviewer's
  assignments collapse into one group**. The set of reviewees the
  rule made eligible for that reviewer *is* the reviewer's group.
  The reviewer answers **once** for the whole set instead of once
  per reviewee.

This yields exactly **one group per reviewer per group-scoped
instrument** — the reviewer's eligible-reviewee set. There is no
tag clustering and no notion of multiple groups within one
instrument. A reviewer with no assignments for the instrument
simply has no group row.

`Full Matrix` is the natural maximal case: every reviewer's group
is *every reviewee*. A predicate / quota rule narrows each
reviewer's group to whatever it makes eligible. Either way the
rule defines membership and nothing else does.

## Data model

The mechanism: keep ordinary single-reviewee `Assignment` and
`Response` rows, **fan one reviewer answer out to a `Response` row
per group member on write**, and **collapse the duplicates back
to one on read** keyed on `(reviewer_id, instrument_id,
response_field_id)`.

- `Response.assignment_id` stays strictly single-reviewee — no
  nullable FKs, no polymorphic target. Every existing
  non-group-aware query keeps working unchanged.
- The group of a `(reviewer, instrument)` pair is simply *that
  reviewer's `Assignment` rows for that instrument*. No stored
  group identity, no derivation from tags.
- Downstream code that aggregates by reviewee — Manage
  Invitations' Review Progress column, the Responses page's
  per-reviewee coverage, the Extract Data exports — routes
  through one shared helper, `responses.collapse_group_duplicates`
  (see "Aggregation contract").

### Schema

| Field | Where | Type | Notes |
|---|---|---|---|
| `group_kind` | `Instrument` | `String(32) \| NULL` | **Already exists** — shipped inert in 13D PR 6. `NULL` = per-reviewee instrument (today's default). A non-null value flags the instrument group-scoped **and** stores the display-content choice: one of `members` / `summary` / `both` (see "Reviewer surface"). The column is **repurposed** by this design — it no longer stores tag keys. 13C PR 1 is the first writer. |
| `reviewee_group_description` | `operator_rule_sets` **and** `session_rule_sets` | `Text \| NULL` | **New — one migration in 13C PR 1.** Operator-authored plain-English description of the group the rule forms (e.g. "Each reviewer's project team"). Used as the `summary` display content. `NULL` / blank → fall back to the RuleSet's `description`. Lives on both the library row and the per-session copy, mirroring how `description` is carried on both. The five seeded RuleSets ship with a default value (`spec/rule_based_assignment.md` §5.4). |

No `Assignment` change. No `Response` change. The per-instrument
sort spec reuses the existing `Instrument.sort_display_fields`
column (Segment 13B) — see "Operator editor".

`group_kind` keeping the name "kind" is mild legacy drift — it now
holds a display-content choice, not a grouping kind. Renaming the
column would cost a migration for no behavioural gain; 13C PR 1
updates the model docstring instead.

## Operator editor

### Creation

Two creation entrypoints on the action row of
`/operator/sessions/{id}/instruments`:

- **Add an instrument** — today's button. Creates a per-reviewee
  instrument (`group_kind = NULL`).
- **Add a group-scoped instrument** — new button. Creates a
  group-scoped instrument with `group_kind` set to the default
  display choice (`both` — rule summary followed by the member
  list). Inserted immediately after the current card, like "Add
  an instrument".

**Mode is set at creation and is not toggleable.** An operator who
wants to change an instrument's mode deletes it and recreates it.
A toggle would have to either silently rewrite the instrument's
display configuration or refuse — both worse than delete-and-
recreate, and a separate creation button surfaces the affordance
directly. This follows the existing editor idiom (shape is set at
creation; Lock / Unlock governs visibility, not data shape).

### Editor surface for a group-scoped instrument

Identical to the per-reviewee editor except for the **Display
Fields** section, which is **reshaped, not removed**.

For a group-scoped instrument the Display Fields table carries
three columns:

- **Group Description** — a single vertically-merged cell
  spanning every row, holding an edit box. It defaults to the
  pinned rule's `reviewee_group_description` (which itself falls
  back to the rule's `description`); the operator may override
  the text here.
- **Friendly Label** — the tag's session-wide friendly label,
  read-only, resolved the same way as a per-reviewee instrument's
  Display Fields labels (`app/services/field_labels.py`).
- **Sort** — the per-instrument sort control (the Segment 13B
  sort spec, `Instrument.sort_display_fields`). For a group-scoped
  instrument the sort orders **two things**: the inline
  member-name list within a group cell, and, where group rows are
  listed on operator pages, the group rows themselves (a group
  sorts by its first member under the spec).

**Eligible rows.** The table's rows are the reviewee tags and
pair-context tags that **carry data** — the *same eligibility
standard* as a per-reviewee instrument's Display Fields (see
`spec/instruments.md` "Display Fields"): every populated
`RevieweeTag1/2/3` and `PairContextTag1/2/3`, **up to six rows**.
Name, Email, and Profile are individual attributes and never
appear on a group-scoped instrument's Display Fields table.

The reviewer-surface group column's content
(`members` / `summary` / `both`, stored in `group_kind`) is a
separate display choice — see "Reviewer surface". Its editor
control is not yet sited; the default for a freshly created
group-scoped instrument is `both`.

Response Fields, Response Fields Help, descriptions,
accepting-responses / visibility toggles, and the Save / Edit /
Delete affordances are all unchanged. A small chip near the
instrument-card heading reads **Group-scoped** so the operator
never wonders which mode they are editing.

### Rule is required

A group-scoped instrument's rule is pinned through the existing
Segment 15B per-instrument rule flow (the Rule Based card on the
Assignments page — `spec/rule_based_assignment.md` §7.1). The
difference: for a group-scoped instrument the rule is
**mandatory**. The instrument's `accepting_responses` toggle
cannot be turned on while `rule_set_id` is `NULL`; the service
layer rejects the open with an inline banner pointing the
operator at the Assignments page. `Full Matrix` is a valid pin
(group = every reviewee).

## The rule and its group description

The `reviewee_group_description` field is authored in an
operator-editable **text box on the Rule Builder page**
(`spec/rule_based_assignment.md` §7.2) alongside the RuleSet's
name and description — it is a property of the rule, not of the
instrument. One rule may be pinned to several instruments; the
description travels with the rule.

The five seeded RuleSets ship with a sensible default
`reviewee_group_description` (e.g. *Intra-group peer review* →
"All reviewees with the same tag1 as reviewer" — see
`spec/rule_based_assignment.md` §5.4). The operator overrides
that default in the text box with friendlier session-specific
copy — "Your work squad", "Your tutorial group", "Your lab
group", and so on. Because the override lives on the per-session
RuleSet copy (`session_rule_sets`), it is per-session.

When a group-scoped instrument's display choice is `summary` or
`both`, the reviewer surface and the operator preview render the
group **summary**, resolved as: `reviewee_group_description`,
and — when that is blank — a fallback to the RuleSet's
`description`.

## Reviewer surface

A group-scoped instrument renders as a self-contained block,
visually distinct from per-reviewee instrument blocks:

- **Heading** — the instrument's operator-editable description,
  same as today.
- **One group row.** The reviewer has exactly one group for the
  instrument (their eligible-reviewee set). The row carries a
  single **group column** whose content follows `group_kind`
  (member names / rule summary / both) and one set of response
  inputs — one rating, one comment, etc., for the whole group.
- A reviewer with no assignments for the instrument gets no row.

The visual distinction from per-reviewee tables is intentional:
the operator's "Add a group-scoped instrument" choice produces a
table the reviewer immediately reads as group-scoped, with no
ambiguity about whether the rating is per-person or per-group.

The reviewer-surface preview hub (`spec/preview_hub.md`) renders
these blocks alongside the per-reviewee ones for the
picker-selected reviewer.

### Write fan-out

The reviewer submits one answer per response field. On submit the
write path **fans that answer out** to a `Response` row for every
`(reviewer, reviewee)` assignment in the group — the same value
written N times, once per member. Each row remains an ordinary
single-assignment `Response`.

## Aggregation contract

A single helper centralizes group-aware aggregation:

```python
# app/services/responses.py (proposed)

def collapse_group_duplicates(rows):
    """Collapse the N group-duplicate response rows back to one.

    For rows belonging to a group-scoped instrument, emit a single
    row keyed on (reviewer_id, instrument_id, response_field_id)
    with the shared value. Per-reviewee rows pass through
    unchanged. Consumers that need the per-member fan-out shape
    (e.g. a CSV export with one row per member) use the raw rows
    without routing through this helper.
    """
```

Every consumer that aggregates by reviewee or reports
"completion" routes through the helper. The contract: a single
group response counts as **one completion** at the
group-scoped-instrument level, not N.

**Trade-off — dedup discipline.** The collapse must be honored
everywhere data leaves the system or rolls up. A missed collapse
in a CSV export over-counts group responses by the group size.
The single helper plus a unit test pinning the contract is the
defense; reviewing every aggregator's call site is mandatory when
the feature ships (see `guide/segment_13C_enhanced_instrument.md`
PR 2).

### Extraction

The Extract Data exports collapse the per-member rows to **one
row per group** (one per reviewer per group-scoped instrument).
Because a group-scoped row has no single reviewee identity, the
export surfaces the group instead — a column carrying the member
list and / or the rule summary (matching the instrument's
`group_kind` choice) in place of the per-reviewee identity
columns. Per-reviewee instruments are unaffected.

Segment 18D Part 3 rides along here: the analysis-facing
Responses extract gains a derived instrument *flavour* column
(per-reviewee vs group-scoped) so downstream analysis can split
the two without re-deriving from the schema.

## Out of scope

- **Per-question group scope.** A whole instrument is one mode or
  the other; an instrument never mixes per-reviewee and group
  questions.
- **Tag-cluster grouping.** The superseded mechanism — composite
  `group_kind`, derived tag tuples, multiple groups per
  instrument. Do not reintroduce it.
- **Mode-flipping after creation.** Operators delete and
  recreate.
- **Manual CSV assignment mode for group-scoped instruments.**
  The rule is required, so assignment is always rule-driven.
- **A separate `Group` entity.** The group is just a reviewer's
  assignment set; no table is needed.
- **A rule-tree → English renderer.** The `summary` display
  content comes from the operator-authored
  `reviewee_group_description` (with a name / description
  fallback), not from machine-generating prose from the predicate
  tree.

## Open questions

- **Large-group member lists.** "Alice, Bob, Carol" reads cleanly
  for a handful of members; a 30-member list does not. A
  "+N more" truncation with hover-to-expand is probably right —
  lock the copy when PR 2 starts.
- **Group-scoped reminders.** A reviewer who has not answered a
  group-scoped instrument — does the reminder say "you have an
  unanswered group rating" or enumerate the group? Probably the
  former; confirm with an operator before shipping.

## Cross-references

- `app/db/models/instrument.py` — `group_kind` column (exists;
  repurposed by this design) and `rule_set_id` (the pinned rule).
- `app/db/models/rule_set.py` / `app/db/models/session_rule_set.py`
  — gain `reviewee_group_description` (13C PR 1 migration).
- `app/services/instruments/_display_fields.py` — the sort-spec
  service (`set_sort_display_fields`) a group-scoped instrument
  reuses unchanged.
- `app/services/responses.py` — home of the proposed
  `collapse_group_duplicates` helper.
- `spec/rule_based_assignment.md` — §7.1 (pinning a rule to an
  instrument) and §7.2 (the Rule Builder page, where
  `reviewee_group_description` is authored).
- `spec/instruments.md` — the operator Instruments page; the
  action-row and Display Fields sections gain the group-scoped
  variant.
- `spec/reviewer-surface.md` — the reviewer-surface group block.
- `spec/preview_hub.md` — group-scoped instruments render in the
  reviewer-surface preview card.
