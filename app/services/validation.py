from __future__ import annotations

from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Instrument,
    InstrumentResponseField,
    Reviewee,
    Reviewer,
    ReviewSession,
)
from app.schemas.validation import Severity, ValidationIssue


def validate_session_setup(
    db: Session, review_session: ReviewSession
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    if not review_session.name:
        issues.append(
            ValidationIssue(
                severity=Severity.error,
                source="session",
                field="name",
                message="Session has no name",
            )
        )
    if not review_session.code:
        issues.append(
            ValidationIssue(
                severity=Severity.error,
                source="session",
                field="code",
                message="Session has no code",
            )
        )

    reviewers = list(
        db.execute(
            select(Reviewer).where(Reviewer.session_id == review_session.id)
        ).scalars()
    )
    if not reviewers:
        issues.append(
            ValidationIssue(
                severity=Severity.error,
                source="reviewers",
                message="No reviewers — import a reviewer CSV before activation",
            )
        )
    else:
        for email, count in Counter(r.email.lower() for r in reviewers).items():
            if count > 1:
                issues.append(
                    ValidationIssue(
                        severity=Severity.error,
                        source="reviewers",
                        field="email",
                        message=f"Duplicate reviewer email '{email}' ({count} rows)",
                    )
                )

    reviewees = list(
        db.execute(
            select(Reviewee).where(Reviewee.session_id == review_session.id)
        ).scalars()
    )
    if not reviewees:
        issues.append(
            ValidationIssue(
                severity=Severity.error,
                source="reviewees",
                message="No reviewees — import a reviewee CSV before activation",
            )
        )
    else:
        for ident, count in Counter(
            r.email_or_identifier.lower() for r in reviewees
        ).items():
            if count > 1:
                issues.append(
                    ValidationIssue(
                        severity=Severity.error,
                        source="reviewees",
                        field="email_or_identifier",
                        message=f"Duplicate reviewee identifier '{ident}' ({count} rows)",
                    )
                )

    instruments = list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars()
    )
    for instrument in instruments:
        field_count = db.execute(
            select(InstrumentResponseField.id).where(
                InstrumentResponseField.instrument_id == instrument.id
            )
        ).first()
        if field_count is None:
            label = (
                instrument.description.strip()
                if instrument.description and instrument.description.strip()
                else instrument.name
            )
            issues.append(
                ValidationIssue(
                    severity=Severity.error,
                    source="instruments",
                    message=f"Instrument '{label}' has no response fields",
                )
            )

    if review_session.assignment_mode is None:
        issues.append(
            ValidationIssue(
                severity=Severity.warning,
                source="assignments",
                message=(
                    "No assignments generated yet — reviewers will see an "
                    "empty surface"
                ),
            )
        )

    return issues
