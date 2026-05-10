"""Unit tests for ``app/schemas/rules.py`` — Segment 13A PR 1.

Covers the typed in-memory shape of a RuleSet:

- Predicate validation (field allow-list, operator-operand pairing,
  regex compilation, list operands non-empty, case-sensitive flag).
- Discriminated-union dispatch on ``Rule.kind``.
- Quota min/max ordering rule.
- Composite rule recursion + uniqueness of rule ids inside a RuleSet.
- Golden round-trip of a non-trivial RuleSet through
  ``model_dump`` → ``model_validate``.
"""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas.rules import (
    ALLOWED_PREDICATE_FIELDS,
    Combinator,
    CompositeOp,
    CompositeRule,
    FilterRule,
    MatchRule,
    Predicate,
    QuotaRule,
    QuotaScope,
    QuotaSelection,
    Rule,
    RuleSetSchema,
    RuleSetScope,
    SelectionStrategy,
)


# ---------------------------------------------------------------------------
# Predicate
# ---------------------------------------------------------------------------


def test_predicate_equals_with_literal_validates() -> None:
    pred = Predicate(
        field="reviewer.tag1", operator="equals", operand="Group01"
    )
    assert pred.field == "reviewer.tag1"
    assert pred.operator == "equals"
    assert pred.operand == "Group01"
    assert pred.case_sensitive is False


def test_predicate_unknown_field_rejected() -> None:
    with pytest.raises(ValidationError) as exc:
        Predicate(field="reviewer.tag9", operator="equals", operand="x")
    assert "unknown predicate field" in str(exc.value)


def test_predicate_same_as_requires_field_operand_on_other_side() -> None:
    pred = Predicate(
        field="reviewer.tag1",
        operator="same_as",
        operand="reviewee.tag1",
    )
    assert pred.operand == "reviewee.tag1"

    with pytest.raises(ValidationError) as exc:
        Predicate(
            field="reviewer.tag1",
            operator="same_as",
            operand="reviewer.tag2",
        )
    assert "compares across populations" in str(exc.value)


def test_predicate_in_requires_non_empty_string_list() -> None:
    pred = Predicate(
        field="reviewer.tag2",
        operator="in",
        operand=["Senior", "Lead"],
    )
    assert pred.operand == ["Senior", "Lead"]

    with pytest.raises(ValidationError):
        Predicate(field="reviewer.tag2", operator="in", operand=[])


def test_predicate_matches_requires_compilable_regex() -> None:
    pred = Predicate(
        field="reviewer.tag1", operator="matches", operand=r"Group\d+"
    )
    assert pred.operand == r"Group\d+"

    with pytest.raises(ValidationError) as exc:
        Predicate(
            field="reviewer.tag1", operator="matches", operand="["
        )
    assert "does not" in str(exc.value).lower()


def test_predicate_is_empty_takes_no_operand() -> None:
    pred = Predicate(field="reviewee.tag3", operator="is_empty")
    assert pred.operand is None

    with pytest.raises(ValidationError) as exc:
        Predicate(
            field="reviewee.tag3", operator="is_empty", operand="x"
        )
    assert "takes no operand" in str(exc.value)


def test_predicate_case_sensitive_flag_round_trips() -> None:
    pred = Predicate(
        field="reviewer.email",
        operator="equals",
        operand="alice@example.edu",
        case_sensitive=True,
    )
    dumped = pred.model_dump()
    assert dumped["case_sensitive"] is True
    assert Predicate.model_validate(dumped).case_sensitive is True


def test_allowed_predicate_fields_match_spec_vocabulary() -> None:
    """Spec §4.4 names email + tag1/2/3 on each side; Segment 15D PR 3
    extends the allow-list with ``pair_context.tag1/2/3`` (per-pair
    attributes living on the new ``relationships`` table)."""

    expected = {
        f"{side}.{name}"
        for side in ("reviewer", "reviewee")
        for name in ("email", "tag1", "tag2", "tag3")
    } | {
        f"pair_context.tag{n}" for n in (1, 2, 3)
    }
    assert ALLOWED_PREDICATE_FIELDS == expected


# ---------------------------------------------------------------------------
# Rule kinds + discriminated union
# ---------------------------------------------------------------------------


def test_filter_rule_round_trips() -> None:
    rule = FilterRule(
        id="no_cross_region",
        predicate=Predicate(
            field="reviewer.tag3",
            operator="different_from",
            operand="reviewee.tag3",
        ),
    )
    assert rule.kind == "FILTER"
    assert rule.enabled is True


def test_match_rule_round_trips() -> None:
    rule = MatchRule(
        id="same_group",
        predicate=Predicate(
            field="reviewer.tag1",
            operator="same_as",
            operand="reviewee.tag1",
        ),
    )
    assert rule.kind == "MATCH"


def test_quota_rule_min_must_not_exceed_max() -> None:
    QuotaRule(
        id="three_each",
        scope=QuotaScope.PER_REVIEWEE,
        min=3,
        max=3,
        selection=QuotaSelection(strategy=SelectionStrategy.RANDOM, seed=42),
    )

    with pytest.raises(ValidationError) as exc:
        QuotaRule(
            id="bad",
            scope=QuotaScope.PER_REVIEWEE,
            min=5,
            max=3,
            selection=QuotaSelection(
                strategy=SelectionStrategy.ROUND_ROBIN
            ),
        )
    assert "exceeds max" in str(exc.value)


def test_composite_rule_requires_at_least_one_child() -> None:
    with pytest.raises(ValidationError):
        CompositeRule(id="empty", op=CompositeOp.AND, rules=[])


def test_composite_rule_nests_recursively() -> None:
    inner = CompositeRule(
        id="inner",
        op=CompositeOp.OR,
        rules=[
            MatchRule(
                id="a",
                predicate=Predicate(
                    field="reviewer.tag1",
                    operator="same_as",
                    operand="reviewee.tag1",
                ),
            ),
        ],
    )
    outer = CompositeRule(
        id="outer",
        op=CompositeOp.AND,
        rules=[
            inner,
            FilterRule(
                id="not_self",
                predicate=Predicate(
                    field="reviewer.email",
                    operator="not_equals",
                    operand="reviewee.email",
                ),
            ),
        ],
    )
    assert outer.rules[0].kind == "COMPOSITE"
    assert outer.rules[1].kind == "FILTER"


def test_rule_discriminator_dispatches_on_kind() -> None:
    """A bare ``kind`` field on a dict drives Pydantic's
    discriminated-union resolution into the right concrete subclass."""

    rule_adapter = TypeAdapter(Rule)
    payload = {
        "id": "r1",
        "kind": "QUOTA",
        "scope": "PER_REVIEWER",
        "min": None,
        "max": 5,
        "selection": {"strategy": "ROUND_ROBIN"},
    }
    rule = rule_adapter.validate_python(payload)
    assert isinstance(rule, QuotaRule)


def test_rule_discriminator_rejects_unknown_kind() -> None:
    rule_adapter = TypeAdapter(Rule)
    with pytest.raises(ValidationError):
        rule_adapter.validate_python({"id": "r1", "kind": "INVENTED"})


# ---------------------------------------------------------------------------
# RuleSet
# ---------------------------------------------------------------------------


def test_ruleset_round_trips_through_model_dump() -> None:
    ruleset = RuleSetSchema(
        name="Lead-led review",
        description="Intra-group OR cross-group leads.",
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
                        id="rev_lead_diff_group",
                        predicate=Predicate(
                            field="reviewer.tag1",
                            operator="different_from",
                            operand="reviewee.tag1",
                        ),
                    ),
                ],
            ),
        ],
    )

    dumped = ruleset.model_dump()
    rebuilt = RuleSetSchema.model_validate(dumped)
    assert rebuilt.model_dump() == dumped
    assert rebuilt.combinator == Combinator.ANY_OF
    assert len(rebuilt.rules) == 2
    assert rebuilt.rules[1].kind == "COMPOSITE"


def test_ruleset_rejects_duplicate_rule_ids_anywhere_in_tree() -> None:
    with pytest.raises(ValidationError) as exc:
        RuleSetSchema(
            name="dup",
            combinator=Combinator.ALL_OF,
            rules=[
                MatchRule(
                    id="a",
                    predicate=Predicate(
                        field="reviewer.tag1",
                        operator="same_as",
                        operand="reviewee.tag1",
                    ),
                ),
                CompositeRule(
                    id="composite",
                    op=CompositeOp.AND,
                    rules=[
                        FilterRule(
                            id="a",
                            predicate=Predicate(
                                field="reviewer.email",
                                operator="not_equals",
                                operand="reviewee.email",
                            ),
                        )
                    ],
                ),
            ],
        )
    assert "duplicate rule id" in str(exc.value)


def test_ruleset_defaults_to_personal_scope_with_excluded_self_reviews() -> None:
    ruleset = RuleSetSchema(
        name="empty",
        combinator=Combinator.ALL_OF,
    )
    assert ruleset.scope == RuleSetScope.personal
    assert ruleset.options.excludeSelfReviews is True
    assert ruleset.metadata.isSeed is False
    assert ruleset.rules == []


def test_ruleset_extra_keys_rejected() -> None:
    """``extra='forbid'`` keeps imports tight — unknown keys would be a
    schema-version mismatch rather than silent drift."""

    with pytest.raises(ValidationError):
        RuleSetSchema.model_validate(
            {
                "name": "x",
                "combinator": "ALL_OF",
                "rogue_key": True,
            }
        )
