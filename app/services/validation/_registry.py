"""``REGISTERED_RULES``, the fix-link helpers it names, and
``validate_session_setup``, which runs them. Segment 20E rung 4b, moved unchanged from
``validation.py``.
"""

from __future__ import annotations


from sqlalchemy.orm import Session

from app.db.models import (
    ReviewSession,
)
from app.schemas.validation import Severity, ValidationIssue
from app.services.validation._inputs import (
    ValidationRule,
    load_validation_inputs,
)
from app.services.validation._rosters import (
    _check_session_no_name,
    _check_session_no_code,
    _check_reviewers_empty,
    _check_reviewers_duplicate_email,
    _check_observers_duplicate_email,
    _CROSS_ROSTER_WHY,
    _check_reviewers_cross_roster_identity,
    _check_reviewees_cross_roster_identity,
    _check_observers_cross_roster_identity,
    _check_reviewees_empty,
    _check_reviewees_duplicate_id,
    _check_reviewers_duplicate_account,
    _check_reviewees_duplicate_account,
    _check_observers_duplicate_account,
    _DUPLICATE_ACCOUNT_WHY,
    _check_reviewees_unreachable_for_results,
    _check_email_template_no_help_contact,
    _check_reviewees_mirror_drift,
    _MIRROR_DRIFT_WHY,
)
from app.services.validation._assignments import (
    _check_assignments_no_included_pairs,
    _check_assignments_reviewer_missing,
    _check_assignments_reviewer_missing_for_instrument,
    _check_assignments_instrument_empty,
)
from app.services.validation._instruments import (
    _check_instruments_no_fields,
    _check_instruments_no_rule_pinned,
    _check_new_model_no_visible_response_fields,
    _check_instruments_rule_set_unloadable,
    _check_instruments_stale_generated,
    _check_instruments_zero_included,
    _check_instruments_no_display_fields,
)

# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #


def _session_edit_url(s: ReviewSession) -> str:
    # 18R Item 4 Slice 5 — the Edit page is retired from the UI; session
    # config is edited in place on Session Home's Session details card.
    # "Fix" links open that card in edit mode, with no fragment (19X
    # Item 7); the row-level Fix links keep theirs.
    return f"/operator/sessions/{s.public_id}?editing=1"


def _reviewers_url(s: ReviewSession) -> str:
    return f"/operator/sessions/{s.public_id}/reviewers"


def _reviewees_url(s: ReviewSession) -> str:
    return f"/operator/sessions/{s.public_id}/reviewees"


def _observers_url(s: ReviewSession) -> str:
    return f"/operator/sessions/{s.public_id}/observers"


def _instruments_url(s: ReviewSession) -> str:
    return f"/operator/sessions/{s.public_id}/instruments"


def _assignments_url(s: ReviewSession) -> str:
    return f"/operator/sessions/{s.public_id}/assignments"


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
        key="reviewers.duplicate_account",
        source="reviewers",
        severity=Severity.warning,
        why=_DUPLICATE_ACCOUNT_WHY,
        fix_url=_reviewers_url,
        fix_page_label="Reviewers Setup",
        check=_check_reviewers_duplicate_account,
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
        key="reviewees.duplicate_account",
        source="reviewees",
        severity=Severity.warning,
        why=_DUPLICATE_ACCOUNT_WHY,
        fix_url=_reviewees_url,
        fix_page_label="Reviewees Setup",
        check=_check_reviewees_duplicate_account,
    ),
    ValidationRule(
        key="reviewees.mirror_drift",
        source="reviewees",
        severity=Severity.error,
        why=_MIRROR_DRIFT_WHY,
        fix_url=_reviewers_url,
        fix_page_label="Reviewers Setup",
        check=_check_reviewees_mirror_drift,
    ),
    ValidationRule(
        key="reviewees.unreachable_for_results",
        source="reviewees",
        severity=Severity.warning,
        why=(
            "A reviewee sees the responses written about them when "
            "they sign in with the email their identifier holds. "
            "With no email there, nothing they sign in as matches "
            "them, so they can never reach those responses. "
            "Non-blocking in case "
            "the identifiers are meant to be anonymous (an "
            "analysis-only session); the warning just names the "
            "implication."
        ),
        fix_url=_reviewees_url,
        fix_page_label="Reviewees Setup",
        check=_check_reviewees_unreachable_for_results,
    ),
    ValidationRule(
        key="observers.duplicate_email",
        source="observers",
        severity=Severity.error,
        why=(
            "Observer email is the join key the collation surface "
            "authenticates against. Two rows sharing one mailbox make "
            "the observer's access ambiguous, and the roster reads as "
            "though one person were two. Required to be unique — the "
            "database enforces it on writes, and this check reports a "
            "row that predates that guarantee."
        ),
        fix_url=_observers_url,
        fix_page_label="Observers Setup",
        check=_check_observers_duplicate_email,
    ),
    ValidationRule(
        key="observers.duplicate_account",
        source="observers",
        severity=Severity.warning,
        why=_DUPLICATE_ACCOUNT_WHY,
        fix_url=_observers_url,
        fix_page_label="Observers Setup",
        check=_check_observers_duplicate_account,
    ),
    ValidationRule(
        key="reviewers.cross_roster_identity",
        source="reviewers",
        severity=Severity.error,
        why=_CROSS_ROSTER_WHY,
        fix_url=_reviewers_url,
        fix_page_label="Reviewers Setup",
        check=_check_reviewers_cross_roster_identity,
    ),
    ValidationRule(
        key="reviewees.cross_roster_identity",
        source="reviewees",
        severity=Severity.error,
        why=_CROSS_ROSTER_WHY,
        fix_url=_reviewees_url,
        fix_page_label="Reviewees Setup",
        check=_check_reviewees_cross_roster_identity,
    ),
    ValidationRule(
        key="observers.cross_roster_identity",
        source="observers",
        severity=Severity.error,
        why=_CROSS_ROSTER_WHY,
        fix_url=_observers_url,
        fix_page_label="Observers Setup",
        check=_check_observers_cross_roster_identity,
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
            "Retired: this check raises no findings. An instrument "
            "with no assignment rules uses Full Matrix, so a missing "
            "rule is not a problem in itself. Whether the instrument "
            "is ready is checked by the visible-response-fields "
            "check and by its three Band 1 links, which must each "
            "be set. It stays listed so past audit entries still "
            "name it."
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
            "Reviewers see only active assignments. When every "
            "assignment across every instrument is inactive on the "
            "Assignments page — or none has been generated yet — "
            "reviewers land on an empty page and have nothing to do. "
            "Prepare again, or select assignments there and use "
            "Activate, before activating the session; or proceed "
            "knowing reviewers will see no work."
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
            "An active reviewer with no included assignment on an "
            "active reviewee sees an empty review surface and gets no "
            "invitation. Typically this means the pinned rule "
            "excluded the reviewer (e.g. a tag mismatch on an "
            "Intra-group rule), every reviewee they review is "
            "inactive, or the reviewer joined the roster after the "
            "last Generate. Re-Generate after fixing the rule or "
            "roster."
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
            "The default invitation, reminder and responses-received "
            "emails end with a 'Questions? Contact …' line, and the "
            "reviewer surface shows one under its title; both are "
            "dropped when help contact is unset, and an overridden "
            "body that names $help_contact reads 'the person running "
            "this review'. Setting one improves the reviewer "
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
        key="instruments.rule_set_unloadable",
        source="instruments",
        severity=Severity.error,
        why=(
            "Generate runs each instrument's stored assignment rule. "
            "One the engine can't load, written before the writers "
            "checked or edited outside the app, fails Generate, so "
            "Prepare can't finish until the rule is changed or removed "
            "in the instrument's Instrument assignment rule and saved."
        ),
        fix_url=_instruments_url,
        fix_page_label="Instruments Setup",
        check=_check_instruments_rule_set_unloadable,
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
    check function set.

    Every input more than one rule needs is loaded once, up front, and
    handed to each ``check`` — see :class:`ValidationInputs` for what
    that covers and why it is a per-run object rather than a cache."""
    inputs = load_validation_inputs(db, review_session)
    issues: list[ValidationIssue] = []
    for rule in REGISTERED_RULES:
        url = rule.fix_url(review_session)
        for issue in rule.check(db, review_session, inputs):
            issue.rule_key = rule.key
            issue.fix_url = url
            issue.fix_page_label = rule.fix_page_label
            issue.why = rule.why
            issues.append(issue)
    return issues
