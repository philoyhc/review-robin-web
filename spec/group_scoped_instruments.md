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

> **Revised 2026-05-18 — tag-composed identity.** A later
> iteration of the same day dropped the free-text "Group
> Description" field — and its `reviewee_group_description`
> (RuleSet) and `Instrument.group_description` columns. The
> group's on-screen identity is instead **composed from the
> reviewee / pair-context tags the operator marks Include** on
> the Display Fields table, plus optionally the member Name
> list. This needs **no new columns** — the existing
> `InstrumentDisplayField.visible` flag is the Include checkbox
> and the 13B sort spec orders the rows. The sections below
> reflect this model. The interim free-text design (and its
> migration) is superseded.

This file is the source of truth for the design. The
implementation plan lives at
**`guide/segment_13C_enhanced_instrument.md`**; 13C also picks up
the Replicate-instrument button on the same action-row sweep.

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

### Schema — no migration

13C ships **zero migrations.** The group-scoped instrument is
carried entirely by columns that already exist:

| Field | Where | Type | Notes |
|---|---|---|---|
| `group_kind` | `Instrument` | `String(32) \| NULL` | **Already exists** — shipped inert in 13D PR 6. `NULL` = per-reviewee instrument; **any non-null value** flags the instrument group-scoped. The specific string is not interpreted — the `add-group` route writes `"both"` as an inert marker; a future cleanup could simplify it. |
| `visible` | `InstrumentDisplayField` | `Boolean` | Existing per-row flag. On a group-scoped instrument it is the **Include** checkbox — which tag (or Name) rows compose the group identity on the reviewer surface. |
| `sort_display_fields` | `Instrument` | `JSON \| NULL` | Existing Segment 13B per-instrument sort spec. Orders the tag rows and the member-name list. |

No `Assignment`, `Response`, or RuleSet change. The free-text
"Group Description" field explored in an interim draft — and its
`reviewee_group_description` / `Instrument.group_description`
columns — was dropped (see the 2026-05-18 revision note); the
group identity is composed from tags instead.

## Operator editor

### Creation

Two creation entrypoints on the action row of
`/operator/sessions/{id}/instruments`:

- **Add an instrument** — today's button. Creates a per-reviewee
  instrument (`group_kind = NULL`).
- **Add group instrument** — new button. Creates a group-scoped
  instrument (`group_kind` non-null — the `add-group` route
  writes the inert marker `"both"`). Inserted immediately after
  the current card, like "Add instrument".

**Mode is set at creation and is not toggleable.** An operator who
wants to change an instrument's mode deletes it and recreates it.
A toggle would have to either silently rewrite the instrument's
display configuration or refuse — both worse than delete-and-
recreate, and a separate creation button surfaces the affordance
directly. This follows the existing editor idiom (shape is set at
creation; Lock / Unlock governs visibility, not data shape).

### Editor surface for a group-scoped instrument

Identical to the per-reviewee editor except for the **Display
Fields** section, which is reshaped to the per-reviewee table
restricted to **tag rows plus a Name row**:

- **Rows.** Every reviewee tag and pair-context tag that
  **carries data** — `RevieweeTag1/2/3` and
  `PairContextTag1/2/3`, up to six rows, the same eligibility
  standard as a per-reviewee instrument's Display Fields
  (`spec/instruments.md` "Display Fields") — followed by a
  single **Name** (`RevieweeName`) row. Email and Profile never
  appear.
- **Columns.**
  - **Friendly Label** — the tag's session-wide friendly label,
    read-only (`app/services/field_labels.py`).
  - **Include** — a checkbox per row, persisted to the existing
    `InstrumentDisplayField.visible` flag. The ticked rows
    compose the group identity on the reviewer surface (see
    "Composing the group identity"). Unlike a per-reviewee
    instrument, the **Name row is not locked** here — its
    Include is operator-choosable (unticking it omits the
    member-name list).
  - **Sort** — the per-instrument sort control (the Segment 13B
    sort spec, `Instrument.sort_display_fields`), ordering the
    tag rows and the member-name list.

**There is no free-text group-description field.** The group's
on-screen identity is composed from the Included tags. When the
operator wants to convey something the tags do not, they use the
**instrument's own friendly description** (the block heading,
`Instrument.description`) — exactly as for a per-reviewee
instrument.

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

## Reviewer surface

A group-scoped instrument renders as a self-contained block,
visually distinct from per-reviewee instrument blocks:

- **Heading** — the instrument's operator-editable description,
  same as today.
- **One group row.** The reviewer has exactly one group for the
  instrument (their eligible-reviewee set). The row carries a
  single **group-identity column** and one set of response
  inputs — one rating, one comment, etc., for the whole group.
- A reviewer with no assignments for the instrument gets no row.

The visual distinction from per-reviewee tables is intentional:
the operator's "Add a group-scoped instrument" choice produces a
table the reviewer immediately reads as group-scoped, with no
ambiguity about whether the rating is per-person or per-group.

The reviewer-surface preview hub (`spec/preview_hub.md`) renders
these blocks alongside the per-reviewee ones for the
picker-selected reviewer.

### Composing the group identity

The group-identity column is built from the Display Fields rows
the operator marked **Include**, rendered as up to three lines:

1. **Reviewee tags** — the Included reviewee-tag values,
   comma-separated.
2. **Pair-context tags** — the Included pair-context-tag values,
   comma-separated, on the next line.
3. **Member names** — when the Name row is Included, the group
   members' names, comma-separated, on the next line.

Tag **values are shown verbatim** — no friendly-label prefix.
The operator names the tag values themselves, so a `tag2` value
of `Group 5` and a `tag3` value of `Team A` render directly as
`Group 5, Team A`.

The group is **rule-defined**, so its members are not guaranteed
to share a value for a given tag. When an Included tag has more
than one distinct value across the group, all distinct values
are shown comma-separated. In practice this composed identity
works cleanly because operators Include the tags the pinned rule
clusters on — the vast majority of group-review cases (e.g. an
*Intra-group* rule with its group tag Included) — so a single
crisp value per tag is the norm; the Name row is the unambiguous
fallback when it is not. (See also `spec/rule_based_assignment.md`
§7.2 on ordering the predicate-editor field selector
reviewee-/pair-tags-first, which keeps a relevant tag in play
for nearly every rule.)

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
export surfaces the **composed group identity** instead — the
Included tag values and, when the Name row is Included, the
member-name list — in place of the per-reviewee identity
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
- **A free-text group-description field.** Dropped in favour of
  the tag-composed identity (see the 2026-05-18 revision note).
  The instrument's own friendly description carries any prose
  the operator wants to add.

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
  the group-scoped flag) and `rule_set_id` (the pinned rule).
- `app/db/models/instrument_field.py` — `InstrumentDisplayField`,
  whose existing `visible` flag is the Include checkbox on a
  group-scoped instrument.
- `app/services/instruments/_display_fields.py` — the display-
  field CRUD + the sort-spec service (`set_sort_display_fields`),
  both reused by the group-scoped editor.
- `app/services/responses.py` — home of the proposed
  `collapse_group_duplicates` helper.
- `spec/rule_based_assignment.md` — §7.1 (pinning a rule to an
  instrument) and §7.2 (the Rule Builder predicate editor, whose
  field selector lists reviewee tags then pair-context tags,
  omitting reviewer tags — so nearly every rule keeps a
  reviewee/pair tag in play for the composed identity).
- `spec/instruments.md` — the operator Instruments page; the
  action-row and Display Fields sections gain the group-scoped
  variant.
- `spec/reviewer-surface.md` — the reviewer-surface group block.
- `spec/preview_hub.md` — group-scoped instruments render in the
  reviewer-surface preview card.
