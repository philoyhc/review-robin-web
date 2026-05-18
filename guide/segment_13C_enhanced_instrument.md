# Segment 13C — Enhanced instruments

> **Re-scoped 2026-05-15 — investigation update.** The original
> 13C design stamped per-instrument group metadata onto the
> `Assignment.context` JSON column. That column was retired in
> 15D PR 6b (`pair_context_*` keys lifted to the `relationships`
> table; `assignment_context_*` retired entirely). An
> investigation confirmed this is **not** a blocker: a group is
> fully derivable from `Instrument.group_kind` + the reviewee's
> own `tag_N` value — `Assignment.context` only ever held a
> *stamped copy* of derivable data. **Decision (2026-05-15):
> derive the group live; no `Assignment` schema change, and 13C
> needs no migration at all** (`Instrument.group_kind` already
> shipped inert in 13D PR 6). 15B (Per-instrument assignments)
> has shipped, so 13C is unblocked. The PR ladder, schema
> section, and mechanism description below were rewritten to
> match; the pre-2026-05-15 design (context-stamping, rule-engine
> fanout PR, 5 PRs) is superseded.

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

Planning — re-scoped 2026-05-15. `Instrument.group_kind`
(`String(32) | NULL`) already shipped inert in 13D PR 6, and the
derive-the-group decision (see "How a group is derived" below)
removes the rule-engine fanout PR + the `Assignment.context`
stamping the original plan called for. Net: **3 PRs, zero
migrations.**

### PR 1 — Operator editor: "Add a group-scoped instrument"

New action-row button alongside the existing "Add new
instrument". An inline dialog asks which reviewee tag(s) (Tag 1 /
Tag 2 / Tag 3) identify the group — one for a simple grouping,
several for a composite; pick order sets key order. Creation
sets `group_kind` to the comma-joined key list (e.g. `"tag_1"`
or `"tag_1,tag_2,tag_3"`) on the new instrument. The
group-scoped editor restricts display fields to the three
reviewee tags, locks the `group_kind` tags into the leading
positions in key order, and shows a per-card chip
"Group-scoped (by Tag 1)" (or "… by Tag 1 + Tag 2" for a
composite). Mode is set at creation and is not toggleable
(operators delete + recreate). Audit event
`instrument.created_group_scoped`.

No schema change — `group_kind` already exists. After PR 1,
group-scoped instruments can be authored and generate
`Assignment` rows normally (FullMatrix produces standard
`(reviewer, reviewee)` rows); the reviewer surface still renders
them per-reviewee until PR 2. The operator's `accepting_responses`
toggle (default `False`) is the gate against premature reviewer
exposure in that interim.

### PR 2 — Reviewer surface: group blocks + write fanout + aggregation sweep

The end-to-end reviewer-facing feature, landed as one PR so
there is never a window where group responses exist but
aggregators over-count them.

- A service helper derives group membership: given a
  group-scoped instrument and a reviewer's assignments for it,
  cluster by `reviewee.tag_N` (N from `group_kind`).
- The reviewer surface renders a group-scoped instrument as a
  self-contained block — one group-identity row per group
  (source-tag value + member names), one set of response
  inputs. Read path collapses the N member assignments into one
  logical group row; the preview hub renders the same blocks.
- Submit fans the reviewer's single answer across all N
  assignments' response rows for the group.
- `responses.collapse_group_duplicates(rows)` + the mandatory
  sweep migrating every aggregator (Manage Invitations Review
  Progress, Responses page coverage, Extract Data exports) — see
  "Aggregation contract" below.

FullMatrix needs **no engine change** — its output is already
"every reviewer × every reviewee", which the surface clusters by
tag. RuleBased group-selection (a quota rule that selects whole
*groups* rather than individuals) is **out of scope** for the
first cut — rule mode means FullMatrix here. Manual CSV mode is
disallowed for group-scoped instruments.

> **Sizing note.** PR 2 is the largest PR. Split into 2a
> (render + write fanout) / 2b (aggregation sweep) **only** if
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
of the source's state. Audit event `instrument.duplicated`
carries the source + new instrument IDs.

Independent of PRs 1-2 — can land in any order relative to them.

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
| `Add group-scoped instrument` | Secondary | Always visible. **New (PR 1).** Creates a group-scoped instrument inserted immediately after this one. |
| `Duplicate instrument` | Secondary | Always visible. **New (PR 3).** Clones this instrument's content; new card inserted immediately after the source. |

`Edit` / `Save` / `Cancel` remain mutually exclusive per the
existing spec; the three create-flavour buttons (`Add new`,
`Add group-scoped`, `Duplicate`) are always present and never
contend with the editing-state machine.

`Delete this instrument` continues to live in the right-hand
Danger Zone card per `spec/instruments.md` Section C.

## Schema — none required

13C ships **zero migrations.**

- **`Instrument.group_kind`** (`String(32) | NULL`) already
  exists — shipped inert in 13D PR 6. `NULL` = a per-reviewee
  instrument (today's default); a non-null value is an ordered,
  comma-joined list of one or more distinct source-field keys
  (`tag_1` / `tag_2` / `tag_3`) naming the reviewee tag(s) that
  define the group — e.g. `tag_1` for a simple grouping or
  `tag_1,tag_2,tag_3` for a composite. The longest list is 17
  characters, so `String(32)` already fits — still zero
  migrations. The operator-facing display label
  ("Group-scoped (by Tag 1)") lives in template copy. 13C PR 1
  is the first writer of this column.
- **No `Assignment` change.** The original design stamped
  `Assignment.context` JSON with `{group_id, group_kind,
  group_size}`; that column was retired in 15D PR 6b. It is not
  needed — every value is derived (see below).
- **No `Response` change.** `Response.assignment_id` stays
  strictly single-reviewee. The write path fans one answer to N
  response rows, but each row is still an ordinary
  single-assignment `Response` — no nullable FKs, no
  polymorphic target.

## How a group is derived

A group-scoped instrument's `group_kind` is a comma-joined list
of one or more keys drawn from {`tag_1`, `tag_2`, `tag_3`}. For
any reviewer, their group memberships for that instrument are
computed live:

1. Take the reviewer's `Assignment` rows for the instrument.
2. Join each to its `Reviewee` and read the reviewee's value for
   every key in `group_kind` (`Reviewee.tag_1` / `tag_2` /
   `tag_3` — these columns exist), forming a tag tuple.
3. Reviewees sharing the same tag tuple form one **group**; that
   tuple *is* the group identity (`group_id`).
4. `group_size` = the count of distinct reviewees in the
   cluster.

No value is stored — `Assignment.context` was only ever a
stamped copy of this. The reviewer surface clusters on read, the
submit path fans on write, and `collapse_group_duplicates`
groups on the same derived key.

**Trade-off (accepted 2026-05-15).** Deriving live means group
membership tracks the reviewee's *current* grouping tags. If an
operator edits one of those tags after assignments are
generated, that reviewee re-clusters. In practice this is benign: editing
session entities after activation requires reverting to draft,
which regenerates assignments anyway. Freezing membership at
generation time would have needed a new stamped `Assignment`
column — deliberately not done.

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
- **Multi-level grouping in one instrument** — one instrument
  renders rows at a single granularity only. A *composite*
  `group_kind` (a tuple of tags naming one granularity) is
  supported and is not this rejected case — see the spec's
  "One grouping per instrument".
- **Mode-flipping after creation** — operators delete and
  recreate.
- **Manual CSV mode for group-scoped instruments** — rule mode
  only first cut.
- **RuleBased group-selection** — a quota / predicate rule that
  selects whole *groups* (rather than individuals) then fans to
  members. First cut is FullMatrix-only, which needs no engine
  change. Group-aware RuleBased selection is a later concern.
- **A separate `Group` entity** — the group identifier is just
  a tag value.
- **Cross-session instrument duplication / templates** — the
  duplicate button copies *within a session* only. A "save
  this instrument as a template" feature is a separate concern
  if it ever surfaces.

## Aggregation contract for group-scoped responses

PR 2 introduces `responses.collapse_group_duplicates(rows)` per
the spec. It collapses the N group-duplicate response rows to
one, keyed on `(reviewer_id, response_field_id, group_id)` where
`group_id` is the **derived** group identity (the tuple of the
reviewee's `group_kind`-tag values — see "How a group is
derived"), not a stored field. Every consumer that aggregates by reviewee or reports
"completion" routes through the helper:

- `views.build_invitations_rows` — Review Progress column.
- `views.build_responses_rows` — Responses page coverage.
- Extract Data exports (the per-entity + unified exporters).

The contract: a single group response counts as **one
completion** at the group-scoped-instrument level, not N. The
test suite gains a single shared fixture (a group-scoped
instrument with N assignments and one rendered response) +
assertions against each consumer's output.

The work in PR 2 includes a sweep over every aggregator
identified above; missing one means an export over-counts
group responses by `group_size`. Reviewer's note pinned in the
PR description: this sweep is mandatory.

PR 2's Extract Data work also **materializes the derived group
identity as explicit columns** on the exported rows — one
column per `group_kind` key — so the CSV reads standalone (see
the spec's "Materializing the group identity at extraction").
The group identity stays unstored; only the *export* surfaces
it as columns, computed the same way `collapse_group_duplicates`
derives `group_id`.

## Relationship to Segment 13A and 13B

13A, 13B, and 13C are siblings — independent of each other,
shippable in any order. See
[`segment_13B_sort_tables.md`](segment_13B_sort_tables.md)
"Relationship to Segment 13A and 13C" for the per-segment
surface map.

## Doc impact

When 13C kicks off:

- Update `spec/instruments.md` Section C "Action row" to
  describe the two new buttons (Add group-scoped instrument,
  Duplicate instrument) and the post-13C button set.
- Update `spec/reviewer-surface.md` to describe the group-block
  treatment for group-scoped instruments.
- Update `guide/todo_master.md` to move 13C from Upcoming to
  in-progress; move to Done when PR 3 lands.
- Migrate this file to `guide/archive/` when PR 3 merges.
- `spec/group_scoped_instruments.md` ticks off when each
  Open question / Out-of-scope item from its design spec
  resolves.

## Ride-along — Segment 18D Part 3

Segment 18D (Export and import update) handed its **Part 3** to
13C: once group-scoped instruments exist, the analysis-facing
Responses extract (`extracts/responses_extract.py`) should gain a
derived `Instrument` *flavour* column so downstream analysis can
split group-scoped answers from per-pair answers without
re-deriving from the schema. Add it as a small ride-along when
13C ships — see `guide/archive/segment_18D_export_and_import_update.md`
Part 3.
