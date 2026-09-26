"""Branching between response fields (19T Item 10;
``guide/advanced_instruments.md`` Item 1).

A **parent** field carries a condition (``branch_op`` + ``branch_value``)
and its **governed** fields point at it through ``branch_parent_id``. A
branch is **open** for an assignment when the parent is answered and the
answer satisfies the condition; otherwise it is **closed**, and its
governed fields can't be answered.

Everything here is pure: it reads fields and answers and never touches
the database, so the save rule, the reviewer surface and (later) the
required counts can share one definition of "open" and can't disagree.

Operators are stored as short tokens rather than symbols, because a
settings-CSV cell starting with ``=`` or ``>`` is read as a formula by
spreadsheet software.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from typing import Protocol

# Integer / Decimal parents compare against one number.
NUMERIC_OPS: dict[str, str] = {
    "eq": "=",
    "ne": "≠",
    "gt": ">",
    "ge": "≥",
    "lt": "<",
    "le": "≤",
}
# List parents: "is", one option or several comma-separated, read as
# *any of*.
LIST_OP = "is"
BRANCH_OPS: frozenset[str] = frozenset({*NUMERIC_OPS, LIST_OP})

# Inline ``data_type`` values a parent may have. String can't be a parent.
PARENT_DATA_TYPES: frozenset[str] = frozenset({"Integer", "Decimal", "List"})


class BranchField(Protocol):
    """The attributes of ``InstrumentResponseField`` this module reads."""

    id: int
    label: str
    order: int
    required: bool
    branch_parent_id: int | None
    branch_op: str | None
    branch_value: str | None
    _inline_data_type: str | None
    _inline_list_csv: str | None


def _list_items(text: str | None) -> list[str]:
    return [item.strip() for item in (text or "").split(",") if item.strip()]


def _finite_number(text: str | None) -> float | None:
    try:
        value = float((text or "").strip())
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def condition_error(
    data_type: str | None,
    list_csv: str | None,
    op: str | None,
    value: str | None,
) -> str | None:
    """Why a parent's condition can't be stored, or None when it can.

    ``data_type`` is the parent's inline type (``Integer`` / ``Decimal`` /
    ``List``); ``list_csv`` its List options."""
    if data_type not in PARENT_DATA_TYPES:
        return "A String field can't have a branch."
    if data_type == "List":
        if op != LIST_OP:
            return "A List field's branch condition must be \"is\"."
        chosen = _list_items(value)
        if not chosen:
            return "Choose at least one option for the branch condition."
        options = set(_list_items(list_csv))
        missing = [item for item in chosen if item not in options]
        if missing:
            return (
                "The branch condition names an option the list doesn't "
                f"have: {', '.join(missing)}."
            )
        return None
    if op not in NUMERIC_OPS:
        return "Choose a comparison for the branch condition."
    if _finite_number(value) is None:
        return "The branch condition needs a number."
    return None


def branch_is_open(parent: BranchField, answer: str | None) -> bool:
    """Whether ``parent``'s branch is open for an answer to ``parent``.

    An unanswered parent closes its branch, as does an answer that doesn't
    parse against the parent's type. A field with no condition has no
    branch to open."""
    op, value = parent.branch_op, parent.branch_value
    if not op or answer is None or not answer.strip():
        return False
    if op == LIST_OP:
        return answer.strip() in set(_list_items(value))
    left, right = _finite_number(answer), _finite_number(value)
    if left is None or right is None:
        return False
    if op == "eq":
        return left == right
    if op == "ne":
        return left != right
    if op == "gt":
        return left > right
    if op == "ge":
        return left >= right
    if op == "lt":
        return left < right
    if op == "le":
        return left <= right
    return False


def applicable_field_ids(
    fields: Iterable[BranchField],
    answer_by_field_id: Mapping[int, str | None],
) -> set[int]:
    """The ids of the fields an assignment can answer, given its answers.

    A field outside any branch always applies; a governed field applies
    while its parent's branch is open. On a group-scoped instrument the
    caller passes the group row's answers, since the parent's answer is
    shared across the row."""
    field_list = list(fields)
    by_id = {field.id: field for field in field_list}
    applicable: set[int] = set()
    for field in field_list:
        parent_id = field.branch_parent_id
        if parent_id is None:
            applicable.add(field.id)
            continue
        parent = by_id.get(parent_id)
        if parent is not None and branch_is_open(
            parent, answer_by_field_id.get(parent_id)
        ):
            applicable.add(field.id)
    return applicable


def branch_structure_errors(
    fields: Iterable[BranchField],
) -> list[tuple[str, str]]:
    """Every way an instrument's fields break the branching rules, as
    ``(field label, reason)`` pairs, empty when they don't.

    The rules (the design record's Rulings and 19T Item 10's answers): one
    level, so a parent is never governed; a parent is an Integer, Decimal
    or List field with a valid condition; a governed field is never
    required (Item 2 lifts this); a condition always governs at least one
    field, since a branch is one unit; and a branch's fields directly
    follow their parent in field order, so no field sits inside a branch
    it isn't part of."""
    field_list = list(fields)
    by_id = {field.id: field for field in field_list}
    governed_by_parent: dict[int, list[BranchField]] = {}
    errors: list[tuple[str, str]] = []
    for field in field_list:
        parent_id = field.branch_parent_id
        if parent_id is None:
            continue
        parent = by_id.get(parent_id)
        if parent is None:
            errors.append((field.label, "Its branch's parent field is missing."))
            continue
        if parent.branch_parent_id is not None:
            errors.append(
                (field.label, "A field inside a branch can't have a branch.")
            )
        if field.required:
            errors.append(
                (field.label, "A field inside a branch can't be required.")
            )
        governed_by_parent.setdefault(parent_id, []).append(field)
    for field in field_list:
        has_condition = bool(field.branch_op or field.branch_value)
        if field.id in governed_by_parent:
            msg = condition_error(
                field._inline_data_type,
                field._inline_list_csv,
                field.branch_op,
                field.branch_value,
            )
            if msg is not None:
                errors.append((field.label, msg))
        elif has_condition:
            errors.append(
                (field.label, "Its branch condition governs no field.")
            )
    ordered = sorted(field_list, key=lambda f: f.order)
    for index, field in enumerate(ordered):
        governed = governed_by_parent.get(field.id)
        if not governed:
            continue
        following = ordered[index + 1 : index + 1 + len(governed)]
        if {f.id for f in following} != {f.id for f in governed}:
            errors.append(
                (field.label, "A branch's fields must directly follow their parent.")
            )
    return errors
