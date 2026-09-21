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

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Instrument,
    InstrumentDisplayField,
    InstrumentResponseField,
    Observer,
    Reviewee,
    Reviewer,
    ReviewSession,
)
from app.schemas.validation import Severity, ValidationIssue
from app.services.csv_imports import is_comparable_identity
from app.services.email_identity import normalize_email
from app.services.instruments import _instrument_label
from app.services.participants import is_email_identified


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
    check: Callable[
        [Session, ReviewSession, "ValidationInputs"],
        Iterable[ValidationIssue],
    ]


@dataclass(frozen=True)
class ValidationInputs:
    """What one report run loads once, for every check to read.

    Twenty-two checks each loading for themselves is how two of them
    come to disagree about what "the session's instruments" means. It
    is also why one run issued 43 queries for 21 distinct reads
    (19R Item 5; ``guide/app_responsiveness.md`` Finding 6).

    **Measured, not guessed.** This carries exactly what more than one
    check loaded: the instrument list, the three rosters, the roster
    non-empty probes (now ``bool()`` over a list already loaded), the
    per-instrument response-field / visible-response-field /
    display-field presence, and ``included_count_per_instrument``. A
    load only one check makes stays in that check.

    **Per run, never a cache.** :func:`validate_session_setup` builds
    one of these per call and drops it. A check must not see a roster
    older than the request that asked.
    """

    instruments: tuple[Instrument, ...]
    reviewers: tuple[Reviewer, ...]
    reviewees: tuple[Reviewee, ...]
    observers: tuple[Observer, ...]
    #: Instrument ids with at least one ``InstrumentResponseField`` row.
    instruments_with_response_fields: frozenset[int]
    #: …with at least one ``visible=True`` response field.
    instruments_with_visible_response_fields: frozenset[int]
    #: …with at least one ``InstrumentDisplayField`` row.
    instruments_with_display_fields: frozenset[int]
    included_count_by_instrument: Mapping[int, int]

    @property
    def active_reviewees(self) -> tuple[Reviewee, ...]:
        """The roster filtered in Python rather than re-queried."""
        return tuple(r for r in self.reviewees if r.status == "active")


def load_validation_inputs(
    db: Session, review_session: ReviewSession
) -> ValidationInputs:
    """Load everything more than one registered rule needs, once.

    The three rosters are ordered by id so that "the first duplicate's
    row" in a ``fix_anchor`` is a fact rather than whatever the dialect
    happened to return — SQLite grants an unordered ``SELECT`` the
    insertion order anyway, so no test fails if the clause goes, which
    is exactly why it is stated here once instead of per rule.

    The per-instrument presence sets join through
    ``Instrument.session_id`` rather than an ``IN`` over instrument
    ids. The id list is short today, but ``IN`` is the shape that hits
    SQLite's 999-variable ceiling once it is not.
    """
    # Local import: ``assignments`` imports this module's siblings.
    from app.services import assignments as assignments_service

    def _instrument_ids(
        field_model: type[InstrumentResponseField]
        | type[InstrumentDisplayField],
        *extra: object,
    ) -> frozenset[int]:
        stmt = (
            select(field_model.instrument_id)
            .join(Instrument, Instrument.id == field_model.instrument_id)
            .where(Instrument.session_id == review_session.id)
            .distinct()
        )
        for clause in extra:
            stmt = stmt.where(clause)
        return frozenset(row[0] for row in db.execute(stmt).all())

    return ValidationInputs(
        instruments=tuple(
            db.execute(
                select(Instrument)
                .where(Instrument.session_id == review_session.id)
                .order_by(Instrument.order, Instrument.id)
            ).scalars()
        ),
        reviewers=tuple(
            db.execute(
                select(Reviewer)
                .where(Reviewer.session_id == review_session.id)
                .order_by(Reviewer.id)
            ).scalars()
        ),
        reviewees=tuple(
            db.execute(
                select(Reviewee)
                .where(Reviewee.session_id == review_session.id)
                .order_by(Reviewee.id)
            ).scalars()
        ),
        observers=tuple(
            db.execute(
                select(Observer)
                .where(Observer.session_id == review_session.id)
                .order_by(Observer.id)
            ).scalars()
        ),
        instruments_with_response_fields=_instrument_ids(
            InstrumentResponseField
        ),
        instruments_with_visible_response_fields=_instrument_ids(
            InstrumentResponseField, InstrumentResponseField.visible.is_(True)
        ),
        instruments_with_display_fields=_instrument_ids(
            InstrumentDisplayField
        ),
        included_count_by_instrument=(
            assignments_service.included_count_per_instrument(
                db, review_session.id
            )
        ),
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


def _check_instruments_no_fields(
    db: Session,
    review_session: ReviewSession,
    inputs: ValidationInputs,
) -> Iterable[ValidationIssue]:
    for instrument in inputs.instruments:
        if instrument.id not in inputs.instruments_with_response_fields:
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
    db: Session,
    review_session: ReviewSession,
    inputs: ValidationInputs,
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
    if sum(inputs.included_count_by_instrument.values()) == 0:
        yield ValidationIssue(
            severity=Severity.warning,
            source="assignments",
            message=(
                "No included assignment rows on any instrument — "
                "reviewers will see an empty surface"
            ),
        )


def _check_assignments_reviewer_missing(
    db: Session,
    review_session: ReviewSession,
    inputs: ValidationInputs,
) -> Iterable[ValidationIssue]:
    """Single-instrument sessions: every reviewer must appear on at
    least one ``Assignment`` row.

    Skipped when ``assignment_mode is None`` — a session that has
    never been Generated has no actionable per-reviewer breakdown,
    and surfacing every-reviewer-missing on top of the
    ``assignments.no_included_pairs`` warning would double up the
    noise. (``instruments.no_rule_pinned`` was named here too
    until Wave 5 PR 5.3 retired it; it is inert and raises
    nothing.) Also skipped on multi-instrument sessions — the
    per-instrument rule
    (``assignments.reviewer_missing_for_instrument``) carries the
    breakdown there.
    """
    if review_session.assignment_mode is None:
        return
    if len(inputs.instruments) != 1:
        return
    reviewer_ids_with_assignments = {
        row[0]
        for row in db.execute(
            select(Assignment.reviewer_id)
            .where(Assignment.session_id == review_session.id)
            .distinct()
        ).all()
    }
    for reviewer in inputs.reviewers:
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
    db: Session,
    review_session: ReviewSession,
    inputs: ValidationInputs,
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
    if len(inputs.instruments) <= 1:
        return
    # Per-instrument reviewer-presence map keyed by instrument_id.
    presence: dict[int, set[int]] = {
        i.id: set() for i in inputs.instruments
    }
    for instrument_id, reviewer_id in db.execute(
        select(Assignment.instrument_id, Assignment.reviewer_id)
        .where(Assignment.session_id == review_session.id)
        .distinct()
    ).all():
        if instrument_id in presence:
            presence[instrument_id].add(reviewer_id)
    for instrument in inputs.instruments:
        in_use = presence[instrument.id]
        if not in_use:
            # Sibling instrument_empty rule covers this case.
            continue
        for reviewer in inputs.reviewers:
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
    db: Session,
    review_session: ReviewSession,
    inputs: ValidationInputs,
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
    if len(inputs.instruments) <= 1:
        return
    instrument_ids_with_rows = {
        row[0]
        for row in db.execute(
            select(Assignment.instrument_id)
            .where(Assignment.session_id == review_session.id)
            .distinct()
        ).all()
    }
    for instrument in inputs.instruments:
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
    db: Session,
    review_session: ReviewSession,
    inputs: ValidationInputs,
) -> Iterable[ValidationIssue]:
    """Wave 5 PR 5.3 — retired. Pre-PR-5.3 the rule fired on legacy
    instruments with NULL ``rule_set_id``. With the legacy /
    new-model split collapsed, every instrument now defaults to
    Full Matrix on untouched Band 1 (Wave 4 PR 1), so a NULL
    ``rule_set_id`` is never "not set up." The
    ``instruments.no_visible_response_fields`` rule still covers
    the readiness gap (zero visible response fields). The rule
    key stays registered so audit history remains addressable.
    """
    return
    yield  # pragma: no cover — make this an Iterable


def _check_new_model_no_visible_response_fields(
    db: Session,
    review_session: ReviewSession,
    inputs: ValidationInputs,
) -> Iterable[ValidationIssue]:
    """Warning per new-model instrument with no ``visible=True``
    :class:`InstrumentResponseField` rows once the session has
    reviewers + reviewees.

    Without a visible response field, the reviewer surface renders
    zero rows on the instrument's tab even though assignments exist
    (Wave 4 PR 2 — replaces the rule-set-pinned readiness gap for
    new-model instruments).
    """
    if not inputs.reviewers or not inputs.reviewees:
        return
    for instrument in inputs.instruments:
        if instrument.id in inputs.instruments_with_visible_response_fields:
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
    db: Session,
    review_session: ReviewSession,
    inputs: ValidationInputs,
) -> Iterable[ValidationIssue]:
    """Warning per instrument whose materialized rows have fallen out of
    step with what the engine would produce now.

    The criterion is the first sentence: a reconcile run would insert
    or delete at least one pair. The two situations this rule's ``why``
    names are the ones an operator recognises — the pinned rule
    changed, or the rosters or relationships moved after Generate —
    but they are not exhaustive, since the diff also reads
    ``group_kind`` and the session's self-review setting.

    The verdict is the engine's own diff
    (``assignments.staleness_by_instrument``). Since 19R Item 2 that
    diff may be served from a stamped cache rather than recomputed, so
    it agrees with what Generate would do **under the conditions**
    ``spec/assignments.md`` § *Staleness* states — the stamp covering
    every input the diff reads, and Generate writing the fresh verdict
    through. Stating it unconditionally is what that item's close
    deliberately stopped doing.

    **An instrument that has never generated is not flagged**, and the
    engine decides that rather than this check: staleness means
    materialized rows that have fallen out of step, which needs rows to
    have been materialized. An always-stale badge on a fresh session is
    the failure mode that retired the previous signal. The Workflow
    card's Generate step and the ``assignments.*`` empty rules carry
    that case instead.

    **This rule was a registered no-op between Wave 5 PR 5.1 and Segment
    19N.** Its predecessor compared per-rule eligible counts via a helper
    that retired with the operator-library tier, and the replacement was
    judged unnecessary because "the Workflow card + Generate button
    already cover the *operator pinned a rule but never generated*
    case" — which is not one of the two situations the ``why`` names, so
    both of them were covered by nothing while the rule stayed in the
    registry with a fix link. *A check that returns nothing reports a
    clean bill on exactly the thing it exists to catch*, which is worse
    than its absence, because the operator reads the silence as an
    answer.
    """
    from app.services import assignments as assignments_service

    state_by_instrument = assignments_service.staleness_by_instrument(
        db, review_session
    )
    if not any(state.stale for state in state_by_instrument.values()):
        return
    for instrument in inputs.instruments:
        state = state_by_instrument.get(instrument.id)
        if state is None or not state.stale:
            continue
        yield ValidationIssue(
            severity=Severity.warning,
            source="instruments",
            message=(
                f"Instrument {_instrument_label(instrument)!r} would "
                f"change if assignments were regenerated — re-Generate "
                f"to refresh the pairs"
            ),
            fix_anchor=f"#instrument-{instrument.id}",
        )


def _check_instruments_zero_included(
    db: Session,
    review_session: ReviewSession,
    inputs: ValidationInputs,
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

    # Only one check needs the generated counts, so they stay a live
    # read here rather than joining `ValidationInputs`. Note the
    # asymmetry that creates: `generated` is read now, `included` was
    # snapshotted at the top of the run. They agree because a report
    # run never touches `assignments` rows — the one write in it is
    # `staleness_by_instrument` caching its verdict onto instruments —
    # and a check that broke that would have to say so here.
    generated_by_instrument = assignments_service.existing_count_per_instrument(
        db, review_session.id
    )
    for instrument in inputs.instruments:
        generated = generated_by_instrument.get(instrument.id, 0)
        included = inputs.included_count_by_instrument.get(instrument.id, 0)
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
    db: Session,
    review_session: ReviewSession,
    inputs: ValidationInputs,
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
    db: Session,
    review_session: ReviewSession,
    inputs: ValidationInputs,
) -> Iterable[ValidationIssue]:
    for instrument in inputs.instruments:
        if instrument.id not in inputs.instruments_with_response_fields:
            # The no_fields rule already covers this; skip.
            continue
        if instrument.id not in inputs.instruments_with_display_fields:
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
    # 18R Item 4 Slice 5 — the Edit page is retired from the UI; session
    # config is edited in place on Session Home's Session details card.
    # "Fix" links open that card in edit mode.
    return f"/operator/sessions/{s.id}?editing=1#session-config"


def _reviewers_url(s: ReviewSession) -> str:
    return f"/operator/sessions/{s.id}/reviewers"


def _reviewees_url(s: ReviewSession) -> str:
    return f"/operator/sessions/{s.id}/reviewees"


def _observers_url(s: ReviewSession) -> str:
    return f"/operator/sessions/{s.id}/observers"


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
        key="reviewees.unreachable_for_results",
        source="reviewees",
        severity=Severity.warning,
        why=(
            "The /me/sessions/{id}/results surface gates on the "
            "reviewee's identifier being a deliverable email — "
            "without one, the reviewee can't authenticate and so "
            "won't see the responses written about them. Non-blocking "
            "in case the operator is intentionally using anonymous "
            "identifiers (analysis-only sessions); the warning just "
            "names the implication."
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
            "Retired in Wave 5 PR 5.3 and inert by design — this "
            "rule raises no findings, so no operator reads this "
            "copy. A NULL ``rule_set_id`` is never \"not set up\": "
            "every instrument defaults to the synthetic Full "
            "Matrix on untouched Band 1. "
            "``instruments.no_visible_response_fields`` covers the "
            "readiness gap. The key stays registered so audit "
            "history remains addressable "
            "(``spec/validate_page.md``)."
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
