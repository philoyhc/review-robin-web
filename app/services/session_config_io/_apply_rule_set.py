"""``session_rule_sets[N].*`` parse + apply.

Upsert by ``name`` so the per-instrument ``rule_set_name`` references
resolve against the same row pool whether the CSV came from a fresh
export or a hand-edited one.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, SessionRuleSet

from ._apply_shared import (
    _RX_RULE_SET,
    _VALID_COMBINATORS,
    _ParsedConfig,
    _ParseError,
    _parse_bool,
    _parse_int,
    _parse_json,
    _RuleSetSpec,
)


def _apply_rule_set_kv(
    plan: _ParsedConfig, field_path: str, value: str, data_type: str
) -> None:
    match = _RX_RULE_SET.match(field_path)
    if match is None:
        raise _ParseError(
            f"unrecognised session_rule_sets[] key {field_path!r}"
        )
    n, attr = int(match.group(1)), match.group(2)
    spec = plan.session_rule_sets.setdefault(n, _RuleSetSpec())
    if attr == "name":
        spec.name = value or None
    elif attr == "description":
        spec.description = value or None
    elif attr == "combinator":
        if value and value not in _VALID_COMBINATORS:
            raise _ParseError(
                f"unknown combinator {value!r}; expected one of "
                f"{sorted(_VALID_COMBINATORS)}"
            )
        spec.combinator = value or None
    elif attr == "exclude_self_reviews":
        spec.exclude_self_reviews = _parse_bool(value)
    elif attr == "seed":
        spec.seed = _parse_int(value)
    elif attr == "rules_json":
        spec.rules_json = _parse_json(value, default=[])
    else:
        raise _ParseError(f"unknown session_rule_sets[] attribute {attr!r}")
    del data_type  # unused


def _apply_session_rule_sets(
    db: Session, review_session: ReviewSession, plan: _ParsedConfig
) -> int:
    """Upsert ``session_rule_sets`` rows by ``name``; delete
    existing rows not in the CSV. (Wave 5 PR 5.2 retired the
    seeded set, so all rows are operator-authored.)"""

    existing = {
        snap.name: snap
        for snap in db.execute(
            select(SessionRuleSet).where(
                SessionRuleSet.session_id == review_session.id
            )
        ).scalars()
    }

    written = 0
    for spec in plan.session_rule_sets.values():
        assert spec.name is not None  # cross-row check enforced
        # ``SessionRuleSet.description`` is NOT NULL — empty cell
        # ⇒ empty string, not None.
        description = spec.description or ""
        snap = existing.pop(spec.name, None)
        if snap is None:
            snap = SessionRuleSet(
                session_id=review_session.id,
                name=spec.name,
                description=description,
                combinator=spec.combinator or "ALL_OF",
                exclude_self_reviews=spec.exclude_self_reviews,
                seed=spec.seed,
                rules_json=spec.rules_json,
            )
            db.add(snap)
        else:
            snap.description = description
            snap.combinator = spec.combinator or "ALL_OF"
            snap.exclude_self_reviews = spec.exclude_self_reviews
            snap.seed = spec.seed
            snap.rules_json = spec.rules_json
        written += 1

    for orphan in existing.values():
        db.delete(orphan)
    db.flush()

    return written
