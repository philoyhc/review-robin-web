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
inspect the *policy* an instrument is enforcing — today,
Links 1 + 2 live together inside the existing Rule Builder
card (already a full Link 1 + Link 2 surface; see Link 1's
"Today" section), Link 3 lives as a binary group-scoped flag
plus boundary-tag checkboxes inside the Display Fields table,
Link 4 lives only in operators' heads, and Links 5 and 6 have
nowhere to live at all.

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

**Today.** Already fully expressible in the existing Rule
Builder — Link 1 is not a new capability, just a clearer way
to name a job the operator can do today.

Three engine + UI properties together make this so:

1. **The predicate vocabulary speaks both sides.** The engine's
   rule predicates reference fields in two address spaces,
   `reviewer.*` and `reviewee.*` (plus `pair_context.*`). A
   predicate like `reviewer.tag2 equals "Lead"` is valid rule
   syntax and runs correctly. See
   [`spec/rule_based_assignment.md`](../spec/rule_based_assignment.md) §4.1.

2. **The UI's field-picker (LHS) already includes reviewer
   tags.** Inspecting the live picker
   (`app/web/views/_rule_builder.py:_FIELD_PICKER_VALUES`)
   confirms `reviewer.tag1 / tag2 / tag3` are listed alongside
   the reviewee and pair-context tags — the operator can pick
   any of the nine as the LHS of a predicate. The operand-side
   (RHS) picker accepts literals or any of the nine same
   fields. (`spec/rule_based_assignment.md` §7.2 carries a
   stale claim that the LHS picker "omits the reviewer tags";
   the code does not implement that constraint and the spec
   should be flagged for cleanup.)

3. **RuleSets allow conjunction.** Multiple MATCH / FILTER
   rules combine with `ALL_OF` / `ANY_OF` combinators. So an
   operator can chain `MATCH(reviewer.tag2 equals "Lead")` —
   a pure Link-1 reviewer filter — with `MATCH(reviewee.tag1
   same_as reviewer.tag1)` — a Link-2 pair-level constraint —
   inside one RuleSet.

So the existing Rule Builder is **already a Link 1 + Link 2
construct, in both engine and UI**. An operator wanting "only
managers (Link 1) review only their own direct reports
(Link 2)" can author both predicates as rules in one RuleSet
today, with no chain-builder UI involved.

**What the chain builder adds.** Not new expressive power —
just a clearer mental model. Splitting the predicate set into
"who reviews" and "who do they review" surfaces the *intent*
the existing Rule Builder asks the operator to encode in one
flat rule list. Operators authoring sessions often think of
the two scopes as separate decisions; the chain builder
matches that mental model. (Whether the UI split is worth the
extra surface area is captured as an open question — see
[§Open questions](#open-questions) on sub-card boundaries.)

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

**Storage.** Two equivalent representations are possible:
(a) a separate `reviewer_scope` JSON column on `instruments`
(see [D1](#d1--reviewer-scope-predicate-link-1)), or
(b) folding Link 1's predicate into the same RuleSet that
carries Link 2's predicates as an additional rule with
`kind=FILTER` and a `reviewer.*`-anchored predicate. Given that
the engine + UI already accept exactly this conjunction,
**(b) is now the natural default** — no new column, no new
rule-evaluation seam, no new persistence path. (a) was the
earlier doc's working assumption back when the spec made Link 1
look like a net-new capability; the codebase check has flipped
the choice. The trade-off is revisited in
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

As noted under Link 1, **the existing Rule Builder is already a
Link 1 + Link 2 construct in both engine and UI**: the
LHS field picker exposes reviewer tags, the operand picker
accepts both literals and any field, and rules conjoin via
`ALL_OF` / `ANY_OF` combinators. An operator who wants "only
managers review only their own direct reports" can author both
predicates as rules in one RuleSet today. The chain builder
splits the two scopes visually into separate sub-cards (or
keeps them combined — see [§UI shape](#ui-shape) on the
links-vs-cards distinction), but the underlying predicate
vocabulary is shared, and a single backing RuleSet is the
natural place for both to live.

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
sub-card may host two or more links:

- **Link 1 + Link 2 — the strongest pairing.** These share a
  predicate vocabulary (both speak `reviewer.*`, `reviewee.*`,
  and `pair_context.*`), already share one engine, and already
  share one UI: the existing Rule Builder *is* a Link 1 + Link 2
  surface (see Link 1's "Today" section). A combined "Assignment
  rule" sub-card embedding the existing Rule Builder
  ~unchanged — perhaps just with two visual sections labelled
  *Who reviews* and *Who they review* to surface the
  decomposition — is the lowest-friction layout and the doc's
  recommended choice for sub-cards 1 + 2.
- **Link 4 + Link 5 + Link 6 — the second-strongest pairing.**
  All three are per-audience policies that attach to the same
  audience row: who reads + what shape they see + when they
  see it. A combined "Per-audience access" sub-card with one
  row per audience — `audience kind | predicate? | read shape |
  release timing` — collapses three sub-cards into one, at the
  cost of slightly denser per-row information.
- **Link 4 + Link 5** alone or **Link 4 + Link 6** alone are
  smaller intermediate collapses if the triple feels too
  dense.

Taking both strongest pairings, the chain naturally reads as
**three sub-cards**, not six:

1. **Assignment rule** (Links 1 + 2) — the existing Rule
   Builder, possibly re-headed.
2. **Unit of review** (Link 3) — unit choice + boundary tags.
3. **Per-audience access** (Links 4 + 5 + 6) — one row per
   audience carrying audience kind, predicate, read shape,
   release timing.

This is the doc's **working assumption** going forward — three
sub-cards, not six. The six-link decomposition stays in the
text as the conceptual model the operator is encoding; the UI
collapses two of the three groups into single editors that
match the way operators already think about them.

Pilot feedback may push toward a different boundary (split the
Per-audience triple, fold Link 3 into Assignment rule, etc.).
The data model is unchanged either way; only the sub-card
boundary moves.

### Default layout — three sub-cards

Under the working assumption (two strongest pairings collapsed),
the full-width frame holds **three sub-cards** in a single row
(a `.bottom-grid` extended to three equal columns). Each
sub-card carries a short title, a one-line current-state
summary, and an **Edit** button:

- **Assignment rule** (Links 1 + 2) — embeds the existing
  Rule Builder card ~unchanged, possibly with two visual
  sections labelled *Who reviews* and *Who they review* to
  surface the Link 1 / Link 2 decomposition. Summary:
  `Assignment rule: Same-team peers, leads only (2 rules)`.
- **Unit of review** (Link 3) — unit choice (Individual /
  Grouped) + boundary tag selection. Summary:
  `Unit of review: Individual` (or
  `Unit of review: Grouped by reviewee.tag1 + tag3`).
- **Per-audience access** (Links 4 + 5 + 6) — one row per
  enabled audience carrying audience kind, predicate (for
  observers), read shape, and release timing. Summary:
  `Per-audience access: Operators (raw, always), Reviewees
  (anonymised text, on release — not yet released)`.

Clicking **Edit** on a sub-card opens the link's full editor —
either inline below the chain row (preferred for visual
continuity) or as a child page in the same chrome
(`/operator/sessions/{id}/instruments/{iid}/chain/{section}`,
where `{section} ∈ {assignment-rule, unit-of-review,
per-audience-access}`). The child-page approach mirrors the
existing Rule Builder pattern; the inline approach is gentler
on context but requires more careful state management.

Sub-cards render in the same per-instrument tint as their
parent card. The Identity row (instrument number + name + short
label + status pills) moves to a thin header row above the
sub-cards inside the same full-width card frame.

### Wireframe

```
┌─ Instrument #2 — "Peer skill assessment"  [accepting]  [showing] ─────────┐
│                                                                           │
│  ┌──── Assignment rule ──┐ ┌── Unit of review ──┐ ┌── Per-audience ─────┐ │
│  │ Who reviews:          │ │ Individual         │ │ Operators   raw  ─  │ │
│  │   reviewer.tag2=Lead  │ │                    │ │ Reviewees   anon  ⏳│ │
│  │ Who they review:      │ │                    │ │ (Observers not set) │ │
│  │   reviewee.tag1 same  │ │                    │ │                     │ │
│  │   as reviewer.tag1    │ │                    │ │                     │ │
│  │                       │ │                    │ │                     │ │
│  │            [Edit ▸]   │ │       [Edit ▸]     │ │         [Edit ▸]    │ │
│  └───────────────────────┘ └────────────────────┘ └─────────────────────┘ │
│                                                                           │
│  ↓ (Display Fields, Response Fields, etc. continue below)                 │
└───────────────────────────────────────────────────────────────────────────┘
```

The chain row is the *first* sub-card of the per-instrument
card, above Display Fields and Response Fields.

### Alternative — six sub-cards, one per link

If pilot feedback shows operators prefer the six-link
decomposition surfaced one-per-card, the doc's previous
working assumption (six sixth-width sub-cards in a row, one
per link) remains a valid fallback:

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

The Identity row collapses into the chain-card header.

### State machine

The chain sub-cards share the per-instrument card's existing
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

Tracking the six-link chain requires four schema additions —
each separable and independently shippable. Links 1 and 2
reuse the existing per-instrument RuleSet pin (both predicates
live as rules in the same backing RuleSet); Link 3 reuses
(and refines) the existing group-scoped instrument schema.

### D1 — Reviewer scope predicate (Link 1)

**No schema change** under the doc's current working
assumption. Link 1's predicate lives as an additional `FILTER`
rule with a `reviewer.*`-anchored predicate inside the same
RuleSet that carries Link 2's predicates (storage option (b)
from Link 1's "Today" section). The existing engine already
evaluates this exact shape correctly.

A dedicated `reviewer_scope` JSON column remains an
*alternative* (storage option (a)) — preserved here in case a
future implementation needs a separate persistence slot, e.g.
to cache the reviewer-only subset of rules. The chain builder
doc does not assume this slot exists.

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
| **0 — Schema pre-positioning** | Inert columns + tables on `instruments` (D3, D4, D5, D6 — no D1 under the working assumption). No behaviour change. | nothing |
| **1 — UI shell** | Replace the per-instrument card's Identity + Rule row with the three-sub-card chain layout (Assignment rule / Unit of review / Per-audience access). The Assignment-rule sub-card wraps the existing Rule Builder affordance unchanged. The Unit-of-review sub-card reflects the current `group_kind` flag read-only. The Per-audience sub-card is a placeholder showing "Operators only" by default. | Part 0 |
| **2 — Link 1 surfacing** | Re-head the existing Rule Builder card's two visual sections as *Who reviews* (Link 1) and *Who they review* (Link 2). No engine, no schema, no storage work — purely a label and ordering pass over the Rule Builder template to surface the Link 1 / Link 2 decomposition the operator is already encoding. | Parts 0 + 1 |
| **3 — Link 3 (unit of review)** | Promote the existing `group_kind` flag + Display-Fields-table boundary-tag checkboxes into the Unit-of-review sub-card editor. Add post-creation mode-switching backed by the reconciler. Display Fields table loses its boundary-tag column. | Parts 0 + 1 |
| **4 — Link 4 (visibility, operator + reviewee audiences)** | Light up the visibility column of the Per-audience sub-card. Per-reviewee read path on a new `/reviewer/sessions/{id}/{position}/about-me` surface (the reviewee dashboard the audience model has long anticipated). | Parts 0 + 1 |
| **5 — Link 5 (read shape, summarised + anonymised for reviewee audience)** | Light up the read-shape column of the Per-audience sub-card. Aggregator service computing summaries; anonymisation transformer; k-anonymity floor enforcement. | Part 4 |
| **6 — Link 6 (release timing, operator + reviewee audiences)** | Light up the release-timing column of the Per-audience sub-card + per-instrument-per-audience Release / Un-release affordance on the operator surface. Read-path guard consults `instrument_releases` before serving any "on_release" audience. | Part 4 |
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
   predicate inside the Link 2 RuleSet. **The doc now assumes
   (b)** — the engine and UI already accept this exact
   conjunction, and the recommended sub-card layout (Link 1 +
   Link 2 collapsed into one Assignment-rule sub-card) makes
   the single-RuleSet storage natural. (a) was the earlier
   working assumption back when Link 1 looked like a net-new
   capability; the codebase check has flipped the default. The
   open question now is whether (a) buys anything worth its
   cost — a single inert reviewer_scope column might still be
   worth it as a *cache* of the reviewer-only subset of rules,
   if reviewer-scope evaluation becomes a hot path. Deferred
   until Part 2 implementation forces the choice.
3. **Sub-card boundary.** The "links are not cards" note above
   sketches several collapses. The doc now defaults to
   **three sub-cards**: Assignment rule (Links 1 + 2), Unit of
   review (Link 3), Per-audience access (Links 4 + 5 + 6).
   Pilot feedback may push toward a different boundary (split
   Per-audience, fold Unit of review into Assignment rule,
   etc.). Decision revisited in Part 1's UI shell or in a
   later refactor.
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

- [`spec/rule_based_assignment.md`](../spec/rule_based_assignment.md) — the existing Rule Builder is already a Link 1 + Link 2 construct in both engine and UI (LHS field picker exposes reviewer tags, operand picker accepts all nine field positions, rules conjoin via `ALL_OF` / `ANY_OF`). The chain builder re-presents the same capability with the Link 1 / Link 2 decomposition surfaced. **Stale claim to flag for a future spec sweep:** §7.2 "Field-selector ordering" says the LHS picker "omits the reviewer tags". The code (`app/web/views/_rule_builder.py:_FIELD_PICKER_VALUES`, lines 96-106) lists `reviewer.tag1/2/3` first. The spec describes a design intent that the implementation does not (and arguably should not) enforce.
- [`spec/instruments.md`](../spec/instruments.md) — the per-instrument card the chain builder lives inside.
- [`spec/group_scoped_instruments.md`](../spec/group_scoped_instruments.md) — group-scoped behaviour the chain must respect.
- [`spec/reconciling_regeneration.md`](../spec/reconciling_regeneration.md) — pair-preservation under chain edits.
- [`spec/validate_page.md`](../spec/validate_page.md) — where chain-builder validation issues surface.
- [`spec/csv_contracts.md`](../spec/csv_contracts.md) — Settings round-trip implications.
- [`spec/settings_inventory.md`](../spec/settings_inventory.md) — friendly labels the editors consume.
- [`spec/audience_and_identity_model.md`](../spec/audience_and_identity_model.md) — the audience model Links 4, 5, and 6 are operationalising.
- [`spec/lifecycle.md`](../spec/lifecycle.md) — Link 6's release-stamp lifecycle layers on top of the session lifecycle; per-instrument release flips do not move the session between states.
- [`spec/rrw_functional_spec.md`](../spec/rrw_functional_spec.md) — once this work ships, the functional spec §5 (Core concepts) and §10 (Reviewer experience) acquire new responsibilities; until then, the functional contract reads as today (operators only).
