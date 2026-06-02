"""Unit tests for ``app/schemas/observer_cohort_rule.py``.

Pins the persisted payload shape for ``Observer.cohort_rule``
before the service / route plumbing reads it.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.observer_cohort_rule import (
    CohortCombinator,
    CohortRule,
    CohortRuleSet,
)


def test_empty_ruleset_validates() -> None:
    rs = CohortRuleSet.model_validate({})
    assert rs.combinator == CohortCombinator.AND
    assert rs.rules == []


def test_ruleset_round_trip() -> None:
    payload = {
        "combinator": "AND",
        "rules": [
            {
                "field": "reviewer.tag1",
                "op": "IS THE SAME AS",
                "operand_tag": "observer.email",
                "operand_value": "",
            },
            {
                "field": "reviewee.tag1",
                "op": "IS",
                "operand_tag": "",
                "operand_value": "math",
            },
        ],
    }
    rs = CohortRuleSet.model_validate(payload)
    assert rs.model_dump(mode="json") == payload


def test_or_combinator_validates() -> None:
    rs = CohortRuleSet.model_validate(
        {"combinator": "OR", "rules": []}
    )
    assert rs.combinator == CohortCombinator.OR


def test_unknown_field_rejected() -> None:
    with pytest.raises(ValidationError, match="unknown cohort-rule field"):
        CohortRule.model_validate(
            {
                "field": "reviewer.tag9",
                "op": "IS",
                "operand_tag": "",
                "operand_value": "x",
            }
        )


def test_unknown_operator_rejected() -> None:
    with pytest.raises(ValidationError):
        CohortRule.model_validate(
            {
                "field": "reviewer.tag1",
                "op": "matches",
                "operand_tag": "",
                "operand_value": "x",
            }
        )


def test_field_operator_requires_operand_tag() -> None:
    with pytest.raises(
        ValidationError, match="requires operand_tag"
    ):
        CohortRule.model_validate(
            {
                "field": "reviewer.tag1",
                "op": "IS THE SAME AS",
                "operand_tag": "",
                "operand_value": "",
            }
        )


def test_field_operator_unknown_operand_tag_rejected() -> None:
    with pytest.raises(ValidationError, match="unknown cohort-rule operand_tag"):
        CohortRule.model_validate(
            {
                "field": "reviewer.tag1",
                "op": "IS THE SAME AS",
                "operand_tag": "observer.nope",
                "operand_value": "",
            }
        )


def test_field_operator_accepts_observer_operand() -> None:
    rule = CohortRule.model_validate(
        {
            "field": "reviewer.tag1",
            "op": "IS DIFFERENT FROM",
            "operand_tag": "observer.tag1",
            "operand_value": "",
        }
    )
    assert rule.operand_tag == "observer.tag1"


def test_field_operator_accepts_cross_roster_operand() -> None:
    rule = CohortRule.model_validate(
        {
            "field": "reviewer.tag1",
            "op": "IS THE SAME AS",
            "operand_tag": "reviewee.tag2",
            "operand_value": "",
        }
    )
    assert rule.operand_tag == "reviewee.tag2"


def test_value_operator_allows_empty_value() -> None:
    rule = CohortRule.model_validate(
        {
            "field": "reviewer.tag1",
            "op": "CONTAINS",
            "operand_tag": "",
            "operand_value": "",
        }
    )
    assert rule.operand_value == ""


def test_extra_keys_rejected() -> None:
    with pytest.raises(ValidationError):
        CohortRule.model_validate(
            {
                "field": "reviewer.tag1",
                "op": "IS",
                "operand_tag": "",
                "operand_value": "x",
                "junk": "no",
            }
        )
