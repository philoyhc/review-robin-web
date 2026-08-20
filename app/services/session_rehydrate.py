"""Rehydrate — pre-flight analyzer + shared naming helpers.

Segment 18P PR G1. :func:`analyze_rehydrate_set` is the mandatory
pre-flight (``spec/rehydrate.md`` §3.3): given the resolved extract file
set (``{filename: bytes}``), it reports **completeness** (required files +
headers), **cross-file integrity** (responses references resolve against
the rosters + settings — catches a cross-session file mix), and a
**preview** (the derived ``_REHYD`` name / code + entity counts), with a
verdict of blocking errors vs warnings.

The ``_REHYD`` name / unique-code derivation lives here too, shared with
the commit orchestrator (PR H). No DB writes — this is read-only.
"""
from __future__ import annotations

import csv
import datetime as _dt
import io
import re
import zipfile
from dataclasses import dataclass, field as _dc_field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Reviewee, Reviewer, ReviewSession, SessionOperator, User
from app.services.email_identity import normalize_email
from app.services.extracts.responses_import import (
    ResponsesFormatError,
    parse_responses_csv,
)

_NAME_MAX = 255
_CODE_MAX = 64

# Extract file kinds → the suffix that identifies them. The extracts emit
# ``{code}_<kind>.csv``; a loose ``<kind>.csv`` also matches. Stats /
# metadata / per-instrument / token / data-shape files don't end in any of
# these, so they're ignored.
_KIND_SUFFIX = {
    "settings": "settings.csv",
    "reviewers": "reviewers.csv",
    "reviewees": "reviewees.csv",
    "relationships": "relationships.csv",
    "observers": "observers.csv",
    "responses": "responses.csv",
}

_RX_SHORT_LABEL = re.compile(r"^instruments\[(\d+)\]\.short_label$")
_RX_FIELD_KEY = re.compile(
    r"^instruments\[(\d+)\]\.response_fields\[\d+\]\.field_key$"
)


@dataclass
class _SettingsInfo:
    name: str
    code: str
    observers_enabled: bool
    relationships_enabled: bool
    short_labels: set[str]
    field_keys: set[tuple[str, str]]  # (short_label, field_key)


@dataclass
class RehydrateReport:
    ok: bool = False
    errors: list[str] = _dc_field(default_factory=list)
    warnings: list[str] = _dc_field(default_factory=list)
    preview: dict[str, Any] = _dc_field(default_factory=dict)


# --------------------------------------------------------------------------- #
# File resolution + lightweight parsers
# --------------------------------------------------------------------------- #


def _resolve_files(files: dict[str, bytes]) -> dict[str, bytes]:
    """Map each uploaded file to a kind by suffix. First match per kind
    wins; unrecognised files are ignored."""
    resolved: dict[str, bytes] = {}
    for name, content in files.items():
        lname = name.lower()
        for kind, suffix in _KIND_SUFFIX.items():
            if kind not in resolved and lname.endswith(suffix):
                resolved[kind] = content
                break
    return resolved


def _decode(content: bytes) -> str:
    return content.decode("utf-8-sig")


def _bool_cell(value: str) -> bool:
    return value.strip().lower() in {"true", "1", "yes"}


def _parse_settings(content: bytes) -> _SettingsInfo | None:
    reader = csv.reader(io.StringIO(_decode(content)))
    rows = list(reader)
    if not rows or tuple(rows[0]) != ("field", "value", "data_type"):
        return None
    name = code = ""
    observers_enabled = relationships_enabled = False
    short_label_by_index: dict[int, str] = {}
    field_keys_by_index: dict[int, set[str]] = {}
    for row in rows[1:]:
        if len(row) < 2:
            continue
        field, value = row[0], row[1]
        if field == "session.name":
            name = value
        elif field == "session.code":
            code = value
        elif field == "session.observers_enabled":
            observers_enabled = _bool_cell(value)
        elif field == "session.relationships_enabled":
            relationships_enabled = _bool_cell(value)
            continue
        m = _RX_SHORT_LABEL.match(field)
        if m is not None:
            short_label_by_index[int(m.group(1))] = value
            continue
        m = _RX_FIELD_KEY.match(field)
        if m is not None:
            field_keys_by_index.setdefault(int(m.group(1)), set()).add(value)
    short_labels = {sl for sl in short_label_by_index.values() if sl}
    field_keys: set[tuple[str, str]] = set()
    for idx, keys in field_keys_by_index.items():
        sl = short_label_by_index.get(idx, "")
        for key in keys:
            field_keys.add((sl, key))
    return _SettingsInfo(
        name=name,
        code=code,
        observers_enabled=observers_enabled,
        relationships_enabled=relationships_enabled,
        short_labels=short_labels,
        field_keys=field_keys,
    )


def _emails_from_csv(content: bytes, column: str) -> set[str] | None:
    reader = csv.DictReader(io.StringIO(_decode(content)))
    if not reader.fieldnames or column not in reader.fieldnames:
        return None
    emails: set[str] = set()
    for row in reader:
        value = normalize_email(row.get(column))
        if value:
            emails.add(value)
    return emails


def _row_count(content: bytes) -> int:
    reader = csv.reader(io.StringIO(_decode(content)))
    rows = [r for r in reader if r and any(c.strip() for c in r)]
    return max(0, len(rows) - 1)  # minus the header


def _examples(items: set[str], n: int = 3) -> str:
    sample = sorted(items)[:n]
    more = "" if len(items) <= n else f", … (+{len(items) - n} more)"
    return ", ".join(repr(s) for s in sample) + more


# --------------------------------------------------------------------------- #
# Naming — shared with the commit orchestrator (PR H)
# --------------------------------------------------------------------------- #


def derive_rehydrate_name(
    db: Session, *, user: User, original_name: str
) -> str:
    """``<original>_REHYD``, or ``_REHYD_1`` / ``_REHYD_2`` … on collision
    against the operator's own session names."""
    existing = {
        row
        for row in db.execute(
            select(ReviewSession.name)
            .join(
                SessionOperator,
                SessionOperator.session_id == ReviewSession.id,
            )
            .where(SessionOperator.user_id == user.id)
        ).scalars()
    }

    def _fit(candidate: str) -> str:
        return candidate[:_NAME_MAX]

    base = _fit(f"{original_name}_REHYD")
    if base not in existing:
        return base
    n = 1
    while True:
        candidate = _fit(f"{original_name}_REHYD_{n}")
        if candidate not in existing:
            return candidate
        n += 1


def derive_unique_code(db: Session, *, original_code: str) -> str:
    """A ``sessions.code`` not yet taken — ``<original>-rehyd``, then
    ``-rehyd-2`` … (codes are globally unique)."""
    candidate = f"{original_code}-rehyd"[:_CODE_MAX]
    n = 2
    while (
        db.execute(
            select(ReviewSession.id).where(ReviewSession.code == candidate)
        ).first()
        is not None
    ):
        candidate = f"{original_code}-rehyd-{n}"[:_CODE_MAX]
        n += 1
    return candidate


# --------------------------------------------------------------------------- #
# The analyzer
# --------------------------------------------------------------------------- #


def analyze_rehydrate_set(
    db: Session, *, files: dict[str, bytes], user: User
) -> RehydrateReport:
    errors: list[str] = []
    warnings: list[str] = []
    resolved = _resolve_files(files)

    # 1. Completeness — the four always-required files.
    for kind in ("settings", "reviewers", "reviewees", "responses"):
        if kind not in resolved:
            errors.append(
                f"Missing {kind}.csv — rehydrate needs the full extract set."
            )
    if errors:
        return RehydrateReport(ok=False, errors=errors, warnings=warnings)

    settings = _parse_settings(resolved["settings"])
    if settings is None:
        errors.append(
            "settings.csv header/format not recognised "
            "(expected field,value,data_type)."
        )
        return RehydrateReport(ok=False, errors=errors, warnings=warnings)

    reviewer_emails = _emails_from_csv(resolved["reviewers"], "ReviewerEmail")
    reviewee_emails = _emails_from_csv(resolved["reviewees"], "RevieweeEmail")
    if reviewer_emails is None:
        errors.append("reviewers.csv is missing its ReviewerEmail column.")
    if reviewee_emails is None:
        errors.append("reviewees.csv is missing its RevieweeEmail column.")

    # Conditional files — required when the settings imply them.
    if settings.observers_enabled and "observers" not in resolved:
        errors.append(
            "settings.csv has observers enabled, but observers.csv is missing."
        )
    if settings.relationships_enabled and "relationships" not in resolved:
        errors.append(
            "settings.csv has relationships enabled, but relationships.csv "
            "is missing."
        )
    if errors:
        return RehydrateReport(ok=False, errors=errors, warnings=warnings)

    assert reviewer_emails is not None and reviewee_emails is not None

    # 2. Cross-file integrity — responses references resolve.
    try:
        parsed = parse_responses_csv(resolved["responses"])
    except ResponsesFormatError as exc:
        errors.append(str(exc))
        return RehydrateReport(ok=False, errors=errors, warnings=warnings)

    unknown_reviewers: set[str] = set()
    unknown_reviewees: set[str] = set()
    unknown_instruments: set[str] = set()
    unknown_fields: set[str] = set()
    for row in parsed:
        rvr = normalize_email(row.reviewer_email)
        if rvr and rvr not in reviewer_emails:
            unknown_reviewers.add(rvr)
        if row.flavour != "group-scoped":
            rve = normalize_email(row.reviewee_email)
            if rve and rve not in reviewee_emails:
                unknown_reviewees.add(rve)
        short = row.instrument_short_label.strip()
        if short and short not in settings.short_labels:
            unknown_instruments.add(short)
        elif short and (short, row.field_key.strip()) not in settings.field_keys:
            unknown_fields.add(f"{short}.{row.field_key.strip()}")

    if unknown_reviewers:
        errors.append(
            f"{len(unknown_reviewers)} reviewer email(s) in responses.csv "
            f"aren't in reviewers.csv (files from different sessions?): "
            f"{_examples(unknown_reviewers)}."
        )
    if unknown_reviewees:
        errors.append(
            f"{len(unknown_reviewees)} reviewee email(s) in responses.csv "
            f"aren't in reviewees.csv: {_examples(unknown_reviewees)}."
        )
    if unknown_instruments:
        errors.append(
            f"{len(unknown_instruments)} instrument(s) in responses.csv "
            f"aren't in settings.csv: {_examples(unknown_instruments)}."
        )
    if unknown_fields:
        errors.append(
            f"{len(unknown_fields)} response field(s) in responses.csv "
            f"aren't in settings.csv: {_examples(unknown_fields)}."
        )

    # 3. Preview — what a Rehydrate would create.
    observers = (
        _row_count(resolved["observers"]) if "observers" in resolved else 0
    )
    relationships = (
        _row_count(resolved["relationships"])
        if "relationships" in resolved
        else 0
    )
    preview = {
        "name": derive_rehydrate_name(
            db, user=user, original_name=settings.name
        ),
        "code": derive_unique_code(db, original_code=settings.code),
        "original_name": settings.name,
        "original_code": settings.code,
        "reviewers": len(reviewer_emails),
        "reviewees": len(reviewee_emails),
        "observers": observers,
        "relationships": relationships,
        "instruments": len(settings.short_labels),
        "responses": len(parsed),
    }

    return RehydrateReport(
        ok=not errors, errors=errors, warnings=warnings, preview=preview
    )


# --------------------------------------------------------------------------- #
# Stash payload packing — a file set ↔ a single zip blob. Shared with the
# validate route (stash) and the commit orchestrator (unstash).
# --------------------------------------------------------------------------- #


def pack_file_set(files: dict[str, bytes]) -> bytes:
    """Zip a ``{filename: bytes}`` set into one blob for the stash."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in sorted(files.items()):
            zf.writestr(name, content)
    return buf.getvalue()


def unpack_file_set(blob: bytes) -> dict[str, bytes]:
    """Inverse of :func:`pack_file_set`."""
    out: dict[str, bytes] = {}
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        for member in zf.namelist():
            out[member] = zf.read(member)
    return out


# --------------------------------------------------------------------------- #
# The commit orchestrator (PR H)
# --------------------------------------------------------------------------- #


class RehydrateError(Exception):
    """A step of the reconstruction pipeline failed. The orchestrator
    hard-deletes the partially-built session before re-raising, so no
    half-rehydrated session survives (``spec/rehydrate.md`` §7)."""


def _settings_rows(content: bytes) -> list[Any]:
    """Parse the 3-column ``field,value,data_type`` settings CSV into
    ``session_config_io.Row`` records for :func:`apply_session_config`."""
    from app.services.session_config_io import HEADER, Row

    reader = csv.reader(io.StringIO(_decode(content)))
    rows_iter = iter(reader)
    try:
        header = next(rows_iter)
    except StopIteration as exc:
        raise RehydrateError("settings.csv is empty.") from exc
    if [c.strip() for c in header] != list(HEADER):
        raise RehydrateError("settings.csv header not recognised.")
    out: list[Any] = []
    for raw in rows_iter:
        if not raw:
            continue
        if len(raw) < 3:
            raise RehydrateError("settings.csv has a malformed row.")
        out.append(Row(field=raw[0], value=raw[1], data_type=raw[2]))
    return out


def _rewrite_identity_rows(rows: list[Any], *, name: str, code: str) -> list[Any]:
    """Return the settings rows with the ``session.name`` / ``session.code``
    value cells replaced by the derived ``_REHYD`` name + unique code —
    otherwise ``apply`` would restore the original name and collide on the
    unique ``code`` index (``spec/rehydrate.md`` §6.2)."""
    from app.services.session_config_io import Row

    rewritten: list[Any] = []
    for row in rows:
        if row.field == "session.name":
            rewritten.append(Row(field=row.field, value=name, data_type=row.data_type))
        elif row.field == "session.code":
            rewritten.append(Row(field=row.field, value=code, data_type=row.data_type))
        else:
            rewritten.append(row)
    return rewritten


def _compose_description(
    settings: _SettingsInfo, *, original_description: str, today: _dt.date
) -> str:
    """Original description + the provenance note (``spec/rehydrate.md``
    §5). The date is stamped by this (non-pure) layer, injectable for
    deterministic tests."""
    note = (
        f'[Rehydrated {today.isoformat()} from an extract of '
        f'"{settings.name}" ({settings.code}).\n'
        "Restored: settings, reviewers, reviewees, observers, "
        "relationships, assignments (regenerated), and submitted "
        "responses.\n"
        "Not restored: invitations, email send history, and participant "
        "results-acknowledgements.]"
    )
    original = (original_description or "").strip()
    return f"{original}\n\n{note}" if original else note


def _original_description(rows: list[Any]) -> str:
    for row in rows:
        if row.field == "session.description":
            return row.value or ""
    return ""


def rehydrate_session(
    db: Session,
    *,
    files: dict[str, bytes],
    user: User,
    correlation_id: str | None = None,
    today: _dt.date | None = None,
) -> ReviewSession:
    """Rebuild a live session from a complete extract file set.

    Runs the full reconstruction pipeline (``spec/rehydrate.md`` §6) as
    one logical unit: create the draft shell → apply settings (with the
    ``_REHYD`` name + unique-code rewrite) → import reviewers / reviewees /
    observers / relationships → regenerate assignments → load responses
    (Part F, backfilling any missing assignment). The session lands in
    **draft** — never auto-activated. On any failure the partially-built
    session is hard-deleted so no half-rehydrated session survives.

    Assumes the caller has already run :func:`analyze_rehydrate_set` on the
    same set and got a clean verdict; the parsers here still fail safe.
    """
    from app.schemas.sessions import SessionCreate
    from app.services import audit, csv_imports, relationships, sessions
    from app.services.assignments import replace_assignments
    from app.services.extracts.responses_import import load_responses
    from app.services.session_config_io import apply_session_config

    today = today or _dt.date.today()
    resolved = _resolve_files(files)
    if "settings" not in resolved:
        raise RehydrateError("settings.csv is required to rehydrate.")
    settings = _parse_settings(resolved["settings"])
    if settings is None:
        raise RehydrateError("settings.csv header/format not recognised.")

    new_name = derive_rehydrate_name(
        db, user=user, original_name=settings.name
    )
    new_code = derive_unique_code(db, original_code=settings.code)
    settings_rows = _settings_rows(resolved["settings"])
    description = _compose_description(
        settings,
        original_description=_original_description(settings_rows),
        today=today,
    )

    review_session = sessions.create_session(
        db,
        user=user,
        payload=SessionCreate(
            name=new_name,
            code=new_code,
            description=description,
            relationships_enabled="relationships" in resolved,
            observers_enabled="observers" in resolved,
        ),
        correlation_id=correlation_id,
    )

    try:
        # 1. Settings — rewrite the identity rows so apply keeps our
        #    derived name / code, then rebuild instruments + config.
        apply_rows = _rewrite_identity_rows(
            settings_rows, name=new_name, code=new_code
        )
        apply_result = apply_session_config(
            db, review_session, apply_rows, user=user, correlation_id=correlation_id
        )
        if not apply_result.ok:
            raise RehydrateError(
                "settings.csv failed to apply: "
                + "; ".join(apply_result.errors)
            )

        # 2. Rosters.
        reviewers_parse = csv_imports.parse_reviewer_csv(resolved["reviewers"])
        if reviewers_parse.is_blocked:
            raise RehydrateError("reviewers.csv failed validation.")
        csv_imports.save_reviewers(
            db,
            session=review_session,
            user=user,
            rows=reviewers_parse.rows,
            filename="reviewers.csv",
            correlation_id=correlation_id or "",
            field_labels_captured=reviewers_parse.field_labels,
        )

        reviewees_parse = csv_imports.parse_reviewee_csv(resolved["reviewees"])
        if reviewees_parse.is_blocked:
            raise RehydrateError("reviewees.csv failed validation.")
        csv_imports.save_reviewees(
            db,
            session=review_session,
            user=user,
            rows=reviewees_parse.rows,
            filename="reviewees.csv",
            correlation_id=correlation_id or "",
            field_labels_captured=reviewees_parse.field_labels,
        )

        if "observers" in resolved:
            observers_parse = csv_imports.parse_observer_csv(resolved["observers"])
            if observers_parse.is_blocked:
                raise RehydrateError("observers.csv failed validation.")
            csv_imports.save_observers(
                db,
                session=review_session,
                user=user,
                rows=observers_parse.rows,
                filename="observers.csv",
                correlation_id=correlation_id or "",
            )

        # 3. Relationships — resolve against the just-imported rosters.
        if "relationships" in resolved:
            roster_reviewers = list(
                db.execute(
                    select(Reviewer).where(
                        Reviewer.session_id == review_session.id
                    )
                ).scalars()
            )
            roster_reviewees = list(
                db.execute(
                    select(Reviewee).where(
                        Reviewee.session_id == review_session.id
                    )
                ).scalars()
            )
            rel_parse = relationships.parse_relationship_csv(
                resolved["relationships"],
                reviewers=roster_reviewers,
                reviewees=roster_reviewees,
            )
            if rel_parse.is_blocked:
                raise RehydrateError("relationships.csv failed validation.")
            relationships.save_relationships(
                db,
                session=review_session,
                user=user,
                rows=rel_parse.rows,
                filename="relationships.csv",
                correlation_id=correlation_id or "",
                field_labels_captured=rel_parse.field_labels,
            )

        # 4. Assignments — regenerate from the restored rule sets.
        replace_assignments(
            db,
            review_session=review_session,
            user=user,
            correlation_id=correlation_id or "",
        )

        # 5. Responses — load, backfilling any assignment the rules didn't
        #    regenerate (e.g. default Full-Matrix instruments).
        parsed_responses = parse_responses_csv(resolved["responses"])
        load_result = load_responses(
            db, review_session=review_session, rows=parsed_responses
        )

        counts = {
            "reviewers": len(reviewers_parse.rows),
            "reviewees": len(reviewees_parse.rows),
            "responses": load_result.responses,
            "assignments_backfilled": load_result.assignments_created,
        }
        audit.write_event(
            db,
            event_type="session.rehydrated",
            summary=(
                f"Rehydrated session {review_session.code} from an extract "
                f'of "{settings.name}" ({settings.code})'
            ),
            actor_user_id=user.id,
            session=review_session,
            payload=audit.counts(**counts),
            context={"source_code": settings.code, "source_name": settings.name},
            correlation_id=correlation_id,
        )
        db.commit()
    except Exception:
        # Hard-delete the partially-built session so no half-rehydrated
        # session survives (all-or-nothing — spec/rehydrate.md §7).
        db.rollback()
        fresh = db.get(ReviewSession, review_session.id)
        if fresh is not None:
            sessions.delete_session(
                db, review_session=fresh, user=user, correlation_id=correlation_id
            )
        raise

    db.refresh(review_session)
    return review_session
