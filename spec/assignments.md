# Assignments

**The rule engine + the Assignments operator page.**

An **Assignment** is a `(reviewer, reviewee, instrument)` triple
materialised in the `assignments` table, with an `include`
boolean controlling whether the reviewer actually sees the
reviewee on their per-instrument page. Assignments are not
authored row-by-row; they're **generated** by running a per-
instrument rule pass over the session's reviewer × reviewee
matrix and slotting one row per surviving pair (Individual) or
per (reviewer, group_key) (Group).

This spec covers:

- The rule model that drives generation.
- The Assignments operator page at
  `/operator/sessions/{session_id}/assignments` — the
  per-instrument status table, the preview table, and the
  Self-review / Include / Show toggles.
- The reconcile + regenerate path that preserves saved
  responses across re-runs.

For the instrument side — what an instrument is, how Band 1
authors a rule, where `group_kind` lives — see
`spec/instruments.md`.

> **Status.** Implemented through Wave 5 (the post-collapse
> world). The library tier (operator-side RuleSet library +
> Rule Builder page) retired in Wave 5 PR 5.1 (PR #1446); every
> rule now lives on its instrument's Band 1. The synthetic
> Full Matrix shipped in Wave 4 PR 1. Historical doc set:
> `spec/archive/rule_based_assignment.md` and the fan-out half
> of `spec/archive/group_scoped_instruments.md`.

## Contents

- [Concept](#concept)
- [Rule model](#rule-model)
  - [Conceptual pipeline](#conceptual-pipeline)
  - [Rule kinds](#rule-kinds)
  - [Predicate vocabulary](#predicate-vocabulary)
  - [Combinator semantics](#combinator-semantics)
  - [RuleSet structure](#ruleset-structure)
- [Where the rule lives](#where-the-rule-lives)
- [Synthetic Full Matrix](#synthetic-full-matrix)
- [Self-review policy](#self-review-policy)
- [Group-scoped fan-out](#group-scoped-fan-out)
- [Evaluation algorithm](#evaluation-algorithm)
- [Assignments operator page](#assignments-operator-page)
- [Reconcile + regenerate](#reconcile--regenerate)
- [Validation surfaces](#validation-surfaces)
- [Worked example](#worked-example)
- [Open / deferred](#open--deferred)

## Concept

An Assignment connects three entities:

- **Reviewer** — a row in `reviewers`. Has Name + Email + up
  to three tag columns (`tag_1 / 2 / 3`).
- **Reviewee** — a row in `reviewees`. Has Name +
  email-or-identifier + up to three tag columns. `status`
  flags rosters: only `status='active'` reviewees are
  candidates for generation.
- **Instrument** — a row in `instruments`. Owns the rule (via
  `rule_set_id` or the synthetic Full Matrix when NULL) and
  the unit-of-review (`group_kind`).

Plus one pair-level entity:

- **Relationship** — a row in `relationships`, keyed by
  `(reviewer_id, reviewee_id)`. Holds the **pair-context tags**
  (`tag_1 / 2 / 3`) — facts that depend on the pair (e.g. "this
  reviewer is the team lead for this reviewee"). Pair-context
  rows are imported from CSV alongside the rosters.

Generation produces zero or more `Assignment` rows per
instrument. Each row carries:

- `reviewer_id`, `reviewee_id`, `instrument_id`.
- `group_key: str | NULL` — for group-scoped instruments, the
  comma-joined values of the boundary tags that make this
  reviewee a member of one group. NULL on Individual
  instruments.
- `include: bool` — whether the reviewer sees this reviewee on
  their per-instrument page. Defaults to True; the
  Assignments-page **Self review** toggle (and the per-row
  Include toggle on the preview table) drive it.

## Rule model

### Conceptual pipeline

For one instrument:

```
        full universe              ────────────────────────────────
        (every reviewer ×          1. Universe (assembled from the
          every active reviewee)      session's rosters)
                  │
                  ▼
        FILTER (Link 1 + Link 2    2. Filter (drop pairs that fail
         Composite rules)             tag predicates)
                  │
                  ▼
        MATCH (Link 2 cross-side    3. Match (drop pairs whose
         operators)                    cross-side operands disagree)
                  │
                  ▼
        QUOTA (currently unused     4. Quota (cap pairs per actor)
         on Band 1)
                  │
                  ▼
        Surviving pairs             5. Materialise into Assignment
                  │                    rows (one per pair for
                  ▼                    Individual; one per
        SELF-REVIEW (drop or keep      (reviewer, group_key) for
         based on rule-set              Group)
         exclude_self_reviews)
```

Wave 5 PR 5.2 + 5.3 collapsed the legacy / new-model split, so
every instrument's rule passes through this same pipeline. Band 1
of the instrument card is the only operator-facing entry into
the pipeline.

### Rule kinds

The internal `Rule` discriminated union supports four kinds.
Band 1 (the only authoring surface today) emits only `MATCH`
and `COMPOSITE`. The other two are honoured by the engine but
not surfaced in the UI.

| Kind | Purpose | Surfaced in UI? |
|---|---|---|
| `MATCH` | One predicate (`field operator operand`). | Yes — one per cell in Link 1 / 2's rule list. |
| `COMPOSITE` | Wraps a list of child rules with `AND` / `OR`. | Yes — one per Link in Band 1 (Link 1's Composite, Link 2's Composite). |
| `FILTER` | Domain-restriction rule (legacy slot). | No — Band 1 uses `MATCH` directly inside `COMPOSITE`. |
| `QUOTA` | Cap pairs per actor. | No. |

### Predicate vocabulary

A `MATCH` rule carries a `predicate` of `{field, operator, operand, case_sensitive}`.

**Field namespaces** (Wave 5):

| Namespace | Source | Available tag slots |
|---|---|---|
| `reviewer.tagN` | `Reviewer.tag_N` | `tag1 / tag2 / tag3` |
| `reviewee.tagN` | `Reviewee.tag_N` | `tag1 / tag2 / tag3` |
| `pair_context.tagN` | `Relationship.tag_N` | `tag1 / tag2 / tag3` |

Only namespace + slot combinations with at least one populated
roster row appear in the Band 1 dropdowns
(`views._instruments._new_model_usable_tags`).

**Operators** (UI → engine internal):

| UI | Engine internal | Operand shape |
|---|---|---|
| `IS` | `equals` | Free-text string |
| `IS NOT` | `not_equals` | Free-text string |
| `IS THE SAME AS` | `same_as` | A reviewer-side tag namespace (e.g. `reviewer.tag1`) |
| `IS DIFFERENT FROM` | `different_from` | A reviewer-side tag namespace |

The cross-side operators (`same_as` / `different_from`) read
the operand as another field reference rather than a literal —
they let Link 2 express "reviewee shares the reviewer's role
tag" without listing every value in the world.

`case_sensitive=False` is the default; the engine lowercases
both sides before comparison.

### Combinator semantics

The wrapping `Combinator` enum on a `RuleSet` or `COMPOSITE`:

- `ALL_OF` — every child must match (logical AND).
- `ANY_OF` — at least one child must match (logical OR).
- *(legacy)* `NONE_OF` — engine honours it but Band 1 doesn't
  emit it.

Band 1's outer `SessionRuleSet.combinator` is always `ALL_OF` —
Link 1's Composite ∩ Link 2's Composite. Inside each Composite,
the Link's per-cell combinator toggle (`AND` / `OR`) maps onto
the Composite's `op` field.

### RuleSet structure

Stored in `session_rule_sets`:

```python
SessionRuleSet(
    id: int,
    session_id: int,
    name: str,                      # "New-model instrument #{id} Band 1"
    description: str,
    combinator: str,                # ALL_OF | ANY_OF
    exclude_self_reviews: bool,     # see Self-review policy below
    seed: int | None,               # deterministic seed for QUOTA's RNG
    rules_json: list[dict],         # the rule list serialisation
)
```

`rules_json` is the persisted top-level rule list. For a Band 1-
materialised row it's typically:

```json
[
  {"id": "link1", "kind": "COMPOSITE", "op": "AND",
   "enabled": true,
   "rules": [
     {"id": "link1-r0", "kind": "MATCH", "enabled": true,
      "predicate": {"field": "reviewer.tag1",
                    "operator": "equals",
                    "operand": "Lead",
                    "case_sensitive": false}}
   ]},
  {"id": "link2", "kind": "COMPOSITE", "op": "OR",
   "enabled": true,
   "rules": [...]}
]
```

An untouched Link in `all` mode contributes no Composite (the
list is empty for that slot). When both Links are `all` and no
filter rules exist, no `SessionRuleSet` row is materialised at
all — the instrument keeps `rule_set_id=NULL` and the engine
substitutes the synthetic Full Matrix at evaluate time.

## Where the rule lives

> **Wave 5 collapse.** The pre-Wave-5 world had two authoring
> surfaces: a per-instrument pinned rule on the Instruments
> page and a standalone **Rule Builder page** at
> `/operator/sessions/{id}/rules` that managed the session's
> `SessionRuleSet` rows directly. Wave 5 PR 5.1 retired the
> Rule Builder page. PR 5.2 retired the cross-session
> `operator_rule_sets` library + `rule_set_revisions` tables.

Post-Wave-5, the only place to author a rule is **Band 1 of an
instrument card** (see `spec/instruments.md` § Band 1). The
rule is per-instrument and per-session:

- Each instrument's Band 1 either lazily materialises one
  `SessionRuleSet` row (when any Link is in `filter` / `group`
  mode with rules) or leaves `Instrument.rule_set_id=NULL`
  (when every Link is `all` / `individual`).
- The materialised row is owned by the instrument: deleting the
  instrument leaves the row behind (FK `ON DELETE SET NULL`),
  but the operator's exposure to it is via Band 1 only.
- Renaming, "Save As", or sharing rules across instruments is
  not supported. Replicate-the-instrument is the substitute.

There is no scope `personal` / `library` / `seeded` distinction
anymore — every row is per-session.

## Synthetic Full Matrix

When `Instrument.rule_set_id is NULL`, the engine substitutes a
synthetic schema (Wave 4 PR 1):

```python
RuleSetSchema(
    name="Full Matrix (new-model default)",
    combinator=Combinator.ALL_OF,
    rules=[],
    options=RuleSetOptions(excludeSelfReviews=False, seed=0),
)
```

Effects:

- **All pairs survive the filter** (empty rule list = no
  constraint).
- **Self-reviews are not excluded at generate.** The
  `Assignment.include` value falls back to
  `ReviewSession.self_reviews_active` (default True). The
  per-instrument Self-review toggle on the Assignments page
  flips `include` after generation.
- **`revision_seed=0`** for the engine's deterministic RNG (the
  rule-set id can't serve as seed when no row exists).

Materialised `SessionRuleSet` rows from Band 1 align with this
default: `_create_band1_rule_set` sets `exclude_self_reviews=False`
(PR #1452, 2026-05-26). The two paths are intentionally
indistinguishable from the generator's point of view.

## Self-review policy

**`excludeSelfReviews` is ALWAYS `False`.** The rule engine never
drops self-review pairs at the desugar stage — neither during
assignments generation nor during the Band 2 instrument-preview
sample pick. This is project-wide policy and is enforced in three
layers so it can't be silently re-enabled:

1. The `RuleSetOptions.excludeSelfReviews` Pydantic default is
   `False`.
2. `assignments._schema_from_row` hard-codes
   `excludeSelfReviews=False` when wrapping a `SessionRuleSet`
   row into a schema — the row's `exclude_self_reviews` column is
   ignored (it stays `False` on every Band-1 materialisation
   anyway, but the hardcode is defence-in-depth).
3. `instruments._band1.find_sample_in_scope_reviewee` (the
   `/preview-sample` workhorse) constructs its schema with
   `excludeSelfReviews=False`.

If an operator wants to **suppress** self-reviews, the two
supported affordances are:

- **Link rules.** Add a Link 2 (or Link 1) rule like `reviewee.email
  IS DIFFERENT FROM reviewer.email`. The engine evaluates these as
  ordinary filter logic, so the (R, R) pair never reaches
  materialisation. (Other tag-pair predicates also work — anything
  the operator wants to control.)
- **Per-instrument Self-review toggle.** Self-review pairs *are*
  materialised; flip the toggle on the Assignments page to set
  `Assignment.include=False` on every `(R, R)` row in that
  instrument. The session-level `ReviewSession.self_reviews_active`
  (default True) seeds this on first generation.

Reasoning: silently dropping self-pairs at the desugar stage
(a) is invisible to the operator — the row doesn't show up to be
inspected or toggled, and (b) under-counted group composition by
one whenever the sample reviewer was themselves a member of the
group (symmetric reviewer/reviewee sessions). The toggle path is
explicit, reversible without re-Generate, and inspectable on the
Assignments page.

Two attributes still drive whether self-review rows appear as
*active*:

1. **`SessionRuleSet.exclude_self_reviews`** (rule-set level).
   Vestigial column — the engine layer hardcodes False regardless
   of its value. Migration `d2e4f6a8c1b3` backfilled every row to
   `False` so the column matches behaviour, and
   `_create_band1_rule_set` writes `False` on every save.
2. **`ReviewSession.self_reviews_active`** (session level,
   defaults True). When a self-review pair is materialised, its
   `Assignment.include` is `True if self_reviews_active else False`.

In other words: self-review rows are always materialised. Whether
they're "active" is a post-generation toggle. This is the
user-facing affordance — the operator can flip self-review
inclusion at any time without re-running Generate.

### Group-scoped instruments — the whole-group rule

On a **group-scoped** instrument (`Instrument.group_kind`
non-NULL — see *Group-scoped fan-out* below), one logical
review-of-a-group is stored as **multiple `Assignment` rows**:
one row per `(reviewer, group_member)` pair, sharing a single
`group_key`. The reviewer fills out one answer for the whole
group; the save layer copies that answer onto every member
row.

The canonical self-review rule under this fan-out is the
**whole-group rule**: a review of a group counts as a
self-review iff **the reviewer is themselves a member of the
group they're reviewing** (i.e., one of the `(R, member)`
pairs in the group has `member == R` by the `is_self_review`
identity test). When the rule fires, **every** `Assignment`
row in that group is a self-review row, not just the `(R, R)`
member pair. Excluding self-reviews on a group-scoped
instrument rules the whole group out, not just the `(R, R)`
cell.

The canonical computation surface is
`assignments.classify_self_review(db, session_id=, rows=)` in
`app/services/assignments.py`; on individual-scoped
instruments it collapses to the per-row
`is_self_review(reviewer, reviewee)` test, and on group-
scoped instruments it applies the whole-group rule.

**Source of truth — `Assignment.is_self_review` column.**
The boolean column on the `assignments` table persists the
canonical classification for every row. Every write site
(regenerate, manual add, instrument clone / replicate) and
every edit trigger (reviewer email, reviewee identifier or
boundary tag, relationship pair-context tag, instrument
`group_kind`) calls
`assignments.recompute_self_review_classification` so the
column never drifts. Every downstream reader (extracts,
audit counters, the in-app `Assignments`-page status
blocks, the `set_instrument_self_reviews_active` toggle
backend) consumes the column directly. The
`assignments.replace_assignments` regenerate path closes
with a continuous-gate invariant
(`assignments.verify_self_review_classification`); strict
in test envs, log-and-auto-correct in production. The
overall consolidation plan + the five-PR ladder that
landed it lives in `guide/archive/self_review_consolidate.md`.

Pair-level `is_self_review(reviewer, reviewee)` survives as
a helper for the rule-engine desugar paths that operate on
**unsaved pair candidates** (where no `Assignment` row
exists yet), and as the inner per-row test inside
`classify_self_review`'s individual-scoped arm. Callers that
have an `Assignment` row in hand should read the column.

## Group-scoped fan-out

When `Instrument.group_kind` is non-NULL, the instrument is
**group-scoped**: the unit of review is a group of reviewees
rather than one reviewee at a time. The reviewer fills out one
answer for the whole group.

### Boundary key

`Instrument.group_kind` encodes the boundary spec — comma-
joined tag-key codes, e.g. `"r1"` (reviewee.tag_1),
`"r1,p2"` (reviewee.tag_1 AND pair_context.tag_2). See
`spec/instruments.md` § Link 3 for the encoding.

For a given (reviewer, reviewee) pair, the boundary key is the
tuple of those tag values in declaration order. Two reviewees
that share the same boundary key (with the same reviewer) are
in the same group.

The sentinel `"both"` (group instrument with no boundary tag)
means "all active reviewees form one global group per reviewer."

### Storage shape

One `Assignment` row per **(reviewer, reviewee)** pair, with
the boundary key copied into `Assignment.group_key`:

```
reviewer_id | reviewee_id | instrument_id | group_key   | include
------------+-------------+---------------+-------------+--------
1           | 10          | 5             | "Team Red"  | True
1           | 11          | 5             | "Team Red"  | True
1           | 12          | 5             | "Team Blue" | True
```

The decision to store per-reviewee rows (not per-group rows) is
documented in `spec/archive/group_scoped_instruments.md` §
"Why single-reviewee rows" — short version: stay consistent
with Individual storage so the same `assignments` table powers
both flavours; collapse-on-read instead of fork-on-write.

### Collapse-on-read

The reviewer surface groups the rows by `(reviewer_id,
instrument_id, group_key)` and renders one card per group:

- Identity cell: bold comma-joined boundary-tag values on top,
  member names below (truncated to first 10 with a `... + N
  more`).
- One set of response fields shared by every member of the
  group.

Writes from the reviewer fan-out across every group member: a
single response submission writes one `responses` row per
`(reviewer, reviewee, instrument)` tuple in the group, all
carrying the same answer. Reads collapse the rows back into one
group — extraction and aggregation respect this contract (see
`spec/csv_contracts.md`).

### Self-review interaction

On a group-scoped instrument, a "self review group" is **any
group containing the reviewer as one of its members**. The
self-review toggle drops the **whole group** when toggled off,
not just the self-row inside it. The implementation:
`_self_review_assignment_ids` in
`app/services/assignments.py` walks group_key membership rather
than per-row reviewer/reviewee identity.

## Evaluation algorithm

Implemented in `app/services/rules/engine.py`. The contract:

```python
result = engine.evaluate(
    rule_set_schema,
    reviewers=reviewers,
    reviewees=reviewees,
    pair_context_lookup=pair_context_lookup,  # (reviewer_id, reviewee_id) → Relationship
    override_exclude_self_reviews=...,        # per-call override; None = use schema's
    revision_seed=revision_seed,              # deterministic RNG seed
)
# result.pairs: list[(Reviewer, Reviewee)]
# result.excluded_counts: dict[reason -> int]
```

Steps:

1. **Build the universe.** Cartesian product of `reviewers` and
   `reviewees` (active only).
2. **Run the rule list.** Each rule in `rule_set_schema.rules`
   contributes a per-pair predicate; the top-level `combinator`
   wraps them.
3. ~~**Apply self-review exclusion.**~~ **Retired in Wave 5 /
   PR #1475 — project-wide policy is now `excludeSelfReviews=False`
   everywhere; the engine never drops `(R, R)` pairs at the
   desugar stage.** See the "Self-review policy" section above
   for rationale and the two supported suppression paths (Link
   rule + per-instrument Self-review toggle).
4. **Apply QUOTA.** Currently inert — no Band-1 QUOTA emission.
5. **Materialise.**
   - Individual: one row per surviving pair.
   - Group: one row per pair, with `group_key` populated.
   - `include` = `True` for non-self pairs;
     `session.self_reviews_active` for self pairs.

The engine is pure (no DB writes); the materialise step is the
caller's responsibility. `app/services/assignments.py` is the
write-side caller.

### Determinism

`revision_seed` is the `SessionRuleSet.id` (for materialised
rule sets) or `0` (for the synthetic Full Matrix). The seed
feeds any RNG decisions (today only QUOTA, which is dormant).
A given (rule, roster, seed) triple is bit-stable across
re-runs.

## Assignments operator page

The Operations-row page at
`/operator/sessions/{session_id}/assignments`. Top → bottom:

1. **Per-instrument status table** — one row per instrument
   summarising the current materialisation.
2. **Validation results banner** (when `?validated=1` or a
   validation pass surfaces issues).
3. **Assignments preview** — the row-level table of materialised
   pairs, with filter chips + per-row Include checkbox.

The page reuses the Workflow card chrome shared with Session
Home + other Operations-row pages.

### Per-instrument status table

Columns (left → right):

| Column | Meaning |
|---|---|
| Instrument | `block.instrument_label` — Short label or full name. |
| Type | "Individual" or "Group" (driven by `Instrument.group_kind`). |
| Generated | Pill carrying the row count, plus a `stale` pill when the current rule + roster pass would produce a different set. "Not generated yet" when zero. |
| Groups | Group count (distinct `(reviewer, group_key)` over the rows) for group instruments; "—" for individual. |
| Self review | Pill carrying the total self-review row count, plus an inline checkbox that bulk-flips `Assignment.include` on every self-review row in this instrument. Pill colour is `pill-info` (blue) when all are active, `pill-warning` (yellow) when not. The checkbox renders only when `self_review_total > 0`; on a session with no roster overlaps it doesn't render. |
| Included | Pill carrying the count of `include=True` rows. "—" before Generate. |
| Show | Per-instrument filter checkbox — client-side DOM toggle that hides / shows the instrument's pairs in the preview table below. Default: checked when any row materialised. |
| (action) | "Edit on Instruments page" deep-link to the instrument's card. |

The Rule column retired 2026-05-26 (PR #1451) — the rule lives
on Band 1 and isn't load-bearing as a column once the implicit
Full Matrix default landed.

### Self-review toggle wiring

The checkbox is bound to a per-instrument form
`POST /sessions/{sid}/assignments/instrument/{iid}/self-reviews-active`
with `active=true|false`. The service helper
`assignments.set_instrument_self_reviews_active`:

1. Loads every assignment row on the instrument with its
   reviewer / reviewee.
2. Computes the self-review subset
   (`_self_review_assignment_ids`, group-aware).
3. Flips `include` on every self-review row whose current value
   differs from the target.
4. Emits an audit event
   `assignments.instrument_self_reviews_active_set` with
   `counts.flipped` + `context.active` + `refs.instrument_id`.

Past activation (`is_ready`), the checkbox disables with the
title "Session is ongoing — revert to draft to change
self-review inclusion." The lifecycle spec spells out the
revert path.

### Preview table

The full assignment matrix, one row per `Assignment`. Columns
left → right:

| Column | Sortable? | Filterable? |
|---|---|---|
| (select) | — | — |
| Reviewer name | yes | — |
| Reviewer.tag1 / 2 / 3 | yes | implicit via row filter |
| Reviewee name | yes | — |
| Reviewee.tag1 / 2 / 3 | yes | implicit |
| Pair.tag1 / 2 / 3 | yes | implicit |
| Include | yes (boolean) | yes (toggle) |
| Instrument | yes | yes (per-instrument Show checkbox in the status table above) |

Rows with `include=False` render dimmed. The (select) column
enables bulk-set Include via a checkbox column header + a
per-row checkbox; the action row above the table carries
`Include selected` / `Exclude selected` buttons.

#### Bulk-set Include

`POST /assignments/include` with the selected
`assignment_id`s + `include=true|false`. Service helper
`assignments.bulk_set_assignment_include`. Lifecycle-aware
(same revert-to-draft guard as the self-review toggle when
the session is `is_ready`).

## Reconcile + regenerate

> **Background.** The pre-Wave-5 "Generate assignments" path
> wholesale-replaced an instrument's rows on every re-run,
> deleting saved responses. Segment 13D PRs #1065 → #1069 (also
> documented in `spec/archive/.../reconciling_regeneration.md`,
> kept) replaced this with a **diff-and-reconcile** path that
> preserves responses on pairs that survive the re-run.

The current behaviour: when Generate runs (manually or as part
of the Workflow-card Activate super-button), for each
instrument:

1. Run the engine over the current rule + roster.
2. Compute the diff against existing `Assignment` rows:
   - **To-insert.** New pairs the engine produced.
   - **To-delete.** Existing pairs no longer surviving the
     rule. **Their responses are deleted too** — this is the
     destructive part. The Workflow-card Activate super-button
     surfaces a `prepare_confirm` modal listing the deleted
     pairs first, so the operator acknowledges the loss
     before it happens.
   - **To-keep.** Pairs surviving both passes. Their
     `Assignment.include` is preserved; their responses
     survive untouched.

The diff is bit-stable (the engine's deterministic seed
guarantees the same pass produces the same set), so re-running
Generate without changing anything is a no-op.

### Staleness

The status-table "Generated" cell carries a `stale` pill when
the current rule + roster pass would produce a different set
from what's stored. The check is `stamp_changed(instrument,
db)`: hashes the rule + roster + group_kind and compares
against `instrument.cached_group_pair_stamp` (group instruments)
or a similar per-instrument digest.

A stale instrument doesn't auto-regenerate — the operator must
click the Generate button (or the Activate super-button, which
runs Generate transitively). The staleness signal is
informational.

### `reconcile_impact` dry-run

Used by the Activate super-button to show the
`prepare_confirm` modal before any destructive write happens.
Returns a tuple `(responses_deleted, deleted_pairs)`. The
Workflow card surfaces this and gates the final Activate POST
on operator acknowledgement.

## Validation surfaces

Registered rules in `app/services/validation.py:REGISTERED_RULES`
that fire on this page's domain:

- **`assignments.no_included_pairs`** (error) — every row on
  every instrument has `include=False`. The reviewer page would
  show nothing.
- **`assignments.reviewer_missing`** (error) — a reviewer has
  zero `include=True` rows across every instrument. They'd
  receive an invitation pointing at an empty surface.
- **`assignments.reviewer_missing_for_instrument`** (warning) —
  per-instrument variant: a reviewer has rows on some
  instruments but zero `include=True` on a specific one.
  Surfaces the per-instrument empty-page risk.
- **`assignments.instrument_empty`** (warning) — an instrument
  has zero materialised rows. Likely caused by an over-
  restrictive rule.

All four surface through the standard Validate page with
"Fix on Assignments" deep-link targeting the per-instrument
row.

## Worked example

A program coordinator runs a peer-review session: ten
reviewers, ten reviewees, three "team" tags. The coordinator
wants each reviewer to review the four people in their own
team **except themselves**, and a separate group instrument for
each team to evaluate the team's overall collaboration.

**Setup:**

- Reviewer + Reviewee CSVs imported with `tag_1` populated as
  the team name.
- Two instruments:

| Instrument | Link 1 | Link 2 | Link 3 | Self-review |
|---|---|---|---|---|
| Peer review | All (no filter) | reviewee.tag1 IS THE SAME AS reviewer.tag1 | Individual | Excluded via per-instrument toggle |
| Team retro | All | reviewee.tag1 IS THE SAME AS reviewer.tag1 | Group on reviewee.tag1 | N/A (group contains the reviewer; self-review toggle drops the group) |

**Generate** runs the engine:

- For **Peer review**: 10 × 10 universe → 10 × 4 surviving
  (each reviewer's team has 4 others on average; sizes vary)
  → 30-ish `Assignment` rows. Self-review rows (reviewer ==
  reviewee) materialise but their `include` is `True` until
  the operator clicks the per-instrument Self-review toggle on
  the Assignments page, which bulk-flips them to `False`.
- For **Team retro**: same surviving pairs, but
  `group_key` = team name. Rows still per-reviewee (10 rows
  for a 5-team session), but the reviewer surface collapses
  them into one card per team. Self-review groups (the team
  the reviewer belongs to) are dropped via the toggle.

After **Activate**, the reviewer logs in and sees:

- Peer review page: 4 row cards, one per teammate. Click any to
  fill in.
- Team retro page: 1 group card, identity reading the team name
  with up to 10 member names below.

## Open / deferred

- **Cross-instrument rule reuse.** No "share this Band 1 across
  instruments" affordance. Replicate-the-instrument substitutes.
- **QUOTA in Band 1.** The engine honours QUOTA rules, but
  Band 1 doesn't emit them. Use case (cap per reviewer load)
  hasn't surfaced as critical yet.
- **Per-instrument scheduled regenerate.** Generate fires
  manually only. A future scheduled regenerate after roster
  imports could land cleanly on the reconcile path.
- **Audit-log surface for self-review toggles.** The events
  are written; surfacing a per-instrument "self-review toggle
  history" timeline is not yet on the page.
- **Resurrecting the library tier.** The Wave 5 retirement of
  `operator_rule_sets` was scoped to a single-author use case.
  If shared rule evolution across sessions becomes a real ask,
  the per-instrument Band 1 design leaves a clean reintroduction
  path (a per-workspace library + a `library_origin_id`
  back-reference on `session_rule_sets`).
