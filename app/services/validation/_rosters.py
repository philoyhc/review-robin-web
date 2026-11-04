"""The rules on the session's own fields and its rosters: names and codes,
empty and duplicate rosters, one person across rosters, duplicate
directory accounts, reachability for results, the email template's help
contact. Segment 20E rung 4b, moved unchanged from
``validation.py``.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import (
    Observer,
    Reviewee,
    Reviewer,
    ReviewSession,
)
from app.schemas.validation import Severity, ValidationIssue
from app.services.csv_imports import is_comparable_identity
from app.services.email_identity import normalize_email, normalize_object_id
from app.services.participants import is_email_identified
from app.services.validation._inputs import (
    ValidationInputs,
)

# --------------------------------------------------------------------------- #
# Individual rule check functions
# --------------------------------------------------------------------------- #


def _check_session_no_name(
    db: Session,
    review_session: ReviewSession,
    inputs: ValidationInputs,
) -> Iterable[ValidationIssue]:
    if not review_session.name:
        yield ValidationIssue(
            severity=Severity.error,
            source="session",
            field="name",
            message="Session has no name",
        )


def _check_session_no_code(
    db: Session,
    review_session: ReviewSession,
    inputs: ValidationInputs,
) -> Iterable[ValidationIssue]:
    if not review_session.code:
        yield ValidationIssue(
            severity=Severity.error,
            source="session",
            field="code",
            message="Session has no code",
        )


def _check_session_end_passed(
    db: Session,
    review_session: ReviewSession,
    inputs: ValidationInputs,
) -> Iterable[ValidationIssue]:
    """The review's end has passed before it opens (segment 14E): End, or
    with no End, Release from (``session_lifecycle.review_end``). The
    end closes the session, so activating would close it at once."""
    from app.services import session_lifecycle as lifecycle

    if review_session.status not in ("draft", "validated"):
        return
    which = "End" if review_session.deadline is not None else "Release responses from"
    field = "deadline" if review_session.deadline is not None else "responses_release_at"
    if lifecycle.deadline_has_passed(review_session):
        yield ValidationIssue(
            severity=Severity.error,
            source="session",
            field=field,
            message=(
                f"{which} has passed: activating would close the session at "
                f"once. Move it later, or clear it."
            ),
        )
        return
    # A scheduled Start at or after the end would open a session already
    # over: the scheduled activation would be skipped (round-3 read).
    end = lifecycle.review_end(review_session)
    start = review_session.scheduled_activate_at
    if end is not None and start is not None:
        start = start if start.tzinfo else start.replace(tzinfo=end.tzinfo)
        if start >= end:
            yield ValidationIssue(
                severity=Severity.error,
                source="session",
                field=field,
                message=(
                    f"{which} is not after Start: the session would close "
                    f"as it opened. Move it later, or move Start earlier."
                ),
            )


def _check_reviewers_empty(
    db: Session,
    review_session: ReviewSession,
    inputs: ValidationInputs,
) -> Iterable[ValidationIssue]:
    if not inputs.reviewers:
        yield ValidationIssue(
            severity=Severity.error,
            source="reviewers",
            message="No reviewers — import a reviewer CSV before activation",
        )


def _check_reviewers_duplicate_email(
    db: Session,
    review_session: ReviewSession,
    inputs: ValidationInputs,
) -> Iterable[ValidationIssue]:
    by_email: dict[str, list[Reviewer]] = {}
    for r in inputs.reviewers:
        by_email.setdefault(normalize_email(r.email), []).append(r)
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


def _check_observers_duplicate_email(
    db: Session,
    review_session: ReviewSession,
    inputs: ValidationInputs,
) -> Iterable[ValidationIssue]:
    """The backstop reviewers and reviewees have had all along.

    Observers carry the only DB-level uniqueness of the three rosters
    (``uq_observer_session_email``), so a duplicate can only be a row
    that predates the constraint or one that arrived by a path going
    around the services. That is the point rather than an argument
    against the rule: the Validate page's job is to report, and
    observers were the one roster it had nothing to report with
    (19Q Item 7).
    """
    # The roster arrives ordered by id from ``load_validation_inputs``,
    # which is what makes "the first duplicate's row" below a fact
    # rather than whatever the dialect happened to return. Where the
    # choice reaches operator-facing copy it is made in Python instead
    # — `csv_imports._identity_holders`.
    by_email: dict[str, list[Observer]] = {}
    for o in inputs.observers:
        by_email.setdefault(normalize_email(o.email), []).append(o)
    for email, dupes in by_email.items():
        if len(dupes) > 1:
            yield ValidationIssue(
                severity=Severity.error,
                source="observers",
                field="email",
                message=f"Duplicate observer email '{email}' ({len(dupes)} rows)",
                # First duplicate's row is the deep-link target.
                fix_anchor=f"#observer-row-{dupes[0].id}",
            )


# --------------------------------------------------------------------------- #
# Cross-roster identity (19Q Item 7)
# --------------------------------------------------------------------------- #
#
# One mailbox under two names across two rosters. The create / edit
# services and all three CSV importers refuse such a pair from rung 1
# on (``csv_imports.cross_table_identity_conflict``); these rules are
# what finds the pairs that were already in the session when they
# started refusing.
#
# Three registered rules over one generator rather than one rule with
# a session-wide source: the operator fixes the conflict on a roster
# page, so each side of it needs that page's ``fix_url`` and its own
# row anchor. A single rule carries one ``fix_url`` for every issue it
# emits, which would send half of them to the wrong page.


_CROSS_ROSTER_WHY = (
    "The same mailbox under two different names is one person "
    "recorded twice, and nothing downstream can tell which "
    "spelling is right: results, collation, and the reviewer's own "
    "surface all key on the email. Reviewer / reviewee overlap "
    "itself is legitimate and stays so — a self-review is exactly "
    "that — as long as the name agrees. Fix whichever row has the "
    "name wrong."
)

# ``(source, ValidationInputs roster attribute, identifier attribute,
# name attribute, anchor prefix)`` in the order the Validate page reads
# best: reviewers, reviewees, observers.
_ROSTER_IDENTITY_FIELDS: tuple[
    tuple[str, str, str, str, str], ...
] = (
    ("reviewers", "reviewers", "email", "name", "reviewer-row"),
    (
        "reviewees",
        "reviewees",
        "email_or_identifier",
        "name",
        "reviewee-row",
    ),
    ("observers", "observers", "email", "display_name", "observer-row"),
)

# Singular labels for the message; "reviewers" reads wrong inside
# "… as a reviewers".
_ROSTER_SINGULAR = {
    "reviewers": "reviewer",
    "reviewees": "reviewee",
    "observers": "observer",
}


@dataclass(frozen=True)
class _IdentityHolder:
    """One roster row that names a mailbox."""

    source: str
    row_id: int
    name: str
    anchor_prefix: str
    #: The column the conflict is in, rendered to the operator as a
    #: `<code>` chip. Reviewees do not have an `email` column, and the
    #: sibling `reviewees.duplicate_id` rule names `email_or_identifier`
    #: — one rule in the same section must not name a column the roster
    #: does not have.
    field: str


def _identity_holders_by_email(
    inputs: ValidationInputs,
) -> dict[str, list[_IdentityHolder]]:
    """Every named roster row in the session, keyed by normalized email.

    Rows that cannot disagree with anything are left out by
    ``csv_imports.is_comparable_identity`` — the same predicate the
    write guards apply, called rather than restated, because a rule
    with two homes is the defect this item is fixing one level up.

    The three rosters come from ``ValidationInputs``, already ordered
    by id, so this reads no database of its own — it was the largest
    repeat in the run, pulling all three rosters once per cross-roster
    rule.
    """
    holders: dict[str, list[_IdentityHolder]] = {}
    for source, roster_attr, id_attr, name_attr, anchor_prefix in (
        _ROSTER_IDENTITY_FIELDS
    ):
        for row in getattr(inputs, roster_attr):
            identifier = getattr(row, id_attr) or ""
            name = getattr(row, name_attr) or ""
            if not is_comparable_identity(identifier, name):
                continue
            holders.setdefault(normalize_email(identifier), []).append(
                _IdentityHolder(
                    source=source,
                    row_id=row.id,
                    name=name,
                    anchor_prefix=anchor_prefix,
                    field=id_attr,
                )
            )
    return holders


def _cross_roster_identity_issues(
    inputs: ValidationInputs, source: str
) -> Iterable[ValidationIssue]:
    """One issue per ``source`` row whose name another roster disagrees with.

    Disagreement is exact on the stored (already-trimmed) name — the
    comparison rung 1's guards make, chosen rather than inherited
    (19Q Item 7, open question 2). Two rows in the *same* roster are
    left to that roster's ``duplicate_*`` rule, so a within-roster
    duplicate is not reported twice.
    """
    for email, holders in sorted(_identity_holders_by_email(inputs).items()):
        for holder in holders:
            if holder.source != source:
                continue
            others = [
                other
                for other in holders
                if other.source != holder.source and other.name != holder.name
            ]
            if not others:
                continue
            spelled = ", ".join(
                f"'{other.name}' as a "
                f"{_ROSTER_SINGULAR[other.source]}"
                for other in others
            )
            yield ValidationIssue(
                severity=Severity.error,
                source=source,
                field=holder.field,
                message=(
                    f"'{email}' is '{holder.name}' here, but {spelled}. "
                    "One mailbox, one name — fix whichever row is wrong."
                ),
                fix_anchor=f"#{holder.anchor_prefix}-{holder.row_id}",
            )


def _check_reviewers_cross_roster_identity(
    db: Session,
    review_session: ReviewSession,
    inputs: ValidationInputs,
) -> Iterable[ValidationIssue]:
    return _cross_roster_identity_issues(inputs, "reviewers")


def _check_reviewees_cross_roster_identity(
    db: Session,
    review_session: ReviewSession,
    inputs: ValidationInputs,
) -> Iterable[ValidationIssue]:
    return _cross_roster_identity_issues(inputs, "reviewees")


def _check_observers_cross_roster_identity(
    db: Session,
    review_session: ReviewSession,
    inputs: ValidationInputs,
) -> Iterable[ValidationIssue]:
    return _cross_roster_identity_issues(inputs, "observers")


def _check_reviewees_empty(
    db: Session,
    review_session: ReviewSession,
    inputs: ValidationInputs,
) -> Iterable[ValidationIssue]:
    if not inputs.reviewees:
        yield ValidationIssue(
            severity=Severity.error,
            source="reviewees",
            message="No reviewees — import a reviewee CSV before activation",
        )


def _check_reviewees_duplicate_id(
    db: Session,
    review_session: ReviewSession,
    inputs: ValidationInputs,
) -> Iterable[ValidationIssue]:
    by_ident: dict[str, list[Reviewee]] = {}
    for r in inputs.reviewees:
        by_ident.setdefault(normalize_email(r.email_or_identifier), []).append(r)
    for ident, dupes in by_ident.items():
        if len(dupes) > 1:
            yield ValidationIssue(
                severity=Severity.error,
                source="reviewees",
                field="email_or_identifier",
                message=f"Duplicate reviewee identifier '{ident}' ({len(dupes)} rows)",
                fix_anchor=f"#reviewee-row-{dupes[0].id}",
            )


def _duplicate_accounts(
    rows: Iterable[Any], *, source: str, label: str, address_attr: str
) -> Iterable[ValidationIssue]:
    """Two or more active rows in one roster bound to one directory
    account (segment 19Z): one person entered twice, by mail and by
    sign-in name, since each address passes the duplicate-address rule.
    The gates and the dashboard take the lowest id, so the warning names
    the rows rather than blocking; an inactive row is not counted. Rows
    arrive ordered by id, so the first is the one that answers."""
    by_account: dict[str, list[Any]] = {}
    for row in rows:
        if row.status == "active" and row.directory_object_id:
            by_account.setdefault(normalize_object_id(row.directory_object_id), []).append(row)
    for dupes in by_account.values():
        if len(dupes) > 1:
            addresses = ", ".join(f"'{getattr(row, address_attr)}'" for row in dupes)
            yield ValidationIssue(
                severity=Severity.warning,
                source=source,
                field=address_attr,
                message=(
                    f"{len(dupes)} {label} rows are one directory account: {addresses}"
                ),
                fix_anchor=f"#{label}-row-{dupes[0].id}",
            )


def _check_reviewers_duplicate_account(
    db: Session, review_session: ReviewSession, inputs: ValidationInputs
) -> Iterable[ValidationIssue]:
    return _duplicate_accounts(inputs.reviewers, source="reviewers", label="reviewer", address_attr="email")


def _check_reviewees_duplicate_account(
    db: Session, review_session: ReviewSession, inputs: ValidationInputs
) -> Iterable[ValidationIssue]:
    return _duplicate_accounts(
        inputs.reviewees, source="reviewees", label="reviewee", address_attr="email_or_identifier"
    )


def _check_observers_duplicate_account(
    db: Session, review_session: ReviewSession, inputs: ValidationInputs
) -> Iterable[ValidationIssue]:
    return _duplicate_accounts(inputs.observers, source="observers", label="observer", address_attr="email")


def _check_reviewees_mirror_drift(
    db: Session,
    review_session: ReviewSession,
    inputs: ValidationInputs,
) -> Iterable[ValidationIssue]:
    """Under symmetric review, every reviewer has exactly one reviewee
    linked to it (``mirrors_reviewer_id``), every reviewee is linked to a
    reviewer on the roster, and each linked pair agrees on every mirrored
    field (``symmetric_review.MIRRORED_FIELDS``, compared as the sync
    writes them). Only a writer that skipped the sync leaves it otherwise
    (segment 20F). Nothing to check with the mode off."""
    if not review_session.symmetric_review:
        return
    from app.services.symmetric_review import MIRRORED_FIELDS

    reviewers = {r.id: r for r in inputs.reviewers}
    linked: dict[int, list[Reviewee]] = {}
    for reviewee in inputs.reviewees:
        if reviewee.mirrors_reviewer_id in reviewers:
            linked.setdefault(reviewee.mirrors_reviewer_id, []).append(reviewee)
        else:
            yield ValidationIssue(
                severity=Severity.error,
                source="reviewees",
                field="mirrors_reviewer_id",
                message=(
                    f"Reviewee '{reviewee.email_or_identifier}' mirrors no reviewer "
                    "on the roster"
                ),
            )
    for reviewer in inputs.reviewers:
        mirrors = linked.get(reviewer.id, [])
        if len(mirrors) != 1:
            yield ValidationIssue(
                severity=Severity.error,
                source="reviewees",
                field="mirrors_reviewer_id",
                message=(
                    f"Reviewer '{reviewer.email}' has no mirrored reviewee"
                    if not mirrors
                    else f"Reviewer '{reviewer.email}' is mirrored by {len(mirrors)} reviewees"
                ),
                fix_anchor=f"#reviewer-row-{reviewer.id}",
            )
            continue
        differing = [
            reviewee_field
            for reviewee_field, reviewer_field in MIRRORED_FIELDS
            if getattr(mirrors[0], reviewee_field) != getattr(reviewer, reviewer_field)
        ]
        if differing:
            yield ValidationIssue(
                severity=Severity.error,
                source="reviewees",
                field=differing[0],
                message=(
                    f"Reviewee '{mirrors[0].email_or_identifier}' differs from its "
                    f"reviewer '{reviewer.email}' in {', '.join(differing)}"
                ),
                fix_anchor=f"#reviewer-row-{reviewer.id}",
            )


_MIRROR_DRIFT_WHY = (
    "Under symmetric review the Reviewees roster is a copy of the "
    "Reviewers roster, kept in step on every reviewer save. A reviewee "
    "missing, extra or different from its reviewer means a change "
    "reached the reviewers without the copy, so assignments and results "
    "would follow the wrong roster. Saving any reviewer row on the "
    "Reviewers page brings the copy back into step."
)


_DUPLICATE_ACCOUNT_WHY = (
    "A roster address is resolved through the directory at upload, and a "
    "row bound to an account admits only that account. Two rows on one "
    "account are one person entered twice, by mail and by sign-in name; "
    "the person sees the lower row only. Non-blocking: remove or "
    "deactivate the row that should not be there."
)


def _check_reviewees_unreachable_for_results(
    db: Session,
    review_session: ReviewSession,
    inputs: ValidationInputs,
) -> Iterable[ValidationIssue]:
    """W8 — soft warning when any reviewee's ``email_or_identifier``
    isn't a deliverable email. The ``/me/sessions/{id}/results``
    surface gates on ``is_email_identified`` (W2 dependency); a
    reviewee with a non-email handle has no inbox to authenticate
    against and so won't see the responses written about them.

    Non-blocking — the operator may have non-email reviewees on
    purpose (anonymous IDs for analysis-only). The warning just
    surfaces the implication so they decide knowingly."""
    unreachable = [
        r for r in inputs.active_reviewees if not is_email_identified(r)
    ]
    if not unreachable:
        return
    noun = "reviewee" if len(unreachable) == 1 else "reviewees"
    yield ValidationIssue(
        severity=Severity.warning,
        source="reviewees",
        field="email_or_identifier",
        message=(
            f"{len(unreachable)} {noun} cannot view their results: "
            "identifier is not an email so /me/sessions/.../results "
            "stays unreachable for them."
        ),
        fix_anchor=f"#reviewee-row-{unreachable[0].id}",
    )


def _check_email_template_no_help_contact(
    db: Session,
    review_session: ReviewSession,
    inputs: ValidationInputs,
) -> Iterable[ValidationIssue]:
    if not (review_session.help_contact and review_session.help_contact.strip()):
        yield ValidationIssue(
            severity=Severity.info,
            source="email_template",
            message=(
                "No help contact set — the default emails omit their "
                "'Questions? Contact …' line"
            ),
        )
