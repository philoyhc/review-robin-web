"""Handoffs from another Cordware application (segment 23A).

The interop proof of concept's create: another application's operator
posts a bundle of roster CSVs, and Review Robin makes a draft session
from it with its own importers (`spec/handoffs.md`;
`cordware/docs/cordware_interoperability_consolidated_spec_v0.3.md`
§6.3). This module owns the bundle's shape and the replay lookup; the
route runs the create through Quick Setup's pipeline.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import cast

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    AuditEvent,
    Instrument,
    InstrumentResponseField,
    Response,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from app.services import audit, csv_imports, monitoring, permissions, unit_of_work
from app.services.date_formatting import iso_in_zone
from app.services.lifecycle_display import lifecycle_display_label
from app.services.sessions import resolve_session_timezone

PROTOCOL = "cordware.csv-handoff"
PROTOCOL_VERSION = 1
OPERATION = "reviewrobin.create_draft_session"
#: The whole request body, CSVs included.
MAX_BYTES = 1024 * 1024
#: Rosters only (interop spec §13.1): no Settings file.
REQUIRED_FILES = ("reviewers", "reviewees")
OPTIONAL_FILES = ("relationships", "observers")
#: The audit event written with the draft, before its rosters; its
#: ``context`` carries the transfer, which is how a replay is recognized.
EVENT = "session.handoff_created"
#: Written once the rosters have saved: the mark of a complete transfer,
#: independent of what the rosters hold later (an operator may clear one).
COMPLETED = "session.handoff_completed"
#: How long after its draft a transfer with no rosters yet counts as still
#: running: past the create's 120 s directory budget and the roster save,
#: with room to spare. Older, it was cut off.
IN_PROGRESS = timedelta(minutes=5)


class HandoffError(Exception):
    """A refused handoff: an error code from the interop spec's
    vocabulary (§7.3), an HTTP status, and lines for the sender to show;
    with the session it concerns, when there is one, and a finer reason."""

    def __init__(
        self,
        code: str,
        status: int,
        details: list[str] | None = None,
        *,
        review_session: ReviewSession | None = None,
        reason: str | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.status = status
        self.details = details or []
        self.review_session = review_session
        self.reason = reason


@dataclass(frozen=True)
class Bundle:
    transfer_id: str
    source_app: str
    name: str
    code: str
    #: CSV bytes by Quick Setup slot, in slot order.
    files: dict[str, bytes]


def _encoded(value: str, key: str) -> bytes:
    """UTF-8, or :class:`HandoffError`: JSON admits an escaped unpaired
    surrogate (``\\ud800``) that no UTF-8 text, and no database, holds, and
    an escaped NUL (``\\u0000``) that Postgres text columns refuse."""
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise HandoffError("invalid_package", 422, [f"`{key}` is not valid Unicode text."]) from exc
    if b"\x00" in encoded:
        raise HandoffError("invalid_package", 422, [f"`{key}` holds a NUL character."])
    return encoded


def _text(data: dict[str, object], key: str, limit: int) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise HandoffError(
            "invalid_package", 422, [f"`{key}` must be text of 1–{limit} characters"]
        )
    _encoded(value, key)
    return value.strip()


def parse_bundle(body: bytes) -> Bundle:
    """The bundle, or :class:`HandoffError`. Checks the envelope only:
    the CSVs are Quick Setup's to check, with its own parsers and caps."""
    try:
        raw: object = json.loads(body)
    except (ValueError, UnicodeDecodeError, RecursionError) as exc:
        # RecursionError: a body nested deeper than the parser's stack.
        raise HandoffError("invalid_package", 422, ["The body is not JSON."]) from exc
    if not isinstance(raw, dict):
        raise HandoffError("invalid_package", 422, ["The body is not a JSON object."])
    data = cast(dict[str, object], raw)
    if (
        data.get("protocol") != PROTOCOL
        or data.get("protocol_version") != PROTOCOL_VERSION
        or data.get("operation") != OPERATION
    ):
        raise HandoffError(
            "unsupported_version",
            422,
            [f"Expected `{PROTOCOL}` version {PROTOCOL_VERSION}, operation `{OPERATION}`."],
        )
    transfer_id = _text(data, "transfer_id", 64)
    try:
        uuid.UUID(transfer_id)
    except ValueError as exc:
        raise HandoffError("invalid_package", 422, ["`transfer_id` must be a UUID."]) from exc
    source_app = _text(data, "source_app", 64)
    suggestion = data.get("session_suggestion")
    if not isinstance(suggestion, dict):
        raise HandoffError("invalid_package", 422, ["`session_suggestion` must be an object."])
    suggestion = cast(dict[str, object], suggestion)
    name = _text(suggestion, "name", 255)
    code = _text(suggestion, "code", 64)
    files = data.get("files")
    if not isinstance(files, dict):
        raise HandoffError("invalid_package", 422, ["`files` must be an object."])
    files = cast(dict[str, object], files)
    allowed = set(REQUIRED_FILES) | set(OPTIONAL_FILES)
    unknown = sorted(set(files) - allowed)
    if unknown:
        raise HandoffError(
            "invalid_package",
            422,
            # ASCII-escaped: a key is the sender's text, and may hold what
            # no UTF-8 response can (a lone surrogate).
            [
                f"Not accepted: {', '.join(json.dumps(k) for k in unknown)}. "
                f"Rosters only: {', '.join(sorted(allowed))}."
            ],
        )
    missing = [kind for kind in REQUIRED_FILES if kind not in files]
    if missing:
        raise HandoffError("invalid_package", 422, [f"Missing: {', '.join(missing)}."])
    contents: dict[str, bytes] = {}
    for kind in (*REQUIRED_FILES, *OPTIONAL_FILES):
        if kind not in files:
            continue
        value = files[kind]
        if not isinstance(value, str):
            raise HandoffError("invalid_package", 422, [f"`files.{kind}` must be CSV text."])
        contents[kind] = _encoded(value, f"files.{kind}")
    return Bundle(transfer_id, source_app, name, code, contents)


@dataclass(frozen=True)
class Prior:
    review_session: ReviewSession
    actor_user_id: int | None
    completed: bool
    started_at: datetime


def _transfer_of(event: AuditEvent) -> object:
    detail: dict[str, object] = event.detail or {}
    context = detail.get("context")
    if not isinstance(context, dict):
        return None
    return cast(dict[str, object], context).get("transfer_id")


def prior_transfer(db: Session, transfer_id: str) -> Prior | None:
    """The session an earlier create of this transfer made, if it still
    exists, and whether that create completed. Read from the audit
    events, so the proof of concept needs no table of its own."""
    events = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.event_type.in_((EVENT, COMPLETED)))
        .order_by(AuditEvent.id)
    ).all()
    mine = [e for e in events if _transfer_of(e) == transfer_id and e.session is not None]
    created = next((e for e in mine if e.event_type == EVENT), None)
    if created is None or created.session is None:
        return None
    completed = any(e.event_type == COMPLETED and e.session_id == created.session_id for e in mine)
    started = created.created_at
    if started.tzinfo is None:  # SQLite drops tzinfo on write; naive is UTC
        started = started.replace(tzinfo=UTC)
    return Prior(created.session, created.actor_user_id, completed, started)


def rosters_saved(db: Session, review_session: ReviewSession) -> bool:
    """Both rosters hold rows. Quick Setup saves every slot in one unit,
    so a create whose completion was never recorded but whose rosters are
    here was cut off between that save and the record; one with neither
    was cut off before the save."""
    return (
        csv_imports.existing_reviewer_count(db, review_session.id) > 0
        and csv_imports.existing_reviewee_count(db, review_session.id) > 0
    )


def _transfer_context(bundle: Bundle) -> dict[str, str | int | bool]:
    return {"transfer_id": bundle.transfer_id, "source_app": bundle.source_app}


def replayed(db: Session, user: User, bundle: Bundle) -> ReviewSession | None:
    """The session an earlier create of this transfer made, for a replay
    to answer ``already_created`` with; ``None`` when the transfer is new.

    Raises :class:`HandoffError` when the replay is refused: another
    sender's transfer, a session this user may no longer operate (the
    sender once is not the operator now), a transfer whose first try may
    still be running (no rosters yet, started within :data:`IN_PROGRESS`:
    the sender keeps its transfer and tries again), or a transfer cut off
    before its rosters saved, whose draft is left for its operator rather
    than deleted. A transfer cut off between the roster save and its
    completion record gets the record here."""
    prior = prior_transfer(db, bundle.transfer_id)
    if prior is None:
        return None
    if prior.actor_user_id != user.id:
        raise HandoffError("duplicate_conflict", 409)
    if not permissions.user_can_view_session(db, user, prior.review_session.id):
        raise HandoffError("not_authorized", 403)
    if not prior.completed:
        if not rosters_saved(db, prior.review_session):
            if datetime.now(UTC) - prior.started_at < IN_PROGRESS:
                raise HandoffError(
                    "transfer_in_progress",
                    409,
                    ["The first try of this transfer is still running. Try again in a moment."],
                )
            raise HandoffError(
                "transfer_incomplete",
                409,
                ["An earlier try of this transfer stopped before its rosters were saved."],
                review_session=prior.review_session,
            )
        record_completed(db, prior.review_session, user, bundle)
    return prior.review_session


def record_created(
    db: Session,
    review_session: ReviewSession,
    user: User,
    bundle: Bundle,
    correlation_id: str | None,
) -> None:
    """Record the transfer with its new draft, before the rosters, so a
    retry after anything later finds it, and commit both as one unit: the
    draft is created with ``commit=False`` so it never lands without its
    record. A discarded draft takes the record with it
    (``sessions.delete_session`` drops its events)."""
    audit.write_event(
        db,
        event_type=EVENT,
        summary=f"Session {review_session.code} created from {bundle.source_app}",
        actor_user_id=user.id,
        session=review_session,
        payload=audit.counts(files=len(bundle.files)),
        context=_transfer_context(bundle),
        correlation_id=correlation_id,
    )
    unit_of_work.commit(db)


def check_rosters(db: Session, review_session: ReviewSession) -> None:
    """:class:`HandoffError` unless both rosters hold rows. A handoff
    carries people to review and to be reviewed, and a roster with no
    rows also would leave "both rosters saved" not meaning "the save
    happened" for :func:`replayed`."""
    if not rosters_saved(db, review_session):
        raise HandoffError(
            "invalid_setup",
            422,
            ["A handoff needs at least one reviewer and one reviewee."],
            reason="empty_roster",
        )


def record_completed(
    db: Session, review_session: ReviewSession, user: User, bundle: Bundle
) -> None:
    """The completion record: the rosters have saved. A replay reads it,
    whatever the rosters hold later."""
    audit.write_event(
        db,
        event_type=COMPLETED,
        summary=f"Session {review_session.code}: rosters from {bundle.source_app} saved",
        actor_user_id=user.id,
        session=review_session,
        payload=audit.counts(
            reviewers=csv_imports.existing_reviewer_count(db, review_session.id),
            reviewees=csv_imports.existing_reviewee_count(db, review_session.id),
        ),
        context=_transfer_context(bundle),
    )
    unit_of_work.commit(db)


#: The status projection's shape; a sender reads this before the counts.
STATUS_SCHEMA_VERSION = 1


def linked(db: Session, user: User, transfer_id: str) -> ReviewSession:
    """The session a completed handoff made, for the reverse flow's reads
    (segment 23B), or :class:`HandoffError`. A sender names its transfer,
    never a free session reference, so it reads only what its own handoff
    made (interop spec §6.6); the caller must operate that session now."""
    try:
        uuid.UUID(transfer_id)
    except ValueError:
        raise HandoffError("not_linked", 404) from None
    prior = prior_transfer(db, transfer_id)
    if prior is None:
        raise HandoffError("not_linked", 404)
    if not permissions.user_can_view_session(db, user, prior.review_session.id):
        raise HandoffError("not_authorized", 403)
    if not prior.completed:
        raise HandoffError(
            "transfer_incomplete",
            409,
            ["This transfer did not finish, so its session has nothing to report."],
            review_session=prior.review_session,
        )
    return prior.review_session


def status(db: Session, review_session: ReviewSession) -> dict[str, object]:
    """The live status a sender shows (interop spec §6.4, D4): the
    lifecycle state and counts, each with its denominator named, no single
    percentage and no answers. Reads only: no lifecycle step runs here."""
    progress = monitoring.per_reviewer_progress(db, review_session)
    summary = monitoring.summarize(progress)
    instruments = db.scalar(
        select(func.count())
        .select_from(Instrument)
        .where(Instrument.session_id == review_session.id)
    )
    group_instruments = db.scalar(
        select(func.count())
        .select_from(Instrument)
        .where(Instrument.session_id == review_session.id, Instrument.group_kind.is_not(None))
    )
    return {
        "status_schema_version": STATUS_SCHEMA_VERSION,
        "session_ref": review_session.public_id,
        "session_code": review_session.code,
        "name": review_session.name,
        "state": review_session.status,
        "state_label": lifecycle_display_label(review_session.status),
        "as_of": datetime.now(UTC).isoformat(timespec="seconds"),
        "counts": {
            "reviewers": csv_imports.existing_reviewer_count(db, review_session.id),
            "reviewees": csv_imports.existing_reviewee_count(db, review_session.id),
            "instruments": instruments or 0,
            "group_instruments": group_instruments or 0,
            # Of the active reviewers' included assignments; "completed"
            # is Review Robin's own: every required field answered.
            "assignments": sum(p.assignment_count for p in progress),
            "assignments_completed": sum(p.completed_count for p in progress),
            # Of the reviewers with assignments.
            "reviewers_assigned": summary.assigned,
            "reviewers_invited": summary.invited,
            "reviewers_opened": summary.opened,
            "reviewers_submitted": summary.submitted,
        },
    }


#: The answers a sender fetches (segment 23B): ``responses.csv``'s names
#: where they overlap, with the instrument's stable ``session_seq`` in
#: place of its position, and no preamble.
RESULTS_HEADER = (
    "ReviewerEmail",
    "RevieweeEmail",
    "InstrumentSeq",
    "InstrumentLabel",
    "FieldKey",
    "FieldLabel",
    "ResponseType",
    "Value",
    "SubmittedAt",
)
COMPLETION_HEADER = ("ReviewerEmail", "RevieweeEmail", "InstrumentSeq", "State")
EXPORTED = "session.handoff_results_exported"


@dataclass(frozen=True)
class CsvSnapshot:
    name: str
    body: bytes
    rows: int
    etag: str


def _snapshot(name: str, header: tuple[str, ...], rows: list[tuple[str, ...]]) -> CsvSnapshot:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(header)
    writer.writerows(rows)
    body = buffer.getvalue().encode("utf-8")
    return CsvSnapshot(name, body, len(rows), f'"sha256-{hashlib.sha256(body).hexdigest()}"')


def _counted_assignments(review_session: ReviewSession):
    """The assignments the status counts: included, of active reviewers
    (as ``monitoring``), on per-reviewee instruments. Group-scoped ones are
    left out: what a group means for one application is undefined
    (interop spec §6.5)."""
    return (
        select(Assignment, Reviewer, Reviewee, Instrument)
        .join(Reviewer, Assignment.reviewer_id == Reviewer.id)
        .join(Reviewee, Assignment.reviewee_id == Reviewee.id)
        .join(Instrument, Assignment.instrument_id == Instrument.id)
        .where(
            Assignment.session_id == review_session.id,
            Assignment.include.is_(True),
            Reviewer.status == "active",
            Instrument.group_kind.is_(None),
        )
    )


def results_csv(db: Session, review_session: ReviewSession) -> CsvSnapshot:
    """Submitted answers, one row per answer, values as stored (author,
    2026-11-11). Saved drafts are left out (§6.5). A complete snapshot:
    a receiver reconciles on reviewer, reviewee, instrument and field."""
    zone = resolve_session_timezone(review_session)
    stmt = (
        select(Response, Reviewer, Reviewee, Instrument, InstrumentResponseField)
        .join(Assignment, Response.assignment_id == Assignment.id)
        .join(Reviewer, Assignment.reviewer_id == Reviewer.id)
        .join(Reviewee, Assignment.reviewee_id == Reviewee.id)
        .join(Instrument, Assignment.instrument_id == Instrument.id)
        .join(InstrumentResponseField, Response.response_field_id == InstrumentResponseField.id)
        .where(
            Assignment.session_id == review_session.id,
            Assignment.include.is_(True),
            Reviewer.status == "active",
            Instrument.group_kind.is_(None),
            Response.submitted_at.is_not(None),
        )
        .order_by(
            Reviewer.email,
            Reviewee.email_or_identifier,
            Instrument.session_seq,
            InstrumentResponseField.order,
            InstrumentResponseField.id,
        )
    )
    rows = [
        (
            reviewer.email,
            reviewee.email_or_identifier,
            str(instrument.session_seq),
            instrument.short_label or "",
            field.field_key,
            field.label,
            field.response_type,
            response.value if response.value is not None else "",
            iso_in_zone(response.submitted_at, zone),
        )
        for response, reviewer, reviewee, instrument, field in db.execute(stmt)
    ]
    return _snapshot("results.csv", RESULTS_HEADER, rows)


def completion_csv(db: Session, review_session: ReviewSession) -> CsvSnapshot:
    """One row per counted assignment and where it stands, read as Review
    Robin records submission: a submit stamps every saved answer, and an
    edit afterwards clears that answer's stamp.

    - ``submitted``: it has answers and all are submitted; or it has none
      and its reviewer has submitted (optional fields left blank leave no
      rows), by Monitoring's own reviewer state.
    - ``in_progress``: it has answers, not all submitted.
    - ``not_started``: no answers, and its reviewer has not submitted.
    """
    # Answer rows and submitted rows per assignment. A comprehension, not
    # dict(): a Result has .keys(), so dict() would read it as a mapping.
    answers = {
        assignment_id: (rows, submitted)
        for assignment_id, rows, submitted in db.execute(
            select(
                Response.assignment_id, func.count(Response.id), func.count(Response.submitted_at)
            )
            .join(Assignment, Response.assignment_id == Assignment.id)
            .where(Assignment.session_id == review_session.id)
            .group_by(Response.assignment_id)
        )
    }
    reviewer_submitted = {
        progress.reviewer.id
        for progress in monitoring.per_reviewer_progress(db, review_session)
        if progress.pill_state == "submitted"
    }
    stmt = _counted_assignments(review_session).order_by(
        Reviewer.email, Reviewee.email_or_identifier, Instrument.session_seq
    )
    out: list[tuple[str, ...]] = []
    for assignment, reviewer, reviewee, instrument in db.execute(stmt):
        rows, submitted = answers.get(assignment.id, (0, 0))
        if rows:
            state = "submitted" if submitted == rows else "in_progress"
        else:
            state = "submitted" if reviewer.id in reviewer_submitted else "not_started"
        out.append(
            (reviewer.email, reviewee.email_or_identifier, str(instrument.session_seq), state)
        )
    return _snapshot("completion.csv", COMPLETION_HEADER, out)


def record_export(
    db: Session,
    review_session: ReviewSession,
    user: User,
    transfer_id: str,
    snapshot: CsvSnapshot,
) -> None:
    """Audit a fetch the sender took away (§6.5 step 2); a ``304`` takes
    nothing and is not recorded."""
    audit.write_event(
        db,
        event_type=EXPORTED,
        summary=f"Session {review_session.code}: {snapshot.name} fetched by its sender",
        actor_user_id=user.id,
        session=review_session,
        payload=audit.counts(rows=snapshot.rows),
        context={"transfer_id": transfer_id, "file": snapshot.name, "etag": snapshot.etag},
    )
    unit_of_work.commit(db)
