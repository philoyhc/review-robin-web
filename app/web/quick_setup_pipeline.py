"""The pipeline every Quick Setup upload runs through (segment 23I): it
checks every attached file, then saves them all in one unit. Quick
Setup's routes, New session's ``create_session`` and the handoff create
and re-send call it.

Outside the operator routes package, as ``app/web/roster_import.py`` is,
so slices can share it without importing one another (``CLAUDE.md``,
"Architecture at a glance"). It imports ``_shared`` inside the functions
that use it, never at the top: a top-level import would be a cycle
through the package's ``__init__``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import TypedDict, cast

from fastapi import (
    HTTPException,
    UploadFile,
)
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, User
from app.schemas.imports import (
    ObserverImportRow,
    RevieweeImportRow,
    ReviewerImportRow,
)
from app.services import (
    csv_imports,
    held_uploads,
    linked_apps,
    session_config_io,
    session_guard,
    sessions,
    unit_of_work,
)
from app.services import (
    relationships as relationships_service,
)
from app.services import (
    responses as responses_service,
)
from app.services import session_lifecycle as lifecycle
from app.web import views
from app.web.deps import (
    request_correlation_id,
)
from app.web.roster_import import (
    release_hold,
)
from cordware.graph import Directory

# --------------------------------------------------------------------------- #
# Segment 11J PR A — Quick Setup card live wiring
# --------------------------------------------------------------------------- #
#
# Every Quick Setup upload — a per-slot route, the card's submit-all, and
# the Create page's staged files — runs through ``run``: it
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


@dataclass(frozen=True)
class SlotFailure:
    """Why a slot refused an upload: the ``quick_setup_reason`` token,
    plus the lines its banner lists when the file failed validation —
    a Settings CSV's errors (findings D31), a roster file's kinds of
    problem (``views.roster_problem_details``), the instruments a
    Settings file would delete — and none for every other reason.
    ``count`` is how many instruments that is, the value the re-offered
    tick carries (findings S4), or how many saved group answers a
    Relationships file would clear (findings S1)."""

    reason: str
    details: list[str] = field(default_factory=list[str])
    count: int = 0


@dataclass(frozen=True)
class SlotRefusal:
    """A refused Quick Setup upload: the slot the banner names, and why."""

    kind: str
    failure: SlotFailure


#: The slots a directory check runs on (segment 21F).
_ROSTER_KINDS = ("reviewers", "reviewees", "observers")


#: A staged slot's parsed rows, by ``kind``: a roster's import rows, or
#: a Settings file's rows (Relationships stages its bytes instead).
type _StagedRows = (
    list[ReviewerImportRow]
    | list[RevieweeImportRow]
    | list[ObserverImportRow]
    | list[session_config_io.Row]
)


@dataclass(frozen=True)
class _StagedSlot:
    """A file that passed every check, held until the save. A roster
    carries its parsed rows and header labels; Relationships carries its
    bytes, because its rows need the ids the roster saves assign; and
    Settings carries its parsed rows."""

    kind: str
    filename: str
    rows: _StagedRows = field(default_factory=list[session_config_io.Row])
    field_labels: dict[tuple[str, str], str] | None = None
    content: bytes = b""
    #: A roster's directory check (segment 21F), run before the save unit.
    directory: csv_imports.DirectoryCheck | None = None


class _UnitRefused(Exception):
    """A refusal found inside the save unit, which rolls everything back."""

    def __init__(self, refusal: SlotRefusal) -> None:
        super().__init__(refusal.kind)
        self.refusal = refusal


#: The refusals a tick answers, which hold the submit's files (segment
#: 19W): the replace tick (or the response-loss ack it stands for), and
#: the Settings file's deletion count (findings S4).
_ASKS = frozenset({"needs_confirm", "deletes_instruments", views.DIRECTORY_SIGN_IN})


@dataclass(frozen=True)
class Merged:
    """A submit's files in slot order: the ones chosen now, and for each
    slot left empty the one a refused submit held (segment 19W).
    ``token`` is the hold in play; ``lost`` says the page named a hold
    that has lapsed or is not this operator's and session's."""

    contents: dict[str, bytes]
    filenames: dict[str, str]
    token: str | None
    lost: bool = False


def merge_held(
    db: Session,
    *,
    chosen: dict[str, bytes],
    chosen_names: dict[str, str],
    held_token: str | None,
    user: User,
    review_session: ReviewSession,
) -> Merged:
    token = (held_token or "").strip() or None
    held = (
        held_uploads.take(db, token=token, user=user, session_id=review_session.id) if token else {}
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
    return Merged(
        contents=contents,
        filenames=filenames,
        token=token if held else None,
        lost=token is not None and not held,
    )


def settle_hold(
    db: Session,
    *,
    refusal: SlotRefusal | None,
    merged: Merged,
    user: User,
    review_session: ReviewSession,
) -> tuple[dict[str, str] | None, str | None]:
    """After the submit: on an ask, hold every file of it and return what
    the hold now holds, by slot, with its token; otherwise end any hold
    in play. The names come from the hold itself, so a file it skipped
    (over the cap) is neither named nor sent again."""
    if refusal is None or refusal.failure.reason not in _ASKS:
        release_hold(db, token=merged.token, user=user, review_session=review_session)
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
    held = held_uploads.take(db, token=token, user=user, session_id=review_session.id)
    if not held:
        return None, None
    return {kind: f.filename for kind, f in held.items()}, token


def attached(**files: UploadFile | None) -> dict[str, UploadFile]:
    """The slots with a file chosen, in dispatch order. A browser posts
    an untouched file input as an empty-named part, so a blank filename
    counts as no file (the slots are skipped silently)."""
    return {
        kind: upload
        for kind in SLOT_ORDER
        if (upload := files.get(kind)) is not None and upload.filename
    }


async def run(
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
    directory: Directory | None = None,
) -> SlotRefusal | None:
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

    The checks and the saves run in the threadpool: they wait on the
    session row lock (the checks only for a Settings file's short-row
    report, findings S3), and waiting on the event loop would stall the
    worker whose other requests hold that lock until their teardown runs
    on the same loop (findings Bc3)."""

    contents = {kind: await upload.read() for kind, upload in uploads.items()}
    filenames = {kind: upload.filename or "" for kind, upload in uploads.items()}
    return await run_contents(
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
        directory=directory,
    )


async def run_contents(
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
    directory: Directory | None = None,
    unit_guard: Callable[[], None] | None = None,
    unit_record: Callable[[], None] | None = None,
) -> SlotRefusal | None:
    """:func:`run` on bytes already read, in slot order:
    the submit-all route feeds it files a refused submit held (segment
    19W) beside the ones chosen now. ``unit_guard`` and ``unit_record``
    run inside the save unit (:func:`_save_uploads`)."""
    from app.web.routes_operator._shared import acknowledged_loss, roster_address

    if not contents:
        # Nothing to save, but a caller's checks and record still run under
        # the session lock: a linked re-send carrying only its settings,
        # before its rosters (segment 23J), applies them in ``unit_record``.
        if unit_guard is not None or unit_record is not None:
            with unit_of_work.atomic(db):
                session_guard.lock_session(db, review_session)
                if unit_guard is not None:
                    unit_guard()
                if unit_record is not None:
                    unit_record()
        return None
    first = next(iter(contents))
    if not lifecycle.is_editable(review_session):
        return SlotRefusal(first, SlotFailure("lifecycle"))
    # Segment 20B — under symmetric review the reviewees mirror the
    # reviewers, so a Reviewees file is refused when the mode will be on
    # once this submit's Settings file (if any) applies.
    settings_symmetric = (
        session_config_io.settings_symmetric_review(contents["settings"])
        if "settings" in contents
        else None
    )
    symmetric = sessions.symmetric_review_after_settings(db, review_session, settings_symmetric)
    if "reviewees" in contents and symmetric:
        return SlotRefusal("reviewees", SlotFailure("symmetric_reviewees"))
    # Segment 23E — observers are off on a linked session: a roster for
    # them is refused, so an upload cannot turn them on.
    if "observers" in contents and linked_apps.locks(review_session, linked_apps.Lock.OBSERVERS):
        return SlotRefusal("observers", SlotFailure("observers_off"))

    # In the threadpool too: a Settings file with a short row is
    # validated under the session lock (findings S3).
    staged = await run_in_threadpool(
        _check_uploads,
        db,
        review_session=review_session,
        contents=contents,
        filenames=filenames,
        confirm_replace=confirm_replace,
        acknowledge_response_loss=acknowledge_response_loss,
        replacing=replacing,
        symmetric=symmetric,
    )
    if isinstance(staged, SlotRefusal):
        return staged
    # Segment 21F: each roster's addresses resolved through the directory
    # on the operator's token, as the Setup pages' import does: after
    # the checks, so a refused file is not looked up, and before the
    # save unit, so no lookup waits under the session lock.
    # One lookup for every roster in the submit, under one budget (Codex,
    # #3430).
    rosters = [i for i, item in enumerate(staged) if item.kind in _ROSTER_KINDS]
    checks = await run_in_threadpool(
        csv_imports.directory_checks,
        directory,
        [[roster_address(row) for row in staged[i].rows] for i in rosters],
    )
    # Segment 20G: a check the sign-in stopped saves nothing. The submit's
    # files are held (`_ASKS`) and the card asks to renew and submit again.
    for i, check in zip(rosters, checks, strict=True):
        if check.stopped:
            return SlotRefusal(staged[i].kind, SlotFailure(views.DIRECTORY_SIGN_IN))
    staged = list(staged)
    for i, check in zip(rosters, checks, strict=True):
        staged[i] = replace(staged[i], directory=check)
    try:
        await run_in_threadpool(
            _save_uploads,
            db,
            review_session=review_session,
            user=user,
            staged=staged,
            correlation_id=correlation_id or request_correlation_id(),
            symmetric_target=settings_symmetric,
            acknowledged_deletions=(
                acknowledged_loss(acknowledge_instrument_deletion) if replacing else None
            ),
            acknowledged_group_loss=acknowledged_loss(acknowledge_response_loss),
            unit_guard=unit_guard,
            unit_record=unit_record,
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
) -> SlotFailure | None:
    """The replacement tick and, where a slot's replace discards
    answers, the response-loss acknowledgement (`spec/lifecycle.md`
    §3.2). A roster asks only when it holds rows; Settings asks on any
    existing session, since it rebuilds every instrument (findings C3).
    Relationships and Observers check the tick only."""
    from app.web.routes_operator._shared import _require_response_loss_ack

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
        return SlotFailure("needs_confirm")
    if kind in {"reviewers", "reviewees", "settings"}:
        try:
            _require_response_loss_ack(db, review_session, acknowledge_response_loss)
        except HTTPException:
            return SlotFailure("needs_confirm")
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
    symmetric: bool = False,
) -> list[_StagedSlot] | SlotRefusal:
    """Every gate before the save, for every attached file, before
    anything is written. Not lock-free: a short-row Settings file's
    report takes the session lock, so the caller runs this off the event
    loop (findings S3). Slot by slot in dispatch order: the file's own checks,
    then its replacement gates, so the first slot that refuses is the
    one reported — what the slot-by-slot dispatch reported before."""
    from app.web.routes_operator._shared import ROSTER_PARSERS

    parsed = {
        kind: ROSTER_PARSERS[kind](contents[kind]) for kind in contents if kind in ROSTER_PARSERS
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
            kind: [] if result.is_blocked else result.rows for kind, result in parsed.items()
        },
    )

    staged: list[_StagedSlot] = []
    for kind in contents:
        if kind in parsed:
            result = parsed[kind]
            issues = [*result.issues, *identity.get(kind, [])]
            if result.is_blocked or any(issue.severity == "error" for issue in issues):
                return SlotRefusal(
                    kind,
                    SlotFailure("parse", views.roster_problem_details(issues)),
                )
            item = _StagedSlot(
                kind,
                filenames[kind],
                rows=result.rows,
                # Observers carry no friendly labels (19C Item 1).
                field_labels=(None if kind == "observers" else result.field_labels),
            )
        elif kind == "relationships":
            # Each parser's result, by the slot it was parsed for.
            reviewers = cast(
                "csv_imports.ParseResult[ReviewerImportRow] | None",
                parsed.get("reviewers"),
            )
            reviewees = cast(
                "csv_imports.ParseResult[RevieweeImportRow] | None",
                parsed.get("reviewees"),
            )
            result = relationships_service.parse_relationship_upload(
                db,
                review_session.id,
                contents[kind],
                incoming_reviewers=reviewers.rows if reviewers else None,
                incoming_reviewees=reviewees.rows if reviewees else None,
                symmetric=symmetric,
            )
            if result.is_blocked or any(issue.severity == "error" for issue in result.issues):
                return SlotRefusal(
                    kind,
                    SlotFailure("parse", views.roster_problem_details(result.issues)),
                )
            item = _StagedSlot(kind, filenames[kind], content=contents[kind])
        else:  # settings
            if not contents[kind]:
                return SlotRefusal(kind, SlotFailure("parse"))
            rows, row_errors, parse_error = _read_settings_csv(contents[kind])
            if parse_error is not None:
                return SlotRefusal(kind, SlotFailure("parse"))
            if row_errors:
                # A short row refuses the file, reported with every
                # other error the file holds (findings D10).
                errors = session_config_io.validate_session_config(
                    review_session, rows, row_errors=row_errors
                )
                return SlotRefusal(
                    kind,
                    SlotFailure("parse", views.settings_error_details(errors)),
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
            return SlotRefusal(kind, gate)
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
    acknowledged_group_loss: int = 0,
    symmetric_target: bool | None = None,
    unit_guard: Callable[[], None] | None = None,
    unit_record: Callable[[], None] | None = None,
) -> None:
    """Save every checked file in one ``unit_of_work.atomic``: the
    per-entity savers nest inside it, so nothing commits until the last
    slot has saved, and any refusal rolls every slot back.

    ``unit_guard`` runs once the session lock is held, before any save,
    and refuses by raising; ``unit_record`` runs after the last save,
    and writes without committing. A handoff re-send rechecks its link
    under the lock and records its transfer in the same commit as the
    rosters (segment 23F, Codex on #3915).

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
            if unit_guard is not None:
                unit_guard()
            # Segment 20B — Settings save last (``SLOT_ORDER``), so a file
            # that sets symmetric review sets it here, first: turned on
            # beside empty rosters, this submit's reviewers mirror; turned
            # off, its Reviewees file saves. Under the lock, so the
            # empty-roster check and the flip are the unit's (Codex on
            # #3490); a refused unit rolls it back with the rest.
            if symmetric_target is not None:
                sessions.set_symmetric_review_for_import(
                    db,
                    review_session,
                    symmetric_target,
                    user=user,
                    correlation_id=correlation_id,
                )
            before = {
                field_name: getattr(review_session, field_name)
                for field_name in sessions.FEATURE_TOGGLE_FOR_ROSTER.values()
            }
            populated: list[str] = []
            # A Settings file in the same submit rebuilds every instrument,
            # which deletes every response after this slot's save, so
            # Relationships has nothing to ask about (the read of S1).
            group_ack = (
                None if any(item.kind == "settings" for item in staged) else acknowledged_group_loss
            )
            for item in staged:
                current = item.kind
                saved = _save_slot(
                    db,
                    item,
                    review_session=review_session,
                    user=user,
                    correlation_id=correlation_id,
                    acknowledged_deletions=acknowledged_deletions,
                    acknowledged_group_loss=group_ack,
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
            if unit_record is not None:
                unit_record()
    except lifecycle.SessionStateConflict as exc:
        # Segment 20B: a turn-on committed since the checks refuses a
        # Reviewees file under the lock (Codex on #3490).
        reason = "symmetric_reviewees" if exc.code == "symmetric_review" else "lifecycle"
        raise _UnitRefused(SlotRefusal(current, SlotFailure(reason))) from exc


class _SaveCommon(TypedDict):
    """The keyword arguments every slot's saver takes."""

    session: ReviewSession
    user: User
    filename: str
    correlation_id: str


def _save_slot(
    db: Session,
    item: _StagedSlot,
    *,
    review_session: ReviewSession,
    user: User,
    correlation_id: str,
    acknowledged_deletions: int | None = None,
    acknowledged_group_loss: int | None = 0,
) -> int:
    """Save one checked slot; returns how many roster rows it saved
    (0 for Settings).

    Relationships asks before clearing saved group answers, as its Setup
    card does (findings S1, author's ruling 2026-10-22): a file that
    would clear them is refused with the count unless
    ``acknowledged_group_loss`` is that count. The card is locked
    whenever answers exist, so only a stale tab or a direct POST meets
    the refusal, and only a direct POST can carry the count."""

    common: _SaveCommon = {
        "session": review_session,
        "user": user,
        "filename": item.filename,
        "correlation_id": correlation_id,
    }
    # ``item.rows`` holds the rows its ``kind`` was parsed into.
    if item.kind == "reviewers":
        csv_imports.save_reviewers(
            db,
            rows=cast("list[ReviewerImportRow]", item.rows),
            field_labels_captured=item.field_labels,
            directory=item.directory,
            **common,
        )
        return len(item.rows)
    elif item.kind == "reviewees":
        csv_imports.save_reviewees(
            db,
            rows=cast("list[RevieweeImportRow]", item.rows),
            field_labels_captured=item.field_labels,
            directory=item.directory,
            **common,
        )
        return len(item.rows)
    elif item.kind == "observers":
        csv_imports.save_observers(
            db,
            rows=cast("list[ObserverImportRow]", item.rows),
            directory=item.directory,
            **common,
        )
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
        if result.is_blocked or any(issue.severity == "error" for issue in result.issues):
            raise _UnitRefused(
                SlotRefusal(
                    "relationships",
                    SlotFailure("parse", views.roster_problem_details(result.issues)),
                )
            )
        try:
            relationships_service.save_relationships(
                db,
                rows=result.rows,
                field_labels_captured=result.field_labels,
                acknowledged_loss=acknowledged_group_loss,
                **common,
            )
        except responses_service.GroupAnswersWouldClear as exc:
            raise _UnitRefused(
                SlotRefusal(
                    "relationships",
                    SlotFailure("clears_group_answers", count=exc.count),
                )
            ) from exc
        return len(result.rows)
    else:  # settings
        lifecycle.require_editable(db, review_session)
        try:
            result = session_config_io.apply_session_config(
                db,
                review_session,
                cast("list[session_config_io.Row]", item.rows),
                user=user,
                correlation_id=correlation_id,
                acknowledged_deletions=acknowledged_deletions,
            )
        except session_config_io.InstrumentsWouldDelete as exc:
            # Refuse, then re-offer (findings S4): the banner names the
            # instruments, and its tick sends their count back.
            raise _UnitRefused(
                SlotRefusal(
                    "settings",
                    SlotFailure(
                        "deletes_instruments",
                        views.deleted_instrument_details(exc.labels),
                        count=exc.count,
                    ),
                )
            ) from exc
        if not result.ok:
            raise _UnitRefused(
                SlotRefusal(
                    "settings",
                    SlotFailure("parse", views.settings_error_details(result.errors)),
                )
            )
        return 0


def _read_settings_csv(
    content: bytes,
) -> tuple[list[session_config_io.Row], list[session_config_io.ApplyError], str | None]:
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
