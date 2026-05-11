"""Extract Data downloads — Segment 12A-1 + 12A-3 + 12B.

Six GET routes, one per Extract Data card row:

- Settings (12A-1 PR 1) — 3-column key/value/data-type CSV.
- Reviewers / Reviewees (12A-1 PR 2) — wide CSVs that
  round-trip with the existing per-entity importers.
- Responses (12A-1 PR 4) — wide row-per-observation CSV for
  downstream analysis (no import counterpart).
- Relationships (12A-3 PR 1) — wide CSV that round-trips with
  the importer shipped by 15D PR 1.
- Audit log (12B PR 1) — wide CSV of ``audit_events`` rows
  for the session; system-emitted, no import counterpart.

The Manual Assignments route from 12A-1 PR 3 retired in
12A-3 PR 2 — assignments are derived post-15D (output, not
input), so the download has no place in a porting bundle.

All routes live here so the route file mirrors the Extract Data
card on Session Home.

No lifecycle gate — extraction is read-only and useful in every
state (``draft`` / ``validated`` / ``ready`` / ``closed``). The
Extract Data card stays interactive even when the yellow lock
card is active; lock disables setup mutations only, not reads.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, ReviewSession, User
from app.db.session import get_db
from app.services import audit, responses as responses_service
from app.services.extracts import filename, stream_csv
from app.services.extracts.audit_events_extract import serialize_audit_events
from app.services.extracts.relationships_extract import serialize_relationships
from app.services.extracts.responses_extract import serialize_responses
from app.services.extracts.reviewees_extract import serialize_reviewees
from app.services.extracts.reviewers_extract import serialize_reviewers
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


@router.get("/sessions/{session_id}/export/audit_log.csv")
def export_audit_log_csv(
    session_id: int,
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
    # Count up front so the audit event carries the row count
    # without materialising the streaming generator. The
    # ``session.audit_log_extracted`` event we're about to write
    # is NOT included in this count — the next download will
    # capture it (the recursion is bounded and intentional).
    body_count = db.execute(
        select(func.count())
        .select_from(AuditEvent)
        .where(AuditEvent.session_id == review_session.id)
    ).scalar_one()

    audit.write_event(
        db,
        event_type="session.audit_log_extracted",
        summary=(
            f"Extracted Audit log CSV for session {review_session.code} "
            f"({body_count} rows)"
        ),
        actor_user_id=user.id,
        session=review_session,
        payload=audit.counts(rows=body_count),
    )

    download_name = filename(review_session, "audit_log")
    # ``serialize_audit_events`` streams via a ``yield_per(1000)``
    # cursor; iterate lazily so memory stays flat on long-running
    # sessions.
    return StreamingResponse(
        stream_csv(serialize_audit_events(db, review_session)),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{download_name}"',
        },
    )
