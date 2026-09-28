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
import re
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
# List parents: "is" or "is not", against one option or several
# comma-separated, read as *any of* and *none of*.
LIST_OPS: dict[str, str] = {
    "is": "is",
    "is_not": "is not",
}
# 19T Item 12 — Integer / Decimal parents can also compare against a range,
# stored as ``low to high`` (``2 to 4``, ``-5 to -1``). "Inclusive" on
# outside counts the ends as outside, so ``out_inc`` is the complement of
# ``in_exc`` and ``out_exc`` of ``in_inc``. Accepted by Save and the
# settings CSV from rung 3, when the builder can show one (Codex on #2657).
RANGE_OPS: frozenset[str] = frozenset({"in_inc", "in_exc", "out_inc", "out_exc"})
RANGE_SEPARATOR = " to "

# The builder's select, spelled out, in the author's order (19T Item 12):
# ``(token, name, symbol)``. The symbols are what tooltips and the extract
# show (``condition_label``); a range's symbols sit around the label there.
NUMERIC_OP_CHOICES: tuple[tuple[str, str, str], ...] = (
    ("eq", "is equal to", "="),
    ("ne", "is not equal to", "≠"),
    ("ge", "is more than (inclusive)", "≥"),
    ("gt", "is more than (exclusive)", ">"),
    ("le", "is less than (inclusive)", "≤"),
    ("lt", "is less than (exclusive)", "<"),
    ("in_inc", "is within (inclusive)", "≤"),
    ("in_exc", "is within (exclusive)", "<"),
    ("out_inc", "is outside (inclusive)", "≤"),
    ("out_exc", "is outside (exclusive)", "<"),
)
LIST_OP_CHOICES: tuple[tuple[str, str, str], ...] = tuple(
    (token, name, name) for token, name in LIST_OPS.items()
)

BRANCH_OPS: frozenset[str] = frozenset({*NUMERIC_OPS, *LIST_OPS, *RANGE_OPS})

# 19T Item 13 — what a parent's condition does to its governed fields:
# ``show`` them (Item 10's kind: closed means unanswerable), or ``require``
# them (always answerable; required exactly while the condition holds).
# Stored on the parent as ``branch_mode``; null reads ``show``.
BRANCH_MODE_SHOW = "show"
BRANCH_MODE_REQUIRE = "require"
BRANCH_MODES: frozenset[str] = frozenset({BRANCH_MODE_SHOW, BRANCH_MODE_REQUIRE})

# 19T Item 11, the author's ruling on pre-positioning 4.
REQUIRED_GOVERNED_NEEDS_ANCHOR_MESSAGE = (
    "A field inside a branch can be required only when the instrument has "
    "an active required field outside any branch."
)

# Inline ``data_type`` values a parent may have. String can't be a parent.
PARENT_DATA_TYPES: frozenset[str] = frozenset({"Integer", "Decimal", "List"})


class BranchField(Protocol):
    """The attributes of ``InstrumentResponseField`` this module reads."""

    id: int
    label: str
    order: int
    required: bool
    visible: bool
    branch_parent_id: int | None
    branch_op: str | None
    branch_value: str | None
    _inline_data_type: str | None
    _inline_list_csv: str | None
    # ``branch_mode`` (19T Item 13) is read through :func:`branch_mode`,
    # which treats an object without it as Show.


def branch_mode(parent: BranchField | None) -> str:
    """A parent's mode, ``show`` or ``require`` (19T Item 13). Anything but
    ``require`` reads Show, so a null column and an object without one
    keep Item 10's meaning."""
    mode = getattr(parent, "branch_mode", None)
    return BRANCH_MODE_REQUIRE if mode == BRANCH_MODE_REQUIRE else BRANCH_MODE_SHOW


def _list_items(text: str | None) -> list[str]:
    return [item.strip() for item in (text or "").split(",") if item.strip()]


# A plain decimal number, and nothing else ``float()`` would take ("1_000",
# "inf", "nan"). The builder's and the reviewer surface's scripts use the
# same pattern before ``Number()``, so the three can't disagree on whether a
# condition or an answer is a number (the item's cumulative read).
# ASCII digits only: Python's ``\d`` also matches "١" and other Unicode
# digits, where JavaScript's doesn't (Codex on #2647).
DECIMAL_PATTERN = r"[+-]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?"
_DECIMAL = re.compile(DECIMAL_PATTERN)


def _finite_number(text: str | None) -> float | None:
    stripped = (text or "").strip()
    if not _DECIMAL.fullmatch(stripped):
        return None
    value = float(stripped)
    return value if math.isfinite(value) else None


def parse_range(text: str | None) -> tuple[float, float] | None:
    """A range condition's ``(low, high)``, or None when ``text`` isn't one:
    exactly two plain numbers joined by ``RANGE_SEPARATOR``, low strictly
    below high (the author's ruling, 19T Item 12)."""
    parts = (text or "").split(RANGE_SEPARATOR)
    if len(parts) != 2:
        return None
    low, high = _finite_number(parts[0]), _finite_number(parts[1])
    if low is None or high is None or not low < high:
        return None
    return low, high


def canonical_condition_value(op: str | None, value: str | None) -> str | None:
    """``value`` as the builder sends it back: stripped, and a range's ends
    stripped around one ``RANGE_SEPARATOR``. The settings CSV stores this, so
    a hand-spaced ``2 to  4`` doesn't later read as a changed condition to
    the lock on an answered branch (19T Item 12's cumulative read)."""
    if value is None:
        return None
    parts = value.split(RANGE_SEPARATOR)
    if op in RANGE_OPS and len(parts) == 2:
        return RANGE_SEPARATOR.join(part.strip() for part in parts)
    return value.strip() or None


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
        if op not in LIST_OPS:
            return "A List field's branch condition must be \"is\" or \"is not\"."
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
    if op in RANGE_OPS:
        return range_error(value)
    if op not in NUMERIC_OPS:
        return "Choose a comparison for the branch condition."
    if _finite_number(value) is None:
        return "The branch condition needs a number."
    return None


def range_error(value: str | None) -> str | None:
    """Why a range condition's ``low to high`` can't be stored, naming the
    end at fault (19T Item 12), or None when ``parse_range`` reads it."""
    parts = (value or "").split(RANGE_SEPARATOR)
    if len(parts) == 1:
        # Save strips the joined value, so an empty end arrives as "2 to"
        # or "to 4"; name that end rather than the shape.
        text = parts[0].strip()
        if text == "to" or text.endswith(" to"):
            parts = [text[:-2], ""]
        elif text.startswith("to "):
            parts = ["", text[2:]]
    if len(parts) != 2:
        return "The branch condition needs a range: a low and a high number."
    low, high = _finite_number(parts[0]), _finite_number(parts[1])
    if low is None:
        return "The range's low end needs a number."
    if high is None:
        return "The range's high end needs a number."
    if not low < high:
        return "The range's low end must be below its high end."
    return None


def condition_label(parent: BranchField) -> str:
    """A parent's condition as people read it: "Rating ≥ 4", "Colour is Red
    or Blue", "Colour is not Red or Blue". The reviewer surface's hint on a
    closed cell and the by-instrument extract's metadata both use it."""
    op, value = parent.branch_op or "", (parent.branch_value or "").strip()
    if op in RANGE_OPS and parse_range(value) is not None:
        # The ends as the operator typed them ("1.50" stays "1.50"), after
        # the field's name like every other condition, so a negative low end
        # never starts an extract cell (a formula to spreadsheet software).
        low, high = (part.strip() for part in value.split(RANGE_SEPARATOR))
        return {
            "in_inc": f"{parent.label} ≥ {low} and ≤ {high}",
            "in_exc": f"{parent.label} > {low} and < {high}",
            "out_inc": f"{parent.label} ≤ {low} or ≥ {high}",
            "out_exc": f"{parent.label} < {low} or > {high}",
        }[op]
    if op in LIST_OPS:
        options = _list_items(value)
        joined = (
            ", ".join(options[:-1]) + " or " + options[-1]
            if len(options) > 1
            else "".join(options)
        )
        return f"{parent.label} {LIST_OPS[op]} {joined}"
    return f"{parent.label} {NUMERIC_OPS.get(op, op)} {value}"


def branch_is_open(parent: BranchField, answer: str | None) -> bool:
    """Whether ``parent``'s branch is open for an answer to ``parent``.

    An unanswered parent closes its branch, as does an answer that doesn't
    parse against the parent's type. A field with no condition has no
    branch to open."""
    op, value = parent.branch_op, parent.branch_value
    if not op or answer is None or not answer.strip():
        return False
    if op in LIST_OPS:
        chosen = answer.strip() in set(_list_items(value))
        return chosen if op == "is" else not chosen
    if op in RANGE_OPS:
        x, bounds = _finite_number(answer), parse_range(value)
        if x is None or bounds is None:
            return False
        low, high = bounds
        if op == "in_inc":
            return low <= x <= high
        if op == "in_exc":
            return low < x < high
        if op == "out_inc":
            return x <= low or x >= high
        return x < low or x > high
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
    while its parent applies *and* the parent's branch is open. Under a
    require-mode parent (19T Item 13) the condition decides only whether
    the field is required, so the field applies whenever its parent does. The walk
    goes up the whole chain, so a field under a closed ancestor is closed
    even while a stale answer below it still meets its own condition.
    Branches are one level deep today (19T Item 14 lifts that), where
    this is the same answer as checking the parent alone; walking the
    chain here is 19T Item 11's pre-positioning 3. On a group-scoped
    instrument the caller passes the group row's answers, since the
    parent's answer is shared across the row."""
    field_list = list(fields)
    by_id = {field.id: field for field in field_list}
    memo: dict[int, bool] = {}

    def applies(field: BranchField, seen: frozenset[int]) -> bool:
        if field.id in memo:
            return memo[field.id]
        parent_id = field.branch_parent_id
        if parent_id is None:
            result = True
        else:
            parent = by_id.get(parent_id)
            # A missing parent, or a cycle the structure rules refuse,
            # closes the branch rather than recursing forever.
            result = (
                parent is not None
                and parent.id not in seen
                and applies(parent, seen | {field.id})
                and (
                    branch_mode(parent) == BRANCH_MODE_REQUIRE
                    or branch_is_open(parent, answer_by_field_id.get(parent_id))
                )
            )
        memo[field.id] = result
        return result

    return {field.id for field in field_list if applies(field, frozenset())}


def required_field_ids(
    fields: Iterable[BranchField],
    answer_by_field_id: Mapping[int, str | None],
) -> set[int]:
    """The ids of the fields an assignment must answer, given its answers.

    A required field is required only while it applies, so a required
    governed field behind a closed branch is neither required nor missing
    (19T Item 11). Every required count goes through this one function
    rather than testing ``required`` and applicability itself, so a second
    kind of condition (Item 13), which makes a field required rather than
    shown, changes only this (Item 11's pre-positioning 1).

    Under a require-mode parent (Item 13) a governed field's own
    ``required`` is ignored: it is required exactly while it applies and
    its parent's condition holds, an unanswered parent holding nothing.
    A hidden one never is: its R is grayed out in the builder, so the
    operator couldn't otherwise stop a field no reviewer sees from being
    owed (the cumulative read on #2676)."""
    field_list = list(fields)
    by_id = {field.id: field for field in field_list}
    applicable = applicable_field_ids(field_list, answer_by_field_id)
    required: set[int] = set()
    for field in field_list:
        if field.id not in applicable:
            continue
        parent = by_id.get(field.branch_parent_id)
        if parent is not None and branch_mode(parent) == BRANCH_MODE_REQUIRE:
            if field.visible and branch_is_open(
                parent, answer_by_field_id.get(parent.id)
            ):
                required.add(field.id)
        elif field.required:
            required.add(field.id)
    return required


def may_be_required_field_ids(fields: Iterable[BranchField]) -> set[int]:
    """The ids of the fields some assignment could be required to answer:
    what a "*" marks and what "has a required field" asks (19T Item 13).
    A visible field under a require-mode parent may be, whatever its own
    ``required`` says, and a hidden one never is (as
    :func:`required_field_ids`); any other field may be when it is
    ``required``."""
    field_list = list(fields)
    by_id = {field.id: field for field in field_list}
    out: set[int] = set()
    for field in field_list:
        parent = by_id.get(field.branch_parent_id)
        if parent is not None and branch_mode(parent) == BRANCH_MODE_REQUIRE:
            if field.visible:
                out.add(field.id)
        elif field.required:
            out.add(field.id)
    return out


def branch_structure_errors(
    fields: Iterable[BranchField],
) -> list[tuple[str, str]]:
    """Every way an instrument's fields break the branching rules, as
    ``(field label, reason)`` pairs, empty when they don't.

    The rules (the design record's Rulings and 19T Item 10's answers): one
    level, so a parent is never governed; a parent is an Integer, Decimal
    or List field with a valid condition; a condition always governs at
    least one field, since a branch is one unit; and a branch's fields
    directly follow their parent in field order, so no field sits inside a
    branch it isn't part of.

    **A required governed field needs an active required field outside
    any branch** (19T Item 11, the author's ruling on its pre-positioning
    4). The reviewer rollups count an assignment with no required field
    complete only once it has a response row, and a required governed
    field behind a closed branch isn't required; an active required
    ungoverned field is answered at every submit, so a submit always
    leaves a row. It holds at any depth and for any kind of condition,
    and only a visible governed field needs it, since a hidden one counts
    nowhere on the reviewer side. A field under a require-mode parent (19T
    Item 13) counts as a required governed field whatever its own
    ``required``, since an unanswered parent leaves it optional."""
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
        governed_by_parent.setdefault(parent_id, []).append(field)
    has_anchor = any(
        f.required and f.visible and f.branch_parent_id is None for f in field_list
    )
    if not has_anchor:
        may_be_required = may_be_required_field_ids(field_list)
        errors.extend(
            (field.label, REQUIRED_GOVERNED_NEEDS_ANCHOR_MESSAGE)
            for field in field_list
            if field.branch_parent_id is not None
            and field.id in may_be_required
            and field.visible
        )
    for field in field_list:
        # A mode (19T Item 13) belongs to a condition, so a lone one is an
        # orphan too.
        has_condition = bool(
            field.branch_op or field.branch_value or getattr(field, "branch_mode", None)
        )
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
