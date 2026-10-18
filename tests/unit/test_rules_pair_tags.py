"""A relationship tag judges the pair (author, 2026-10-18;
``guide/archive/pair_context_tags_further_clarify.md`` Item 1).

``pair_context.tagN`` reads the one pair being judged: "Link 2 pair tag
IS Friend" keeps exactly the Friend pairs, "IS NOT COI" rules out
exactly the COI pairs, and "IS FILLED" / "IS EMPTY" keep or rule out
the pairs carrying any value. A pair with no relationship has no value.
The person-level reading (``reviewer.pair_tagN`` / ``reviewee.pair_tagN``)
is retired.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from pydantic import ValidationError

from app.schemas.rules import Combinator, MatchRule, Predicate, RuleSetSchema
from app.services.rules import engine


@dataclass
class _Reviewer:
    id: int
    email: str
    tag_1: str | None = None


@dataclass
class _Reviewee:
    id: int
    email_or_identifier: str
    tag_1: str | None = None


@dataclass
class _Relationship:
    tag_1: str | None = None
    tag_2: str | None = None
    tag_3: str | None = None
    status: str = "active"


RANA = _Reviewer(id=1, email="rana@example.edu")
SAM = _Reviewer(id=2, email="sam@example.edu")
CAROL = _Reviewee(id=10, email_or_identifier="carol@example.edu")
DAN = _Reviewee(id=11, email_or_identifier="dan@example.edu")
EVE = _Reviewee(id=12, email_or_identifier="eve@example.edu")


def _pairs(field: str, operator: str, operand: object, lookup: dict) -> set[tuple[str, str]]:
    predicate: dict[str, object] = {"field": field, "operator": operator}
    if operand is not None:
        predicate["operand"] = operand
    rule_set = RuleSetSchema(
        name="t",
        description="",
        combinator=Combinator.ALL_OF,
        rules=[MatchRule(id="r", predicate=Predicate.model_validate(predicate))],
    )
    result = engine.evaluate(
        rule_set,
        reviewers=[RANA, SAM],
        reviewees=[CAROL, DAN, EVE],
        pair_context_lookup=lookup,
    )
    return {
        (reviewer.email.split("@")[0], reviewee.email_or_identifier.split("@")[0])
        for reviewer, reviewee in result.pairs
    }


# Rana–Carol is a Friend pair; Sam–Dan a Friend pair; Sam–Eve a COI pair.
LOOKUP = {
    (1, 10): _Relationship(tag_1="Friend"),
    (2, 11): _Relationship(tag_1="Friend"),
    (2, 12): _Relationship(tag_1="COI"),
}
EVERY_PAIR = {(r, e) for r in ("rana", "sam") for e in ("carol", "dan", "eve")}


def test_pair_tag_is_keeps_exactly_the_tagged_pairs() -> None:
    assert _pairs("pair_context.tag1", "equals", "Friend", LOOKUP) == {
        ("rana", "carol"),
        ("sam", "dan"),
    }


def test_pair_tag_is_not_rules_out_exactly_the_tagged_pairs() -> None:
    assert _pairs("pair_context.tag1", "not_equals", "COI", LOOKUP) == EVERY_PAIR - {
        ("sam", "eve")
    }


def test_pair_tag_filled_keeps_exactly_the_pairs_with_a_value() -> None:
    assert _pairs("pair_context.tag1", "is_not_empty", None, LOOKUP) == {
        ("rana", "carol"),
        ("sam", "dan"),
        ("sam", "eve"),
    }


def test_pair_tag_empty_rules_out_exactly_the_pairs_with_a_value() -> None:
    assert _pairs("pair_context.tag1", "is_empty", None, LOOKUP) == {
        ("rana", "dan"),
        ("rana", "eve"),
        ("sam", "carol"),
    }
    assert _pairs("pair_context.tag2", "is_empty", None, LOOKUP) == EVERY_PAIR


def test_an_inactive_relationship_has_no_value() -> None:
    lookup = {(1, 10): _Relationship(tag_1="Friend", status="inactive")}
    assert _pairs("pair_context.tag1", "equals", "Friend", lookup) == set()
    assert _pairs("pair_context.tag1", "is_not_empty", None, lookup) == set()
    assert _pairs("pair_context.tag1", "is_empty", None, lookup) == EVERY_PAIR


@pytest.mark.parametrize("field", ["reviewer.pair_tag1", "reviewee.pair_tag3"])
def test_a_persons_pair_tag_is_no_longer_a_field(field: str) -> None:
    with pytest.raises(ValidationError, match="unknown predicate field"):
        Predicate(field=field, operator="is_not_empty")
