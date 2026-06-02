"""Observer cohort materialiser — evaluate ``cohort_rule`` against
the session's rosters and return the in-cohort participant ids.

Reads ``Observer.cohort_rule`` (validated via
``app.schemas.observer_cohort_rule.CohortRuleSet``) and produces
a ``CohortIds`` pair: the set of reviewer ids + reviewee ids
the observer is scoped to.

Per-rule semantics:

- Left side (``field``) is the rule's roster attribute. MVP
  supports ``reviewer.tag1`` / ``reviewer.tag2`` / ``reviewer.tag3``
  and the ``reviewee.*`` mirror. ``pair_context.*`` is recognised
  by the schema but the materialiser treats it as an unmatched
  rule (returns empty side) until the pair-level join lands as
  a follow-up.
- Right side is either:
  - a literal value (``operand_value``) for ``IS`` / ``IS NOT`` /
    ``CONTAINS`` / ``DOES NOT CONTAIN``;
  - an observer attribute (``operand_tag`` starting with
    ``observer.``) for ``IS THE SAME AS`` / ``IS DIFFERENT FROM``.
    Cross-roster operands (``reviewer.X IS THE SAME AS
    reviewee.Y``) are recognised by the schema but the
    materialiser treats them as unmatched until the pair-level
    join lands.
- Comparisons are case-insensitive. ``CONTAINS`` /
  ``DOES NOT CONTAIN`` use substring (not regex) — explicitly
  not regex per ``guide/observers.md`` MVP scope.
- A rule that only constrains one side leaves the other side
  unconstrained (None). ``AND`` then intersects only the
  constrained sides; ``OR`` unions only the constrained sides.
- An ``observer`` with no saved rule returns an empty cohort.
  The operator must explicitly author a rule for observers to
  see anything.

The downstream consumers (W17 collation surface, the
By-instrument extract's cohort filter) call ``materialize_cohort``
once per observer per request and treat the result as opaque
``frozenset[int]`` bags.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Observer, Reviewee, Reviewer


@dataclass(frozen=True)
class CohortIds:
    """Materialised observer cohort. Empty frozensets mean the
    observer's rule didn't match any rows on that side."""

    reviewer_ids: frozenset[int]
    reviewee_ids: frozenset[int]


_REVIEWER_TAG_COLUMNS: dict[str, Any] = {
    "tag1": Reviewer.tag_1,
    "tag2": Reviewer.tag_2,
    "tag3": Reviewer.tag_3,
}

_REVIEWEE_TAG_COLUMNS: dict[str, Any] = {
    "tag1": Reviewee.tag_1,
    "tag2": Reviewee.tag_2,
    "tag3": Reviewee.tag_3,
}


def _observer_attr_value(observer: Observer, attr: str) -> str | None:
    """Map a canonical observer-side attr name (``"name"`` /
    ``"email"`` / ``"tag1"``) to the corresponding column value on
    the row. Returns ``None`` for unknown attrs or when the
    column is null/empty so a downstream comparison can skip
    cleanly without a SQL filter against ``NULL``."""
    if attr == "name":
        value = observer.display_name
    elif attr == "email":
        value = observer.email
    elif attr == "tag1":
        value = observer.tag_1
    else:
        return None
    return value if value else None


@dataclass(frozen=True)
class _RuleResult:
    """Per-rule outcome before AND / OR combination. ``None`` on
    a side means the rule didn't constrain that side (passes
    through unchanged when intersecting)."""

    reviewer_ids: frozenset[int] | None
    reviewee_ids: frozenset[int] | None


_UNMATCHED = _RuleResult(
    reviewer_ids=frozenset(), reviewee_ids=frozenset()
)


def _evaluate_rule(
    db: Session,
    session_id: int,
    observer: Observer,
    rule: dict[str, Any],
) -> _RuleResult:
    """Single-rule evaluation. See module docstring for the
    supported predicate shapes."""
    field = str(rule.get("field", ""))
    op = str(rule.get("op", ""))
    operand_tag = str(rule.get("operand_tag", ""))
    operand_value = str(rule.get("operand_value", ""))

    if not field or "." not in field:
        return _UNMATCHED

    namespace, attr = field.split(".", 1)

    # Resolve left-side column for the SQL filter.
    if namespace == "reviewer":
        column = _REVIEWER_TAG_COLUMNS.get(attr)
    elif namespace == "reviewee":
        column = _REVIEWEE_TAG_COLUMNS.get(attr)
    else:
        # ``pair_context.*`` — supported by the schema but the
        # pair-level join isn't in the MVP materialiser yet.
        return _UNMATCHED

    if column is None:
        return _UNMATCHED

    # Resolve right-side value.
    if op in ("IS THE SAME AS", "IS DIFFERENT FROM"):
        if not operand_tag.startswith("observer."):
            # Cross-roster operand (e.g. ``reviewer.tag1 IS THE
            # SAME AS reviewee.tag2``) — supported by the schema
            # but not by the MVP materialiser.
            return _UNMATCHED
        observer_attr = operand_tag.split(".", 1)[1]
        right_value = _observer_attr_value(observer, observer_attr)
        if right_value is None:
            # Observer's referenced attribute is empty → no
            # meaningful comparison; matches nothing.
            return _UNMATCHED
        # ``IS THE SAME AS`` → equality; ``IS DIFFERENT FROM`` →
        # inequality. Both case-insensitive.
        if op == "IS THE SAME AS":
            sql_predicate = func.lower(column) == right_value.lower()
        else:
            sql_predicate = func.lower(column) != right_value.lower()
    elif op == "IS":
        sql_predicate = func.lower(column) == operand_value.lower()
    elif op == "IS NOT":
        sql_predicate = func.lower(column) != operand_value.lower()
    elif op == "CONTAINS":
        # Case-insensitive substring; ``%`` escape isn't needed
        # because the operator types a plain value (no wildcards
        # promised). MVP scope: not regex.
        sql_predicate = func.lower(column).contains(operand_value.lower())
    elif op == "DOES NOT CONTAIN":
        sql_predicate = ~func.lower(column).contains(operand_value.lower())
    else:
        return _UNMATCHED

    if namespace == "reviewer":
        ids = frozenset(
            row[0]
            for row in db.execute(
                select(Reviewer.id).where(
                    Reviewer.session_id == session_id,
                    sql_predicate,
                )
            ).all()
        )
        return _RuleResult(reviewer_ids=ids, reviewee_ids=None)
    else:  # reviewee
        ids = frozenset(
            row[0]
            for row in db.execute(
                select(Reviewee.id).where(
                    Reviewee.session_id == session_id,
                    sql_predicate,
                )
            ).all()
        )
        return _RuleResult(reviewer_ids=None, reviewee_ids=ids)


def _all_reviewer_ids(db: Session, session_id: int) -> frozenset[int]:
    return frozenset(
        row[0]
        for row in db.execute(
            select(Reviewer.id).where(Reviewer.session_id == session_id)
        ).all()
    )


def _all_reviewee_ids(db: Session, session_id: int) -> frozenset[int]:
    return frozenset(
        row[0]
        for row in db.execute(
            select(Reviewee.id).where(Reviewee.session_id == session_id)
        ).all()
    )


def _combine_and(
    results: list[_RuleResult],
    *,
    session_id: int,
    db: Session,
) -> CohortIds:
    """Intersect constrained sides; sides where every rule was
    unconstrained fall back to the full roster on that side."""
    reviewer_constrained = [
        r.reviewer_ids for r in results if r.reviewer_ids is not None
    ]
    reviewee_constrained = [
        r.reviewee_ids for r in results if r.reviewee_ids is not None
    ]
    if reviewer_constrained:
        reviewer_ids = reviewer_constrained[0]
        for s in reviewer_constrained[1:]:
            reviewer_ids = reviewer_ids & s
    else:
        reviewer_ids = _all_reviewer_ids(db, session_id)
    if reviewee_constrained:
        reviewee_ids = reviewee_constrained[0]
        for s in reviewee_constrained[1:]:
            reviewee_ids = reviewee_ids & s
    else:
        reviewee_ids = _all_reviewee_ids(db, session_id)
    return CohortIds(
        reviewer_ids=frozenset(reviewer_ids),
        reviewee_ids=frozenset(reviewee_ids),
    )


def _combine_or(
    results: list[_RuleResult],
    *,
    session_id: int,
    db: Session,
) -> CohortIds:
    """Union constrained sides; sides where any rule was
    unconstrained fall back to the full roster on that side
    (OR with "all" = "all")."""
    reviewer_unconstrained = any(r.reviewer_ids is None for r in results)
    reviewee_unconstrained = any(r.reviewee_ids is None for r in results)
    if reviewer_unconstrained:
        reviewer_ids = _all_reviewer_ids(db, session_id)
    else:
        reviewer_ids = frozenset()
        for r in results:
            assert r.reviewer_ids is not None
            reviewer_ids = reviewer_ids | r.reviewer_ids
    if reviewee_unconstrained:
        reviewee_ids = _all_reviewee_ids(db, session_id)
    else:
        reviewee_ids = frozenset()
        for r in results:
            assert r.reviewee_ids is not None
            reviewee_ids = reviewee_ids | r.reviewee_ids
    return CohortIds(
        reviewer_ids=frozenset(reviewer_ids),
        reviewee_ids=frozenset(reviewee_ids),
    )


def materialize_cohort(db: Session, *, observer: Observer) -> CohortIds:
    """Evaluate ``observer.cohort_rule`` and return the in-cohort
    reviewer + reviewee ids for this observer.

    Empty cohort (no matches on either side) when:

    - ``observer.cohort_rule is None`` (the operator hasn't
      authored anything yet);
    - the saved rule has an empty ``rules`` list;
    - the rule's predicates don't resolve to any rows.
    """
    rule_set = observer.cohort_rule
    if not rule_set:
        return CohortIds(frozenset(), frozenset())
    rules = rule_set.get("rules") or []
    if not rules:
        return CohortIds(frozenset(), frozenset())

    combinator = str(rule_set.get("combinator", "AND")).upper()
    session_id = observer.session_id

    per_rule = [
        _evaluate_rule(db, session_id, observer, rule_dict)
        for rule_dict in rules
    ]

    if combinator == "OR":
        return _combine_or(per_rule, session_id=session_id, db=db)
    return _combine_and(per_rule, session_id=session_id, db=db)
