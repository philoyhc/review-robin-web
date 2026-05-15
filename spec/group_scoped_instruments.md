# Enhanced instruments — group-scoped review

**Status.** Forward-looking design spec. Not yet implemented.
Captures the design for a second kind of instrument — a
**group-scoped instrument** — alongside today's per-reviewee
instrument, so a reviewer can record one rating / comment / etc.
about a *group* of reviewees rather than per-individual.

> **Revised 2026-05-15.** The original design stamped group
> metadata onto an `Assignment.context` JSON column. That column
> was retired in 15D PR 6b. The mechanism was reworked: the
> group is **derived** from `Instrument.group_kind` + the
> reviewee's own `tag_N` value, not stored. `Assignment.context`
> only ever held a stamped copy of derivable data. Net effect:
> group-scoped instruments need **no schema change at all**
> (`Instrument.group_kind` already exists, shipped inert in
> 13D PR 6). The "Data model", "Rule-engine integration", and
> "Aggregation contract" sections below carry the reworked
> mechanism.
>
> **Revised 2026-05-15 (composite key).** `group_kind` was a
> single reviewee tag key; it is now an **ordered, comma-joined
> list** of one or more distinct tag keys
> (`tag_1` / `tag_2` / `tag_3`) — e.g. `tag_1` or
> `tag_1,tag_2,tag_3`. The group a reviewee belongs to is the
> **tuple** of those tags' values, so an operator can partition
> by a composite like *(cohort, class, small group)* without
> packing all three facets into one overloaded tag value. This
> is still **one grouping per instrument** — one set of rows at
> one granularity — not the rejected multi-level case (see
> "One grouping per instrument"). Still zero schema change:
> `group_kind` is already `String(32)`, which holds the longest
> composite (`tag_1,tag_2,tag_3`, 17 chars).

This file is the source of truth for the design. Implementation
plan lives at **`guide/segment_13C_enhanced_instrument.md`**;
13C also picks up the duplicate-instrument button on the same
action-row sweep. Sibling segments: **13A** (rule-based
assignments — `guide/archive/segment_13A_rulebased_assignment_builder.md`)
and **13B** (sort by reviewee —
`guide/archive/segment_13B_sort_tables.md`). The three are
independent and can ship in any order. 13A's rule engine
materialises the per-member assignment fan-out, but needs no
group-specific change for the FullMatrix-first cut (see
"Rule-engine integration").

Subsequent edits to this design go here and propagate to the
implementation, not the other way around.

---

## Rationale

Today every reviewer's response on the reviewer surface is keyed
to a single `(reviewer, reviewee)` assignment via
`app/db/models/assignment.py`. That works when the operator's
question is "rate Alice on collaboration." It does not work when
the question is "rate the *team's* collaboration" — a single
answer that should apply to all members of a group, not be
copy-pasted per individual.

There are two ways to add group support:

- **Per-question scope** — let a single instrument mix
  individual ("rate Alice's communication") and group ("rate the
  team's collaboration") questions, with a per-field
  `group_scope` flag. More flexible, but every group-row needs
  its own visual distinction on the reviewer surface (badge or
  shaded background) so the reviewer doesn't accidentally answer
  the team question per-person.
- **Per-instrument scope (this spec).** A whole instrument is
  either per-reviewee (today's default) or group-scoped. The
  reviewer surface renders distinct sub-tables per instrument —
  the visual context shift is the affordance, no per-row
  treatment needed. Operator authoring is also crisper: an
  instrument's mode is a label-level choice ("Add an instrument"
  vs "Add a group-scoped instrument") rather than a per-field
  fork.

Per-instrument scope wins on reviewer cognitive load: the
reviewer never sees the same question wording twice in different
contexts. Operator pays the cost when the same questions apply
both individually *and* to the group — they author two
instruments. That cost is small and explicit; conflating the two
on the reviewer's screen is not worth the savings.

## One grouping per instrument

A group-scoped instrument carries **one** grouping — one set of
rows at one granularity. The instrument's `group_kind`
identifies that grouping; it may be a single reviewee tag or a
**composite** of several. **The same instrument cannot generate
rows at two different granularities** (e.g. one instrument
producing "rate your small group" + "rate your cohort" rows for
the same reviewer).

The reasoning mirrors the per-question argument: the reviewer
seeing "rate the team's collaboration" twice with two different
group memberships (Small Group: Team Alpha vs Cohort: Spring
2026) is exactly the cognitive trap to avoid. Operators who
genuinely need both author two instruments. If
"instrument template / clone" ships later, the duplication cost
goes to roughly zero.

### Single vs composite grouping — the distinction

A **composite** `group_kind` is *not* the rejected multi-level
case. Multi-level would render rows at two granularities at once
(a small-group block *and* a cohort block) — two memberships,
two row-sets, the cognitive trap above. A composite key instead
identifies **one** granularity whose group is named by a *tuple*
of tags: a reviewer sees one row per distinct
`(cohort, class, small group)` combination, each question once.

The composite exists because real groupings nest. "Small group
G4" is only unambiguous *within* a cohort and class; absent
composite support an operator must pack the parent facets into
the tag value itself (`2026-5A-G4` instead of `G4`) — brittle,
and it forces the same packing on every consumer of that tag.
Letting `group_kind` name an ordered list of tags
(`tag_1,tag_2,tag_3`) keeps each tag clean and single-purpose.

`group_kind` is an ordered, comma-joined list of distinct tag
keys. The first key is the **primary** group-identity column
(position 0 in the editor's display fields, the lead facet in
the reviewer-surface group label). Order is operator-chosen and
preserved. A single-tag value (`tag_1`) is just the
one-element case — no special path.

## Data model — no schema change at all

The trick: **duplicate `Response` rows per group member**, and
**derive** the group each row belongs to from the instrument's
`group_kind` + the reviewee's own tag values — so downstream
consumers can collapse the duplicates back to one without any
stored group metadata.

- The group a `(reviewer, reviewee)` assignment belongs to is
  the **tuple** of the reviewee's tag values for the tag keys
  named in the instrument's `group_kind` (one key for a simple
  grouping, several for a composite). Reviewees whose tag tuple
  matches on every key form one group; that tuple *is* the
  `group_id`. Nothing is stamped on the `Assignment`.
- The reviewer surface presents **one** set of response inputs
  per group, shaped against the response fields of the
  group-scoped instrument; submit writes the same value to every
  underlying `Assignment`'s response rows (one per group
  member).
- Downstream code that aggregates by reviewee — Manage
  Invitations' Review Progress column, the Responses page's
  per-reviewee coverage, the Extract Data exports — routes
  through one shared helper (proposed name:
  `responses.collapse_group_duplicates(rows)`) that groups by
  `(reviewer_id, response_field_id, group_id, value)` — where
  `group_id` is the derived reviewee tag tuple — and returns
  either the deduped row or the per-reviewee fan-out, depending
  on the consumer's needs.

This keeps `Response.assignment_id` strictly single-reviewee —
no nullable FKs, no polymorphic target — and lets every existing
non-group-aware query keep working unchanged. Group awareness is
opt-in per consumer.

**Trade-off — dedup discipline.** The dedup logic must be
honored everywhere data leaves the system or rolls up. Exports
especially: a missed dedup in a CSV export over-counts group
responses by `group_size`. The single helper + a unit test
pinning the contract is the defense; reviewing every
aggregator's call site for migration is mandatory when the
feature ships.

**Trade-off — derived (not frozen) membership.** Because the
group is derived live, editing any of a reviewee's grouping tags
after assignment generation re-clusters that reviewee. This is benign
in practice: editing session entities after activation requires
reverting to draft, which regenerates assignments anyway.
Freezing membership at generation time would need a new stamped
`Assignment` column — deliberately rejected (decided 2026-05-15).

### Schema — none required

| Field | Where | Type | Notes |
|---|---|---|---|
| `group_kind` | `Instrument` | `String(32) | NULL` | **Already exists** — shipped inert in 13D PR 6. `NULL` = per-reviewee instrument (today's default). Non-null = group-scoped; the column stores an ordered, comma-joined list of one or more distinct source-field keys (`tag_1` / `tag_2` / `tag_3`) — e.g. `tag_1` or `tag_1,tag_2,tag_3`. The display labels ("Small Group", "Cohort", "Team", etc.) live in operator copy. |

No `Assignment` and no `Response` change. The original design's
`Assignment.context` stamping is not needed — the group is
derived. `group_kind` stays a plain string: the comma-joined
tag-key list needs no migration (the column is already
`String(32)`, and the longest list — `tag_1,tag_2,tag_3` — is
17 characters). If a future power-user case demands a richer
group definition, a lookup-table FK can replace it
forward-compatibly.

## Operator editor

### Creation

Two creation entrypoints on `/operator/sessions/{id}/instruments`:

- **Add an instrument** — today's button. Creates a per-reviewee
  instrument (`group_kind=NULL`).
- **Add a group-scoped instrument** — new button. Opens a small
  inline dialog asking which reviewee tag(s) identify the group
  (Tag 1 / Tag 2 / Tag 3). The operator picks one tag for a
  simple grouping or several for a composite — the pick order
  sets the key order, first = primary identity. Creates a
  group-scoped instrument with `group_kind` set to the
  comma-joined list (e.g. `tag_1` or `tag_1,tag_2`).

**Mode is set at creation and is not toggleable** afterward. An
operator who wants to change an instrument's mode deletes it and
adds a new one in the desired mode. The reasoning:

- **No mid-edit invalid state.** A toggle that flipped an
  existing instrument from per-reviewee to group-scoped would
  immediately render most of its display fields illegal (group
  mode allows only the three reviewee tags — see below). The
  editor would have to either auto-truncate forbidden fields
  (data loss surprise) or refuse the toggle (toggle that
  doesn't toggle). Both options are worse than "delete and
  recreate."
- **Discoverability.** A separate creation button surfaces the
  affordance directly. A hidden in-card toggle would leave
  group-scoped instruments effectively invisible until someone
  told the operator they exist.
- **Codebase idiom.** Existing editors (Quick Setup, email
  templates) use Lock / Unlock for visibility but not for
  swapping data-shape — they prefer the shape to be set at
  creation. Following the same pattern keeps the mental model
  consistent.

### Editor surface for a group-scoped instrument

Nearly identical to the per-reviewee editor, with one
restriction:

- **Display fields are restricted to the three reviewee tags
  (`tag_1` / `tag_2` / `tag_3`).** Name, Email, Profile Link,
  and Pair Context 1/2/3 are *individual* attributes — they
  don't make sense as columns on a group-scoped row, where the
  identity is the group, not a person.
- The display-fields picker hides the disallowed sources entirely
  in group mode (rather than showing them disabled).
- The tag(s) chosen as `group_kind` at creation are locked into
  the display-fields list, in `group_kind` order — the primary
  (first) tag as the "group identity" column at position 0, any
  further composite tags immediately after it. Operators can
  still re-order or hide any non-`group_kind` tags.
- Response fields, descriptions, ordering, accepting-responses
  / visibility toggles, and the Save / Edit / Delete affordances
  are unchanged.

A small visual chip near the instrument-card heading reads
**Group-scoped (by Tag 1)** — or, for a composite key,
**Group-scoped (by Tag 1 + Tag 2 + Tag 3)** — so the operator
never wonders which mode they're editing.

## Reviewer surface

A group-scoped instrument renders as a self-contained block on
the reviewer surface, distinct from per-reviewee instrument
blocks:

- **Heading** — instrument's operator-editable description, same
  as today.
- **Group identity row** — for each group the reviewer is
  assigned on, one labeled row reads e.g.
  `Small Group: Team Alpha — Alice, Bob, Carol`. For a composite
  `group_kind` the label joins every facet in key order, e.g.
  `Cohort: Spring 2026 · Class: 5A · Small Group: G4 — Alice,
  Bob, Carol`. The facet values come from the source-field tag
  values; the member names from joining `Assignment` rows back
  to their reviewees. A single set of response inputs sits on
  that row — one rating, one comment, etc., for the whole group.
- **Multiple groups, one instrument.** A reviewer assigned across
  multiple groups (e.g. they're in two cohorts) gets one row per
  group within the same instrument's table.

The visual distinction from per-reviewee tables is intentional:
the operator's "Add a group-scoped instrument" choice produces a
table the reviewer immediately reads as group-scoped, no
ambiguity about whether the rating is per-person or per-group.

The reviewer-surface preview hub
(`spec/preview_hub.md`) renders these blocks alongside the
per-reviewee ones for the picker-selected reviewer.

## Rule-engine integration

Segment 13A's rule engine
(`guide/archive/segment_13A_rulebased_assignment_builder.md`) is the
natural place to materialize group assignments. When the
operator runs assignment generation against a group-scoped
instrument:

1. The engine reads each reviewee's tag values for the keys in
   `group_kind` (one key, or several for a composite).
2. Reviewees clustered by that tag tuple form **groups** — the
   group identifier is the shared tuple (e.g. all reviewees with
   `tag_1="Team Alpha"` form one group; or, for a composite,
   all reviewees matching on `(tag_1, tag_2, tag_3)`).
3. For each `(reviewer, group)` pair the rule selects, the
   engine emits **one `Assignment` per group member** (i.e. the
   matrix is fanned out per-member). The rows are ordinary
   `(reviewer, reviewee, instrument)` assignments — nothing is
   stamped; the group is recoverable from each reviewee's
   grouping tags.
4. The reviewer surface sees N rows for the group on the wire,
   clusters them by the derived `group_id` (the reviewee tag
   tuple) into one logical row in the rendered template, and
   writes the reviewer's single answer back to all N rows on
   submit.

**FullMatrix needs no engine change.** Its output is already
"every reviewer × every reviewee" — for a group-scoped
instrument that is exactly the per-member fan-out, and the
reviewer surface does the clustering on read. Group-aware
*RuleBased* selection — a quota / predicate rule that picks
whole groups rather than individuals — is a later concern; the
first cut is FullMatrix-only.

Manual CSV imports are tricky for group-scoped instruments
because the operator would have to write multiple rows that
share a `group_id` — a footgun. The simplest first cut: Manual
mode is **disallowed** for group-scoped instruments; operators
use rule mode (FullMatrix or a future RuleBased) to materialize
group assignments. If a real need shows up, Manual could later
accept a `group_id` column on the CSV.

## Aggregation contract

A single helper centralizes the group-aware aggregation. Proposed
shape (subject to revision when 13A reaches the planning stage):

```python
# app/services/responses.py (proposed)

def collapse_group_duplicates(
    rows: Iterable[ResponseRow],
) -> list[ResponseRow]:
    """Collapse N group-duplicate response rows back to one.

    For each input row that belongs to a group-scoped instrument,
    derive its ``group_id`` (the tuple of the reviewee's tag
    values for the keys in the instrument's ``group_kind``) and
    emit a single row keyed on
    ``(reviewer_id, response_field_id, group_id)``
    with the shared value. Per-reviewee rows pass through
    unchanged.

    Consumers that need the *fanout* shape (e.g. a CSV export
    where each group member should appear as a separate row,
    with the value duplicated) call ``rows`` directly without
    routing through this helper.
    """
```

Every consumer that aggregates by reviewee or reports
"completion" routes through the helper. The contract: a single
group response counts as **one completion** at the
group-scoped-instrument level, not N. The Manage Invitations'
Review Progress column reports per-reviewer completions
correctly because the count is "instruments where this reviewer
has answered everything" — a per-reviewer-per-instrument metric
that doesn't care about the underlying fanout.

### Materializing the group identity at extraction

The group identity is *derived*, not stored — but that's a
storage decision, not an output one. At the point of
extraction, the Extract Data exports **should surface the
derived group identity as explicit columns** on the exported
rows, even though no group column exists on `Response`. One
column per `group_kind` key (e.g. `Cohort`, `Class`, `Small
Group`) carrying that row's tag-tuple facets, so the export
reads standalone — a human opening the CSV sees which group a
response belongs to without re-joining to `Instrument` +
`Reviewee` themselves.

This holds for both export shapes: the collapsed shape (one row
per group) and the fanout shape (one row per member). The
exporter computes the facets the same way `collapse_group_duplicates`
derives `group_id` — reading the instrument's `group_kind`
keys against each reviewee's tags — and writes them as ordinary
columns. Per-reviewee (non-group) instruments simply leave
these columns blank.

## What's out of scope

- **Per-question group scope.** Rejected (see Rationale).
- **Multi-level grouping in one instrument.** Rejected — one
  instrument renders rows at a single granularity only, never a
  small-group block *and* a cohort block together. This is
  distinct from a **composite** `group_kind` (supported): a
  composite is still one granularity, named by a tuple of tags.
  See "One grouping per instrument".
- **Mode-flipping after creation.** Rejected. Operators delete
  and recreate.
- **DB schema modifications.** Rejected — and not needed. The
  duplicate-`Response`-rows + derive-the-group approach carries
  the whole feature with zero migrations: `Response` keeps its
  single-reviewee FK shape, and `Instrument.group_kind` already
  exists.
- **A separate `Group` entity.** Not needed for this design —
  the group identifier is just a tag value or tag tuple (or a
  hash of one).
  If a future feature needs richer group metadata (a description,
  a membership history, etc.), a `Group` table can be added
  without disturbing the rest of this spec.
- **Manual CSV mode for group-scoped instruments.** Out of scope
  for the first cut; rule mode only.

## Open questions

- **Group name source.** A group's display name is built from
  its grouping-tag values — one facet per `group_kind` key,
  joined in key order (see Reviewer surface). If groups ever
  need a human-readable name *distinct* from the grouping tags
  themselves, a dedicated display tag or a `Group` lookup table
  would be the path. Defer until an operator asks.
- **Cohort vs Small Group vocabulary.** Whether `Instrument.group_kind`
  stores the source-field key (`tag_1`) or a domain label
  (`small_group`) is an open call. Source-field key is more
  honest; domain label reads better. A small mapping table on
  the operator UI ("Tag 1 = Small Group") could bridge them.
- **Reviewer-surface header copy.** "Small Group: Team Alpha —
  Alice, Bob, Carol" reads cleanly when the group has 3-5
  members; for larger groups it gets unwieldy. A "+N more"
  truncation pattern with a hover-to-expand affordance is
  probably the right answer; lock the copy when the work
  starts.
- **Group-scoped reminders / responses-received emails.** A
  reviewer who hasn't answered a group-scoped question — does
  the reminder say "you have unanswered group ratings" or list
  the groups individually? Probably the former (the reminder
  doesn't need to enumerate groups), but worth confirming with
  an operator before shipping.

## Cross-references

- `app/db/models/instrument.py` — `group_kind` column (already
  exists, shipped inert in 13D PR 6).
- `app/db/models/reviewee.py` — `tag_1` / `tag_2` / `tag_3`
  columns; the tuple of the reviewee's values for the
  `group_kind` keys is the derived `group_id`.
- `app/services/instruments/_display_fields.py` — `DISPLAY_FIELD_LABELS` /
  `DISPLAY_FIELD_KEYS` mappings; group-scoped instrument editor
  picks against a restricted subset of the same registry.
- `guide/archive/segment_13A_rulebased_assignment_builder.md` — likely
  home for the rule-engine work that materializes group
  assignments.
- `spec/sort_by_reviewee.md` — the other in-flight reviewer-
  surface spec; group-scoped instruments interact with sort UX
  only loosely (a group-scoped sub-table sorts by group name,
  not by individual reviewee).
- `spec/architecture.md` — domain hierarchy. The
  group-scoped-instrument addition doesn't change the
  hierarchy; it only adds a flavour to the existing
  Instrument entity.
- `spec/preview_hub.md` — group-scoped instruments render in
  the reviewer-surface preview card alongside per-reviewee
  ones.
