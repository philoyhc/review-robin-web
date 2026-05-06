"""Pre-activation setup validation as a registered rule list.

Each rule emits ``ValidationIssue`` instances annotated with the
rule's ``key``, ``fix_url``, and (where the issue points at a
specific row) a ``fix_anchor``. The Validate page (Segment 11G)
renders a "Fix on {page} ↗" deep-link per issue and surfaces a
"Why this check?" disclosure (PR C) by reading these fields.

The previous monolithic ``validate_session_setup`` function
became one rule per check; the public signature is unchanged
(``list[ValidationIssue]``).
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Instrument,
    InstrumentDisplayField,
    InstrumentResponseField,
    Reviewee,
    Reviewer,
    ReviewSession,
)
from app.schemas.validation import Severity, ValidationIssue


# --------------------------------------------------------------------------- #
# Rule shape
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ValidationRule:
    """One pre-activation check.

    ``key`` is the stable identifier the audit log + UI surfaces
    use (e.g. ``"reviewers.duplicate_email"``); change it only via
    a migration once 11K's audit-event detail schema lands.

    ``check`` runs the actual query and yields raw
    ``ValidationIssue`` instances; the orchestrator stamps
    ``rule_key`` / ``fix_url`` / ``fix_page_label`` and ``source``
    onto each issue. ``fix_anchor`` is set per-issue by the check
    itself when the issue points at a specific row (e.g. the
    duplicate-email rule sets the anchor to the first duplicate's
    ``#reviewer-row-{id}``).
    """

    key: str
    source: str
    severity: Severity
    why: str
    fix_url: Callable[[ReviewSession], str]
    fix_page_label: str
    check: Callable[[Session, ReviewSession], Iterable[ValidationIssue]]


# --------------------------------------------------------------------------- #
# Individual rule check functions
# --------------------------------------------------------------------------- #


def _check_session_no_name(
    db: Session, review_session: ReviewSession
) -> Iterable[ValidationIssue]:
    if not review_session.name:
        yield ValidationIssue(
            severity=Severity.error,
            source="session",
            field="name",
            message="Session has no name",
        )


def _check_session_no_code(
    db: Session, review_session: ReviewSession
) -> Iterable[ValidationIssue]:
    if not review_session.code:
        yield ValidationIssue(
            severity=Severity.error,
            source="session",
            field="code",
            message="Session has no code",
        )


def _check_reviewers_empty(
    db: Session, review_session: ReviewSession
) -> Iterable[ValidationIssue]:
    has_any = db.execute(
        select(Reviewer.id)
        .where(Reviewer.session_id == review_session.id)
        .limit(1)
    ).first()
    if has_any is None:
        yield ValidationIssue(
            severity=Severity.error,
            source="reviewers",
            message="No reviewers — import a reviewer CSV before activation",
        )


def _check_reviewers_duplicate_email(
    db: Session, review_session: ReviewSession
) -> Iterable[ValidationIssue]:
    reviewers = list(
        db.execute(
            select(Reviewer).where(Reviewer.session_id == review_session.id)
        ).scalars()
    )
    by_email: dict[str, list[Reviewer]] = {}
    for r in reviewers:
        by_email.setdefault(r.email.lower(), []).append(r)
    for email, dupes in by_email.items():
        if len(dupes) > 1:
            yield ValidationIssue(
                severity=Severity.error,
                source="reviewers",
                field="email",
                message=f"Duplicate reviewer email '{email}' ({len(dupes)} rows)",
                # First duplicate's row is the deep-link target.
                fix_anchor=f"#reviewer-row-{dupes[0].id}",
            )


def _check_reviewees_empty(
    db: Session, review_session: ReviewSession
) -> Iterable[ValidationIssue]:
    has_any = db.execute(
        select(Reviewee.id)
        .where(Reviewee.session_id == review_session.id)
        .limit(1)
    ).first()
    if has_any is None:
        yield ValidationIssue(
            severity=Severity.error,
            source="reviewees",
            message="No reviewees — import a reviewee CSV before activation",
        )


def _check_reviewees_duplicate_id(
    db: Session, review_session: ReviewSession
) -> Iterable[ValidationIssue]:
    reviewees = list(
        db.execute(
            select(Reviewee).where(Reviewee.session_id == review_session.id)
        ).scalars()
    )
    by_ident: dict[str, list[Reviewee]] = {}
    for r in reviewees:
        by_ident.setdefault(r.email_or_identifier.lower(), []).append(r)
    for ident, dupes in by_ident.items():
        if len(dupes) > 1:
            yield ValidationIssue(
                severity=Severity.error,
                source="reviewees",
                field="email_or_identifier",
                message=f"Duplicate reviewee identifier '{ident}' ({len(dupes)} rows)",
                fix_anchor=f"#reviewee-row-{dupes[0].id}",
            )


def _check_instruments_no_fields(
    db: Session, review_session: ReviewSession
) -> Iterable[ValidationIssue]:
    instruments = list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars()
    )
    for instrument in instruments:
        has_field = db.execute(
            select(InstrumentResponseField.id).where(
                InstrumentResponseField.instrument_id == instrument.id
            )
        ).first()
        if has_field is None:
            label = (
                instrument.description.strip()
                if instrument.description and instrument.description.strip()
                else instrument.name
            )
            yield ValidationIssue(
                severity=Severity.error,
                source="instruments",
                message=f"Instrument '{label}' has no response fields",
                fix_anchor=f"#instrument-{instrument.id}",
            )


def _check_assignments_no_mode(
    db: Session, review_session: ReviewSession
) -> Iterable[ValidationIssue]:
    if review_session.assignment_mode is None:
        yield ValidationIssue(
            severity=Severity.warning,
            source="assignments",
            message=(
                "No assignments generated yet — reviewers will see an "
                "empty surface"
            ),
        )


def _check_email_template_no_help_contact(
    db: Session, review_session: ReviewSession
) -> Iterable[ValidationIssue]:
    if not (review_session.help_contact and review_session.help_contact.strip()):
        yield ValidationIssue(
            severity=Severity.info,
            source="email_template",
            message=(
                "No help contact set — reviewer-facing emails will fall "
                "back to a generic placeholder"
            ),
        )


def _check_instruments_no_display_fields(
    db: Session, review_session: ReviewSession
) -> Iterable[ValidationIssue]:
    instruments = list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars()
    )
    for instrument in instruments:
        has_response_field = db.execute(
            select(InstrumentResponseField.id).where(
                InstrumentResponseField.instrument_id == instrument.id
            )
        ).first()
        if has_response_field is None:
            # The no_fields rule already covers this; skip.
            continue
        has_display_field = db.execute(
            select(InstrumentDisplayField.id).where(
                InstrumentDisplayField.instrument_id == instrument.id
            )
        ).first()
        if has_display_field is None:
            label = (
                instrument.description.strip()
                if instrument.description and instrument.description.strip()
                else instrument.name
            )
            yield ValidationIssue(
                severity=Severity.warning,
                source="instruments",
                message=(
                    f"Instrument '{label}' has no display fields — reviewer "
                    f"pages will be sparse"
                ),
                fix_anchor=f"#instrument-{instrument.id}",
            )


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #


def _session_edit_url(s: ReviewSession) -> str:
    return f"/operator/sessions/{s.id}/edit"


def _reviewers_url(s: ReviewSession) -> str:
    return f"/operator/sessions/{s.id}/reviewers"


def _reviewees_url(s: ReviewSession) -> str:
    return f"/operator/sessions/{s.id}/reviewees"


def _instruments_url(s: ReviewSession) -> str:
    return f"/operator/sessions/{s.id}/instruments"


def _assignments_url(s: ReviewSession) -> str:
    return f"/operator/sessions/{s.id}/assignments"


REGISTERED_RULES: tuple[ValidationRule, ...] = (
    ValidationRule(
        key="session.no_name",
        source="session",
        severity=Severity.error,
        why=(
            "The session name appears in operator dashboards, the audit "
            "log, and reviewer-facing email subjects. A session without "
            "a name is hard to identify across surfaces."
        ),
        fix_url=_session_edit_url,
        fix_page_label="Edit session",
        check=_check_session_no_name,
    ),
    ValidationRule(
        key="session.no_code",
        source="session",
        severity=Severity.error,
        why=(
            "The session code is the operator-typed short identifier "
            "used in URLs, export filenames, and audit lookups. "
            "Required."
        ),
        fix_url=_session_edit_url,
        fix_page_label="Edit session",
        check=_check_session_no_code,
    ),
    ValidationRule(
        key="reviewers.empty",
        source="reviewers",
        severity=Severity.error,
        why=(
            "Activation creates per-reviewer invitations from the "
            "Reviewers roster. With zero reviewers nothing happens "
            "on Activate."
        ),
        fix_url=_reviewers_url,
        fix_page_label="Reviewers Setup",
        check=_check_reviewers_empty,
    ),
    ValidationRule(
        key="reviewers.duplicate_email",
        source="reviewers",
        severity=Severity.error,
        why=(
            "Reviewer email is the join key the invitation flow uses. "
            "Duplicates would cause the second reviewer's invite to "
            "overwrite the first, and Activate would fail loudly. "
            "Required to be unique."
        ),
        fix_url=_reviewers_url,
        fix_page_label="Reviewers Setup",
        check=_check_reviewers_duplicate_email,
    ),
    ValidationRule(
        key="reviewees.empty",
        source="reviewees",
        severity=Severity.error,
        why=(
            "Reviewees are the subjects the reviewers will review. "
            "Without any, generated assignments are empty and "
            "reviewers see no work."
        ),
        fix_url=_reviewees_url,
        fix_page_label="Reviewees Setup",
        check=_check_reviewees_empty,
    ),
    ValidationRule(
        key="reviewees.duplicate_id",
        source="reviewees",
        severity=Severity.error,
        why=(
            "Reviewee email-or-identifier is the per-reviewee join "
            "key for assignments. Duplicates would cause silently "
            "wrong assignment routing. Required to be unique."
        ),
        fix_url=_reviewees_url,
        fix_page_label="Reviewees Setup",
        check=_check_reviewees_duplicate_id,
    ),
    ValidationRule(
        key="instruments.no_fields",
        source="instruments",
        severity=Severity.error,
        why=(
            "An instrument with no response fields renders an empty "
            "review surface for the reviewer. Add at least one "
            "response field before activating."
        ),
        fix_url=_instruments_url,
        fix_page_label="Instruments Setup",
        check=_check_instruments_no_fields,
    ),
    ValidationRule(
        key="assignments.no_mode",
        source="assignments",
        severity=Severity.warning,
        why=(
            "An active session with no assignment mode means "
            "reviewers see an empty review surface and have nothing "
            "to do. Generate assignments before activating, or "
            "proceed knowing reviewers will see no work to complete."
        ),
        fix_url=_assignments_url,
        fix_page_label="Assignments Setup",
        check=_check_assignments_no_mode,
    ),
    ValidationRule(
        key="email_template.no_help_contact",
        source="email_template",
        severity=Severity.info,
        why=(
            "Reviewer-facing emails include a 'Questions? Contact …' "
            "line that falls back to a generic placeholder when help "
            "contact is unset. Setting one improves the reviewer "
            "experience but isn't required."
        ),
        fix_url=_session_edit_url,
        fix_page_label="Edit session",
        check=_check_email_template_no_help_contact,
    ),
    ValidationRule(
        key="instruments.no_display_fields",
        source="instruments",
        severity=Severity.warning,
        why=(
            "Display fields surface reviewee context (name, photo, "
            "tags) on the reviewer page. An instrument with response "
            "fields but no display fields will render reviewer pages "
            "sparsely. Not blocking — sometimes intentional."
        ),
        fix_url=_instruments_url,
        fix_page_label="Instruments Setup",
        check=_check_instruments_no_display_fields,
    ),
)


# --------------------------------------------------------------------------- #
# Orchestrator (public entry point — signature unchanged)
# --------------------------------------------------------------------------- #


def validate_session_setup(
    db: Session, review_session: ReviewSession
) -> list[ValidationIssue]:
    """Run every registered rule against the session.

    Stamps each emitted issue with the rule's ``rule_key``, ``fix_url``,
    and ``fix_page_label``; preserves any per-issue ``fix_anchor`` the
    check function set."""
    issues: list[ValidationIssue] = []
    for rule in REGISTERED_RULES:
        url = rule.fix_url(review_session)
        for issue in rule.check(db, review_session):
            issue.rule_key = rule.key
            issue.fix_url = url
            issue.fix_page_label = rule.fix_page_label
            issue.why = rule.why
            issues.append(issue)
    return issues
