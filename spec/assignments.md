# Assignments

**The rule engine + the Assignments operator page.**

An **Assignment** is a `(reviewer, reviewee, instrument)` triple
materialised in the `assignments` table, with an `include`
boolean controlling whether the reviewer actually sees the
reviewee on their per-instrument page. Assignments are not
authored row-by-row; they're **generated** by running a per-
instrument rule pass over the session's reviewer × reviewee
matrix and slotting one row per surviving pair (Individual) or
per (reviewer, group_key) (Group). **The rule engine
(`assignments.replace_assignments`) is the only path that creates
an `Assignment` row** — nothing hand-creates, uploads or edits one
into existence; a process that cannot place a row (e.g. rehydrate's
responses importer, `spec/rehydrate.md` §6.3) drops it rather than
fabricating one.

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

> **One rule per instrument, authored in one place.** Every rule
> lives on its instrument's Band 1: there is no operator-side
> RuleSet library and no standalone Rule Builder page, and an
> instrument with no rule at all evaluates against the synthetic
> Full Matrix. Superseded designs are kept as records at
> `spec/archive/rule_based_assignment.md` and in the fan-out half
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

Every instrument's rule passes through this one pipeline, and
Band 1 of the instrument card is its only operator-facing entry.

### Rule kinds

The internal `Rule` discriminated union supports four kinds.
Band 1 (the only authoring surface today) emits only `MATCH`
and `COMPOSITE`. The other two are honoured by the engine but
not surfaced in the UI.

| Kind | Purpose | Surfaced in UI? |
|---|---|---|
| `MATCH` | One predicate (`field operator operand`). | Yes — one per cell in Link 1 / 2's rule list. |
| `COMPOSITE` | Wraps a list of child rules with `AND` / `OR`. | Yes — one per Link in Band 1 (Link 1's Composite, Link 2's Composite). |
| `FILTER` | Domain-restriction rule. | No — Band 1 uses `MATCH` directly inside `COMPOSITE`. |
| `QUOTA` | Cap pairs per actor. | No. |

### Predicate vocabulary

A `MATCH` rule carries a `predicate` of `{field, operator, operand, case_sensitive}`.

**Field namespaces:**

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
- `NONE_OF` — the engine honours it; Band 1 never emits it.

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
filter rules exist, the Band 1 save path materializes no
`SessionRuleSet` row — the instrument keeps `rule_set_id=NULL`
and the engine substitutes the synthetic Full Matrix at evaluate
time.

**One control materializes a row without any Link rule**: turning
on the Link 3 self-review exclusion checkbox
(`spec/instruments.md` § *Self-review exclusion*), which needs
somewhere to store its flag. The row it creates carries
`rules_json=[]`, which the engine evaluates identically to the
synthetic Full Matrix — same empty rules, same `ALL_OF`, and the
seed the two differ on is read only inside the quota-rule loop an
empty rule set never enters. So the row changes no assignment.

## Where the rule lives

The only place to author a rule is **Band 1 of an
instrument card** — titled **"Instrument assignment rule"** for the operator
(the "Instrument" prefix disambiguates it from this Operations-row
Assignments page), with Links labelled *Who does the review* / *Who is being
reviewed* / *Unit of review* (see `spec/instruments.md` § Instrument
assignment rule). "Band 1" and the `link1`–`link3` ids remain the internal
names. The rule is per-instrument and per-session:

- Each instrument's Band 1 either lazily materialises one
  `SessionRuleSet` row (when any Link is in `filter` / `group`
  mode with rules) or leaves `Instrument.rule_set_id=NULL`
  (when every Link is `all` / `individual`).
- The materialised row is owned by the instrument: deleting the
  instrument leaves the row behind (FK `ON DELETE SET NULL`),
  but the operator's exposure to it is via Band 1 only.
- Renaming, "Save As", or sharing rules across instruments is
  not supported. Replicate-the-instrument is the substitute.

There is no scope `personal` / `library` / `seeded`
distinction — every row is per-session.

## Synthetic Full Matrix

When `Instrument.rule_set_id is NULL`, the engine substitutes a
synthetic schema:

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
default — `_create_band1_rule_set` sets
`exclude_self_reviews=False` — so the two paths are deliberately
indistinguishable from the generator's point of view.

## Self-review policy

**`excludeSelfReviews` is ALWAYS `False`.** The rule engine never
drops self-review pairs at the **desugar stage** — neither during
assignments generation nor during the Band 2 instrument-preview
sample pick. This is project-wide policy and is enforced in three
layers so it can't be silently re-enabled.

**The desugar stage, not self-review exclusion as such.** Since
19O Item 1, an operator *can* exclude self-reviews per instrument,
and the generator honors it — but **after** the engine's pair
fan-out, never inside it. The distinction is the whole policy: by
the time the fan-out is done, `_diff_one_instrument` already knows
whole-group membership, so a group-scoped instrument drops the
entire group rather than one `(R, R)` pair. The desugar stage
cannot know that, because it filters pairs before group
composition is computed.

The three layers below therefore still hold exactly as written;
they are what keeps the exclusion out of the desugar stage.

1. The `RuleSetOptions.excludeSelfReviews` Pydantic default is
   `False`.
2. `assignments._session_rule_set_to_schema` hard-codes
   `excludeSelfReviews=False` when wrapping a `SessionRuleSet`
   row into a schema — the row's `exclude_self_reviews` column is
   ignored, and this hardcode is what makes the engine ignore it.
   The column itself is operator-settable (config import today;
   the Link 3 checkbox from 19O.1 rung 2) and is no longer reset
   on each Band-1 save, so a `True` can persist in the row and in
   the by-instrument extract's *Self-review excluded* cell while
   the engine still ignores it.
3. `instruments._band1.find_sample_in_scope_reviewee` (the
   `/preview-sample` workhorse) constructs its schema with
   `excludeSelfReviews=False`. It honors the instrument's own
   `exclude_self_reviews` flag the same way the generator does —
   by filtering the engine's **output**, whole group at a time —
   so the Band 2 preview never shows a sample that Generate
   would not produce (`spec/instruments.md` § *Preview review
   instrument*).

### Suppressing self-reviews

Two supported affordances, answering different questions —
*don't generate them* and *don't count the ones generated*.

- **Exclude at the rule (Link 3 checkbox).** The **Self reviews**
  control in the Link 3 column, whose label follows the unit of
  review — see `spec/instruments.md` § *Self-review exclusion* for
  both spellings, which are stated there and deliberately not
  repeated here. It writes
  `SessionRuleSet.exclude_self_reviews`. Honored at
  the `pair_include` branch of `_diff_one_instrument`, **after**
  the fan-out: the pair is omitted from `new_pairs` entirely
  rather than written with `include=False`. On a group-scoped
  instrument this drops **every member row of the reviewer's
  group**, which is the behavior the desugar stage could not
  give. **Group membership is read from the roster, not from the
  surviving pairs** — a Link rule can filter the `(R, R)` pair out
  of the fan-out while leaving the reviewer's group-mates in it,
  and the group is still the reviewer's own. Takes effect **at the
  next Generate**, not on save.
  **Destructive on an already-generated instrument**: the dropped
  pair falls into `to_delete` and its saved `Response` rows go
  with it, counted by the reconcile dry-run's `responses_deleted`
  and confirmed on the Prepare card before anything is written.
  A reviewee whose identifier is not an email is never a
  self-review, so the flag cannot drop an anonymous reviewee's
  row.
- **Per-instrument Self-review toggle.** Self-review pairs *are*
  materialised; flip the toggle on the Assignments page to set
  `Assignment.include=False` on every `(R, R)` row in that
  instrument. The session-level `ReviewSession.self_reviews_active`
  (default True) seeds this on first generation. Reversible
  without a re-Generate, and it destroys nothing.

**Prefer the toggle when in doubt**: it is reversible in place and
keeps the rows inspectable. The rule is for the case where the
operator never wanted the rows at all.

**Formerly listed here and removed:** *"add a Link 2 rule like
`reviewee.email IS DIFFERENT FROM reviewer.email`"*. No operator
can author it — the Band 1 field picker offers only
`tag1`/`tag2`/`tag3`, and the general Rule Builder was retired with
the library tier. It was also pair-level, so on a group-scoped
instrument it would drop `(R, R)` and leave the rest of the group
mis-classified as an ordinary review. The Link 3 checkbox replaces
it.

Reasoning for keeping exclusion out of the desugar stage: dropping
self-pairs there (a) is invisible to the operator — the row doesn't
show up to be inspected or toggled, and (b) under-counted group
composition by one whenever the sample reviewer was themselves a
member of the group (symmetric reviewer/reviewee sessions). Both
are answered by honoring the flag after the fan-out instead: the
group is whole, and the Assignments page reads **"Excluded by
rule"** in the *Self review* cell rather than a bare `0` — *none
exist* and *none kept* being different facts.

Two attributes still drive whether self-review rows appear as
*active*:

1. **`SessionRuleSet.exclude_self_reviews`** (rule-set level).
   Operator-settable, default `False`: written by the Link 3
   checkbox, by session-config import, and carried by a session
   clone. The *engine* ignores it (layer 2 above), but the
   generator honors it after the fan-out, so a `True` means the
   instrument generates no self-review row at all. Also surfaces
   in the by-instrument extract's *Self-review excluded* cell.
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
`app/services/assignments/`; on individual-scoped
instruments it collapses to the per-row
`is_self_review(reviewer, reviewee)` test, and on group-
scoped instruments it applies the whole-group rule.

**Source of truth — `Assignment.is_self_review` column.**
The boolean column on the `assignments` table persists the
canonical classification for every row. **Regenerate is the only write
site** — no other path creates an `Assignment` row — and it calls
`assignments.recompute_self_review_classification` as part of
materialising each pass. Every edit trigger (reviewer email, reviewee
identifier or
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
rationale for consolidating on the column is recorded in
`guide/archive/self_review_consolidate.md`.

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
`app/services/assignments/` walks group_key membership rather
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
3. **No self-review exclusion *at this stage*.** Project-wide
   policy is `excludeSelfReviews=False` everywhere, so the engine
   never drops `(R, R)` pairs at the desugar stage. Exclusion, when
   an operator asks for it, happens **after** this pipeline — see
   the "Self-review policy" section above for why, and for the two
   supported suppression paths (the Link 3 checkbox + the
   per-instrument Self-review toggle).
4. **Apply QUOTA.** Currently inert — no Band-1 QUOTA emission.
5. **Materialise.**
   - Individual: one row per surviving pair.
   - Group: one row per pair, with `group_key` populated.
   - `include` = `True` for non-self pairs;
     `session.self_reviews_active` for self pairs.

The engine is pure (no DB writes); the materialise step is the
caller's responsibility. `app/services/assignments/` is the
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
3. **Assignments preview card** — the row-level table of
   materialised pairs, with a per-row Include checkbox. It carries
   **no `<h2>`** — a preview-table card does not take one, and this
   page's `<h2>` belongs to the status table above.

   The card opens with the **two-pane toolbar**
   (`.table-card-toolbar.is-split`) the other six table pages carry;
   `spec/setup_pages.md` § *The table toolbar* states the shape once.
   The left pane holds the column chips, the pager cluster
   and the preview-count line; the right pane holds the filter strip,
   in this order: **`Status:`, `Search by:`, the search box, `Clear`,
   `Search`** — the submit last, as `spec/setup_pages.md` § *The table
   toolbar* has it for the rosters.

   **There was an `Operator-actions card` here until 19P.5**, half
   width and flush right (`.grid-right` in a `bottom-grid`), carrying
   both the strip and the bulk Inactivate / Activate row. Rung 1
   moved the strip into the toolbar, rung 2 moved the actions into
   the row expander, and the card, its grid and the `.grid-right`
   rule went with them. **This page took the roster idiom last and
   is the only Operations page with selection**, which is why it gets
   both halves where Invitations and Responses get the toolbar alone.

   The three chip groups sit on one line where they fit. **This page
   labels each group, where the other six say `Show columns:` once** —
   `Show reviewers:` / `Show reviewees:` / `Show relationships:`,
   nine slots from three sources against one
   `rrw-assignment-col-visibility` key. A slot with nothing in it
   across the session's rosters renders neither chip nor column, and
   a group with all three empty renders no label either. In the
   half-width pane three groups often do not fit, so the row carries
   `.col-chip-row.is-grouped` and wraps **between** groups with the
   second line flush left rather than indented
   (`spec/ui_elements.md` §10). The rule
   and the primitive are in `spec/setup_pages.md`, "Preview tables
   (shared toggle pattern)"; pair-context presence is counted
   **active-only**, matching the rule engine, where the
   Relationships Setup page counts every row.

   The table sits in `.table-scroll`. With all nine tag slots
   populated it renders 14 columns — 1508px inside a 1360px card —
   so its overflow belongs inside the card rather than scrolling the
   whole page, the same wrapper Invitations and Responses use.

The page reuses the Workflow card chrome shared with Session
Home + other Operations-row pages.

### Per-instrument status table

Under the card's `<h2>`, a `.muted` line:

> Pairs are materialised from each instrument's rule and appear at
> Prepare.

The page's one non-obvious fact. Pairs are a **materialised
derivative**, so there is no add-or-remove control here and an
operator looking for one is looking on the wrong page — the change
they want is the instrument's rule. Asserted in
`tests/integration/test_page_guidance.py`.

Deliberately *not* a `.page-guidance` card: those are a Setup page
affordance for explaining a page's whole purpose, and one sentence
about this card's own table does not need the idiom.

Columns (left → right):

| Column | Meaning |
|---|---|
| Instrument | `block.instrument_label` — the operator-facing label from `instruments._instrument_label`: **`short_label`**, else the `Instrument_{session_seq}` fallback that nudges the operator to set one. The stored `name` is a pure internal handle and is **never** rendered (`spec/instruments.md`, the operator-identifier policy) — it is not part of the label chain, so a search or a label built from it would match a string no operator can see. The column's server-side sort key is the SQL form of the same rule (`assignments/_coverage.py::_instrument_label_sql`), pinned against the Python one by `tests/integration/test_instrument_session_seq.py` after 19Q Item 6 found them drifted: the Python form moved to `session_seq` and the SQL stayed on `id`, so the page sorted by a string it no longer displayed. |
| Type | "Individual" or "Group" (driven by `Instrument.group_kind`). |
| Generated | Pill carrying the row count. "Not generated yet" when zero. A `stale` pill rides alongside when the rows have fallen out of step — see "Staleness". |
| Groups | Group count (distinct `(reviewer, group_key)` over the rows) for group instruments; "—" for individual. |
| Self review | Pill carrying the total self-review row count, plus an inline checkbox that bulk-flips `Assignment.include` on every self-review row in this instrument. Pill colour is `pill-info` (blue) when all are active, `pill-warning` (yellow) when not. The checkbox renders only when `self_review_total > 0`; on a session with no roster overlaps it doesn't render. |
| Included | Pill carrying the count of `include=True` rows. "—" before Generate. |
| Show | Per-instrument filter checkbox — client-side DOM toggle that hides / shows the instrument's pairs in the preview table below. Default: checked when any row materialised. |
| (action) | "Edit on Instruments page" deep-link to the instrument's card. |

**There is no Rule column**, and re-adding one buys nothing: the
rule lives on Band 1, and with the implicit Full Matrix default a
rule name here names either Band 1 or nothing.

### Self-review toggle wiring

The checkbox is bound to a per-instrument form
`POST /sessions/{sid}/assignments/{iid}/self-reviews/active`
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

Whenever the session is **not editable** — `ready`, `expired` or
`archived` — the checkbox disables, matching the
`_require_editable` its route enforces. Gating the template on
`is_ready` alone instead leaves the box live on `expired` and
`archived`, where the route answers 409. Its title
names the way out that state actually has: *"Revert to draft to
change self-review inclusion."* on `ready` and `expired`, which
`revert_session_to_draft` accepts, and *"Unarchive this session
…"* on `archived`, which it refuses. `spec/lifecycle.md` §2.5
and §5 carry the state machine.

### The row expander

**The selection's controls are a row injected into the table** beneath
the selected row, not a card beside it — the roster idiom
(`spec/setup_pages.md` § *The row expander*), taken here at 19P.5
rung 2. It carries the selected count — `N of M selected`, as the
rosters render it and not the card's bare `N selected` — and the
status button the selection makes actionable.

**M is the *visible* rows, not the rendered window.** The rosters'
contract says rendered window and is right for them, because they
filter server-side. Here `rows()` filters `allRows()` to
`style.display !== "none"`, so the `Show` checkboxes move M as well as
what can be ticked — which is the whole reason this page needs its own
statement of the count.

Three things differ from the rosters, and each follows from what this
page is:

- **It offers only the actionable status button** — `Inactivate` when
  every selected pair is included, `Activate` when every one is
  excluded, both when the selection is mixed. The retired card
  rendered both always, so a selection of entirely-included rows
  carried an `Activate` that would no-op on every row. **A behaviour
  change, not a relocation**, and the same one 19P.1 made on
  Reviewers.
- **No `Edit` and no `Delete`.** Assignments are not edited row by
  row and not deleted at all — the operator changes which pairs exist
  by changing the rule or the rosters and regenerating (§ *Reconcile +
  regenerate*). So there is no two-stage delete gate here, and the
  count is the only other thing in the row.
- **The funnel counts visible rows, not selected ones.** This is the
  only page with a *client-side* filter: the status table's
  per-instrument `Show` checkboxes hide rows with `display: none`,
  which breaks the rosters' unstated assumption that a selectable row
  is a visible one. The panel anchors after the last **visible**
  selected row and its `colSpan` is recounted on every chip toggle;
  both were defects when the idiom was first ported. The page's
  sortable headers need the same care — `_rrwApplySort` slices
  `tbody.children` with the injected panel among them, so the panel is
  removed before a sort rather than sorted null-last to the foot of
  the table.

The count renders as **bare text, not a pill**: the expander's
background and the info-pill background resolve to the same primitive
in both themes, so a pill inside the expander is invisible.

### The page's lifecycle surface

The Assignments page splits the way the roster Setup pages do
(`spec/setup_pages.md`, and `spec/lifecycle.md` §5):

- **The selection-driven half follows `is_editable`** — row
  checkboxes, the select-all header cell, the hidden
  `assignments-bulk-form` they post to, the selected count,
  `Inactivate` / `Activate` and the wiring script render only on
  `draft` and `validated`, which is what all five mutating routes
  enforce.
- **The read-only half renders in every state** — the `Search by:`
  select, the search box, `Clear` and the `Search` button. The count
  itself is not in the strip — see "The preview-count line" below.
  Reading a finished session's assignments is legitimate, and
  mid-session is exactly when an operator checks who is assigned to
  whom.

**The split is per-half, not per-card — and since 19P.5 the two
halves are not in one card at all.** The strip is the table
toolbar's right pane and the selection controls are in the row
expander, which is a stronger form of the same rule: a surface that
renders in every state and a surface that appears only on a ticked
row cannot share a predicate, because they no longer share an
element. The rule is kept because the reason outlives the card —
gating one container on one predicate disagreed with the mutating
routes on **three of the five lifecycle states**, in both
directions: on `not is_ready`, `expired` and `archived` offered live
controls the routes refuse, and `ready` lost the search altogether.

**No lock card here.** The four roster pages have none on
`expired` / `archived` (`spec/lifecycle.md` §5) while Instruments
carries one; a third variant would widen that inconsistency
rather than close it.

### Search matching

`?q=` filters the pairs; `?search_by=` scopes it. The matching rule
is the one `spec/setup_pages.md` "Search matching and suggestions"
settles for the roster pages, applied to a pair:

| Column | Rule |
|---|---|
| Reviewer `name` / `email`, Reviewee `name` / `email_or_identifier` | substring, case-insensitive |
| `tag_1..3` on either side | **whole value**, case- and surrounding-whitespace-insensitive |

`search_by` is `all` (either side), `reviewer` or `reviewee`, and it
scopes a side's tags along with its name and handle — **tags need no
control of their own here**, because they belong to the reviewer and
the reviewee individually rather than to the pair. (Relationships'
pair-context tags are the case that has no side to attribute them
to, and `spec/setup_pages.md` records why they match both.)

Scoping is **per side, not per person**: on a self-review row the
reviewer and reviewee are the same person, so that person's tag
matches under `reviewer` *and* under `reviewee`.

**The rule is expressed twice, deliberately.** The roster pages run
it in Python over a loaded list
(`app/web/views/_filters.py::_matches_row`); this page runs it in
SQL, because `count_pairs` and the `PAIR_PREVIEW_LIMIT` cap both run
in the query and the preview-count line keeps its meaning — `N` is
the pairs matching the term, `M` every pair in the session.
`tests/integration/test_assignments_search_tags.py` holds one table
of cases against both paths so they cannot drift apart silently.
Its known limit: Python `str.casefold` and SQL `lower` agree on
ASCII but not on every codepoint.

**The typeahead** offers both sides'
`"Name (handle)"` labels in **one** list, sorted case-insensitively
and capped at `REVIEWERS_DATALIST_CAP`. One list rather than one per
side because `Search by:` can change without a reload; the picked
handle resolves against whichever side the scope allows anyway.

**Tag values are not offered**, unlike the roster pages' list. A tag
identifies too many pairs to partition by here, where on a roster of
people it partitions usefully. Tag *matching*, above, is unaffected.

**A picked label matches the handle by equality**, and this is
load-bearing rather than a refinement: the term submitted is the
whole label, and `%Ana Lim (ana@example.edu)%` is a substring of no
name and no email — so without the rule a picked suggestion returns
**nothing**. Equality is also what separates `ana@example.edu` from
`ana2@example.edu`, which a name substring cannot.

Detection is `views.assignments_picked_handles`, resolved **per
side** against the **uncapped** label sets, so a label past the
display cap that the operator types from memory is still recognised.
The two sides carry different rules, both inherited from the roster
pages rather than newly invented: a **reviewer** tail must contain
`@` (their handle is always an email, and the guard also stops a tag
like `Group (B)` reading as a pick), a **reviewee** tail need not
(`email_or_identifier` may be an anonymous ID). A pick naming a side
the scope excludes matches nothing, rather than falling back to a
substring search that would ignore the scope.

**Not partitioned by instrument.** A session carries a handful of
distinct instruments against a roster of hundreds, so an instrument
partition divides the list barely at all. The per-instrument `Show` checkboxes in the status table remain
the instrument-side filter — client-side, over the rendered window.

### Status filter

`?status=` filters the pairs by **`Assignment.include`** — the
boolean the row expander's **Inactivate** / **Activate** buttons
flip, and which the Include column already shows as a
`no` pill. Without the filter an operator can inactivate in bulk
and then have no way to list the result back, which is what it is
for.

| value | matches |
|---|---|
| `all` (and anything unrecognised) | every pair |
| `active` | `include IS true` |
| `inactive` | `include IS false` |

Options come from `views.ASSIGNMENTS_STATUS_OPTIONS`; the select is
the roster pages' shape (`spec/setup_pages.md`).

**It composes with the search into the preview-count line** — `N` is
the pairs matching *both* filters, `M` every pair in the session.
That is the roster pages' own reading of the same sentence
(`views/_filters.py`: *"Filters compose: status + search"*).

**The column chips ignore both filters.** `col_data_sample` is built
from an unfiltered `list_pairs` so narrowing the view never flips a
chip's enabled state. It is aliased to the filtered sample only when
*neither* filter is active, purely to skip a second query.

The value is normalised at the route before it reaches the context,
because it also rides the bulk form's hidden `filter_status` field
and returns on the next request — an unrecognised value would
otherwise persist there. The route parameter is named `filter_status`
with a `status` alias: `status` alone shadows the module-level
`status` import (`status.HTTP_200_OK`).

### The preview-count line

**One count, in one place.** The page's counts are the single
sentence the seven preview pages share, rendered by
`operator/partials/_preview_count_line.html` in
`.table-showing-hint` — the roster pages' class, and not
`.form-help`, which sets `--fs-small` and would render this page's
line a size smaller than the identical sentence on a roster. Since
19P.5 rung 1 it renders **inside the toolbar's left pane**, with the
chips and the pager, rather than below the toolbar.

The noun is **`assignments`**, never `unique pairs`. The branches and
the rule behind them are in `spec/setup_pages.md`, "Preview tables
(shared toggle pattern)" — this page is capped by
`PAIR_PREVIEW_LIMIT` (200, unlifted by a filter).

**Where a pager renders, the line says nothing about position**,
because the ranges already state it. The filtered branches read
`Showing 2 assignments.` and, when the cap truncates a filtered view,
`Showing 500 of 900 assignments, 400 more not shown.` A count of one
takes the singular.

**The page is paged**: `?offset=` cuts a 200-row page out of the whole
matching set, **clamped rather than rejected**
(`views.clamp_offset`), with the `.table-pager-cluster`
(`spec/ui_elements.md` §10) above *and* below the table, and
suppressed entirely while a filter is active — the operator's own
partition wins, and the count line speaks for that view instead. Both
affordances read the same filter flag, so they cannot disagree about
which mode the page is in.

### Sorting the pair list

**The operator's sort is applied by the query, not to its result.**
Sorting a fetched window in Python (`views.apply_cookie_sort`, which
the roster pages use) would sort page 2 *within* page 2 — invisible
on an unpaged table, a lie on a paged one. So every sort key
translates to `ORDER BY` in `assignments.list_pairs`, including
`pair_tag_*`, which reaches the pair's tags through an outer join to
`relationships` gated on `status = 'active'` — the same condition the
rule engine applies.

**The translation preserves `apply_cookie_sort`'s semantics exactly**,
because the alternative is every sorted table reshuffling on the day
it lands:

| Rule | In SQL |
|---|---|
| An empty string is not a value | `NULLIF(col, '')` |
| Absent sorts **last**, in both directions | `NULLS LAST` on every clause |
| Text compares by code point | explicit `COLLATE "C"` on Postgres; SQLite's default BINARY already does |
| Ties fall through, then to a stable order | the sort keys, then `(reviewer_id, reviewee_id, instrument_id)` |

The third rule is the one with teeth. On Postgres 16, under a
locale-aware collation seven names order
`_edge | alpha | ana lim | Ana Lim | Bravo | charlie | Delta`, and
under `C` they order `Ana Lim | Bravo | Delta | _edge | alpha |
ana lim | charlie` — the second being what this app renders. Azure
Postgres commonly carries a locale-aware collation,
so the guard is load-bearing in production and invisible on SQLite.

The fourth rule is what makes paging safe: without a **total** order
two adjacent pages can show the same row or neither.

**A search matching nothing renders no count line** — the shared
rule, not a quirk of this page (`spec/setup_pages.md`, "Preview
tables"). The line sits inside the preview card's `pair_sample`
gate, so there is no table for it to caption, and `No assignments
match the search.` owns that state alone. (Were the helper called in
that state it would return `Showing 0 assignments.`; the gate means
it is not.)

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

A row with `include=False` renders its Include cell as a
warning-coloured `no` pill (`.pill-empty`); the row itself is **not**
dimmed or otherwise restyled. The (select) column
enables bulk-set Include via a checkbox column header + a
per-row checkbox; the **row expander** injected beneath the
selection carries the **`Inactivate`** / **`Activate`** buttons the
selection drives — only what is actionable for it, so one on a
single-status selection and both on a mixed one. § *The row expander*
above states the rule.

#### Bulk-set Include

Two routes, `POST /assignments/bulk-inactivate` and
`POST /assignments/bulk-activate`, both over the service helper
`assignments.bulk_set_assignment_include`. The buttons are
**`Inactivate`** / **`Activate`**; `spec/operator_button_audit.md`
is the catalogue for that copy. Lifecycle-aware (the same
`_require_editable` guard as the self-review toggle — `draft` or
`validated`).

## Reconcile + regenerate

Generate never wholesale-replaces an instrument's rows: it
**diffs and reconciles**, so responses on pairs that survive the
re-run survive with them. `spec/reconciling_regeneration.md`
carries the algorithm and the reasons it may not be simplified
back.

When Generate runs — on its own, or inside the Workflow card's
Prepare step — then for each instrument:

1. Run the engine over the current rule + roster.
2. Compute the diff against existing `Assignment` rows:
   - **To-insert.** New pairs the engine produced.
   - **To-delete.** Existing pairs no longer surviving the
     rule. **Their responses are deleted too** — this is the
     destructive part. The Workflow card's **Prepare session**
     button detours through a `prepare_confirm` banner naming
     both counts first, so the operator acknowledges the loss
     before it happens (`spec/workflow_card.md`).
   - **To-keep.** Pairs surviving both passes. Their
     responses survive untouched, but their
     `Assignment.include` is **recomputed, not preserved**.
     `_generate.py:345-347` sets the expected value to
     `self_reviews_active` for a self-review pair and `True`
     for every other pair, and `:462-466` writes it back
     whenever it differs from the stored one — so an
     operator's manual Inactivate on a non-self pair is reset
     to `True` on the next Generate. That reset is the
     deliberate state of the round trip today, not an
     oversight: assignment-row status carries through no
     export and no clone, and restoring it is future work
     (`guide/archive/segment_19N_generated_assignments.md` Item 1,
     Semantics 6; `spec/roundtrip_coverage.md` records the
     gap).

The diff is bit-stable (the engine's deterministic seed
guarantees the same pass produces the same set), so re-running
Generate without changing anything is a no-op.

### Staleness

An instrument is **stale** when it has materialised rows and a
regeneration would insert or delete at least one pair — the pinned rule
changed, or the rosters or relationships moved after Generate.

**Two surfaces carry it:** a `stale` pill beside the instrument's
Generated count on this page, and an `instruments.stale_generated`
warning on Validate naming each affected instrument. There is no
page-level badge, and no Next Action affordance — the pre-Validate
Generate resolver that once consumed the session-wide aggregate is not
wired to any route.

**The verdict is the engine's own diff**, not a comparison of counts.
Two properties follow, and both are the contract rather than an
implementation note:

- **A change that swaps one pair for another is stale**, even though the
  totals match. A count comparison reports a session fresh while every
  row names a reviewer the rule no longer selects.
- **Unpinned instruments go stale too.** A NULL `rule_set_id` is the Full
  Matrix default at the diff site, so an unpinned instrument generates
  like any other and can fall out of step like any other.

**A never-generated instrument is not stale.** A run would insert its
whole fan-out, so treating that as staleness lights up every fresh
session, and a badge that is always on is one the operator learns to
ignore. That case belongs to the Workflow card's Generate step and the
`assignments.*` empty rules. The same boundary means an instrument whose
roster was emptied reads as never-generated rather than stale: deleting a
roster entry cascades its rows away, and the empty rules carry it.

Regeneration is always the operator's own act — nothing auto-regenerates,
and the Generate button (or Prepare session, which runs Generate
transitively) is the only path. **Staleness is a prompt, never a
blocker:** it is a warning, so it does not gate activation.

### `reconcile_impact` dry-run

Used by the **Prepare session** button to show the
`prepare_confirm` banner before any destructive write happens.
Returns the `new` / `deleted` / `kept` / `responses_deleted` counts
a real run would cause, **aggregated across the session** — the banner
asks one question and needs one answer. A per-instrument preview reads
`staleness_by_instrument` instead, which is that shape; the two share
the engine's diff, so they cannot disagree.
The Workflow card renders `responses_deleted` and `deleted_pairs`
from it and gates the re-POST on
`acknowledge_response_loss=true`.

## Validation surfaces

Registered rules in `app/services/validation.py:REGISTERED_RULES`
that fire on this page's domain:

- **`assignments.no_included_pairs`** (warning) — every row on
  every instrument has `include=False`. The reviewer page would
  show nothing.
- **`assignments.reviewer_missing`** (warning) — a reviewer has
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
- **A cross-session rule library.** Dropped as out of scope for a
  single-author use case. If shared rule evolution across sessions
  becomes a real ask, the per-instrument Band 1 design leaves a
  clean reintroduction path (a per-workspace library + a
  `library_origin_id` back-reference on `session_rule_sets`).
