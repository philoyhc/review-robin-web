"""View-shape helpers for the Observers Setup page.

Carries the per-row adapters the Observers table uses — the friendly
summary string the Cohort column renders — and the several-row cohort
editor's state (operator pages Item 4).

See ``guide/archive/observers.md`` "Match-axis schema — decided" for the
storage shape these helpers translate from.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from app.db.models import Observer
from app.services.observers import same_cohort_rule

# Display labels only. The KEYS are stored — they are what a saved
# `cohort_rule` holds — so they never move; 19P.2 rung 6 changed the
# right-hand side alone, dropping the digit from the tag slot's label to
# match the roster index and the preview table's `<th>`. Observers have
# exactly one tag slot, so `Tag 1` numbered a series of one, and after
# the header changed a single row read `Tag` in its column and
# `Observer: Tag 1` in its Cohort cell.
_COHORT_OBSERVER_FRIENDLY: dict[str, str] = {
    "observer.name": "Observer: Name",
    "observer.email": "Observer: Email",
    "observer.tag1": "Observer: Tag",
}


def _cohort_field_friendly(
    canonical_key: str,
    tag_labels: dict[str, list[tuple[str, str]]],
) -> str:
    """Resolve a ``reviewer.tag1`` / ``observer.email`` / etc.
    canonical key into the operator's friendly label, falling
    back to the canonical key itself when nothing matches (e.g.
    the slot's tag has since been cleared)."""
    if canonical_key in _COHORT_OBSERVER_FRIENDLY:
        return _COHORT_OBSERVER_FRIENDLY[canonical_key]
    for namespace, prefix in (
        ("reviewer", "Reviewer: "),
        ("reviewee", "Reviewee: "),
        ("pair_context", "Pair Context: "),
    ):
        for key, friendly in tag_labels.get(namespace, []):
            if key == canonical_key:
                return prefix + friendly
    return canonical_key


def cohort_rule_summary(
    rule: dict[str, Any] | None,
    *,
    tag_labels: dict[str, list[tuple[str, str]]],
) -> str:
    """One-line summary of the first rule on a saved cohort
    payload, suffixed with ``+ N more`` when extra rules exist.

    Returns ``""`` when ``rule`` is ``None`` or carries no rule
    cells — the Cohort cell falls back to the ``—`` placeholder
    in those cases.
    """
    if not rule:
        return ""
    rules = rule.get("rules") or []
    if not rules:
        return ""
    first = rules[0]
    field = _cohort_field_friendly(str(first.get("field", "")), tag_labels)
    op = str(first.get("op", ""))
    if op in ("IS THE SAME AS", "IS DIFFERENT FROM"):
        operand = _cohort_field_friendly(
            str(first.get("operand_tag", "")), tag_labels
        )
    else:
        operand_value = str(first.get("operand_value", ""))
        # ASCII straight quotes so the summary string survives
        # CSV / shell exports if it ever leaves the rendered HTML;
        # ``«empty»`` (item 6) keeps its distinctive look for the
        # "filter on blank field" case so the operator can tell
        # it apart from an unfilled cell at a glance.
        operand = f'"{operand_value}"' if operand_value else "«empty»"
    summary = f"{field} {op} {operand}".strip()
    extra = len(rules) - 1
    if extra > 0:
        summary += f" + {extra} more"
    return summary


@dataclass(frozen=True)
class RuleEditState:
    """The several-row cohort editor, as the page renders it."""

    #: The selected ids it edits, in request order; empty when it is not
    #: open (fewer than two of them on the rendered rows).
    ids: list[int]
    #: The rule to load: the one they share, or ``None`` when they differ.
    rule: dict[str, Any] | None
    #: Whether their rules differ (the bar says so).
    mixed: bool
    #: The id of the last of them on the page, which the bar hangs under.
    last_id: int | None


def rule_edit_state(
    shown: Sequence[Observer], requested_ids: Iterable[int]
) -> RuleEditState:
    """Which selected rows the several-row editor edits, and what it
    loads (operator pages Item 4).

    Only rows this page renders are edited — a stale id (deleted, or
    another session's) is dropped rather than edited blind — and fewer
    than two left opens nothing: one row is the row editor's. One shared
    rule loads; differing rules load nothing. Compared as the service
    compares them, so NULL and an imported empty set are one "no rule".
    """
    by_id = {o.id: o for o in shown}
    ids = [i for i in dict.fromkeys(requested_ids) if i in by_id]
    if len(ids) < 2:
        return RuleEditState(ids=[], rule=None, mixed=False, last_id=None)
    first = by_id[ids[0]].cohort_rule
    mixed = not all(same_cohort_rule(first, by_id[i].cohort_rule) for i in ids)
    chosen = set(ids)
    last_id = next((o.id for o in reversed(shown) if o.id in chosen), None)
    return RuleEditState(
        ids=ids, rule=None if mixed else first, mixed=mixed, last_id=last_id,
    )
