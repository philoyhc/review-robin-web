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

from app.db.models import AuditEvent, ReviewSession

PROTOCOL = "cordware.csv-handoff"
PROTOCOL_VERSION = 1
OPERATION = "reviewrobin.create_draft_session"
#: The whole request body, CSVs included.
MAX_BYTES = 1024 * 1024
#: Rosters only (interop spec §13.1): no Settings file.
REQUIRED_FILES = ("reviewers", "reviewees")
OPTIONAL_FILES = ("relationships", "observers")
#: The audit event a successful create writes; its ``context`` carries
#: the transfer, which is how a replay is recognized.
EVENT = "session.handoff_created"


class HandoffError(Exception):
    """A refused handoff: an error code from the interop spec's
    vocabulary (§7.3), an HTTP status, and lines for the sender to show."""

    def __init__(self, code: str, status: int, details: list[str] | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.status = status
        self.details = details or []


@dataclass(frozen=True)
class Bundle:
    transfer_id: str
    source_app: str
    name: str
    code: str
    #: CSV bytes by Quick Setup slot, in slot order.
    files: dict[str, bytes]


def _text(data: dict[str, object], key: str, limit: int) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise HandoffError(
            "invalid_package", 422, [f"`{key}` must be text of 1–{limit} characters"]
        )
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
        contents[kind] = value.encode("utf-8")
    return Bundle(transfer_id, source_app, name, code, contents)


@dataclass(frozen=True)
class Prior:
    review_session: ReviewSession
    actor_user_id: int | None


def prior_transfer(db: Session, transfer_id: str) -> Prior | None:
    """The session an earlier create of this transfer made, if it still
    exists. Read from the audit events, so the proof of concept needs
    no table of its own."""
    events = db.scalars(
        select(AuditEvent).where(AuditEvent.event_type == EVENT).order_by(AuditEvent.id)
    ).all()
    for event in events:
        detail: dict[str, object] = event.detail or {}
        context = detail.get("context")
        if not isinstance(context, dict):
            continue
        found = cast(dict[str, object], context).get("transfer_id")
        if found == transfer_id and event.session is not None:
            return Prior(event.session, event.actor_user_id)
    return None
