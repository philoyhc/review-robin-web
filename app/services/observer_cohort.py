"""Observer cohort materialiser — evaluate ``cohort_rule`` against
the session's assignments and return the in-cohort assignment ids
plus per-side distinct counts.

The rule partitions assignments using reviewer / reviewee tag
predicates (and optionally observer-attribute operands). Each
assignment row binds one reviewer + one reviewee; the rule's
per-row predicate decides whether that row is in the observer's
cohort.

Per-rule semantics:

- Left side (``field``) is the rule's roster attribute. Supports
  ``reviewer.tag1`` / ``reviewer.tag2`` / ``reviewer.tag3`` and
  the ``reviewee.*`` mirror. ``pair_context.*`` is recognised by
  the schema but the predicate treats it as unmatched (pair-level
  join deferred — see ``guide/archive/observers_clean_up.md`` item 13).
- Right side is either:
  - a literal value (``operand_value``) for ``IS`` / ``IS NOT`` /
    ``CONTAINS`` / ``DOES NOT CONTAIN``;
  - an observer attribute (``operand_tag`` starting with
    ``observer.``) for ``IS THE SAME AS`` / ``IS DIFFERENT FROM``.
    Cross-roster operands (``reviewer.X IS THE SAME AS
    reviewee.Y``) are recognised by the schema but the predicate
    treats them as unmatched (same pair-level deferral — item 14).
- Comparisons are case-insensitive. ``CONTAINS`` /
  ``DOES NOT CONTAIN`` use substring (not regex).
- Per-rule pass/fail bits combine via the rule set's combinator
  (``AND`` → all must pass, ``OR`` → at least one must pass).
- An observer with no saved rule (or an empty ``rules`` list)
  yields an empty cohort.

The downstream consumers (W17 collation surface stats + the
per-instrument CSV download filter) call
``materialize_cohort_assignments`` per ``(observer, instrument)``
and treat the result as an opaque ``frozenset[int]`` of
assignment ids plus the two side-distinct counts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db.models import Assignment, Observer, Reviewee, Reviewer


_REVIEWER_TAG_ATTRS: dict[str, str] = {
    "tag1": "tag_1",
    "tag2": "tag_2",
    "tag3": "tag_3",
}

_REVIEWEE_TAG_ATTRS: dict[str, str] = _REVIEWER_TAG_ATTRS


def _reviewer_attr_value(reviewer: Reviewer, attr: str) -> str | None:
    column = _REVIEWER_TAG_ATTRS.get(attr)
    if column is None:
        return None
    return getattr(reviewer, column, None)


def _reviewee_attr_value(reviewee: Reviewee, attr: str) -> str | None:
    column = _REVIEWEE_TAG_ATTRS.get(attr)
    if column is None:
        return None
    return getattr(reviewee, column, None)


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
class CohortAssignments:
    """Per-(observer, instrument) materialised cohort.

    ``assignment_ids`` is the pool of in-cohort assignment rows
    for the instrument; the surface's stats query filters
    responses through it. The two ``distinct_*_count`` slots are
    the per-side individual counts derivable from those
    assignments — the headcount badges Row 1 / Row 2 render
    alongside the shared aggregate.
    """

    assignment_ids: frozenset[int]
    distinct_reviewer_count: int
    distinct_reviewee_count: int


EMPTY_COHORT = CohortAssignments(
    assignment_ids=frozenset(),
    distinct_reviewer_count=0,
    distinct_reviewee_count=0,
)


def observer_has_rule(observer: Observer) -> bool:
    """True iff the observer carries a saved cohort rule with at
    least one rule cell. ``False`` when ``cohort_rule`` is
    ``None`` or its ``rules`` list is empty — the surface uses
    this to distinguish "no rule authored" (empty-cohort message)
    from "rule authored but matched nothing on this instrument"
    (sections render with zero counts)."""
    if not observer.cohort_rule:
        return False
    rules = observer.cohort_rule.get("rules") or []
    return bool(rules)


def _rule_matches_row(
    rule: dict[str, Any],
    *,
    observer: Observer,
    reviewer: Reviewer,
    reviewee: Reviewee,
) -> bool:
    """Evaluate a single rule against one ``(reviewer, reviewee)``
    pair plus the observer. Returns ``True`` iff the rule's
    predicate is satisfied. See module docstring for the
    supported predicate shapes."""
    field = str(rule.get("field", ""))
    op = str(rule.get("op", ""))
    operand_tag = str(rule.get("operand_tag", ""))
    operand_value = str(rule.get("operand_value", ""))

    if not field or "." not in field:
        return False
    namespace, attr = field.split(".", 1)

    if namespace == "reviewer":
        left = _reviewer_attr_value(reviewer, attr)
    elif namespace == "reviewee":
        left = _reviewee_attr_value(reviewee, attr)
    else:
        # ``pair_context.*`` — schema permits but pair-level join
        # isn't implemented (clean_up item 13).
        return False

    if op in ("IS THE SAME AS", "IS DIFFERENT FROM"):
        if not operand_tag.startswith("observer."):
            # Cross-roster operand — schema permits but pair-level
            # join isn't implemented (clean_up item 14).
            return False
        observer_attr = operand_tag.split(".", 1)[1]
        right = _observer_attr_value(observer, observer_attr)
        if right is None:
            return False
        left_cmp = (left or "").lower()
        right_cmp = right.lower()
        if op == "IS THE SAME AS":
            return left_cmp == right_cmp
        return left_cmp != right_cmp

    left_cmp = (left or "").lower()
    value_cmp = operand_value.lower()
    if op == "IS":
        return left_cmp == value_cmp
    if op == "IS NOT":
        return left_cmp != value_cmp
    if op == "CONTAINS":
        return value_cmp in left_cmp
    if op == "DOES NOT CONTAIN":
        return value_cmp not in left_cmp
    return False


def assignment_matches_cohort(
    rule_set: dict[str, Any] | None,
    *,
    observer: Observer,
    reviewer: Reviewer,
    reviewee: Reviewee,
) -> bool:
    """True iff this ``(reviewer, reviewee)`` assignment satisfies
    the observer's saved cohort rule.

    Per-row evaluation that respects what each rule actually
    references — a rule on ``reviewer.*`` checks the reviewer, a
    rule on ``reviewee.*`` checks the reviewee, and unmentioned
    sides aren't second-guessed. Per-rule pass/fail bits combine
    via the rule set's combinator (``AND`` → all, ``OR`` → any).

    Returns ``False`` when ``rule_set`` is ``None`` or carries no
    rules (no cohort scope ⇒ no rows pass).
    """
    if not rule_set:
        return False
    rules = rule_set.get("rules") or []
    if not rules:
        return False
    combinator = str(rule_set.get("combinator", "AND")).upper()
    results = [
        _rule_matches_row(
            r, observer=observer, reviewer=reviewer, reviewee=reviewee
        )
        for r in rules
    ]
    if combinator == "OR":
        return any(results)
    return all(results)


def materialize_cohort_assignments(
    db: Session,
    *,
    observer: Observer,
    instrument_id: int,
) -> CohortAssignments:
    """Walk the (observer, instrument) assignment list and return
    the in-cohort assignment ids + per-side distinct counts.

    Returns ``EMPTY_COHORT`` when:
    - ``observer.cohort_rule`` is ``None`` or carries no rule
      cells (caught by ``observer_has_rule``);
    - the rule doesn't match any of the instrument's assignments.

    Reviewer + reviewee are eager-loaded via ``joinedload`` so the
    Python-side per-row evaluation is one query, not 1 + 2·N.
    """
    if not observer_has_rule(observer):
        return EMPTY_COHORT

    rule_set = observer.cohort_rule
    rows = (
        db.execute(
            select(Assignment)
            .options(
                joinedload(Assignment.reviewer),
                joinedload(Assignment.reviewee),
            )
            .where(
                Assignment.session_id == observer.session_id,
                Assignment.instrument_id == instrument_id,
            )
        )
        .scalars()
        .all()
    )

    assignment_ids: set[int] = set()
    reviewer_ids: set[int] = set()
    reviewee_ids: set[int] = set()
    for asgn in rows:
        if assignment_matches_cohort(
            rule_set,
            observer=observer,
            reviewer=asgn.reviewer,
            reviewee=asgn.reviewee,
        ):
            assignment_ids.add(asgn.id)
            reviewer_ids.add(asgn.reviewer_id)
            reviewee_ids.add(asgn.reviewee_id)

    return CohortAssignments(
        assignment_ids=frozenset(assignment_ids),
        distinct_reviewer_count=len(reviewer_ids),
        distinct_reviewee_count=len(reviewee_ids),
    )
