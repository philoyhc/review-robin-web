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
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import RuleSet, RuleSetRevision, User
from app.services import audit


def list_visible_rule_sets(
    db: Session, *, user: User
) -> list[RuleSet]:
    """Seeds + ``user``'s Personal RuleSets (excluding soft-deleted),
    sorted so every consumer renders seeds first in their deliberate
    install order, then Personal RuleSets.

    Within seeds, install-time id ordering pins the canonical sequence
    (Full Matrix → Intra-group → Cross-group → Same-group-different-
    role → Three-per-reviewee). Personal RuleSets follow in id order
    — a placeholder until a future PR refines that half to sort by
    most-recently-updated.

    The ordering is ``is_seed DESC, id ASC``: ``is_seed=True`` (i.e.
    seed rows) sorts before ``is_seed=False`` (Personal rows) under
    descending order, then id ascending pins the canonical sub-
    sequence within each group. Sorting by ``scope`` directly would
    put ``"personal"`` ahead of ``"seed"`` alphabetically, which is
    the opposite of what every dropdown wants.
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
        .order_by(RuleSet.is_seed.desc(), RuleSet.id)
    )
    return list(db.execute(stmt).scalars())


def list_personal_rule_sets(
    db: Session, *, owner_user: User
) -> list[RuleSet]:
    """``owner_user``'s Personal-scope RuleSets (no seeds, no soft-
    deleted), in id order. Used by 15C Slice 2's
    ``materialise_operator_libraries`` to enumerate the library
    entries that should be copied into a newly-created session."""

    stmt = (
        select(RuleSet)
        .where(
            RuleSet.is_seed.is_(False),
            RuleSet.owner_user_id == owner_user.id,
            RuleSet.deleted_at.is_(None),
        )
        .order_by(RuleSet.id)
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


def save_as_rule_set_from_schema(
    db: Session,
    *,
    rule_set_schema,  # RuleSetSchema (avoid Pydantic forward refs)
    owner: User,
    new_name: str,
    source_rule_set_id: int | None,
    source_revision_id: int | None,
    correlation_id: str,
) -> RuleSet:
    """Persist an edited RuleSet (Segment 13A PR 5b's Save As).

    Validation has already happened: ``rule_set_schema`` is a fully-
    validated ``RuleSetSchema`` instance from the route. This helper
    is the DB-write counterpart to ``copy_rule_set`` for the edited-
    tree path. Always creates a new Personal RuleSet; PR 6's Save
    will land the in-place revision write that branches on
    ``source_rule_set_id`` matching the loaded ID.

    Audit event: ``rule_set.created`` with ``context.via='save_as'``
    (vs. ``via='copy'`` for the unchanged-tree path) and
    ``refs.source_rule_set_id`` / ``source_revision_id`` for
    provenance back to the row the operator started editing from.
    """

    now = datetime.now(timezone.utc)

    new_rule_set = RuleSet(
        name=new_name,
        description=rule_set_schema.description or "",
        scope="personal",
        owner_user_id=owner.id,
        is_seed=False,
    )
    db.add(new_rule_set)
    db.flush()

    rules_payload = [
        rule.model_dump(mode="json") for rule in rule_set_schema.rules
    ]
    new_revision = RuleSetRevision(
        rule_set_id=new_rule_set.id,
        revision_no=1,
        combinator=rule_set_schema.combinator.value,
        exclude_self_reviews=rule_set_schema.options.excludeSelfReviews,
        seed=rule_set_schema.options.seed,
        rules_json=rules_payload,
        created_at=now,
        created_by_user_id=owner.id,
    )
    db.add(new_revision)
    db.flush()
    new_rule_set.current_revision_id = new_revision.id
    db.flush()

    refs: dict[str, int] = {
        "rule_set_id": new_rule_set.id,
        "rule_set_revision_id": new_revision.id,
    }
    if source_rule_set_id is not None:
        refs["source_rule_set_id"] = source_rule_set_id
    if source_revision_id is not None:
        refs["source_revision_id"] = source_revision_id

    audit.write_event(
        db,
        event_type="rule_set.created",
        summary=(
            f"Saved As RuleSet {new_name!r} "
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
        refs=refs,
        context={"via": "save_as"},
        correlation_id=correlation_id,
    )

    db.commit()
    return new_rule_set


# Segment 13A PR 6 — Edit / Rename / Delete + revisioning.


def save_in_place(
    db: Session,
    *,
    rule_set: RuleSet,
    rule_set_schema,  # RuleSetSchema (avoid Pydantic forward refs)
    actor: User,
    correlation_id: str,
) -> RuleSetRevision:
    """Append a new revision to ``rule_set`` from the validated
    schema and bump ``current_revision_id``.

    Past ``assignments.generated`` audit rows pinned to the previous
    revision id stay resolvable — old revisions are retained, never
    deleted. Audit ``rule_set.updated`` with a ``changes`` envelope
    that diffs the *metadata* (combinator / exclude_self_reviews /
    seed / rule_count); the per-rule diff inside ``rules_json`` is
    intentionally not unrolled — the previous revision row carries
    the full prior tree if a downstream consumer needs it.
    """

    now = datetime.now(timezone.utc)

    previous_revision_no = (
        db.execute(
            select(RuleSetRevision.revision_no)
            .where(RuleSetRevision.rule_set_id == rule_set.id)
            .order_by(RuleSetRevision.revision_no.desc())
        ).scalars().first()
        or 0
    )
    new_revision_no = previous_revision_no + 1

    previous_revision = (
        db.execute(
            select(RuleSetRevision).where(
                RuleSetRevision.id == rule_set.current_revision_id
            )
        ).scalar_one_or_none()
        if rule_set.current_revision_id is not None
        else None
    )

    rules_payload = [
        rule.model_dump(mode="json") for rule in rule_set_schema.rules
    ]
    new_revision = RuleSetRevision(
        rule_set_id=rule_set.id,
        revision_no=new_revision_no,
        combinator=rule_set_schema.combinator.value,
        exclude_self_reviews=rule_set_schema.options.excludeSelfReviews,
        seed=rule_set_schema.options.seed,
        rules_json=rules_payload,
        created_at=now,
        created_by_user_id=actor.id,
    )
    db.add(new_revision)
    db.flush()
    rule_set.current_revision_id = new_revision.id
    db.flush()

    changes_pairs: dict[str, list[Any]] = {}
    if previous_revision is not None:
        if previous_revision.combinator != new_revision.combinator:
            changes_pairs["combinator"] = [
                previous_revision.combinator, new_revision.combinator
            ]
        if (
            previous_revision.exclude_self_reviews
            != new_revision.exclude_self_reviews
        ):
            changes_pairs["exclude_self_reviews"] = [
                previous_revision.exclude_self_reviews,
                new_revision.exclude_self_reviews,
            ]
        if previous_revision.seed != new_revision.seed:
            changes_pairs["seed"] = [
                previous_revision.seed, new_revision.seed
            ]
        prev_count = len(previous_revision.rules_json or [])
        new_count = len(new_revision.rules_json or [])
        if prev_count != new_count:
            changes_pairs["rule_count"] = [prev_count, new_count]
        # Tree-shape changes (ids / order / predicates) collapse into
        # a single boolean diff key — operators see "rules edited" in
        # the audit log without the row exploding to one entry per
        # leaf change.
        if previous_revision.rules_json != new_revision.rules_json:
            changes_pairs["rules_edited"] = [True, True]

    audit.write_event(
        db,
        event_type="rule_set.updated",
        summary=(
            f"Saved RuleSet {rule_set.name!r} "
            f"(revision {new_revision_no})"
        ),
        actor_user_id=actor.id,
        payload=audit.changes(changes_pairs) if changes_pairs else None,
        refs={
            "rule_set_id": rule_set.id,
            "rule_set_revision_id": new_revision.id,
            "previous_revision_id": (
                previous_revision.id if previous_revision is not None else 0
            ),
        },
        context={"via": "save"},
        correlation_id=correlation_id,
    )

    db.commit()
    return new_revision


def rename_rule_set(
    db: Session,
    *,
    rule_set: RuleSet,
    new_name: str,
    new_description: str,
    actor: User,
    correlation_id: str,
) -> RuleSet:
    """Update ``rule_set.name`` / ``description`` without touching
    the rule tree or bumping the revision number.

    Audit ``rule_set.updated`` with a ``changes`` envelope of just
    the name / description diff. ``via='rename'`` marks this apart
    from ``save`` events for downstream filtering.
    """

    old_name = rule_set.name
    old_description = rule_set.description or ""
    rule_set.name = new_name
    rule_set.description = new_description
    db.flush()

    changes_pairs: dict[str, list[Any]] = {}
    if old_name != new_name:
        changes_pairs["name"] = [old_name, new_name]
    if old_description != new_description:
        changes_pairs["description"] = [old_description, new_description]

    audit.write_event(
        db,
        event_type="rule_set.updated",
        summary=f"Renamed RuleSet {old_name!r} → {new_name!r}",
        actor_user_id=actor.id,
        payload=audit.changes(changes_pairs) if changes_pairs else None,
        refs={"rule_set_id": rule_set.id},
        context={"via": "rename"},
        correlation_id=correlation_id,
    )

    db.commit()
    return rule_set


def soft_delete_rule_set(
    db: Session,
    *,
    rule_set: RuleSet,
    actor: User,
    correlation_id: str,
) -> RuleSet:
    """Soft-delete a Personal RuleSet by setting ``deleted_at``.

    Revisions are retained — past ``assignments.generated`` audit
    rows that pinned a specific revision id still resolve via
    ``load_rule_set`` (which intentionally doesn't filter on
    ``deleted_at``). The library list (visible to operators) hides
    the row.
    """

    now = datetime.now(timezone.utc)
    snapshot_payload = audit.snapshot(
        {
            "id": rule_set.id,
            "name": rule_set.name,
            "scope": rule_set.scope,
            "is_seed": rule_set.is_seed,
            "owner_user_id": rule_set.owner_user_id,
        }
    )
    rule_set.deleted_at = now
    db.flush()

    audit.write_event(
        db,
        event_type="rule_set.deleted",
        summary=f"Soft-deleted RuleSet {rule_set.name!r}",
        actor_user_id=actor.id,
        payload=snapshot_payload,
        refs={"rule_set_id": rule_set.id},
        context={"soft": True},
        correlation_id=correlation_id,
    )

    db.commit()
    return rule_set
