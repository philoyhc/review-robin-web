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

from dataclasses import dataclass, field
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
    csv_imports,
    date_formatting,
    operator_settings,
    relationships as relationships_service,
    scheduled_events,
    session_config_io,
    session_owners,
    session_tags,
    sessions,
)
from app.services import unit_of_work
from app.services import session_lifecycle as lifecycle
from app.web import views
from app.web.deps import (
    get_or_create_user,
    request_correlation_id,
    require_session_operator,
)
from app.web.routes_operator._shared import (
    _require_response_loss_ack,
    session_payload_error,
)


router = APIRouter()


@router.post("/sessions", response_model=None)
async def create_session(
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
    timezone_name = (
        operator_settings.parse_display_timezone_input(display_timezone)
        or operator_settings.get_display_timezone(user)
    )
    if not operator_settings.is_valid_timezone(timezone_name):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"unknown timezone {timezone_name!r}",
        )

    parsed_deadline: datetime | None = None
    if deadline:
        try:
            parsed_deadline = date_formatting.parse_local_datetime(
                deadline, timezone_name
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="deadline must be ISO-8601",
            ) from exc

    # 18G Part 1: optional Start anchor for scheduled activation.
    try:
        parsed_scheduled_activate_at = (
            scheduled_events.parse_and_validate_scheduled_activate_at(
                scheduled_activate_at, timezone_name=timezone_name
            )
        )
    except scheduled_events.ScheduledActivateError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    # 18G Part 2: optional auto-send invite offsets. Per-entry rules
    # validate against the (possibly freshly-set) Start anchor.
    try:
        parsed_invite_offsets = (
            scheduled_events.parse_and_validate_invite_offsets(
                invite_offsets,
                scheduled_activate_at=parsed_scheduled_activate_at,
            )
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
        parsed_reminder_offsets = (
            scheduled_events.parse_and_validate_reminder_offsets(
                reminder_offsets,
                deadline=parsed_deadline,
            )
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
        parsed_responses_release_at = (
            scheduled_events.parse_and_validate_responses_release_at(
                responses_release_at, timezone_name=timezone_name
            )
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

    # Cross-field datetime ordering: Start ≤ End ≤ Release-from.
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
            responses_release_at=parsed_responses_release_at,
            responses_release_until=parsed_responses_release_until,
        )
    except ValidationError as exc:
        raise session_payload_error(exc) from exc
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
    home_url = f"/operator/sessions/{review_session.id}"
    # 18R Item 4 Slice 5 — the Edit page is retired; a bare create lands on
    # Session Home with the Session details card open in edit mode so the
    # operator can continue filling in details in place.
    edit_url = f"{home_url}?editing=1#session-config"

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
        session was created, so this cannot fail on an email. Runs on
        every path the Tags box does — a failed upload keeps what the
        operator staged, as it keeps what they typed.
        """
        if not owner_targets:
            return
        session_owners.set_owners(
            db,
            review_session=review_session,
            actor=user,
            targets=[user, *owner_targets],
            correlation_id=correlation_id,
        )

    def quick_setup_error_redirect(
        kind: str, reason: str, details: list[str] | None = None
    ) -> RedirectResponse:
        # The typed tags are written here too, so a failed upload does
        # not silently discard something the operator typed on this
        # page. Safe on every slot: a refused upload saved nothing, the
        # Settings file included, so this is still "after the settings
        # CSV" in the only sense that matters.
        write_typed_tags()
        write_staged_owners()
        query = _quick_setup_error_query(kind, reason, details or ())
        return RedirectResponse(
            url=f"{home_url}?{query}#quick-setup-{kind}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    # Nothing to replace on a new session, so the replacement tick is
    # satisfied trivially and Settings skips its gate (``replacing``).
    uploads = _attached(
        reviewers=reviewers_file,
        reviewees=reviewees_file,
        relationships=relationships_file,
        observers=observers_file,
        settings=settings_file,
    )
    refusal = await _run_quick_setup(
        uploads=uploads,
        review_session=review_session,
        user=user,
        db=db,
        confirm_replace="true",
        acknowledge_response_loss=None,
        replacing=False,
        correlation_id=correlation_id,
    )
    if refusal is not None:
        return quick_setup_error_redirect(
            refusal.kind, refusal.failure.reason, refusal.failure.details
        )
    last_fragment = f"#quick-setup-{list(uploads)[-1]}" if uploads else ""

    write_typed_tags()
    write_staged_owners()

    # Quick Setup uploads anchor at their fragment on Session Home;
    # a bare create (no uploads) opens the Session details card in edit
    # mode (``edit_url``) so the operator continues setting up details.
    target_url = f"{home_url}{last_fragment}" if last_fragment else edit_url
    return RedirectResponse(
        url=target_url,
        status_code=status.HTTP_303_SEE_OTHER,
    )


# --------------------------------------------------------------------------- #
# Segment 11J PR A — Quick Setup card live wiring
# --------------------------------------------------------------------------- #
#
# Every Quick Setup upload — a per-slot route, the card's submit-all, and
# the Create page's staged files — runs through ``_run_quick_setup``: it
# checks every attached file, then saves them all in one unit
# (``guide/quick_setup_update.md`` Item 1). On success the route 303s
# back to Session Home with no flag (the slot's count indicator is the
# success signal); on a refusal it 303s with
# ``?quick_setup_error={kind}&quick_setup_reason=...`` so the GET render
# places a ``.banner.banner-error`` above the slot that refused.

#: The dispatch order (`spec/quick_setup_card_spec.md` "Per-slot
#: dispatch"): the order files are checked in, the order a refusal is
#: attributed in, and the order they are saved in.
SLOT_ORDER = ("reviewers", "reviewees", "relationships", "observers", "settings")

_ROSTER_PARSERS = {
    "reviewers": csv_imports.parse_reviewer_csv,
    "reviewees": csv_imports.parse_reviewee_csv,
    "observers": csv_imports.parse_observer_csv,
}


@dataclass(frozen=True)
class _SlotFailure:
    """Why a slot refused an upload: the ``quick_setup_reason`` token,
    plus the lines its banner lists when the file failed validation —
    a Settings CSV's errors (findings D31), a roster file's kinds of
    problem (``views.roster_problem_details``) — and none for every
    other reason."""

    reason: str
    details: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _SlotRefusal:
    """A refused Quick Setup upload: the slot the banner names, and why."""

    kind: str
    failure: _SlotFailure


@dataclass(frozen=True)
class _StagedSlot:
    """A file that passed every check, held until the save. A roster
    carries its parsed rows and header labels; Relationships carries its
    bytes, because its rows need the ids the roster saves assign; and
    Settings carries its parsed rows."""

    kind: str
    filename: str
    rows: list = field(default_factory=list)
    field_labels: dict | None = None
    content: bytes = b""


class _UnitRefused(Exception):
    """A refusal found inside the save unit, which rolls everything back."""

    def __init__(self, refusal: _SlotRefusal) -> None:
        super().__init__(refusal.kind)
        self.refusal = refusal


def _attached(**files: UploadFile | None) -> dict[str, UploadFile]:
    """The slots with a file chosen, in dispatch order. A browser posts
    an untouched file input as an empty-named part, so a blank filename
    counts as no file (the slots are skipped silently)."""
    return {
        kind: files[kind]
        for kind in SLOT_ORDER
        if files.get(kind) is not None and files[kind].filename
    }


async def _run_quick_setup(
    *,
    uploads: dict[str, UploadFile],
    review_session: ReviewSession,
    user: User,
    db: Session,
    confirm_replace: str | None,
    acknowledge_response_loss: str | None,
    replacing: bool,
    correlation_id: str | None = None,
) -> _SlotRefusal | None:
    """Check every attached file, then save every one in one unit.

    The one save site behind every Quick Setup upload route — which is
    why a fix here reaches all of them (`spec/quick_setup_card_spec.md`
    "Per-slot dispatch"). Files uploaded together are checked against
    each other and against the existing rosters they do not replace
    (author's rule, 2026-10-12); one refused file leaves the session as
    it was. ``replacing`` is ``False`` only on Create, whose Settings
    slot has nothing to replace.

    The saves run in the threadpool: they wait on the session row lock,
    and waiting on the event loop would stall the worker whose other
    requests hold that lock until their teardown runs on the same loop
    (findings Bc3)."""

    if not uploads:
        return None
    first = next(iter(uploads))
    if not lifecycle.is_editable(review_session):
        return _SlotRefusal(first, _SlotFailure("lifecycle"))

    contents = {kind: await upload.read() for kind, upload in uploads.items()}
    filenames = {kind: upload.filename or "" for kind, upload in uploads.items()}
    staged = _check_uploads(
        db,
        review_session=review_session,
        contents=contents,
        filenames=filenames,
        confirm_replace=confirm_replace,
        acknowledge_response_loss=acknowledge_response_loss,
        replacing=replacing,
    )
    if isinstance(staged, _SlotRefusal):
        return staged
    try:
        await run_in_threadpool(
            _save_uploads,
            db,
            review_session=review_session,
            user=user,
            staged=staged,
            correlation_id=correlation_id or request_correlation_id(),
        )
    except _UnitRefused as exc:
        return exc.refusal
    return None


def _replace_gate(
    db: Session,
    review_session: ReviewSession,
    *,
    kind: str,
    confirm_replace: str | None,
    acknowledge_response_loss: str | None,
    replacing: bool,
) -> _SlotFailure | None:
    """The replacement tick and, where a slot's replace discards
    answers, the response-loss acknowledgement (`spec/lifecycle.md`
    §3.2). A roster asks only when it holds rows; Settings asks on any
    existing session, since it rebuilds every instrument (findings C3).
    Relationships and Observers check the tick only."""

    if kind == "settings":
        if not replacing:
            return None
        existing = 1
    elif kind == "relationships":
        existing = relationships_service.existing_count(db, review_session.id)
    else:
        existing = {
            "reviewers": csv_imports.existing_reviewer_count,
            "reviewees": csv_imports.existing_reviewee_count,
            "observers": csv_imports.existing_observer_count,
        }[kind](db, review_session.id)
    if existing == 0:
        return None
    if confirm_replace != "true":
        return _SlotFailure("needs_confirm")
    if kind in {"reviewers", "reviewees", "settings"}:
        try:
            _require_response_loss_ack(
                db, review_session, acknowledge_response_loss
            )
        except HTTPException:
            return _SlotFailure("needs_confirm")
    return None


def _check_uploads(
    db: Session,
    *,
    review_session: ReviewSession,
    contents: dict[str, bytes],
    filenames: dict[str, str],
    confirm_replace: str | None,
    acknowledge_response_loss: str | None,
    replacing: bool,
) -> list[_StagedSlot] | _SlotRefusal:
    """Every gate but the lock, for every attached file, before anything
    is written. Slot by slot in dispatch order: the file's own checks,
    then its replacement gates, so the first slot that refuses is the
    one reported — what the slot-by-slot dispatch reported before."""

    parsed = {
        kind: _ROSTER_PARSERS[kind](contents[kind])
        for kind in contents
        if kind in _ROSTER_PARSERS
    }
    # Each roster file against the other uploads and the rosters they
    # do not replace — a blocked file has no rows to hold a name.
    identity = csv_imports.check_incoming_identity(
        db,
        session_id=review_session.id,
        incoming={
            kind: result.rows
            for kind, result in parsed.items()
            if not result.is_blocked
        },
    )

    staged: list[_StagedSlot] = []
    for kind in contents:
        if kind in parsed:
            result = parsed[kind]
            issues = [*result.issues, *identity.get(kind, [])]
            if result.is_blocked or any(
                issue.severity == "error" for issue in issues
            ):
                return _SlotRefusal(
                    kind,
                    _SlotFailure("parse", views.roster_problem_details(issues)),
                )
            item = _StagedSlot(
                kind,
                filenames[kind],
                rows=result.rows,
                # Observers carry no friendly labels (19C Item 1).
                field_labels=(
                    None if kind == "observers" else result.field_labels
                ),
            )
        elif kind == "relationships":
            reviewers = parsed.get("reviewers")
            reviewees = parsed.get("reviewees")
            roster_reviewers, roster_reviewees = (
                relationships_service.rosters_for_relationships(
                    db,
                    review_session.id,
                    incoming_reviewers=reviewers.rows if reviewers else None,
                    incoming_reviewees=reviewees.rows if reviewees else None,
                )
            )
            result = relationships_service.parse_relationship_csv(
                contents[kind],
                reviewers=roster_reviewers,
                reviewees=roster_reviewees,
                reviewers_uploaded=reviewers is not None,
                reviewees_uploaded=reviewees is not None,
            )
            if result.is_blocked or any(
                issue.severity == "error" for issue in result.issues
            ):
                return _SlotRefusal(
                    kind,
                    _SlotFailure(
                        "parse", views.roster_problem_details(result.issues)
                    ),
                )
            item = _StagedSlot(kind, filenames[kind], content=contents[kind])
        else:  # settings
            if not contents[kind]:
                return _SlotRefusal(kind, _SlotFailure("parse"))
            rows, row_errors, parse_error = _read_settings_csv(contents[kind])
            if parse_error is not None:
                return _SlotRefusal(kind, _SlotFailure("parse"))
            if row_errors:
                # A short row refuses the file, reported with every
                # other error the file holds (findings D10).
                errors = session_config_io.validate_session_config(
                    review_session, rows, row_errors=row_errors
                )
                return _SlotRefusal(
                    kind,
                    _SlotFailure("parse", views.settings_error_details(errors)),
                )
            item = _StagedSlot(kind, filenames[kind], rows=rows)

        gate = _replace_gate(
            db,
            review_session,
            kind=kind,
            confirm_replace=confirm_replace,
            acknowledge_response_loss=acknowledge_response_loss,
            replacing=replacing,
        )
        if gate is not None:
            return _SlotRefusal(kind, gate)
        staged.append(item)
    return staged


def _save_uploads(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    staged: list[_StagedSlot],
    correlation_id: str,
) -> None:
    """Save every checked file in one ``unit_of_work.atomic``: the
    per-entity savers nest inside it, so nothing commits until the last
    slot has saved, and any refusal rolls every slot back.

    Each roster saver locks the session and re-reads it (findings Bc4),
    so an activation committed since the checks refuses here, with the
    ``lifecycle`` reason on the slot that met it. The friendly labels
    ride every roster save (``field_labels_captured``); omitting them
    once dropped them silently, and the roster header is the only way
    back since 19C Item 1 retired them from the settings bundle."""

    current = staged[0].kind
    try:
        with unit_of_work.atomic(db):
            for item in staged:
                current = item.kind
                _save_slot(
                    db,
                    item,
                    review_session=review_session,
                    user=user,
                    correlation_id=correlation_id,
                )
    except lifecycle.SessionStateConflict as exc:
        raise _UnitRefused(
            _SlotRefusal(current, _SlotFailure("lifecycle"))
        ) from exc


def _save_slot(
    db: Session,
    item: _StagedSlot,
    *,
    review_session: ReviewSession,
    user: User,
    correlation_id: str,
) -> None:
    common = {
        "session": review_session,
        "user": user,
        "filename": item.filename,
        "correlation_id": correlation_id,
    }
    if item.kind == "reviewers":
        csv_imports.save_reviewers(
            db, rows=item.rows, field_labels_captured=item.field_labels, **common
        )
    elif item.kind == "reviewees":
        csv_imports.save_reviewees(
            db, rows=item.rows, field_labels_captured=item.field_labels, **common
        )
    elif item.kind == "observers":
        csv_imports.save_observers(db, rows=item.rows, **common)
    elif item.kind == "relationships":
        # Parsed again against the rosters as they now stand inside the
        # unit, for their real ids. The check already parsed it against
        # the same rows, so a refusal here is a defect, not an operator's
        # problem: it raises, and the unit rolls back.
        reviewers, reviewees = relationships_service.rosters_for_relationships(
            db, review_session.id
        )
        result = relationships_service.parse_relationship_csv(
            item.content, reviewers=reviewers, reviewees=reviewees
        )
        if result.is_blocked or any(
            issue.severity == "error" for issue in result.issues
        ):
            raise RuntimeError(
                "Quick Setup: the Relationships file passed its check but "
                "not its save-time parse"
            )
        relationships_service.save_relationships(
            db,
            rows=result.rows,
            field_labels_captured=result.field_labels,
            **common,
        )
    else:  # settings
        lifecycle.require_editable(db, review_session)
        result = session_config_io.apply_session_config(
            db,
            review_session,
            item.rows,
            user=user,
            correlation_id=correlation_id,
        )
        if not result.ok:
            raise _UnitRefused(
                _SlotRefusal(
                    "settings",
                    _SlotFailure(
                        "parse", views.settings_error_details(result.errors)
                    ),
                )
            )


def _slot_redirect(
    review_session: ReviewSession, kind: str, refusal: _SlotRefusal | None
) -> RedirectResponse:
    """Back to the slot on Session Home, with the refusal's flag if any."""

    home_url = f"/operator/sessions/{review_session.id}"
    if refusal is None:
        url = f"{home_url}#quick-setup-{kind}"
    else:
        query = _quick_setup_error_query(
            refusal.kind, refusal.failure.reason, refusal.failure.details
        )
        url = f"{home_url}?{query}#quick-setup-{refusal.kind}"
    return RedirectResponse(url=url, status_code=status.HTTP_303_SEE_OTHER)


async def _single_slot(
    kind: str,
    file: UploadFile,
    *,
    review_session: ReviewSession,
    user: User,
    db: Session,
    confirm_replace: str | None,
    acknowledge_response_loss: str | None = None,
) -> RedirectResponse:
    """A per-slot route: the shared pipeline with one file."""

    refusal = await _run_quick_setup(
        uploads={kind: file},
        review_session=review_session,
        user=user,
        db=db,
        confirm_replace=confirm_replace,
        acknowledge_response_loss=acknowledge_response_loss,
        replacing=True,
    )
    return _slot_redirect(review_session, kind, refusal)


@router.post(
    "/sessions/{session_id}/quick-setup/reviewers",
    response_class=HTMLResponse,
    response_model=None,
)
async def quick_setup_reviewers_submit(
    file: UploadFile = File(...),
    confirm_replace: str | None = Form(default=None),
    acknowledge_response_loss: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    return await _single_slot(
        "reviewers",
        file,
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
    file: UploadFile = File(...),
    confirm_replace: str | None = Form(default=None),
    acknowledge_response_loss: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    return await _single_slot(
        "reviewees",
        file,
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
    file: UploadFile = File(...),
    confirm_replace: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Quick Setup card slot 3 (Relationships). Checked against the
    session's current rosters, since no roster file rides with it."""

    return await _single_slot(
        "relationships",
        file,
        review_session=review_session,
        user=user,
        db=db,
        confirm_replace=confirm_replace,
    )


@router.post(
    "/sessions/{session_id}/quick-setup/observers",
    response_class=HTMLResponse,
    response_model=None,
)
async def quick_setup_observers_submit(
    file: UploadFile = File(...),
    confirm_replace: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Quick Setup card Observers slot. No response-loss acknowledgement:
    observer rows cascade nothing. The cross-roster identity check has
    applied since 19Q Item 7 — one person may hold two roles, never two
    names (author's ruling, 2026-09-19)."""

    return await _single_slot(
        "observers",
        file,
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
    confirm_replace: str | None = Form(default=None),
    acknowledge_response_loss: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """The card's single bottom Submit.

    The Submit button is gated client-side on file presence; this
    handler is the source of truth and skips empty slots silently. Every
    attached file is checked first, then all are saved in one unit
    (``_run_quick_setup``): a refusal names its slot and leaves every
    slot unsaved. Success 303s to Home at the last slot's fragment, or
    the card root when nothing was attached."""

    uploads = _attached(
        reviewers=reviewers_file,
        reviewees=reviewees_file,
        relationships=relationships_file,
        observers=observers_file,
        settings=settings_file,
    )
    refusal = await _run_quick_setup(
        uploads=uploads,
        review_session=review_session,
        user=user,
        db=db,
        confirm_replace=confirm_replace,
        acknowledge_response_loss=acknowledge_response_loss,
        replacing=True,
    )
    if refusal is not None or uploads:
        return _slot_redirect(
            review_session, list(uploads)[-1] if uploads else "", refusal
        )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}",
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
    confirm_replace: str | None = Form(default=None),
    acknowledge_response_loss: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Apply a Settings CSV to ``review_session``.

    Lifecycle gate: ``status in {"draft", "validated"}``. A settings
    re-import rebuilds the instrument structure, so it discards any
    submitted reviewer responses the session carried over from a
    prior activation cycle — ``apply_session_config`` clears them
    explicitly so the rebuild does not trip the ``responses`` foreign
    key. It therefore needs ``confirm_replace=true``, and
    ``acknowledge_response_loss=true`` when responses exist (findings
    C3).

    Reachable from the Quick Setup Settings slot and as a direct POST
    endpoint, with the redirect shape the other slots use."""

    return await _single_slot(
        "settings",
        file,
        review_session=review_session,
        user=user,
        db=db,
        confirm_replace=confirm_replace,
        acknowledge_response_loss=acknowledge_response_loss,
    )


def _quick_setup_error_query(
    kind: str, reason: str, details: list[str] | tuple[str, ...] = ()
) -> str:
    """The ``?quick_setup_error=…`` query a failed slot redirects with;
    each detail line rides as a ``quick_setup_detail`` value."""

    pairs = [("quick_setup_error", kind), ("quick_setup_reason", reason)]
    pairs += [("quick_setup_detail", line) for line in details]
    return urlencode(pairs)


def _read_settings_csv(
    content: bytes,
) -> tuple[
    list[session_config_io.Row], list[session_config_io.ApplyError], str | None
]:
    """Parse the 3-column ``field,value,data_type`` CSV bytes
    into a list of ``Row`` records.

    Returns ``(rows, row_errors, error_token)``. ``error_token`` is
    ``None`` unless the file cannot be read at all — ``"decode"`` /
    ``"header"`` / ``"unreadable"`` — which the route maps to
    ``quick_setup_reason=parse`` with no detail; the granularity is
    here only for future log surfacing. A short row is not that: it
    comes back in ``row_errors`` (``session_config_io.split_rows``),
    reported by row number with the file's other errors (findings
    D10)."""

    import csv as _csv
    import io as _io

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return [], [], "decode"

    reader = _csv.reader(_io.StringIO(text))
    iterator = iter(reader)
    # A cell past the csv module's field limit raises from either read;
    # it is a malformed file like the others, not a 500 (findings Dc8).
    try:
        header = next(iterator)
    except StopIteration:
        return [], [], "header"
    except _csv.Error:
        return [], [], "unreadable"
    if [c.strip() for c in header] != list(session_config_io.HEADER):
        return [], [], "header"

    try:
        rows, row_errors = session_config_io.split_rows(iterator)
    except _csv.Error:
        return [], [], "unreadable"
    return rows, row_errors, None
