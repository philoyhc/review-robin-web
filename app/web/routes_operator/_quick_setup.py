"""Quick Setup card on Session Home — per-slot
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
from urllib.parse import urlencode

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
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, User
from app.db.session import get_db
from app.schemas.sessions import SessionCreate
from app.services import (
    date_formatting,
    linked_apps,
    operator_settings,
    scheduled_events,
    session_owners,
    session_tags,
    sessions,
)
from app.web import quick_setup_pipeline as pipeline
from app.web import urls, views
from app.web.deps import (
    OperatorAllowlistDenied,
    get_or_create_user,
    request_correlation_id,
    require_session_operator,
)
from app.web.roster_import import (
    release_hold,
)
from app.web.routes_operator._shared import (
    directory_or_none,
    render_session_home,
    session_payload_error,
)

router = APIRouter()


@router.post("/sessions", response_model=None)
async def create_session(
    request: Request,
    name: str = Form(...),
    code: str = Form(...),
    description: str | None = Form(default=None),
    deadline: str | None = Form(default=None),
    scheduled_activate_at: str | None = Form(default=None),
    invite_offsets: str | None = Form(default=None),
    reminder_offsets: str | None = Form(default=None),
    display_timezone: str = Form(default=""),
    help_contact: str | None = Form(default=None),
    relationships_enabled: bool = Form(default=False),
    observers_enabled: bool = Form(default=False),
    symmetric_review: bool = Form(default=False),
    responses_release_at: str | None = Form(default=None),
    responses_release_until: str | None = Form(default=None),
    tags: str | None = Form(default=None),
    owners: list[str] = Form(default=[]),
    reviewers_file: UploadFile | None = File(default=None),
    reviewees_file: UploadFile | None = File(default=None),
    relationships_file: UploadFile | None = File(default=None),
    observers_file: UploadFile | None = File(default=None),
    settings_file: UploadFile | None = File(default=None),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    # 18B PR 4: the Create form carries the per-session display
    # timezone. Blank ⇒ fall back to the operator's default. The
    # deadline picker is wall-clock in this zone.
    timezone_name = operator_settings.parse_display_timezone_input(
        display_timezone
    ) or operator_settings.get_display_timezone(user)
    if not operator_settings.is_valid_timezone(timezone_name):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"unknown timezone {timezone_name!r}",
        )

    parsed_deadline: datetime | None = None
    if deadline:
        try:
            parsed_deadline = date_formatting.parse_local_datetime(deadline, timezone_name)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="deadline must be ISO-8601",
            ) from exc

    # 18G Part 1: optional Start anchor for scheduled activation.
    try:
        parsed_scheduled_activate_at = scheduled_events.parse_and_validate_scheduled_activate_at(
            scheduled_activate_at, timezone_name=timezone_name
        )
    except scheduled_events.ScheduledActivateError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    # 18G Part 2: optional auto-send invite offsets. Per-entry rules
    # validate against the (possibly freshly-set) Start anchor.
    try:
        parsed_invite_offsets = scheduled_events.parse_and_validate_invite_offsets(
            invite_offsets,
            scheduled_activate_at=parsed_scheduled_activate_at,
        )
    except scheduled_events.ScheduledActivateError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    # 18G Part 3: optional auto-send reminder offsets, anchored on
    # ``deadline``. Per-entry rules validate against the (possibly
    # freshly-set) deadline.
    try:
        parsed_reminder_offsets = scheduled_events.parse_and_validate_reminder_offsets(
            reminder_offsets,
            deadline=parsed_deadline,
        )
    except scheduled_events.ScheduledActivateError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    # Participant-model W14 + S12 — Release-responses anchor +
    # close datetime. Until is validated against the (possibly
    # freshly-set) anchor.
    try:
        parsed_responses_release_at = scheduled_events.parse_and_validate_responses_release_at(
            responses_release_at, timezone_name=timezone_name
        )
        parsed_responses_release_until = (
            scheduled_events.parse_and_validate_responses_release_until(
                responses_release_until,
                timezone_name=timezone_name,
                responses_release_at=parsed_responses_release_at,
            )
        )
    except scheduled_events.ScheduledActivateError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    # Cross-field datetime ordering: Start < End ≤ Release-from.
    # Runs after every individual parse so the operator gets the
    # field-level error before the ordering error.
    try:
        scheduled_events.validate_schedule_ordering(
            scheduled_activate_at=parsed_scheduled_activate_at,
            deadline=parsed_deadline,
            responses_release_at=parsed_responses_release_at,
        )
    except scheduled_events.ScheduledActivateError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    # 19S Item 9 Part A — the Owners card's staged rows, validated before
    # the session exists: one email that is not a workspace operator
    # refuses the create with nothing written, as every other field on
    # this form does. Applied after the session is created, below.
    try:
        owner_targets = session_owners.resolve_owners(db, owners)
    except session_owners.OwnerOperationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.message,
        ) from exc

    # A taken code is a form error like the others, not the unique
    # constraint's IntegrityError (which answered 500).
    try:
        sessions.ensure_code_available(db, code)
    except sessions.SessionCodeTakenError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    # One correlation id for the whole create, so every audit event it
    # produces — the session, each Quick Setup slot, tags, owners — groups
    # as one request. ``request_correlation_id`` mints a fresh id per call
    # (19S Item 9 rung 4; Session Home's save got the same fix in rung 2).
    correlation_id = request_correlation_id()

    try:
        payload = SessionCreate(
            name=name,
            code=code,
            description=description or None,
            deadline=parsed_deadline,
            display_timezone=timezone_name,
            help_contact=help_contact or None,
            scheduled_activate_at=parsed_scheduled_activate_at,
            invite_offsets=parsed_invite_offsets,
            reminder_offsets=parsed_reminder_offsets,
            relationships_enabled=relationships_enabled,
            observers_enabled=observers_enabled,
            symmetric_review=symmetric_review,
            responses_release_at=parsed_responses_release_at,
            responses_release_until=parsed_responses_release_until,
        )
    except ValidationError as exc:
        raise session_payload_error(exc) from exc
    # The creator becomes the first owner. The router's allowlist gate
    # read their flag unlocked, so it is re-read under the owner-add
    # lock, held until ``create_session`` commits: a revoke committed
    # since bounces as the gate would have.
    # The lock waits off the event loop, as Quick Setup's session lock
    # does (findings S4; S3).
    if not await run_in_threadpool(session_owners.lock_owner_eligible, db, user):
        raise OperatorAllowlistDenied()
    review_session = sessions.create_session(
        db,
        user=user,
        payload=payload,
        correlation_id=correlation_id,
    )

    # If the operator staged any Quick Setup uploads on the new-session
    # page, they run through the same pipeline as the card on Session
    # Home: every file checked, then all saved in one unit. The session
    # row is already committed and stays either way. On a refusal,
    # nothing uploaded is saved and the operator lands on Home with the
    # slot's error flag (the Quick Setup card and its error markers live
    # on Home, not the Edit page).
    home_url = f"/operator/sessions/{review_session.public_id}"
    # 18R Item 4 Slice 5 — the Edit page is retired; a bare create lands on
    # Session Home with the Session details card open in edit mode so the
    # operator can continue filling in details in place. No fragment: the
    # address ends at the session, as Save's does (19X Item 7).
    edit_url = f"{home_url}?editing=1"

    def write_typed_tags() -> None:
        """Apply the Create page's Tags box, if the operator typed one.

        **Called after the settings-CSV block on every path**, which is
        the whole mechanism: the form wins over a settings CSV's
        ``session_tags[]`` rows by running last, not by changing
        ``_apply_session_tags`` — that applier is wipe-and-replace and
        is shared with ``POST /sessions/{id}/import-config`` on an
        existing session, so narrowing it there to serve Create would
        be the wrong seam (19S Item 6, `Semantics`).

        An empty box writes **nothing** rather than an empty tag set.
        The distinction matters because ``set_tags`` is a replace: it
        would drop whatever a settings CSV had just applied, which is
        the opposite of leaving the CSV unopposed. So the caller's
        emptiness guard is load-bearing, and no ``session.tag_added``
        event is emitted for a create with no typed tag.
        """
        if not (tags and tags.strip()):
            return
        session_tags.set_tags(
            db,
            review_session=review_session,
            user=user,
            tags=tags.split(","),
            correlation_id=correlation_id,
        )

    def write_staged_owners() -> None:
        """Apply the Owners card's staged rows (19S Item 9 Part A).

        The creator is always in the set, so they can never be staged
        out: a session keeps its first owner. Validated before the
        session was created, so it refuses one only if they changed since:
        revoked, demoted or deleted (``add_owner`` re-reads them under the
        owner-add lock), or already added by someone else.
        ``skip_refused`` leaves that one out and adds the rest, rather
        than answering 500 on a session already made. Runs on every path
        the Tags box does — a failed upload keeps what the operator
        staged, as it keeps what they typed.
        """
        if not owner_targets:
            return
        session_owners.set_owners(
            db,
            review_session=review_session,
            actor=user,
            targets=[user, *owner_targets],
            correlation_id=correlation_id,
            skip_refused=True,
        )

    async def quick_setup_error_redirect(kind: str) -> RedirectResponse:
        # The typed tags are written here too, so a failed upload does
        # not silently discard something the operator typed on this
        # page. Safe on every slot: a refused upload saved nothing, the
        # Settings file included, so this is still "after the settings
        # CSV" in the only sense that matters.
        write_typed_tags()
        await run_in_threadpool(write_staged_owners)
        # A redirect, not a re-render: the session is committed, and
        # rendering Home at this POST's URL would replay the create on a
        # refresh. So the file's lines are not carried, only the fixed
        # ``refused`` code; uploading the file again in Quick Setup shows
        # them (findings O7).
        # No slot fragment (19X Item 7): Home's banner script scrolls
        # to the shown banner on load.
        query = _quick_setup_error_query(kind, "refused")
        return urls.redirect(
            request,
            url=f"{home_url}?{query}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    # Nothing to replace on a new session, so the replacement tick is
    # satisfied trivially and Settings skips its gate (``replacing``).
    uploads = pipeline.attached(
        reviewers=reviewers_file,
        reviewees=reviewees_file,
        relationships=relationships_file,
        observers=observers_file,
        settings=settings_file,
    )
    refusal = await pipeline.run(
        uploads=uploads,
        review_session=review_session,
        user=user,
        db=db,
        confirm_replace="true",
        acknowledge_response_loss=None,
        replacing=False,
        correlation_id=correlation_id,
        directory=directory_or_none(request),
    )
    if refusal is not None:
        return await quick_setup_error_redirect(refusal.kind)

    write_typed_tags()
    # ``add_owner`` takes the owner-add lock per staged owner (findings S4).
    await run_in_threadpool(write_staged_owners)

    # Staged files that all applied land at the top of Session Home, the
    # new session as a whole, rather than at the last slot that ran
    # (author, 19X Item 5); a refusal above lands on its slot's banner.
    # A bare create (no uploads) opens the Session details card in edit
    # mode (``edit_url``) so the operator continues setting up details.
    target_url = home_url if uploads else edit_url
    return urls.redirect(
        request,
        url=target_url,
        status_code=status.HTTP_303_SEE_OTHER,
    )


def _slot_response(
    request: Request,
    db: Session,
    *,
    user: User,
    review_session: ReviewSession,
    kind: str,
    refusal: pipeline.SlotRefusal | None,
    held: dict[str, str] | None = None,
    held_token: str | None = None,
    notice: str | None = None,
) -> HTMLResponse | RedirectResponse:
    """Back to the slot on Session Home on success, with ``notice`` as
    its ``quick_setup_notice`` code when there is one; on a refusal, Session
    Home rendered again at 422 with the slot's banner and the file's own
    lines, which a URL therefore never carries (findings O7). ``held``
    names the files an ask held, by slot, under ``held_token``
    (segment 19W)."""

    if refusal is None:
        query = f"?quick_setup_notice={notice}" if notice else ""
        return urls.redirect(
            request,
            url=f"/operator/sessions/{review_session.public_id}{query}#quick-setup-{kind}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return render_session_home(
        request,
        db,
        user=user,
        review_session=review_session,
        quick_setup=views.build_quick_setup_context(
            db,
            review_session,
            user=user,
            error_kind=refusal.kind,
            error_reason=refusal.failure.reason,
            error_details=tuple(refusal.failure.details),
            error_count=refusal.failure.count,
            held=held,
            held_token=held_token,
        ),
        http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
    )


async def _single_slot(
    kind: str,
    file: UploadFile,
    *,
    request: Request,
    review_session: ReviewSession,
    user: User,
    db: Session,
    confirm_replace: str | None,
    acknowledge_response_loss: str | None = None,
    acknowledge_instrument_deletion: str | None = None,
) -> HTMLResponse | RedirectResponse:
    """A per-slot route: the shared pipeline with one file."""

    refusal = await pipeline.run(
        uploads={kind: file},
        review_session=review_session,
        user=user,
        db=db,
        confirm_replace=confirm_replace,
        acknowledge_response_loss=acknowledge_response_loss,
        replacing=True,
        acknowledge_instrument_deletion=acknowledge_instrument_deletion,
        directory=directory_or_none(request),
    )
    return _slot_response(
        request,
        db,
        user=user,
        review_session=review_session,
        kind=kind,
        refusal=refusal,
    )


def _quick_setup_session(
    review_session: ReviewSession = Depends(require_session_operator),
) -> ReviewSession:
    """The session for a Quick Setup upload, refused when its linked
    application takes Quick Setup (segment 23F): the card is hidden there,
    and its rosters and set-up come from the application."""
    if linked_apps.locks(review_session, linked_apps.Lock.QUICK_SETUP):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=linked_apps.off_message(review_session, "Quick Setup"),
        )
    return review_session


def _settings_import_session(
    review_session: ReviewSession = Depends(require_session_operator),
) -> ReviewSession:
    """The session for a Settings import, refused when its linked
    application takes the import (segment 23F): the import rebuilds every
    instrument, which is the application's set-up."""
    if linked_apps.locks(review_session, linked_apps.Lock.SETTINGS_IMPORT):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=linked_apps.off_message(review_session, "The Settings import"),
        )
    return review_session


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
    review_session: ReviewSession = Depends(_quick_setup_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    return await _single_slot(
        "reviewers",
        file,
        request=request,
        review_session=review_session,
        user=user,
        db=db,
        confirm_replace=confirm_replace,
        acknowledge_response_loss=acknowledge_response_loss,
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
    review_session: ReviewSession = Depends(_quick_setup_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    return await _single_slot(
        "reviewees",
        file,
        request=request,
        review_session=review_session,
        user=user,
        db=db,
        confirm_replace=confirm_replace,
        acknowledge_response_loss=acknowledge_response_loss,
    )


@router.post(
    "/sessions/{session_id}/quick-setup/relationships",
    response_class=HTMLResponse,
    response_model=None,
)
async def quick_setup_relationships_submit(
    request: Request,
    file: UploadFile = File(...),
    confirm_replace: str | None = Form(default=None),
    acknowledge_response_loss: str | None = Form(default=None),
    review_session: ReviewSession = Depends(_quick_setup_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    """Quick Setup card slot 3 (Relationships). Checked against the
    session's current rosters, since no roster file rides with it.
    ``acknowledge_response_loss`` is the count of group answers it may
    clear (findings S1)."""

    return await _single_slot(
        "relationships",
        file,
        request=request,
        review_session=review_session,
        user=user,
        db=db,
        confirm_replace=confirm_replace,
        acknowledge_response_loss=acknowledge_response_loss,
    )


@router.post(
    "/sessions/{session_id}/quick-setup/observers",
    response_class=HTMLResponse,
    response_model=None,
)
async def quick_setup_observers_submit(
    request: Request,
    file: UploadFile = File(...),
    confirm_replace: str | None = Form(default=None),
    review_session: ReviewSession = Depends(_quick_setup_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    """Quick Setup card Observers slot. No response-loss acknowledgement:
    observer rows cascade nothing. The cross-roster identity check has
    applied since 19Q Item 7 — one person may hold two roles, never two
    names (author's ruling, 2026-09-19)."""

    return await _single_slot(
        "observers",
        file,
        request=request,
        review_session=review_session,
        user=user,
        db=db,
        confirm_replace=confirm_replace,
    )


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
    observers_file: UploadFile | None = File(default=None),
    settings_file: UploadFile | None = File(default=None),
    held_token: str | None = Form(default=None),
    confirm_replace: str | None = Form(default=None),
    acknowledge_response_loss: str | None = Form(default=None),
    acknowledge_instrument_deletion: str | None = Form(default=None),
    review_session: ReviewSession = Depends(_quick_setup_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    """The card's single bottom Submit.

    The Submit button is gated client-side on file presence; this
    handler is the source of truth and skips empty slots silently. Every
    attached file is checked first, then all are saved in one unit
    (``pipeline.run``): a refusal names its slot and leaves every
    slot unsaved, answered by Session Home rendered again at 422 with
    the slot's banner (findings O7). Success 303s to Home at the last
    slot's fragment, or the card root when nothing was attached.

    Segment 19W: a refusal that asks a question (``needs_confirm``,
    ``deletes_instruments``) holds every file of the submit under one
    token, so the next Submit answers it with nothing chosen again; a
    slot left empty then takes its held file, and a newly chosen one
    wins. A save or any other refusal ends the hold."""

    uploads = pipeline.attached(
        reviewers=reviewers_file,
        reviewees=reviewees_file,
        relationships=relationships_file,
        observers=observers_file,
        settings=settings_file,
    )
    chosen = {kind: await upload.read() for kind, upload in uploads.items()}
    merged = pipeline.merge_held(
        db,
        chosen=chosen,
        chosen_names={k: u.filename or "" for k, u in uploads.items()},
        held_token=held_token,
        user=user,
        review_session=review_session,
    )
    if merged.lost:
        # The hold the page named has lapsed: save nothing, rather than
        # the newly chosen files alone, and say so (segment 19W).
        return render_session_home(
            request,
            db,
            user=user,
            review_session=review_session,
            quick_setup=views.build_quick_setup_context(
                db, review_session, user=user, held_lost=True
            ),
            http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    contents, filenames = merged.contents, merged.filenames
    refusal = await pipeline.run_contents(
        contents=contents,
        filenames=filenames,
        review_session=review_session,
        user=user,
        db=db,
        confirm_replace=confirm_replace,
        acknowledge_response_loss=acknowledge_response_loss,
        replacing=True,
        acknowledge_instrument_deletion=acknowledge_instrument_deletion,
        directory=directory_or_none(request),
    )
    held_names, token = pipeline.settle_hold(
        db,
        refusal=refusal,
        merged=merged,
        user=user,
        review_session=review_session,
    )
    if refusal is not None or contents:
        return _slot_response(
            request,
            db,
            user=user,
            review_session=review_session,
            kind=list(contents)[-1] if contents else "",
            refusal=refusal,
            held=held_names,
            held_token=token,
            notice=(
                "kept_reviewees"
                if refusal is None and views.quick_setup_kept_reviewees(review_session, contents)
                else None
            ),
        )
    return urls.redirect(
        request,
        url=f"/operator/sessions/{review_session.public_id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/{session_id}/quick-setup/dismiss")
def quick_setup_dismiss(
    request: Request,
    held_token: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """A Quick Setup banner's Dismiss while its ask holds the submit's
    files: end the hold and land on the card (segment 19W)."""
    release_hold(db, token=held_token, user=user, review_session=review_session)
    return urls.redirect(
        request,
        url=f"/operator/sessions/{review_session.public_id}#quick-setup",
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
    request: Request,
    file: UploadFile = File(...),
    confirm_replace: str | None = Form(default=None),
    acknowledge_response_loss: str | None = Form(default=None),
    acknowledge_instrument_deletion: str | None = Form(default=None),
    review_session: ReviewSession = Depends(_settings_import_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    """Apply a Settings CSV to ``review_session``.

    Lifecycle gate: ``status in {"draft", "validated"}``. A settings
    re-import rebuilds the instrument structure, so it discards any
    submitted reviewer responses the session carried over from a
    prior activation cycle — ``apply_session_config`` clears them
    explicitly so the rebuild does not trip the ``responses`` foreign
    key. It therefore needs ``confirm_replace=true``, and
    ``acknowledge_response_loss=true`` when responses exist (findings
    C3). A file that would delete instruments it does not name is
    refused naming them until ``acknowledge_instrument_deletion``
    carries their count (findings S4).

    Reachable from the Quick Setup Settings slot and as a direct POST
    endpoint, answering as the other slots do."""

    return await _single_slot(
        "settings",
        file,
        request=request,
        review_session=review_session,
        user=user,
        db=db,
        confirm_replace=confirm_replace,
        acknowledge_response_loss=acknowledge_response_loss,
        acknowledge_instrument_deletion=acknowledge_instrument_deletion,
    )


def _quick_setup_error_query(kind: str, reason: str) -> str:
    """The ``?quick_setup_error=…&quick_setup_reason=…`` codes the Create
    page's refusal redirects with: the slot and a fixed reason, never the
    file's text (findings O7)."""

    return urlencode([("quick_setup_error", kind), ("quick_setup_reason", reason)])
