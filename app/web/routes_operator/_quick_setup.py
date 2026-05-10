"""Quick Setup card on Session Home — per-slot lock toggle, per-slot
submit handlers (reviewers / reviewees / assignments), and the
consolidated submit-all handler. Also owns ``POST /sessions``
(``create_session``), which dispatches the same per-slot pipeline
when the operator stages uploads on the new-session page.

Slice 7 of the major refactor.

Source range in pre-refactor ``routes_operator.py``: 669-1259
(plus ``create_session`` from 80-205, deferred from PR 5 because
of its tight coupling to the helpers in this slice).
"""

from __future__ import annotations

from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, User
from app.db.session import get_db
from app.schemas.sessions import SessionCreate
from app.services import (
    assignments,
    csv_imports,
    relationships as relationships_service,
    session_config_io,
    sessions,
)
from app.services import session_lifecycle as lifecycle
from app.web.deps import (
    get_or_create_user,
    request_correlation_id,
    require_session_operator,
)
from app.web.routes_operator._shared import (
    _quick_setup_cookie_name,
    _require_response_loss_ack,
)


router = APIRouter()


@router.post("/sessions", response_model=None)
async def create_session(
    name: str = Form(...),
    code: str = Form(...),
    description: str | None = Form(default=None),
    deadline: str | None = Form(default=None),
    help_contact: str | None = Form(default=None),
    reviewers_file: UploadFile | None = File(default=None),
    reviewees_file: UploadFile | None = File(default=None),
    relationships_file: UploadFile | None = File(default=None),
    settings_file: UploadFile | None = File(default=None),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    parsed_deadline: datetime | None = None
    if deadline:
        try:
            parsed_deadline = datetime.fromisoformat(deadline)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="deadline must be ISO-8601",
            ) from exc

    payload = SessionCreate(
        name=name,
        code=code,
        description=description or None,
        deadline=parsed_deadline,
        help_contact=help_contact or None,
    )
    review_session = sessions.create_session(
        db,
        user=user,
        payload=payload,
        correlation_id=request_correlation_id(),
    )

    # If the operator staged any Quick Setup uploads on the new-session
    # page, dispatch them through the same per-slot pipeline used by
    # the consolidated submit-all handler on Session Home. The session
    # was just created — no replace-confirmation is needed (there's
    # nothing to overwrite). On the first slot's failure, redirect to
    # Home with the slot's error flag.
    home_url = f"/operator/sessions/{review_session.id}"

    def quick_setup_error_redirect(
        kind: str, reason: str
    ) -> RedirectResponse:
        return RedirectResponse(
            url=(
                f"{home_url}?quick_setup_error={kind}"
                f"&quick_setup_reason={reason}#quick-setup-{kind}"
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    last_fragment = ""

    if reviewers_file is not None and reviewers_file.filename:
        reason = await _run_quick_setup_import(
            file=reviewers_file,
            confirm_replace="true",
            acknowledge_response_loss=None,
            review_session=review_session,
            user=user,
            db=db,
            kind="reviewers",
            existing_count_fn=csv_imports.existing_reviewer_count,
            parse_fn=csv_imports.parse_reviewer_csv,
            save_fn=csv_imports.save_reviewers,
        )
        if reason is not None:
            return quick_setup_error_redirect("reviewers", reason)
        last_fragment = "#quick-setup-reviewers"

    if reviewees_file is not None and reviewees_file.filename:
        reason = await _run_quick_setup_import(
            file=reviewees_file,
            confirm_replace="true",
            acknowledge_response_loss=None,
            review_session=review_session,
            user=user,
            db=db,
            kind="reviewees",
            existing_count_fn=csv_imports.existing_reviewee_count,
            parse_fn=csv_imports.parse_reviewee_csv,
            save_fn=csv_imports.save_reviewees,
        )
        if reason is not None:
            return quick_setup_error_redirect("reviewees", reason)
        last_fragment = "#quick-setup-reviewees"

    if relationships_file is not None and relationships_file.filename:
        reason = await _run_quick_setup_relationships(
            file=relationships_file,
            confirm_replace="true",
            review_session=review_session,
            user=user,
            db=db,
        )
        if reason is not None:
            return quick_setup_error_redirect("relationships", reason)
        last_fragment = "#quick-setup-relationships"

    if settings_file is not None and settings_file.filename:
        reason = await _run_quick_setup_settings(
            file=settings_file,
            review_session=review_session,
            user=user,
            db=db,
        )
        if reason is not None:
            return quick_setup_error_redirect("settings", reason)
        last_fragment = "#quick-setup-settings"

    return RedirectResponse(
        url=f"{home_url}{last_fragment}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


# --------------------------------------------------------------------------- #
# Segment 11J PR A — Quick Setup card live wiring
# --------------------------------------------------------------------------- #
#
# Three live POST endpoints back the Quick Setup card on Session Home:
#
#   - ``POST /sessions/{id}/quick-setup/lock`` flips the per-session
#     ``HttpOnly`` cookie that drives the card's ``is_locked`` state.
#   - ``POST /sessions/{id}/quick-setup/reviewers`` /
#     ``POST /sessions/{id}/quick-setup/reviewees`` delegate to a thin
#     ``_handle_quick_setup_import`` wrapper that reuses the existing
#     per-entity import pipeline. On success the wrapper 303s back to
#     Session Home with no flag (the slot's count indicator is the
#     success signal). On parse / validation / lifecycle rejection it
#     303s with ``?quick_setup_error={kind}&quick_setup_reason=...``
#     so the GET render places a ``.banner.banner-error`` inside the
#     offending slot.


@router.post(
    "/sessions/{session_id}/quick-setup/lock",
    response_class=HTMLResponse,
    response_model=None,
)
def quick_setup_lock_toggle(
    action: str = Form(...),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Flip the Quick Setup card's per-session lock cookie.

    ``action="unlock"`` sets ``qsu_{id}=1`` (and the next render
    drops ``.locked`` from the body wrapper); ``action="lock"`` clears
    the cookie. The toggle is visual only — the service layer
    (``_require_editable``) stays the source of truth for whether a
    slot's submit can mutate.
    """

    redirect = RedirectResponse(
        url=(
            f"/operator/sessions/{review_session.id}#quick-setup"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )
    cookie_name = _quick_setup_cookie_name(review_session.id)
    # Path ``/`` so the cookie is visible on every subsequent request
    # — including pages outside ``/operator/sessions/{id}/`` like
    # ``/operator/sessions`` (lobby), ``/operator/settings``, and
    # ``/about``. The navigation middleware in ``app/main.py`` deletes
    # the cookie on any path that isn't Session Home or a quick-setup
    # endpoint, so leaving Home from any direction relocks the card.
    cookie_path = "/"
    if action == "unlock":
        redirect.set_cookie(
            key=cookie_name,
            value="1",
            path=cookie_path,
            httponly=True,
            samesite="lax",
        )
    else:
        redirect.delete_cookie(
            key=cookie_name,
            path=cookie_path,
        )
    # Touch unused params to silence type checkers; ``user`` / ``db``
    # are pulled in for the operator-permission dependency chain.
    del user, db
    return redirect


@router.post(
    "/sessions/{session_id}/quick-setup/reviewers",
    response_class=HTMLResponse,
    response_model=None,
)
async def quick_setup_reviewers_submit(
    request: Request,
    file: UploadFile = File(...),
    confirm_replace: str | None = Form(default=None),
    acknowledge_response_loss: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    return await _handle_quick_setup_import(
        request=request,
        file=file,
        confirm_replace=confirm_replace,
        acknowledge_response_loss=acknowledge_response_loss,
        review_session=review_session,
        user=user,
        db=db,
        kind="reviewers",
        existing_count_fn=csv_imports.existing_reviewer_count,
        parse_fn=csv_imports.parse_reviewer_csv,
        save_fn=csv_imports.save_reviewers,
    )


@router.post(
    "/sessions/{session_id}/quick-setup/reviewees",
    response_class=HTMLResponse,
    response_model=None,
)
async def quick_setup_reviewees_submit(
    request: Request,
    file: UploadFile = File(...),
    confirm_replace: str | None = Form(default=None),
    acknowledge_response_loss: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    return await _handle_quick_setup_import(
        request=request,
        file=file,
        confirm_replace=confirm_replace,
        acknowledge_response_loss=acknowledge_response_loss,
        review_session=review_session,
        user=user,
        db=db,
        kind="reviewees",
        existing_count_fn=csv_imports.existing_reviewee_count,
        parse_fn=csv_imports.parse_reviewee_csv,
        save_fn=csv_imports.save_reviewees,
    )


async def _handle_quick_setup_import(
    *,
    request: Request,
    file: UploadFile,
    confirm_replace: str | None,
    acknowledge_response_loss: str | None,
    review_session: ReviewSession,
    user: User,
    db: Session,
    kind: str,
    existing_count_fn,
    parse_fn,
    save_fn,
) -> RedirectResponse:
    """Quick Setup card slot handler — thin wrapper over the same
    parse / save pipeline the per-entity Setup pages use.

    On success: 303 → Session Home with no flag; the slot's count
    indicator on the next render is the success signal (per the
    "no flash banner" direction in segment_11J).

    On parse / validation failure, missing-confirm, or lifecycle
    rejection: 303 → Session Home with ``?quick_setup_error={kind}``
    and a ``quick_setup_reason`` token that drives the slot's
    inline ``banner-error`` copy.
    """

    home_url = f"/operator/sessions/{review_session.id}"
    fragment = f"#quick-setup-{kind}"
    error_reason = await _run_quick_setup_import(
        file=file,
        confirm_replace=confirm_replace,
        acknowledge_response_loss=acknowledge_response_loss,
        review_session=review_session,
        user=user,
        db=db,
        kind=kind,
        existing_count_fn=existing_count_fn,
        parse_fn=parse_fn,
        save_fn=save_fn,
    )
    if error_reason is not None:
        return RedirectResponse(
            url=(
                f"{home_url}?quick_setup_error={kind}"
                f"&quick_setup_reason={error_reason}{fragment}"
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(
        url=f"{home_url}{fragment}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/sessions/{session_id}/quick-setup/relationships",
    response_class=HTMLResponse,
    response_model=None,
)
async def quick_setup_relationships_submit(
    file: UploadFile = File(...),
    confirm_replace: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Quick Setup card slot 3 (Relationships) handler. Mirrors the
    Reviewers / Reviewees per-slot routes but resolves the parser's
    ``reviewers=`` / ``reviewees=`` kwargs against the session's
    rosters before calling
    ``relationships_service.parse_relationship_csv``."""

    home_url = f"/operator/sessions/{review_session.id}"
    fragment = "#quick-setup-relationships"
    error_reason = await _run_quick_setup_relationships(
        file=file,
        confirm_replace=confirm_replace,
        review_session=review_session,
        user=user,
        db=db,
    )
    if error_reason is not None:
        return RedirectResponse(
            url=(
                f"{home_url}?quick_setup_error=relationships"
                f"&quick_setup_reason={error_reason}{fragment}"
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(
        url=f"{home_url}{fragment}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


async def _run_quick_setup_relationships(
    *,
    file: UploadFile,
    confirm_replace: str | None,
    review_session: ReviewSession,
    user: User,
    db: Session,
) -> str | None:
    """Reusable Relationships-slot pipeline shared by the per-slot
    route and the consolidated ``submit-all`` handler. Returns the
    ``quick_setup_reason`` token on failure, ``None`` on success."""

    if not lifecycle.is_editable(review_session):
        return "lifecycle"

    content = await file.read()
    reviewers = assignments.list_reviewers(db, review_session.id)
    reviewees = assignments.list_reviewees(db, review_session.id)
    result = relationships_service.parse_relationship_csv(
        content, reviewers=reviewers, reviewees=reviewees
    )
    if result.is_blocked or any(
        issue.severity == "error" for issue in result.issues
    ):
        return "parse"

    existing = relationships_service.existing_count(db, review_session.id)
    if existing > 0 and confirm_replace != "true":
        return "needs_confirm"

    relationships_service.save_relationships(
        db,
        session=review_session,
        user=user,
        rows=result.rows,
        filename=file.filename or "",
        correlation_id=request_correlation_id(),
    )
    return None


async def _run_quick_setup_import(
    *,
    file: UploadFile,
    confirm_replace: str | None,
    acknowledge_response_loss: str | None,
    review_session: ReviewSession,
    user: User,
    db: Session,
    kind: str,
    existing_count_fn,
    parse_fn,
    save_fn,
) -> str | None:
    """Reusable parse / save pipeline shared by the per-slot routes
    and the consolidated ``submit-all`` handler. Returns the
    ``quick_setup_reason`` token on failure, ``None`` on success."""

    if not lifecycle.is_editable(review_session):
        return "lifecycle"

    content = await file.read()
    result = parse_fn(content)
    if not result.is_blocked:
        result.issues.extend(
            csv_imports.check_cross_table_identity(
                db,
                session_id=review_session.id,
                rows=result.rows,
                kind=kind,
            )
        )

    if result.is_blocked or any(
        issue.severity == "error" for issue in result.issues
    ):
        return "parse"

    existing = existing_count_fn(db, review_session.id)
    if existing > 0 and confirm_replace != "true":
        return "needs_confirm"

    if existing > 0:
        try:
            _require_response_loss_ack(
                db, review_session, acknowledge_response_loss
            )
        except HTTPException:
            return "needs_confirm"

    save_fn(
        db,
        session=review_session,
        user=user,
        rows=result.rows,
        filename=file.filename or "",
        correlation_id=request_correlation_id(),
    )
    return None


@router.post(
    "/sessions/{session_id}/quick-setup/submit-all",
    response_class=HTMLResponse,
    response_model=None,
)
async def quick_setup_submit_all(
    request: Request,
    reviewers_file: UploadFile | None = File(default=None),
    reviewees_file: UploadFile | None = File(default=None),
    relationships_file: UploadFile | None = File(default=None),
    settings_file: UploadFile | None = File(default=None),
    confirm_replace: str | None = Form(default=None),
    acknowledge_response_loss: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Consolidated Quick Setup submit handler.

    Replaces the per-slot Submit buttons (one per slot) with a
    single bottom Submit on the card. For each slot whose file is
    attached, dispatches to the same internal pipeline the per-slot
    route uses (kept alive as backend-only entry points).

    Post-15D PR 7a the Assignments slot retired entirely;
    generation is no longer driven from Quick Setup. PR 7c
    re-introduces a Relationships slot in the same chain.

    Per the locked decision, the Submit button itself is gated
    client-side on file presence; this server-side handler is the
    source of truth and skips empty slots silently.

    On the first slot's failure the operator is redirected back to
    Home with that slot's ``?quick_setup_error=...&quick_setup_reason=...``
    flag; later slots in the dispatch order don't run on a failure
    upstream. Success 303s to Home with no flag and the slot
    fragment of the last slot that ran (or the card root when
    nothing did).
    """

    home_url = f"/operator/sessions/{review_session.id}"

    def error_redirect(kind: str, reason: str) -> RedirectResponse:
        return RedirectResponse(
            url=(
                f"{home_url}?quick_setup_error={kind}"
                f"&quick_setup_reason={reason}#quick-setup-{kind}"
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    last_fragment = ""

    if reviewers_file is not None and reviewers_file.filename:
        reason = await _run_quick_setup_import(
            file=reviewers_file,
            confirm_replace=confirm_replace,
            acknowledge_response_loss=acknowledge_response_loss,
            review_session=review_session,
            user=user,
            db=db,
            kind="reviewers",
            existing_count_fn=csv_imports.existing_reviewer_count,
            parse_fn=csv_imports.parse_reviewer_csv,
            save_fn=csv_imports.save_reviewers,
        )
        if reason is not None:
            return error_redirect("reviewers", reason)
        last_fragment = "#quick-setup-reviewers"

    if reviewees_file is not None and reviewees_file.filename:
        reason = await _run_quick_setup_import(
            file=reviewees_file,
            confirm_replace=confirm_replace,
            acknowledge_response_loss=acknowledge_response_loss,
            review_session=review_session,
            user=user,
            db=db,
            kind="reviewees",
            existing_count_fn=csv_imports.existing_reviewee_count,
            parse_fn=csv_imports.parse_reviewee_csv,
            save_fn=csv_imports.save_reviewees,
        )
        if reason is not None:
            return error_redirect("reviewees", reason)
        last_fragment = "#quick-setup-reviewees"

    if relationships_file is not None and relationships_file.filename:
        reason = await _run_quick_setup_relationships(
            file=relationships_file,
            confirm_replace=confirm_replace,
            review_session=review_session,
            user=user,
            db=db,
        )
        if reason is not None:
            return error_redirect("relationships", reason)
        last_fragment = "#quick-setup-relationships"

    if settings_file is not None and settings_file.filename:
        reason = await _run_quick_setup_settings(
            file=settings_file,
            review_session=review_session,
            user=user,
            db=db,
        )
        if reason is not None:
            return error_redirect("settings", reason)
        last_fragment = "#quick-setup-settings"

    return RedirectResponse(
        url=f"{home_url}{last_fragment}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


# --------------------------------------------------------------------------- #
# Segment 12A-3 PR 3 + PR 4 — Settings importer route + Quick Setup slot
# --------------------------------------------------------------------------- #


@router.post(
    "/sessions/{session_id}/import-config",
    response_class=HTMLResponse,
    response_model=None,
)
async def import_session_config(
    file: UploadFile = File(...),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Apply a Settings CSV to ``review_session``.

    Lifecycle gate: ``status in {"draft", "validated"}``;
    importing into a session with reviewer responses is blocked
    via the gate (responses only exist in ``ready``).

    Reachable from Quick Setup slot 4 (PR 4) and as a direct
    POST endpoint — same success / error redirect shape the
    other Quick Setup slots use: ``?config_imported=ok`` flash
    on success, ``?quick_setup_error=settings&quick_setup_reason=...``
    on failure (lifecycle / parse / apply)."""

    home_url = f"/operator/sessions/{review_session.id}"
    fragment = "#quick-setup-settings"

    reason = await _run_quick_setup_settings(
        file=file,
        review_session=review_session,
        user=user,
        db=db,
    )
    if reason is not None:
        return RedirectResponse(
            url=(
                f"{home_url}?quick_setup_error=settings"
                f"&quick_setup_reason={reason}{fragment}"
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return RedirectResponse(
        url=f"{home_url}?config_imported=ok{fragment}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


async def _run_quick_setup_settings(
    *,
    file: UploadFile,
    review_session: ReviewSession,
    user: User,
    db: Session,
) -> str | None:
    """Reusable Settings-slot pipeline shared by the per-slot
    route, the submit-all handler, and the create-session
    handler. Returns the ``quick_setup_reason`` token on
    failure, ``None`` on success."""

    if not lifecycle.is_editable(review_session):
        return "lifecycle"

    content = await file.read()
    if not content:
        return "parse"

    rows, parse_error = _read_settings_csv(content)
    if parse_error is not None:
        return "parse"

    result = session_config_io.apply_session_config(
        db,
        review_session,
        rows,
        user=user,
        correlation_id=request_correlation_id(),
    )
    if not result.ok:
        return "parse"
    return None


def _read_settings_csv(
    content: bytes,
) -> tuple[list[session_config_io.Row], str | None]:
    """Parse the 3-column ``field,value,data_type`` CSV bytes
    into a list of ``Row`` records.

    Returns ``(rows, error_token)`` — ``error_token`` is ``None``
    on success, a token like ``"decode"`` / ``"header"`` /
    ``"shape"`` on failure. The route maps every error token to
    ``quick_setup_reason=parse``; the granularity is here only
    for future log surfacing."""

    import csv as _csv
    import io as _io

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return [], "decode"

    reader = _csv.reader(_io.StringIO(text))
    iterator = iter(reader)
    try:
        header = next(iterator)
    except StopIteration:
        return [], "header"
    if [c.strip() for c in header] != list(session_config_io.HEADER):
        return [], "header"

    rows: list[session_config_io.Row] = []
    for raw in iterator:
        if not raw:
            continue
        if len(raw) < 3:
            return [], "shape"
        rows.append(
            session_config_io.Row(
                field=raw[0],
                value=raw[1],
                data_type=raw[2],
            )
        )
    return rows, None
