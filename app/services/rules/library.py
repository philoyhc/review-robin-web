"""RuleSet library queries — Segment 13A PR 4 + PR 5a.

Visible RuleSets for an operator are: every seed (workspace-wide,
read-only) plus the operator's own Personal-scope RuleSets that
haven't been soft-deleted. PR 5a's editor is the first surface that
exercises the Personal half end-to-end via ``copy_rule_set`` —
operators can clone any visible RuleSet (including seeds) into a
new Personal RuleSet they own.

``load_rule_set`` resolves a RuleSet by id and returns its current
revision. Unlike ``list_visible_rule_sets``, this resolver does
*not* filter on ``deleted_at`` — past audit refs (an
``assignments.generated`` row pinned to a since-deleted RuleSet)
must still resolve cleanly. The library list is the only surface
that hides soft-deleted rows.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import RuleSet, RuleSetRevision, User
from app.services import audit


def list_visible_rule_sets(
    db: Session, *, user: User
) -> list[RuleSet]:
    """Seeds + ``user``'s Personal RuleSets (excluding soft-deleted),
    sorted so the editor selector renders seeds first in their
    deliberate install order, then Personal RuleSets.

    Within seeds, install-time id ordering pins the canonical sequence
    (Full Matrix → Intra-group → Cross-group → Same-group-different-
    role → Three-per-reviewee). PR 5 will refine the Personal half to
    sort by most-recently-updated; the inline `id` ordering here
    happens to coincide with most-recently-updated for the empty PR 4
    Personal library and is a placeholder until then.
    """

    stmt = (
        select(RuleSet)
        .where(
            or_(
                RuleSet.is_seed.is_(True),
                RuleSet.owner_user_id == user.id,
            ),
            RuleSet.deleted_at.is_(None),
        )
        .order_by(RuleSet.scope, RuleSet.id)
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


def copy_rule_set(
    db: Session,
    *,
    source: RuleSet,
    source_revision: RuleSetRevision,
    owner: User,
    new_name: str,
    correlation_id: str,
) -> RuleSet:
    """Clone ``source`` (any RuleSet, including seeds) into a new
    Personal-scope RuleSet owned by ``owner``.

    Creates a new ``rule_sets`` row (scope='personal',
    is_seed=False), inserts a single ``rule_set_revisions`` row
    with the source revision's ``rules_json`` / ``combinator`` /
    ``exclude_self_reviews`` / ``seed`` copied verbatim, and points
    ``current_revision_id`` at it. The new revision starts at
    ``revision_no=1``; the source's revision history is not
    inherited (Personal RuleSets get their own monotonic revision
    stream from PR 6 onward).

    Emits a ``rule_set.created`` audit event with a ``snapshot``
    payload of the new RuleSet's metadata + revision shape, plus a
    ``refs`` slot pointing back at the source for provenance.
    """

    now = datetime.now(timezone.utc)

    new_rule_set = RuleSet(
        name=new_name,
        description=source.description or "",
        scope="personal",
        owner_user_id=owner.id,
        is_seed=False,
    )
    db.add(new_rule_set)
    db.flush()

    new_revision = RuleSetRevision(
        rule_set_id=new_rule_set.id,
        revision_no=1,
        combinator=source_revision.combinator,
        exclude_self_reviews=source_revision.exclude_self_reviews,
        seed=source_revision.seed,
        # ``deepcopy`` so future edits to the source RuleSet's
        # ``rules_json`` (in PR 5b) don't surface here through any
        # accidentally-shared list reference.
        rules_json=deepcopy(source_revision.rules_json),
        created_at=now,
        created_by_user_id=owner.id,
    )
    db.add(new_revision)
    db.flush()

    new_rule_set.current_revision_id = new_revision.id
    db.flush()

    audit.write_event(
        db,
        event_type="rule_set.created",
        summary=(
            f"Copied RuleSet {source.name!r} → {new_name!r} "
            f"(personal scope, owned by user_id={owner.id})"
        ),
        actor_user_id=owner.id,
        payload=audit.snapshot(
            {
                "id": new_rule_set.id,
                "name": new_rule_set.name,
                "scope": new_rule_set.scope,
                "is_seed": new_rule_set.is_seed,
                "combinator": new_revision.combinator,
                "exclude_self_reviews": (
                    new_revision.exclude_self_reviews
                ),
                "rule_count": len(new_revision.rules_json or []),
            }
        ),
        refs={
            "rule_set_id": new_rule_set.id,
            "rule_set_revision_id": new_revision.id,
            "source_rule_set_id": source.id,
            "source_revision_id": source_revision.id,
        },
        context={"via": "copy"},
        correlation_id=correlation_id,
    )

    db.commit()
    return new_rule_set
