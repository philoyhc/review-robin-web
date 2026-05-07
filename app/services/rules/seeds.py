"""Seeded RuleSets — Segment 13A PR 3.

The six canonical seeds the spec names in §5.4 and the plan
expands in PR 3. Definitions live as Pydantic
``RuleSetSchema`` instances so they can be validated at import
time and round-tripped through the engine before reaching the
DB.

The Alembic data migration that installs these into ``rule_sets``
+ ``rule_set_revisions`` imports from this module — keeping
the seed text close to the engine code rather than scattering
JSON literals through migration files. If a future seed lands
or an existing seed changes shape, that's a *new* migration
appended to the chain; the existing migration's output is
historically frozen by the rows it already wrote.

Pinned guide: ``guide/rules_table.md`` lays out each canonical
case in one row. The literals here are the byte-equivalent
RuleSetSchema realisation.
"""

from __future__ import annotations

from typing import Final

from app.schemas.rules import (
    Combinator,
    CompositeOp,
    CompositeRule,
    MatchRule,
    Predicate,
    QuotaRule,
    QuotaScope,
    QuotaSelection,
    RuleSetMetadata,
    RuleSetOptions,
    RuleSetSchema,
    RuleSetScope,
    SelectionStrategy,
)


SEED_FULL_MATRIX: Final[RuleSetSchema] = RuleSetSchema(
    name="Full Matrix",
    description="Pair every reviewer with every reviewee.",
    scope=RuleSetScope.seed,
    combinator=Combinator.ALL_OF,
    rules=[],
    options=RuleSetOptions(excludeSelfReviews=True, seed=None),
    metadata=RuleSetMetadata(isSeed=True),
)


SEED_INTRA_GROUP: Final[RuleSetSchema] = RuleSetSchema(
    name="Intra-group peer review",
    description="Reviewer and reviewee share tag1.",
    scope=RuleSetScope.seed,
    combinator=Combinator.ALL_OF,
    rules=[
        MatchRule(
            id="same_tag1",
            predicate=Predicate(
                field="reviewer.tag1",
                operator="same_as",
                operand="reviewee.tag1",
            ),
        )
    ],
    options=RuleSetOptions(excludeSelfReviews=True, seed=None),
    metadata=RuleSetMetadata(isSeed=True),
)


SEED_CROSS_GROUP: Final[RuleSetSchema] = RuleSetSchema(
    name="Cross-group peer review",
    description=(
        "Reviewer and reviewee have different tag1 — useful for "
        "fresh-perspective rounds."
    ),
    scope=RuleSetScope.seed,
    combinator=Combinator.ALL_OF,
    rules=[
        MatchRule(
            id="diff_tag1",
            predicate=Predicate(
                field="reviewer.tag1",
                operator="different_from",
                operand="reviewee.tag1",
            ),
        )
    ],
    options=RuleSetOptions(excludeSelfReviews=True, seed=None),
    metadata=RuleSetMetadata(isSeed=True),
)


SEED_SAME_GROUP_DIFFERENT_ROLE: Final[RuleSetSchema] = RuleSetSchema(
    name="Same group, different role",
    description=(
        "Same tag1, different tag2. Pair within the team but never "
        "with someone of the same role."
    ),
    scope=RuleSetScope.seed,
    combinator=Combinator.ALL_OF,
    rules=[
        MatchRule(
            id="same_tag1",
            predicate=Predicate(
                field="reviewer.tag1",
                operator="same_as",
                operand="reviewee.tag1",
            ),
        ),
        MatchRule(
            id="diff_tag2",
            predicate=Predicate(
                field="reviewer.tag2",
                operator="different_from",
                operand="reviewee.tag2",
            ),
        ),
    ],
    options=RuleSetOptions(excludeSelfReviews=True, seed=None),
    metadata=RuleSetMetadata(isSeed=True),
)


SEED_THREE_REVIEWERS_PER_REVIEWEE: Final[RuleSetSchema] = RuleSetSchema(
    name="Three reviewers per reviewee",
    description=(
        "Full candidate pool, then a PER_REVIEWEE quota of "
        "min=3, max=3, random with a fixed seed."
    ),
    scope=RuleSetScope.seed,
    combinator=Combinator.ALL_OF,
    rules=[
        QuotaRule(
            id="three_each",
            scope=QuotaScope.PER_REVIEWEE,
            min=3,
            max=3,
            selection=QuotaSelection(
                strategy=SelectionStrategy.RANDOM, seed=42
            ),
        )
    ],
    options=RuleSetOptions(excludeSelfReviews=True, seed=None),
    metadata=RuleSetMetadata(isSeed=True),
)


SEED_LEAD_LED: Final[RuleSetSchema] = RuleSetSchema(
    name="Lead-led review",
    description=(
        "Union of (a) intra-group pairings and (b) cross-group "
        "pairings where both sides have tag2 = Lead."
    ),
    scope=RuleSetScope.seed,
    combinator=Combinator.ANY_OF,
    rules=[
        MatchRule(
            id="intra_group",
            predicate=Predicate(
                field="reviewer.tag1",
                operator="same_as",
                operand="reviewee.tag1",
            ),
        ),
        CompositeRule(
            id="cross_group_leads",
            op=CompositeOp.AND,
            rules=[
                MatchRule(
                    id="rev_lead",
                    predicate=Predicate(
                        field="reviewer.tag2",
                        operator="equals",
                        operand="Lead",
                    ),
                ),
                MatchRule(
                    id="rvw_lead",
                    predicate=Predicate(
                        field="reviewee.tag2",
                        operator="equals",
                        operand="Lead",
                    ),
                ),
                MatchRule(
                    id="diff_tag1",
                    predicate=Predicate(
                        field="reviewer.tag1",
                        operator="different_from",
                        operand="reviewee.tag1",
                    ),
                ),
            ],
        ),
    ],
    options=RuleSetOptions(excludeSelfReviews=True, seed=None),
    metadata=RuleSetMetadata(isSeed=True),
)


# Order matters: drives ``seed_order`` on the inserted rows and the
# library selector's order in the editor (alphabetical-by-name within
# the seed group, but the install order pins the tie-breaker for any
# future seeds that share a starting letter).
SEEDS: Final[list[RuleSetSchema]] = [
    SEED_FULL_MATRIX,
    SEED_INTRA_GROUP,
    SEED_CROSS_GROUP,
    SEED_SAME_GROUP_DIFFERENT_ROLE,
    SEED_THREE_REVIEWERS_PER_REVIEWEE,
    SEED_LEAD_LED,
]
