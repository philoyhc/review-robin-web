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
    Assignment,
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


def _check_assignments_no_included_pairs(
    db: Session, review_session: ReviewSession
) -> Iterable[ValidationIssue]:
    """Session-wide warning: zero included rows across every
    instrument.

    Replaces the retired ``assignments.no_mode`` rule (which fired
    only when ``assignment_mode`` was NULL). The successor catches
    a strictly broader case — sessions where Generate ran but every
    row is currently ``include=False`` (e.g. self-reviews bulk-
    deactivated on every instrument), and sessions that never
    generated at all. Either way reviewers would see an empty
    surface.

    Per-instrument detail rides on the
    ``instruments.zero_included`` warning.
    """
    from app.services import assignments as assignments_service

    included = assignments_service.included_count_per_instrument(
        db, review_session.id
    )
    if sum(included.values()) == 0:
        yield ValidationIssue(
            severity=Severity.warning,
            source="assignments",
            message=(
                "No included assignment rows on any instrument — "
                "reviewers will see an empty surface"
            ),
        )


def _instrument_label(instrument: Instrument) -> str:
    """Short reviewer-facing label for messages, with the long
    name as a fallback when no short label is set."""
    return instrument.short_label or instrument.name


def _check_assignments_reviewer_missing(
    db: Session, review_session: ReviewSession
) -> Iterable[ValidationIssue]:
    """Single-instrument sessions: every reviewer must appear on at
    least one ``Assignment`` row.

    Skipped when ``assignment_mode is None`` — a session that has
    never been Generated has no actionable per-reviewer breakdown,
    and surfacing every-reviewer-missing on top of the
    ``assignments.no_included_pairs`` /
    ``instruments.no_rule_pinned`` warnings would double up the
    noise. Also skipped on multi-instrument sessions — the
    per-instrument rule
    (``assignments.reviewer_missing_for_instrument``) carries the
    breakdown there.
    """
    if review_session.assignment_mode is None:
        return
    instruments = list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars()
    )
    if len(instruments) != 1:
        return
    reviewers = list(
        db.execute(
            select(Reviewer)
            .where(Reviewer.session_id == review_session.id)
            .order_by(Reviewer.id)
        ).scalars()
    )
    reviewer_ids_with_assignments = {
        row[0]
        for row in db.execute(
            select(Assignment.reviewer_id)
            .where(Assignment.session_id == review_session.id)
            .distinct()
        ).all()
    }
    for reviewer in reviewers:
        if reviewer.id in reviewer_ids_with_assignments:
            continue
        yield ValidationIssue(
            severity=Severity.warning,
            source="assignments",
            field=f"reviewer_id:{reviewer.id}",
            message=(
                f"Reviewer {reviewer.name!r} ({reviewer.email}) is "
                "missing assignments"
            ),
            fix_anchor=f"#reviewer-row-{reviewer.id}",
        )


def _check_assignments_reviewer_missing_for_instrument(
    db: Session, review_session: ReviewSession
) -> Iterable[ValidationIssue]:
    """Multi-instrument sessions: every (reviewer, instrument) pair
    must appear on at least one ``Assignment`` row.

    Skipped on single-instrument sessions (the sibling
    ``assignments.reviewer_missing`` rule covers those without the
    per-instrument breakdown). Skipped when ``assignment_mode is
    None`` — a never-generated session has no actionable
    per-reviewer breakdown. Per-instrument issues are suppressed for
    an instrument that has zero rows total — the sibling
    ``assignments.instrument_empty`` rule covers that single case
    instead, so the operator sees one issue per empty instrument
    rather than (reviewers × instruments) duplicated noise.
    """
    if review_session.assignment_mode is None:
        return
    instruments = list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars()
    )
    if len(instruments) <= 1:
        return
    reviewers = list(
        db.execute(
            select(Reviewer)
            .where(Reviewer.session_id == review_session.id)
            .order_by(Reviewer.id)
        ).scalars()
    )
    # Per-instrument reviewer-presence map keyed by instrument_id.
    presence: dict[int, set[int]] = {i.id: set() for i in instruments}
    for instrument_id, reviewer_id in db.execute(
        select(Assignment.instrument_id, Assignment.reviewer_id)
        .where(Assignment.session_id == review_session.id)
        .distinct()
    ).all():
        if instrument_id in presence:
            presence[instrument_id].add(reviewer_id)
    for instrument in instruments:
        in_use = presence[instrument.id]
        if not in_use:
            # Sibling instrument_empty rule covers this case.
            continue
        for reviewer in reviewers:
            if reviewer.id in in_use:
                continue
            yield ValidationIssue(
                severity=Severity.warning,
                source="assignments",
                field=(
                    f"reviewer_id:{reviewer.id}"
                    f"|instrument_id:{instrument.id}"
                ),
                message=(
                    f"Reviewer {reviewer.name!r} ({reviewer.email}) "
                    f"is missing assignments for the "
                    f"{_instrument_label(instrument)!r} instrument"
                ),
                fix_anchor=f"#instrument-{instrument.id}",
            )


def _check_assignments_instrument_empty(
    db: Session, review_session: ReviewSession
) -> Iterable[ValidationIssue]:
    """Multi-instrument sessions: every instrument must have at
    least one ``Assignment`` row.

    Skipped on single-instrument sessions (the session-wide
    ``assignments.no_included_pairs`` warning + per-instrument
    ``instruments.zero_included`` warning cover the no-rows case
    without needing the multi-instrument breakdown). Skipped when
    ``assignment_mode is None`` for the same reason.
    """
    if review_session.assignment_mode is None:
        return
    instruments = list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars()
    )
    if len(instruments) <= 1:
        return
    instrument_ids_with_rows = {
        row[0]
        for row in db.execute(
            select(Assignment.instrument_id)
            .where(Assignment.session_id == review_session.id)
            .distinct()
        ).all()
    }
    for instrument in instruments:
        if instrument.id in instrument_ids_with_rows:
            continue
        yield ValidationIssue(
            severity=Severity.warning,
            source="assignments",
            field=f"instrument_id:{instrument.id}",
            message=(
                f"Instrument {_instrument_label(instrument)!r} has "
                "no assignments — reviewers won't see this page"
            ),
            fix_anchor=f"#instrument-{instrument.id}",
        )


def _check_instruments_no_rule_pinned(
    db: Session, review_session: ReviewSession
) -> Iterable[ValidationIssue]:
    """Warning per **legacy** instrument with ``rule_set_id IS NULL``
    once the session has reviewers + reviewees.

    Without a pinned rule, ``replace_assignments`` silently skips
    the instrument — reviewers landing on its page see nothing.
    Gating on rosters being populated prevents the rule from firing
    on a freshly created session (which always has a default
    instrument that's unpinned out of the box); the
    ``reviewers.empty`` / ``reviewees.empty`` errors already cover
    that case more specifically.

    Wave 4 PR 2 — new-model instruments default to Full Matrix when
    Band 1 is untouched (PR 1 fix), so a NULL ``rule_set_id`` on
    a new-model instrument is no longer "not set up." The parallel
    ``instruments.no_visible_response_fields`` rule covers the
    new-model readiness gap.
    """
    has_reviewer = db.execute(
        select(Reviewer.id)
        .where(Reviewer.session_id == review_session.id)
        .limit(1)
    ).first()
    has_reviewee = db.execute(
        select(Reviewee.id)
        .where(Reviewee.session_id == review_session.id)
        .limit(1)
    ).first()
    if has_reviewer is None or has_reviewee is None:
        return
    instruments = list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars()
    )
    for instrument in instruments:
        if instrument.rule_set_id is not None:
            continue
        if instrument.is_new_model:
            continue
        yield ValidationIssue(
            severity=Severity.warning,
            source="instruments",
            message=(
                f"Instrument {_instrument_label(instrument)!r} has no "
                "rule pinned — Generate will skip it; reviewers see "
                "an empty page"
            ),
            fix_anchor=f"#instrument-{instrument.id}",
        )


def _check_new_model_no_visible_response_fields(
    db: Session, review_session: ReviewSession
) -> Iterable[ValidationIssue]:
    """Warning per new-model instrument with no ``visible=True``
    :class:`InstrumentResponseField` rows once the session has
    reviewers + reviewees.

    Without a visible response field, the reviewer surface renders
    zero rows on the instrument's tab even though assignments exist
    (Wave 4 PR 2 — replaces the rule-set-pinned readiness gap for
    new-model instruments).
    """
    has_reviewer = db.execute(
        select(Reviewer.id)
        .where(Reviewer.session_id == review_session.id)
        .limit(1)
    ).first()
    has_reviewee = db.execute(
        select(Reviewee.id)
        .where(Reviewee.session_id == review_session.id)
        .limit(1)
    ).first()
    if has_reviewer is None or has_reviewee is None:
        return
    instruments = list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .where(Instrument.is_new_model.is_(True))
            .order_by(Instrument.order, Instrument.id)
        ).scalars()
    )
    if not instruments:
        return
    new_model_ids = [inst.id for inst in instruments]
    visible_rows = db.execute(
        select(InstrumentResponseField.instrument_id)
        .where(InstrumentResponseField.instrument_id.in_(new_model_ids))
        .where(InstrumentResponseField.visible.is_(True))
        .distinct()
    ).all()
    configured_ids = {row[0] for row in visible_rows}
    for instrument in instruments:
        if instrument.id in configured_ids:
            continue
        yield ValidationIssue(
            severity=Severity.warning,
            source="instruments",
            message=(
                f"Instrument {_instrument_label(instrument)!r} has no "
                "visible response fields — reviewers see an empty page. "
                "Select at least one response-field chip on the "
                "instrument's card."
            ),
            fix_anchor=f"#instrument-{instrument.id}",
        )


def _check_instruments_stale_generated(
    db: Session, review_session: ReviewSession
) -> Iterable[ValidationIssue]:
    """Wave 5 PR 5.1 — retired. The rule used
    ``session_library.evaluate_session_rule_eligibility`` to
    compare per-rule eligible-pair counts against materialised
    counts. That helper retired with the operator-library tier.
    The Workflow card + Generate button already cover the
    "operator pinned a rule but never generated" case the rule
    was catching, so no replacement is needed. The
    ``instruments.stale_generated`` rule key stays in
    ``ValidationRule`` registry as a no-op check so the rule key
    remains addressable from audit history.
    """
    return
    yield  # pragma: no cover — make this an Iterable


def _check_instruments_zero_included(
    db: Session, review_session: ReviewSession
) -> Iterable[ValidationIssue]:
    """Warning per instrument with ``generated_count > 0`` but
    ``included_count == 0``.

    Typical cause: the operator bulk-deactivated every row on the
    instrument (e.g. flipping the Self review checkbox off on a
    self-review-only instrument). Reviewers will land on the
    instrument's page and see nothing.

    Instruments that never generated are silent here — the sibling
    ``assignments.instrument_empty`` / ``assignments.no_included_pairs``
    rules cover the no-rows-at-all case.
    """
    from app.services import assignments as assignments_service

    generated_by_instrument = assignments_service.existing_count_per_instrument(
        db, review_session.id
    )
    included_by_instrument = assignments_service.included_count_per_instrument(
        db, review_session.id
    )
    instruments = list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars()
    )
    for instrument in instruments:
        generated = generated_by_instrument.get(instrument.id, 0)
        included = included_by_instrument.get(instrument.id, 0)
        if generated > 0 and included == 0:
            yield ValidationIssue(
                severity=Severity.warning,
                source="instruments",
                message=(
                    f"Instrument {_instrument_label(instrument)!r} has "
                    f"{generated} generated row"
                    f"{'' if generated == 1 else 's'} but none are "
                    "included — reviewers won't see this page"
                ),
                fix_anchor=f"#instrument-{instrument.id}",
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
        key="instruments.no_rule_pinned",
        source="instruments",
        severity=Severity.warning,
        why=(
            "Each legacy instrument needs a pinned RuleSet so "
            "Generate knows how to materialise reviewer / reviewee "
            "pairs. An unpinned legacy instrument is silently "
            "skipped during generation, leaving its reviewer page "
            "empty. Pin a rule on the Instruments page card. "
            "(New-model instruments default to Full Matrix on "
            "untouched Band 1 and are not affected by this rule.)"
        ),
        fix_url=_instruments_url,
        fix_page_label="Instruments Setup",
        check=_check_instruments_no_rule_pinned,
    ),
    ValidationRule(
        key="instruments.no_visible_response_fields",
        source="instruments",
        severity=Severity.warning,
        why=(
            "A new-model instrument needs at least one visible "
            "response-field chip selected, otherwise reviewers see "
            "an empty page even though assignments exist. Toggle a "
            "response-field chip on the instrument's card to make "
            "it visible to reviewers."
        ),
        fix_url=_instruments_url,
        fix_page_label="Instruments Setup",
        check=_check_new_model_no_visible_response_fields,
    ),
    ValidationRule(
        key="assignments.no_included_pairs",
        source="assignments",
        severity=Severity.warning,
        why=(
            "Reviewers see assignments only for rows where the "
            "``include`` flag is True. When every row across every "
            "instrument is deactivated — or no rows have been "
            "generated yet — reviewers land on an empty surface "
            "and have nothing to do. Re-Generate or re-include rows "
            "before activating, or proceed knowing reviewers will "
            "see no work."
        ),
        fix_url=_assignments_url,
        fix_page_label="Assignments",
        check=_check_assignments_no_included_pairs,
    ),
    ValidationRule(
        key="assignments.reviewer_missing",
        source="assignments",
        severity=Severity.warning,
        why=(
            "A reviewer with no assignment rows sees an empty "
            "review surface and has nothing to do. Typically this "
            "means the pinned rule excluded the reviewer (e.g. a "
            "tag mismatch on an Intra-group rule) or the reviewer "
            "joined the roster after the last Generate. Re-Generate "
            "after fixing the rule or roster."
        ),
        fix_url=_assignments_url,
        fix_page_label="Assignments",
        check=_check_assignments_reviewer_missing,
    ),
    ValidationRule(
        key="assignments.reviewer_missing_for_instrument",
        source="assignments",
        severity=Severity.warning,
        why=(
            "On a multi-instrument session each instrument has its "
            "own pinned rule. A reviewer who's present on some "
            "instruments but missing on others sees a partial "
            "review surface — they'll never reach the pages where "
            "they have no assignments. Adjust that instrument's "
            "rule on the Instruments page or re-Generate."
        ),
        fix_url=_instruments_url,
        fix_page_label="Instruments",
        check=_check_assignments_reviewer_missing_for_instrument,
    ),
    ValidationRule(
        key="assignments.instrument_empty",
        source="assignments",
        severity=Severity.warning,
        why=(
            "An instrument with zero assignment rows is invisible "
            "to every reviewer — the page never opens for anyone. "
            "Either pin a rule on the Instruments page and "
            "re-Generate, or delete the instrument."
        ),
        fix_url=_instruments_url,
        fix_page_label="Instruments",
        check=_check_assignments_instrument_empty,
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
    ValidationRule(
        key="instruments.stale_generated",
        source="instruments",
        severity=Severity.warning,
        why=(
            "Generated assignment rows are materialised from the "
            "engine's eligible-pair output at Generate time. When "
            "the pinned rule changes, or the reviewer / reviewee "
            "rosters or relationships change after Generate, the "
            "materialised rows fall out of sync with what the engine "
            "would produce now. Re-Generate to refresh the pairs."
        ),
        fix_url=_assignments_url,
        fix_page_label="Assignments",
        check=_check_instruments_stale_generated,
    ),
    ValidationRule(
        key="instruments.zero_included",
        source="instruments",
        severity=Severity.warning,
        why=(
            "An instrument with generated rows but zero included "
            "rows is invisible to every reviewer — typically the "
            "operator bulk-deactivated rows (e.g. flipped the Self "
            "review checkbox off). Re-include rows on the "
            "Assignments page or re-Generate."
        ),
        fix_url=_assignments_url,
        fix_page_label="Assignments",
        check=_check_instruments_zero_included,
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
