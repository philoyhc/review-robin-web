# Canonical RuleSet cases

The four canonical seeded RuleSets for Advanced (RuleBased) assignment
mode, expressed in the engine's vocabulary
(`app/schemas/rules.py` + `app/services/rules/engine.py`). Each row is
one seeded RuleSet; the **Rules** column writes out the rule tree using
the kind / operator / operand identifiers the schema accepts.

`Full Matrix` is the degenerate empty-rules case (combinator `ALL_OF`,
zero rules, `excludeSelfReviews=true`); it's installed as a fifth seed
for parity with Simple mode but is not listed below because there's no
rule expression to lay out.

| # | Name                          | Combinator | excludeSelfReviews | Rules |
|---|-------------------------------|------------|--------------------|-------|
| 1 | Intra-group peer review       | `ALL_OF`   | `true`             | `MATCH(reviewer.tag1 same_as reviewee.tag1)` |
| 2 | Cross-group peer review       | `ALL_OF`   | `true`             | `MATCH(reviewer.tag1 different_from reviewee.tag1)` |
| 3 | Same group, different role    | `ALL_OF`   | `true`             | `MATCH(reviewer.tag1 same_as reviewee.tag1)` &nbsp;∧&nbsp; `MATCH(reviewer.tag2 different_from reviewee.tag2)` |
| 4 | Three reviewers per reviewee  | `ALL_OF`   | `true`             | `QUOTA(scope=PER_REVIEWEE, min=3, max=3, selection=RANDOM(seed=42))` |

## Reading the cells

- **Combinator** is the top-level merge for the rule list.
  - `ALL_OF` (AND) intersects the per-rule allowed sets — every rule
    must include the pair.
  - `ANY_OF` (OR) unions them — at least one rule must include the
    pair.
  - `PIPELINE` applies rules in declaration order, last-writer-wins.
  - The combinator only matters when the rule list has length ≥ 2; a
    single-rule RuleSet behaves identically under any combinator.
- **`excludeSelfReviews=true`** is the canonical filter desugared
  before the rule list runs. It drops pairs where
  `reviewer.email` matches `reviewee.email_or_identifier` (case-
  insensitive). All four canonical cases set it to `true` because a
  pair like (Alice, Alice) is never a useful review obligation.
- **Rules** column conventions:
  - `MATCH(field op operand)` — a `MATCH` rule whose `predicate.field`,
    `predicate.operator`, and `predicate.operand` are as shown.
  - `FILTER(...)` — same shape, but the rule removes matching pairs
    instead of keeping them. None of the four canonical cases use
    `FILTER` directly; the self-review filter is implicit via
    `excludeSelfReviews`.
  - `QUOTA(...)` — a `QUOTA` rule. `scope` is `PER_REVIEWER` or
    `PER_REVIEWEE`; `selection` is either `RANDOM(seed=N)` or
    `ROUND_ROBIN`; `min` / `max` are inclusive bounds. The seed pins
    determinism — two evaluations against the same RuleSet revision
    produce identical pair sets.
  - `COMPOSITE(op, [child, child, …])` — a Composite rule whose
    children are themselves rules. `op` is `AND` / `OR` / `NOT`;
    children are evaluated and merged under that operator. Composites
    nest recursively (a child can be another Composite). Not
    exercised by the canonical seeds — operators reach for it via
    the editor when they need OR-combinations or grouped negations.
  - **`∧`** is `ALL_OF` glue between siblings at the top level (case 3).
- Predicate operands prefixed `reviewer.` / `reviewee.` are field
  references on the *opposite* side, not literals — this is what makes
  `same_as` / `different_from` cross-side comparisons.

## What the cases pin

The four rows together exercise the engine primitives that operators
hit most often. The canonical seed library is intentionally narrow —
each seed covers a single common workflow and stays out of
combinator-flexing territory.

| Primitive | Exercised by |
|---|---|
| `MATCH` rule kind | 1, 2, 3 |
| `QUOTA` rule kind, `RANDOM` selection | 4 |
| `ALL_OF` combinator | 1, 2, 3, 4 |
| Cross-side operators (`same_as`, `different_from`) | 1, 2, 3 |
| `excludeSelfReviews` desugar | all four |

Engine primitives **not** exercised by the seeds — `ANY_OF`,
`PIPELINE`, `COMPOSITE` (with `AND` / `OR` / `NOT`), `FILTER`,
literal-equality `equals`, `in` / `not_in`, `matches` / `not_matches`,
`is_empty` / `is_not_empty`, `case_sensitive=true`, and
`ROUND_ROBIN` selection — are still covered by the engine unit
tests in `tests/unit/test_rules_engine.py` and remain available to
operator-built RuleSets through the editor (Segment 13A PR 5+).

## Cross-references

- Spec: `spec/rule_based_assignment.md` §4 (RuleSet model) +
  §5.4 (Seeded RuleSets).
- Schemas: `app/schemas/rules.py` for the typed Python shape.
- Engine: `app/services/rules/engine.py` for the algorithm; tests at
  `tests/unit/test_rules_engine.py` round-trip each combinator.
- Seed installer: Segment 13A PR 3 (and the Lead-led drop in a
  follow-up). The four canonical cases here are byte-equivalent to
  the rows the installer writes into `rule_set_revisions.rules_json`.
