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
from app.services.extracts.entity_metadata_extract import (
    SELF_REVIEW_HANDLING_DEFAULT,
    SELF_REVIEW_HANDLING_STATES,
    build_reviewee_metadata,
    build_reviewer_metadata,
    self_review_handling_filename_suffix,
)
from app.services.extracts.observers_extract import serialize_observers
from app.services.extracts.participant_tokens_extract import (
    serialize_participant_tokens,
)
from app.services.extracts.relationships_extract import serialize_relationships
from app.services.extracts.responses_extract import serialize_responses
from app.services.extracts.reviewees_extract import serialize_reviewees
from app.services.extracts.reviewers_extract import serialize_reviewers
from app.services.extracts.zip_bundle import (
    build_by_instrument_bundle,
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


@router.get("/sessions/{session_id}/export/observers.csv")
def export_observers_csv(
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    rows = list(serialize_observers(db, review_session))
    body_count = max(0, len(rows) - 1)

    audit.write_event(
        db,
        event_type="session.observers_extracted",
        summary=(
            f"Extracted Observers CSV for session {review_session.code} "
            f"({body_count} observers)"
        ),
        actor_user_id=user.id,
        session=review_session,
        payload=audit.counts(rows=body_count),
    )

    download_name = filename(review_session, "observers")
    return StreamingResponse(
        stream_csv(rows),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{download_name}"',
        },
    )


@router.get("/sessions/{session_id}/export/participant_tokens.csv")
def export_participant_tokens_csv(
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Operator-side deanonymization key — one row per Reviewer +
    Reviewee with the per-session opaque token the Anonymized
    ``by_instrument`` CSV swaps in for names + emails on the
    observer collation surface. Lets the operator answer "which
    row is ``R-a3f8b2c1``?" without re-hashing the roster by hand.

    No lifecycle gate (read-only); no ``observers_enabled`` gate
    on the route itself (the chrome that surfaces the download
    handles visibility), so a deep-link to the URL still works
    for diagnostics on a session that briefly toggled observers
    off."""
    rows = list(serialize_participant_tokens(db, review_session))
    body_count = max(0, len(rows) - 1)

    audit.write_event(
        db,
        event_type="session.participant_tokens_extracted",
        summary=(
            "Extracted participant tokens CSV for session "
            f"{review_session.code} ({body_count} rows)"
        ),
        actor_user_id=user.id,
        session=review_session,
        payload=audit.counts(rows=body_count),
    )

    download_name = filename(review_session, "participant_tokens")
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
    data_shapes: int = Query(default=1),
    tokens: int = Query(default=1),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> Response:
    """The Extract data tab's Zip-all bundle — the unified
    Responses CSV + reviewer/reviewee stats + one per-instrument
    CSV in one archive. Built fully in memory.

    ``?data_shapes=0`` excludes the saved Data shape CSVs
    from the bundle — driven by the intro card's
    ``Data shaper`` chip. Default (chip on) includes every
    saved shape, one CSV each named
    ``{code}_{slug(name)}.csv``.

    ``?tokens=0`` excludes ``participant_tokens.csv`` from the
    bundle — driven by the intro card's ``Token keys`` chip.
    The chip + CSV only render / ship when the session has
    ``observers_enabled`` on; without observers the tokens
    have no consumer.

    Filename: ``{code}_responses.zip``. Per
    ``guide/extract_data.md`` the per-card lens downloads are
    the fine-grained alternative; this button is the one-click
    "all response files" shortcut."""
    zip_bytes, counts = build_responses_bundle(
        db,
        review_session,
        include_data_shapes=(data_shapes != 0),
        include_participant_tokens=(tokens != 0),
    )

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


@router.get(
    "/sessions/{session_id}/export/by_instrument_bundle.zip"
)
def export_by_instrument_bundle_zip(
    instrument: list[int] | None = Query(default=None),
    meta: int = Query(default=1),
    all_rows: int = Query(default=1),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> Response:
    """The Extract data tab's By-instrument Zip-all button —
    one wide-format CSV per instrument carrying a meta header
    + the cross-reviewer comparison table. Filename:
    ``{code}_by_instrument.zip`` (members named
    ``{code}_by_instrument_{slug}.csv``). Per
    ``guide/extract_data.md``.

    Query params (driven by the card's chip row):

    * ``?instrument=42&instrument=43`` — only these instrument
      ids ship. Omitted = every instrument on the session.
    * ``?meta=0`` — drop the meta header block and the blank
      separator row from each CSV.
    * ``?all_rows=0`` — only assignment rows with at least one
      response ship in each CSV.
    """
    instrument_ids = set(instrument) if instrument else None
    zip_bytes, counts = build_by_instrument_bundle(
        db,
        review_session,
        instrument_ids=instrument_ids,
        include_metadata=meta != 0,
        include_empty_assignments=all_rows != 0,
    )

    audit.write_event(
        db,
        event_type="session.by_instrument_bundle_extracted",
        summary=(
            f"Extracted By-instrument bundle for session "
            f"{review_session.code}"
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
                f'attachment; filename="{code}_by_instrument.zip"'
            ),
        },
    )


def _normalise_self_review_handling(raw: str | None) -> str:
    """Coerce the ``?self_review_handling=`` query param to one of
    the three canonical states. Unknown / missing values fall back
    to ``include_self`` so a malformed link still returns a
    sensible default (today's behaviour pre-chip)."""
    if raw and raw in SELF_REVIEW_HANDLING_STATES:
        return raw
    return SELF_REVIEW_HANDLING_DEFAULT


def _metadata_download_name(
    review_session: ReviewSession, kind: str, suffix: str
) -> str:
    """Insert the Self-review handling chip's filename suffix
    (``_self`` / ``_noself`` / ``_both``) between the kind slug
    and the ``.csv`` extension. Falls through to :func:`filename`
    so the canonical-name policy stays in one place."""
    base = filename(review_session, kind)
    if base.endswith(".csv"):
        return base[: -len(".csv")] + suffix + ".csv"
    return base + suffix


@router.get("/sessions/{session_id}/export/reviewer_metadata.csv")
def export_reviewer_metadata_csv(
    instrument: list[int] | None = Query(default=None),
    all: int = Query(default=1),
    self_review_handling: str = Query(default=SELF_REVIEW_HANDLING_DEFAULT),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Backs the Extract data tab's Reviewer response metadata
    card. ``?instrument=<id>`` (repeated) drives the per-(instrument,
    field) column blocks; omitted = no per-field blocks (just the
    cross-instrument totals). ``?all=0`` filters body rows to
    reviewers with at least one non-empty response in scope.

    ``?self_review_handling=`` ∈ ``{"include_self", "exclude_self",
    "both"}`` drives the chip's three-state column shape (PR A of
    the Self-review handling chip slice per
    ``guide/extract_data.md`` § *Self-review handling*). Unknown
    values fall through to ``include_self`` so today's chip-less
    links keep working unchanged.
    """
    state = _normalise_self_review_handling(self_review_handling)
    instrument_ids = set(instrument) if instrument else None
    rows = build_reviewer_metadata(
        db,
        review_session,
        instrument_ids=instrument_ids,
        all_reviewers=all != 0,
        self_review_handling=state,
    )
    body_count = len(rows) - 1  # subtract header

    audit.write_event(
        db,
        event_type="session.reviewer_metadata_extracted",
        summary=(
            f"Extracted Reviewer response metadata for session "
            f"{review_session.code} ({body_count} rows)"
        ),
        actor_user_id=user.id,
        session=review_session,
        payload=audit.counts(
            rows=body_count,
            instruments=len(instrument_ids) if instrument_ids else 0,
        ),
        context={"self_review_handling": state},
    )

    download_name = _metadata_download_name(
        review_session,
        "reviewer_metadata",
        self_review_handling_filename_suffix(state),
    )
    return StreamingResponse(
        stream_csv(rows),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{download_name}"',
        },
    )


@router.get("/sessions/{session_id}/export/reviewee_metadata.csv")
def export_reviewee_metadata_csv(
    instrument: list[int] | None = Query(default=None),
    all: int = Query(default=1),
    self_review_handling: str = Query(default=SELF_REVIEW_HANDLING_DEFAULT),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Backs the Extract data tab's Reviewee response metadata
    card — symmetric to ``export_reviewer_metadata_csv``. See
    that route for the ``?self_review_handling=`` contract."""
    state = _normalise_self_review_handling(self_review_handling)
    instrument_ids = set(instrument) if instrument else None
    rows = build_reviewee_metadata(
        db,
        review_session,
        instrument_ids=instrument_ids,
        all_reviewees=all != 0,
        self_review_handling=state,
    )
    body_count = len(rows) - 1

    audit.write_event(
        db,
        event_type="session.reviewee_metadata_extracted",
        summary=(
            f"Extracted Reviewee response metadata for session "
            f"{review_session.code} ({body_count} rows)"
        ),
        actor_user_id=user.id,
        session=review_session,
        payload=audit.counts(
            rows=body_count,
            instruments=len(instrument_ids) if instrument_ids else 0,
        ),
        context={"self_review_handling": state},
    )

    download_name = _metadata_download_name(
        review_session,
        "reviewee_metadata",
        self_review_handling_filename_suffix(state),
    )
    return StreamingResponse(
        stream_csv(rows),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{download_name}"',
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
