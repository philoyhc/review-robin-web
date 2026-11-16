"""The session settings a linked application owns and re-sends (segment
23F rung 3, `guide/segment_23F_linked_drafts.md`).

A re-send's settings file carries only the rows its application's profile
owns (``LinkedProfile.owned_settings``): the session's name, code,
description, timezone, help contact, tags, Start, End and Relationships
switch. They are parsed and checked as the Settings import checks them,
then written directly, so nothing else of the draft moves: no instrument
is rebuilt, and its ordinals and fields stay as they are. Name and code
are written, not filled only when blank as the import fills them.
"""

from __future__ import annotations

import csv
import dataclasses
import io
import re
from datetime import datetime
from typing import cast

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, User
from app.services import (
    linked_instruments,
    operator_settings,
    scheduled_events,
    session_tags,
    sessions,
)
from app.services.linked_apps import LinkedProfile, Lock
from app.services.session_config_io import (
    HEADER,
    Row,
    SessionSettings,
    parse_session_settings,
    split_rows,
)

#: The ``owned_settings`` entry that owns the session's tags.
TAGS = "session_tags"
_TAG_ROW = re.compile(r"^session_tags\[\d+\]\.tag$")
#: The owned ``session.*`` fields ``sessions.update_session`` writes.
_UPDATE_FIELDS = frozenset(
    {
        "name",
        "code",
        "description",
        "help_contact",
        "scheduled_activate_at",
        "deadline",
        "relationships_enabled",
    }
)
#: Text fields where a blank cell means no value.
_BLANK_IS_NONE = frozenset({"description", "help_contact"})


class NotOwned(ValueError):
    """A re-send's settings file carried rows its application does not own."""

    def __init__(self, fields: list[str]) -> None:
        super().__init__(", ".join(fields))
        self.fields = fields


class SettingsRefused(ValueError):
    """A re-send's owned rows that the Settings import's checks refuse."""

    def __init__(self, details: list[str]) -> None:
        super().__init__("; ".join(details))
        self.details = details


def is_owned(profile: LinkedProfile, field: str) -> bool:
    """Whether a Settings field path is the linked application's."""
    if field in profile.owned_settings:
        return True
    if profile.has(Lock.INSTRUMENT_STRUCTURE) and linked_instruments.owns_row(field):
        return True
    return TAGS in profile.owned_settings and _TAG_ROW.match(field) is not None


def read_rows(content: bytes) -> list[Row]:
    """A settings file's data rows, its header dropped, read as the
    Settings import reads them (``session_config_io.split_rows``): a row
    of fewer than three cells, or holding a NUL, is refused rather than
    padded into a blank value that would clear a field (Codex on #3920).
    :class:`SettingsRefused` for those, and for content that is not
    UTF-8 CSV."""
    try:
        reader = csv.reader(io.StringIO(content.decode("utf-8-sig")))
        raw = [cells for cells in reader if any(cell.strip() for cell in cells)]
    except (UnicodeDecodeError, csv.Error) as exc:
        raise SettingsRefused(["The settings file is not UTF-8 CSV."]) from exc
    if raw and tuple(cell.strip().lower() for cell in raw[0][:3]) == HEADER:
        raw = raw[1:]
    rows, errors = split_rows(raw)
    if errors:
        raise SettingsRefused([f"row {e.row_number}: {e.message}" for e in errors])
    return rows


def prepare(
    db: Session, review_session: ReviewSession, profile: LinkedProfile, content: bytes
) -> SessionSettings:
    """The re-sent settings, checked and not yet written.

    :class:`NotOwned` for any row the profile does not own;
    :class:`SettingsRefused` for a malformed row, what the import's row
    checks refuse, a name
    or code ``SessionCreate`` refuses, an unknown timezone, or a schedule
    out of order on the values the session would hold;
    ``sessions.SessionCodeTakenError`` for a code another session holds."""
    rows = read_rows(content)
    foreign = sorted({row.field for row in rows if not is_owned(profile, row.field)})
    if foreign:
        raise NotOwned(foreign)
    settings, errors = parse_session_settings(rows)
    if errors:
        raise SettingsRefused([f"{error.field}: {error.message}" for error in errors])
    if settings.instrument is not None:
        try:
            linked_instruments.the_instrument(db, review_session)
        except linked_instruments.NotOneInstrument as exc:
            raise SettingsRefused([str(exc)]) from exc
        problems = linked_instruments.row_errors(settings.instrument, settings.instrument_rows)
        if problems:
            raise SettingsRefused(problems)
    overrides = _normalized(settings.overrides)
    try:
        sessions.edit_payload(
            review_session, **{k: v for k, v in overrides.items() if k in _UPDATE_FIELDS}
        )
    except ValidationError as exc:
        raise SettingsRefused(
            [f"session.{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()]
        ) from exc
    zone = overrides.get("display_timezone")
    if zone is not None and not operator_settings.is_valid_timezone(str(zone)):
        raise SettingsRefused([f"session.display_timezone: unknown timezone {zone!r}"])
    if "code" in overrides:
        sessions.ensure_code_available(
            db, str(overrides["code"]), exclude_session_id=review_session.id
        )
    check_schedule(review_session, overrides)
    return dataclasses.replace(settings, overrides=overrides)


def check_schedule(review_session: ReviewSession, overrides: dict[str, object]) -> None:
    """The schedule's order on the values the session will hold: a re-send
    writes End, where the import would only fill it when blank.
    :class:`SettingsRefused` when out of order."""
    try:
        scheduled_events.validate_schedule_ordering(
            scheduled_activate_at=_when(
                overrides.get("scheduled_activate_at", review_session.scheduled_activate_at)
            ),
            deadline=_when(overrides.get("deadline", review_session.deadline)),
            responses_release_at=review_session.responses_release_at,
        )
    except scheduled_events.ScheduledActivateError as exc:
        raise SettingsRefused([str(exc)]) from exc


def apply(
    db: Session,
    review_session: ReviewSession,
    settings: SessionSettings,
    *,
    user: User,
    correlation_id: str | None,
) -> None:
    """Write checked settings through the services that own each field,
    each audited as an operator's edit would be. Inside a caller's unit
    (the re-send's save) these only flush. The code and the schedule's
    order are checked again here, under that unit's session lock, against
    the values an overlapping re-send may have committed since
    :func:`prepare` (Codex on #3920): :class:`SettingsRefused` when the
    order no longer holds."""
    overrides = settings.overrides
    if "scheduled_activate_at" in overrides or "deadline" in overrides:
        check_schedule(review_session, overrides)
    if "code" in overrides:
        sessions.ensure_code_available(
            db, str(overrides["code"]), exclude_session_id=review_session.id
        )
    changes = {k: v for k, v in overrides.items() if k in _UPDATE_FIELDS}
    if changes:
        sessions.update_session(
            db,
            review_session=review_session,
            user=user,
            payload=sessions.edit_payload(review_session, **changes),
            correlation_id=correlation_id,
        )
    if "display_timezone" in overrides:
        sessions.set_session_display_timezone(
            db,
            review_session=review_session,
            user=user,
            timezone_name=cast("str | None", overrides["display_timezone"]),
            correlation_id=correlation_id,
        )
    if settings.instrument is not None:
        linked_instruments.apply_owned(
            db, review_session, settings.instrument, settings.instrument_rows, actor=user
        )
    if settings.tags is not None:
        session_tags.set_tags(
            db,
            review_session=review_session,
            user=user,
            tags=settings.tags,
            correlation_id=correlation_id,
        )


def _normalized(overrides: dict[str, object]) -> dict[str, object]:
    out = dict(overrides)
    for key in _BLANK_IS_NONE & out.keys():
        if out[key] == "":
            out[key] = None
    return out


def _when(value: object) -> datetime | None:
    return value if isinstance(value, datetime) else None
