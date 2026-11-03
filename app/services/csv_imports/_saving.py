"""Saving and deleting a roster: the three ``save_*`` and ``delete_all_*``,
``_save`` (replace, append, merge) and the counts. Segment 20E rung 2,
moved unchanged.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Observer,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from app.schemas.imports import (
    ObserverImportRow,
    ReviewerImportRow,
    RevieweeImportRow,
)
from app.services import audit, field_labels, symmetric_review
from app.services import directory_accounts, roster_bulk, unit_of_work
from app.services import invitations as invitations_service
from app.services import session_lifecycle as lifecycle
from app.services.email_identity import normalize_object_id
from app.services.csv_imports._parse import (
    log,
)
from app.services.csv_imports._identity import (
    DirectoryCheck,
)
from app.services.csv_imports._modes import (
    AppendConflict,
    append_conflicts,
    merge_conflicts,
    _merge_rows,
)

def existing_reviewer_count(db: Session, session_id: int) -> int:
    return _count(db, Reviewer, session_id)


def existing_reviewee_count(db: Session, session_id: int) -> int:
    return _count(db, Reviewee, session_id)


def existing_observer_count(db: Session, session_id: int) -> int:
    return _count(db, Observer, session_id)


def _count(
    db: Session,
    model: type[Reviewer] | type[Reviewee] | type[Observer],
    session_id: int,
) -> int:
    stmt = select(func.count(model.id)).where(model.session_id == session_id)
    return int(db.execute(stmt).scalar_one())


def save_reviewers(
    db: Session,
    *,
    session: ReviewSession,
    user: User,
    rows: list[ReviewerImportRow],
    filename: str,
    correlation_id: str,
    field_labels_captured: dict[tuple[str, str], str] | None = None,
    directory: DirectoryCheck | None = None,
    append: bool = False,
    merge: bool = False,
    columns: frozenset[str] = frozenset(),
    acknowledged_loss: int | None = None,
) -> tuple[int, int]:
    # One commit for the roster and its labels, so the lock taken by
    # the gate holds to the end and a refusal can't follow a committed
    # replace (findings Bc4).
    with unit_of_work.atomic(db):
        lifecycle.require_editable(db, session)
        result = _save(
            db,
            session=session,
            user=user,
            model=Reviewer,
            rows=rows,
            event_type="reviewers.imported",
            source_label="reviewers",
            filename=filename,
            correlation_id=correlation_id,
            to_kwargs=_reviewer_to_kwargs,
            directory=directory,
            append=append,
            merge=merge,
            columns=columns,
        )
        if merge and not session.symmetric_review:
            # A merge can bind a reviewer to the account a reviewee holds
            # under another address, which makes their pair a self-review
            # (Codex, #3440). Under symmetric review the reconcile below
            # recomputes once the mirror carries the change too.
            from app.services.assignments import recompute_self_review_classification

            recompute_self_review_classification(db, session_id=session.id)
        # Segment 19C Item 1 — reconcile reviewer friendly labels from
        # the roster header (upsert present, clear absent). ``None`` = a
        # caller that isn't an import; skip untouched.
        if field_labels_captured is not None:
            field_labels.apply_import(
                db,
                session,
                source_type="reviewer",
                captured=field_labels_captured,
                user=user,
                correlation_id=correlation_id,
                clear_absent=not (append or merge),
            )
        # 20B — under symmetric review the reviewee roster follows, with
        # the labels this import carries. A merge's tag changes that
        # redraw answered groups ask first (``acknowledged_loss``), as a
        # Reviewees merge does.
        symmetric_review.sync_reviewees_from_reviewers(
            db, session, acknowledged_loss=acknowledged_loss
        )
    return result


def save_reviewees(
    db: Session,
    *,
    session: ReviewSession,
    user: User,
    rows: list[RevieweeImportRow],
    filename: str,
    correlation_id: str,
    field_labels_captured: dict[tuple[str, str], str] | None = None,
    directory: DirectoryCheck | None = None,
    append: bool = False,
    merge: bool = False,
    columns: frozenset[str] = frozenset(),
    acknowledged_loss: int | None = None,
) -> tuple[int, int]:
    from app.services import responses as responses_service
    from app.services.instruments import seed_display_fields_from_reviewees

    # One commit for the roster, its display fields and its labels, as
    # in ``save_reviewers`` (findings Bc4).
    with unit_of_work.atomic(db):
        lifecycle.require_editable(db, session)
        from app.services.symmetric_review import refuse_reviewee_write

        refuse_reviewee_write(session)
        # A merge can move a reviewee between groups by a tag change
        # (segment 19Z): snapshot the partitions, and after the save ask
        # before clearing any group that gained a member, as the
        # reviewee row editor does.
        groups_before = (
            responses_service.snapshot_group_partitions(
                db,
                session_id=session.id,
                instrument_ids=responses_service.session_group_instrument_ids(
                    db, session_id=session.id, source_type="reviewee"
                ),
            )
            if merge
            else {}
        )
        result = _save(
            db,
            session=session,
            user=user,
            model=Reviewee,
            rows=rows,
            event_type="reviewees.imported",
            source_label="reviewees",
            filename=filename,
            correlation_id=correlation_id,
            to_kwargs=_reviewee_to_kwargs,
            directory=directory,
            append=append,
            merge=merge,
            columns=columns,
        )
        if merge:
            from app.services.assignments import recompute_self_review_classification

            responses_service.clear_changed_groups(
                db,
                session_id=session.id,
                before=groups_before,
                acknowledged_loss=acknowledged_loss,
            )
            recompute_self_review_classification(db, session_id=session.id)
        # Lazy-seed display fields for any populated reviewee slots
        # (profile_link / tag_1..3) — see guide/unfinished_business item #14.
        seed_display_fields_from_reviewees(db, session)
        # Segment 19C Item 1 — reconcile reviewee friendly labels from
        # the roster header (upsert present, clear absent).
        if field_labels_captured is not None:
            field_labels.apply_import(
                db,
                session,
                source_type="reviewee",
                captured=field_labels_captured,
                user=user,
                correlation_id=correlation_id,
                clear_absent=not (append or merge),
            )
    return result


def save_observers(
    db: Session,
    *,
    session: ReviewSession,
    user: User,
    rows: list[ObserverImportRow],
    filename: str,
    correlation_id: str,
    directory: DirectoryCheck | None = None,
    append: bool = False,
    merge: bool = False,
    columns: frozenset[str] = frozenset(),
) -> tuple[int, int]:
    lifecycle.require_not_archived(db, session)
    return _save(
        db,
        session=session,
        user=user,
        model=Observer,
        rows=rows,
        event_type="observers.imported",
        source_label="observers",
        filename=filename,
        correlation_id=correlation_id,
        to_kwargs=_observer_to_kwargs,
        directory=directory,
        append=append,
        merge=merge,
        columns=columns,
    )


def _observer_to_kwargs(row: ObserverImportRow, session_id: int) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "email": row.email,
        "display_name": row.display_name,
        "tag_1": row.tag_1,
        "status": row.status,
        "cohort_rule": row.cohort_rule,
    }


def _reviewer_to_kwargs(row: ReviewerImportRow, session_id: int) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "name": row.name,
        "email": row.email,
        "profile_link": row.profile_link,
        "tag_1": row.tag_1,
        "tag_2": row.tag_2,
        "tag_3": row.tag_3,
        "status": row.status,
    }


def _reviewee_to_kwargs(row: RevieweeImportRow, session_id: int) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "name": row.name,
        "email_or_identifier": row.email_or_identifier,
        "profile_link": row.profile_link,
        "tag_1": row.tag_1,
        "tag_2": row.tag_2,
        "tag_3": row.tag_3,
        "status": row.status,
    }


def _save(
    db: Session,
    *,
    session: ReviewSession,
    user: User,
    model: Any,
    rows: list[Any],
    event_type: str,
    source_label: str,
    filename: str,
    correlation_id: str,
    to_kwargs: Any,
    directory: DirectoryCheck | None = None,
    append: bool = False,
    merge: bool = False,
    columns: frozenset[str] = frozenset(),
) -> tuple[int, int]:
    """Replace ``model``'s roster with ``rows``, or with ``append`` add
    them and keep every row, assignment and response already there
    (segment 19Z). Returns ``(replaced, new)``; an append replaces 0.

    With ``merge`` (the upsert amendment) a row already on the roster
    is updated and any other added (`_merge_rows`); ``new`` counts the
    rows added. Two file rows on one directory account refuse it
    (`merge_conflicts`), before anything is written.

    An append is refused, before anything is written, by any row
    `append_conflicts` names (`AppendConflict`). It runs here, under
    the session lock the caller holds, so a row added since the
    caller's own check is caught too."""
    if append:
        conflicts = append_conflicts(
            db, session_id=session.id, kind=source_label, rows=rows, directory=directory
        )
        if conflicts:
            raise AppendConflict(conflicts)
    if merge:
        conflicts = merge_conflicts(kind=source_label, rows=rows, directory=directory)
        if conflicts:
            raise AppendConflict(conflicts)
    keeps = append or merge
    lifecycle.invalidate_if_validated(
        db,
        review_session=session,
        user=user,
        reason=f"{source_label}_imported",
        correlation_id=correlation_id,
    )
    # Nothing in `assignments` references an observer, so their events
    # omit the key rather than count rows they never delete (findings
    # S10). The same omitted-not-zero rule as `cascaded_relationships`.
    # An append deletes nothing, so it cascades nothing: the counts are
    # omitted, not zeroed.
    cascaded_assignment_count = (
        _count_assignments(db, session.id)
        if _reaches_assignments(model) and not keeps
        else None
    )
    # Before the delete below: the FK cascade is the database's, so
    # counting afterwards reads 0. Same mechanism as `_delete_all`.
    cascaded_relationship_count = (
        _count_relationships(db, session.id)
        if roster_bulk.reaches_relationships(model) and not keeps
        else None
    )

    existing_rows = list(
        db.execute(select(model).where(model.session_id == session.id)).scalars()
    )
    # A replace re-adds every row, so a row whose address the directory
    # gave no answer for (an expired token, a failed lookup) would lose
    # the account it was bound to and stop admitting a person whose mail
    # differs. Such a row keeps its earlier binding instead (assessment
    # 2026-11-02, M1); an address the directory did answer for takes
    # that answer, bound or not.
    earlier: dict[str, dict[str, str | None]] = {}
    if directory is not None and not keeps:
        for held in existing_rows:
            address = getattr(held, "email", None) or getattr(held, "email_or_identifier", None)
            held_key = directory_accounts.key(address)
            held_binding = directory_accounts.binding(held)
            if held_key in directory.unchecked and held_binding is not None:
                earlier.setdefault(held_key, held_binding)
    # An account the directory just bound another of the file's rows to
    # is not carried: the stale binding would put that person on two
    # rows (cold read of M1's fix).
    if earlier:
        fresh = {
            normalize_object_id(account.object_id)
            for row in rows
            if (account := directory.accounts.get(
                directory_accounts.key(
                    getattr(row, "email", None) or getattr(row, "email_or_identifier", None)
                )
                or ""
            ))
            is not None
        }
        earlier = {
            k: b
            for k, b in earlier.items()
            if normalize_object_id(b["directory_object_id"] or "") not in fresh
        }
    kept_bindings = 0
    if keeps:
        replaced, kept = 0, len(existing_rows)
    else:
        replaced, kept = len(existing_rows), 0
        _detach_outbox_if_reviewers(db, model=model, session_id=session.id, rows=existing_rows)
        for row in existing_rows:
            db.delete(row)
        db.flush()

    merged = (
        _merge_rows(
            db,
            session=session,
            user=user,
            model=model,
            kind=source_label,
            existing=existing_rows,
            rows=rows,
            to_kwargs=to_kwargs,
            directory=directory,
            correlation_id=correlation_id,
        )
        if merge
        else None
    )
    for row in rows if merged is None else []:
        kwargs = to_kwargs(row, session.id)
        if directory is not None:
            # Segment 21F: the account the row's address resolved to, or
            # none (not found, ambiguous, or not an address). An address
            # the directory gave no answer for keeps the replaced row's
            # account, if it had one (M1, above); else none.
            address = kwargs.get("email") or kwargs.get("email_or_identifier")
            row_key = directory_accounts.key(address) or ""
            carried = earlier.pop(row_key, None)
            if carried is not None:
                kwargs.update(carried)
                kept_bindings += 1
            else:
                kwargs.update(directory_accounts.columns(directory.accounts.get(row_key)))
        db.add(model(**kwargs))
    db.flush()

    audit.write_event(
        db,
        event_type=event_type,
        summary=(
            f"Merged {source_label}: {merged[0]} added, {merged[1]} updated"
            if merged is not None
            else f"Appended {len(rows)} {source_label} (kept {kept})"
            if append
            else f"Imported {len(rows)} {source_label} (replaced {replaced})"
        ),
        actor_user_id=user.id,
        session=session,
        payload=audit.counts(
            **(
                {"new": merged[0], "updated": merged[1], "unchanged": merged[2]}
                if merged is not None
                else {"new": len(rows), "kept": kept}
                if append
                else {"new": len(rows), "replaced": replaced}
            ),
            **(
                {"cascaded_assignments": cascaded_assignment_count}
                if cascaded_assignment_count is not None
                else {}
            ),
            # 19O.5 — a replace deletes every existing row and re-adds,
            # so it takes the relationships with it exactly as
            # `delete-all` does. Counted before `_replace_rows` runs.
            **(
                {"cascaded_relationships": cascaded_relationship_count}
                if cascaded_relationship_count is not None
                else {}
            ),
            # Segment 21F: what the directory check came to, over the
            # file's distinct addresses. Omitted when the caller ran none.
            **(directory.counts if directory is not None else {}),
            # Of the not-checked rows, those that kept the account an
            # earlier import bound them to (M1). Omitted when none did.
            **({"directory_kept": kept_bindings} if kept_bindings else {}),
        ),
        context=(
            {
                **({"filename": filename} if filename else {}),
                **({"mode": "append"} if append else {}),
                **({"mode": "upsert"} if merge else {}),
            }
            or None
        ),
        correlation_id=correlation_id,
    )

    unit_of_work.commit(db)
    unit_of_work.after_commit(
        db,
        lambda: log.info(
            "roster imported",
            extra={
                "session_id": session.id,
                "source": source_label,
                "new": merged[0] if merged is not None else len(rows),
                "replaced": replaced,
                **({"mode": "append", "kept": kept} if append else {}),
                **({"mode": "upsert"} if merge else {}),
                **(
                    {"cascaded_assignments": cascaded_assignment_count}
                    if cascaded_assignment_count is not None
                    else {}
                ),
                **(
                    {"cascaded_relationships": cascaded_relationship_count}
                    if cascaded_relationship_count is not None
                    else {}
                ),
                "correlation_id": correlation_id,
            },
        ),
    )
    return replaced, (merged[0] if merged is not None else len(rows))


def _detach_outbox_if_reviewers(
    db: Session, *, model: Any, session_id: int, rows: list[Any]
) -> None:
    """Clear the outbox FKs before a reviewer delete (19O.3).

    ``_save`` and ``_delete_all`` are generic over ``Reviewer`` /
    ``Reviewee`` / ``Observer``; only reviewers are referenced by
    ``email_outbox``, so only they need the unlink. Gated on the model
    rather than on the ids, because reviewer and reviewee ids overlap
    and an unguarded id list would unlink another table's rows.
    """
    if model is not Reviewer or not rows:
        return
    invitations_service.detach_outbox(
        db,
        session_id=session_id,
        reviewer_ids=[row.id for row in rows],
        reviewers_deleted=True,
    )


def _reaches_assignments(model: type) -> bool:
    """Whether deleting a ``model`` row deletes assignments: a reviewer
    or reviewee row does, through the foreign-key cascade; an observer
    row does not."""
    return model is Reviewer or model is Reviewee


def _count_assignments(db: Session, session_id: int) -> int:
    from app.db.models import Assignment

    stmt = select(func.count(Assignment.id)).where(
        Assignment.session_id == session_id
    )
    return int(db.execute(stmt).scalar_one())


def _count_relationships(db: Session, session_id: int) -> int:
    # The service's own counter, not a third copy of the query. Imported
    # inside the function because `relationships` imports this module at
    # its top level — a module-level import here would cycle.
    from app.services import relationships as relationships_service

    return relationships_service.existing_count(db, session_id)


def existing_assignment_count(db: Session, session_id: int) -> int:
    """Used by routes to surface the cascade warning before import."""
    return _count_assignments(db, session_id)


def delete_all_reviewers(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    correlation_id: str,
) -> tuple[int, int]:
    lifecycle.require_editable(db, review_session)
    return _delete_all(
        db,
        review_session=review_session,
        user=user,
        model=Reviewer,
        event_type="reviewers.deleted_all",
        source_label="reviewers",
        correlation_id=correlation_id,
    )


def delete_all_reviewees(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    correlation_id: str,
) -> tuple[int, int]:
    lifecycle.require_editable(db, review_session)
    return _delete_all(
        db,
        review_session=review_session,
        user=user,
        model=Reviewee,
        event_type="reviewees.deleted_all",
        source_label="reviewees",
        correlation_id=correlation_id,
    )


def delete_all_observers(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    correlation_id: str,
) -> tuple[int, int]:
    lifecycle.require_not_archived(db, review_session)
    return _delete_all(
        db,
        review_session=review_session,
        user=user,
        model=Observer,
        event_type="observers.deleted_all",
        source_label="observers",
        correlation_id=correlation_id,
    )


def _delete_all(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    model: Any,
    event_type: str,
    source_label: str,
    correlation_id: str,
) -> tuple[int, int]:
    lifecycle.invalidate_if_validated(
        db,
        review_session=review_session,
        user=user,
        reason=f"{source_label}_deleted_all",
        correlation_id=correlation_id,
    )
    # Omitted for observers, as in `_save` (findings S10).
    cascaded_assignments = (
        _count_assignments(db, review_session.id)
        if _reaches_assignments(model)
        else None
    )
    # 19O.5 — the whole session's relationships, because emptying either
    # roster empties them all. Taken before the delete: the cascade is
    # `ondelete="CASCADE"` on the FK with no ORM collection on either
    # parent, so a count afterwards always reads 0.
    cascaded_relationships = (
        _count_relationships(db, review_session.id)
        if roster_bulk.reaches_relationships(model)
        else None
    )
    rows = list(
        db.execute(
            select(model).where(model.session_id == review_session.id)
        ).scalars()
    )
    deleted = len(rows)
    _detach_outbox_if_reviewers(
        db, model=model, session_id=review_session.id, rows=rows
    )
    for row in rows:
        db.delete(row)
    db.flush()

    audit.write_event(
        db,
        event_type=event_type,
        summary=f"Deleted all {deleted} {source_label}",
        actor_user_id=user.id,
        session=review_session,
        payload=audit.counts(
            deleted=deleted,
            **(
                {"cascaded_assignments": cascaded_assignments}
                if cascaded_assignments is not None
                else {}
            ),
            # Omitted, not zero, for observers: nothing references them,
            # so their event keeps the payload it had.
            **(
                {"cascaded_relationships": cascaded_relationships}
                if cascaded_relationships is not None
                else {}
            ),
        ),
        correlation_id=correlation_id,
    )
    if model is Reviewer:
        # 20B — under symmetric review the reviewee roster follows.
        symmetric_review.sync_reviewees_from_reviewers(db, review_session)
    db.commit()
    log.info(
        "roster deleted",
        extra={
            "session_id": review_session.id,
            "source": source_label,
            "deleted": deleted,
            **(
                {"cascaded_assignments": cascaded_assignments}
                if cascaded_assignments is not None
                else {}
            ),
            **(
                {"cascaded_relationships": cascaded_relationships}
                if cascaded_relationships is not None
                else {}
            ),
            "correlation_id": correlation_id,
        },
    )
    return deleted, cascaded_assignments or 0
