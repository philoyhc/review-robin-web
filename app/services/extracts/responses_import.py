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
  Per-reviewee instrument rows resolve the reviewee by email and
  find-or-create the assignment (backfill). **Group-scoped** instrument
  rows are collapsed in the export (one row per group, empty
  ``RevieweeEmail``, the group identity composed into ``RevieweeName``);
  they are **fanned back out** to every member assignment of the matching
  group. The group is matched by reusing the exporter's own group-identity
  computation (:func:`responses_extract._group_export_index`), so the
  import identity and the export identity agree by construction.
"""
from __future__ import annotations

import csv
import io
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

__all__ = [
    "ResponsesFormatError",
    "ResponseLoadResult",
    "parse_responses_csv",
    "load_responses",
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


@dataclass
class ResponseLoadResult:
    responses: int = 0
    assignments_created: int = 0
    warnings: list[str] = _dc_field(default_factory=list)


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
    fields), and regenerated assignments. Per-reviewee rows backfill a
    missing assignment; group-scoped rows fan out to existing member
    assignments. Returns counts + a warning per unresolved row.
    """
    result = ResponseLoadResult()

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

    def _stage(
        assignment_id: int,
        field_id: int,
        value: str | None,
        saved_at: datetime,
        submitted_at: datetime | None,
        version: int,
    ) -> None:
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
            result.warnings.append(
                f"unknown reviewer {row.reviewer_email!r}"
            )
            continue
        instrument = instr_by_short.get(
            row.instrument_short_label.strip()
        ) or instr_by_position.get(row.instrument_name.strip())
        if instrument is None:
            result.warnings.append(
                "unknown instrument "
                f"{row.instrument_short_label or row.instrument_name!r}"
            )
            continue
        field = fields.get((instrument.id, row.field_key.strip()))
        if field is None:
            result.warnings.append(
                f"unknown response field {row.field_key!r} on "
                f"instrument {instrument.short_label or instrument.name!r}"
            )
            continue
        saved_at = _parse_dt(row.saved_at)
        if saved_at is None:
            result.warnings.append(
                f"row for {reviewer.email} / {row.field_key} has no "
                "parseable SavedAt"
            )
            continue
        submitted_at = _parse_dt(row.submitted_at)
        version = _parse_version(row.version)
        value = row.value if row.value != "" else None

        if row.flavour == "group-scoped":
            group_key = identity_to_key.get(
                (instrument.id, row.reviewee_name.strip())
            )
            if group_key is None:
                result.warnings.append(
                    f"couldn't match group {row.reviewee_name!r} on "
                    f"instrument {instrument.short_label or instrument.name!r}"
                )
                continue
            member_assignments = members_by.get(
                (reviewer.id, instrument.id, group_key), []
            )
            if not member_assignments:
                result.warnings.append(
                    f"no member assignments for group {row.reviewee_name!r} "
                    f"/ reviewer {reviewer.email}"
                )
                continue
            for member in member_assignments:
                _stage(
                    member.id, field.id, value, saved_at, submitted_at, version
                )
            continue

        # Per-reviewee row.
        reviewee = reviewees.get(normalize_email(row.reviewee_email))
        if reviewee is None:
            result.warnings.append(
                f"unknown reviewee {row.reviewee_email!r}"
            )
            continue
        triple = (reviewer.id, reviewee.id, instrument.id)
        assignment = asgn_by_triple.get(triple)
        if assignment is None:
            assignment = Assignment(
                session_id=review_session.id,
                reviewer_id=reviewer.id,
                reviewee_id=reviewee.id,
                instrument_id=instrument.id,
                include=True,
                is_self_review=(
                    normalize_email(reviewer.email)
                    == normalize_email(reviewee.email_or_identifier)
                ),
                created_by_mode="manual",
            )
            db.add(assignment)
            db.flush()
            asgn_by_triple[triple] = assignment
            result.assignments_created += 1
        _stage(
            assignment.id, field.id, value, saved_at, submitted_at, version
        )

    for response in staged.values():
        db.add(response)
    db.flush()
    result.responses = len(staged)
    return result
