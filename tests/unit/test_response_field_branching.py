"""19T Item 10 rung 2 — the branching rules in
``app/services/responses/_branching.py``: conditions, whether a branch is
open, which fields an assignment can answer, and the structure rules."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.services.responses import (
    applicable_field_ids,
    branch_is_open,
    branch_structure_errors,
    condition_error,
)


@dataclass
class Field:
    id: int
    label: str
    order: int
    required: bool = False
    branch_parent_id: int | None = None
    branch_op: str | None = None
    branch_value: str | None = None
    _inline_data_type: str | None = "Integer"
    _inline_list_csv: str | None = None


def _parent(**kw) -> Field:
    return Field(**{"id": 1, "label": "Rating", "order": 0,
                    "branch_op": "ge", "branch_value": "4", **kw})


def _governed(**kw) -> Field:
    return Field(**{"id": 2, "label": "Why", "order": 1,
                    "branch_parent_id": 1, "_inline_data_type": "String", **kw})


@pytest.mark.parametrize(
    ("data_type", "list_csv", "op", "value", "expected"),
    [
        ("Integer", None, "ge", "4", None),
        ("Decimal", None, "lt", "2.5", None),
        ("String", None, "eq", "x", "A String field can't have a branch."),
        ("Integer", None, "is", "4", "Choose a comparison for the branch condition."),
        ("Integer", None, "eq", "", "The branch condition needs a number."),
        ("Integer", None, "eq", "inf", "The branch condition needs a number."),
        ("List", "Red,Green,Blue", "is", "Red, Blue", None),
        ("List", "Red,Green", "eq", "Red", "A List field's branch condition must be \"is\"."),
        ("List", "Red,Green", "is", " , ", "Choose at least one option for the branch condition."),
        ("List", "Red,Green", "is", "Red, Pink",
         "The branch condition names an option the list doesn't have: Pink."),
    ],
)
def test_condition_error(data_type, list_csv, op, value, expected) -> None:
    assert condition_error(data_type, list_csv, op, value) == expected


@pytest.mark.parametrize(
    ("op", "value", "answer", "is_open"),
    [
        ("eq", "3", "3", True),
        ("eq", "3", "3.0", True),
        ("ne", "3", "3", False),
        ("gt", "3", "4", True),
        ("gt", "3", "3", False),
        ("ge", "3", "3", True),
        ("lt", "3", "2", True),
        ("le", "3", "4", False),
        # An unanswered parent closes its branch, and so does an answer
        # that doesn't parse as a number.
        ("ge", "3", None, False),
        ("ge", "3", "  ", False),
        ("ge", "3", "many", False),
        # List parents: "is" any of the chosen options.
        ("is", "Red, Blue", "Blue", True),
        ("is", "Red, Blue", " Red ", True),
        ("is", "Red, Blue", "Green", False),
        # A field with no condition has no branch to open.
        (None, None, "3", False),
    ],
)
def test_branch_is_open(op, value, answer, is_open) -> None:
    assert branch_is_open(_parent(branch_op=op, branch_value=value), answer) is is_open


def test_applicable_fields_follow_the_parent_answer() -> None:
    fields = [_parent(), _governed(), Field(id=3, label="Notes", order=2)]
    assert applicable_field_ids(fields, {1: "5"}) == {1, 2, 3}
    assert applicable_field_ids(fields, {1: "2"}) == {1, 3}
    # Unanswered: the branch is closed, the rest still apply.
    assert applicable_field_ids(fields, {}) == {1, 3}


def test_a_valid_branch_has_no_structure_errors() -> None:
    assert branch_structure_errors(
        [_parent(), _governed(), _governed(id=3, label="How", order=2)]
    ) == []


def test_structure_errors_name_each_broken_rule() -> None:
    # One level: a governed field can't itself have a branch.
    nested = [
        _parent(),
        _governed(_inline_data_type="Integer", branch_op="eq", branch_value="1"),
        _governed(id=3, label="Deep", order=2, branch_parent_id=2),
    ]
    assert ("Deep", "A field inside a branch can't have a branch.") in (
        branch_structure_errors(nested)
    )
    # Governed fields are never required (Item 2 lifts this).
    assert branch_structure_errors([_parent(), _governed(required=True)]) == [
        ("Why", "A field inside a branch can't be required.")
    ]
    # A String parent.
    assert branch_structure_errors(
        [_parent(_inline_data_type="String"), _governed()]
    ) == [("Rating", "A String field can't have a branch.")]
    # A branch is one unit: a condition always governs a field.
    assert branch_structure_errors([_parent()]) == [
        ("Rating", "Its branch condition governs no field.")
    ]
    # A parent outside the instrument's fields.
    assert branch_structure_errors([_governed()]) == [
        ("Why", "Its branch's parent field is missing.")
    ]


def test_a_branch_must_directly_follow_its_parent() -> None:
    notes = Field(id=3, label="Notes", order=1)
    assert branch_structure_errors(
        [_parent(), notes, _governed(order=2)]
    ) == [("Rating", "A branch's fields must directly follow their parent.")]
