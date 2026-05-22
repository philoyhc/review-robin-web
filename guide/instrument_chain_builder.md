# Instrument chain builder

> **Stub created 2026-05-22.** Sketch-level scope only. Detailed
> PR breakdowns get drafted when this work is picked up.

A forward-looking UI + data design for a **unified
"instrument chain" builder** that exposes the four key decisions
about an instrument — who reviews, who they review, who can see
the responses, and what they can see — as one card per link in
a chain. Replaces today's "Identity + Assignment Rule" half-card
pair on the per-instrument card with a four-link layout.

This is a generalisation of the existing per-instrument
[`spec/rule_based_assignment.md`](../spec/rule_based_assignment.md)
contract: the rule engine currently solves only Link 2 (who does
the reviewer review?). Links 1, 3, and 4 are net-new conceptual
slots; each layers a different policy on top of an instrument.

---

## Goal

For each instrument in a session, let the operator pin a
complete **review chain** in one screen — answering, in turn:

1. **Who are the reviewers?** Which subset of the session's
   reviewer roster fills out this instrument.
2. **Who is each reviewer reviewing?** Per-reviewer reviewee
   universe — the existing rule-engine job.
3. **Who can see the responses?** Which cohorts (operators only,
   reviewees themselves, tagged observers) can read responses
   once they are saved.
4. **What can they see?** Whether the responses are surfaced as
   raw values, summarised aggregates, or anonymised cells.

Today the operator answers these four questions in different
places (some on the Setup pages, some on Instruments, some
nowhere — Links 3 and 4 do not exist in the system yet). The
chain builder collects them into one continuous editor.

---

## Why one card per link

Each link in the chain depends on the link before it: scoping
reviewees only makes sense once reviewers are scoped; visibility
only makes sense once the response set exists; the read-shape
(raw / summary / anonymised) only makes sense once the
visibility audience exists.

Rendering the four as a left-to-right chain of equal-width cards
makes the dependency explicit. It also gives the operator a
single instrument-level surface to inspect the *policy* an
instrument is enforcing — today, Link 2 lives on the per-
instrument card, Link 3 lives only in operator's heads, and
Link 4 has nowhere to live at all.

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

### Link 2 — Reviewee scope per reviewer

**Question.** For each reviewer in Link 1's set, who are they
reviewing on this instrument?

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

### Link 3 — Visibility scope

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

### Link 4 — Read shape

**Question.** When a non-operator audience (Link 3) reads a
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

Inside the full-width frame, four **quarter-width sub-cards**
sit in a single row (a `.bottom-grid` extended to four equal
columns), one per link. Each sub-card carries:

- A short title — `1. Reviewers`, `2. Reviewees`,
  `3. Visibility`, `4. Read shape`.
- A one-line current-state summary in body text, e.g.:
  - `1. Reviewers: All active (no filter)`
  - `2. Reviewees: Same-team peers (RuleSet "Intra-group peer")`
  - `3. Visibility: Operators + reviewees`
  - `4. Read shape: Reviewees see anonymised text`
- A small **Edit** button bottom-right of each sub-card.

Clicking **Edit** on a sub-card opens the link's full editor —
either inline below the chain row (preferred for visual
continuity) or as a child page in the same chrome
(`/operator/sessions/{id}/instruments/{iid}/chain/{link}`, where
`{link} ∈ {reviewers, reviewees, visibility, read-shape}`). The
child-page approach mirrors the existing Rule Builder pattern;
the inline approach is gentler on context but requires more
careful state management.

Sub-cards render in the same per-instrument tint as their
parent card. The Identity row (instrument number + name + short
label + status pills) moves to a thin header row above the four
sub-cards inside the same full-width card frame.

### Wireframe

```
┌─ Instrument #2 — "Peer skill assessment"  [accepting]  [showing] ─┐
│                                                                   │
│  ┌──── 1. ────┐ ┌──── 2. ────┐ ┌──── 3. ────┐ ┌──── 4. ────┐    │
│  │  Reviewers │ │  Reviewees │ │  Visibility│ │ Read shape │    │
│  │            │ │            │ │            │ │            │    │
│  │  All active│ │  Same-team │ │  Operators │ │  Reviewees:│    │
│  │            │ │  peers     │ │  + reviewee│ │  anonymised│    │
│  │            │ │            │ │  themselves│ │  text      │    │
│  │            │ │            │ │            │ │            │    │
│  │  [Edit ▸]  │ │  [Edit ▸]  │ │  [Edit ▸]  │ │  [Edit ▸]  │    │
│  └────────────┘ └────────────┘ └────────────┘ └────────────┘    │
│                                                                   │
│  ↓ (Display Fields, Response Fields, etc. continue below)         │
└───────────────────────────────────────────────────────────────────┘
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
to edit" tooltip. Visibility (Link 3) and Read shape (Link 4)
edits do **not** invalidate the session back to `draft` — they
affect downstream reads, not the assignment matrix. Reviewer
scope (Link 1) and Reviewee scope (Link 2) edits **do**
invalidate (they change which pairs the assignment matrix
materialises). This split honours the existing
`invalidate_if_validated` discipline.

---

## Data model deltas

Tracking the four-link chain requires four schema additions —
each separable and independently shippable.

### D1 — Reviewer scope predicate (Link 1)

A new JSON column on `instruments`:
- `reviewer_scope` — nullable JSON. When non-null, a predicate
  in the same shape as the existing rule predicates. When null,
  defaults to "all active reviewers".

### D2 — Reviewee scope (Link 2)

No schema change. The existing `instruments.rule_set_id`
column + `session_rule_sets` table carry this.

### D3 — Visibility scope (Link 3)

A new structured column on `instruments`:
- `visibility_audiences` — JSON array of objects, each carrying
  `{audience_kind, predicate?, unlock_at}`. `audience_kind ∈
  {operator, reviewee, observer}`. `predicate` is required for
  `observer`. `unlock_at ∈ {save, submit, session_close,
  deadline}`.

Plus a downstream read-path guard that consults this column on
every response-row read by a non-operator.

### D4 — Read shape (Link 4)

A new JSON column on `instruments`:
- `read_shapes` — JSON object keyed by audience kind, valued by
  `{shape: raw|summarised|anonymised, k_anonymity_floor: int}`.

Or alternatively, merge D3 and D4 into one column carrying
`audience + shape + unlock_at` per row. The unified shape is
preferable because the three policies always travel together.

### Migrations

One Alembic revision adding the JSON columns inert (default null).
Followed by a service layer that writes them, then a route layer
that surfaces them, then read-path guards on the non-operator
response surfaces. Each layer ships as its own PR slice.

---

## Sequencing

The chain builder is **not** a single deliverable. It is a
sequence of independently-shippable parts:

| Part | Scope | Depends on |
|---|---|---|
| **0 — Schema pre-positioning** | Inert JSON columns on `instruments` (D1–D4). No behaviour change. | nothing |
| **1 — UI shell** | Replace the per-instrument card's Identity + Rule row with the four-sub-card chain layout. Sub-cards 1 / 3 / 4 are placeholder cards showing "Default" everywhere; sub-card 2 wraps the existing Rule Builder affordance unchanged. | Part 0 |
| **2 — Link 1 (reviewer scope)** | Light up the Reviewers sub-card editor + service-layer predicate evaluation in the assignment generator. | Parts 0 + 1 |
| **3 — Link 3 (visibility, operator + reviewee audiences)** | Light up the Visibility sub-card editor. Per-reviewee read path on a new `/reviewer/sessions/{id}/{position}/about-me` surface (the reviewee dashboard the audience model has long anticipated). | Parts 0 + 1 |
| **4 — Link 4 (read shape, summarised + anonymised for reviewee audience)** | Light up the Read shape sub-card editor. Aggregator service computing summaries; anonymisation transformer; k-anonymity floor enforcement. | Part 3 |
| **5 — Link 3 (observer audiences)** | Reviewee-tag-defined and pair-context-defined observer audiences. Observer dashboard surface. | Part 3 |
| **6 — Link 4 (read shape for observer audiences)** | Per-observer-audience read shape configuration. | Parts 4 + 5 |

Parts 0 + 1 must land in that order. After Part 1, parts 2 / 3
are independent and can interleave. Parts 4 / 5 / 6 depend on
their respective earlier parts as noted.

---

## Cross-cutting concerns

### Validation surface

Each link in the chain contributes new validation rules:

- **Link 1** — predicate references unknown tag slots; predicate
  excludes every active reviewer (empty reviewer set is an
  error, not a warning).
- **Link 2** — existing rule-engine validation, unchanged.
- **Link 3** — observer-audience predicate references unknown
  tag slots; visibility-audience set is empty (every instrument
  must have at least Operators).
- **Link 4** — k-anonymity floor is achievable given the
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

The chain layout applies to group-scoped instruments as well.
Link 2's reviewee scope already cooperates with the group-
boundary tag selectors on the Display Fields table (see
[`spec/group_scoped_instruments.md`](../spec/group_scoped_instruments.md)).
Link 3's visibility model for group-scoped instruments needs an
explicit rule: a reviewee in a group sees the group's response,
not the per-member fan-out — i.e. the existing read-time
collapse continues to apply.

### Reconciling regeneration

Editing Link 1 (reviewer scope) or Link 2 (reviewee scope)
changes the pair set the assignment matrix materialises. The
existing reconciler ([`spec/reconciling_regeneration.md`](../spec/reconciling_regeneration.md))
handles this without operator action — pairs the new chain
drops cascade-delete their responses; pairs the new chain
keeps preserve theirs; the super-button dry-runs the impact
and prompts when responses would be lost.

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
3. **Self-review row in Link 3.** When the reviewer is also the
   reviewee, the "reviewee can see their own response" audience
   is trivially satisfied — but the operator may want to *hide*
   self-review entries from the reviewee's own dashboard
   (mirrors the existing self-review-active flag). Per-instrument
   override?
4. **Aggregation across reviewers — what does Link 4
   "Summarised" do for non-numeric RTDs?** Easy for `Likert5` /
   `1-to-5int` / `100int`. Less clear for `Short_text` /
   `Long_text` — count + length distribution + (optionally) a
   word-frequency list? Deferred to Part 4 design.
5. **Operator vs sys-admin power over Link 3.** Should an
   operator be allowed to enable reviewee-visible feedback
   without sys-admin oversight, or should sys-admin sign off on
   any non-operator audience? Deferred to a permissions sweep
   alongside Part 3.

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
