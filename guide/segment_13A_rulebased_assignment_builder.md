# Segment 13A — Advanced (RuleBased) assignment mode

> **Renamed 2026-05-07** from `segment_13_rulebased_assignment_builder_plan.md`.
> Segment 13 split into three sibling segments:
> - **13A** (this file) — the rule-builder work: real `RuleBased`
>   rule menu replaces the placeholder card on
>   `/operator/sessions/{id}/assignments`.
> - **13B** — sort by reviewee. Reviewer-surface sort UX (operator
>   default sort + reviewer live override). Functional spec at
>   `spec/sort_by_reviewee.md`; plan at
>   `guide/segment_13B_sort_by_reviewee.md`.
> - **13C** — enhanced instruments. Group-scoped instruments
>   (per-instrument flavour where one answer covers a group of
>   reviewees) + a "Duplicate instrument" action-row button.
>   Functional spec at `spec/enhanced_instruments.md`; plan at
>   `guide/segment_13C_enhanced_instrument.md`.
>
> The three are independent and can ship in any order. Together
> they cover the original Segment 13 framing ("rule-based
> assignment builder + sort UX") plus the group-scoped enhancement
> that surfaced later.

> **Plan refreshed 2026-05-07** against [`spec/rule_based_assignment.md`](../spec/rule_based_assignment.md)
> — the canonical functional spec for Advanced mode. This plan
> handles sequencing, DB shape, audit wiring, and PR slicing; the
> spec owns the user-visible model (predicate vocabulary, combinator
> semantics, quota rules, library, seeds, validation rules). Read
> the spec first; this plan layers on top of it.

The Setup → Assignments page already ships **Full Matrix** and
**Manual upload** as fully-working modes, with self-review exclusion
covered as a checkbox on each. Segment 13A adds the third mode —
**Advanced**, also called **Rule Based** in the UI — replacing the
disabled placeholder card on `/operator/sessions/{id}/assignments`
with a real RuleSet-driven generator backed by a saveable Personal-
scope library. The standalone Full Matrix card retires at the end of
13A: its job is taken over by the seeded `Full Matrix` RuleSet, which
is byte-equivalent on output. Manual upload is unchanged.

## Status

Planning. Sized as **8 PRs** in dependency order:

1. **PR 1 — Schema.** RuleSet + RuleSetRevision tables, Pydantic
   schemas mirroring the JSON rule tree, migration. No engine, no UI.
2. **PR 2 — Engine.** Pure-Python evaluator (predicates, combinators,
   quotas, deterministic ordering). No DB, no UI; unit tests on
   synthetic populations. Does not yet wire to `replace_assignments`.
3. **PR 3 — Seeded RuleSets.** Install the six seeds spelt out in
   the spec (Full Matrix, Intra-group, Cross-group, Same-group-
   different-role, Three-per-reviewee, Lead-led). Read-only marker;
   round-trip tests through PR 2's engine on canonical fixtures.
4. **PR 4 — Rule Based card (seeds-only).** Replace the placeholder
   card with a real card carrying a RuleSet selector, an
   "Exclude self-review" checkbox, and a Generate button. Wired to
   the existing `replace_assignments(...)` writer. First user-
   visible PR; library limited to seeds.
5. **PR 5 — Editor child page + Save / Save As (Personal scope).**
   Adds a child page at
   `/operator/sessions/{id}/assignments/rule-based/edit/{rule_set_id}`
   reachable from a "Build / Edit rules" button on the card. Owns the
   metadata strip, combinator selector, rule list, predicate editor,
   and quota editor. Save / Save As creates Personal-scope RuleSets
   (first revision). The card's selector now lists seeds + Personal.
6. **PR 6 — Edit / Rename / Delete + revisioning.** Edit existing
   Personal RuleSets in place (each Save creates a new revision),
   rename, soft-delete. Past `assignments.generated` audit refs stay
   resolvable.
7. **PR 7 — Live preview panel.** Distribution stats per reviewer /
   per reviewee, sampled pair list, warnings. Reuses the engine from
   PR 2; runs server-side on each editor save / rule toggle.
8. **PR 8 — Retire standalone Full Matrix card.** Removes the Full
   Matrix card from the assignments page. The seeded `Full Matrix`
   RuleSet (PR 3) covers the same case from inside the Rule Based
   card. Retains the audit-event family (`assignments.generated`
   with `mode='full_matrix'`) for backward-compatibility — only the
   UI surface goes; the writer is unchanged.

PRs 4-7 each gain user-visible value on top of the previous; PR 5 is
the biggest and may need to split into 5a (editor scaffolding,
Save As of unchanged seed copy) and 5b (predicate + quota editor) if
scope balloons. PRs 1-3 are infrastructure-only with no operator UI.
PR 8 is intentionally the last PR — by the time it lands, the Rule
Based path has been live and exercised through PRs 4-7.

**Export / Import is deferred to Segment 12A** as a separate PR
(see "Out of scope" below). 12A executes after 13A in the workplan;
13A ships without RuleSet portability and 12A picks it up alongside
the rest of its CSV / JSON I/O work.

## Relationship to existing assignment modes

| Mode | UI | Status before 13A | After 13A |
|---|---|---|---|
| Full Matrix | Standalone card on Setup → Assignments, with `Exclude self-review` checkbox | Shipped | **Retired (PR 8)** — same behaviour available as the seeded `Full Matrix` RuleSet inside the Rule Based card |
| Manual upload | Standalone card on Setup → Assignments, CSV upload + `Exclude self-review` checkbox | Shipped | Unchanged |
| **Advanced (Rule Based)** | **Card on Setup → Assignments, currently a `placeholder_card` stub** | **Placeholder** | **Functional — this segment** |

Advanced mode is **conceptually a superset** of Full Matrix (every
Full Matrix output is reproducible by an empty-rule RuleSet with
`excludeSelfReviews=true` — that's exactly what the seeded
`Full Matrix` RuleSet is). PR 8 leans on that equivalence to retire
the standalone card without losing any operator-facing behaviour.

The `AssignmentMode` enum at `app/schemas/assignments.py:8-11`
already declares `rule_based`; PR 4 is the first PR to use it.
After PR 8, `full_matrix` mode persists in the audit log (it's the
mode the seeded RuleSet's runs are recorded under) but no longer
has its own UI surface.

## Card design (PR 4 surface, evolved through PR 5)

The Rule Based card on `/operator/sessions/{id}/assignments` has the
following affordances after PR 5. PR 4 ships everything except the
"Build / Edit rules" button.

```
┌─ Rule Based Assignment ────────────────────────┐
│                                                 │
│  RuleSet:  [▼ Intra-group peer review        ]  │
│            Reviewer and reviewee share tag1.    │
│                                                 │
│  ☑ Exclude self-review                          │
│    (when a reviewer's email matches a           │
│     reviewee's identifier)                      │
│                                                 │
│  [ Build / Edit rules… ]      [ Generate ]      │
│                                                 │
│  Last generated: 47 assignments • 3 minutes ago │
│                                                 │
└─────────────────────────────────────────────────┘
```

Element-by-element:

- **RuleSet selector.** Dropdown listing visible RuleSets, grouped:
  - Group 1: **Seeds** (read-only, system-provided — six entries
    from PR 3).
  - Group 2: **Personal** (this user's saved RuleSets, ordered by
    most-recently-updated; lands in PR 5 onward — empty until then).
  - The selector renders each entry as `{name}` with the one-line
    `description` shown below the selector when an entry is picked
    (mirrors the seed `description` that's stored on
    `rule_set_revisions.rules_json` metadata, populated from
    `seeds.py` for seeds and from the editor for Personal).
  - Default selection: the seeded `Intra-group peer review`
    (first entry in alphabetical-within-group order across the
    seeds).

- **Exclude self-review checkbox.** A card-level checkbox that
  reads `rule_set.options.excludeSelfReviews` from the currently-
  selected RuleSet on first render and lets the operator override
  for this Generate without saving back to the RuleSet. Tooltip:
  "When checked, pairs where the reviewer's email matches the
  reviewee's identifier are dropped before the rules run.
  Overrides this RuleSet's saved setting for this Generate only;
  edit the RuleSet to change the saved default." The audit context
  records the actual value applied (in
  `assignments.generated.context.exclude_self_reviews`) plus the
  RuleSet revision id, so the audit is unambiguous about what ran.

- **"Build / Edit rules" button.** Lands in PR 5. Opens the editor
  child page at
  `/operator/sessions/{id}/assignments/rule-based/edit/{rule_set_id}`
  for the currently-selected RuleSet. When a seed is selected, the
  editor opens read-only with a Save As affordance (you can clone
  the seed and modify the clone). When a Personal RuleSet is
  selected, the editor opens for in-place editing (PR 6 onward) or
  Save As (PR 5).

  A `+ New blank RuleSet` entry at the top of the selector opens
  the editor with no RuleSet pre-loaded; Save As is required.

- **Generate button.** POSTs to
  `/operator/sessions/{id}/assignments/rule-based/generate` with
  `rule_set_id` and the checkbox value. Runs the engine, calls
  `replace_assignments(...)`, and 303s back to the assignments page
  with a banner.

- **Last generated summary.** Inline passive line below the buttons,
  rendered when an `assignments.generated` audit row with
  `mode='rule_based'` exists for this session: shows the pair count
  and a relative timestamp. Click links to the Manage Assignments
  page. Empty when no generation has happened yet.

The card stays interactive in `draft` and `validated` states. On
`ready`, the existing yellow lock card pattern applies — Generate
is disabled with the standard explanation; the selector remains
browsable for inspection. Closed sessions reject Generate; the
card stays read-only.

The editor child page is reachable only via the "Build / Edit rules"
button (no direct link from any other page in 13A). Workspace-level
RuleSet management (a hypothetical `/operator/rule-sets/` index) is
out of scope; operators reach their Personal library through the
selector on any session's assignments page.

## DB shape

Rules and RuleSets are persisted in two new tables. The rule tree
itself lives as a JSON column inside `RuleSetRevision` rather than
being normalised into per-rule rows — the engine consumes the tree
as a whole, the editor serialises it as a whole, and the rule shape
is recursive (composite rules contain rules). A normalised schema
would force every editor save to walk a tree of joins that no
consumer benefits from.

```
rule_sets
  id                 BIGINT PK
  name               VARCHAR(255)
  description        TEXT
  scope              VARCHAR(16)        # 'seed' | 'personal'
  owner_user_id      BIGINT FK users(id) NULL  # NULL for seeds
  is_seed            BOOLEAN
  current_revision_id BIGINT FK rule_set_revisions(id) NULL  # latest revision pointer
  deleted_at         TIMESTAMPTZ NULL   # soft delete; rows pinned by audit refs
  created_at         TIMESTAMPTZ
  updated_at         TIMESTAMPTZ

rule_set_revisions
  id                 BIGINT PK
  rule_set_id        BIGINT FK rule_sets(id) ON DELETE CASCADE
  revision_no        INTEGER            # 1-based, monotonically increasing per rule_set_id
  combinator         VARCHAR(16)        # 'all_of' | 'any_of' | 'pipeline'
  exclude_self_reviews BOOLEAN
  seed               INTEGER NULL       # for RANDOM-strategy quotas
  rules_json         JSON               # serialised Rule[] (nested for composites)
  created_at         TIMESTAMPTZ
  created_by_user_id BIGINT FK users(id) NULL
  UNIQUE (rule_set_id, revision_no)
```

Notes on the shape:

- **Two scopes only.** `seed` and `personal`. A future `shared`
  scope is a plausible extension but not in 13A or 12A; if it
  materialises later, it slots into the `scope` column without
  schema churn.
- **Soft delete for `rule_sets`.** Generated assignments carry the
  RuleSet id and revision id in their `assignments.generated` audit
  context (see "Audit events" below). Hard-deleting the row would
  orphan that reference. Soft delete (`deleted_at IS NOT NULL`)
  hides the row from the library while preserving the link from the
  audit log.
- **Revisions, not row mutations.** Saving an edit to a Personal
  RuleSet appends a new `rule_set_revisions` row and bumps
  `current_revision_id`. The previous revision rows are retained;
  past `assignments.generated` rows pin a specific revision id, so
  an edit doesn't retroactively change the historical record.
- **JSON column, dialect-neutral.** Use `sqlalchemy.JSON`
  (the dialect-neutral version), per the project rule that
  `app/db/models/` does not import from
  `sqlalchemy.dialects.postgresql`. SQLite tests already round-trip
  JSON columns elsewhere (e.g. instrument validation block); reuse
  that pattern.
- **No FK from `rule_set_revisions.created_by_user_id` to a session.**
  RuleSets are workspace-scoped, not session-scoped — a Personal
  RuleSet is reusable across every session the operator runs. The
  link from "this generation used this RuleSet" lives in the
  `assignments.generated` audit context, keyed by `session_id` (top-
  level identity) and `rule_set_revision_id` (in `refs`).

The Pydantic schemas mirror the spec's JSON shape and live at
`app/schemas/rules.py`. The DB models are at
`app/db/models/rule_set.py`.

## Engine

`app/services/rules/engine.py` exports two top-level functions:

```python
def evaluate(rule_set: RuleSetSchema, *, reviewers: list[Reviewer],
             reviewees: list[Reviewee],
             override_exclude_self_reviews: bool | None = None
             ) -> EvaluationResult: ...

def validate_rule_set(rule_set: RuleSetSchema,
                      reviewers: list[Reviewer],
                      reviewees: list[Reviewee]) -> list[ValidationIssue]: ...
```

`EvaluationResult` carries:

- `pairs: list[tuple[Reviewer, Reviewee]]` — the surviving
  assignments, in deterministic `(reviewer.email, reviewee.email)`
  order.
- `excluded_counts: dict[str, int]` — exclusion reasons,
  flatten-keyed (`self_review`, `predicate.<rule_id>`,
  `quota.per_reviewer`, `quota.per_reviewee`).
  The `excluded_<reason>` key family is the one Segment 11K pre-
  flattened on `assignments.generated.context` for exactly this
  case.
- `warnings: list[str]` — zero-assignment, quota-not-fully-met
  (when `min` is set but the candidate pool was already smaller),
  unreferenced rules, etc.

The optional `override_exclude_self_reviews` argument is what the
card-level checkbox feeds in: when set, it shadows
`rule_set.options.excludeSelfReviews` for that one evaluation
without mutating the RuleSet. The editor-side preview never passes
this argument (it always reflects the saved value).

`validate_rule_set` runs without populations to surface schema
errors (unknown field name in a predicate, malformed regex, quota
`min > max`, etc.); with populations it adds emptiness / quota-
satisfiability checks. The library editor calls it on every keystroke
to populate the live preview panel.

Engine guarantees:

- **Deterministic.** Same `(rule_set, reviewers, reviewees,
  override?)` always yields the same pairs in the same order.
  RANDOM-strategy quotas use `rule_set.options.seed` (an integer);
  when unset, fall back to a hash of the RuleSet's current revision
  id so the result is reproducible without operator action.
- **Pure.** No DB calls, no time reads, no side effects. The engine
  takes already-loaded reviewer / reviewee lists and returns a
  result; the caller writes to the DB via `replace_assignments(...)`.
- **Predicate vocabulary** matches the spec section §4.4 exactly.
  Field names are operator-facing dotted form (`reviewer.tag1`,
  `reviewee.email`); the engine internally maps `tag1/2/3` to the
  ORM column names `tag_1/2/3` on the model.

## Audit events

Three new event types, plus an extension of the existing one:

| event_type | Payload envelope | Identity / refs / context |
|---|---|---|
| `rule_set.created` | `snapshot` (full RuleSet incl. rules JSON) | `refs.rule_set_id`, `refs.rule_set_revision_id`; `context.scope`, `context.is_seed=False` |
| `rule_set.updated` | `changes` (top-level metadata only — name, description, current revision pointer) **plus** a new revision row whose `id` lands in `refs.rule_set_revision_id` | `refs.rule_set_id`, `refs.rule_set_revision_id` |
| `rule_set.deleted` | `snapshot` (final state) | `refs.rule_set_id`; `context.soft=True` |
| `assignments.generated` (existing) | `counts` (already shipped: assignments / excluded keys) | New `refs.rule_set_id`, `refs.rule_set_revision_id` (only set when `mode='rule_based'`); existing `context.mode='rule_based'`, new `context.exclude_self_reviews=<bool>` recording the actually-applied value (whether from the RuleSet or the card override), existing `context.filename` stays unset for rule-based runs |

Register all four under `EVENT_SCHEMAS` in `app/services/audit.py`
(see Segment 11K). Strict-mode tests will fail the registration
gate if a new event type is omitted.

The `assignments.generated.excluded_counts` keyspace gains:

- `predicate.<rule_id>` — pairs dropped because they failed a
  predicate from a named rule.
- `quota.per_reviewer` and `quota.per_reviewee` — pairs dropped to
  cap a reviewer's / reviewee's count at `max`. (No per-id keys —
  flatten only by axis, not by id, to keep the audit detail size
  bounded.)
- `self_review` — already shipped; reused unchanged when the
  RuleSet's `excludeSelfReviews` (or the card override) is true.

Run the audit-strict-mode tests under
`tests/unit/test_audit_detail_schema.py` to confirm every new
event-type registration; round-trip the existing `excluded_*`
flatten through the registry.

## Predicate vocabulary mapping

The spec uses a short dotted form (`reviewer.tag1`, `reviewee.email`)
for operator-facing predicates. The engine converts these to the ORM
column names at evaluation time:

| Spec form | Model column | Notes |
|---|---|---|
| `reviewer.email` | `Reviewer.email` | Case-insensitive equality. |
| `reviewer.tag1` | `Reviewer.tag_1` | Underscore inserted. |
| `reviewer.tag2` / `tag3` | `Reviewer.tag_2` / `tag_3` | Same. |
| `reviewee.email` | `Reviewee.email_or_identifier` | The reviewee identifier may be a non-email string; case-insensitive equality continues to apply. |
| `reviewee.tag1/2/3` | `Reviewee.tag_1/2/3` | Same. |

The mapping table lives at `app/services/rules/fields.py` and is the
single source of truth — the editor's field picker, the engine's
predicate executor, and the validator all read from it. Adding a
new addressable field (e.g. `reviewee.profile_link`) is a one-row
edit there.

Empty / missing values follow the spec rule: `tag_*` is nullable and
treated as `None`; predicates returning a comparison against `None`
short-circuit to `false` unless the operator is `is_empty`. The
engine never raises on missing fields.

## Scope

### In

- New tables and Pydantic schemas (PR 1).
- Pure-Python rule engine with deterministic eval + a structured
  validator (PR 2).
- Six seeded RuleSets installed via Alembic data migration (PR 3).
- Operator-facing Rule Based card on the assignments page replacing
  the placeholder, with selector + exclude-self-review checkbox +
  Generate (PR 4).
- Editor child page reached from the card; Save / Save As / in-place
  Save / Rename / Delete + revisioning (PRs 5-6).
- Live preview panel on the editor (PR 7).
- Retirement of the standalone Full Matrix card (PR 8).

### Out (deferred or never)

- **Export / Import of RuleSets.** Deferred to **Segment 12A**
  (the workplan's import/export segment). 12A grows a new PR for
  RuleSet JSON round-trip; 13A ships without portability. Cross-
  reference: see the new "RuleSet round-trip" subsection in
  [`guide/segment_12A_import_export.md`](segment_12A_import_export.md).
- **Shared scope.** Personal-only in 13A. A workspace-shared scope
  is a plausible future extension but isn't 13A-blocking. The DB
  shape leaves room for it (`rule_sets.scope` column accepts a
  future `'shared'` value); no UI today.
- **Workspace-level RuleSet management page** (e.g.
  `/operator/rule-sets/` listing every Personal RuleSet across
  sessions). Operators reach their library via any session's
  Rule Based card. If a workspace-level page becomes useful later,
  it's additive — the underlying tables already support it.
- **Cross-session rule libraries** beyond Personal — out. RuleSets
  are workspace-scoped (any session can use any of the operator's
  Personal RuleSets); per-team or per-organisation hierarchies are
  not on the roadmap.
- **Weighted allocation** — out. Quota rules cap multiplicity but
  don't optimise for balance across reviewers.
- **Optimisation objectives** (minimise repeat pairings across
  cycles, etc.) — out. The spec defers these explicitly.
- **History-aware quota selection** (e.g. "don't pair reviewers
  who paired in the last cycle") — out.
- **Random allocation strategies beyond `RANDOM` and `ROUND_ROBIN`** —
  out. The two strategies the spec names cover the cases we have.
- **Editing or deleting Seeded RuleSets in place** — out. Seeds are
  read-only by design; operators duplicate to modify.
- **A migration tool to re-flow existing manual / full-matrix
  assignments through Advanced mode** — out. Existing assignments
  on a session are wipe-and-replaced by `replace_assignments(...)`
  whenever any mode is regenerated, which is the existing contract;
  we don't need a one-shot migrator.
- **Multi-instrument-aware rules** (e.g. "rule R applies to
  instrument X only") — out. Today's `Assignment.instrument_id`
  per-instrument pairing carries through the engine just like it
  does for Full Matrix; rules don't gain instrument-awareness in
  this segment.

## Proposed PR sequence

### PR 1 — Schema + Pydantic shapes

**Goal.** Land the persistence layer and the typed in-memory rule
shape so PR 2's engine has something to consume. No engine, no UI,
no operator-visible change.

- New Alembic migration creating `rule_sets` and
  `rule_set_revisions`, indexes on `(scope, deleted_at)` and
  `(rule_set_id, revision_no)`.
- New ORM models `RuleSet` + `RuleSetRevision` at
  `app/db/models/rule_set.py`. Use `Mapped[]` / `mapped_column`
  per project convention; no `dialects.postgresql` imports.
- New Pydantic schemas at `app/schemas/rules.py` mirroring the
  spec's JSON shape:
  - `RuleSetSchema` (id, name, description, scope, combinator,
    options, rules, metadata).
  - `RuleSchema` discriminated union: `FilterRule`, `MatchRule`,
    `QuotaRule`, `CompositeRule`. Use a `kind` literal field as the
    discriminator.
  - `Predicate` with the operators from spec §4.4, validated at
    `model_validate` time (regex compiles, set membership lists are
    non-empty, etc.).
  - `RuleSetRevisionSchema` for revision metadata.
- Migration round-trip tests (`alembic upgrade head` then
  `alembic downgrade -1`); both dialects (SQLite + Postgres CI job).
- Unit tests on Pydantic shapes — golden roundtrip of a non-trivial
  RuleSet, validation rejections (unknown operator, malformed
  regex, etc.), discriminated-union dispatch.

No new operator-visible behaviour. The placeholder card on
`/operator/sessions/{id}/assignments` is unchanged.

### PR 2 — Engine + validator + tests

**Goal.** Pure-Python evaluator that consumes a `RuleSetSchema` and
two population lists and returns deterministic pairs. No DB, no UI.

- New module `app/services/rules/engine.py` implementing `evaluate`
  and `validate_rule_set` per the "Engine" section above.
- New module `app/services/rules/fields.py` holding the
  field-name → ORM-column mapping (single source of truth).
- New module `app/services/rules/predicates.py` with one function per
  operator (`equals`, `not_equals`, `in_`, `not_in`, `matches`,
  `not_matches`, `is_empty`, `is_not_empty`, `same_as`,
  `different_from`).
- New module `app/services/rules/quotas.py` with the two selection
  strategies (`RANDOM` seeded, `ROUND_ROBIN`). Quotas operate on the
  surviving pairs from the content phase; a `min` violation surfaces
  as a `warnings` entry, not a hard error.
- Unit tests at `tests/unit/test_rules_engine.py` covering:
  - Each predicate operator on each addressable field.
  - Combinator semantics: ALL_OF intersects, ANY_OF unions,
    PIPELINE applies in order.
  - Composite rules nest correctly (AND inside OR, etc.).
  - Quota rules cap at `max`; under `min`, populate `warnings`.
  - Self-review exclusion at the RuleSet `excludeSelfReviews=true`
    level (the desugar happens before content rules).
  - The `override_exclude_self_reviews` argument shadows the
    RuleSet's stored value without mutating it.
  - Determinism: 100 RANDOM-quota runs with the same seed yield
    identical output; differing seeds yield differing output.
  - Empty population edge cases (empty R, empty E, both empty).
  - Field-mapping unit tests assert `tag1 → tag_1` (etc.) and reject
    unknown field names.
- No integration tests yet (no route, no DB write).

### PR 3 — Seeded RuleSets

**Goal.** Install the six seeds the spec names. Library is empty
for everyone (no UI yet); the seeds are read-only DB rows.

- Alembic data migration that inserts six rows into `rule_sets`
  (scope=`seed`, owner_user_id=NULL, is_seed=True) and one
  initial revision per seed into `rule_set_revisions` (revision_no=1).
  Hand-rolled migration; no autogenerate (we're not changing the
  schema).
- Seed definitions live at `app/services/rules/seeds.py` as Python
  literals (Pydantic `RuleSetSchema` instances), not in the
  migration file — the migration imports from `seeds.py` and writes
  the JSON. This way the seed definitions stay close to the rest of
  the engine code and edits don't churn migration files.
- Six seeds, names per spec §5.4:
  1. **Full Matrix** — empty rules, ALL_OF, `excludeSelfReviews=true`.
     Drives PR 8's retirement of the standalone Full Matrix card.
  2. **Intra-group peer review** — single MATCH rule
     `reviewer.tag1 same_as reviewee.tag1`, ALL_OF,
     `excludeSelfReviews=true`.
  3. **Cross-group peer review** — single MATCH rule
     `reviewer.tag1 different_from reviewee.tag1`, ALL_OF,
     `excludeSelfReviews=true`.
  4. **Same group, different role** — two MATCH rules under ALL_OF
     (`tag1 same_as`, `tag2 different_from`), `excludeSelfReviews=true`.
  5. **Three reviewers per reviewee** — empty content rules, single
     QUOTA rule `PER_REVIEWEE min=3 max=3 RANDOM seed=42`,
     `excludeSelfReviews=true`.
  6. **Lead-led review** — ANY_OF combinator with two branches:
     intra-group MATCH; and a COMPOSITE AND of (`reviewer.tag2=Lead`,
     `reviewee.tag2=Lead`, `tag1 different_from`).
- `tests/unit/test_rules_seeds.py` runs each seed through PR 2's
  engine on a canonical fixture population (e.g. 4 groups × 5
  members, 1 lead per group) and asserts the pair count + a sample
  of pairs match the spec's expected behaviour.
- Pin a test that the seeded `Full Matrix` RuleSet, evaluated on a
  fixture population with `excludeSelfReviews=true`, produces the
  same pair set as `assignments.generate_full_matrix(...)` with
  `exclude_self_review=True` on the same population. This is the
  load-bearing equivalence behind PR 8's retirement.
- No `audit_events` writes — the data migration is a one-time
  install.

### PR 4 — Rule Based card (seeds-only)

**Goal.** First user-visible PR. Replace the placeholder Rule Based
card on `/operator/sessions/{id}/assignments` with a working card
limited to the six seeds. The operator picks a seed → optionally
flips the Exclude self-review checkbox → clicks Generate → the
existing `replace_assignments(...)` writes the assignments and
rotates the audit log.

- New service module `app/services/rules/library.py` exposing:
  - `list_visible_rule_sets(db, *, user) -> list[RuleSet]` —
    returns seeds + Personal-scope RuleSets owned by `user`. In PR 4
    the user filter still applies but no Personal rows exist yet, so
    it returns just seeds. Same query covers PR 5 onward
    unchanged.
  - `load_rule_set(db, rule_set_id) -> tuple[RuleSet, RuleSetRevision]`
    — resolves a RuleSet by id and returns the row plus its current
    revision. Resolves soft-deleted rows too (used for audit-ref
    resolution).
- Extend `replace_assignments(...)`
  (`app/services/assignments.py`) to accept an optional
  `rule_set_revision: RuleSetRevision | None` parameter. When set,
  the audit context grows `refs.rule_set_id` +
  `refs.rule_set_revision_id`, `mode` becomes `'rule_based'`
  (already in the enum), and `context.exclude_self_reviews` records
  the actually-applied value.
- New route handlers in `app/web/routes_operator.py`:
  - `GET /operator/sessions/{id}/assignments/rule-based` — renders
    the seeds-only library + the picker UI. Anchor: replaces the
    `placeholder_card` macro at `session_assignments.html:133-142`.
    *(Optional — the card may render directly in
    `session_assignments.html` without a dedicated GET; choose
    whichever fits the existing page's render pattern.)*
  - `POST /operator/sessions/{id}/assignments/rule-based/generate` —
    body has `rule_set_id` and `exclude_self_reviews` (the
    checkbox). Loads the RuleSet, runs PR 2's engine with the
    override, invokes `replace_assignments(...)`, 303s back to the
    assignments page with a banner.
- Template work: replace the placeholder card with a real partial
  `_rule_based_card.html`. The partial renders the layout described
  in "Card design" above:
  - The selector dropdown (seeds only in PR 4; Personal added by
    PR 5's library extension).
  - The selected RuleSet's one-line description.
  - The Exclude self-review checkbox initialised from the selected
    RuleSet's `options.excludeSelfReviews` (initial render uses
    the default selection's value; the editor in PR 5 adds an
    inline JS hook to update it on selector change without a page
    reload).
  - The Generate button.
  - The Last-generated summary (read from the most recent
    `assignments.generated` audit row for this session with
    `mode='rule_based'`).
  - **Not yet** the Build / Edit rules button — that lands in PR 5.
- Audit:
  - `assignments.generated` with the new
    `refs.rule_set_id` / `refs.rule_set_revision_id` and
    `context.exclude_self_reviews`. Run the strict-mode test gate.
  - No `rule_set.*` events yet (no creates / edits / deletes).
- Tests:
  - `tests/integration/test_rule_based_generate.py` — login as
    operator, GET the page, POST Generate with `rule_set_id` of
    each seed, with the override checkbox both true and false on
    the same seed, assert assignments wrote and the audit context
    reflects the actually-applied value.
  - `tests/unit/test_rules_library.py` — `list_visible_rule_sets`
    returns the six seeds, sorted by name, when no Personal rows
    exist.
  - Lifecycle gate: posting Generate on a `ready` / `closed`
    session 409s with the standard yellow lock card explanation
    (the existing assignments-page gate covers this — extend the
    test to confirm the new POST inherits it).

After PR 4, an operator can pick "Intra-group peer review" from a
dropdown and generate working assignments without touching code or
SQL. This is the smallest useful Advanced-mode shape.

### PR 5 — Editor child page + Save / Save As (Personal scope)

**Goal.** Operators can open a child page from the Rule Based card,
inspect a seed's rules, modify them, and save the result as a new
Personal RuleSet. First write path into `rule_sets` from the UI.

- Add the **Build / Edit rules** button to the Rule Based card (PR 4
  partial). It links to the editor child page for the
  currently-selected RuleSet, with `+ New blank RuleSet` as a
  selector entry that opens the editor with no RuleSet pre-loaded.
- Library list (`list_visible_rule_sets`) now includes Personal-scope
  RuleSets owned by the current user (`scope='personal' AND
  owner_user_id=current_user.id AND deleted_at IS NULL`), grouped
  separately in the selector.
- New editor child page at
  `GET /operator/sessions/{id}/assignments/rule-based/edit/{rule_set_id}`
  (and a `…/edit/new` variant for blank-start):
  - **Metadata strip** — name, description (textareas).
  - **Combinator selector** — radio (`ALL_OF` / `ANY_OF` /
    `PIPELINE`).
  - **`excludeSelfReviews` checkbox** (the persisted RuleSet
    setting; distinct from the card's transient override).
  - **Rule list** — ordered, with per-row drag handle + enable
    toggle + kind selector (FILTER / MATCH / QUOTA / COMPOSITE).
  - **Predicate editor** — for FILTER / MATCH (and inside COMPOSITE):
    field picker (auto-populated from the field-name table at
    `app/services/rules/fields.py`), operator picker
    (auto-populated by field type), operand picker (auto-populated
    from the loaded session's actual tag values where the field is
    a tag — `tag1`'s pickable values are the distinct non-empty
    values present on Reviewers + Reviewees in this session).
  - **Quota editor** — scope (`PER_REVIEWER` / `PER_REVIEWEE`),
    `min` / `max` numerics, selection strategy (`RANDOM` with seed
    field / `ROUND_ROBIN`).
  - The session id in the URL feeds the operand picker (and PR 7's
    preview); the RuleSet itself is workspace-scoped, so the same
    `rule_set_id` is reachable from any session's editor.
- Save / Save As actions:
  - **Save As** — primary action when editing a seed (seeds are
    read-only). Prompts for name + description, creates a new
    `rule_sets` row in `personal` scope owned by the current user,
    inserts a `rule_set_revisions` row with the edited tree,
    points `current_revision_id` at it. Audit `rule_set.created`
    with `snapshot` of the full RuleSet + first revision. After
    save, 303 back to the editor at the new RuleSet's URL.
  - **Save** — primary action when editing a Personal RuleSet. PR 5
    only ships Save As (Save = Save As under a different label
    when the loaded RuleSet is a seed); PR 6 adds in-place Save
    that creates a new revision on the existing RuleSet.
- Routes:
  - `GET /operator/sessions/{id}/assignments/rule-based/edit/{rule_set_id}` —
    render the editor with the selected RuleSet loaded.
  - `GET /operator/sessions/{id}/assignments/rule-based/edit/new` —
    render the editor blank.
  - `POST /operator/sessions/{id}/assignments/rule-based/save-as` —
    body has the new name / description and the edited rule tree
    (JSON).
- Validation: `validate_rule_set(...)` runs server-side on save; the
  editor template surfaces returned `ValidationIssue`s inline above
  the affected rule with the standard error-banner colour.
- Audit `rule_set.created` registered in `EVENT_SCHEMAS`.
- Tests:
  - `tests/unit/test_rules_library.py` extended: `list_visible_rule_sets`
    surfaces user A's Personal RuleSets to user A, hides them from
    user B, and shows seeds to both.
  - `tests/integration/test_rule_set_editor.py` — load a seed via
    the editor URL, edit, Save As, assert library now shows the new
    Personal RuleSet, audit emitted, predicate edits round-trip
    exactly through the JSON column.
  - Permission tests: Save As as user A creates a Personal RuleSet
    visible to A but not user B.

### PR 6 — Edit / Rename / Delete + revisioning

**Goal.** Round out the lifecycle of Personal RuleSets — edit in
place (with revisioning), rename (without rewriting rules), delete
(soft).

- New routes (siblings of PR 5's Save As):
  - `POST /operator/sessions/{id}/assignments/rule-based/save` —
    same body as Save As but targets an existing Personal RuleSet
    via a `rule_set_id` form field. Inserts a new
    `rule_set_revisions` row with `revision_no = previous + 1`,
    bumps `current_revision_id`. Audit `rule_set.updated` with
    `changes` envelope (just metadata diffs) and the new revision id
    in `refs`.
  - `POST /operator/sessions/{id}/assignments/rule-based/rename` —
    body has `rule_set_id`, `name`, `description`. Touches
    `rule_sets` only, no new revision. Audit `rule_set.updated`
    with `changes` envelope (name/description diff).
  - `POST /operator/sessions/{id}/assignments/rule-based/delete` —
    body has `rule_set_id`. Sets `deleted_at = now` on the RuleSet
    (no cascade — revisions are kept for the audit trail). Audit
    `rule_set.deleted`. Returns 303 to the assignments page.
- Permission gate: Save / Rename / Delete reject with 403 if
  `owner_user_id != current_user.id`. Seeds reject all three (they
  have no owner; the editor surfaces only Save As when a seed is
  loaded).
- Library list query now hides `deleted_at IS NOT NULL` rows. The
  selector on the card automatically reflects this; previously-
  selected deleted RuleSets fall back to the default seed.
- A Personal RuleSet pinned by a past `assignments.generated` row
  remains resolvable: the audit's `refs.rule_set_id` /
  `rule_set_revision_id` still load via
  `load_rule_set(...)`, which doesn't filter on `deleted_at` (only
  the library list does).
- `rule_set.updated` and `rule_set.deleted` registered in
  `EVENT_SCHEMAS`.
- Tests:
  - Save creates a new revision with the right `revision_no`;
    `current_revision_id` follows.
  - Rename without rule changes produces no new revision.
  - Delete is soft — RuleSet still resolvable by id; library hides
    it. Past audit refs still resolve.
  - Permission gate: user B cannot Save / Rename / Delete user A's
    Personal RuleSet.
  - Seed RuleSets reject Save / Rename / Delete with the appropriate
    400 / 403.

After PR 6, the Personal-scope library is fully functional. Future
PRs add inspection (live preview) and tidy up (retire Full Matrix).

### PR 7 — Live preview panel

**Goal.** Add an inline live panel to the editor that updates as the
operator edits. The panel surfaces distribution stats + warnings
before the operator commits.

- Editor template gains a right-hand panel rendered from a new
  partial `_rule_set_preview.html`. Contents:
  - **Pair count** — total assignments the current RuleSet would
    produce.
  - **Distribution per reviewer** — mini bar chart or count list:
    "5 reviewers → 12 assignments each; 3 reviewers → 0 assignments".
  - **Distribution per reviewee** — same shape from the reviewee
    side.
  - **Sampled pairs** — first 10 surviving pairs in deterministic
    order, each rendered as `Reviewer — Reviewee`.
  - **Warnings** — bullet list from `EvaluationResult.warnings`
    (zero-assignment, quota under-met, unreferenced rules).
- Server-side render, no client-side rule evaluation. Each editor
  POST that targets `…/preview` (a separate read-only endpoint that
  doesn't write) returns the rendered partial. The editor page wires
  it via inline JS (one `fetch` + replace) — same progressive-
  enhancement convention used elsewhere (instruments live preview,
  quick-setup lock toggle).
- New route
  `POST /operator/sessions/{id}/assignments/rule-based/preview` —
  body has the in-progress rule tree JSON. Returns the preview
  partial. Session id from the URL feeds the operand picker and
  the engine call (the preview always runs against the URL session's
  populations).
- The preview panel uses
  `engine.evaluate(rule_set, reviewers=R, reviewees=E)` against the
  session's actual populations, then computes the per-side
  distribution from `result.pairs`. The card's checkbox-level
  override is **not** applied — the preview reflects the saved
  `excludeSelfReviews` setting, since that's what'll persist.
- Tests:
  - `tests/unit/test_rule_preview_view.py` — given a known
    `EvaluationResult`, the view-shape adapter produces the right
    distribution arrays.
  - `tests/integration/test_rule_preview.py` — POST the preview
    route with each seed, assert pair count + sampled pairs match
    a fixture.
  - The preview is read-only: posting it twice in a row produces no
    `assignments.generated` audit and no `rule_set.*` audit.

### PR 8 — Retire standalone Full Matrix card

**Goal.** Remove the standalone Full Matrix card from the
assignments page now that the seeded `Full Matrix` RuleSet covers
the same case from inside the Rule Based card. Last PR of 13A; no
new behaviour, only consolidation.

- Delete the Full Matrix card markup from
  `session_assignments.html` (lines 146-176 today).
- Delete the route handler that backs it
  (`POST /operator/sessions/{id}/assignments/full-matrix` or
  whatever the existing path is — one of the existing handlers in
  `routes_operator.py:882-948`'s neighbourhood). The
  `replace_assignments(...)` writer stays (Manual upload still uses
  it); only the route + form go.
- Delete the corresponding tests in
  `tests/integration/test_assignment_routes.py` covering the
  retired route.
- The `assignments.generated` audit row family with
  `mode='full_matrix'` remains valid for the historical record (past
  rows pinned by it stay readable). New rows with this mode never
  emit again — the seeded RuleSet writes `mode='rule_based'`.
- Update `session_assignments.html` so the layout reflows from three
  cards to two (Rule Based + Manual). The page-grid pattern adapts
  cleanly.
- Card-design touch: add a small one-time inline note on the Rule
  Based card after upgrade — "Full Matrix is now available as a
  seeded RuleSet" — visible until the operator dismisses it (cookie
  flag) or for a fixed window (e.g. one week post-deploy). Optional;
  if the card's selector already defaults to a sensible seed, the
  note is overkill. Decide on PR-prep review.
- Tests:
  - The assignments page renders without a Full Matrix card section.
  - The retired route returns 404.
  - The Manual upload card and the Rule Based card both still
    function.
  - Existing `tests/unit/test_assignments_full_matrix.py` continues
    to pass (it tests the `generate_full_matrix(...)` function, not
    the route — and that function stays alive because the seeded
    `Full Matrix` RuleSet's evaluator produces the same output;
    the unit test pinned by PR 3 cross-checks this).

After PR 8, the assignments page has two cards: Manual upload and
Rule Based. Operators who previously used Full Matrix find it as the
default seed in the Rule Based selector with the same output as
before.

## Implementation pointers

- **Rule tree as JSON in one revision row** is the right call — see
  the rationale in "DB shape" above. Resist the urge to normalise
  into `rule_set_rules` + `rule_set_predicates` tables; the engine
  consumes the tree as a whole, the editor saves it as a whole, and
  composite rules force recursion that joins can't help with.
- **Use the existing `replace_assignments(...)` writer** for PR 4's
  Generate. Don't write a parallel writer just because the source
  is a RuleSet — the audit shape, lifecycle gate, and DB write are
  all the same as Full Matrix / Manual. Adding the optional
  `rule_set_revision=` argument is the only change; the
  `excluded_counts` dict already accepts new keys per Segment 11K.
- **Field-mapping table is the single source of truth.** Adding a
  new addressable field (`reviewee.profile_link`, `reviewer.status`,
  etc.) is one row in `app/services/rules/fields.py`; the editor's
  picker reads from it, the predicate executor reads from it, the
  validator reads from it. Don't fork the list across modules.
- **Determinism is non-negotiable.** Two runs of the same
  `(rule_set, populations, override?)` must produce byte-identical
  assignments in the same order. Anywhere the engine touches an
  unordered set (dict iteration, `set` traversal), explicitly sort.
  RANDOM-strategy quotas seed from
  `rule_set.options.seed ?? hash(rule_set_revision_id)`.
- **Predicate validation runs at save time, not at generate time.**
  An unknown field name or a malformed regex is a save-time error
  surfaced inline in the editor; the engine assumes a validated
  RuleSet and may crash on an invalid one. This keeps the engine
  small and predictable.
- **Empty values are treated as `None`.** Per the spec — empty
  string in `tag_*` is the same as NULL. Normalise on read inside
  the engine (`value or None`); the editor's operand picker shows
  empty values as a sentinel "(empty)" entry.
- **Case-insensitive equality is the default.** All string
  comparisons trim and lowercase before equality. The spec's
  case-sensitive flag rides on the predicate; until an operator
  asks for it, the editor's UI doesn't surface the toggle (the
  data model carries the flag for forward-compat).
- **The `excluded_<reason>` flatten on `assignments.generated.context`**
  was pre-laid by Segment 11K specifically for this case — the
  flatten keys are unconstrained, so adding `predicate.<rule_id>`
  and `quota.per_reviewer` / `quota.per_reviewee` doesn't need a
  schema change. Land the new keys with the strict-mode test
  enabled (default in tests).
- **Keep predicate field names operator-facing in the rules JSON.**
  Store `reviewer.tag1`, not `reviewer.tag_1` — the JSON is what
  operators read in export files (Segment 12A) and the editor's
  raw view; the ORM-column underscore is an implementation detail.
  The mapping happens once, in the engine's predicate executor.
- **Card-level checkbox is a per-Generate override only.** It does
  not write back to the RuleSet's `options.excludeSelfReviews`. The
  editor's checkbox is the one that persists. The audit's
  `context.exclude_self_reviews` records the actually-applied value
  — the audit log is the source of truth for what ran.
- **PR 8's Full Matrix retirement is load-bearing on PR 3's
  equivalence test.** The retirement only ships if PR 3's pinned
  test (the seeded `Full Matrix` RuleSet produces the same pair set
  as `generate_full_matrix(...)`) is green. If the equivalence
  fails, fix the seed before PR 8 — don't loosen the test.

## Test impact

- New unit tests:
  - `tests/unit/test_rules_engine.py` (PR 2; ~40-60 cases covering
    each predicate, combinator, quota, edge case).
  - `tests/unit/test_rules_seeds.py` (PR 3; 6 seeds × canonical
    fixture + the Full Matrix equivalence pin).
  - `tests/unit/test_rules_library.py` (PRs 4-6; library list
    queries, Save As / Save / Rename / Delete state transitions).
  - `tests/unit/test_rules_predicates.py` (PR 2; one test per
    operator, including missing-value behaviour).
  - `tests/unit/test_rules_quotas.py` (PR 2; RANDOM determinism,
    ROUND_ROBIN distribution, under-min warnings).
  - `tests/unit/test_rule_preview_view.py` (PR 7).
- New integration tests:
  - `tests/integration/test_rule_based_generate.py` (PR 4; route +
    audit + override checkbox).
  - `tests/integration/test_rule_set_editor.py` (PR 5; Save As).
  - `tests/integration/test_rule_set_lifecycle.py` (PR 6; Save /
    Rename / Delete + revisioning).
  - `tests/integration/test_rule_preview.py` (PR 7).
  - `tests/integration/test_full_matrix_retirement.py` (PR 8; the
    standalone card and route are gone, the seeded RuleSet still
    produces equivalent output).
- One golden-fixture file per seed under
  `tests/fixtures/rule_set_seeds/{name}.csv` — the canonical
  population's expected pairs. Edits to a seed force a deliberate
  fixture update, which is the cheapest place to think it through.
- `tests/unit/test_audit_detail_schema.py` — extend the
  registry-coverage test with the four new event types
  (`rule_set.created`, `rule_set.updated`, `rule_set.deleted`,
  plus the extended `assignments.generated` refs and
  `context.exclude_self_reviews`). Strict-mode test catches any
  unregistered emit at PR landing.
- Existing tests that touch the standalone Full Matrix route
  (`tests/integration/test_assignment_routes.py`) are pruned in
  PR 8; tests that touch the underlying writer
  (`tests/unit/test_assignments_full_matrix.py`) stay.

## Doc impact

- `docs/status.md` gains a timeline entry per shipped PR; the "as of"
  header advances to "end of Segment 13A" once PR 8 merges.
- `guide/todo_master.md`:
  - Move 13A from **Upcoming** to the in-progress block once PR 1
    lands; move to **Done** when PR 8 merges.
  - 13B stays in **Upcoming** untouched (independent segment).
  - Update 12A's entry to flag the new RuleSet I/O PR (cross-
    reference; 12A's plan owns the details).
- `spec/rule_based_assignment.md` — the canonical spec; one-liner
  added on each PR if it clarifies a previously-ambiguous point
  (e.g. PR 6's revisioning model). The plan owns sequencing; the
  spec owns the model.
- `spec/operator_ui_concept.md` — the Setup-pages section gets a
  one-liner clarifying that the Assignments page ships two modes
  after 13A (Manual + Rule Based), with Rule Based opening a
  dedicated editor child page. Verify on PR 8 review.
- `spec/architecture.md` — under "Audit-event detail schema", the
  worked-examples table gets one row per new event type
  (`rule_set.created` / `rule_set.updated` / `rule_set.deleted`) and
  the `assignments.generated` row gains the `refs.rule_set_*`
  callout when `mode='rule_based'`.
- Archive this plan to `guide/archive/` once PR 8 merges, per the
  convention 11K established.
