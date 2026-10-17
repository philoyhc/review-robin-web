"""Predicate evaluation per ``(reviewer, reviewee)`` pair.

One function per operator from ``spec/rule_based_assignment.md`` §4.4.
The dispatch table at the bottom is what
``app/services/rules/engine.py`` calls into.

Every field reads as a *set* of values (``fields.get_field_values``): at
most one for a roster or per-pair tag, any number for a person-level
pair tag (``reviewer.pair_tagN`` / ``reviewee.pair_tagN``). An empty
string is no value. The operators over that set (author, 2026-10-17;
``guide/archive/assignment_rule_clarify.md`` Item 2):

- ``equals`` / ``in`` / ``matches`` pass when some value matches, so a
  field with no value fails them; ``not_equals`` / ``not_in`` are their
  negation, so a field with no value **passes**.
- ``same_as`` passes when the two sides share a value, or both have
  none; ``different_from`` is its negation, so a value against no
  value passes and no value against no value fails.
- ``is_empty`` / ``is_not_empty`` test for no value / some value.
- ``not_matches`` keeps failing a field with no value.

All string comparisons trim leading/trailing whitespace and lowercase
both sides by default; a predicate may opt in to case-sensitive
comparison via ``Predicate.case_sensitive``.
"""

from __future__ import annotations

import re
from typing import Callable

from app.schemas.rules import Predicate
from app.services.rules.fields import FIELD_MAP, get_field_values


def _normalise(value: object | None, *, case_sensitive: bool) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text if case_sensitive else text.lower()


def _values(
    dotted: str, predicate: Predicate, *, reviewer: object, reviewee: object
) -> tuple[str, ...]:
    """The field's values, normalised, empties dropped.

    A tuple, not a set: this runs once per pair per rule, and nearly
    every field has at most one value, so the single-value path stays
    allocation-light at 1000 × 1000 rosters.
    """
    raws = get_field_values(dotted, reviewer=reviewer, reviewee=reviewee)
    if not raws:
        return ()
    case_sensitive = predicate.case_sensitive
    if len(raws) == 1:
        value = _normalise(raws[0], case_sensitive=case_sensitive)
        return () if value is None else (value,)
    normalised = (_normalise(raw, case_sensitive=case_sensitive) for raw in raws)
    return tuple(v for v in normalised if v is not None)


def _lhs(predicate: Predicate, *, reviewer: object, reviewee: object) -> tuple[str, ...]:
    return _values(predicate.field, predicate, reviewer=reviewer, reviewee=reviewee)


# ---------------------------------------------------------------------------
# Operator implementations
# ---------------------------------------------------------------------------


def _equals(predicate: Predicate, *, reviewer: object, reviewee: object) -> bool:
    rhs = _normalise(predicate.operand, case_sensitive=predicate.case_sensitive)
    if rhs is None:
        return False
    return rhs in _lhs(predicate, reviewer=reviewer, reviewee=reviewee)


def _not_equals(
    predicate: Predicate, *, reviewer: object, reviewee: object
) -> bool:
    return not _equals(predicate, reviewer=reviewer, reviewee=reviewee)


def _in(predicate: Predicate, *, reviewer: object, reviewee: object) -> bool:
    members = {
        _normalise(item, case_sensitive=predicate.case_sensitive)
        for item in (predicate.operand or [])
    }
    members.discard(None)
    return any(v in members for v in _lhs(predicate, reviewer=reviewer, reviewee=reviewee))


def _not_in(predicate: Predicate, *, reviewer: object, reviewee: object) -> bool:
    return not _in(predicate, reviewer=reviewer, reviewee=reviewee)


def _matches(
    predicate: Predicate, *, reviewer: object, reviewee: object
) -> bool:
    flags = 0 if predicate.case_sensitive else re.IGNORECASE
    return any(
        re.search(str(predicate.operand), value, flags=flags) is not None
        for value in _lhs(predicate, reviewer=reviewer, reviewee=reviewee)
    )


def _not_matches(
    predicate: Predicate, *, reviewer: object, reviewee: object
) -> bool:
    values = _lhs(predicate, reviewer=reviewer, reviewee=reviewee)
    if not values:
        return False
    flags = 0 if predicate.case_sensitive else re.IGNORECASE
    return all(
        re.search(str(predicate.operand), value, flags=flags) is None
        for value in values
    )


def _is_empty(
    predicate: Predicate, *, reviewer: object, reviewee: object
) -> bool:
    return not _lhs(predicate, reviewer=reviewer, reviewee=reviewee)


def _is_not_empty(
    predicate: Predicate, *, reviewer: object, reviewee: object
) -> bool:
    return bool(_lhs(predicate, reviewer=reviewer, reviewee=reviewee))


def _same_as(
    predicate: Predicate, *, reviewer: object, reviewee: object
) -> bool:
    operand = str(predicate.operand)
    if operand not in FIELD_MAP:
        # The schema admits only field operands here; defensive only.
        return False
    lhs = _lhs(predicate, reviewer=reviewer, reviewee=reviewee)
    rhs = _values(operand, predicate, reviewer=reviewer, reviewee=reviewee)
    if not lhs or not rhs:
        return not lhs and not rhs
    if len(lhs) == 1:
        return lhs[0] in rhs
    return any(v in rhs for v in lhs)


def _different_from(
    predicate: Predicate, *, reviewer: object, reviewee: object
) -> bool:
    return not _same_as(predicate, reviewer=reviewer, reviewee=reviewee)


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
