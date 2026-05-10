"""Unit coverage for Segment 15D PR 3 — `pair_context.tag_N`
predicate-field grammar additions.

PR 3 ships:
- Schema acceptance of ``pair_context.tag1/2/3`` in
  ``ALLOWED_PREDICATE_FIELDS``.
- ``FIELD_MAP`` entries for the new family.
- ``get_field_value`` stub that returns ``None`` for any
  ``pair_context.*`` field — predicates evaluate to ``False`` (or
  ``True`` for ``is_empty``) without crashing the engine. PR 4
  swaps the stub for a real lookup against the ``relationships``
  table.
- Editor field-picker dropdown gains the three new options.

These tests pin the contract PR 4 will inherit: schema accepts the
fields; field-map round-trips; engine evaluation is safe; UI surface
exposes the option.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.rules import (
    ALLOWED_PREDICATE_FIELDS,
    Combinator,
    FilterRule,
    MatchRule,
    Predicate,
    RuleSetSchema,
)
from app.services.rules.fields import (
    FIELD_MAP,
    get_field_value,
    parse_field,
)


def test_pair_context_fields_in_allowed_set() -> None:
    assert "pair_context.tag1" in ALLOWED_PREDICATE_FIELDS
    assert "pair_context.tag2" in ALLOWED_PREDICATE_FIELDS
    assert "pair_context.tag3" in ALLOWED_PREDICATE_FIELDS


def test_predicate_accepts_pair_context_field() -> None:
    """The Pydantic validator on ``Predicate.field`` no longer rejects
    pair_context tag references."""

    p = Predicate(
        field="pair_context.tag1",
        operator="equals",
        operand="Mentor",
    )
    assert p.field == "pair_context.tag1"


def test_predicate_rejects_unknown_pair_context_slot() -> None:
    """Only tag1/2/3 are allowed; tag4 stays a validation error."""

    with pytest.raises(ValidationError):
        Predicate(
            field="pair_context.tag4",
            operator="equals",
            operand="x",
        )


def test_match_rule_with_pair_context_predicate() -> None:
    rule = MatchRule(
        id="r1",
        predicate=Predicate(
            field="pair_context.tag1",
            operator="equals",
            operand="Mentor",
        ),
    )
    assert rule.predicate.field == "pair_context.tag1"


def test_filter_rule_with_pair_context_predicate() -> None:
    rule = FilterRule(
        id="r1",
        predicate=Predicate(
            field="pair_context.tag1",
            operator="equals",
            operand="COI",
        ),
    )
    assert rule.predicate.field == "pair_context.tag1"


def test_ruleset_serializes_pair_context_rules() -> None:
    schema = RuleSetSchema(
        name="With pair context",
        description="",
        combinator=Combinator.ALL_OF,
        rules=[
            MatchRule(
                id="r1",
                predicate=Predicate(
                    field="pair_context.tag1",
                    operator="equals",
                    operand="Mentor",
                ),
            ),
        ],
    )
    dumped = schema.model_dump()
    assert dumped["rules"][0]["predicate"]["field"] == "pair_context.tag1"

    # And re-validates cleanly through ``RuleSetSchema`` (so the
    # storage round-trip the engine relies on works).
    rehydrated = RuleSetSchema.model_validate(dumped)
    assert rehydrated.rules[0].predicate.field == "pair_context.tag1"


def test_field_map_has_pair_context_entries() -> None:
    assert FIELD_MAP["pair_context.tag1"] == ("pair_context", "tag_1")
    assert FIELD_MAP["pair_context.tag2"] == ("pair_context", "tag_2")
    assert FIELD_MAP["pair_context.tag3"] == ("pair_context", "tag_3")


def test_parse_field_resolves_pair_context() -> None:
    assert parse_field("pair_context.tag1") == ("pair_context", "tag_1")


def test_get_field_value_pair_context_stub_returns_none() -> None:
    """PR 3 stub: any pair_context.* field returns None regardless of
    the reviewer / reviewee args. PR 4 swaps to a real lookup."""

    class _Stub:
        tag_1 = "Mentor"
        tag_2 = "COI"
        tag_3 = "Prior"

    reviewer = _Stub()
    reviewee = _Stub()
    assert (
        get_field_value(
            "pair_context.tag1", reviewer=reviewer, reviewee=reviewee
        )
        is None
    )
    assert (
        get_field_value(
            "pair_context.tag2", reviewer=reviewer, reviewee=reviewee
        )
        is None
    )
    assert (
        get_field_value(
            "pair_context.tag3", reviewer=reviewer, reviewee=reviewee
        )
        is None
    )


def test_get_field_value_reviewer_path_unchanged() -> None:
    """Regression guard: existing reviewer / reviewee resolution
    isn't disturbed by the new pair_context branch."""

    class _Reviewer:
        tag_1 = "A"

    class _Reviewee:
        tag_2 = "B"

    assert (
        get_field_value(
            "reviewer.tag1", reviewer=_Reviewer(), reviewee=None
        )
        == "A"
    )
    assert (
        get_field_value(
            "reviewee.tag2", reviewer=None, reviewee=_Reviewee()
        )
        == "B"
    )
