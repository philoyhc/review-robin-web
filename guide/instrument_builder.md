# Instrument builder

> **Stub created 2026-05-22, centered as the canonical design 2026-05-22.** Sketch-level scope only.
> Detailed PR breakdowns get drafted when this work is picked up.

The per-instrument editor's UI shape and conceptual model.
One full-width card per instrument carrying every decision the
operator makes about that instrument:

- **Who reviews** + **who they review** — one inline rule
  editor at the top, working over the existing engine's
  `reviewer.*` / `reviewee.*` / `pair_context.*` address spaces.
- **Unit of review** — the per-instrument flavour (per-reviewee
  vs grouped) and its boundary tags.
- **The review form itself** — a **live preview** of one
  reviewer-surface row, sitting in the centre of the editor.
  The operator manipulates display + response fields inline on
  the preview row.
- **Who can see the responses** + **what shape** + **when** —
  per-audience access policy at the bottom.

The card is **vertically organised**: three bands stacked top
to bottom, each its own section within the same parent card
frame. The middle band — the live preview — is the operator's
primary working surface; the top and bottom bands bracket it
with the rules that govern who sees what.

A prior alternative ("instrument chain builder", with the
decisions laid out horizontally as a chain of sub-cards) was
sketched and retired 2026-05-22 in favour of this vertical
model.

---

## Goal

For each instrument in a session, the operator authors a
complete review-form contract in one screen, answering six
questions:

1. **Who are the reviewers?** Which subset of the session's
   reviewer roster fills out this instrument.
2. **Who is each reviewer reviewing?** Per-reviewer reviewee
   pool.
3. **What is the unit of review?** Individual reviewees, or
   reviewees grouped by reviewee tags.
4. **Who can see the responses?** Cohorts (operators, reviewees
   themselves, tagged observers).
5. **What can they see?** Raw, summarised, or anonymised reads.
6. **When can they see them?** While review is ongoing, or only
   after the operator releases.

Today the operator answers these in different places — some on
the Setup pages, some on Instruments, some via the Rule Builder
child page, some nowhere at all (Links 4-6 do not exist in the
system yet, and Link 3 lives only as a binary group-scoped flag
+ in-Display-Fields-table boundary-tag checkboxes). The
instrument builder collects them into one continuous editor.

Questions 1 + 2 are answered by **one inline rule editor**, not
two. See [§Rule authoring](#rule-authoring) below — the
engine has always treated them as one predicate-list problem,
and pilot use confirms that pre-built rule libraries do not
remove the operator's need to author rules from scratch.

---

## Why direct authoring, not libraries

Beta use surfaced a design learning that applies to **two
library mechanisms** the original design carried: the
**RuleSet library** behind Links 1 + 2, and the **Response
Type Definition (RTD) library** behind response field types.

Both libraries are doing less work than the original
abstraction assumed, and both retire in the instrument
builder — though the RTD library keeps a small residue
(List-type definitions) where the reuse argument still holds.

### The rule library retires

The combinatorial space is large. Each session carries three
reviewer-tag slots, three reviewee-tag slots, and three
pair-context-tag slots — nine independent dimensions the
operator can pivot on. A seed like "Intra-group peer review"
covers exactly one combination (`reviewer.tag1 same_as
reviewee.tag1`). An operator who wants to pivot on tag3, or
tag2 + tag3, or tag1 + tag2 + tag3, gets nothing from the seed
— they have to write the rules from scratch.

The personal-library model fares similarly. A rule the
operator saved last time covered the previous session's
specific tag layout; the next session's layout is likely
different enough that the saved rule needs editing anyway. And
**session replication** (the lobby's Duplicate action) already
handles the "reuse this setup" case at the session level —
every instrument's rules ride along with the clone without any
library mechanism.

So the rule library is doing very little work, and the
abstraction it imposes (the operator chooses a RuleSet, then
edits *that*) adds an unnecessary indirection between the
operator and the rule-authoring engine.

**The instrument builder retires the rule library.** The
Assignment-rule editor sits inline in Band 1 of the
per-instrument card, authoring rules directly into the
instrument's own rule list. No RuleSet pinning, no seeded
RuleSets, no "Save to library", no "Add from library", no
Rule Builder child page.

### The RTD library retires for numerical + string types

Response Type Definitions today carry the shape of every
response field's input: data type (String / Integer / Decimal
/ List) plus type-specific bounds (max_length for strings;
min / max / step for numerics; option list for lists). They
are session-scoped, with 10 seeded definitions per new session
(`Long_text` / `Short_text` / `Yes_no` / `Grade` / `Likert5` /
`100int` / `0-to-2int` / `1-to-5int` / `1-to-5half` /
`1-to-5dec`) and an optional personal-library copy-in.

The same combinatorial / reuse argument applies — but only
partially. Splitting RTDs by data type:

- **Numerical RTDs** (Integer, Decimal). A definition like
  `1-to-5int` carries `min=1, max=5, step=1`. Trivial to
  author inline on the response field: pick "Integer", type 1
  in min, 5 in max. The library is doing no real work; saving
  one as a personal RTD or seeding it on every new session
  spends operator attention to deliver a one-second typing
  shortcut.
- **String RTDs** (`Long_text`, `Short_text`). Each carries a
  `max_length` (and possibly a regex pattern in the future).
  Trivial to author inline. Same argument.
- **List RTDs** (`Yes_no`, `Grade`, possibly `Likert5`). These
  carry an **option list** — `["Yes", "No"]`,
  `["A", "B", "C", "D", "F"]`, `["Strongly disagree", …]` —
  that has real authoring cost the first time and real reuse
  value across instruments in the same session (a `Grade`
  list used on every skill assessment). The library
  abstraction earns its keep here.

**The instrument builder retires the RTD library for
numerical and string types, and keeps it (lightly) for List
types.** Numerical + string types become inline cell-level
decisions on each response field; the per-session catalog and
the personal-library copy-in retire for them. List types stay
as a per-session catalog of List definitions — multiple
instruments in the same session may share a List RTD — but
the personal-library copy-in retires for them too. Session
replication carries List RTDs with the clone, same as it
carries rules.

The post-retirement catalog is small: a handful of operator-
authored List RTDs per session, no seeds, no personal
library.

### What gets retired (combined list)

- **Seeded RuleSets** that ship with every new session
  (`Intra-group peer review`, `Cross-group peer review`,
  `FullMatrix`, etc.). Retire the seeding code path; existing
  seeded rows on existing sessions stay until the session is
  deleted or unused.
- **The personal RuleSet library**. The operator-Settings page
  loses the "Library RuleSets" card. The auto-copy-on-session-
  create code path retires.
- **The "Add from library" / "Save to library" affordances**
  on the Rule Builder. The Rule Builder child page itself
  retires once Band 1's inline editor lands.
- **The Available RuleSets sidebar** on the Instruments page.
- **The `library_origin_id` provenance column** on
  `session_rule_sets` — retire as part of the cleanup.
- **All 10 seeded RTDs** that ship with every new session.
  Numerical + string seeds (`Long_text` / `Short_text` /
  `100int` / `0-to-2int` / `1-to-5int` / `1-to-5half` /
  `1-to-5dec`) retire entirely. List-shaped seeds (`Yes_no` /
  `Grade` / `Likert5` if treated as a list) become **optional
  starter templates** for the inline List-RTD editor (see
  below), not auto-seeded session rows.
- **The personal RTD library**. The operator-Settings page
  loses the equivalent "Library RTDs" card. The
  auto-copy-on-session-create code path retires for RTDs too.
- **`OperatorResponseTypeDefinition`** as a separate model
  (today's personal-library entity). Retires.
- **The `library_origin_id`-equivalent provenance column** on
  `response_type_definitions` — retire as part of the cleanup.

### What stays

- **The rule engine itself.** No change. Same
  MATCH / FILTER / QUOTA kinds, same predicate vocabulary,
  same `ALL_OF` / `ANY_OF` combinators, same evaluation order.
- **The `session_rule_sets` table** stays as the per-
  instrument rule-list storage. (Renaming it to
  `instrument_rules` to drop the "set" framing is optional and
  separable.)
- **The `response_type_definitions` table** stays — but
  **only carries List-type rows going forward**. Numerical +
  string types are inlined onto `instrument_response_fields`
  directly. (Renaming the table to `list_response_types` is
  optional and separable.)
- **Session replication** carries instrument rules + List
  RTDs with the clone unchanged.

### Optional: starter templates as one-shot inserts

A lightweight replacement for both libraries: small
**"Insert starter ▾"** menus on the inline editors offering
named templates that prefill the editor — no provenance link,
no library row, no future updates. The operator edits from
there exactly as if they had typed the values themselves.

- **Band 1's Assignment-rule editor** — templates like
  `FullMatrix`, `Intra-group peer review on tag1`,
  `Cross-group peer review on tag2`.
- **Band 2's response-field column editor — numerical type
  picker** — templates like `1-to-5 integer`, `0-to-100
  integer`, `1-to-5 half-step decimal`. Picking one fills in
  data_type + min + max + step.
- **Band 2's response-field column editor — String type
  picker** — templates like `Short text (100 chars)`,
  `Long text (2000 chars)`. Picking one fills in data_type +
  max_length.
- **Band 2's response-field column editor — List type picker**
  — templates like `Yes / No`, `Grade A-F`, `Likert 5-point`.
  Picking one creates a new List RTD in the session's catalog
  with the standard option set; the operator can then edit
  the options.

This preserves the convenience of "I know this pattern, just
give me the starting values" without re-introducing a library
abstraction. Optional and deferred — each editor can ship
without it and add it later if pilot demand materialises.

---

## The six links

The six conceptual decisions an operator makes per instrument.
Each link maps to a slot somewhere in the three vertical bands
of the editor; the mapping is detailed in
[§Layout](#layout) below.

### Link 1 + Link 2 — Assignment rule

**Question.** Which reviewers fill out this instrument, and
who does each reviewer review?

**Today.** The engine already evaluates rule predicates that
reference both `reviewer.*` and `reviewee.*` (plus
`pair_context.*`) address spaces, with `ALL_OF` / `ANY_OF`
combinators across multiple MATCH / FILTER rules. The existing
Rule Builder UI already exposes all nine tag positions on both
the LHS field picker (`_FIELD_PICKER_VALUES` in
`app/web/views/_rule_builder.py:96-106`) and the RHS operand
picker. So a rule like
`reviewer.tag2 equals "Lead" AND reviewee.tag1 same_as
reviewer.tag1` is fully expressible today.

(The spec at `spec/rule_based_assignment.md` §7.2 carries a
stale claim that the LHS picker "omits the reviewer tags" —
the implementation does not enforce this. Flagged for a future
spec sweep.)

**Inputs.** A rule list against the predicate vocabulary:

- **Field picker (LHS)** — any of the nine tag positions.
- **Operator picker** — `equals`, `not_equals`, `in`, `not_in`,
  `matches`, `not_matches`, `is_empty`, `is_not_empty`,
  `same_as`, `different_from`.
- **Operand picker (RHS)** — literal value, list of literals,
  or any of the nine tag positions (for cross-side
  comparisons).
- **Combinator** — `ALL_OF` (default) or `ANY_OF` for joining
  multiple rules.
- **Kind** — `MATCH` (include matching pairs) or `FILTER`
  (exclude matching pairs).

The default rule list is empty, which means **the full matrix**
— every reviewer-reviewee pair in the session is in scope.
Reviewers who land on no pair are simply not assigned the
instrument; this is the natural way to scope reviewers via
rules.

**Output.** A materialised set of `(reviewer, reviewee)` pairs
that Link 3's unit-of-review choice then groups or leaves as-is.

**Audit footprint.** Existing `assignments.generated` event;
the canonical `excluded_counts` envelope captures every rule's
contribution.

### Link 3 — Unit of review

**Question.** Does the reviewer review each reviewee in their
pool *individually* (one row per reviewee) or *grouped* (one
row per group)?

**Today.** A binary `Instrument.group_kind` flag splits
instruments into per-reviewee and group-scoped variants;
group-scoped instruments partition the reviewer's pool by
operator-marked boundary tags inside the Display Fields table.
The mode is set at instrument creation and is one-way (delete
and recreate to switch). See
[`spec/group_scoped_instruments.md`](../spec/group_scoped_instruments.md).

**Inputs.** A unit-of-review choice:

- **Individual** (default) — one row per `(reviewer, reviewee)`
  pair on the reviewer surface.
- **Grouped** — the reviewer's pool partitions by reviewee tags
  marked as boundary tags. One row per group; writes fan out
  to every group member on save.

When Grouped, a multi-select picks which of the three reviewee
tag slots define group identity. Picking zero collapses the
whole pool into one group. Pair-context tags are deliberately
not in scope for Link 3 — group identity is a property of the
reviewee, not of the reviewer-reviewee relationship.

**Mode switching** *after* responses exist needs reconciler
discipline (see [§Reconciling regeneration](#reconciling-regeneration)).

**Audit footprint.** New emitter
`instrument.unit_of_review_updated` carrying the mode +
boundary-tag selection diff.

### Link 4 — Visibility scope

**Question.** Who is allowed to read responses on this
instrument?

**Today.** Operators only.

**Inputs.** A choice of one or more visibility audiences:

- **Operators only** — the today-default.
- **Reviewees themselves** — each reviewee reads every
  response about them.
- **Observers** — a tag-defined cohort. Two sub-variants:
  - **Reviewee-tag-defined** — "every active reviewer whose
    `reviewer.tag1 == reviewee.tag1` can see responses about
    that reviewee".
  - **Pair-context-defined** — "every active reviewer with a
    relationship row where `pair_context.tag2 == 'observer'`
    can see responses about that reviewee".

Each audience is opt-in; the default is "Operators only".
Multiple audiences may be enabled.

**Audit footprint.** New emitter
`instrument.visibility_scope_updated` plus a per-read audit
event family (`response.read_by_reviewee`,
`response.read_by_observer`) gated on a deployment-level
toggle.

### Link 5 — Read shape

**Question.** When a non-operator audience reads a response,
what shape does the data take?

**Inputs.** Three mutually-exclusive shapes per non-operator
audience:

- **Raw** — the literal value the reviewer entered.
- **Summarised** — aggregate-only: counts, mean / median (for
  numeric RTDs), histograms (for List / Yes_no), word counts +
  length distributions (for String). No per-reviewer
  attribution.
- **Anonymised** — per-cell content surfaced but reviewer
  identity stripped.

A k-anonymity floor (default `k = 3`) suppresses any
aggregate / anonymised cell with fewer than k contributing
reviewers.

**Audit footprint.** New emitter
`instrument.read_shape_updated`.

### Link 6 — Release timing

**Question.** When does each non-operator audience start
seeing the responses?

**Inputs.** A per-audience timing choice:

- **While review is ongoing** — reads open the moment the
  audience's eligibility resolves.
- **When released** — reads stay closed until the operator
  flips an explicit **Release responses** action.

Operators are always read-now; only the new non-operator
audiences carry a timing choice. The Release action stamps a
per-`(instrument, audience)` `released_at` timestamp; the
read-path guard consults the stamp. Releases are reversible
("Un-release") with confirmation.

**Defaults.** Reviewees + Observers default to "when released"
so the operator decides timing. Operators are implicitly
"while ongoing" (today's contract).

**Audit footprint.** New emitter
`instrument.release_timing_updated` + emitters
`instrument.responses_released` /
`instrument.responses_unreleased` for every flip.

---

## Layout

One **full-width card** per instrument, replacing the existing
per-instrument card on the Instruments page. Inside, three
stacked sections, each its own visual band within the same
parent card frame:

```
┌─ Instrument #2 — "Peer skill assessment"  [accepting]  [showing] ────────┐
│                                                                          │
│  ── Band 1: Assignment + Unit ────────────────────────────────────────   │
│                                                                          │
│  ┌── Assignment rule (inline editor) ─────────────────────┐ ┌── Unit ──┐│
│  │  Include pairs where                                    │ │Individual││
│  │    reviewer.tag2  is one of  ["Lead"]                   │ │          ││
│  │  AND                                                    │ │ [Edit ▸] ││
│  │    reviewee.tag1  is the same as  reviewer.tag1         │ │          ││
│  │  ⊕ Add rule                            [Insert starter ▾]│ │          ││
│  └─────────────────────────────────────────────────────────┘ └──────────┘│
│                                                                          │
│  ── Band 2: One reviewer-surface row ──────────────────────────────────  │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────────┐│
│  │ Reviewee     │ Team    │ Photo │ Skill rating │ Strengths            ││
│  │ Jane Doe     │ Alpha   │  🧑    │     [4 ▾]    │ [textarea text…]     ││
│  │              │         │       │              │                      ││
│  │ ⊕ Add column                                                         ││
│  └──────────────────────────────────────────────────────────────────────┘│
│  Live preview — sample reviewee: Jane Doe ▾                              │
│                                                                          │
│  ── Band 3: Per-audience access ──────────────────────────────────────   │
│                                                                          │
│  ┌── 4. Visibility ─────┐ ┌── 5. Read shape ─────┐ ┌── 6. Release ─────┐│
│  │ Operators            │ │ Operators: raw       │ │ Operators: always ││
│  │ Reviewees            │ │ Reviewees: anonymise │ │ Reviewees: on rel ││
│  │ (Observers: none)    │ │                      │ │   — not yet       ││
│  │              [Edit ▸]│ │              [Edit ▸]│ │             [Edit ▸]││
│  └──────────────────────┘ └──────────────────────┘ └───────────────────┘│
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

The three bands separate visually with thin horizontal rules,
not with card borders — the bands are sections of one card, not
sub-cards. The instrument identity (number, name, status pills)
sits in the card header above Band 1.

### Band 1 — Assignment + Unit

Two side-by-side regions:

**Left (wider): Assignment rule — inline editor.** Replaces
both the existing Rule Builder card and the Rule Builder child
page. Authors the rule list directly:

- A list of rules, one row per rule, each carrying kind picker
  (Include / Exclude), field picker, operator picker, operand
  picker, and a remove button.
- Combinator pill above the list (`ALL_OF` / `ANY_OF`) when
  there are two or more rules; hidden when there is just one.
- `⊕ Add rule` button below the list to add an empty rule row.
- `Insert starter ▾` button next to Add rule, opening a small
  menu of named templates that prefill the editor (the
  one-shot replacement for seeded RuleSets — see
  [§Why direct rule authoring](#why-direct-rule-authoring-not-a-rule-library)).
- Drag-handle on each rule row for reordering (the engine
  evaluates rules in document order).
- The eligible-pair count cache (from Segment 13C) renders as
  a small caption under the editor: `2,484 reviewer-reviewee
  pairs across 12 reviewers and 207 reviewees`.

The inline editor is **edit-in-place** — no separate child
page, no Save/Cancel "modes" gating individual rule edits.
Each rule row autosaves on blur (or on every keystroke, see
open question on autosave-vs-blur). The whole editor honours
the existing `_require_editable` lifecycle gate — disabled in
`ready` with the standard "Revert to draft to edit" tooltip.

**Right (narrow): Unit of review.** Inline picker:

- **Individual** vs **Grouped** radio.
- When Grouped, a multi-select of reviewee-tag slots that
  define group identity.

Editing Unit autosaves on blur and follows the same lifecycle
gating as Band 1's rule editor.

### Band 2 — Live preview row

The instrument's review form, rendered as a **single sample
row** in the same DOM shape the reviewer surface uses. Sits
full-width in the centre of the card.

Columns left to right:

- **Reviewee identity** — always present, not editable as a
  column (it is the row's anchor). Renders the sample
  reviewee's name + email_or_identifier per the existing
  reviewer-surface contract.
- **Display field columns** — one per display field the
  operator has added. Renders the sample reviewee's value for
  that source. Per-column header shows the friendly label;
  clicking the header opens an inline editor for label /
  source choice / visibility / sort priority / delete.
- **Response field columns** — one per response field the
  operator has added. Renders the field's actual input control
  (`<input>`, `<textarea>`, `<select>`) bound to the field's
  type + bounds. The cell shows a placeholder value, not a
  real response. Per-column header shows the friendly label,
  type pill (`Integer 1-5`, `String 100`, `List: Grade A-F`),
  and required pill; clicking the header opens an inline
  editor for label / key / type / required / help text /
  delete.

  **Inline type editor.** When the operator edits the column's
  type, the editor presents a small per-data-type form:
  - **String** — input for `max_length`. Optional
    "Insert starter ▾" with `Short text (100)` / `Long text
    (2000)`.
  - **Integer** — inputs for `min` / `max` / `step`. Optional
    "Insert starter ▾" with `1-to-5`, `0-to-100`, etc.
  - **Decimal** — inputs for `min` / `max` / `step`. Optional
    "Insert starter ▾" with `1-to-5 half-step`, `1-to-5
    decimal`, etc.
  - **List** — picker over the session's existing List RTDs
    (none by default) plus an `Add new list` action. Picking
    Add new list opens an inner editor for the list's name +
    option values. The created List RTD is a session-level
    row reusable by other instruments. Optional
    "Insert starter ▾" with `Yes / No`, `Grade A-F`,
    `Likert 5-point`.
- **`⊕ Add column`** — last cell. Opens a chooser that asks
  "Display column or Response column?". Picking display
  surfaces the seven D6 sources (filtered to those not already
  added); picking response opens the inline type editor
  described above, starting on the operator's most-recently-
  used data type (or String by default).

The preview row is **interactive**:

- **Reorder columns** by dragging headers (or with ▲/▼ arrows
  on each header for keyboard / accessibility).
- **Rename** a column inline by clicking its header label.
- **Retype** a response column by re-opening the inline type
  editor and switching data type / bounds. Changing the data
  type of a column with saved responses triggers a confirm
  flow naming the cascade impact.
- **Toggle visibility** (display columns only) — invisible
  columns grey out, retaining their slot in the row.
- **Delete** a column with confirmation; response columns with
  saved responses trigger the existing cascade-confirm flow.

The preview row is **never a real response**. The operator's
inputs into response cells are ignored — they exist only to
demonstrate the input control's shape. A small caption
underneath reads: *"Live preview — reviewers see one row like
this per reviewee in their assignment universe. Sample
reviewee: ▾ Jane Doe"* with a selector to switch the sample.

When Link 3 is **Grouped**, Band 2 renders a *group row*
instead of a reviewee row — composed group identity column on
the left, sample group's boundary-tag values shown.

### Band 3 — Per-audience access

Three side-by-side summary blocks for Links 4, 5, 6. Each
shows the link name, a one-line summary of the current
configuration, and an Edit button.

A consolidated **single-row table** is the doc's preferred
later shape — one row per enabled audience carrying
`audience kind | predicate? | read shape | release timing`,
with inline editors per cell. The three-summary-blocks layout
ships first because it's the smaller change; the table
collapse is deferred until Link 4 + Link 5 + Link 6 are all
lit up.

---

## Data model deltas

Four schema deltas — each separable and independently
shippable. Links 1 + 2 reuse the existing per-instrument
`session_rule_sets` rule-list storage with no schema change
(the rule library retires from above the engine line; the
storage table stays). Link 3 reuses (and refines) the existing
group-scoped instrument schema. Plus one delta for the RTD-
library retirement on `instrument_response_fields` +
`response_type_definitions`.

### D-RTD — Response field type inlining

Numerical + string response types inline onto the response
field directly. List types stay as separate session-level
rows referenced by FK.

New / changed columns on `instrument_response_fields`:
- `data_type` — enum `{string, integer, decimal, list}`.
- `max_length` — int, nullable. Used when data_type == string.
- `min`, `max`, `step` — numerics, nullable. Used when
  data_type in `{integer, decimal}`.
- `response_type_definition_id` — kept, becomes nullable.
  Used **only** when data_type == list, pointing at a session-
  level List RTD row.

Changes on `response_type_definitions`:
- The table stays but narrows to **List-type rows only**.
  Numerical + string rows are migrated by inlining their
  bounds onto every referencing `instrument_response_fields`
  row and then dropped.
- `library_origin_id` and any other personal-library
  provenance columns retire.
- Optional rename to `list_response_types` to drop the
  generic RTD framing — separable.

`OperatorResponseTypeDefinition` (the personal-library entity)
retires entirely along with its table.

The migration is one-way and involves data movement: the
operator's RTD catalog and every response field's referenced
RTD must round-trip through a backfill that copies bounds
inline. Backfill must run before retiring the numerical +
string seed rows. Details deferred to Part 1d sequencing.

### D3 — Unit of review (Link 3)

Generalises the existing `Instrument.group_kind` flag and the
boundary-tag checkboxes that live on per-display-field rows
today:

- `unit_of_review` — enum `{individual, grouped}` on
  `instruments`. Replaces the binary `group_kind` flag.
- `group_boundary_tags` — JSON array of `reviewee.tagN` slot
  names (e.g. `["tag1", "tag3"]`). Replaces the existing
  in-Display-Fields-table boundary-tag checkboxes. The
  Display Fields table loses its boundary-tag column once
  this ships.

### D4 — Visibility scope (Link 4)

A new structured column on `instruments`:
- `visibility_audiences` — JSON array of objects
  `{audience_kind, predicate?}`. `audience_kind ∈
  {operator, reviewee, observer}`. `predicate` is required for
  `observer`.

Plus a downstream read-path guard consulting this column on
every response-row read by a non-operator.

### D5 — Read shape (Link 5)

A new JSON column on `instruments`:
- `read_shapes` — JSON object keyed by audience kind, valued by
  `{shape: raw|summarised|anonymised, k_anonymity_floor: int}`.

### D6 — Release timing (Link 6)

Two new structures:
- `release_timing` — JSON object on `instruments` keyed by
  audience kind, valued by `{mode: while_ongoing | on_release}`.
- `instrument_releases` — new table keyed by
  `(instrument_id, audience_kind)`, carrying `released_at` and
  `released_by_user_id`. One row per release flip; `released_at`
  null means "not currently released".

D4 + D5 + D6 may merge into one `audience_policy` JSON column
carrying `{audience_kind, predicate?, shape, k_anonymity_floor,
timing}` per row, with release timestamps still in the
separate `instrument_releases` table.

### Migrations

One Alembic revision per delta, adding columns inert (default
null / preserve `group_kind` value for D3). Service layer
writes them; route layer surfaces them; read-path guards on
non-operator surfaces.

---

## Sequencing

A sequence of independently-shippable parts:

| Part | Scope | Depends on |
|---|---|---|
| **0 — Schema pre-positioning** | Inert columns + tables on `instruments` (D3, D4, D5, D6) plus the inline-type columns on `instrument_response_fields` (D-RTD's `data_type` / `max_length` / `min` / `max` / `step`, all nullable, no backfill yet). No behaviour change. | nothing |
| **1 — UI shell (vertical bands)** | Replace the per-instrument card with the three-band layout. Band 1 shows the existing Rule Builder card on its left and a Unit-of-review picker on its right (the picker reflects today's `group_kind` flag read-only). Band 2 renders the existing Display Fields + Response Fields tables in a transitional state (not yet collapsed into the preview row). Band 3 shows placeholder summary blocks for Links 4-6 (Edit buttons inert). | Part 0 |
| **1b — Inline Assignment rule editor** | Replace Band 1's Rule Builder card with the inline editor described above. Retire the Rule Builder child page. Retire seeded RuleSets, personal-library, "Save to / Add from library" affordances, the Available RuleSets sidebar, and `library_origin_id`. Add the "Insert starter ▾" templates menu. | Part 1 |
| **1c — Live-preview row** | Replace Band 2's selector tables with the live-preview row + inline column-header editing. Sample-reviewee selector. The response-column type editor presents the inline numerical / string / list type form described above. List types continue to pick from session-level RTD rows; numerical + string types render the inline bounds form but the underlying response field still references a `response_type_definitions` row (the data inlining is deferred to Part 1d). | Part 1 |
| **1d — RTD-library retirement** | D-RTD schema delta: add inline data_type / bounds columns to `instrument_response_fields`, backfill from referenced RTDs, drop the numerical + string seeded RTDs from the seeding path, retire the personal-library RTD copy-in, retire `OperatorResponseTypeDefinition`, narrow `response_type_definitions` to List-only rows. Update Band 2's response-column editor to write inline bounds for numerical + string types and reference `response_type_definitions` only for List. The Instruments-page Response Type Definitions card narrows to List entries only (or is folded entirely into Band 2's inline List picker). | Part 1c |
| **2 — Link 3 (unit of review)** | Promote the existing `group_kind` flag + boundary-tag checkboxes into Band 1's Unit-of-review picker. Add post-creation mode-switching backed by the reconciler. Display Fields table loses its boundary-tag column. | Parts 0 + 1 |
| **3 — Link 4 (visibility, operator + reviewee audiences)** | Light up the Visibility summary block in Band 3. Per-reviewee read path on a new `/reviewer/sessions/{id}/{position}/about-me` surface. | Parts 0 + 1 |
| **4 — Link 5 (read shape, summarised + anonymised for reviewee audience)** | Light up the Read-shape summary block in Band 3. Aggregator service, anonymisation transformer, k-anonymity floor. | Part 3 |
| **5 — Link 6 (release timing, operator + reviewee audiences)** | Light up the Release-timing summary block in Band 3 + per-instrument-per-audience Release / Un-release affordance. Read-path guard consults `instrument_releases`. | Part 3 |
| **6 — Link 4 (observer audiences)** | Reviewee-tag-defined and pair-context-defined observer audiences. Observer dashboard surface. | Part 3 |
| **7 — Link 5 (read shape for observer audiences)** | Per-observer-audience read shape configuration. | Parts 4 + 6 |
| **8 — Link 6 (release timing for observer audiences)** | Per-observer-audience release timing. | Parts 5 + 6 |
| **9 — Band 3 table collapse (optional)** | Replace the three-summary-blocks layout with the single-row-per-audience table. | Parts 5 + 6 + 7 + 8 |

Parts 0 + 1 must land in that order. Parts 1b and 1c are
independent once Part 1 ships. Parts 2 / 3 are independent
once Part 1 ships. Parts 4 / 5 / 6 / 7 / 8 cascade per the
dependency column.

---

## Cross-cutting concerns

### Validation surface

Each link contributes new validation rules:

- **Links 1 + 2** — existing rule-engine validation,
  unchanged. Empty rule list with empty reviewer set is a
  warning ("no reviewers in scope"), not an error.
- **Link 3** — when **Grouped**, at least one boundary tag
  must be selected *or* the operator opts in to "single group
  covering the whole pool". A boundary tag with zero non-empty
  values across the roster is a warning.
- **Link 4** — observer-audience predicate references unknown
  tag slots; visibility-audience set is empty (every
  instrument must have at least Operators).
- **Link 5** — k-anonymity floor is achievable given the
  generated assignment count (warning, not error, since
  rosters may grow).
- **Link 6** — release timing references an audience that
  Link 4 did not enable is an error.

Every rule lands as a `ValidationRule` in the existing
registry (see [`spec/validate_page.md`](../spec/validate_page.md))
and surfaces on the Validate page with the standard "Fix on
Instrument Builder ↗" deep-link.

### Friendly labels

The chain editors consume the existing friendly-label registry
(see [`spec/setup_pages.md`](../spec/setup_pages.md) and
[`spec/settings_inventory.md`](../spec/settings_inventory.md)
for the 12 in-scope slots). Predicates render with operator-
customised labels for `reviewer.tag1` etc.; raw machine names
live only in the JSON payloads and audit events.

### Group-scoped instruments

Link 3 *is* the group-scoped-instrument concept, generalised:
the existing binary `group_kind` flag and the Display-Fields-
table boundary-tag checkboxes (see
[`spec/group_scoped_instruments.md`](../spec/group_scoped_instruments.md))
become the Unit-of-review picker. The downstream behaviour —
write fan-out across group members, read-time collapse to one
row per group, aggregation semantics on monitoring and extract
surfaces — carries forward unchanged.

Band 2's live-preview row in Grouped mode renders one group
row instead of one reviewee row; the sample group is the first
group the boundary tags partition the universe into.

Link 4's visibility model for grouped instruments: a reviewee
in a group sees the group's response, not the per-member fan-
out — the existing read-time collapse continues to apply.

### Reconciling regeneration

Editing the rule list (Links 1 + 2) or the unit of review
(Link 3) changes either which pairs the assignment matrix
materialises or how they collapse on the reviewer surface. The
existing reconciler
([`spec/reconciling_regeneration.md`](../spec/reconciling_regeneration.md))
already handles Links 1 + 2 — pairs the new chain drops
cascade-delete their responses; pairs the new chain keeps
preserve theirs; the super-button dry-runs the impact and
prompts when responses would be lost.

Link 3's mode switching is a new reconciler responsibility:

- **Individual → Grouped.** Per-pair responses collapse into
  per-group responses. The reconciler picks one canonical
  value per group (default: most-recently-saved per member);
  members whose values are dropped lose their individual
  response. The super-button dry-run names every reviewee
  whose response would be merged-away.
- **Grouped → Individual.** Per-group responses fan back out
  to per-pair responses by duplicating the group value into
  every member's row. No data loss.

### CSV round-trip

The Settings CSV ([`spec/csv_contracts.md`](../spec/csv_contracts.md))
must round-trip the new instrument fields. Each link's
configuration travels as rows in the Settings CSV's per-
instrument section. The library-related rows (seeded-RuleSet
provenance, personal-library copies) retire from the CSV
alongside the library mechanism.

### Edit-state policy

When the session is `ready` (Activated), the editor splits
along the "assignment-shape vs read-policy" axis:

- **Links 1 + 2 + 3** (Band 1's Assignment rule + Unit of
  review) edit the assignment matrix or its collapse shape;
  the editors render disabled with "Revert to draft to edit"
  tooltips. Editing them invalidates `validated → draft` per
  the existing `invalidate_if_validated` discipline.
- **Band 2 column edits** (add / rename / retype / reorder /
  delete display + response fields) also invalidate, since
  they change the reviewer-surface shape.
- **Links 4 + 5 + 6** (Band 3 per-audience access) edit read-
  time policies only; their editors stay live in `ready`.
  Edits do not invalidate.

The Release / Un-release flips on Link 6 are runtime
operations on an activated session, not setup-time edits, and
have their own per-instrument-per-audience confirm flow.

---

## Open questions

1. **Autosave vs blur-save in Band 1's rule editor.** Each
   rule row could autosave on every keystroke (fastest
   feedback, more requests) or on blur (one save per rule
   edit, slight latency). Default proposal: blur. Decision
   deferred to Part 1b.

2. **Sample reviewee picking.** Band 2's live preview needs a
   sample reviewee. Three policies:
   (a) the first active reviewee that satisfies the rule list
   (deterministic, may spotlight a regular reviewee);
   (b) operator-selectable from a small dropdown of eligible
   reviewees;
   (c) synthetic "John Sample" with placeholders.
   Default proposal: (b), with (a) as fallback when not
   picked. Decision deferred to Part 1c.

3. **Multiple sample rows.** Optionally show N sample rows in
   Band 2 to sanity-check display values across tag
   combinations? Vertical-space cost. Default proposal: one
   row + selector; multi-row mode behind a toggle.

4. **Sort defaults in the preview.** Today's per-instrument
   sort defaults are configured on the Display Fields table
   via the tri-state widget
   (`spec/sort_by_reviewee.md`). In the live-preview model
   that surface goes away — sort priority becomes an inline
   header-context-menu choice. Decision deferred to Part 1c.

5. **Discoverability of unused columns.** A selector table
   shows every available D6 source as a checkbox row; the
   preview row shows only the included columns. Mitigation:
   the `⊕ Add column` chooser lists every D6 source with a
   checkmark next to the ones already present.

6. **Self-review row in Link 4.** When the reviewer is also
   the reviewee, the "reviewee can see their own response"
   audience is trivially satisfied — but the operator may
   want to *hide* self-review entries from the reviewee's own
   dashboard (mirrors the existing self-review-active flag).
   Per-instrument override?

7. **Summarised view for non-numeric RTDs.** Easy for
   `Likert5` / `1-to-5int` / `100int`. Less clear for
   `Short_text` / `Long_text` — count + length distribution +
   (optionally) word-frequency list? Deferred to Part 4
   design.

8. **Operator vs sys-admin power over Link 4.** Should an
   operator be allowed to enable reviewee-visible feedback
   without sys-admin oversight? Deferred to a permissions
   sweep alongside Part 3.

9. **Scheduled release on Link 6.** A per-`(instrument,
   audience)` `release_at` timestamp mirroring 18G auto-send
   would let releases fire on a schedule. Deferred until
   manual release has been exercised in a pilot.

10. **Per-reviewer release granularity.** A finer-grained
    variant would release per-reviewee (e.g. roll out
    feedback one reviewee at a time). Operationally noisier;
    deferred.

11. **Starter-templates menu — included or not?** The
    one-shot "Insert starter rules" menu is the lightweight
    replacement for seeded RuleSets. The doc treats it as
    optional. If pilot operators reach for it rarely, drop
    it; if often, ship it. Decision deferred to Part 1b's
    post-ship feedback.

12. **Rename `session_rule_sets` → `instrument_rules`?**
    The "RuleSet" framing carried the library abstraction
    that retires. Renaming the storage table to match the
    new mental model is optional and separable. Decision
    deferred.

13. **List-RTD card placement after Part 1d.** Once the RTD
    library narrows to List entries only, the
    Instruments-page "Response Type Definitions card" no
    longer needs to be a separate full-width card. Three
    options: (a) keep it as a slim session-wide List
    catalogue below the instrument cards, (b) fold it
    entirely into Band 2's inline List-type editor (every
    Add-list / Edit-list operation happens per-instrument,
    with cross-instrument reuse implicit), (c) keep an
    inline catalogue as a collapsible panel inside Band 2.
    Default proposal: (b), since most operators only see one
    List type per session and the cross-instrument sharing
    is an edge case. Deferred to Part 1d's UI design.

14. **Rename `response_type_definitions` → `list_response_types`?**
    The "RTD" framing was the library abstraction; the
    post-retirement table only carries List rows. Renaming
    to match the narrowed scope is optional and separable.
    Decision deferred.

---

## Related specs

- [`spec/instruments.md`](../spec/instruments.md) — the per-instrument card the instrument builder replaces. The "Response Type Definitions card" section needs a rewrite once Part 1d ships: the card narrows to List-type entries only (or is folded into Band 2's inline List picker entirely).
- [`spec/reviewer-surface.md`](../spec/reviewer-surface.md) — the row shape Band 2 mirrors; the preview row must match it cell-for-cell.
- [`spec/rule_based_assignment.md`](../spec/rule_based_assignment.md) — the rule engine Band 1's editor sits inline on. **Stale claim to flag for a future spec sweep:** §7.2 "Field-selector ordering" says the LHS picker "omits the reviewer tags". The code (`app/web/views/_rule_builder.py:_FIELD_PICKER_VALUES`, lines 96-106) lists `reviewer.tag1/2/3` first. The spec describes a design intent that the implementation does not (and arguably should not) enforce. The library-related sections of this spec also need a rewrite once Part 1b ships.
- [`spec/group_scoped_instruments.md`](../spec/group_scoped_instruments.md) — Link 3's underlying behaviour.
- [`spec/sort_by_reviewee.md`](../spec/sort_by_reviewee.md) — sort-priority semantics that need a new home in Band 2's inline column-header affordance.
- [`spec/reconciling_regeneration.md`](../spec/reconciling_regeneration.md) — pair-preservation under rule + unit-of-review edits.
- [`spec/validate_page.md`](../spec/validate_page.md) — where instrument-builder validation issues surface.
- [`spec/csv_contracts.md`](../spec/csv_contracts.md) — Settings round-trip implications, including the library-row retirement.
- [`spec/settings_inventory.md`](../spec/settings_inventory.md) — friendly labels the editors consume; the operator-library settings retire once Parts 1b (RuleSet library) and 1d (RTD library) ship.
- [`spec/audience_and_identity_model.md`](../spec/audience_and_identity_model.md) — the audience model Links 4, 5, and 6 operationalise.
- [`spec/lifecycle.md`](../spec/lifecycle.md) — Link 6's release-stamp lifecycle layers on top of the session lifecycle; per-instrument release flips do not move the session between states.
