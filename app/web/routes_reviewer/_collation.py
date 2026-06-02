"""Observer collation surface — ``/me/sessions/{id}/collation``.

Two routes:

- ``GET .../collation`` — renders the per-instrument
  collation page. Each visible instrument (per Band 3
  observer-audience visibility policy) gets a 3-row table:
  reviewer-side cohort stats, reviewee-side cohort stats, and
  a conditional download button per the instrument's
  identification mode.
- ``GET .../collation/instruments/{instrument_id}.csv`` —
  streams the per-instrument CSV scoped to the observer's
  cohort. Identification mode (Raw / Anonymized) follows
  Band 3; ``Summarized`` returns 404 because no per-row
  download is offered.

Both routes gate on ``require_observer_in_session`` (the
authenticated user's email must match an active observer's
email in the session, case-insensitive).
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Instrument, Observer, ReviewSession, User
from app.db.session import get_db
from app.services import session_lifecycle as lifecycle
from app.services import visibility_policies
from app.services.extracts.by_instrument_extract import (
    by_instrument_filename_slug,
    serialize_by_instrument,
)
from app.services.observer_cohort import materialize_cohort
from app.web import views
from app.web.deps import get_or_create_user, require_observer_in_session
from app.web.routes_reviewer._shared import (
    _templates,
    build_role_chips,
    reviewer_review_count_for_user,
)

router = APIRouter(prefix="/me")


@router.get(
    "/sessions/{session_id}/collation",
    response_class=HTMLResponse,
)
def observer_collation(
    request: Request,
    observer_session: tuple[Observer, ReviewSession] = Depends(
        require_observer_in_session
    ),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    observer, review_session = observer_session
    context = views.build_observer_collation_context(
        db, observer=observer, review_session=review_session
    )
    return _templates.TemplateResponse(
        request,
        "reviewer/collation.html",
        {
            "user": user,
            "session": review_session,
            "reviewer_review_count": reviewer_review_count_for_user(
                db, user
            ),
            "role_chips": build_role_chips(
                db,
                user=user,
                review_session=review_session,
                active_role="observer",
            ),
            "collation": context,
        },
    )


@router.get(
    "/sessions/{session_id}/collation/instruments/{instrument_id}.csv"
)
def observer_collation_instrument_csv(
    instrument_id: int,
    observer_session: tuple[Observer, ReviewSession] = Depends(
        require_observer_in_session
    ),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Per-instrument CSV download for the observer collation
    surface. Returns the cohort-scoped slice in the
    identification mode the operator set on Band 3."""
    observer, review_session = observer_session

    instrument = db.execute(
        select(Instrument).where(
            Instrument.id == instrument_id,
            Instrument.session_id == review_session.id,
        )
    ).scalar_one_or_none()
    if instrument is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    # Band 3 mode for the observer audience on this instrument.
    policies = visibility_policies.list_for_instrument(db, instrument.id)
    policy = policies.get("observer")
    mode = visibility_policies.resolve_mode(
        policy,
        while_ongoing_open=lifecycle.is_ready(review_session),
        after_release_open=(
            lifecycle.is_response_release_window_open(review_session)
        ),
    )
    if mode is None or mode == "summarized":
        # Observer can't see this instrument right now, or the
        # operator picked Summarized (no per-row download).
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    cohort = materialize_cohort(db, observer=observer)
    if not cohort.reviewer_ids and not cohort.reviewee_ids:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    # Find instrument position in the session for the meta header
    # / filename slug.
    instruments_in_order = list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars()
    )
    try:
        position = next(
            i for i, x in enumerate(instruments_in_order) if x.id == instrument.id
        )
    except StopIteration:
        position = 0

    def _stream() -> Iterable[bytes]:
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        for row in serialize_by_instrument(
            db,
            review_session,
            instrument,
            position=position,
            cohort_filter=cohort,
            identification=mode,
        ):
            writer.writerow(row)
            yield buffer.getvalue().encode("utf-8")
            buffer.seek(0)
            buffer.truncate(0)

    filename = by_instrument_filename_slug(
        instrument, position=position, used=set()
    ) + ".csv"
    return StreamingResponse(
        _stream(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
