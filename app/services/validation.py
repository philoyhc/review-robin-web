from __future__ import annotations

from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Reviewee, Reviewer, ReviewSession
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

    issues.append(
        ValidationIssue(
            severity=Severity.info,
            source="instruments",
            message="Instruments not yet implemented (Segment 8)",
        )
    )
    issues.append(
        ValidationIssue(
            severity=Severity.info,
            source="assignments",
            message="Assignments not yet implemented (Segment 7)",
        )
    )

    return issues
