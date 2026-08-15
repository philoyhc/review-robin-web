"""Rehydrate — pre-flight analyzer + shared naming helpers.

Segment 18P PR G1. :func:`analyze_rehydrate_set` is the mandatory
pre-flight (``docs/rehydrate.md`` §3.3): given the resolved extract file
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
import io
import re
from dataclasses import dataclass, field as _dc_field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, SessionOperator, User
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
        value = (row.get(column) or "").strip().lower()
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
        rvr = row.reviewer_email.strip().lower()
        if rvr and rvr not in reviewer_emails:
            unknown_reviewers.add(rvr)
        if row.flavour != "group-scoped":
            rve = row.reviewee_email.strip().lower()
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
