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
    required_field_ids,
)
from app.services.responses._branching import REQUIRED_GOVERNED_NEEDS_ANCHOR_MESSAGE


@dataclass
class Field:
    id: int
    label: str
    order: int
    required: bool = False
    visible: bool = True
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
        ("List", "Red,Green,Blue", "is_not", "Red, Blue", None),
        ("List", "Red,Green", "eq", "Red",
         "A List field's branch condition must be \"is\" or \"is not\"."),
        ("List", "Red,Green", "is_not", "Pink",
         "The branch condition names an option the list doesn't have: Pink."),
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
        # …and "is not" none of them; unanswered still closes it.
        ("is_not", "Red, Blue", "Green", True),
        ("is_not", "Red, Blue", " Blue ", False),
        ("is_not", "Red, Blue", "", False),
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
    # A required governed field needs an active required field outside
    # any branch (19T Item 11).
    assert branch_structure_errors([_parent(), _governed(required=True)]) == [
        ("Why", REQUIRED_GOVERNED_NEEDS_ANCHOR_MESSAGE)
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


@pytest.mark.parametrize(
    ("op", "value", "label"),
    [
        ("ge", "4", "Colour ≥ 4"),
        ("is", "Red, Blue", "Colour is Red or Blue"),
        ("is_not", "Red, Green, Blue", "Colour is not Red, Green or Blue"),
    ],
)
def test_the_condition_reads_as_the_builder_shows_it(op, value, label) -> None:
    from types import SimpleNamespace

    from app.web.views import branch_condition_label

    parent = SimpleNamespace(label="Colour", branch_op=op, branch_value=value)
    assert branch_condition_label(parent) == label


@pytest.mark.parametrize(
    ("value", "is_number"),
    [("4", True), ("-2.5", True), (".5", True), ("1e3", True), (" 7 ", True),
     ("1_000", False), ("0x10", False), ("inf", False), ("nan", False),
     ("", False), ("4.", True), ("١", False)],
)
def test_a_number_is_a_plain_decimal(value, is_number) -> None:
    """The cumulative read's finding 2: ``float()`` takes "1_000" and "nan"
    where the pages' ``Number()`` doesn't, so all three sides use one
    pattern (``DECIMAL_PATTERN``)."""
    assert (condition_error("Integer", None, "ge", value) is None) is is_number
    assert branch_is_open(_parent(branch_op="ne", branch_value="12345"), value) is is_number


def test_the_pages_use_the_services_number_pattern() -> None:
    """The builder's and the surface's scripts carry the same pattern, so
    none of the three reads "1_000" as a number."""
    from pathlib import Path

    from app.services.responses._branching import DECIMAL_PATTERN

    templates = Path(__file__).resolve().parents[2] / "app/web/templates"
    for name in ("operator/instruments_index.html", "reviewer/review_surface.html"):
        assert f"/^{DECIMAL_PATTERN}$/" in (templates / name).read_text(), name


def test_required_fields_are_the_required_ones_that_apply() -> None:
    """19T Item 11 — a required governed field is required only while its
    branch is open; an optional one never is."""
    fields = [
        _parent(required=True),
        _governed(required=True),
        Field(id=3, label="Note", order=2),
    ]
    assert required_field_ids(fields, {1: "5"}) == {1, 2}
    assert required_field_ids(fields, {1: "2"}) == {1}
    assert required_field_ids(fields, {}) == {1}


def test_applicability_walks_the_whole_chain() -> None:
    """19T Item 11's pre-positioning 3: a field under a closed ancestor is
    closed even while a stale answer below meets its own condition. The
    structure rules still refuse a chain (Item 14 lifts that)."""
    grandparent = _parent()
    parent = _governed(branch_op="ge", branch_value="4", _inline_data_type="Integer")
    child = Field(id=3, label="Why", order=2, branch_parent_id=2,
                  _inline_data_type="String")
    fields = [grandparent, parent, child]
    assert applicable_field_ids(fields, {1: "5", 2: "5"}) == {1, 2, 3}
    assert applicable_field_ids(fields, {1: "2", 2: "5"}) == {1}
    assert applicable_field_ids(fields, {1: "5", 2: "2"}) == {1, 2}
    assert branch_structure_errors(fields)


def test_a_cycle_closes_rather_than_recursing() -> None:
    first = Field(id=1, label="A", order=0, branch_parent_id=2,
                  branch_op="ge", branch_value="1")
    second = Field(id=2, label="B", order=1, branch_parent_id=1,
                   branch_op="ge", branch_value="1")
    assert applicable_field_ids([first, second], {1: "5", 2: "5"}) == set()


def test_a_required_governed_field_needs_an_active_required_anchor() -> None:
    """19T Item 11, the author's ruling on its pre-positioning 4: any active
    required field outside a branch will do, not only the parent."""
    notes = Field(id=3, label="Notes", order=2, _inline_data_type="String")
    # The parent itself.
    assert branch_structure_errors([_parent(required=True), _governed(required=True)]) == []
    # Another field, with the parent optional.
    assert branch_structure_errors(
        [_parent(), _governed(required=True), Field(**{**notes.__dict__, "required": True})]
    ) == []
    # A hidden anchor guarantees nothing: the submit gate skips it.
    assert branch_structure_errors(
        [_parent(required=True, visible=False), _governed(required=True)]
    ) == [("Why", REQUIRED_GOVERNED_NEEDS_ANCHOR_MESSAGE)]
    # A hidden required governed field counts nowhere, so it needs none.
    assert branch_structure_errors(
        [_parent(), _governed(required=True, visible=False), notes]
    ) == []
    # Every required governed field without an anchor is named.
    assert branch_structure_errors(
        [_parent(), _governed(required=True), _governed(id=3, label="How", order=2, required=True)]
    ) == [("Why", REQUIRED_GOVERNED_NEEDS_ANCHOR_MESSAGE),
          ("How", REQUIRED_GOVERNED_NEEDS_ANCHOR_MESSAGE)]
