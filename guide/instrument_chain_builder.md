# Instrument chain builder

> **Stub created 2026-05-22.** Sketch-level scope only. Detailed
> PR breakdowns get drafted when this work is picked up.

A forward-looking UI + data design for a **unified
"instrument chain" builder** that exposes the six key decisions
about an instrument — who reviews, who the reviewer's reviewee
pool is, the unit of review (individual vs group), who can see
the responses, what they can see, and when they can see them —
as one card per link in a chain. Replaces today's "Identity +
Assignment Rule" half-card pair on the per-instrument card with
a six-link layout.

This is a generalisation of the existing per-instrument
[`spec/rule_based_assignment.md`](../spec/rule_based_assignment.md)
contract: the rule engine currently solves only Link 2 (the
reviewee pool), and the group-scoped instrument flag from
[`spec/group_scoped_instruments.md`](../spec/group_scoped_instruments.md)
solves only Link 3 (the unit of review). Links 1, 4, 5, and 6
are net-new conceptual slots; each layers a different policy on
top of an instrument.

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
   reviewees themselves, tagged observers) can read responses.
5. **What can they see?** Whether the responses are surfaced as
   raw values, summarised aggregates, or anonymised cells.
6. **When can the eligible viewers see the responses?** Whether
   reads are open while review is ongoing, or only after the
   operator explicitly releases them.

Today the operator answers these six questions in different
places (some on the Setup pages, some on Instruments, some
nowhere — Links 4, 5, and 6 do not exist in the system yet, and
Link 3 lives only as a binary group-scoped flag + an in-table
boundary-tag selector). The chain builder collects them into
one continuous editor.

---

## Why a chain

Each link in the chain depends on the link before it: scoping
the reviewee pool only makes sense once reviewers are scoped;
the unit of review (individual vs group) only makes sense once
the pool is known; visibility only makes sense once the
response set exists; the read-shape (raw / summary /
anonymised) only makes sense once the visibility audience
exists; release timing only makes sense once there is a
visibility audience with a read shape to gate.

Rendering the six as a left-to-right chain (whether as six
sub-cards, three, or two — see [§UI shape](#ui-shape) on the
links-vs-cards distinction) makes the dependency explicit. It
also gives the operator a single instrument-level surface to
inspect the *policy* an instrument is enforcing — today, Link 1
lives in the engine but is not surfaced in the Rule Builder UI,
Link 2 lives on the per-instrument card, Link 3 lives as a
binary group-scoped flag plus boundary-tag checkboxes inside
the Display Fields table, Link 4 lives only in operators'
heads, and Links 5 and 6 have nowhere to live at all.

The chain is **per instrument**, not per session. Two instruments
in the same session can carry different chains (e.g. a peer-
review instrument with reviewee visibility + anonymised reads,
alongside a self-assessment instrument with operator-only
visibility and raw reads).

---

## The six links

### Link 1 — Reviewer scope

**Question.** Which reviewers on the session's roster fill out
this instrument?

**Today.** Conceptually present in the engine, missing from the
UI. The existing rule predicate vocabulary already speaks both
sides — `reviewer.tag1 / tag2 / tag3` and `reviewer.email` are
first-class reference fields, equal in standing to their
`reviewee.*` counterparts (see
[`spec/rule_based_assignment.md`](../spec/rule_based_assignment.md) §4.1:
"Filter and Match rules are defined as predicates over a
candidate pair `(r, e)`. The vocabulary uses two address
spaces: `reviewer.*` and `reviewee.*`"). Predicates such as
`reviewer.tag2 in ["Senior", "Lead"]` are already valid rule
syntax and run correctly today.

What's missing is the **UI affordance**: the Rule Builder's
field-selector deliberately *omits the reviewer tags* from the
field picker, anchoring every predicate on the reviewee or
pair-context side (`spec/rule_based_assignment.md` §7.2
"Field-selector ordering"). Reviewer-side fields are reachable
only as *operands* via the cross-side `same_as` /
`different_from` operators. So the operator can express
"reviewer and reviewee share tag1" but cannot author "reviewer
tag2 is Lead" in the current UI without hand-writing JSON.

The chain builder lifts that omission by giving Link 1 its own
sub-card whose predicate-field picker is **scoped to
reviewer-side fields only** (mirror image of today's Rule
Builder, which is reviewee-anchored). The engine layer needs no
change — only a UI seam that authors `reviewer.*`-anchored
predicates and stores them.

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

**Relationship to today's RuleSet.** Link 1 and Link 2 are two
*views* on the same underlying predicate space. An operator who
wanted to express "reviewer tag2 = Lead AND reviewee tag1 same
as reviewer tag1" could in principle write a single RuleSet
carrying both predicates and ignore Link 1 entirely — which is
what the existing engine has always allowed. Link 1 exists
because the UI works better when the two scopes are authored
side by side (and because Link 1's predicate has the natural
property of touching only `reviewer.*` and `pair.*` — never
`reviewee.*` — which the chain builder can enforce on the
sub-card's field picker).

**Storage.** Two equivalent representations are possible:
(a) a separate `reviewer_scope` JSON column on `instruments`
(see [D1](#d1--reviewer-scope-predicate-link-1)), or
(b) folding Link 1's predicate into the same RuleSet that
carries Link 2's predicates as an additional rule with
`kind=FILTER` and a `reviewer.*`-anchored predicate. (a) keeps
the UI seam tidy (the chain builder writes one slot, the Rule
Builder writes the other); (b) keeps the engine seam tidy
(only one rule list ever runs). The chain builder doc adopts
(a) as the working assumption; the trade-off is revisited in
[§Open questions](#open-questions).

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

Strictly speaking, **the existing Rule Builder is already a
Link 1 + Link 2 construct at the engine layer** (see Link 1's
"Today" note above). The chain builder splits the two visually
into separate sub-cards because they read more clearly as
distinct decisions, but the underlying predicate vocabulary is
shared. Sub-cards 1 and 2 may even share a single backing
RuleSet if storage option (b) from Link 1 is adopted.

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

**Question.** Who is allowed to read responses on this
instrument? (The *who* — not yet *when*; release timing is
Link 6.)

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
  happens in Link 5.)
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

### Link 6 — Release timing

**Question.** When does each non-operator audience (Link 4)
actually start seeing the responses?

**Today.** N/A — operators read raw responses through CSV
extracts at any time, and no other audience has a read path.

**Proposed inputs.** A per-audience timing choice:

- **While review is ongoing** — reads are open the moment the
  audience's eligibility resolves; responses appear as they
  are saved (and update live as reviewers edit). Suitable for
  formative-feedback patterns where the reviewee can react
  mid-cycle.
- **When released** — reads stay closed until the operator
  flips an explicit **Release responses** action on the
  instrument. Suitable for summative patterns where reviewers
  must not see each other's work-in-progress and the reviewee
  must not see partial drafts.

Per-audience: an operator might let *operators* read at any
time (always-on, default) while *reviewees* see responses only
once released, and *observers* see them only on a separate
release. Each audience independently picks its timing.

**The operators-only audience is always read-now.** Operators
have always read responses live via CSV extract; Link 6 does
not constrain them. Only the new non-operator audiences carry
a timing choice.

**The Release action.** When an instrument has any audience
configured as "when released", a new affordance lights up on
the operator surface — a per-instrument **Release responses**
button (one per audience that is gated). Pressing it stamps a
per-`(instrument, audience)` release timestamp; the read-path
guard consults the stamp before serving any response to that
audience.

**Default proposal.** Reviewees default to "when released" so
the operator is the one who decides timing; Observers default
to "when released" for the same reason. Operators are
implicitly "while review is ongoing" (today's contract).

**Re-closing.** Once released, a release can be revoked
("Un-release") by the operator with confirmation; the
audience loses read access again until re-released. The
release-stamp pattern is reversible, idempotent on multiple
releases, and audit-logged on every flip.

**Composition with session lifecycle.** Release timing layers
*on top of* the session's `accepting_responses` window — it
does not interact with it. A "while review is ongoing"
audience reads from the moment the session is `ready`; a
"when released" audience reads from the moment the operator
flips Release, regardless of whether the session is still
`ready` or has moved past the deadline. (The natural pattern
is to release after the deadline, but the chain does not
enforce that ordering.)

**Audit footprint.** New emitter
`instrument.release_timing_updated` for the config diff. New
emitters `instrument.responses_released` and
`instrument.responses_unreleased` (per audience) for every
flip of the release stamp.

---

## UI shape

One **full-width card** per instrument carrying the chain
builder, replacing the current "Identity + Assignment Rule"
two-half-card row at the top of the per-instrument card.

### Links are not cards

The six links are **conceptual** — six distinct policy
decisions an operator makes about an instrument. **The mapping
from links to sub-cards is a separate UI choice**, and the
natural mapping is not always one-to-one.

Some links pair so tightly with their neighbours that one
sub-card may host two links:

- **Link 1 + Link 2** share a predicate vocabulary (both
  speak `reviewer.*`, `reviewee.*`, and `pair.*`) and have
  always shared one engine. A combined "Assignment rule"
  sub-card with two sections — *Who reviews* and *Who they
  review* — is a reasonable layout, particularly given that
  the existing Rule Builder already takes this form
  implicitly (see Link 1's "Today" note).
- **Link 4 + Link 5** are both per-audience *what-they-see*
  policies — who reads + what shape they read in. A combined
  "Per-audience read policy" sub-card listing each audience
  with its shape inline is reasonable.
- **Link 4 + Link 6** are both per-audience policies that
  attach to the same audience row — who reads + when they
  start reading. A combined "Per-audience access" sub-card
  would carry the audience kind, the predicate (for
  observers), and the release timing on one row.
- **Link 5 + Link 6** travel together on the schema side
  (always per-audience) but address different concerns; a
  combined sub-card would group them as "Per-audience
  surface" but the operator's mental model may keep them
  more legible if they read as separate sub-cards.

The strongest pairing is **Link 4 + Link 5 + Link 6 as one
"Per-audience" sub-card with a row per audience** — a single
table where each row carries `audience kind | predicate? |
read shape | release timing`. This collapses the chain from
six sub-cards to three or four, at the cost of slightly
denser per-row information.

The doc's **working assumption** is the six-sub-card layout
(one per link) — explicit and easy to scan. Pilot feedback may
push toward a collapsed layout once operators show which
groupings they treat as one decision. The data model is
unchanged either way; only the sub-card boundary moves.

### Default layout — one sub-card per link

Under the working assumption, the full-width frame holds six
**sixth-width sub-cards** in a single row (a `.bottom-grid`
extended to six equal columns), one per link. Each sub-card
carries:

- A short title — `1. Reviewers`, `2. Reviewee pool`,
  `3. Unit of review`, `4. Visibility`, `5. Read shape`,
  `6. Release timing`.
- A one-line current-state summary in body text, e.g.:
  - `1. Reviewers: All active (no filter)`
  - `2. Reviewee pool: Same-team peers (RuleSet "Intra-group peer")`
  - `3. Unit of review: Individual`
  - `4. Visibility: Operators + reviewees`
  - `5. Read shape: Reviewees see anonymised text`
  - `6. Release timing: Reviewees on release (not yet released)`
- A small **Edit** button bottom-right of each sub-card.

Clicking **Edit** on a sub-card opens the link's full editor —
either inline below the chain row (preferred for visual
continuity) or as a child page in the same chrome
(`/operator/sessions/{id}/instruments/{iid}/chain/{link}`, where
`{link} ∈ {reviewers, reviewee-pool, unit-of-review, visibility, read-shape, release-timing}`).
The child-page approach mirrors the existing Rule Builder
pattern; the inline approach is gentler on context but requires
more careful state management.

Sub-cards render in the same per-instrument tint as their
parent card. The Identity row (instrument number + name + short
label + status pills) moves to a thin header row above the
sub-cards inside the same full-width card frame.

### Wireframe

```
┌─ Instrument #2 — "Peer skill assessment"  [accepting]  [showing] ────────┐
│                                                                          │
│  ┌── 1. ─┐ ┌── 2. ─┐ ┌── 3. ─┐ ┌── 4. ─┐ ┌── 5. ─┐ ┌── 6. ─┐          │
│  │Review-│ │Review-│ │ Unit  │ │Visib- │ │Read   │ │Release│          │
│  │ers    │ │ee pool│ │ of    │ │ility  │ │shape  │ │timing │          │
│  │       │ │       │ │review │ │       │ │       │ │       │          │
│  │All    │ │Same-  │ │Indiv- │ │Operat-│ │Review-│ │Review-│          │
│  │active │ │team   │ │idual  │ │ors +  │ │ees:   │ │ees: on│          │
│  │       │ │peers  │ │       │ │review-│ │anonym-│ │release│          │
│  │       │ │       │ │       │ │ees    │ │ised   │ │(not   │          │
│  │       │ │       │ │       │ │       │ │text   │ │yet)   │          │
│  │[Edit▸]│ │[Edit▸]│ │[Edit▸]│ │[Edit▸]│ │[Edit▸]│ │[Edit▸]│          │
│  └───────┘ └───────┘ └───────┘ └───────┘ └───────┘ └───────┘          │
│                                                                          │
│  ↓ (Display Fields, Response Fields, etc. continue below)                │
└──────────────────────────────────────────────────────────────────────────┘
```

The chain row is the *first* sub-card of the per-instrument
card, above Display Fields and Response Fields. The instrument's
Identity row collapses into the chain-card header.

### State machine

The six sub-cards share the per-instrument card's existing
**mutually-exclusive edit lock** (only one instrument can be in
edit mode at a time, and within an instrument only one of
Display Fields / Response Fields / Chain links can be open for
editing). Save / Cancel commit to the chain link being edited
without rebuilding the rest of the instrument.

When the session is `ready` (Activated), the chain row splits
along the "assignment-shape vs. read-policy" axis:

- **Links 1, 2, 3** (Reviewer scope, Reviewee pool, Unit of
  review) edit the assignment matrix or its collapse shape on
  the reviewer surface; their Edit buttons render disabled with
  the standard "Revert to draft to edit" tooltip. Editing them
  invalidates `validated → draft` per the existing
  `invalidate_if_validated` discipline.
- **Links 4, 5, 6** (Visibility, Read shape, Release timing)
  edit read-time policies only; their Edit buttons **stay live
  in `ready`**. Edits do not invalidate the session. This is
  the natural pattern — an operator may need to add an
  observer audience or flip a release stamp mid-cycle without
  pausing the reviewer surface.

The Release responses / Un-release flips on Link 6 are runtime
operations on an activated session, not setup-time edits, and
have their own per-instrument-per-audience confirm flow
separate from the chain editor.

---

## Data model deltas

Tracking the six-link chain requires five schema additions —
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
  `{audience_kind, predicate?}`. `audience_kind ∈
  {operator, reviewee, observer}`. `predicate` is required for
  `observer`.

Plus a downstream read-path guard that consults this column on
every response-row read by a non-operator.

### D5 — Read shape (Link 5)

A new JSON column on `instruments`:
- `read_shapes` — JSON object keyed by audience kind, valued by
  `{shape: raw|summarised|anonymised, k_anonymity_floor: int}`.

### D6 — Release timing (Link 6)

Two new structures:
- `release_timing` — JSON object on `instruments` keyed by
  audience kind, valued by `{mode: while_ongoing | on_release}`.
  Operators are implicitly `while_ongoing` and need no row.
- `instrument_releases` — new table keyed by
  `(instrument_id, audience_kind)`, carrying `released_at` and
  `released_by_user_id`. One row per release flip; rows persist
  through un-release (the read-path guard treats `released_at`
  IS NULL as "not currently released").

Alternative shape: merge D4 + D5 + D6 into one
`audience_policy` JSON column carrying
`{audience_kind, predicate?, shape, k_anonymity_floor, timing}`
per row, with the release timestamps still living on the
separate `instrument_releases` table because they are write-
heavy state, not config. The merged shape is preferable for the
three config policies because they always travel together.

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
| **0 — Schema pre-positioning** | Inert columns + tables on `instruments` (D1, D3, D4, D5, D6). No behaviour change. | nothing |
| **1 — UI shell** | Replace the per-instrument card's Identity + Rule row with the six-sub-card chain layout. Sub-cards 1 / 4 / 5 / 6 are placeholder cards showing "Default" everywhere; sub-card 2 wraps the existing Rule Builder affordance unchanged; sub-card 3 reflects the current `group_kind` flag read-only. | Part 0 |
| **2 — Link 1 (reviewer scope)** | Light up the Reviewers sub-card editor + service-layer predicate evaluation in the assignment generator. | Parts 0 + 1 |
| **3 — Link 3 (unit of review)** | Promote the existing `group_kind` flag + Display-Fields-table boundary-tag checkboxes into the Unit-of-review sub-card editor. Add post-creation mode-switching backed by the reconciler. Display Fields table loses its boundary-tag column. | Parts 0 + 1 |
| **4 — Link 4 (visibility, operator + reviewee audiences)** | Light up the Visibility sub-card editor. Per-reviewee read path on a new `/reviewer/sessions/{id}/{position}/about-me` surface (the reviewee dashboard the audience model has long anticipated). | Parts 0 + 1 |
| **5 — Link 5 (read shape, summarised + anonymised for reviewee audience)** | Light up the Read shape sub-card editor. Aggregator service computing summaries; anonymisation transformer; k-anonymity floor enforcement. | Part 4 |
| **6 — Link 6 (release timing, operator + reviewee audiences)** | Light up the Release-timing sub-card editor + per-instrument-per-audience Release / Un-release affordance on the operator surface. Read-path guard consults `instrument_releases` before serving any "on_release" audience. | Part 4 |
| **7 — Link 4 (observer audiences)** | Reviewee-tag-defined and pair-context-defined observer audiences. Observer dashboard surface. | Part 4 |
| **8 — Link 5 (read shape for observer audiences)** | Per-observer-audience read shape configuration. | Parts 5 + 7 |
| **9 — Link 6 (release timing for observer audiences)** | Per-observer-audience release timing + Release affordance for each observer audience. | Parts 6 + 7 |

Parts 0 + 1 must land in that order. After Part 1, parts 2 / 3
/ 4 are independent and can interleave. Parts 5 / 6 / 7 depend
on Part 4. Parts 8 / 9 depend on their respective earlier
parts as noted.

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
- **Link 6** — release timing references an audience that
  Link 4 did not enable is an error. Timing alone is a no-op
  without a paired visibility audience.

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
must learn to round-trip the six-link chain. Each link's
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
2. **Link 1 storage shape.** Two equivalent representations
   exist for the Link 1 predicate (see Link 1 "Storage"):
   (a) a dedicated `reviewer_scope` JSON column on
   `instruments`, separate from the Link 2 RuleSet; or
   (b) one extra `FILTER` rule with a `reviewer.*`-anchored
   predicate inside the Link 2 RuleSet. The doc currently
   assumes (a). (b) is closer to today's engine layer and
   removes one schema row; (a) keeps the UI seam tidier (one
   sub-card writes one slot). Worth re-evaluating once the
   chain-builder UI lands. Decision deferred to Part 2.
3. **Sub-card boundary.** The "links are not cards" note above
   sketches several reasonable collapses (Link 1 + Link 2 into
   one Assignment-rule sub-card; Link 4 + Link 5 + Link 6 into
   one Per-audience sub-card). The working assumption is one
   sub-card per link, but the right collapse may only become
   clear once operators exercise the builder. Decision
   deferred to Part 1's UI shell or to a later refactor.
4. **Per-instrument vs per-session chain templates.** A common
   pilot pattern may be "use the same chain on every instrument
   in a session" (e.g. a 360-review session with consistent
   visibility everywhere). Worth a per-session chain template
   that new instruments inherit? Deferred.
5. **Self-review row in Link 4.** When the reviewer is also the
   reviewee, the "reviewee can see their own response" audience
   is trivially satisfied — but the operator may want to *hide*
   self-review entries from the reviewee's own dashboard
   (mirrors the existing self-review-active flag). Per-instrument
   override?
6. **Aggregation across reviewers — what does Link 5
   "Summarised" do for non-numeric RTDs?** Easy for `Likert5` /
   `1-to-5int` / `100int`. Less clear for `Short_text` /
   `Long_text` — count + length distribution + (optionally) a
   word-frequency list? Deferred to Part 5 design.
7. **Operator vs sys-admin power over Link 4.** Should an
   operator be allowed to enable reviewee-visible feedback
   without sys-admin oversight, or should sys-admin sign off on
   any non-operator audience? Deferred to a permissions sweep
   alongside Part 4.
8. **Per-question unit of review.** Link 3 currently flips the
   whole instrument between Individual and Grouped. Some pilot
   patterns may want a *mixed* instrument — some questions
   asked once per group, others once per reviewee. The
   group-scoped instrument spec deferred this as out of scope;
   it remains out of scope here. Lift trigger: pilot demand.
9. **Scheduled release on Link 6.** The current proposal makes
   release a manual operator action — the operator decides
   when. A natural extension is a per-`(instrument, audience)`
   `release_at` timestamp so the release fires on a schedule
   (mirrors the auto-send-invitations / auto-send-reminders
   pattern from 18G). Deferred until manual release has been
   exercised in a pilot. Lift trigger: operator demand.
10. **Per-reviewer release granularity.** A release is currently
    per-`(instrument, audience)` — every reviewee in the
    audience sees the same release flip. A finer-grained
    variant would release per-reviewee (e.g. release one
    reviewee's responses today, another's tomorrow during a
    rolling feedback distribution). Operationally noisier;
    deferred. Lift trigger: pilot demand.

---

## Related specs

- [`spec/rule_based_assignment.md`](../spec/rule_based_assignment.md) — the existing Rule Builder is, in engine terms, already a Link 1 + Link 2 construct (predicates speak both `reviewer.*` and `reviewee.*` address spaces); the chain builder lifts Link 1 out as a first-class UI affordance.
- [`spec/instruments.md`](../spec/instruments.md) — the per-instrument card the chain builder lives inside.
- [`spec/group_scoped_instruments.md`](../spec/group_scoped_instruments.md) — group-scoped behaviour the chain must respect.
- [`spec/reconciling_regeneration.md`](../spec/reconciling_regeneration.md) — pair-preservation under chain edits.
- [`spec/validate_page.md`](../spec/validate_page.md) — where chain-builder validation issues surface.
- [`spec/csv_contracts.md`](../spec/csv_contracts.md) — Settings round-trip implications.
- [`spec/settings_inventory.md`](../spec/settings_inventory.md) — friendly labels the editors consume.
- [`spec/audience_and_identity_model.md`](../spec/audience_and_identity_model.md) — the audience model Links 4, 5, and 6 are operationalising.
- [`spec/lifecycle.md`](../spec/lifecycle.md) — Link 6's release-stamp lifecycle layers on top of the session lifecycle; per-instrument release flips do not move the session between states.
- [`spec/rrw_functional_spec.md`](../spec/rrw_functional_spec.md) — once this work ships, the functional spec §5 (Core concepts) and §10 (Reviewer experience) acquire new responsibilities; until then, the functional contract reads as today (operators only).
