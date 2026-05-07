"""Unit tests for ``app/services/rules/predicates.py`` — Segment 13A
PR 2.

One test per operator (plus the missing-value rule from spec §9 and
the case-sensitive override).
"""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.schemas.rules import Predicate
from app.services.rules.predicates import evaluate_predicate


@dataclass
class Reviewer:
    email: str
    tag_1: str | None = None
    tag_2: str | None = None
    tag_3: str | None = None


@dataclass
class Reviewee:
    email_or_identifier: str
    tag_1: str | None = None
    tag_2: str | None = None
    tag_3: str | None = None


def _eval(predicate_dict, reviewer, reviewee):
    return evaluate_predicate(
        Predicate.model_validate(predicate_dict),
        reviewer=reviewer,
        reviewee=reviewee,
    )


def test_equals_literal_case_insensitive_by_default() -> None:
    r = Reviewer(email="a@x.edu", tag_1="Group01")
    e = Reviewee(email_or_identifier="b@x.edu")
    assert _eval(
        {"field": "reviewer.tag1", "operator": "equals", "operand": "group01"},
        r,
        e,
    )


def test_equals_case_sensitive_flag_distinguishes() -> None:
    r = Reviewer(email="a@x.edu", tag_1="Group01")
    e = Reviewee(email_or_identifier="b@x.edu")
    assert not _eval(
        {
            "field": "reviewer.tag1",
            "operator": "equals",
            "operand": "group01",
            "case_sensitive": True,
        },
        r,
        e,
    )


def test_not_equals_returns_true_when_distinct() -> None:
    r = Reviewer(email="a@x.edu", tag_1="A")
    e = Reviewee(email_or_identifier="b@x.edu")
    assert _eval(
        {"field": "reviewer.tag1", "operator": "not_equals", "operand": "B"},
        r,
        e,
    )


def test_in_matches_when_value_in_list() -> None:
    r = Reviewer(email="a@x.edu", tag_2="Lead")
    e = Reviewee(email_or_identifier="b@x.edu")
    assert _eval(
        {
            "field": "reviewer.tag2",
            "operator": "in",
            "operand": ["Senior", "Lead"],
        },
        r,
        e,
    )


def test_not_in_inverse_of_in() -> None:
    r = Reviewer(email="a@x.edu", tag_2="Junior")
    e = Reviewee(email_or_identifier="b@x.edu")
    assert _eval(
        {
            "field": "reviewer.tag2",
            "operator": "not_in",
            "operand": ["Senior", "Lead"],
        },
        r,
        e,
    )


def test_matches_regex() -> None:
    r = Reviewer(email="a@x.edu", tag_1="Group17")
    e = Reviewee(email_or_identifier="b@x.edu")
    assert _eval(
        {
            "field": "reviewer.tag1",
            "operator": "matches",
            "operand": r"Group\d+",
        },
        r,
        e,
    )
    assert not _eval(
        {
            "field": "reviewer.tag1",
            "operator": "matches",
            "operand": r"^Cohort",
        },
        r,
        e,
    )


def test_not_matches_inverse_of_matches() -> None:
    r = Reviewer(email="a@x.edu", tag_1="CohortA")
    e = Reviewee(email_or_identifier="b@x.edu")
    assert _eval(
        {
            "field": "reviewer.tag1",
            "operator": "not_matches",
            "operand": r"^Group",
        },
        r,
        e,
    )


def test_is_empty_treats_none_and_blank_as_empty() -> None:
    e = Reviewee(email_or_identifier="b@x.edu")
    assert _eval(
        {"field": "reviewer.tag3", "operator": "is_empty"},
        Reviewer(email="a@x.edu", tag_3=None),
        e,
    )
    assert _eval(
        {"field": "reviewer.tag3", "operator": "is_empty"},
        Reviewer(email="a@x.edu", tag_3="   "),
        e,
    )
    assert not _eval(
        {"field": "reviewer.tag3", "operator": "is_empty"},
        Reviewer(email="a@x.edu", tag_3="set"),
        e,
    )


def test_is_not_empty_inverse_of_is_empty() -> None:
    e = Reviewee(email_or_identifier="b@x.edu")
    assert _eval(
        {"field": "reviewer.tag3", "operator": "is_not_empty"},
        Reviewer(email="a@x.edu", tag_3="set"),
        e,
    )
    assert not _eval(
        {"field": "reviewer.tag3", "operator": "is_not_empty"},
        Reviewer(email="a@x.edu", tag_3=None),
        e,
    )


def test_same_as_compares_across_sides() -> None:
    r = Reviewer(email="a@x.edu", tag_1="GroupA")
    e_match = Reviewee(email_or_identifier="b@x.edu", tag_1="GroupA")
    e_mismatch = Reviewee(email_or_identifier="c@x.edu", tag_1="GroupB")
    assert _eval(
        {
            "field": "reviewer.tag1",
            "operator": "same_as",
            "operand": "reviewee.tag1",
        },
        r,
        e_match,
    )
    assert not _eval(
        {
            "field": "reviewer.tag1",
            "operator": "same_as",
            "operand": "reviewee.tag1",
        },
        r,
        e_mismatch,
    )


def test_different_from_inverse_of_same_as() -> None:
    r = Reviewer(email="a@x.edu", tag_1="GroupA")
    e_diff = Reviewee(email_or_identifier="b@x.edu", tag_1="GroupB")
    assert _eval(
        {
            "field": "reviewer.tag1",
            "operator": "different_from",
            "operand": "reviewee.tag1",
        },
        r,
        e_diff,
    )


def test_missing_field_returns_false_unless_is_empty() -> None:
    """Spec §9: predicates referencing a missing field evaluate to
    false unless the operator is ``is_empty``."""

    r = Reviewer(email="a@x.edu", tag_1=None)
    e = Reviewee(email_or_identifier="b@x.edu")
    for operator, operand in [
        ("equals", "anything"),
        ("not_equals", "anything"),
        ("in", ["a"]),
        ("not_in", ["a"]),
        ("matches", "."),
        ("not_matches", "."),
        ("same_as", "reviewee.tag1"),
        ("different_from", "reviewee.tag1"),
    ]:
        assert not _eval(
            {
                "field": "reviewer.tag1",
                "operator": operator,
                "operand": operand,
            },
            r,
            e,
        ), operator


def test_unknown_operator_raises_keyerror() -> None:
    """Defensive — Pydantic already rejects unknown operators at
    save time, but the dispatch table guards against a programmer
    error too."""

    fake = Predicate.model_construct(
        field="reviewer.tag1", operator="invented", operand="x"
    )
    with pytest.raises(KeyError):
        evaluate_predicate(
            fake,
            reviewer=Reviewer(email="a@x.edu"),
            reviewee=Reviewee(email_or_identifier="b@x.edu"),
        )
