# Enhanced instruments — group-scoped review

**Status.** Implemented — Segment 13C shipped 2026-05-19: the
operator-side editor, the group-boundary tags, the
boundary-scoped reviewer write fan-out, the partition-aware
reviewer surface (one row per group), and the aggregation sweep.
This file captures the full design
for a second kind of instrument — a **group-scoped instrument**
— alongside today's per-reviewee instrument, so a reviewer
records one rating / comment / etc. about a *group* of reviewees
rather than per-individual.

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

> **Revised 2026-05-19 — group-boundary tags.** The rule-based
> model defined a reviewer's group as their *entire*
> rule-eligible reviewee set — one group per reviewer. That
> conflated two separate things: the **universe** (which
> reviewees a reviewer interacts with — the rule's job, exactly
> as for a per-reviewee instrument) and the **group boundary**
> (how that universe partitions into the groups the reviewer
> actually rates). A rule whose universe is "every reviewee in
> the course" still has to split into the tutorial groups within
> it. The boundary is now a separate operator control: a
> **Group by** checkbox column on the Display Fields table marks
> the reviewee / pair-context tags whose shared values define a
> group. Members of a group share *every* ticked tag's value
> (additive); with no tag ticked the whole universe is one group
> (the prior behaviour). The boundary spec is stored in the
> existing `group_kind` column — still no migration. The Display
> Fields table keeps an *Include* column, but it is constrained:
> a tag picked for the boundary is locked Included, a tag not
> picked is not Includable, and only the Name row is freely
> Includable — so the group's on-screen identity is the boundary
> tag values, optionally plus the member-name list. The sections
> below carry this model; "exactly one group per reviewer" no
> longer holds.

This file is the source of truth for the design. The
implementation plan lives at
**`guide/archive/segment_13C_enhanced_instrument.md`**; 13C also picks up
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

## The model — rule selects the universe, tags draw the boundary

A group-scoped instrument behaves like an ordinary instrument
with one shift in **presentation** and one added operator
control:

- It carries a **pinned rule** (`instruments.rule_set_id`, the
  Segment 15B per-instrument RuleSet). The rule is **required**
  before the instrument may accept responses. The rule does
  exactly what it does for a per-reviewee instrument: it selects
  the **universe** — the set of reviewees a given reviewer
  interacts with.
- Assignment generation is **unchanged** — the rule emits
  ordinary `(reviewer, reviewee, instrument)` `Assignment` rows,
  exactly as it does for a per-reviewee instrument. No
  rule-engine change, no fan-out step at generation time.
- It carries **group-boundary tags** — zero or more reviewee /
  pair-context tags the operator marks **Group by** on the
  Display Fields table. They partition each reviewer's universe into the
  groups the reviewer actually rates: two reviewees fall in the
  same group for a reviewer iff they share the same value for
  **every** boundary tag (the boundary is *additive*). With no
  boundary tag set, the whole universe is one group.
- The shift: the reviewer answers **once per group** instead of
  once per reviewee.

Worked example. A rule's universe is "every reviewee in the
course." The operator ticks **Group by** on `Class` and `Team`. A
reviewer whose universe spans two classes of three teams each
faces six group rows — one per `(Class, Team)` value pair — and
answers each once. Ticking only `Team` would merge same-named
teams across classes into one row; the additive `Class + Team`
boundary keeps them distinct without forcing the operator to give
every team a globally-unique name.

A reviewer with no assignments for the instrument has no group
row. `Full Matrix` with no boundary tag is the maximal degenerate
case — one group, every reviewee; a boundary tag splits it. The
rule defines the universe; the boundary tags, and nothing else,
define how it is cut into groups.

## Data model

The mechanism: keep ordinary single-reviewee `Assignment` and
`Response` rows, **fan one reviewer answer out to a `Response` row
per group member on write**, and **collapse the duplicates back
to one on read** keyed on `(reviewer_id, instrument_id,
group_key, response_field_id)` — where `group_key` is the tuple
of boundary-tag values shared by the group's members (empty when
the instrument has no boundary tag).

- `Response.assignment_id` stays strictly single-reviewee — no
  nullable FKs, no polymorphic target. Every existing
  non-group-aware query keeps working unchanged.
- The groups of a `(reviewer, instrument)` pair are the
  partitions of *that reviewer's `Assignment` rows for that
  instrument*, cut by the boundary tags' values. With no boundary
  tag there is a single group — all the reviewer's rows. The only
  stored group identity is the boundary-tag values themselves;
  nothing else is derived or persisted.
- Downstream code that aggregates by reviewee — Manage
  Invitations' Review Progress column, the Responses page's
  per-reviewee coverage, the Extract Data exports — routes
  through one shared helper, `responses.collapse_group_duplicates`
  (see "Aggregation contract").

### Why single-reviewee rows, not reviewer↔group rows

A reviewer↔group `Assignment` row — one row pairing a reviewer
with a *group* rather than an individual reviewee, on the
analogy of the collapsed Extract Data output — was considered
and **rejected** (decided 2026-05-19).

A group here is not a stable, first-class entity. It is
`(reviewer, instrument, boundary-tag-tuple)`: **per-reviewer**
(each reviewer's rule-eligible universe, partitioned —
reviewer A's "Team A" and reviewer B's "Team A" may differ),
**per-instrument** (`group_kind` is an `Instrument` column, so
two group-scoped instruments can partition the same reviewees
differently), and **derived from mutable inputs** — the pinned
rule's output and the reviewees' boundary-tag values.

Storing a group as a row would therefore force *group-identity
reconciliation* on every roster or rule edit: when a reviewee's
boundary tag changes, the group partition changes, and stored
answers must be migrated across group splits / merges / member
moves. Keeping single-reviewee rows makes regrouping a free
**read-time reinterpretation** — zero writes, no migration. It
also keeps `Assignment` uniform (no polymorphic
reviewee-or-group target), keeps every reviewee-keyed query
working unchanged, and keeps group-ness a reversible
per-instrument flag — toggling `group_kind` off restores a plain
per-reviewee instrument with all its rows intact, which is the
source of 13C's zero-migration property.

The Extract Data collapse is not a counter-example: it is a
read-only, terminal projection that never faces mutation —
storage must. The bounded, mechanical cost of this choice — the
write fan-out and read collapse (PR 2 slices B / C / D) — is the
price of *derived* groups, and it is the cheaper price. The
decision would flip only if groups became operator-curated
stable teams (explicit rosters the operator creates and edits)
rather than tag-derived partitions.

**Corrections are the strongest case for this model.** The
common real-world need is not swapping a group member but
*correcting mis-entered data* — a reviewee recorded in the wrong
group (operator typed `{A,B,D}` when the real group is
`{A,B,C}`). A correction is intrinsically surgical: a specific
reviewer→reviewee judgment was recorded about the wrong person.
Because every such judgment is stored as an independently
addressable `(reviewer, reviewee)` atom, a correction maps 1:1
onto row operations — defunct the wrong atoms (`A→D`, `B→D`,
`D→A`, `D→B`), create the right ones (`A→C`, `B→C`, …), and
leave every valid judgment (`A→B`) untouched; only C and D
redo. Group-scoped instruments inherit the correction: removing
a reviewee from a group removes them from the relevant
reviewers' universes, so the wrong member assignments — and the
fanned-out answer copies riding on them — drop wholesale, while
the retained members still carry each reviewer's group answer
through the read-collapse (the representative is a retained,
answered member). A group-entity row could not be corrected this
way — a holistic group answer is not decomposable into per-pair
atoms, so "keep A's and B's contribution, drop the D-ness" is
inexpressible. And because a session mixes per-reviewee and
group-scoped instruments, the per-pair model gives **one**
uniform correction mechanism — defunct / reassign
`(reviewer, reviewee)` atoms — across both instrument kinds,
where a group-entity model would need two.

### Schema — no migration

13C ships **zero migrations.** The group-scoped instrument is
carried entirely by columns that already exist:

| Field | Where | Type | Notes |
|---|---|---|---|
| `group_kind` | `Instrument` | `String(32) \| NULL` | **Already exists** — shipped inert in 13D PR 6. `NULL` = per-reviewee instrument; **any non-null value** flags the instrument group-scoped. The value now **encodes the group-boundary spec**: an ordered, comma-separated list of boundary tag-key codes (`r1`-`r3` reviewee tags, `p1`-`p3` pair-context tags), e.g. `r1,p2`. A group-scoped instrument with no boundary tag keeps the sentinel `"both"` (the legacy marker) so the column stays non-null. Six codes + commas = 17 chars, well inside `String(32)`. |
| `visible` | `InstrumentDisplayField` | `Boolean` | Existing per-row flag — the **Include** checkbox. On a group-scoped instrument a tag row's `visible` follows its Group-by tick (locked on for boundary tags, off otherwise); the **Name** row's `visible` is the freely-chosen "list group members" toggle. |
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
  - **Group by** — a checkbox per **tag** row marking that tag a
    group-boundary key (see "The model"); ticking more than one
    splits the universe additively. The ticked tags' key-codes
    are persisted, ordered, into `group_kind`. The **Name row has
    no Group-by cell** — a group can never be bounded by a
    per-individual identifier. With no tag ticked the reviewer's
    whole universe is one group.
  - **Include** — a checkbox per row, persisted to the existing
    `InstrumentDisplayField.visible` flag; the ticked rows
    compose the group identity on the reviewer surface (see
    "Composing the group identity"). It is **constrained by
    Group by**: a tag ticked for the boundary is **locked
    Included** (its Include box follows the Group-by tick and
    cannot be unticked); a tag *not* ticked for the boundary is
    **not Includable** (its Include box is disabled). Only the
    **Name** row is freely Includable — its Include is
    operator-choosable and independent of any boundary tick.
  - **Sort** — the per-instrument sort control (the Segment 13B
    sort spec, `Instrument.sort_display_fields`), ordering the
    boundary tag-key codes written to `group_kind` and the tag
    values within the composed identity.

  A short helper line under the table explains the split: Group
  by picks how the universe is cut into groups; Include picks
  what renders in the group-identity column.

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
- **One row per group.** The reviewer's universe is partitioned
  by the instrument's boundary tags into one or more groups (just
  one when no boundary tag is set). Each group is a row carrying
  a **group-identity column** and one set of response inputs —
  one rating, one comment, etc., for that whole group.
- A reviewer with no assignments for the instrument gets no row.

The visual distinction from per-reviewee tables is intentional:
the operator's "Add a group-scoped instrument" choice produces a
table the reviewer immediately reads as group-scoped, with no
ambiguity about whether the rating is per-person or per-group.

The reviewer-surface preview hub (`spec/preview_hub.md`) renders
these blocks alongside the per-reviewee ones for the
picker-selected reviewer.

### Composing the group identity

The group-identity column is composed from the Display Fields
rows marked **Include** — which, by the Include constraint above,
is exactly the boundary tags plus optionally the Name row:

1. **Boundary tag values** — the group's value for each Included
   boundary tag, comma-separated, in Sort order, on one line. By
   construction every member shares these values, so each renders
   a single crisp value.
2. **Member names** — when the Name row is Included, the group
   members' names, comma-separated, on a second line below.

Tag **values are shown verbatim** — no friendly-label prefix.
The operator names the tag values themselves, so a boundary tag
value of `Group 5` and another of `Team A` render directly as
`Group 5, Team A`.

When an instrument has no boundary tag the whole universe is one
group with no tag values to show; the member-name list (if the
Name checkbox is ticked) is then the group's only identity, and
operators will normally tick it in that case.

### Write fan-out

The reviewer submits one answer per response field per group. On
submit the write path **fans that answer out** to a `Response`
row for every `(reviewer, reviewee)` assignment **in that
group** — the same value written once per member of the group it
was answered for, not across the reviewer's whole universe. Each
row remains an ordinary single-assignment `Response`.

## Aggregation contract

A single helper centralizes group-aware aggregation:

```python
# app/services/responses.py (proposed)

def collapse_group_duplicates(rows):
    """Collapse the N group-duplicate response rows back to one.

    For rows belonging to a group-scoped instrument, emit a single
    row per group keyed on (reviewer_id, instrument_id, group_key,
    response_field_id) with the shared value — where group_key is
    the boundary-tag value tuple (empty when the instrument has no
    boundary tag). Per-reviewee rows pass through unchanged.
    Consumers that need the per-member fan-out shape (e.g. a CSV
    export with one row per member) use the raw rows without
    routing through this helper.
    """
```

Every consumer that aggregates by reviewee or reports
"completion" routes through the helper. The contract: a single
group response counts as **one completion per group**, not N per
member, and a group-scoped instrument with K boundary-defined
groups counts K completions, not one.

**Trade-off — dedup discipline.** The collapse must be honored
everywhere data leaves the system or rolls up. A missed collapse
in a CSV export over-counts group responses by the group size.
The single helper plus a unit test pinning the contract is the
defense; reviewing every aggregator's call site is mandatory when
the feature ships (see `guide/archive/segment_13C_enhanced_instrument.md`
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
- **Tags as membership.** A group's *membership* is never defined
  by tags — the pinned rule defines the universe, exactly as for
  a per-reviewee instrument. Boundary tags only **partition** an
  already rule-selected universe; they never add or remove
  reviewees. (The superseded pre-2026-05-18 design used a
  composite `group_kind` of tag keys *as the membership
  mechanism, with no rule* — that conflation is what is out of
  scope, not the use of tags to draw a boundary.)
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

- **Large-group member lists.** *Resolved (13C PR 2 slice C).*
  The group-identity cell lists the first 10 member names then a
  `+N more` suffix (no hover-to-expand). The limit lives in one
  constant — `GROUP_MEMBER_NAME_LIMIT` in
  `app/web/routes_reviewer/_surface.py`.
- **Group-scoped reminders.** A reviewer who has not answered a
  group-scoped instrument — does the reminder say "you have an
  unanswered group rating" or enumerate the group? Probably the
  former; confirm with an operator before shipping.
- **Boundary tags with blank values.** A reviewee missing a
  boundary tag's value — do the blanks form their own labelled
  "(unset)" group, or is the row dropped? Probably an "(unset)"
  group so no reviewee silently vanishes; confirm when PR 2
  starts.
- **Stale fan-out copies on a grouping-tag change.** *Decided
  2026-05-19 — implementation pending.* An assignment's
  `group_key` is computed from its **reviewee's** boundary-tag
  values (and, for pair-context boundaries, the
  `(reviewer, reviewee)` relationship) — never from the
  reviewer's own tags. So when a person's grouping-tag value is
  corrected, the answer copies fanned onto every assignment that
  *points at them* are now mis-attributed to whatever group
  those rows re-derive into. Safeguard: on a grouping-tag
  change, defunct every group-scoped `Response` row on
  assignments where that person is the **reviewee** (the rows
  whose `group_key` depends on the changed tag) — not the rows
  they authored, whose `group_key` depends on *their* reviewees
  and stays valid. This is lossless for the reviewer: their
  group answer survives redundantly on the group's other member
  rows (the exception — a two-person group with self-review off
  — is one where the answer should be revisited anyway). A
  pair-context boundary-tag change is narrower still: only the
  one relationship's row.
- **Eligible-pair count on a group-scoped instrument's rule
  card.** *Decided 2026-05-19 — implementation pending.*
  Because single-reviewee `(reviewer, reviewee)` assignment rows
  are generated regardless (see "Why single-reviewee rows, not
  reviewer↔group rows"), the existing "Number of eligible pairs
  found: N" — `len(result.pairs)` from
  `evaluate_session_rule_eligibility`
  (`app/services/rules/session_library.py`) — keeps its meaning
  and **stays** for every instrument. For a **group-scoped**
  instrument a secondary **reviewer-group pair** count is shown
  in parentheses after it, e.g.
  `Number of eligible pairs found: 240 (32 reviewer-group pairs)`.
  The group figure is the count of distinct `(reviewer,
  group_key)` over the engine's `result.pairs`, with `group_key`
  the boundary-tag tuple. Because boundary tags are an
  `Instrument` setting (the same rule pinned on two instruments
  can yield different group counts), this secondary figure is
  **instrument-aware** — derived per-instrument at render, not
  folded into the per-rule `cached_eligible_pair_count`. The
  parenthetical is omitted for per-reviewee instruments.

## Cross-references

- `app/db/models/instrument.py` — `group_kind` column (exists;
  the group-scoped flag, and the encoded group-boundary spec)
  and `rule_set_id` (the pinned rule).
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
