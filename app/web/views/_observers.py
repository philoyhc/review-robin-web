"""View-shape helpers for the Observers Setup page.

Carries the per-row adapters the Observers table uses — the
mixed-state signature the cohort-rule editor JS compares against,
and the friendly summary string the Cohort column renders.

See ``guide/archive/observers.md`` "Match-axis schema — decided" for the
storage shape these helpers translate from.
"""

from __future__ import annotations

import json
from typing import Any

_COHORT_OBSERVER_FRIENDLY: dict[str, str] = {
    "observer.name": "Observer: Name",
    "observer.email": "Observer: Email",
    "observer.tag1": "Observer: Tag 1",
}


def cohort_rule_signature(rule: dict[str, Any] | None) -> str:
    """Stable string key for one observer's saved cohort rule.

    Two observers share the same effective rule iff their
    signatures match — used by the Observers Setup page's
    mixed-state JS to decide whether the editor loads a shared
    rule or shows the "differ — saving overwrites" message.

    ``None`` (no rule saved) maps to ``""`` so the JS distinct-
    count check treats unset observers as a single shared
    "empty" group rather than as N distinct rules.
    """
    if rule is None:
        return ""
    return json.dumps(rule, sort_keys=True, ensure_ascii=False)


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
