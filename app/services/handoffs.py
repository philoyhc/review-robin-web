"""Handoffs from another Cordware application (segment 23A).

The interop proof of concept's create: another application's operator
posts a bundle of roster CSVs, and Review Robin makes a draft session
from it with its own importers (`spec/handoffs.md`;
`cordware/docs/cordware_interoperability_consolidated_spec_v0.3.md`
§6.3). This module owns the bundle's shape and the replay lookup; the
route runs the create through Quick Setup's pipeline.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, ReviewSession, User
from app.services import audit, csv_imports, permissions, unit_of_work

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
            [f"Not accepted: {', '.join(unknown)}. Rosters only: {', '.join(sorted(allowed))}."],
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
    return Prior(created.session, created.actor_user_id, completed)


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
    sender once is not the operator now), or a transfer cut off before its
    rosters saved, whose draft is left for its operator rather than deleted.
    A transfer cut off between the roster save and its completion record
    gets the record here."""
    prior = prior_transfer(db, bundle.transfer_id)
    if prior is None:
        return None
    if prior.actor_user_id != user.id:
        raise HandoffError("duplicate_conflict", 409)
    if not permissions.user_can_view_session(db, user, prior.review_session.id):
        raise HandoffError("not_authorized", 403)
    if not prior.completed:
        if not rosters_saved(db, prior.review_session):
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
    retry after anything later finds it. A discarded draft takes the
    record with it (``sessions.delete_session`` drops its events)."""
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
