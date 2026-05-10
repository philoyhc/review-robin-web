"""Predicate evaluation per ``(reviewer, reviewee)`` pair.

One function per operator from ``spec/rule_based_assignment.md`` §4.4.
The dispatch table at the bottom is what
``app/services/rules/engine.py`` calls into.

Empty / missing values follow spec §9: a predicate referencing a
missing field returns ``False`` unless the operator is
``is_empty``. ``app/services/rules/fields.py::get_field_value``
normalises empty strings to ``None`` so this module's operators see a
uniform notion of "missing".

All string comparisons trim leading/trailing whitespace and lowercase
both sides by default; a predicate may opt in to case-sensitive
comparison via ``Predicate.case_sensitive``.
"""

from __future__ import annotations

import re
from typing import Callable

from app.schemas.rules import Predicate
from app.services.rules.fields import get_field_value


def _normalise(value: object | None, *, case_sensitive: bool) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text if case_sensitive else text.lower()


def _resolve_operand(
    operand: object,
    *,
    reviewer: object,
    reviewee: object,
) -> object | None:
    """``same_as`` / ``different_from`` operands are field references on
    the opposite side. Other operators carry literal values."""

    if isinstance(operand, str) and operand in {
        "reviewer.email",
        "reviewer.tag1",
        "reviewer.tag2",
        "reviewer.tag3",
        "reviewee.email",
        "reviewee.tag1",
        "reviewee.tag2",
        "reviewee.tag3",
        "pair_context.tag1",
        "pair_context.tag2",
        "pair_context.tag3",
    }:
        return get_field_value(
            operand, reviewer=reviewer, reviewee=reviewee
        )
    return operand


# ---------------------------------------------------------------------------
# Operator implementations
# ---------------------------------------------------------------------------


def _equals(predicate: Predicate, *, reviewer: object, reviewee: object) -> bool:
    lhs = _normalise(
        get_field_value(predicate.field, reviewer=reviewer, reviewee=reviewee),
        case_sensitive=predicate.case_sensitive,
    )
    if lhs is None:
        return False
    rhs_raw = _resolve_operand(
        predicate.operand, reviewer=reviewer, reviewee=reviewee
    )
    rhs = _normalise(rhs_raw, case_sensitive=predicate.case_sensitive)
    if rhs is None:
        return False
    return lhs == rhs


def _not_equals(
    predicate: Predicate, *, reviewer: object, reviewee: object
) -> bool:
    lhs = _normalise(
        get_field_value(predicate.field, reviewer=reviewer, reviewee=reviewee),
        case_sensitive=predicate.case_sensitive,
    )
    if lhs is None:
        return False
    rhs_raw = _resolve_operand(
        predicate.operand, reviewer=reviewer, reviewee=reviewee
    )
    rhs = _normalise(rhs_raw, case_sensitive=predicate.case_sensitive)
    if rhs is None:
        return False
    return lhs != rhs


def _in(predicate: Predicate, *, reviewer: object, reviewee: object) -> bool:
    lhs = _normalise(
        get_field_value(predicate.field, reviewer=reviewer, reviewee=reviewee),
        case_sensitive=predicate.case_sensitive,
    )
    if lhs is None:
        return False
    members = [
        _normalise(item, case_sensitive=predicate.case_sensitive)
        for item in (predicate.operand or [])
    ]
    return lhs in members


def _not_in(predicate: Predicate, *, reviewer: object, reviewee: object) -> bool:
    lhs = _normalise(
        get_field_value(predicate.field, reviewer=reviewer, reviewee=reviewee),
        case_sensitive=predicate.case_sensitive,
    )
    if lhs is None:
        return False
    members = [
        _normalise(item, case_sensitive=predicate.case_sensitive)
        for item in (predicate.operand or [])
    ]
    return lhs not in members


def _matches(
    predicate: Predicate, *, reviewer: object, reviewee: object
) -> bool:
    lhs = _normalise(
        get_field_value(predicate.field, reviewer=reviewer, reviewee=reviewee),
        case_sensitive=predicate.case_sensitive,
    )
    if lhs is None:
        return False
    flags = 0 if predicate.case_sensitive else re.IGNORECASE
    return re.search(str(predicate.operand), lhs, flags=flags) is not None


def _not_matches(
    predicate: Predicate, *, reviewer: object, reviewee: object
) -> bool:
    lhs = _normalise(
        get_field_value(predicate.field, reviewer=reviewer, reviewee=reviewee),
        case_sensitive=predicate.case_sensitive,
    )
    if lhs is None:
        return False
    flags = 0 if predicate.case_sensitive else re.IGNORECASE
    return re.search(str(predicate.operand), lhs, flags=flags) is None


def _is_empty(
    predicate: Predicate, *, reviewer: object, reviewee: object
) -> bool:
    return (
        get_field_value(predicate.field, reviewer=reviewer, reviewee=reviewee)
        is None
    )


def _is_not_empty(
    predicate: Predicate, *, reviewer: object, reviewee: object
) -> bool:
    return (
        get_field_value(predicate.field, reviewer=reviewer, reviewee=reviewee)
        is not None
    )


def _same_as(
    predicate: Predicate, *, reviewer: object, reviewee: object
) -> bool:
    return _equals(predicate, reviewer=reviewer, reviewee=reviewee)


def _different_from(
    predicate: Predicate, *, reviewer: object, reviewee: object
) -> bool:
    return _not_equals(predicate, reviewer=reviewer, reviewee=reviewee)


_DISPATCH: dict[
    str, Callable[..., bool]
] = {
    "equals": _equals,
    "not_equals": _not_equals,
    "in": _in,
    "not_in": _not_in,
    "matches": _matches,
    "not_matches": _not_matches,
    "is_empty": _is_empty,
    "is_not_empty": _is_not_empty,
    "same_as": _same_as,
    "different_from": _different_from,
}


def evaluate_predicate(
    predicate: Predicate,
    *,
    reviewer: object,
    reviewee: object,
) -> bool:
    """Return ``True`` if the candidate pair satisfies the predicate."""

    op = _DISPATCH.get(predicate.operator)
    if op is None:
        # Pydantic's ``Predicate`` validator already rejects unknown
        # operators at save time; this branch is defensive only.
        raise KeyError(f"unknown predicate operator: {predicate.operator!r}")
    return op(predicate, reviewer=reviewer, reviewee=reviewee)
