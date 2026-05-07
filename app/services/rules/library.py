"""RuleSet library queries — Segment 13A PR 4.

Visible RuleSets for an operator are: every seed (workspace-wide,
read-only) plus the operator's own Personal-scope RuleSets that
haven't been soft-deleted. PR 4 ships only the seed half — Personal
RuleSets land with PR 5's editor — but the query below already
honours the Personal filter so PR 5 is a thin diff.

``load_rule_set`` resolves a RuleSet by id and returns its current
revision. Unlike ``list_visible_rule_sets``, this resolver does
*not* filter on ``deleted_at`` — past audit refs (an
``assignments.generated`` row pinned to a since-deleted RuleSet)
must still resolve cleanly. The library list is the only surface
that hides soft-deleted rows.
"""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import RuleSet, RuleSetRevision, User


def list_visible_rule_sets(
    db: Session, *, user: User
) -> list[RuleSet]:
    """Seeds + ``user``'s Personal RuleSets (excluding soft-deleted),
    sorted by ``(scope, name)`` so seeds render in the editor selector
    above Personal entries."""

    stmt = (
        select(RuleSet)
        .where(
            or_(
                RuleSet.is_seed.is_(True),
                RuleSet.owner_user_id == user.id,
            ),
            RuleSet.deleted_at.is_(None),
        )
        .order_by(RuleSet.scope, RuleSet.name)
    )
    return list(db.execute(stmt).scalars())


def load_rule_set(
    db: Session, rule_set_id: int
) -> tuple[RuleSet, RuleSetRevision] | None:
    """Resolve a RuleSet + its current revision by id.

    Returns ``None`` if the RuleSet doesn't exist or has no current
    revision pointed at. Soft-deleted rows still resolve so audit
    refs stay readable."""

    rule_set = db.execute(
        select(RuleSet).where(RuleSet.id == rule_set_id)
    ).scalar_one_or_none()
    if rule_set is None or rule_set.current_revision_id is None:
        return None
    revision = db.execute(
        select(RuleSetRevision).where(
            RuleSetRevision.id == rule_set.current_revision_id
        )
    ).scalar_one_or_none()
    if revision is None:
        return None
    return rule_set, revision
