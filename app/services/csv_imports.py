from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Reviewee, Reviewer, ReviewSession, User
from app.schemas.imports import ReviewerImportRow, RevieweeImportRow
from app.schemas.validation import Severity, ValidationIssue
from app.services import audit, session_lifecycle as lifecycle

MAX_BYTES = 1 * 1024 * 1024
MAX_ROWS = 5000

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass
class ParseResult:
    rows: list[ReviewerImportRow] | list[RevieweeImportRow]
    issues: list[ValidationIssue]

    @property
    def is_blocked(self) -> bool:
        return any(issue.is_blocking for issue in self.issues)


def _decode_csv(content: bytes, source: str) -> tuple[str | None, ValidationIssue | None]:
    if len(content) > MAX_BYTES:
        return None, ValidationIssue(
            severity=Severity.error,
            source=source,
            message=f"File too large (max {MAX_BYTES // 1024} KiB)",
        )
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return None, ValidationIssue(
            severity=Severity.error,
            source=source,
            message="File is not valid UTF-8",
        )
    return text, None


def _read_dict_rows(
    text: str,
    source: str,
) -> tuple[list[dict[str, str]] | None, ValidationIssue | None]:
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return None, ValidationIssue(
            severity=Severity.error,
            source=source,
            message="CSV has no header row",
        )
    rows = list(reader)
    if len(rows) > MAX_ROWS:
        return None, ValidationIssue(
            severity=Severity.error,
            source=source,
            message=f"Too many rows (max {MAX_ROWS})",
        )
    return rows, None


def _missing_columns_issues(
    fieldnames: list[str],
    required: list[str],
    source: str,
) -> list[ValidationIssue]:
    return [
        ValidationIssue(
            severity=Severity.error,
            source=source,
            message=f"Missing required column: {col}",
            field=col,
        )
        for col in required
        if col not in fieldnames
    ]


def _cell(row: dict[str, str], key: str) -> str:
    value = row.get(key)
    return value.strip() if value else ""


def _none_if_blank(row: dict[str, str], key: str) -> str | None:
    value = _cell(row, key)
    return value or None


def _parse_email(
    value: str,
    *,
    strict: bool,
    source: str,
    row_number: int,
    field: str,
) -> str | ValidationIssue:
    """Validate ``value`` as an email address.

    With ``strict=True`` the value must match ``_EMAIL_RE`` — the
    reviewer path, where every reviewer needs an institutional email
    for auth.

    With ``strict=False`` non-email identifiers are accepted (no
    ``@``); but if an ``@`` is present the value must still match
    ``_EMAIL_RE`` so typos like ``foo@`` or ``@bar`` are caught
    rather than imported and dying later on send. This is the
    reviewee path today, where reviewees aren't expected to use the
    app.

    The ``strict`` flag is the seam for the future symmetric mode
    where reviewees use the app and require institutional email; at
    that point the reviewee call site flips ``strict=True`` (or
    threads it from a per-session toggle).
    """
    if not strict and "@" not in value:
        return value
    if not _EMAIL_RE.fullmatch(value):
        return ValidationIssue(
            severity=Severity.error,
            source=source,
            row_number=row_number,
            field=field,
            message=f"{field} '{value}' is not a valid email address",
        )
    return value


def parse_reviewer_csv(content: bytes) -> ParseResult:
    source = "reviewers"
    issues: list[ValidationIssue] = []

    text, decode_issue = _decode_csv(content, source)
    if decode_issue is not None:
        return ParseResult(rows=[], issues=[decode_issue])
    assert text is not None

    raw_rows, count_issue = _read_dict_rows(text, source)
    if count_issue is not None:
        return ParseResult(rows=[], issues=[count_issue])
    assert raw_rows is not None

    reader = csv.DictReader(io.StringIO(text))
    fieldnames = list(reader.fieldnames or [])

    issues.extend(
        _missing_columns_issues(fieldnames, ["ReviewerName", "ReviewerEmail"], source)
    )
    if issues:
        return ParseResult(rows=[], issues=issues)

    parsed: list[ReviewerImportRow] = []
    seen_emails: dict[str, int] = {}

    for index, raw in enumerate(raw_rows, start=1):
        name = _cell(raw, "ReviewerName")
        email = _cell(raw, "ReviewerEmail")
        if not name:
            issues.append(
                ValidationIssue(
                    severity=Severity.error,
                    source=source,
                    row_number=index,
                    field="ReviewerName",
                    message="ReviewerName is required",
                )
            )
            continue
        if not email:
            issues.append(
                ValidationIssue(
                    severity=Severity.error,
                    source=source,
                    row_number=index,
                    field="ReviewerEmail",
                    message="ReviewerEmail is required",
                )
            )
            continue
        email_check = _parse_email(
            email,
            strict=True,
            source=source,
            row_number=index,
            field="ReviewerEmail",
        )
        if isinstance(email_check, ValidationIssue):
            issues.append(email_check)
            continue
        if email.lower() in seen_emails:
            issues.append(
                ValidationIssue(
                    severity=Severity.error,
                    source=source,
                    row_number=index,
                    field="ReviewerEmail",
                    message=(
                        f"Duplicate ReviewerEmail '{email}' "
                        f"(also on row {seen_emails[email.lower()]})"
                    ),
                )
            )
            continue
        seen_emails[email.lower()] = index
        parsed.append(
            ReviewerImportRow(
                name=name,
                email=email,
                tag_1=_none_if_blank(raw, "ReviewerTag1"),
                tag_2=_none_if_blank(raw, "ReviewerTag2"),
                tag_3=_none_if_blank(raw, "ReviewerTag3"),
            )
        )

    return ParseResult(rows=parsed, issues=issues)


def parse_reviewee_csv(content: bytes) -> ParseResult:
    source = "reviewees"
    issues: list[ValidationIssue] = []

    text, decode_issue = _decode_csv(content, source)
    if decode_issue is not None:
        return ParseResult(rows=[], issues=[decode_issue])
    assert text is not None

    raw_rows, count_issue = _read_dict_rows(text, source)
    if count_issue is not None:
        return ParseResult(rows=[], issues=[count_issue])
    assert raw_rows is not None

    reader = csv.DictReader(io.StringIO(text))
    fieldnames = list(reader.fieldnames or [])

    issues.extend(
        _missing_columns_issues(fieldnames, ["RevieweeName", "RevieweeEmail"], source)
    )
    if issues:
        return ParseResult(rows=[], issues=issues)

    parsed: list[RevieweeImportRow] = []
    seen_identifiers: dict[str, int] = {}

    for index, raw in enumerate(raw_rows, start=1):
        name = _cell(raw, "RevieweeName")
        identifier = _cell(raw, "RevieweeEmail")
        if not name:
            issues.append(
                ValidationIssue(
                    severity=Severity.error,
                    source=source,
                    row_number=index,
                    field="RevieweeName",
                    message="RevieweeName is required",
                )
            )
            continue
        if not identifier:
            issues.append(
                ValidationIssue(
                    severity=Severity.error,
                    source=source,
                    row_number=index,
                    field="RevieweeEmail",
                    message="RevieweeEmail is required",
                )
            )
            continue
        identifier_check = _parse_email(
            identifier,
            strict=False,
            source=source,
            row_number=index,
            field="RevieweeEmail",
        )
        if isinstance(identifier_check, ValidationIssue):
            issues.append(identifier_check)
            continue
        if identifier.lower() in seen_identifiers:
            issues.append(
                ValidationIssue(
                    severity=Severity.error,
                    source=source,
                    row_number=index,
                    field="RevieweeEmail",
                    message=(
                        f"Duplicate RevieweeEmail '{identifier}' "
                        f"(also on row {seen_identifiers[identifier.lower()]})"
                    ),
                )
            )
            continue
        seen_identifiers[identifier.lower()] = index
        parsed.append(
            RevieweeImportRow(
                name=name,
                email_or_identifier=identifier,
                profile_link=_none_if_blank(raw, "PhotoLink"),
                tag_1=_none_if_blank(raw, "RevieweeTag1"),
                tag_2=_none_if_blank(raw, "RevieweeTag2"),
                tag_3=_none_if_blank(raw, "RevieweeTag3"),
            )
        )

    return ParseResult(rows=parsed, issues=issues)


def existing_reviewer_count(db: Session, session_id: int) -> int:
    return _count(db, Reviewer, session_id)


def existing_reviewee_count(db: Session, session_id: int) -> int:
    return _count(db, Reviewee, session_id)


def _count(db: Session, model: type[Reviewer] | type[Reviewee], session_id: int) -> int:
    stmt = select(model.id).where(model.session_id == session_id)
    return len(db.execute(stmt).all())


def save_reviewers(
    db: Session,
    *,
    session: ReviewSession,
    user: User,
    rows: list[ReviewerImportRow],
    filename: str,
    correlation_id: str,
) -> tuple[int, int]:
    return _save(
        db,
        session=session,
        user=user,
        model=Reviewer,
        rows=rows,
        event_type="reviewers.imported",
        source_label="reviewers",
        filename=filename,
        correlation_id=correlation_id,
        to_kwargs=_reviewer_to_kwargs,
    )


def save_reviewees(
    db: Session,
    *,
    session: ReviewSession,
    user: User,
    rows: list[RevieweeImportRow],
    filename: str,
    correlation_id: str,
) -> tuple[int, int]:
    result = _save(
        db,
        session=session,
        user=user,
        model=Reviewee,
        rows=rows,
        event_type="reviewees.imported",
        source_label="reviewees",
        filename=filename,
        correlation_id=correlation_id,
        to_kwargs=_reviewee_to_kwargs,
    )
    # Lazy-seed display fields for any populated reviewee slots
    # (profile_link / tag_1..3) — see guide/unfinished_business item #14.
    from app.services.instruments import seed_display_fields_from_reviewees

    if seed_display_fields_from_reviewees(db, session):
        db.commit()
    return result


def _reviewer_to_kwargs(row: ReviewerImportRow, session_id: int) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "name": row.name,
        "email": row.email,
        "tag_1": row.tag_1,
        "tag_2": row.tag_2,
        "tag_3": row.tag_3,
    }


def _reviewee_to_kwargs(row: RevieweeImportRow, session_id: int) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "name": row.name,
        "email_or_identifier": row.email_or_identifier,
        "profile_link": row.profile_link,
        "tag_1": row.tag_1,
        "tag_2": row.tag_2,
        "tag_3": row.tag_3,
    }


def _save(
    db: Session,
    *,
    session: ReviewSession,
    user: User,
    model: Any,
    rows: list[Any],
    event_type: str,
    source_label: str,
    filename: str,
    correlation_id: str,
    to_kwargs: Any,
) -> tuple[int, int]:
    lifecycle.invalidate_if_validated(
        db,
        review_session=session,
        user=user,
        reason=f"{source_label}_imported",
        correlation_id=correlation_id,
    )
    cascaded_assignment_count = _count_assignments(db, session.id)

    existing_rows = list(
        db.execute(select(model).where(model.session_id == session.id)).scalars()
    )
    replaced = len(existing_rows)
    for row in existing_rows:
        db.delete(row)
    db.flush()

    for row in rows:
        db.add(model(**to_kwargs(row, session.id)))
    db.flush()

    audit.write_event(
        db,
        event_type=event_type,
        summary=f"Imported {len(rows)} {source_label} (replaced {replaced})",
        actor_user_id=user.id,
        session_id=session.id,
        detail={
            "replaced_count": replaced,
            "new_count": len(rows),
            "filename": filename,
            "cascaded_assignment_count": cascaded_assignment_count,
        },
        correlation_id=correlation_id,
    )

    db.commit()
    return replaced, len(rows)


def _count_assignments(db: Session, session_id: int) -> int:
    from app.db.models import Assignment

    stmt = select(Assignment.id).where(Assignment.session_id == session_id)
    return len(db.execute(stmt).all())


def existing_assignment_count(db: Session, session_id: int) -> int:
    """Used by routes to surface the cascade warning before import."""
    return _count_assignments(db, session_id)


def delete_all_reviewers(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    correlation_id: str,
) -> tuple[int, int]:
    return _delete_all(
        db,
        review_session=review_session,
        user=user,
        model=Reviewer,
        event_type="reviewers.deleted_all",
        source_label="reviewers",
        correlation_id=correlation_id,
    )


def delete_all_reviewees(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    correlation_id: str,
) -> tuple[int, int]:
    return _delete_all(
        db,
        review_session=review_session,
        user=user,
        model=Reviewee,
        event_type="reviewees.deleted_all",
        source_label="reviewees",
        correlation_id=correlation_id,
    )


def _delete_all(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    model: Any,
    event_type: str,
    source_label: str,
    correlation_id: str,
) -> tuple[int, int]:
    lifecycle.invalidate_if_validated(
        db,
        review_session=review_session,
        user=user,
        reason=f"{source_label}_deleted_all",
        correlation_id=correlation_id,
    )
    cascaded = _count_assignments(db, review_session.id)
    rows = list(
        db.execute(
            select(model).where(model.session_id == review_session.id)
        ).scalars()
    )
    deleted = len(rows)
    for row in rows:
        db.delete(row)
    db.flush()

    audit.write_event(
        db,
        event_type=event_type,
        summary=f"Deleted all {deleted} {source_label}",
        actor_user_id=user.id,
        session_id=review_session.id,
        detail={
            "deleted_count": deleted,
            "cascaded_assignment_count": cascaded,
        },
        correlation_id=correlation_id,
    )
    db.commit()
    return deleted, cascaded
