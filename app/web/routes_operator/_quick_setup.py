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

from app.web import urls
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
from app.services import held_uploads, session_guard, unit_of_work
from app.services import session_lifecycle as lifecycle
from app.web import views
from app.web.deps import (
    OperatorAllowlistDenied,
    get_or_create_user,
    request_correlation_id,
    require_session_operator,
)
from app.web.routes_operator._shared import (
    _require_response_loss_ack,
    acknowledged_loss,
    release_hold,
    render_session_home,
    session_payload_error,
)


router = APIRouter()


@router.post("/sessions", response_model=None)
async def create_session(
    request: Request, name: str = Form(...),
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
    # The creator becomes the first owner. The router's allowlist gate
    # read their flag unlocked, so it is re-read under the owner-add
    # lock, held until ``create_session`` commits: a revoke committed
    # since bounces as the gate would have.
    if not session_owners.lock_owner_eligible(db, user):
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

    def quick_setup_error_redirect(kind: str) -> RedirectResponse:
        # The typed tags are written here too, so a failed upload does
        # not silently discard something the operator typed on this
        # page. Safe on every slot: a refused upload saved nothing, the
        # Settings file included, so this is still "after the settings
        # CSV" in the only sense that matters.
        write_typed_tags()
        write_staged_owners()
        # A redirect, not a re-render: the session is committed, and
        # rendering Home at this POST's URL would replay the create on a
        # refresh. So the file's lines are not carried, only the fixed
        # ``refused`` code; uploading the file again in Quick Setup shows
        # them (findings O7).
        # No slot fragment (19X Item 7): Home's banner script scrolls
        # to the shown banner on load.
        query = _quick_setup_error_query(kind, "refused")
        return urls.redirect(request,
            url=f"{home_url}?{query}",
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
        return quick_setup_error_redirect(refusal.kind)

    write_typed_tags()
    write_staged_owners()

    # Staged files that all applied land at the top of Session Home, the
    # new session as a whole, rather than at the last slot that ran
    # (author, 19X Item 5); a refusal above lands on its slot's banner.
    # A bare create (no uploads) opens the Session details card in edit
    # mode (``edit_url``) so the operator continues setting up details.
    target_url = home_url if uploads else edit_url
    return urls.redirect(request,
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
# success signal). On a refusal an existing session's route renders
# Session Home again at 422, with a ``.banner.banner-error`` above the
# slot that refused listing the file's own lines; the Create page, whose
# session is already committed, 303s with the fixed
# ``?quick_setup_error={kind}&quick_setup_reason=refused`` code instead
# (findings O7).

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
    problem (``views.roster_problem_details``), the instruments a
    Settings file would delete — and none for every other reason.
    ``count`` is how many instruments that is, the value the re-offered
    tick carries (findings S4)."""

    reason: str
    details: list[str] = field(default_factory=list)
    count: int = 0


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


#: The refusals a tick answers, which hold the submit's files (segment
#: 19W): the replace tick (or the response-loss ack it stands for), and
#: the Settings file's deletion count (findings S4).
_ASKS = frozenset({"needs_confirm", "deletes_instruments"})


@dataclass(frozen=True)
class _Merged:
    """A submit's files in slot order: the ones chosen now, and for each
    slot left empty the one a refused submit held (segment 19W).
    ``token`` is the hold in play; ``lost`` says the page named a hold
    that has lapsed or is not this operator's and session's."""

    contents: dict[str, bytes]
    filenames: dict[str, str]
    token: str | None
    lost: bool = False


def _merge_held(
    db: Session,
    *,
    chosen: dict[str, bytes],
    chosen_names: dict[str, str],
    held_token: str | None,
    user: User,
    review_session: ReviewSession,
) -> _Merged:
    token = (held_token or "").strip() or None
    held = (
        held_uploads.take(db, token=token, user=user, session_id=review_session.id)
        if token
        else {}
    )
    contents: dict[str, bytes] = {}
    filenames: dict[str, str] = {}
    for kind in SLOT_ORDER:
        if kind in chosen:
            contents[kind] = chosen[kind]
            filenames[kind] = chosen_names[kind]
        elif kind in held:
            contents[kind] = held[kind].content
            filenames[kind] = held[kind].filename
    return _Merged(
        contents=contents,
        filenames=filenames,
        token=token if held else None,
        lost=token is not None and not held,
    )


def _settle_hold(
    db: Session,
    *,
    refusal: _SlotRefusal | None,
    merged: _Merged,
    user: User,
    review_session: ReviewSession,
) -> tuple[dict[str, str] | None, str | None]:
    """After the submit: on an ask, hold every file of it and return what
    the hold now holds, by slot, with its token; otherwise end any hold
    in play. The names come from the hold itself, so a file it skipped
    (over the cap) is neither named nor sent again."""
    if refusal is None or refusal.failure.reason not in _ASKS:
        release_hold(
            db, token=merged.token, user=user, review_session=review_session
        )
        return None, None
    # Nothing of the refused unit rides with the hold's commit.
    db.rollback()
    token = held_uploads.hold(
        db,
        user=user,
        session_id=review_session.id,
        files={
            kind: held_uploads.HeldFile(
                filename=merged.filenames[kind] or "upload.csv", content=content
            )
            for kind, content in merged.contents.items()
        },
        token=merged.token,
    )
    db.commit()
    if token is None:
        return None, None
    held = held_uploads.take(
        db, token=token, user=user, session_id=review_session.id
    )
    if not held:
        return None, None
    return {kind: f.filename for kind, f in held.items()}, token


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
    acknowledge_instrument_deletion: str | None = None,
) -> _SlotRefusal | None:
    """Check every attached file, then save every one in one unit.

    The one save site behind every Quick Setup upload route — which is
    why a fix here reaches all of them (`spec/quick_setup_card_spec.md`
    "Per-slot dispatch"). Files uploaded together are checked against
    each other and against the existing rosters they do not replace
    (author's rule, 2026-10-12); one refused file leaves the session as
    it was. ``replacing`` is ``False`` only on Create, whose Settings
    slot has nothing to replace.

    ``acknowledge_instrument_deletion`` is the count the re-offered
    Settings tick carries: a Settings file that would delete instruments
    is refused naming them unless it matches (findings S4). Create does
    not ask, since a new session holds only its Default instrument.

    The saves run in the threadpool: they wait on the session row lock,
    and waiting on the event loop would stall the worker whose other
    requests hold that lock until their teardown runs on the same loop
    (findings Bc3)."""

    contents = {kind: await upload.read() for kind, upload in uploads.items()}
    filenames = {kind: upload.filename or "" for kind, upload in uploads.items()}
    return await _run_quick_setup_contents(
        contents=contents,
        filenames=filenames,
        review_session=review_session,
        user=user,
        db=db,
        confirm_replace=confirm_replace,
        acknowledge_response_loss=acknowledge_response_loss,
        replacing=replacing,
        correlation_id=correlation_id,
        acknowledge_instrument_deletion=acknowledge_instrument_deletion,
    )


async def _run_quick_setup_contents(
    *,
    contents: dict[str, bytes],
    filenames: dict[str, str],
    review_session: ReviewSession,
    user: User,
    db: Session,
    confirm_replace: str | None,
    acknowledge_response_loss: str | None,
    replacing: bool,
    correlation_id: str | None = None,
    acknowledge_instrument_deletion: str | None = None,
) -> _SlotRefusal | None:
    """:func:`_run_quick_setup` on bytes already read, in slot order:
    the submit-all route feeds it files a refused submit held (segment
    19W) beside the ones chosen now."""

    if not contents:
        return None
    first = next(iter(contents))
    if not lifecycle.is_editable(review_session):
        return _SlotRefusal(first, _SlotFailure("lifecycle"))

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
            acknowledged_deletions=(
                acknowledged_loss(acknowledge_instrument_deletion)
                if replacing
                else None
            ),
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
    # do not replace. A blocked file has no rows to hold a name, but its
    # roster is still being replaced, so it rides in empty: left out, its
    # old roster would hold names again and could refuse an earlier slot
    # for a clash the operator's upload already resolves.
    identity = csv_imports.check_incoming_identity(
        db,
        session_id=review_session.id,
        incoming={
            kind: [] if result.is_blocked else result.rows
            for kind, result in parsed.items()
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
    acknowledged_deletions: int | None = None,
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
            # The toggles as they stood before this submit, read under the
            # session lock (which re-reads the row), so a toggle another
            # request turned on since this one loaded the session is not
            # logged as flipped again (Codex on #3002).
            session_guard.lock_session(db, review_session)
            before = {
                field_name: getattr(review_session, field_name)
                for field_name in sessions.FEATURE_TOGGLE_FOR_ROSTER.values()
            }
            populated: list[str] = []
            for item in staged:
                current = item.kind
                saved = _save_slot(
                    db,
                    item,
                    review_session=review_session,
                    user=user,
                    correlation_id=correlation_id,
                    acknowledged_deletions=acknowledged_deletions,
                )
                if saved:
                    populated.append(item.kind)
            # After every slot, Settings included, so a settings file's
            # ``*_enabled=false`` cannot hide rows this submit just saved
            # (Item 2): an upload that populates a roster turns its tab on.
            if populated:
                sessions.turn_on_populated_features(
                    db,
                    review_session,
                    populated=populated,
                    before=before,
                    user=user,
                    reason="quick_setup_upload",
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
    acknowledged_deletions: int | None = None,
) -> int:
    """Save one checked slot; returns how many roster rows it saved
    (0 for Settings)."""
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
        return len(item.rows)
    elif item.kind == "reviewees":
        csv_imports.save_reviewees(
            db, rows=item.rows, field_labels_captured=item.field_labels, **common
        )
        return len(item.rows)
    elif item.kind == "observers":
        csv_imports.save_observers(db, rows=item.rows, **common)
        return len(item.rows)
    elif item.kind == "relationships":
        # Parsed again against the rosters as they now stand inside the
        # unit, for their real ids — under the session lock, so a roster
        # edit cannot slip in between. The check parsed it against the
        # same rows; should it refuse now anyway (a roster edited between
        # the check and this lock), that is reported as the file's
        # problem and the unit rolls back, rather than answering a 500.
        lifecycle.require_editable(db, review_session)
        reviewers, reviewees = relationships_service.rosters_for_relationships(
            db, review_session.id
        )
        result = relationships_service.parse_relationship_csv(
            item.content, reviewers=reviewers, reviewees=reviewees
        )
        if result.is_blocked or any(
            issue.severity == "error" for issue in result.issues
        ):
            raise _UnitRefused(
                _SlotRefusal(
                    "relationships",
                    _SlotFailure(
                        "parse", views.roster_problem_details(result.issues)
                    ),
                )
            )
        relationships_service.save_relationships(
            db,
            rows=result.rows,
            field_labels_captured=result.field_labels,
            **common,
        )
        return len(result.rows)
    else:  # settings
        lifecycle.require_editable(db, review_session)
        try:
            result = session_config_io.apply_session_config(
                db,
                review_session,
                item.rows,
                user=user,
                correlation_id=correlation_id,
                acknowledged_deletions=acknowledged_deletions,
            )
        except session_config_io.InstrumentsWouldDelete as exc:
            # Refuse, then re-offer (findings S4): the banner names the
            # instruments, and its tick sends their count back.
            raise _UnitRefused(
                _SlotRefusal(
                    "settings",
                    _SlotFailure(
                        "deletes_instruments",
                        views.deleted_instrument_details(exc.labels),
                        count=exc.count,
                    ),
                )
            ) from exc
        if not result.ok:
            raise _UnitRefused(
                _SlotRefusal(
                    "settings",
                    _SlotFailure(
                        "parse", views.settings_error_details(result.errors)
                    ),
                )
            )
        return 0


def _slot_response(
    request: Request,
    db: Session,
    *,
    user: User,
    review_session: ReviewSession,
    kind: str,
    refusal: _SlotRefusal | None,
    held: dict[str, str] | None = None,
    held_token: str | None = None,
) -> HTMLResponse | RedirectResponse:
    """Back to the slot on Session Home on success; on a refusal, Session
    Home rendered again at 422 with the slot's banner and the file's own
    lines, which a URL therefore never carries (findings O7). ``held``
    names the files an ask held, by slot, under ``held_token``
    (segment 19W)."""

    if refusal is None:
        return urls.redirect(request,
            url=f"/operator/sessions/{review_session.public_id}#quick-setup-{kind}",
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

    refusal = await _run_quick_setup(
        uploads={kind: file},
        review_session=review_session,
        user=user,
        db=db,
        confirm_replace=confirm_replace,
        acknowledge_response_loss=acknowledge_response_loss,
        replacing=True,
        acknowledge_instrument_deletion=acknowledge_instrument_deletion,
    )
    return _slot_response(
        request,
        db,
        user=user,
        review_session=review_session,
        kind=kind,
        refusal=refusal,
    )


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
    review_session: ReviewSession = Depends(require_session_operator),
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
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    """Quick Setup card slot 3 (Relationships). Checked against the
    session's current rosters, since no roster file rides with it."""

    return await _single_slot(
        "relationships",
        file,
        request=request,
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
    request: Request,
    file: UploadFile = File(...),
    confirm_replace: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
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
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    """The card's single bottom Submit.

    The Submit button is gated client-side on file presence; this
    handler is the source of truth and skips empty slots silently. Every
    attached file is checked first, then all are saved in one unit
    (``_run_quick_setup``): a refusal names its slot and leaves every
    slot unsaved, answered by Session Home rendered again at 422 with
    the slot's banner (findings O7). Success 303s to Home at the last
    slot's fragment, or the card root when nothing was attached.

    Segment 19W: a refusal that asks a question (``needs_confirm``,
    ``deletes_instruments``) holds every file of the submit under one
    token, so the next Submit answers it with nothing chosen again; a
    slot left empty then takes its held file, and a newly chosen one
    wins. A save or any other refusal ends the hold."""

    uploads = _attached(
        reviewers=reviewers_file,
        reviewees=reviewees_file,
        relationships=relationships_file,
        observers=observers_file,
        settings=settings_file,
    )
    chosen = {kind: await upload.read() for kind, upload in uploads.items()}
    merged = _merge_held(
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
    refusal = await _run_quick_setup_contents(
        contents=contents,
        filenames=filenames,
        review_session=review_session,
        user=user,
        db=db,
        confirm_replace=confirm_replace,
        acknowledge_response_loss=acknowledge_response_loss,
        replacing=True,
        acknowledge_instrument_deletion=acknowledge_instrument_deletion,
    )
    held_names, token = _settle_hold(
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
        )
    return urls.redirect(request,
        url=f"/operator/sessions/{review_session.public_id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/{session_id}/quick-setup/dismiss")
def quick_setup_dismiss(
    request: Request, held_token: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """A Quick Setup banner's Dismiss while its ask holds the submit's
    files: end the hold and land on the card (segment 19W)."""
    release_hold(db, token=held_token, user=user, review_session=review_session)
    return urls.redirect(request,
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
    review_session: ReviewSession = Depends(require_session_operator),
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
