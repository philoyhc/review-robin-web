# Instrument chain builder

> **Stub created 2026-05-22.** Sketch-level scope only. Detailed
> PR breakdowns get drafted when this work is picked up.

A forward-looking UI + data design for a **unified
"instrument chain" builder** that exposes the five key decisions
about an instrument — who reviews, who the reviewer's reviewee
pool is, the unit of review (individual vs group), who can see
the responses, and what they can see — as one card per link in
a chain. Replaces today's "Identity + Assignment Rule" half-card
pair on the per-instrument card with a five-link layout.

This is a generalisation of the existing per-instrument
[`spec/rule_based_assignment.md`](../spec/rule_based_assignment.md)
contract: the rule engine currently solves only Link 2 (the
reviewee pool), and the group-scoped instrument flag from
[`spec/group_scoped_instruments.md`](../spec/group_scoped_instruments.md)
solves only Link 3 (the unit of review). Links 1, 4, and 5 are
net-new conceptual slots; each layers a different policy on top
of an instrument.

---

## Goal

For each instrument in a session, let the operator pin a
complete **review chain** in one screen — answering, in turn:

1. **Who are the reviewers?** Which subset of the session's
   reviewer roster fills out this instrument.
2. **Who is each reviewer reviewing?** Per-reviewer reviewee
   *pool* — the existing rule-engine job, expressed over
   reviewee tags, pair-context tags, and cross-side relations
   with reviewer tags.
3. **What is the unit of review?** Whether the reviewer reviews
   each reviewee individually (one row per reviewee) or
   partitions the pool into groups by reviewee tags and reviews
   one row per group.
4. **Who can see the responses?** Which cohorts (operators only,
   reviewees themselves, tagged observers) can read responses
   once they are saved.
5. **What can they see?** Whether the responses are surfaced as
   raw values, summarised aggregates, or anonymised cells.

Today the operator answers these five questions in different
places (some on the Setup pages, some on Instruments, some
nowhere — Links 4 and 5 do not exist in the system yet, and
Link 3 lives only as a binary group-scoped flag + an in-table
boundary-tag selector). The chain builder collects them into
one continuous editor.

---

## Why one card per link

Each link in the chain depends on the link before it: scoping
the reviewee pool only makes sense once reviewers are scoped;
the unit of review (individual vs group) only makes sense once
the pool is known; visibility only makes sense once the
response set exists; the read-shape (raw / summary /
anonymised) only makes sense once the visibility audience
exists.

Rendering the five as a left-to-right chain of equal-width cards
makes the dependency explicit. It also gives the operator a
single instrument-level surface to inspect the *policy* an
instrument is enforcing — today, Link 2 lives on the per-
instrument card, Link 3 lives as a binary group-scoped flag
plus boundary-tag checkboxes inside the Display Fields table,
Link 4 lives only in operators' heads, and Link 5 has nowhere
to live at all.

The chain is **per instrument**, not per session. Two instruments
in the same session can carry different chains (e.g. a peer-
review instrument with reviewee visibility + anonymised reads,
alongside a self-assessment instrument with operator-only
visibility and raw reads).

---

## The four links

### Link 1 — Reviewer scope

**Question.** Which reviewers on the session's roster fill out
this instrument?

**Today.** Every reviewer on the active roster is implicitly
assigned to every instrument the rule engine produces a pair for.
There is no per-instrument way to say "this instrument is filled
out only by managers" — the operator either splits the roster
across sessions or carries a separate matching session for the
subset.

**Proposed inputs.** A predicate over the session's reviewer
roster, expressed in the same vocabulary the existing rule
engine speaks:

- **Reviewer tags** — `reviewer.tag1 / tag2 / tag3`. Same three
  free-form attribute slots reviewer rows already carry.
- **Pair-context tags** — `pair.tag1 / tag2 / tag3` from the
  Relationships table. Quantified existentially over the
  reviewer's active relationship rows: "this reviewer has at
  least one active relationship row where `pair.tag1 == X`".

The default chain leaves Link 1 empty — every active reviewer is
in scope.

**Output.** A filtered reviewer set that Link 2 then projects
reviewees from.

**Audit footprint.** New emitter
`instrument.reviewer_scope_updated` carrying a before/after diff
of the predicate JSON.

### Link 2 — Reviewee pool per reviewer

**Question.** For each reviewer in Link 1's set, which reviewees
form their *pool* on this instrument? (The pool — not yet the
unit of review; that's Link 3.)

**Today.** This is the existing per-instrument rule engine,
fully specced in
[`spec/rule_based_assignment.md`](../spec/rule_based_assignment.md).
The instrument pins one RuleSet (seeded or personal) whose
MATCH / FILTER / QUOTA predicates select `(reviewer, reviewee)`
pairs from the session's roster.

**Proposed inputs.** Unchanged from today. The chain builder
embeds the existing Rule Builder card's affordances:

- **Reviewee tags** — `reviewee.tag1 / tag2 / tag3`.
- **Pair-context tags** — `pair.tag1 / tag2 / tag3`.
- **Cross-side relations** — `same_as`, `different_from` against
  reviewer fields.

**Composition with Link 1.** The rule engine runs only over
pairs `(r, e)` where `r ∈ Link1.reviewers`. The eligible-pair
count cache that already lives on the per-instrument card (the
Segment 13C reviewer-group-pair counter) covers both filters.

**Audit footprint.** Existing `assignments.generated` event;
the canonical `excluded_counts` envelope captures the Link 1
+ Link 2 join.

### Link 3 — Unit of review

**Question.** Does the reviewer review each reviewee in their
pool *individually* (one row per reviewee), or are reviewees
*grouped* (one row per group)?

**Today.** A binary `Instrument.group_kind` flag splits
instruments into per-reviewee and group-scoped variants;
group-scoped instruments partition the reviewer's pool by
operator-marked boundary tags on the Display Fields table.
The mode is set at instrument creation and is one-way (delete
and recreate to switch). See
[`spec/group_scoped_instruments.md`](../spec/group_scoped_instruments.md)
for the full contract.

**Proposed inputs.** A unit-of-review choice:

- **Individual** (the default) — one row per
  `(reviewer, reviewee)` pair on the reviewer surface; one
  response row per pair × response field. Equivalent to today's
  per-reviewee instrument.
- **Grouped** — the reviewer's pool partitions by **reviewee
  tags** marked as boundary tags. One row per group; writes
  fan out to every group member on save. Equivalent to today's
  group-scoped instrument.

**Boundary-tag selection.** When **Grouped** is chosen, the
sub-card carries a multi-select over the three reviewee tag
slots (`reviewee.tag1 / tag2 / tag3`) marking which combinations
define a group. Picking zero tags collapses the whole pool into
one group. Picking one or more tags makes group membership = the
set of reviewees sharing the *same value* in each picked tag.
(Pair-context tags are deliberately **not** in scope for Link 3
— group identity is a property of the reviewee, not of the
reviewer-reviewee relationship.)

**Composition with Link 2.** Link 3 partitions Link 2's pool;
it does not re-select reviewees. A reviewee Link 2 excluded
from the pool cannot reappear via a group-boundary computation.

**Mode switching.** Switching unit of review *after* responses
exist needs the same reconciler discipline as Link 2 edits
(see [§Cross-cutting concerns / Reconciling regeneration](#reconciling-regeneration)):
switching Individual → Grouped collapses the per-pair responses
into per-group responses with one chosen as canonical and a
prompt for the operator to confirm the data loss; switching
Grouped → Individual fans the per-group response out into
identical per-pair responses (no data loss) but flips the
reviewer surface from "one row per group" back to "one row per
reviewee".

**Audit footprint.** New emitter
`instrument.unit_of_review_updated` carrying the mode +
boundary-tag selection diff.

### Link 4 — Visibility scope

**Question.** Once a response is saved on this instrument, who
is allowed to read it?

**Today.** Operators only. The reviewer who wrote the response
can see their own work on the review surface; nobody else (not
the reviewee, not other operators outside the session, not
peers) has a read path. Response export to the operator's
chosen analytical tool is the only outbound channel.

**Proposed inputs.** A choice of one or more visibility
audiences, each independently configurable:

- **Operators only** — the today-default. Every owner of the
  session can read every response.
- **Reviewees themselves** — each reviewee gets a read view of
  every response *about them*. (Cross-reviewer aggregation
  happens in Link 4.)
- **Observers** — a tag-defined cohort of session members who
  read responses about a specific reviewee. Two sub-variants:
  - **Reviewee-tag-defined observers** — "every active reviewer
    whose `reviewer.tag1 == reviewee.tag1` can see responses
    about that reviewee" (e.g. a manager observes their direct
    reports).
  - **Pair-context-defined observers** — "every active reviewer
    with a relationship row where `pair.tag2 == 'observer'` can
    see responses about that reviewee" (e.g. an explicit
    observer relationship).

Each audience is opt-in; the default is "Operators only" which
matches today's contract. Multiple audiences may be enabled
simultaneously (operators + reviewees + tagged observers).

**Output.** A response-row read filter that gates every
response-surfacing route (extract endpoints, future per-reviewee
dashboard, future observer dashboard).

**Open question — temporality.** Is visibility unlocked at
submission, at session close, or immediately on save? Default
proposal: **visibility unlocks at session close** (the
`accepting_responses=false` state). Per-instrument override
slot.

**Audit footprint.** New emitter
`instrument.visibility_scope_updated` plus a per-read audit
event family (`response.read_by_reviewee`,
`response.read_by_observer`) gated on a deployment-level toggle
because per-read audit can be high volume.

### Link 5 — Read shape

**Question.** When a non-operator audience (Link 4) reads a
response, what shape does the data take?

**Today.** N/A — operators read raw responses through CSV
extracts, and no other audience has a read path.

**Proposed inputs.** Three mutually-exclusive shapes per
non-operator audience:

- **Raw** — the literal value the reviewer entered.
  Recommended only when the audience is the reviewee or a
  tightly-scoped observer cohort and the operator has decided
  attribution is part of the feedback.
- **Summarised** — aggregate-only: counts, mean / median (for
  numeric RTDs), value-distribution histogram (for List /
  Yes_no RTDs), word-counts and length distributions (for
  String RTDs). No per-reviewer attribution; no per-cell text.
- **Anonymised** — per-cell content surfaced but reviewer
  identity stripped. Useful for free-text feedback the reviewee
  reads without knowing which peer wrote what.

Per-audience: an operator might let *reviewees* see anonymised
text + summarised numerics, while *observers* see raw values.

**Open question — k-anonymity floor.** Summarised and
anonymised views collapse trivially when only one reviewer
contributed. Proposed default: suppress any aggregate with
fewer than **k = 3** contributing reviewers (configurable
per instrument). Below threshold, the cell renders a
"too few responses to display" placeholder.

**Audit footprint.** New emitter
`instrument.read_shape_updated` with the per-audience
configuration diff.

---

## UI shape

One **full-width card** per instrument carrying the chain
builder, replacing the current "Identity + Assignment Rule"
two-half-card row at the top of the per-instrument card.

Inside the full-width frame, five **fifth-width sub-cards** sit
in a single row (a `.bottom-grid` extended to five equal
columns), one per link. Each sub-card carries:

- A short title — `1. Reviewers`, `2. Reviewee pool`,
  `3. Unit of review`, `4. Visibility`, `5. Read shape`.
- A one-line current-state summary in body text, e.g.:
  - `1. Reviewers: All active (no filter)`
  - `2. Reviewee pool: Same-team peers (RuleSet "Intra-group peer")`
  - `3. Unit of review: Individual`
  - `4. Visibility: Operators + reviewees`
  - `5. Read shape: Reviewees see anonymised text`
- A small **Edit** button bottom-right of each sub-card.

Clicking **Edit** on a sub-card opens the link's full editor —
either inline below the chain row (preferred for visual
continuity) or as a child page in the same chrome
(`/operator/sessions/{id}/instruments/{iid}/chain/{link}`, where
`{link} ∈ {reviewers, reviewee-pool, unit-of-review, visibility, read-shape}`).
The child-page approach mirrors the existing Rule Builder
pattern; the inline approach is gentler on context but requires
more careful state management.

Sub-cards render in the same per-instrument tint as their
parent card. The Identity row (instrument number + name + short
label + status pills) moves to a thin header row above the four
sub-cards inside the same full-width card frame.

### Wireframe

```
┌─ Instrument #2 — "Peer skill assessment"  [accepting]  [showing] ──┐
│                                                                    │
│  ┌── 1. ──┐ ┌── 2. ──┐ ┌── 3. ──┐ ┌── 4. ──┐ ┌── 5. ──┐         │
│  │Review- │ │Reviewee│ │ Unit   │ │Visibil-│ │Read    │         │
│  │ers     │ │ pool   │ │ of     │ │ity     │ │shape   │         │
│  │        │ │        │ │ review │ │        │ │        │         │
│  │All     │ │Same-   │ │Indivi- │ │Operat- │ │Reviewe-│         │
│  │active  │ │team    │ │dual    │ │ors +   │ │es:     │         │
│  │        │ │peers   │ │        │ │reviewee│ │anonym- │         │
│  │        │ │        │ │        │ │them-   │ │ised    │         │
│  │        │ │        │ │        │ │selves  │ │text    │         │
│  │[Edit ▸]│ │[Edit ▸]│ │[Edit ▸]│ │[Edit ▸]│ │[Edit ▸]│         │
│  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘         │
│                                                                    │
│  ↓ (Display Fields, Response Fields, etc. continue below)          │
└────────────────────────────────────────────────────────────────────┘
```

The chain row is the *first* sub-card of the per-instrument
card, above Display Fields and Response Fields. The instrument's
Identity row collapses into the chain-card header.

### State machine

The four sub-cards share the per-instrument card's existing
**mutually-exclusive edit lock** (only one instrument can be in
edit mode at a time, and within an instrument only one of
Display Fields / Response Fields / Chain links can be open for
editing). Save / Cancel commit to the chain link being edited
without rebuilding the rest of the instrument.

When the session is `ready` (Activated), every Edit button on
the chain row is disabled, with the standard "Revert to draft
to edit" tooltip. Visibility (Link 4) and Read shape (Link 5)
edits do **not** invalidate the session back to `draft` — they
affect downstream reads, not the assignment matrix. Reviewer
scope (Link 1), Reviewee pool (Link 2), and Unit of review
(Link 3) edits **do** invalidate (they change which pairs the
assignment matrix materialises or how it collapses on the
reviewer surface). This split honours the existing
`invalidate_if_validated` discipline.

---

## Data model deltas

Tracking the five-link chain requires four schema additions —
each separable and independently shippable. Link 2 reuses the
existing per-instrument RuleSet pin; Link 3 reuses (and refines)
the existing group-scoped instrument schema.

### D1 — Reviewer scope predicate (Link 1)

A new JSON column on `instruments`:
- `reviewer_scope` — nullable JSON. When non-null, a predicate
  in the same shape as the existing rule predicates. When null,
  defaults to "all active reviewers".

### D2 — Reviewee pool (Link 2)

No schema change. The existing `instruments.rule_set_id`
column + `session_rule_sets` table carry this.

### D3 — Unit of review (Link 3)

Generalises the existing `Instrument.group_kind` flag and the
boundary-tag checkboxes that live on per-display-field rows
today. Proposed reshape:
- `unit_of_review` — enum `{individual, grouped}` on
  `instruments`. Replaces the binary group-scoped flag's role
  in lifecycle decisions.
- `group_boundary_tags` — JSON array of `reviewee.tagN` slot
  names (e.g. `["tag1", "tag3"]`). Replaces the existing
  in-Display-Fields-table boundary-tag checkboxes. The
  Display Fields table loses its boundary-tag column once this
  ships.

Mode transitions (`individual → grouped` and back) are handled
by an extension of the reconciler covering Link 2 + Link 3
together — see [§Reconciling regeneration](#reconciling-regeneration)
below.

### D4 — Visibility scope (Link 4)

A new structured column on `instruments`:
- `visibility_audiences` — JSON array of objects, each carrying
  `{audience_kind, predicate?, unlock_at}`. `audience_kind ∈
  {operator, reviewee, observer}`. `predicate` is required for
  `observer`. `unlock_at ∈ {save, submit, session_close,
  deadline}`.

Plus a downstream read-path guard that consults this column on
every response-row read by a non-operator.

### D5 — Read shape (Link 5)

A new JSON column on `instruments`:
- `read_shapes` — JSON object keyed by audience kind, valued by
  `{shape: raw|summarised|anonymised, k_anonymity_floor: int}`.

Or alternatively, merge D4 and D5 into one column carrying
`audience + shape + unlock_at` per row. The unified shape is
preferable because the three policies always travel together.

### Migrations

One Alembic revision per delta adding the new columns inert
(default null / the existing group_kind for D3). Followed by a
service layer that writes them, then a route layer that
surfaces them, then read-path guards on the non-operator
response surfaces. Each layer ships as its own PR slice.

---

## Sequencing

The chain builder is **not** a single deliverable. It is a
sequence of independently-shippable parts:

| Part | Scope | Depends on |
|---|---|---|
| **0 — Schema pre-positioning** | Inert columns on `instruments` (D1, D3, D4, D5). No behaviour change. | nothing |
| **1 — UI shell** | Replace the per-instrument card's Identity + Rule row with the five-sub-card chain layout. Sub-cards 1 / 4 / 5 are placeholder cards showing "Default" everywhere; sub-card 2 wraps the existing Rule Builder affordance unchanged; sub-card 3 reflects the current `group_kind` flag read-only. | Part 0 |
| **2 — Link 1 (reviewer scope)** | Light up the Reviewers sub-card editor + service-layer predicate evaluation in the assignment generator. | Parts 0 + 1 |
| **3 — Link 3 (unit of review)** | Promote the existing `group_kind` flag + Display-Fields-table boundary-tag checkboxes into the Unit-of-review sub-card editor. Add post-creation mode-switching backed by the reconciler. Display Fields table loses its boundary-tag column. | Parts 0 + 1 |
| **4 — Link 4 (visibility, operator + reviewee audiences)** | Light up the Visibility sub-card editor. Per-reviewee read path on a new `/reviewer/sessions/{id}/{position}/about-me` surface (the reviewee dashboard the audience model has long anticipated). | Parts 0 + 1 |
| **5 — Link 5 (read shape, summarised + anonymised for reviewee audience)** | Light up the Read shape sub-card editor. Aggregator service computing summaries; anonymisation transformer; k-anonymity floor enforcement. | Part 4 |
| **6 — Link 4 (observer audiences)** | Reviewee-tag-defined and pair-context-defined observer audiences. Observer dashboard surface. | Part 4 |
| **7 — Link 5 (read shape for observer audiences)** | Per-observer-audience read shape configuration. | Parts 5 + 6 |

Parts 0 + 1 must land in that order. After Part 1, parts 2 / 3
/ 4 are independent and can interleave. Parts 5 / 6 / 7 depend
on their respective earlier parts as noted.

---

## Cross-cutting concerns

### Validation surface

Each link in the chain contributes new validation rules:

- **Link 1** — predicate references unknown tag slots; predicate
  excludes every active reviewer (empty reviewer set is an
  error, not a warning).
- **Link 2** — existing rule-engine validation, unchanged.
- **Link 3** — when **Grouped**, at least one boundary tag must
  be selected *or* the operator explicitly opts in to "single
  group covering the whole pool". A boundary tag referencing an
  unknown reviewee tag slot is an error. A boundary tag with
  zero non-empty values across the reviewee roster is a warning
  (the partition will collapse to one group at runtime).
- **Link 4** — observer-audience predicate references unknown
  tag slots; visibility-audience set is empty (every instrument
  must have at least Operators).
- **Link 5** — k-anonymity floor is achievable given the
  generated assignment count (warning, not error, since rosters
  may grow later).

Every rule lands as a `ValidationRule` in the existing registry
(see [`spec/validate_page.md`](../spec/validate_page.md)) and
surfaces on the Validate page with the standard "Fix on Chain
Builder ↗" deep-link.

### Friendly labels

The chain editors consume the existing friendly-label registry
(see `spec/setup_pages.md` and [`spec/settings_inventory.md`](../spec/settings_inventory.md)
for the 12 in-scope slots). Predicates render with
operator-customised labels for `reviewer.tag1` etc.; raw machine
names live only in the JSON payloads and audit events.

### Group-scoped instruments

Link 3 *is* the group-scoped-instrument concept, generalised:
the existing binary `group_kind` flag and the Display-Fields-
table boundary-tag checkboxes (see
[`spec/group_scoped_instruments.md`](../spec/group_scoped_instruments.md))
become the Unit-of-review sub-card. The downstream behaviour —
write fan-out across group members, read-time collapse to one
row per group, aggregation semantics on monitoring and extract
surfaces — carries forward unchanged.

Link 4's visibility model for grouped instruments needs an
explicit rule: a reviewee in a group sees the group's response,
not the per-member fan-out — i.e. the existing read-time
collapse continues to apply. (Two members of the same group
therefore see the same response when the Reviewees audience is
enabled.)

### Reconciling regeneration

Editing Link 1 (reviewer scope), Link 2 (reviewee pool), or
Link 3 (unit of review) changes either which pairs the
assignment matrix materialises or how they collapse on the
reviewer surface. The existing reconciler
([`spec/reconciling_regeneration.md`](../spec/reconciling_regeneration.md))
already handles Links 1 and 2 — pairs the new chain drops
cascade-delete their responses; pairs the new chain keeps
preserve theirs; the super-button dry-runs the impact and
prompts when responses would be lost.

Link 3's mode switching is a new reconciler responsibility:

- **Individual → Grouped.** Per-pair responses collapse into
  per-group responses. The reconciler picks one canonical
  value per group (proposed: the most-recently-saved per
  member, with the operator-confirmed alternative of "first
  saved"). Members whose values are dropped lose their
  individual response. The super-button dry-run names every
  reviewee whose response would be merged-away.
- **Grouped → Individual.** Per-group responses fan back out to
  per-pair responses by duplicating the group value into every
  member's row. No data loss; every member now carries the
  same value as their starting point, which the reviewer can
  edit per-pair on the next save.

### CSV round-trip

The Settings CSV ([`spec/csv_contracts.md`](../spec/csv_contracts.md))
must learn to round-trip the four-link chain. Each link's
predicate / configuration travels as one or more rows in the
Settings CSV's per-instrument section. The CSV is the
historical baseline for round-trip stability — the new columns
must not break it.

---

## Open questions

1. **Inline editor vs child page.** The Rule Builder lives on
   its own child page today; the chain builder could either
   match (each link gets its own child page) or invert
   (everything inline on Instruments). Inline keeps the
   instrument card vertically dense; child pages keep each
   editor uncluttered. Decision deferred to Part 1.
2. **Per-instrument vs per-session chain templates.** A common
   pilot pattern may be "use the same chain on every instrument
   in a session" (e.g. a 360-review session with consistent
   visibility everywhere). Worth a per-session chain template
   that new instruments inherit? Deferred.
3. **Self-review row in Link 4.** When the reviewer is also the
   reviewee, the "reviewee can see their own response" audience
   is trivially satisfied — but the operator may want to *hide*
   self-review entries from the reviewee's own dashboard
   (mirrors the existing self-review-active flag). Per-instrument
   override?
4. **Aggregation across reviewers — what does Link 5
   "Summarised" do for non-numeric RTDs?** Easy for `Likert5` /
   `1-to-5int` / `100int`. Less clear for `Short_text` /
   `Long_text` — count + length distribution + (optionally) a
   word-frequency list? Deferred to Part 5 design.
5. **Operator vs sys-admin power over Link 4.** Should an
   operator be allowed to enable reviewee-visible feedback
   without sys-admin oversight, or should sys-admin sign off on
   any non-operator audience? Deferred to a permissions sweep
   alongside Part 4.
6. **Per-question unit of review.** Link 3 currently flips the
   whole instrument between Individual and Grouped. Some pilot
   patterns may want a *mixed* instrument — some questions
   asked once per group, others once per reviewee. The
   group-scoped instrument spec deferred this as out of scope;
   it remains out of scope here. Lift trigger: pilot demand.

---

## Related specs

- [`spec/rule_based_assignment.md`](../spec/rule_based_assignment.md) — Link 2 is this spec, generalised.
- [`spec/instruments.md`](../spec/instruments.md) — the per-instrument card the chain builder lives inside.
- [`spec/group_scoped_instruments.md`](../spec/group_scoped_instruments.md) — group-scoped behaviour the chain must respect.
- [`spec/reconciling_regeneration.md`](../spec/reconciling_regeneration.md) — pair-preservation under chain edits.
- [`spec/validate_page.md`](../spec/validate_page.md) — where chain-builder validation issues surface.
- [`spec/csv_contracts.md`](../spec/csv_contracts.md) — Settings round-trip implications.
- [`spec/settings_inventory.md`](../spec/settings_inventory.md) — friendly labels the editors consume.
- [`spec/audience_and_identity_model.md`](../spec/audience_and_identity_model.md) — the audience model Link 3 + 4 are operationalising.
- [`spec/rrw_functional_spec.md`](../spec/rrw_functional_spec.md) — once this work ships, the functional spec §5 (Core concepts) and §10 (Reviewer experience) acquire new responsibilities; until then, the functional contract reads as today (operators only).
