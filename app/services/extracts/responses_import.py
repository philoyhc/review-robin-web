"""Responses importer — Segment 18P PR F.

The one genuinely new algorithm in the rehydrate feature. The responses
extract (``responses_extract.py``) is **output-only** — reviewers create
responses, operators don't upload them — so reloading a session's
responses from its ``responses.csv`` is net-new machinery.

Two steps:

- :func:`parse_responses_csv` — a parser for the sectioned, analysis-format
  ``responses.csv`` (a per-instrument preamble / field dictionary, a blank
  row, the 21-column header, then the data table). Pure; no DB. It has its
  own (streaming) reader and **no artificial row cap** — a 1,500-reviewer
  file is far larger than ``csv_imports``' 5000-row / 1 MiB limits.
- :func:`load_responses` — resolve each row's identity against a
  freshly-reconstructed session and insert ``Response`` rows.
  **Group-scoped** instrument rows are collapsed in the export (one row
  per group, empty ``RevieweeEmail``, the group identity composed into
  ``RevieweeName``); they are **fanned back out** to every member
  assignment of the matching group. The group is matched by reusing the
  exporter's own group-identity computation
  (:func:`responses_extract._group_export_index`), so the import identity
  and the export identity agree by construction.

**A response is only loaded if a generated assignment row can carry it.**
Assignments are always generated, never hand-created, so a row naming a
pair the rules did not produce has nowhere legitimate to live: it is
dropped, with its reason, and :func:`serialize_dropped_responses` renders
the dropped set back out as a CSV the operator can read. This replaced a
find-or-create backfill that fabricated an ``Assignment`` per unmatched
row — which both invented pairs no rule had authorised and wrote the last
``created_by_mode="manual"`` in the codebase.
"""
from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from dataclasses import dataclass, field as _dc_field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Instrument,
    InstrumentResponseField,
    Response,
    Reviewee,
    Reviewer,
    ReviewSession,
)
from app.services.email_identity import normalize_email
from app.services.extracts.responses_extract import HEADER, _group_export_index
from app.services.instruments import _instrument_label
from app.services.responses import closed_governed_field_ids

__all__ = [
    "ResponsesFormatError",
    "DroppedResponseRow",
    "ResponseLoadResult",
    "parse_responses_csv",
    "load_responses",
    "serialize_dropped_responses",
]


class ResponsesFormatError(Exception):
    """The uploaded file isn't a recognisable responses extract (its
    21-column header is missing)."""


# Column indices into the 21-column ``responses_extract.HEADER``.
_C_REVIEWER_EMAIL = 1
_C_REVIEWEE_NAME = 5
_C_REVIEWEE_EMAIL = 6
_C_INSTRUMENT_NAME = 10
_C_INSTRUMENT_SHORT = 11
_C_FIELD_KEY = 12
_C_VALUE = 15
_C_SAVED_AT = 17
_C_SUBMITTED_AT = 18
_C_VERSION = 19
_C_FLAVOUR = 20


@dataclass
class _ParsedResponseRow:
    reviewer_email: str
    reviewee_name: str
    reviewee_email: str
    instrument_name: str  # positional ``instrument_{n}``
    instrument_short_label: str
    field_key: str
    value: str
    saved_at: str
    submitted_at: str
    version: str
    flavour: str  # ``per-reviewee`` | ``group-scoped``
    # The source row, kept verbatim so a dropped row can be written back
    # out byte-identical to what the operator uploaded.
    raw: tuple[str, ...] = ()


@dataclass(frozen=True)
class DroppedResponseRow:
    """One uploaded row that no generated assignment can carry, with the
    reason it could not be placed."""

    raw: tuple[str, ...]
    reason: str


@dataclass
class ResponseLoadResult:
    responses: int = 0
    dropped: list[DroppedResponseRow] = _dc_field(default_factory=list)

    @property
    def dropped_count(self) -> int:
        return len(self.dropped)


def parse_responses_csv(content: bytes) -> list[_ParsedResponseRow]:
    """Parse a responses extract into typed rows.

    The file is a single field-dictionary preamble, a blank row, the
    21-column header, then the data table (``serialize_responses``). We
    stream the reader, skip everything up to and including the header,
    then read the data rows. Blank rows and short rows are skipped;
    a missing header is a hard error.
    """
    text = content.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text))
    header_seen = False
    parsed: list[_ParsedResponseRow] = []
    for raw in reader:
        if not header_seen:
            if tuple(raw) == HEADER:
                header_seen = True
            continue
        if not raw or all(not cell for cell in raw):
            continue
        if len(raw) < len(HEADER):
            continue
        parsed.append(
            _ParsedResponseRow(
                reviewer_email=raw[_C_REVIEWER_EMAIL],
                reviewee_name=raw[_C_REVIEWEE_NAME],
                reviewee_email=raw[_C_REVIEWEE_EMAIL],
                instrument_name=raw[_C_INSTRUMENT_NAME],
                instrument_short_label=raw[_C_INSTRUMENT_SHORT],
                field_key=raw[_C_FIELD_KEY],
                value=raw[_C_VALUE],
                saved_at=raw[_C_SAVED_AT],
                submitted_at=raw[_C_SUBMITTED_AT],
                version=raw[_C_VERSION],
                flavour=raw[_C_FLAVOUR],
                raw=tuple(raw),
            )
        )
    if not header_seen:
        raise ResponsesFormatError(
            "responses.csv is missing its expected 21-column header row"
        )
    return parsed


def _parse_dt(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _parse_version(value: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 1


def load_responses(
    db: Session,
    *,
    review_session: ReviewSession,
    rows: list[_ParsedResponseRow],
) -> ResponseLoadResult:
    """Insert ``Response`` rows for ``review_session`` from parsed rows.

    Assumes the session already has its rosters, instruments (+ response
    fields), and regenerated assignments. Group-scoped rows fan out to
    every member assignment of the matching group.

    A row is loaded only where a generated assignment already exists to
    carry it. Every other row — unknown reviewer, unknown instrument or
    field, unparseable timestamp, unmatched group, or a pair the rules
    did not generate — is returned in ``result.dropped`` with its reason,
    and nothing is fabricated to make it fit.
    """
    result = ResponseLoadResult()

    def _drop(row: _ParsedResponseRow, reason: str) -> None:
        result.dropped.append(DroppedResponseRow(raw=row.raw, reason=reason))

    reviewers = {
        normalize_email(r.email): r
        for r in db.execute(
            select(Reviewer).where(Reviewer.session_id == review_session.id)
        ).scalars()
    }
    reviewees = {
        normalize_email(r.email_or_identifier): r
        for r in db.execute(
            select(Reviewee).where(Reviewee.session_id == review_session.id)
        ).scalars()
    }

    instruments = list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars()
    )
    instr_by_short = {
        i.short_label: i for i in instruments if i.short_label
    }
    instr_by_position = {
        f"instrument_{n}": inst
        for n, inst in enumerate(instruments, start=1)
    }
    fields = {
        (f.instrument_id, f.field_key): f
        for f in db.execute(
            select(InstrumentResponseField)
            .join(
                Instrument,
                InstrumentResponseField.instrument_id == Instrument.id,
            )
            .where(Instrument.session_id == review_session.id)
        ).scalars()
    }

    assignments = list(
        db.execute(
            select(Assignment).where(
                Assignment.session_id == review_session.id
            )
        ).scalars()
    )
    asgn_by_triple = {
        (a.reviewer_id, a.reviewee_id, a.instrument_id): a
        for a in assignments
    }

    # Reuse the exporter's group-identity computation so the identity we
    # match on import is byte-identical to the one the export composed.
    key_by_assignment, identity = _group_export_index(db, review_session)
    identity_to_key = {
        (instrument_id, ident): group_key
        for (instrument_id, group_key), ident in identity.items()
    }
    members_by: dict[tuple[int, int, tuple[str, ...]], list[Assignment]] = {}
    for a in assignments:
        group_key = key_by_assignment.get(a.id)
        if group_key is None:
            continue
        members_by.setdefault(
            (a.reviewer_id, a.instrument_id, group_key), []
        ).append(a)

    # Stage by (assignment_id, response_field_id) — the Response unique
    # key — so a group fan-out or a duplicate row can't double-insert.
    staged: dict[tuple[int, int], Response] = {}
    staged_from: dict[tuple[int, int], _ParsedResponseRow] = {}

    def _stage(
        row: _ParsedResponseRow,
        assignment_id: int,
        field_id: int,
        value: str | None,
        saved_at: datetime,
        submitted_at: datetime | None,
        version: int,
    ) -> None:
        staged_from[(assignment_id, field_id)] = row
        staged[(assignment_id, field_id)] = Response(
            assignment_id=assignment_id,
            response_field_id=field_id,
            value=value,
            saved_at=saved_at,
            submitted_at=submitted_at,
            version=version,
        )

    for row in rows:
        reviewer = reviewers.get(normalize_email(row.reviewer_email))
        if reviewer is None:
            _drop(row, f"unknown reviewer {row.reviewer_email!r}")
            continue
        instrument = instr_by_short.get(
            row.instrument_short_label.strip()
        ) or instr_by_position.get(row.instrument_name.strip())
        if instrument is None:
            _drop(
                row,
                "unknown instrument "
                f"{row.instrument_short_label or row.instrument_name!r}",
            )
            continue
        field = fields.get((instrument.id, row.field_key.strip()))
        if field is None:
            _drop(
                row,
                f"unknown response field {row.field_key!r} on "
                f"instrument {_instrument_label(instrument)!r}",
            )
            continue
        saved_at = _parse_dt(row.saved_at)
        if saved_at is None:
            _drop(row, "no parseable SavedAt")
            continue
        submitted_at = _parse_dt(row.submitted_at)
        version = _parse_version(row.version)
        value = row.value if row.value != "" else None

        if row.flavour == "group-scoped":
            group_key = identity_to_key.get(
                (instrument.id, row.reviewee_name.strip())
            )
            if group_key is None:
                _drop(
                    row,
                    f"couldn't match group {row.reviewee_name!r} on "
                    f"instrument {_instrument_label(instrument)!r}",
                )
                continue
            member_assignments = members_by.get(
                (reviewer.id, instrument.id, group_key), []
            )
            if not member_assignments:
                _drop(
                    row,
                    f"no member assignments for group {row.reviewee_name!r} "
                    f"/ reviewer {reviewer.email}",
                )
                continue
            for member in member_assignments:
                _stage(
                    row, member.id, field.id, value, saved_at, submitted_at,
                    version,
                )
            continue

        # Per-reviewee row.
        reviewee = reviewees.get(normalize_email(row.reviewee_email))
        if reviewee is None:
            _drop(row, f"unknown reviewee {row.reviewee_email!r}")
            continue
        triple = (reviewer.id, reviewee.id, instrument.id)
        assignment = asgn_by_triple.get(triple)
        if assignment is None:
            # No generated assignment covers this pair, so nothing may
            # carry the response. Fabricating one here would invent a
            # pair no rule authorised.
            _drop(
                row,
                f"no generated assignment for {reviewer.email} → "
                f"{reviewee.email_or_identifier} on "
                f"{_instrument_label(instrument)!r}",
            )
            continue
        _stage(
            row, assignment.id, field.id, value, saved_at, submitted_at, version
        )

    # 19T Item 10 — a closed branch holds no value: an answer to a governed
    # field whose parent's imported answer closes its branch is dropped
    # and reported, once per row even when the row fanned out to a group.
    fields_by_instrument: dict[int, list[InstrumentResponseField]] = {}
    for f in fields.values():
        fields_by_instrument.setdefault(f.instrument_id, []).append(f)
    instrument_by_assignment = {a.id: a.instrument_id for a in assignments}
    answers_by_assignment: dict[int, dict[int, str | None]] = {}
    for (assignment_id, field_id), response in staged.items():
        answers_by_assignment.setdefault(assignment_id, {})[field_id] = (
            response.value
        )
    reported: set[int] = set()
    for assignment_id, answers in answers_by_assignment.items():
        closed = closed_governed_field_ids(
            fields_by_instrument.get(instrument_by_assignment[assignment_id], []),
            answers,
        )
        for field_id in closed & answers.keys():
            del staged[(assignment_id, field_id)]
            row = staged_from[(assignment_id, field_id)]
            if id(row) not in reported:
                reported.add(id(row))
                _drop(row, "its branch is closed by the parent field's answer")

    for response in staged.values():
        db.add(response)
    db.flush()
    result.responses = len(staged)
    return result


DROPPED_HEADER = HEADER + ("DropReason",)


def serialize_dropped_responses(
    dropped: list[DroppedResponseRow],
) -> Iterable[tuple[str, ...]]:
    """Yield CSV rows for the responses a load dropped.

    :data:`DROPPED_HEADER` then one row per drop. A dropped row keeps the
    cells it arrived with, so the file sits under the same column names
    as the upload and can be diffed against it; the trailing
    ``DropReason`` says why it could not be placed. Short rows are padded
    and over-long ones truncated, because the 21 columns are what the
    header promises.

    The header is always emitted, so an empty drop set reads as a file
    with no rows rather than an empty download. Yields rows rather than
    bytes, per :func:`app.services.extracts.stream_csv`.
    """
    yield DROPPED_HEADER
    for row in dropped:
        cells = list(row.raw[: len(HEADER)])
        cells += [""] * (len(HEADER) - len(cells))
        yield tuple(cells) + (row.reason,)
