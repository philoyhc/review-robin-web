# Canonical RuleSet cases

The five canonical seeded RuleSets for Advanced (RuleBased) assignment
mode, expressed in the engine's vocabulary
(`app/schemas/rules.py` + `app/services/rules/engine.py`). Each row is
one seeded RuleSet; the **Rules** column writes out the rule tree using
the kind / operator / operand identifiers the schema accepts.

`Full Matrix` is the degenerate empty-rules case (combinator `ALL_OF`,
zero rules, `excludeSelfReviews=true`); it's installed as a sixth seed
for parity with Simple mode but is not listed below because there's no
rule expression to lay out.

| # | Name                          | Combinator | excludeSelfReviews | Rules |
|---|-------------------------------|------------|--------------------|-------|
| 1 | Intra-group peer review       | `ALL_OF`   | `true`             | `MATCH(reviewer.tag1 same_as reviewee.tag1)` |
| 2 | Cross-group peer review       | `ALL_OF`   | `true`             | `MATCH(reviewer.tag1 different_from reviewee.tag1)` |
| 3 | Same group, different role    | `ALL_OF`   | `true`             | `MATCH(reviewer.tag1 same_as reviewee.tag1)` &nbsp;∧&nbsp; `MATCH(reviewer.tag2 different_from reviewee.tag2)` |
| 4 | Three reviewers per reviewee  | `ALL_OF`   | `true`             | `QUOTA(scope=PER_REVIEWEE, min=3, max=3, selection=RANDOM(seed=42))` |
| 5 | Lead-led review               | `ANY_OF`   | `true`             | `MATCH(reviewer.tag1 same_as reviewee.tag1)` &nbsp;∨&nbsp; `COMPOSITE(AND, [MATCH(reviewer.tag2 equals "Lead"), MATCH(reviewee.tag2 equals "Lead"), MATCH(reviewer.tag1 different_from reviewee.tag1)])` |

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
  insensitive). All five canonical cases set it to `true` because a
  pair like (Alice, Alice) is never a useful review obligation.
- **Rules** column conventions:
  - `MATCH(field op operand)` — a `MATCH` rule whose `predicate.field`,
    `predicate.operator`, and `predicate.operand` are as shown.
  - `FILTER(...)` — same shape, but the rule removes matching pairs
    instead of keeping them. None of the five canonical cases use
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
    nest recursively (a child can be another Composite).
  - **`∧`** is `ALL_OF` glue between siblings at the top level (case 3);
    **`∨`** is `ANY_OF` glue (case 5).
- Predicate operands prefixed `reviewer.` / `reviewee.` are field
  references on the *opposite* side, not literals — this is what makes
  `same_as` / `different_from` cross-side comparisons. String literals
  (case 5's `"Lead"`) are quoted.

## What the cases pin

The five rows together exercise every primitive the engine supports —
each canonical case is a single seeded RuleSet but together they form
the smallest set that touches every code path:

| Primitive | Exercised by |
|---|---|
| `MATCH` rule kind | 1, 2, 3, 5 |
| `QUOTA` rule kind, `RANDOM` selection | 4 |
| `COMPOSITE` rule kind, nested rules | 5 |
| `ALL_OF` combinator | 1, 2, 3, 4 |
| `ANY_OF` combinator | 5 |
| Cross-side operators (`same_as`, `different_from`) | 1, 2, 3, 5 |
| Literal-equality operator (`equals`) | 5 |
| `excludeSelfReviews` desugar | all five |

`PIPELINE` and `FILTER` are not exercised by the seeds — they're
available in the editor for operator-built RuleSets but no canonical
case needs them. `COMPOSITE(NOT, …)` is similarly available but unused
at the seed level.

## Cross-references

- Spec: `spec/rule_based_assignment.md` §4 (RuleSet model) +
  §5.4 (Seeded RuleSets).
- Schemas: `app/schemas/rules.py` for the typed Python shape.
- Engine: `app/services/rules/engine.py` for the algorithm; tests at
  `tests/unit/test_rules_engine.py` round-trip each combinator.
- Seed installer: lands in Segment 13A PR 3 — when that PR ships, the
  five canonical cases here become byte-equivalent to the rows the
  installer writes into `rule_set_revisions.rules_json`.
