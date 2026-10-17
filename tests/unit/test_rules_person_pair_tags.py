"""A pair tag as the pair's, or as a person's (author, 2026-10-17;
``guide/archive/assignment_rule_clarify.md`` Item 2).

``pair_context.tagN`` reads the one pair being judged: the operator's
"Link 2 pair tag IS Friend" keeps exactly the Friend pairs, and "IS NOT
COI" rules out exactly the COI pairs, every pair with no relationship
kept. ``reviewer.pair_tagN`` / ``reviewee.pair_tagN`` read every value a
person holds in that slot across their active pairs, whoever the other
side is.
"""

from __future__ import annotations

from dataclasses import dataclass

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


def test_a_reviewers_pair_tag_is_any_of_their_pairs() -> None:
    """Rana holds Friend through Carol alone, yet as a reviewer's tag it
    keeps every one of her pairs."""
    assert _pairs("reviewer.pair_tag1", "equals", "COI", LOOKUP) == {
        ("sam", "carol"),
        ("sam", "dan"),
        ("sam", "eve"),
    }
    assert _pairs("reviewer.pair_tag1", "not_equals", "COI", LOOKUP) == {
        ("rana", "carol"),
        ("rana", "dan"),
        ("rana", "eve"),
    }


def test_a_reviewees_pair_tag_filled_and_empty() -> None:
    assert _pairs("reviewee.pair_tag1", "is_not_empty", None, LOOKUP) == EVERY_PAIR
    assert _pairs("reviewee.pair_tag2", "is_empty", None, LOOKUP) == EVERY_PAIR
    lookup = {(1, 10): _Relationship(tag_1="Friend")}
    assert _pairs("reviewee.pair_tag1", "is_empty", None, lookup) == {
        (r, e) for r in ("rana", "sam") for e in ("dan", "eve")
    }


def test_same_as_compares_the_two_peoples_values() -> None:
    """Sam holds {Friend, COI}; every reviewee holds one of them, so all
    three share a value with Sam. Rana holds {Friend}: Eve, who holds
    only COI, does not."""
    assert _pairs("reviewee.pair_tag1", "same_as", "reviewer.pair_tag1", LOOKUP) == (
        EVERY_PAIR - {("rana", "eve")}
    )
    assert _pairs("reviewee.pair_tag1", "different_from", "reviewer.pair_tag1", LOOKUP) == {
        ("rana", "eve")
    }


def test_no_pair_tag_on_either_side_is_the_same() -> None:
    assert _pairs("reviewee.pair_tag2", "same_as", "reviewer.pair_tag2", LOOKUP) == EVERY_PAIR
    assert _pairs("reviewee.pair_tag2", "different_from", "reviewer.pair_tag2", LOOKUP) == set()


def test_inactive_relationships_give_no_one_a_pair_tag() -> None:
    lookup = {(1, 10): _Relationship(tag_1="Friend", status="inactive")}
    assert _pairs("reviewer.pair_tag1", "equals", "Friend", lookup) == set()
    assert _pairs("reviewee.pair_tag1", "is_empty", None, lookup) == EVERY_PAIR


def test_a_roster_tag_compares_with_a_pair_tag() -> None:
    """A single-valued tag is a set of one, so Carol's own tag can be the
    same as a reviewer's pair tag."""
    carol = _Reviewee(id=10, email_or_identifier="carol@example.edu", tag_1="friend")
    rule_set = RuleSetSchema(
        name="t",
        description="",
        combinator=Combinator.ALL_OF,
        rules=[
            MatchRule(
                id="r",
                predicate=Predicate(
                    field="reviewee.tag1", operator="same_as", operand="reviewer.pair_tag1"
                ),
            )
        ],
    )
    result = engine.evaluate(
        rule_set, reviewers=[RANA], reviewees=[carol], pair_context_lookup=LOOKUP
    )
    assert len(result.pairs) == 1
