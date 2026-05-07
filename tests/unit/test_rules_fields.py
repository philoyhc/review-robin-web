"""Unit tests for ``app/services/rules/fields.py`` — Segment 13A
PR 2."""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.services.rules.fields import (
    FIELD_MAP,
    get_field_value,
    parse_field,
)


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


def test_parse_field_maps_dotted_to_orm_attribute() -> None:
    assert parse_field("reviewer.tag1") == ("reviewer", "tag_1")
    assert parse_field("reviewee.tag3") == ("reviewee", "tag_3")
    assert parse_field("reviewer.email") == ("reviewer", "email")
    assert parse_field("reviewee.email") == ("reviewee", "email_or_identifier")


def test_parse_field_rejects_unknown_name() -> None:
    with pytest.raises(KeyError):
        parse_field("reviewer.unknown")


def test_get_field_value_reads_from_correct_side() -> None:
    r = Reviewer(email="a@x.edu", tag_1="GroupA")
    e = Reviewee(email_or_identifier="b@x.edu", tag_1="GroupB")
    assert get_field_value("reviewer.tag1", reviewer=r, reviewee=e) == "GroupA"
    assert get_field_value("reviewee.tag1", reviewer=r, reviewee=e) == "GroupB"


def test_get_field_value_normalises_blank_to_none() -> None:
    r = Reviewer(email="a@x.edu", tag_2="   ")
    e = Reviewee(email_or_identifier="b@x.edu", tag_3="")
    assert get_field_value("reviewer.tag2", reviewer=r, reviewee=e) is None
    assert get_field_value("reviewee.tag3", reviewer=r, reviewee=e) is None


def test_field_map_is_complete() -> None:
    """The mapping table covers every entry in
    ``ALLOWED_PREDICATE_FIELDS`` from the schemas module — the two
    must agree exactly."""

    from app.schemas.rules import ALLOWED_PREDICATE_FIELDS

    assert set(FIELD_MAP) == ALLOWED_PREDICATE_FIELDS
