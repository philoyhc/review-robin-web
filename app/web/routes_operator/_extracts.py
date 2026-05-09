"""Extract Data downloads — Segment 12A-1.

PR 1 ships the Settings CSV; PR 2 will add the per-entity
roster downloads (Reviewers / Reviewees) and PR 3 the manual-only
Assignments download. All extract routes live here so the route
file mirrors the Extract Data card on Session Home.

No lifecycle gate — extraction is read-only and useful in every
state (``draft`` / ``validated`` / ``ready`` / ``closed``). The
Extract Data card stays interactive even when the yellow lock
card is active; lock disables setup mutations only, not reads.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, User
from app.db.session import get_db
from app.services import audit
from app.services.extracts import filename, stream_csv
from app.services.extracts.reviewees_extract import serialize_reviewees
from app.services.extracts.reviewers_extract import serialize_reviewers
from app.services.session_config_io import (
    HEADER,
    serialize_session_config,
)
from app.web.deps import get_or_create_user, require_session_operator

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
