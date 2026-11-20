"""Handoffs from another Cordware application (segment 23A).

The proof of concept's RRW side: a holding page that another
application opens in a new tab during its operator's click, while it
posts the setup that creates the session, then moves the tab to that
session's Session Home (`cordware/docs/cordware_interoperability_consolidated_spec_v0.3.md`
§7.1); the create and the re-send (segment 23F), which run Quick Setup's
pipeline, ``app/web/quick_setup_pipeline.py``, outside the package so no
slice imports another (segment 23I); and the status and results reads.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from fastapi import (
    APIRouter,
    Depends,
    Request,
    status,
)
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, User
from app.db.session import get_db
from app.schemas.sessions import SessionCreate
from app.services import (
    handoffs,
    linked_apps,
    linked_instruments,
    linked_settings,
    session_config_io,
    session_owners,
    sessions,
)
from app.web import breadcrumbs, urls, views
from app.web import quick_setup_pipeline as pipeline
from app.web.deps import (
    OperatorAllowlistDenied,
    get_or_create_user,
    request_correlation_id,
)
from app.web.downloads import content_disposition
from app.web.routes_operator._shared import (
    _templates,
    directory_or_none,
)

router = APIRouter()

#: Never cached: the page stands in while a session is created.
_NO_STORE = {"Cache-Control": "no-store"}


@router.get("/handoffs/new", response_class=HTMLResponse)
def handoff_holding(request: Request, user: User = Depends(get_or_create_user)) -> HTMLResponse:
    return _templates.TemplateResponse(
        request,
        "operator/handoff_new.html",
        {"user": user, "breadcrumbs": breadcrumbs.operator_sessions_child("New session")},
        headers=_NO_STORE,
    )


def _refused(request: Request, exc: handoffs.HandoffError) -> JSONResponse:
    body: dict[str, object] = {"error": exc.code}
    if exc.details:
        body["details"] = exc.details
    if exc.review_session is not None:
        body["session_home_url"] = urls.url_path(
            request, f"/operator/sessions/{exc.review_session.public_id}"
        )
    return JSONResponse(body, status_code=exc.status, headers=_NO_STORE)


@router.get("/handoffs/{transfer_id}/status", response_model=None)
def handoff_status(
    request: Request,
    transfer_id: str,
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """A handed-off session's live status, for the sender that made it
    (segment 23B; `spec/handoffs.md`). JSON, ``no-store``, read only."""
    try:
        review_session = handoffs.linked(db, user, transfer_id)
    except handoffs.HandoffError as exc:
        return _refused(request, exc)
    body = views.handoff_status(db, review_session)
    body["session_home_url"] = urls.url_path(
        request, f"/operator/sessions/{review_session.public_id}"
    )
    return JSONResponse(body, headers=_NO_STORE)


def _not_modified(if_none_match: str | None, etag: str) -> bool:
    """RFC 9110 §13.1.2: a weak comparison against a list of tags, or *."""
    if not if_none_match:
        return False
    tags = [tag.strip().removeprefix("W/") for tag in if_none_match.split(",")]
    return "*" in tags or etag in tags


def _csv(
    request: Request,
    transfer_id: str,
    user: User,
    db: Session,
    build: Callable[[Session, ReviewSession], handoffs.CsvSnapshot],
) -> Response:
    try:
        review_session = handoffs.linked(db, user, transfer_id)
    except handoffs.HandoffError as exc:
        return _refused(request, exc)
    snapshot = build(db, review_session)
    headers = {
        **_NO_STORE,
        "ETag": snapshot.etag,
        "X-Review-Robin-As-Of": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    # Already up to date (interop spec §6.5): nothing taken, nothing audited.
    if _not_modified(request.headers.get("if-none-match"), snapshot.etag):
        return Response(status_code=304, headers=headers)
    handoffs.record_export(db, review_session, user, transfer_id, snapshot)
    headers["Content-Disposition"] = content_disposition(f"{review_session.code}_{snapshot.name}")
    return Response(snapshot.body, media_type="text/csv; charset=utf-8", headers=headers)


@router.get("/handoffs/{transfer_id}/results.csv", response_model=None)
def handoff_results(
    request: Request,
    transfer_id: str,
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> Response:
    """The submitted answers of a handed-off session, for its sender
    (segment 23B; `spec/handoffs.md`). Audited as an export."""
    return _csv(request, transfer_id, user, db, handoffs.results_csv)


@router.get("/handoffs/{transfer_id}/completion.csv", response_model=None)
def handoff_completion(
    request: Request,
    transfer_id: str,
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> Response:
    """Where each assignment of a handed-off session stands, for its
    sender (segment 23B). No answers. Audited as an export."""
    return _csv(request, transfer_id, user, db, handoffs.completion_csv)


# --------------------------------------------------------------------------- #
# The create and the re-send (segments 23A, 23F), which run Quick Setup's
# pipeline (``app/web/quick_setup_pipeline.py``)
# --------------------------------------------------------------------------- #

#: Every handoff answer: JSON, never cached (interop spec §7.1).
_HANDOFF_HEADERS = {"Cache-Control": "no-store"}


def _handoff_error(
    code: str, status_code: int, details: list[str] | None = None, **extra: str
) -> JSONResponse:
    body: dict[str, object] = {"error": code, **extra}
    if details:
        body["details"] = details
    return JSONResponse(body, status_code=status_code, headers=_HANDOFF_HEADERS)


def _session_home(request: Request, review_session: ReviewSession) -> str:
    return urls.url_path(request, f"/operator/sessions/{review_session.public_id}")


def _handoff_refused(request: Request, exc: handoffs.HandoffError) -> JSONResponse:
    extra: dict[str, str] = {}
    if exc.reason:
        extra["reason"] = exc.reason
    if exc.slot:
        extra["slot"] = exc.slot
    if exc.review_session is not None:
        extra["session_home_url"] = _session_home(request, exc.review_session)
    return _handoff_error(exc.code, exc.status, exc.details, **extra)


def _handoff_receipt(
    request: Request, review_session: ReviewSession, status_word: str
) -> dict[str, str]:
    return {
        "status": status_word,
        "session_ref": review_session.public_id,
        "session_code": review_session.code,
        "session_home_url": _session_home(request, review_session),
    }


async def _handoff_body(request: Request) -> bytes | JSONResponse:
    """The request's body, or the refusal of its headers or size."""
    # A JSON body is the cross-site guard, as the directory endpoints';
    # a browser that names any other origin is refused outright.
    if request.headers.get("sec-fetch-site", "same-origin") != "same-origin":
        return _handoff_error("not_authorized", status.HTTP_403_FORBIDDEN)
    media = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if media != "application/json":
        return _handoff_error("invalid_package", status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)
    # Refused unread when undeclared (a chunked body), as the directory
    # endpoints do: the cap is checked before anything is held.
    declared = request.headers.get("content-length", "")
    if not declared.isdigit():
        return _handoff_error("invalid_package", status.HTTP_411_LENGTH_REQUIRED)
    if int(declared) > handoffs.MAX_BYTES:
        return _handoff_error("invalid_package", status.HTTP_413_CONTENT_TOO_LARGE)
    body = await request.body()
    if len(body) > handoffs.MAX_BYTES:
        return _handoff_error("invalid_package", status.HTTP_413_CONTENT_TOO_LARGE)
    return body


@router.post("/handoffs/sessions", response_model=None)
async def create_handoff_session(
    request: Request,
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Create a draft session from another application's rosters, and its
    settings when it sends them, all or nothing (`spec/handoffs.md`). The
    package gate has already checked that the signer-in is an RRW
    operator. Nothing is prepared, activated, invited or sent here."""
    body = await _handoff_body(request)
    if isinstance(body, JSONResponse):
        return body
    try:
        bundle = handoffs.parse_bundle(body)
    except handoffs.HandoffError as exc:
        return _handoff_refused(request, exc)

    try:
        prior = handoffs.replayed(db, user, bundle)
    except handoffs.HandoffError as exc:
        return _handoff_refused(request, exc)
    if prior is not None:
        return JSONResponse(
            _handoff_receipt(request, prior, "already_created"), headers=_HANDOFF_HEADERS
        )
    try:
        handoffs.check_linked(bundle)
    except handoffs.HandoffError as exc:
        return _handoff_refused(request, exc)
    try:
        sessions.ensure_code_available(db, bundle.code)
    except sessions.SessionCodeTakenError:
        return _handoff_error("session_code_conflict", status.HTTP_409_CONFLICT)
    try:
        payload = SessionCreate(name=bundle.name, code=bundle.code)
    except ValidationError:
        return _handoff_error(
            "invalid_package",
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            ["The session name or code is not valid."],
        )
    if not await run_in_threadpool(session_owners.lock_owner_eligible, db, user):
        raise OperatorAllowlistDenied()

    correlation_id = request_correlation_id()
    # The draft and its transfer record commit together (Codex, cordware#202).
    review_session = sessions.create_session(
        db, user=user, payload=payload, correlation_id=correlation_id, commit=False
    )
    handoffs.record_created(db, review_session, user, bundle, correlation_id)

    def discard() -> None:
        # All or nothing (author, 2026-11-11): the draft goes with its
        # files when they do not all apply, settings included (23D).
        db.rollback()
        sessions.delete_session(
            db, review_session=review_session, user=user, correlation_id=correlation_id
        )

    try:
        refusal = await pipeline.run_contents(
            contents=bundle.files,
            filenames={kind: f"{kind}.csv" for kind in bundle.files},
            review_session=review_session,
            user=user,
            db=db,
            confirm_replace="true",
            acknowledge_response_loss=None,
            replacing=False,
            correlation_id=correlation_id,
            directory=directory_or_none(request),
        )
    except Exception:
        discard()
        raise
    if refusal is not None:
        discard()
        if refusal.failure.reason == views.DIRECTORY_SIGN_IN:
            # Nothing wrong with the files: the operator's directory
            # sign-in lapsed, which only they can renew, in Review Robin.
            return _handoff_error(
                "directory_sign_in",
                status.HTTP_409_CONFLICT,
                ["Your Review Robin sign-in to the directory has lapsed."],
            )
        return _handoff_error(
            "invalid_setup",
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            refusal.failure.details,
            slot=refusal.kind,
            reason=refusal.failure.reason,
        )
    try:
        handoffs.check_rosters(db, review_session)
        handoffs.set_up_instrument(db, review_session, user)
    except handoffs.HandoffError as exc:
        discard()
        return _handoff_refused(request, exc)
    handoffs.record_completed(db, review_session, user, bundle)
    return JSONResponse(
        _handoff_receipt(request, review_session, "created"),
        status_code=status.HTTP_201_CREATED,
        headers=_HANDOFF_HEADERS,
    )


@router.post("/handoffs/{transfer_id}/update", response_model=None)
async def update_handoff_session(
    transfer_id: str,
    request: Request,
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Re-send a linked, unopened draft's rosters and the session settings
    its application owns (segment 23F): the draft the transfer
    ``transfer_id`` created, updated all or nothing through the create's
    pipeline (`spec/handoffs.md` §6a)."""
    body = await _handoff_body(request)
    if isinstance(body, JSONResponse):
        return body
    try:
        bundle = handoffs.parse_bundle(body, operation=handoffs.UPDATE_OPERATION)
        prior = handoffs.prior_update(db, user, bundle)
    except handoffs.HandoffError as exc:
        return _handoff_refused(request, exc)
    if prior is not None:
        return JSONResponse(
            _handoff_receipt(request, prior, "already_updated"), headers=_HANDOFF_HEADERS
        )
    try:
        review_session = handoffs.update_target(db, user, transfer_id, bundle)
        handoffs.check_linked(bundle)
    except handoffs.HandoffError as exc:
        return _handoff_refused(request, exc)
    # A settings file carries the session fields the application owns
    # (rung 3): checked here, written in the save's unit with the rosters.
    files = dict(bundle.files)
    sent_settings = files.pop("settings", None)
    settings: session_config_io.SessionSettings | None = None
    profile = linked_apps.profile_of(review_session)
    if sent_settings is not None and profile is not None:
        try:
            settings = linked_settings.prepare(db, review_session, profile, sent_settings)
        except linked_settings.NotOwned as exc:
            return _handoff_error(
                "invalid_setup",
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                [f"Not the sending application's to set: {', '.join(exc.fields)}."],
                slot="settings",
                reason="not_owned",
            )
        except linked_settings.SettingsRefused as exc:
            return _handoff_error(
                "invalid_setup",
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                exc.details,
                slot="settings",
            )
        except sessions.SessionCodeTakenError:
            return _handoff_error("session_code_conflict", status.HTTP_409_CONFLICT)
    correlation_id = request_correlation_id()

    # A linked instrument's display fields are the operator's from the
    # create on: read under the lock, before the reviewee save seeds more.
    shown: set[tuple[str, str]] = set()

    def guard() -> None:
        handoffs.guard_update(db, user, review_session, bundle)
        if linked_apps.locks(review_session, linked_apps.Lock.INSTRUMENT_STRUCTURE):
            shown.update(linked_instruments.display_sources(db, review_session))

    def record() -> None:
        if settings is not None:
            linked_settings.apply(
                db, review_session, settings, user=user, correlation_id=correlation_id
            )
        linked_instruments.keep_display_fields(db, review_session, shown, actor=user)
        handoffs.record_updated(db, review_session, user, bundle, correlation_id)

    try:
        refusal = await pipeline.run_contents(
            contents=files,
            filenames={kind: f"{kind}.csv" for kind in files},
            review_session=review_session,
            user=user,
            db=db,
            confirm_replace="true",
            acknowledge_response_loss=None,
            replacing=True,
            correlation_id=correlation_id,
            directory=directory_or_none(request),
            # Under the save's lock: not applied by an overlapping retry,
            # still linked, unopened and without responses, so neither a
            # duplicate nor an Unlink or activation since the checks above
            # is overwritten; and the settings and the record commit with
            # the rosters, so a retry finds the whole re-send or none of it.
            unit_guard=guard,
            unit_record=record,
        )
    except sessions.SessionCodeTakenError:
        db.rollback()
        return _handoff_error("session_code_conflict", status.HTTP_409_CONFLICT)
    except linked_settings.SettingsRefused as exc:
        # The schedule, rechecked under the lock (``linked_settings.apply``).
        db.rollback()
        return _handoff_error(
            "invalid_setup", status.HTTP_422_UNPROCESSABLE_CONTENT, exc.details, slot="settings"
        )
    except handoffs.AlreadyUpdated as done:
        db.rollback()
        return JSONResponse(
            _handoff_receipt(request, done.review_session, "already_updated"),
            headers=_HANDOFF_HEADERS,
        )
    except handoffs.HandoffError as exc:
        db.rollback()
        return _handoff_refused(request, exc)
    if refusal is not None:
        db.rollback()
        if refusal.failure.reason == views.DIRECTORY_SIGN_IN:
            return _handoff_error(
                "directory_sign_in",
                status.HTTP_409_CONFLICT,
                ["Your Review Robin sign-in to the directory has lapsed."],
            )
        return _handoff_error(
            "invalid_setup",
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            refusal.failure.details,
            slot=refusal.kind,
            reason=refusal.failure.reason,
        )
    return JSONResponse(
        _handoff_receipt(request, review_session, "updated"), headers=_HANDOFF_HEADERS
    )
