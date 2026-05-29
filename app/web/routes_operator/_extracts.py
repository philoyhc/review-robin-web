"""Extract downloads — per-entity CSVs + two zip bundles.

Eight GET routes:

- Settings (12A-1 PR 1) — 3-column key/value/data-type CSV.
- Reviewers / Reviewees (12A-1 PR 2) — wide CSVs that
  round-trip with the existing per-entity importers.
- Responses (12A-1 PR 4) — analysis-facing per-session CSV
  (no import counterpart).
- Relationships (12A-3 PR 1) — wide CSV that round-trips with
  the importer shipped by 15D PR 1.
- Setup bundle — ``bundle.zip`` (filename ``{code}_setup.zip``).
  Setup-only members (Reviewers + Reviewees + Relationships +
  Settings) for the Session Home Extract Setup card.
- Responses bundle — ``responses_bundle.zip`` (filename
  ``{code}_responses.zip``). Backs the new Extract data
  Operations-strip tab's "Zip all" button. Members: unified
  Responses + reviewer/reviewee stats + per-instrument files.
- Audit log (12B PR 1) — wide CSV of ``audit_events`` rows
  for the session; system-emitted, no import counterpart.

The Manual Assignments route from 12A-1 PR 3 retired in
12A-3 PR 2 — assignments are derived post-15D (output, not
input), so the download has no place in a porting bundle.

No lifecycle gate — extraction is read-only and useful in every
state (``draft`` / ``validated`` / ``ready`` / ``closed``).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, ReviewSession, User
from app.db.session import get_db
from app.services import audit, responses as responses_service
from app.web import views as audit_views
from app.services.extracts import filename, stream_csv
from app.services.extracts.audit_events_extract import serialize_audit_events
from app.services.extracts.relationships_extract import serialize_relationships
from app.services.extracts.responses_extract import serialize_responses
from app.services.extracts.reviewees_extract import serialize_reviewees
from app.services.extracts.reviewers_extract import serialize_reviewers
from app.services.extracts.zip_bundle import (
    build_responses_bundle,
    build_setup_bundle,
)
from app.services.session_config_io import (
    HEADER,
    serialize_session_config,
)
from app.web.deps import (
    get_or_create_user,
    require_session_operator,
    require_sys_admin,
)

router = APIRouter()


@router.get("/sessions/{session_id}/export/settings.csv")
def export_settings_csv(
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    rows = serialize_session_config(db, review_session)
    payload_rows: list[tuple[str, ...]] = [HEADER]
    payload_rows.extend((r.field, r.value, r.data_type) for r in rows)

    audit.write_event(
        db,
        event_type="session.settings_extracted",
        summary=(
            f"Extracted Settings CSV for session {review_session.code} "
            f"({len(rows)} rows)"
        ),
        actor_user_id=user.id,
        session=review_session,
        payload=audit.counts(rows=len(rows)),
    )

    download_name = filename(review_session, "settings")
    return StreamingResponse(
        stream_csv(payload_rows),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{download_name}"',
        },
    )


@router.get("/sessions/{session_id}/export/reviewers.csv")
def export_reviewers_csv(
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    rows = list(serialize_reviewers(db, review_session))
    # First row is the header — body row count is everything else.
    body_count = max(0, len(rows) - 1)

    audit.write_event(
        db,
        event_type="session.reviewers_extracted",
        summary=(
            f"Extracted Reviewers CSV for session {review_session.code} "
            f"({body_count} reviewers)"
        ),
        actor_user_id=user.id,
        session=review_session,
        payload=audit.counts(rows=body_count),
    )

    download_name = filename(review_session, "reviewers")
    return StreamingResponse(
        stream_csv(rows),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{download_name}"',
        },
    )


@router.get("/sessions/{session_id}/export/reviewees.csv")
def export_reviewees_csv(
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    rows = list(serialize_reviewees(db, review_session))
    body_count = max(0, len(rows) - 1)

    audit.write_event(
        db,
        event_type="session.reviewees_extracted",
        summary=(
            f"Extracted Reviewees CSV for session {review_session.code} "
            f"({body_count} reviewees)"
        ),
        actor_user_id=user.id,
        session=review_session,
        payload=audit.counts(rows=body_count),
    )

    download_name = filename(review_session, "reviewees")
    return StreamingResponse(
        stream_csv(rows),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{download_name}"',
        },
    )


@router.get("/sessions/{session_id}/export/relationships.csv")
def export_relationships_csv(
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    rows = list(serialize_relationships(db, review_session))
    body_count = max(0, len(rows) - 1)

    audit.write_event(
        db,
        event_type="session.relationships_extracted",
        summary=(
            f"Extracted Relationships CSV for session {review_session.code} "
            f"({body_count} relationships)"
        ),
        actor_user_id=user.id,
        session=review_session,
        payload=audit.counts(rows=body_count),
    )

    download_name = filename(review_session, "relationships")
    return StreamingResponse(
        stream_csv(rows),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{download_name}"',
        },
    )


@router.get("/sessions/{session_id}/export/responses.csv")
def export_responses_csv(
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    # Count up front so the audit event carries the row count
    # without materialising the streaming generator. ``Response``
    # row count is the body row count (header excluded), per the
    # segment plan's ``len(responses)`` invariant.
    body_count = responses_service.session_response_count(
        db, review_session.id
    )

    audit.write_event(
        db,
        event_type="session.responses_extracted",
        summary=(
            f"Extracted Responses CSV for session {review_session.code} "
            f"({body_count} rows)"
        ),
        actor_user_id=user.id,
        session=review_session,
        payload=audit.counts(rows=body_count),
    )

    download_name = filename(review_session, "responses")
    # ``serialize_responses`` is a streaming generator (yield_per
    # cursor); the StreamingResponse iterates it lazily so memory
    # stays flat on sessions with hundreds of thousands of rows.
    return StreamingResponse(
        stream_csv(serialize_responses(db, review_session)),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{download_name}"',
        },
    )


@router.get("/sessions/{session_id}/export/bundle.zip")
def export_bundle_zip(
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> Response:
    """The Extract Setup card's Zip-all bundle — the four porting
    CSVs (Reviewers / Reviewees / Relationships / Settings) in
    one archive. Built fully in memory.

    Filename: ``{code}_setup.zip``. Slimmed from the original
    "session bundle" on 2026-05-29 when response-data download
    moved to the Extract data Operations tab (per
    ``guide/extract_data.md``)."""
    zip_bytes, counts = build_setup_bundle(db, review_session)

    audit.write_event(
        db,
        event_type="session.setup_bundle_extracted",
        summary=(
            f"Extracted Setup bundle for session {review_session.code}"
        ),
        actor_user_id=user.id,
        session=review_session,
        payload=audit.counts(**counts),
    )

    code = (review_session.code or "session").strip() or "session"
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{code}_setup.zip"',
        },
    )


@router.get("/sessions/{session_id}/export/responses_bundle.zip")
def export_responses_bundle_zip(
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> Response:
    """The Extract data tab's Zip-all bundle — the unified
    Responses CSV + reviewer/reviewee stats + one per-instrument
    CSV in one archive. Built fully in memory.

    Filename: ``{code}_responses.zip``. Per
    ``guide/extract_data.md`` the per-card lens downloads are
    the fine-grained alternative; this button is the one-click
    "all response files" shortcut."""
    zip_bytes, counts = build_responses_bundle(db, review_session)

    audit.write_event(
        db,
        event_type="session.responses_bundle_extracted",
        summary=(
            f"Extracted Responses bundle for session {review_session.code}"
        ),
        actor_user_id=user.id,
        session=review_session,
        payload=audit.counts(**counts),
    )

    code = (review_session.code or "session").strip() or "session"
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{code}_responses.zip"'
            ),
        },
    )


@router.get("/sessions/{session_id}/export/audit_log.csv")
def export_audit_log_csv(
    session_id: int,
    event_type: list[str] | None = Query(default=None),
    severity: list[str] | None = Query(default=None),
    actor: str | None = Query(default=None),
    from_: str | None = Query(default=None, alias="from"),
    to: str | None = Query(default=None),
    user: User = Depends(require_sys_admin),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    # Gate tightened from the relaxed
    # ``require_sys_admin_or_session_operator`` to plain
    # ``require_sys_admin`` (Segment 16C PR 1) — the
    # operator-facing entry point retired with 12B PR 2 →
    # 16A PR 4, and now the Sessions Diagnostics row's "Audit
    # log" link lands on the sys-admin-only child page. The
    # CSV route stays at its current URL so existing
    # programmatic consumers keep working, just gated tighter.
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.id == session_id)
    ).scalar_one_or_none()
    if review_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    # Filter set shared with the in-app viewer (16C PR 2). The
    # Download CSV button on the viewer carries the page's query
    # string over so the spreadsheet honours the active filter
    # strip. Direct hits to the route URL with no filter params
    # produce the full unfiltered CSV (the pre-PR-2 shape).
    try:
        filters = audit_views.parse_audit_log_filters(
            event_types=event_type,
            severities=severity,
            actor=actor,
            from_=from_,
            to=to,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"audit log filter parsing failed: {exc}",
        ) from exc
    # Count up front so the audit event carries the row count
    # without materialising the streaming generator. The
    # ``session.audit_log_extracted`` event we're about to write
    # is NOT included in this count — the next download will
    # capture it (the recursion is bounded and intentional).
    count_stmt = (
        select(func.count())
        .select_from(AuditEvent)
        .where(AuditEvent.session_id == review_session.id)
    )
    # _apply_filters needs the LEFT-JOIN on users.email when
    # actor filtering is active. For the count we want the same
    # WHERE clauses without the join overhead when actor filter
    # is empty — split the cases to stay cheap.
    if filters.actor_email:
        from app.db.models import User as _User

        count_stmt = (
            select(func.count())
            .select_from(AuditEvent)
            .outerjoin(_User, _User.id == AuditEvent.actor_user_id)
            .where(AuditEvent.session_id == review_session.id)
        )
        count_stmt = audit._apply_filters(count_stmt, filters, _User)
    else:
        # No actor filter → no join needed. Just augment WHERE.
        from app.db.models import User as _User

        count_stmt = audit._apply_filters(count_stmt, filters, _User)
    body_count = db.execute(count_stmt).scalar_one()

    audit_event_payload = audit.counts(rows=body_count)
    audit.write_event(
        db,
        event_type="session.audit_log_extracted",
        summary=(
            f"Extracted Audit log CSV for session {review_session.code} "
            f"({body_count} rows"
            f"{', filtered' if filters.is_active else ''})"
        ),
        actor_user_id=user.id,
        session=review_session,
        payload=audit_event_payload,
        context=filters.as_audit_context() or None,
    )

    download_name = filename(review_session, "audit_log")
    # ``serialize_audit_events`` streams via a ``yield_per(1000)``
    # cursor; iterate lazily so memory stays flat on long-running
    # sessions.
    return StreamingResponse(
        stream_csv(serialize_audit_events(db, review_session, filters=filters)),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{download_name}"',
        },
    )
