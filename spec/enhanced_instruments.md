# Enhanced instruments — group-scoped review

**Status.** Forward-looking design spec. Not yet implemented.
Captures the design for a second kind of instrument — a
**group-scoped instrument** — alongside today's per-reviewee
instrument, so a reviewer can record one rating / comment / etc.
about a *group* of reviewees rather than per-individual.

This file is the source of truth for the design. Implementation
plan lives at **`guide/segment_13C_enhanced_instrument.md`**;
13C also picks up the duplicate-instrument button on the same
action-row sweep. Sibling segments: **13A** (rule-based
assignments — `guide/archive/segment_13A_rulebased_assignment_builder.md`)
and **13B** (sort by reviewee —
`guide/segment_13B_sort_by_reviewee.md`). The three are
independent and can ship in any order, though 13A's rule engine
is the natural place to materialize group assignments and 13C
PR 3 leans on it.

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

## One grouping level per instrument

A group-scoped instrument carries **one** grouping level — small
group, cohort, team, etc. The instrument's `group_kind` scalar
identifies which level. **The same instrument cannot generate
rows for multiple grouping levels** (e.g. one instrument
producing "rate your small group" + "rate your cohort" rows for
the same reviewer).

The reasoning mirrors the per-question argument: the reviewer
seeing "rate the team's collaboration" twice with two different
group memberships (Small Group: Team Alpha vs Cohort: Spring
2026) is exactly the cognitive trap to avoid. Operators who
genuinely need both author two instruments. If
"instrument template / clone" ships later, the duplication cost
goes to roughly zero.

`group_kind` starts as a scalar on `Instrument`. If a future
power-user case demands multi-level, the column lifts to a list
in a forward-compatible way. The strict default keeps most
operators out of the complexity.

## Data model — no schema change to `Response`

The trick: **duplicate `Response` rows per group member**, but
stamp each underlying `Assignment` with group metadata so
downstream consumers can collapse the duplicates back to one.

- `Assignment.context` (already a `Mapped[dict[str, Any] | None]`
  JSON column on `app/db/models/assignment.py`, currently unused)
  carries `{"group_id": "team-alpha", "group_kind":
  "small_group", "group_size": 5}` on every assignment that
  belongs to a group-scoped instrument.
- The reviewer surface presents **one** set of response inputs
  per group, shaped against the response fields of the group-
  scoped instrument; submit writes the same value to every
  underlying `Assignment`'s response rows (one per group
  member), all stamped with the same `Assignment.context`.
- Downstream code that aggregates by reviewee — Manage
  Invitations' Review Progress column, the Responses page's
  per-reviewee coverage, the Extract Data exports — routes
  through one shared helper (proposed name:
  `responses.collapse_group_duplicates(rows)`) that groups by
  `(reviewer_id, response_field_id, context.group_id, value)`
  and returns either the deduped row or the per-reviewee fan-
  out, depending on the consumer's needs.

This keeps `Response.assignment_id` strictly single-reviewee —
no nullable FKs, no polymorphic target — and lets every existing
non-group-aware query keep working unchanged. Group awareness is
opt-in per consumer.

**Trade-off.** The dedup logic must be honored everywhere data
leaves the system or rolls up. Exports especially: a missed
dedup in a CSV export over-counts group responses by `group_size`.
The single helper + a unit test pinning the contract is the
defense; reviewing every aggregator's call site for migration is
mandatory when the feature ships.

### Proposed schema additions

| Field | Where | Type | Notes |
|---|---|---|---|
| `group_kind` | `Instrument` | `String(32) | NULL` | `NULL` = per-reviewee instrument (today's default). Non-null = group-scoped. Operator-facing values are a small enum mapped from the Display Field that defines the group (e.g. picking `tag_1` ⇒ `group_kind="tag_1"`). The display label ("Small Group", "Cohort", "Team", etc.) lives in operator copy; the column stores the source-field key. |
| `Assignment.context` (existing) | `Assignment` | `JSON | NULL` | Already on the model. New documented keys for group-scoped assignments: `group_id` (string identifying the group — typically the source-field's value), `group_kind` (mirror of the instrument's), `group_size` (int — for sanity / dedup checks). |

`Instrument.group_kind` can be a scalar enum string (`tag_1` /
`tag_2` / `tag_3`) or a small lookup-table FK to a future
`group_definitions` table. Scalar string is the simpler start and
forward-compatible.

## Operator editor

### Creation

Two creation entrypoints on `/operator/sessions/{id}/instruments`:

- **Add an instrument** — today's button. Creates a per-reviewee
  instrument (`group_kind=NULL`).
- **Add a group-scoped instrument** — new button. Opens a small
  inline dialog asking which reviewee tag identifies the group
  (Tag 1 / Tag 2 / Tag 3). Creates a group-scoped instrument with
  `group_kind` set to the chosen tag.

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
- The tag chosen as `group_kind` at creation is locked into the
  display-fields list as the "group identity" column at
  position 0; operators can still re-order or hide the other
  two tags.
- Response fields, descriptions, ordering, accepting-responses
  / visibility toggles, and the Save / Edit / Delete affordances
  are unchanged.

A small visual chip near the instrument-card heading reads
**Group-scoped (by Tag 1)** so the operator never wonders which
mode they're editing.

## Reviewer surface

A group-scoped instrument renders as a self-contained block on
the reviewer surface, distinct from per-reviewee instrument
blocks:

- **Heading** — instrument's operator-editable description, same
  as today.
- **Group identity row** — for each group the reviewer is
  assigned on, one labeled row reads e.g.
  `Small Group: Team Alpha — Alice, Bob, Carol` (the group name
  comes from the source-field value; the member names from
  joining `Assignment` rows back to their reviewees). A single
  set of response inputs sits on that row — one rating, one
  comment, etc., for the whole group.
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

1. The engine reads each reviewee's `tag_N` value (the
   `group_kind` source).
2. Reviewees clustered by that value form **groups** — the
   group identifier is the shared tag value (e.g. all reviewees
   with `tag_1="Team Alpha"` form one group).
3. For each `(reviewer, group)` pair the rule selects, the
   engine emits **one `Assignment` per group member** (i.e. the
   matrix is fanned out per-member) with `context = {"group_id":
   "team-alpha", "group_kind": "tag_1", "group_size": 5}`
   stamped on every row.
4. The reviewer surface sees N rows for the group on the wire,
   collapses them by `context.group_id` into one logical row in
   the rendered template, and writes the reviewer's single
   answer back to all N rows on submit.

FullMatrix can also support group-scoped instruments by treating
each unique `tag_N` value as a target instead of each individual
reviewee. The engine's emission shape (one row per member,
shared `context.group_id`) is the same.

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

    For each input row whose underlying assignment carries a
    ``context.group_id``, emit a single row keyed on
    ``(reviewer_id, response_field_id, group_id)`` with the
    shared value. Per-reviewee rows pass through unchanged.

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

## What's out of scope

- **Per-question group scope.** Rejected (see Rationale).
- **Multi-level grouping in one instrument.** Rejected.
  `group_kind` is a scalar.
- **Mode-flipping after creation.** Rejected. Operators delete
  and recreate.
- **DB schema modifications to `Response` or its FK shape.**
  Rejected. The duplicate-and-stamp trick on
  `Assignment.context` carries the whole feature without
  touching `Response`.
- **A separate `Group` entity.** Not needed for this design —
  the group identifier is just a tag value (or a hash of one).
  If a future feature needs richer group metadata (a description,
  a membership history, etc.), a `Group` table can be added
  without disturbing the rest of this spec.
- **Manual CSV mode for group-scoped instruments.** Out of scope
  for the first cut; rule mode only.

## Open questions

- **Group name source.** The simplest answer is "the value of the
  source tag" (e.g. `tag_1="Team Alpha"`). If groups need richer
  display names (a separate "human-readable" tag), the
  `group_kind` column could expand to a tuple — `(id_tag,
  display_tag)`. Defer until an operator asks.
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

- `app/db/models/assignment.py` — `Assignment.context` column
  (already exists).
- `app/db/models/instrument.py` — gains `group_kind` column.
- `app/services/instruments.py` — `DISPLAY_FIELD_LABELS` /
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
