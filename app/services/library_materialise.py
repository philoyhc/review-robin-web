"""Cross-tier copy from operator libraries into per-session tables.

Segment 15C Slice 2. When a new session is created, the operator's
library entries (RTDs + RuleSets) are auto-copied into the
session's per-session tables so the operator doesn't have to
"import from another session" or redo their canonical setup.

The single entry point is :func:`materialise_operator_libraries`,
called from :func:`app.services.sessions.create_session` **after**
:func:`app.services.rules.seeds.materialise_seed_rule_sets` so
workspace seeds win any (rare) name collision with personal-
library entries — seeds-first is invariant #5 in
``guide/segment_15C_operator_libraries.md``.

The helper is idempotent: re-running on a session that already
has the copies is a no-op. RTDs collide-by-name with the seeded
RTDs from :func:`ensure_default_response_type_definitions`; the
``(session_id, response_type)`` unique constraint forces a skip on
duplicates. RuleSet name collisions skip via the
``(session_id, name)`` unique constraint.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    ResponseTypeDefinition,
    ReviewSession,
    RuleSetRevision,
    SessionRuleSet,
    User,
)
from app.services.instruments._rtds import list_operator_rtds
from app.services.rules.library import list_personal_rule_sets


@dataclass(frozen=True)
class LibraryMaterialisationResult:
    """Count of rows inserted per tier. ``create_session`` reads
    these to decide whether to emit the per-tier audit events.
    Zero counts mean the operator had nothing in their library
    (the typical case until 15C Slice 5's library-management UI
    ships)."""

    rtds_copied: int
    rule_sets_copied: int


def materialise_operator_libraries(
    db: Session, review_session: ReviewSession, *, owner_user: User
) -> LibraryMaterialisationResult:
    """Copy every operator-library RTD + Personal RuleSet owned by
    ``owner_user`` into ``review_session``'s per-session tables.

    Order: caller must invoke :func:`materialise_seed_rule_sets`
    first so workspace seeds claim their names; this helper then
    skips any library entry whose name collides with a seed.

    Idempotent. Re-running is a no-op — the
    ``(session_id, response_type)`` / ``(session_id, name)`` unique
    constraints catch any duplicate that would slip through the
    in-Python collision filter.
    """
    rtds_copied = _materialise_rtds(db, review_session, owner_user=owner_user)
    rule_sets_copied = _materialise_rule_sets(
        db, review_session, owner_user=owner_user
    )
    if rtds_copied or rule_sets_copied:
        db.flush()
    return LibraryMaterialisationResult(
        rtds_copied=rtds_copied,
        rule_sets_copied=rule_sets_copied,
    )


def _materialise_rtds(
    db: Session, review_session: ReviewSession, *, owner_user: User
) -> int:
    """Copy each operator-library RTD into
    ``response_type_definitions``. Skip names already on the
    session (seed-name collisions or earlier-run idempotent
    copies)."""
    existing_names = set(
        db.execute(
            select(ResponseTypeDefinition.response_type).where(
                ResponseTypeDefinition.session_id == review_session.id
            )
        ).scalars()
    )
    copied = 0
    for source in list_operator_rtds(db, owner_user=owner_user):
        if source.response_type in existing_names:
            continue
        db.add(
            ResponseTypeDefinition(
                session_id=review_session.id,
                response_type=source.response_type,
                data_type=source.data_type,
                min=source.min,
                max=source.max,
                step=source.step,
                list_csv=source.list_csv,
                is_seeded=False,
                seed_order=0,
                library_origin_id=source.id,
            )
        )
        existing_names.add(source.response_type)
        copied += 1
    return copied


def _materialise_rule_sets(
    db: Session, review_session: ReviewSession, *, owner_user: User
) -> int:
    """Copy each operator-library Personal RuleSet into
    ``session_rule_sets`` by snapshotting its current revision.
    Skip names already on the session (seed-name collisions or
    earlier-run idempotent copies)."""
    existing_names = set(
        db.execute(
            select(SessionRuleSet.name).where(
                SessionRuleSet.session_id == review_session.id
            )
        ).scalars()
    )
    copied = 0
    for source in list_personal_rule_sets(db, owner_user=owner_user):
        if source.name in existing_names:
            continue
        revision = _load_current_revision(db, source.current_revision_id)
        if revision is None:
            # Library entry has no current revision pointed at — skip
            # rather than fail, mirroring the resolver's tolerance for
            # historical refs in load_rule_set.
            continue
        db.add(
            SessionRuleSet(
                session_id=review_session.id,
                name=source.name,
                description=source.description or "",
                combinator=revision.combinator,
                exclude_self_reviews=revision.exclude_self_reviews,
                seed=revision.seed,
                rules_json=revision.rules_json,
                library_origin_id=source.id,
            )
        )
        existing_names.add(source.name)
        copied += 1
    return copied


def _load_current_revision(
    db: Session, revision_id: int | None
) -> RuleSetRevision | None:
    if revision_id is None:
        return None
    return db.execute(
        select(RuleSetRevision).where(RuleSetRevision.id == revision_id)
    ).scalar_one_or_none()
