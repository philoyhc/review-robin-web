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
2. `assignments._session_rule_set_to_schema` hard-codes
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
`app/services/assignments/`; on individual-scoped
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
3. **Operator-actions card** — the search / status filter and the
   selection-driven bulk Inactivate / Activate row. Half width,
   flush right (`.grid-right` in a `bottom-grid`).
4. **Assignments preview card** — the row-level table of
   materialised pairs, with a per-row Include checkbox. It carries
   **no `<h2>`**: it was the only preview-table card in the app with
   one, and `Assignments preview` retired in Segment 19I Item 12.

   Above the rows sit the **`Show columns:` chips**, all three
   groups on one line — `Show reviewers:` / `Show reviewees:` /
   `Show relationships:`, nine slots from three sources against one
   `rrw-assignment-col-visibility` key. A slot with nothing in it
   across the session's rosters renders neither chip nor column, and
   a group with all three empty renders no label either. The rule
   and the primitive are in `spec/setup_pages.md`, "Preview tables
   (shared toggle pattern)"; pair-context presence is counted
   **active-only**, matching the rule engine, where the
   Relationships Setup page counts every row.

   The table sits in `.table-scroll`. With all nine tag slots
   populated it renders 14 columns — measured at 1508px inside a
   1360px card — so its overflow belongs inside the card rather than
   scrolling the whole page (Segment 19I Item 12; the same wrapper
   Item 11 gave Invitations and Responses).

The page reuses the Workflow card chrome shared with Session
Home + other Operations-row pages.

### Per-instrument status table

Under the card's `<h2>`, a `.muted` line (Segment 19E):

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
| Instrument | `block.instrument_label` — the operator-facing label from `instruments._instrument_label`: **`short_label`**, else the `Instrument_{id}` fallback that nudges the operator to set one. The stored `name` is a pure internal handle and is **never** rendered (`spec/instruments.md` "Identifiers"). Corrected 2026-09-09 — this read "Short label or full name", and `name` has not participated in the label chain for some time. |
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

Whenever the session is **not editable** — `ready`, `expired` or
`archived` — the checkbox disables, matching the
`_require_editable` its route already enforced (Segment 19I Item
8; it was `is_ready` alone until then, so the box was live on
`expired` and `archived` where the route answered 409). Its title
names the way out that state actually has: *"Revert to draft to
change self-review inclusion."* on `ready` and `expired`, which
`revert_session_to_draft` accepts, and *"Unarchive this session
…"* on `archived`, which it refuses. `spec/lifecycle.md` §2.5
and §5 carry the state machine.

### The page's lifecycle surface (Segment 19I Item 8)

The Assignments page splits the way the roster Setup pages do
(`spec/setup_pages.md`, and `spec/lifecycle.md` §5):

- **The selection-driven half follows `is_editable`** — row
  checkboxes, the select-all header cell, the hidden
  `assignments-bulk-form` they post to, the selected-count pill,
  `Inactivate` / `Activate` and the wiring script render only on
  `draft` and `validated`, which is what all five mutating routes
  enforce.
- **The read-only half renders in every state** — the `Search by:`
  select, the search box, `Clear` and the `Search` button. The count
  itself left this card in Segment 19I Item 10 — see "The
  preview-count line" below. Reading a finished session's
  assignments is legitimate, and mid-session is exactly when an
  operator checks who is assigned to whom.

Before Item 8 the template gated the whole operator-actions card
on `not is_ready`, which disagreed with those routes on **three of
five** states in both directions: `expired` and `archived` offered
live controls the routes refuse, and `ready` lost the search
altogether.

**No lock card here.** The four roster pages still have none on
`expired` / `archived` (`spec/lifecycle.md` §5) while Instruments
gained one in Item 6; a third variant would widen that
inconsistency rather than close it.

### Search matching (Segment 19I Item 7)

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

The tag columns were invisible to this search until Item 7 — a tag
an operator could filter by on the roster pages returned nothing
here.

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

**The typeahead** (Segment 19I Item 9) offers both sides'
`"Name (handle)"` labels in **one** list, sorted case-insensitively
and capped at `REVIEWERS_DATALIST_CAP`. One list rather than one per
side because `Search by:` can change without a reload; the picked
handle resolves against whichever side the scope allows anyway.

**Tag values are not offered**, unlike the roster pages' list. A tag
identifies too many pairs to partition by here, where on a roster of
people it partitions usefully (author's measurement against a large
mock roster, 2026-09-09). Tag *matching*, above, is unaffected.

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

**Not partitioned by instrument.** Raised and set aside 2026-09-09:
a session carries a handful of distinct instruments against a roster
of hundreds, so an instrument partition divides the list barely at
all. The per-instrument `Show` checkboxes in the status table remain
the instrument-side filter — client-side, over the rendered window.

### Status filter (Segment 19I Item 9)

`?status=` filters the pairs by **`Assignment.include`** — the
boolean the operator-actions card's own **Inactivate** / **Activate**
buttons flip, and which the Include column already shows as a
`no` pill. It was visible and unfilterable until Item 9, so an
operator could inactivate in bulk and have no way to list the
result back.

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

### The preview-count line (Segment 19I Item 10)

Until Item 10 this page reported its counts in **three** places: a
`Showing {matching} of {total}.` span flush right in the
operator-actions row, a `Showing first N of M unique pairs.` line
top-left of the preview card in `.form-help`, and a
`…and X more not shown.` line below the table. All three collapse
into the one sentence the seven preview pages share, rendered by
`operator/partials/_preview_count_line.html` in
`.table-showing-hint` — the roster pages' class. `.form-help` sets
`--fs-small`, which is why this page's line used to render a size
smaller than the identical sentence on the rosters.

The noun is **`assignments`**; `unique pairs` is retired. The
branches and the rule behind them are in `spec/setup_pages.md`,
"Preview tables (shared toggle pattern)" — this page is capped by
`PAIR_PREVIEW_LIMIT` (200, unlifted by a filter).

**19J.5 reshaped the sentence.** Where a pager renders the line says
nothing, because the ranges already state the position; the filtered
branches read `Showing 2 assignments.` and, when the cap truncates a
filtered view, `Showing 500 of 900 assignments, 400 more not shown.`
A count of one takes the singular. *This page is not paged yet* — rung
4 wires it, once the sort question below is settled — so it still
renders the pre-19J.5 unfiltered notice (`Showing first 200 of 10,000
assignments; 9,800 more not shown.`), which is true here and nowhere
else, and its pager strip renders inert until then.

**A search matching nothing renders no count line** — the shared
rule, not a quirk of this page (`spec/setup_pages.md`, "Preview
tables"). The line sits inside the preview card's `pair_sample`
gate, so there is no table for it to caption, and `No assignments
match the search.` owns that state alone. Before Item 10 a
`Showing 0 of 1.` also rendered in the filter row, which is what
changed here. (Were the helper called in that state now it would
return `Showing 0 assignments.`; the gate means it is not.)

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
warning-coloured `no` pill (`.pill-empty`); the row itself is not
dimmed or otherwise restyled. **Corrected 2026-09-09 (19I.9)** —
this line previously claimed the whole row dimmed, which no
template or stylesheet has ever implemented. The (select) column
enables bulk-set Include via a checkbox column header + a
per-row checkbox; the operator-actions card carries the
**`Inactivate`** / **`Activate`** buttons the selection drives.

#### Bulk-set Include

Two routes, `POST /assignments/bulk-inactivate` and
`POST /assignments/bulk-activate`, both over the service helper
`assignments.bulk_set_assignment_include`. **Corrected 2026-09-09**
(Segment 19I Item 8): this section named a single
`POST /assignments/include` taking `include=true|false`, and
buttons labelled `Include selected` / `Exclude selected`. Neither
the route nor those labels exists anywhere in the app — only the
helper name was right. `spec/operator_button_audit.md` has carried
the correct labels throughout. Lifecycle-aware
(the same `_require_editable` guard as the self-review toggle —
`draft` or `validated`).

## Reconcile + regenerate

> **Background.** The pre-Wave-5 "Generate assignments" path
> wholesale-replaced an instrument's rows on every re-run,
> deleting saved responses. Segment 13D PRs #1065 → #1069 (also
> documented in `spec/reconciling_regeneration.md`,
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
