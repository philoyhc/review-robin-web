"""View-shape adapters for operator templates.

Translate domain objects into row tuples / dataclasses that templates
iterate over. Service modules stay business-logic-only; templates stay
markup-only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from datetime import datetime

from app.db.models import (
    EmailOutbox,
    Instrument,
    InstrumentResponseField,
    Invitation,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from app.services import (
    assignments,
    csv_imports,
    instruments as instruments_service,
    invitations as invitations_service,
    monitoring,
    responses as responses_service,
    session_lifecycle as lifecycle,
)
from app.web import breadcrumbs


@dataclass
class SetupRow:
    label: str
    value: str
    manage_url: str
    manage_disabled: bool = False
    manage_disabled_reason: str | None = None


def build_setup_rows(
    db: Session, review_session: ReviewSession
) -> list[SetupRow]:
    """Rows for the Session setup card on session detail."""
    sid = review_session.id
    reviewer_count = csv_imports.existing_reviewer_count(db, sid)
    reviewee_count = csv_imports.existing_reviewee_count(db, sid)
    assignment_count = assignments.existing_count(db, sid)
    instruments = list(
        db.execute(
            select(Instrument).where(Instrument.session_id == sid)
        ).scalars()
    )
    instrument_count = len(instruments)
    if instrument_count == 0:
        instruments_value = "Number of instruments: 0"
    else:
        any_open = any(i.accepting_responses for i in instruments)
        all_open = all(i.accepting_responses for i in instruments)
        if all_open:
            status_word = "Open"
        elif not any_open:
            status_word = "Closed"
        else:
            status_word = "Mixed"
        instruments_value = (
            f"Number of instruments: {instrument_count}, Status: {status_word}"
        )

    return [
        SetupRow(
            label="Reviewers",
            value=f"Number of reviewers: {reviewer_count}",
            manage_url=f"/operator/sessions/{sid}/reviewers",
        ),
        SetupRow(
            label="Reviewees",
            value=f"Number of reviewees: {reviewee_count}",
            manage_url=f"/operator/sessions/{sid}/reviewees",
        ),
        SetupRow(
            label="Assignments",
            value=f"Number of assignments: {assignment_count}",
            manage_url=f"/operator/sessions/{sid}/assignments",
        ),
        SetupRow(
            label="Instruments",
            value=instruments_value,
            manage_url=f"/operator/sessions/{sid}/instruments",
        ),
        SetupRow(
            label="Email Invites",
            value="—",
            manage_url=f"/operator/sessions/{sid}/setupinvite",
        ),
    ]


@dataclass
class SessionStatusPills:
    """Counts shown on the standardized session-level status row
    (rendered by ``partials/session_setup_status_row.html``). The
    same five numbers / flags appear on every session-scoped page
    so the chrome reads as a single contract."""

    reviewer_count: int
    reviewee_count: int
    assignment_count: int
    instrument_count: int
    email_invites_set_up: bool


@dataclass(frozen=True)
class InstrumentHeading:
    """Title + optional subtitle for the per-instrument heading card.

    Title lands on the H2; subtitle on a `.muted` body-weight `<p>`
    below it inside `.card.rs-instrument-card`, which sits in column 1
    of the per-instrument intro grid (`.rs-intro-grid`). Either or
    both can be ``None`` — the template only renders the heading card
    when ``title`` is truthy.

    Composition rules per `spec/reviewer-surface.md` "Above the table
    — heading + help block":

    | total_count | short_label | description | title | subtitle |
    |---|---|---|---|---|
    | >1 | set     | set       | "Page #{N}: {short_label}" | description |
    | >1 | set     | unset     | "Page #{N}: {short_label}" | None |
    | >1 | unset   | set       | "Page #{N}"                | description |
    | >1 | unset   | unset     | "Page #{N}"                | None |
    | 1  | set     | set       | "{short_label}"            | description |
    | 1  | set     | unset     | "{short_label}"            | None |
    | 1  | unset   | set       | "{description}" *          | None *     |
    | 1  | unset   | unset     | None                       | None |

    \\* The single-instrument-only-description row preserves the
    legacy heading behaviour (description renders as the H2 text)
    so operators who haven't migrated to ``short_label`` yet don't
    silently lose their per-instrument context. The spec's strict
    reading was "no heading; description shown elsewhere", but
    there's no other display path for ``Instrument.description``
    today; preserving it here is a small spec deviation in service
    of operator continuity.
    """

    title: str | None
    subtitle: str | None


def page_button_label(instrument: Instrument, position: int) -> str:
    """Label for a Page N button on the reviewer surface's action row.

    Returns ``"Page #{N}: {short_label}"`` when the operator has set
    ``Instrument.short_label`` (32-char ceiling enforced at the
    schema layer per Segment 11L); falls back to bare ``"Page #{N}"``
    otherwise.
    """
    short = (instrument.short_label or "").strip()
    if short:
        return f"Page #{position}: {short}"
    return f"Page #{position}"


def instrument_heading(
    *, instrument: Instrument, position: int, total_count: int
) -> InstrumentHeading:
    """Build the per-instrument heading title + subtitle for the
    reviewer surface, per the composition table on
    :class:`InstrumentHeading`.
    """
    short = (instrument.short_label or "").strip()
    desc = (instrument.description or "").strip() or None
    if total_count == 1:
        if short:
            return InstrumentHeading(title=short, subtitle=desc)
        if desc:
            # Legacy behaviour preserved — see the docstring's note.
            return InstrumentHeading(title=desc, subtitle=None)
        return InstrumentHeading(title=None, subtitle=None)
    # Multi-instrument: position prefix is the safety-net default.
    if short:
        return InstrumentHeading(title=f"Page #{position}: {short}", subtitle=desc)
    return InstrumentHeading(title=f"Page #{position}", subtitle=desc)


@dataclass(frozen=True)
class PageButton:
    """View-shape for a Page button on the reviewer-surface action row."""

    position: int
    label: str
    href: str
    is_current: bool


def placeholder_for_field(field: InstrumentResponseField) -> str:
    """Short hint shown inside the input box when empty, so reviewers
    know what shape a value should take. Mirrors the RTD's validation
    block; returns ``""`` for List rows or when the validation block is
    incomplete (e.g. an Integer RTD missing ``step``)."""
    validation = field.validation or {}
    data_type = field.data_type
    if data_type == "String":
        max_length = validation.get("max_length")
        if max_length is None:
            return ""
        min_length = validation.get("min_length") or 0
        return f"{int(min_length)} to {int(max_length)} char"
    if data_type in ("Integer", "Decimal"):
        min_ = validation.get("min")
        max_ = validation.get("max")
        step = validation.get("step")
        if min_ is None or max_ is None or step is None:
            return ""
        if data_type == "Integer":
            return (
                f"{int(min_)} to {int(max_)}, steps of {int(step)}"
            )
        return f"{min_:.1f} to {max_:.1f}, steps of {step:.1f}"
    return ""


def constraint_summary_for_field(field: InstrumentResponseField) -> str:
    """Short ``min-max[, steps of step]`` summary used in the
    above-table constraint row on the reviewer surface. Distinct from
    ``placeholder_for_field`` (``a to b``) — this one uses the dash
    notation requested for the summary line. Returns ``""`` when the
    validation block is incomplete or absent."""
    validation = field.validation or {}
    data_type = field.data_type
    if data_type == "String":
        max_length = validation.get("max_length")
        if max_length is None:
            return ""
        min_length = validation.get("min_length") or 0
        return f"{int(min_length)}-{int(max_length)} char"
    if data_type in ("Integer", "Decimal"):
        min_ = validation.get("min")
        max_ = validation.get("max")
        step = validation.get("step")
        if min_ is None or max_ is None or step is None:
            return ""
        if data_type == "Integer":
            return f"{int(min_)}-{int(max_)}, steps of {int(step)}"
        return f"{min_:.1f}-{max_:.1f}, steps of {step:.1f}"
    # List rows are omitted from the constraint summary — the
    # ``<select>`` already constrains the choice in the input itself.
    return ""


def _bulk_state(values: list[bool]) -> str:
    """Three-state value for a bulk toggle: ``all-on`` / ``all-off`` / ``mixed``."""
    if not values:
        return "all-off"
    on = sum(1 for v in values if v)
    if on == 0:
        return "all-off"
    if on == len(values):
        return "all-on"
    return "mixed"


def build_instruments_context(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    editing: int | None = None,
    saved: int | None = None,
    rtd_error: str | None = None,
    rtd_id: int | None = None,
    rf_save_error: str | None = None,
    editing_rtd_id: int | None = None,
    rtd_delete_blocked_id: int | None = None,
    rtd_delete_blocked_rfs: int | None = None,
    rtd_delete_blocked_instruments: int | None = None,
    rtd_delete_blocked_responses: int | None = None,
    rtd_delete_blocked_assignments: int | None = None,
    rtd_would_empty_id: int | None = None,
    rtd_would_empty_instruments: str | None = None,
) -> dict[str, Any]:
    """Build the template context for the operator instruments index.

    Runs the per-request idempotent display-field / RTD backfills
    (locked-row safety net + lazy seeds + stale-row prune + RTD seed),
    derives the editing-state machine, and packages the URL-driven
    error / cascade query params into the dict the template expects.
    Commits the backfill side-effects before returning so subsequent
    queries see the seeded rows.
    """
    instruments = list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars()
    )
    # Make sure every instrument has its locked Name / Email Display
    # Fields rows. The Alembic migration backfills existing instruments;
    # this is the per-request safety net for any sessions that slip
    # through (e.g. created before the migration ran).
    for instrument in instruments:
        instruments_service.ensure_locked_display_fields(
            db, instrument=instrument
        )
    # Prune Display Fields rows whose underlying data source no longer
    # has any populated value (locked Name / Email rows are exempt and
    # always kept). Runs before the lazy seeds so the canonical seed
    # order — reviewee.* before pair_context.* — falls out naturally:
    # any stale rows are gone, then the seeds append fresh in the
    # canonical sequence.
    instruments_service.prune_unpopulated_display_fields(db, review_session)
    # Per-request idempotent backfill of the lazy-seeded display
    # fields. The reviewee / assignment imports already trigger these
    # in the happy path; calling them on every GET catches sessions
    # whose roster or assignments were imported before the lazy-seed
    # logic landed (PR #203). Cheap — both helpers short-circuit when
    # there's nothing to seed.
    instruments_service.seed_display_fields_from_reviewees(db, review_session)
    instruments_service.seed_display_fields_from_assignments(db, review_session)
    # Idempotent per-request backfill of the seeded RTD catalog.
    # Existing sessions get the rows from the Slice 4a migration; this
    # call covers any session created without going through
    # ``ensure_default_instrument`` (e.g. raw fixtures in tests).
    instruments_service.ensure_default_response_type_definitions(
        db, review_session
    )
    db.commit()

    is_ready = lifecycle.is_ready(review_session)
    can_edit = not is_ready
    # State machine: ``?editing={instrument_id}`` opens that card for
    # editing. The yellow lock card on a ``ready`` session overrides
    # everything — every per-instrument card stays locked.
    editing_instrument_id = None if is_ready else editing
    # Slice 4d: the per-instrument editing state and the RTD editing
    # state are mutually exclusive — one editing context on the page
    # at a time. If both URL params are set (e.g. via a stale link),
    # the per-instrument card wins; the RTD card stays locked.
    effective_editing_rtd_id: int | None = None
    if not is_ready and editing_instrument_id is None:
        effective_editing_rtd_id = editing_rtd_id

    # "Saved" / "not saved" pill on each per-instrument card's status
    # sub-card. An instrument is "saved" if it has at least one audit
    # event indicating an operator-driven persistence of its field
    # tables (display fields saved via bulk save, edit, add, delete,
    # or move). Pure draft instruments — only seeded rows, never
    # touched — render as "not saved".
    instrument_saved_state = instruments_service.saved_state_for_session(
        db, session_id=review_session.id
    )
    rtds = instruments_service.get_session_rtds(
        db, session_id=review_session.id
    )

    rtd_delete_blocked = (
        {
            "id": rtd_delete_blocked_id,
            "response_field_count": rtd_delete_blocked_rfs or 0,
            "instrument_count": rtd_delete_blocked_instruments or 0,
            "response_count": rtd_delete_blocked_responses or 0,
            "assignment_count": rtd_delete_blocked_assignments or 0,
        }
        if rtd_delete_blocked_id is not None
        else None
    )
    rtd_would_empty = (
        {
            "id": rtd_would_empty_id,
            "instrument_numbers": [
                n for n in (rtd_would_empty_instruments or "").split(",") if n
            ],
        }
        if rtd_would_empty_id is not None
        else None
    )

    return {
        "user": user,
        "session": review_session,
        "status_pills": session_status_pills(db, review_session),
        "instruments": instruments,
        "is_ready": is_ready,
        "can_edit": can_edit,
        "bulk_accepting_state": _bulk_state(
            [i.accepting_responses for i in instruments]
        ),
        "bulk_visibility_state": _bulk_state(
            [i.responses_visible_when_closed for i in instruments]
        ),
        "editing_instrument_id": editing_instrument_id,
        "instrument_saved_state": instrument_saved_state,
        "saved_instrument_id": saved,
        "rtds": rtds,
        "rtd_error": rtd_error,
        "rtd_error_id": rtd_id,
        "rf_save_error": rf_save_error,
        "editing_rtd_id": effective_editing_rtd_id,
        "is_some_instrument_editing": editing_instrument_id is not None,
        "is_some_rtd_unlocked": effective_editing_rtd_id is not None,
        "rtd_delete_blocked": rtd_delete_blocked,
        "rtd_would_empty": rtd_would_empty,
        "breadcrumbs": breadcrumbs.operator_session_child(
            review_session, "Instruments"
        ),
    }


# ---------------------------------------------------------------------------
# Segment 11G PR A — Validate page view-shape adapter
# ---------------------------------------------------------------------------
#
# The Validate page is a read-only deep-dive into setup readiness. PR A
# replaces the thin issue list with a structured layout: a top
# **Readiness summary card** (verdict line + severity counts +
# last-validated marker + lifecycle-aware secondary line), a
# **Setup-coverage matrix** (per-entity inventory the operator scans
# at a glance — useful even when the issue list is empty), and the
# existing issue list partial.


@dataclass(frozen=True)
class SetupCoverageRow:
    """One row of the Setup-coverage matrix.

    ``label`` reads the row left-edge (e.g. "Reviewers"). ``status``
    is a short summary string (e.g. "8" or "Default (no overrides)" or
    "✓"). ``source`` matches the validation issue source slug so the
    matrix can link to the issue list section when issues exist for
    that source; ``None`` for rows that don't have a corresponding
    issue source (e.g. "Help contact"). ``error_count`` /
    ``warning_count`` come from the per-source issue tallies and drive
    the inline pill counts when nonzero."""

    label: str
    status: str
    source: str | None
    error_count: int = 0
    warning_count: int = 0


@dataclass(frozen=True)
class SeverityChip:
    """One row of the severity-filter chip strip on the Validate page.

    Rendered as an anchor link flipping ``?severity=`` to ``key``
    (or absent for ``key="all"``). The active chip carries
    ``aria-current="page"`` and a visual outline."""

    key: str  # "all" | "error" | "warning" | "info"
    label: str  # "All issues" | "Errors only" | "Warnings only" | "Info"
    count: int
    is_active: bool


@dataclass(frozen=True)
class IssueSourceGroup:
    """Per-source group on the issue list. ``count_summary`` is the
    inline summary line under the ``<h3>`` (e.g. "2 errors, 1
    warning") respecting the active severity filter."""

    source: str
    count_summary: str
    issues: list[Any]  # list[ValidationIssue], untyped to avoid circular import


@dataclass(frozen=True)
class ValidateContext:
    verdict_line: str
    """Page's at-a-glance verdict ("Ready to activate.", "Has 3
    errors.", "Ready to activate with 2 warnings.")"""
    verdict_class: str
    """``"verdict-clean"`` / ``"verdict-error"`` / ``"verdict-warn"``
    — drives the colour-coded accent on the readiness summary card."""
    error_count: int
    warning_count: int
    info_count: int
    last_validated_text: str
    """Today validation runs live on every GET. Renders as
    "Validated just now" — sets expectations that re-running is free
    and refresh-driven."""
    lifecycle_copy: str
    """Lifecycle-aware secondary line ("Activate from the Next Action
    card on Session Home.", etc.)"""
    setup_coverage: list[SetupCoverageRow]
    severity_filter: str
    """``"all"`` (no filter) / ``"error"`` / ``"warning"`` / ``"info"``"""
    severity_chips: list[SeverityChip]
    """The four-chip strip above the issue list."""
    issue_groups: list[IssueSourceGroup]
    """Pre-grouped issues respecting the severity filter; the partial
    iterates these instead of computing its own per-source split."""
    filtered_issue_count: int
    """Total issues *after* the filter is applied. Drives the
    issue-list empty state when the filter narrows to zero rows."""


def validate_lifecycle_copy(
    session_status: str, has_errors: bool, has_warnings: bool
) -> str:
    """Pure function — easy to unit-test the per-state secondary line.

    The plan covers ``draft``, ``validated``, ``ready``, plus a future
    ``closed`` state that's not yet part of the lifecycle enum. Falls
    through to a generic line for any unexpected status."""
    if session_status == "draft":
        if has_errors:
            return "Resolve the errors below before activating."
        return "Activate from the Next Action card on Session Home."
    if session_status == "validated":
        return "Setup is validated. Activate from Session Home."
    if session_status == "ready":
        return (
            "This session is live. Setup is locked. Revert to draft on "
            "Session Home to make changes."
        )
    if session_status == "closed":
        return "Session closed. This is a snapshot of the final setup state."
    return ""


def _verdict(error_count: int, warning_count: int) -> tuple[str, str]:
    if error_count > 0:
        plural = "" if error_count == 1 else "s"
        return f"Has {error_count} error{plural}.", "verdict-error"
    if warning_count > 0:
        plural = "" if warning_count == 1 else "s"
        return (
            f"Ready to activate with {warning_count} warning{plural}.",
            "verdict-warn",
        )
    return "Ready to activate.", "verdict-clean"


def _setup_coverage_rows(
    db: Session,
    review_session: ReviewSession,
    issue_counts_by_source: dict[str, tuple[int, int]],
) -> list[SetupCoverageRow]:
    sid = review_session.id

    reviewer_count = csv_imports.existing_reviewer_count(db, sid)
    reviewee_count = csv_imports.existing_reviewee_count(db, sid)
    assignment_count = assignments.existing_count(db, sid)
    instrument_count = len(
        list(
            db.execute(
                select(Instrument).where(Instrument.session_id == sid)
            ).scalars()
        )
    )
    has_email_overrides = bool(review_session.email_template_overrides)
    help_contact_set = bool(review_session.help_contact)
    assignment_mode = review_session.assignment_mode

    def _err_warn(source: str) -> tuple[int, int]:
        return issue_counts_by_source.get(source, (0, 0))

    rows: list[SetupCoverageRow] = []
    e, w = _err_warn("session")
    rows.append(
        SetupCoverageRow(
            label="Session name",
            status="✓" if review_session.name else "—",
            source="session",
            error_count=e,
            warning_count=w,
        )
    )
    rows.append(
        SetupCoverageRow(
            label="Session code",
            status="✓" if review_session.code else "—",
            source="session",
            error_count=0,
            warning_count=0,
        )
    )
    e, w = _err_warn("reviewers")
    rows.append(
        SetupCoverageRow(
            label="Reviewers",
            status=str(reviewer_count),
            source="reviewers",
            error_count=e,
            warning_count=w,
        )
    )
    e, w = _err_warn("reviewees")
    rows.append(
        SetupCoverageRow(
            label="Reviewees",
            status=str(reviewee_count),
            source="reviewees",
            error_count=e,
            warning_count=w,
        )
    )
    e, w = _err_warn("instruments")
    rows.append(
        SetupCoverageRow(
            label="Instruments",
            status=(
                f"{instrument_count}" if instrument_count else "—"
            ),
            source="instruments",
            error_count=e,
            warning_count=w,
        )
    )
    e, w = _err_warn("assignments")
    rows.append(
        SetupCoverageRow(
            label="Assignments",
            status=(
                f"{assignment_count} · {assignment_mode}"
                if assignment_count and assignment_mode
                else (str(assignment_count) if assignment_count else "—")
            ),
            source="assignments",
            error_count=e,
            warning_count=w,
        )
    )
    rows.append(
        SetupCoverageRow(
            label="Email template",
            status=(
                "Custom overrides" if has_email_overrides else "Default (no overrides)"
            ),
            source="email_template",
            error_count=0,
            warning_count=0,
        )
    )
    rows.append(
        SetupCoverageRow(
            label="Help contact",
            status="Set" if help_contact_set else "—",
            source=None,
        )
    )
    return rows


_VALID_SEVERITY_FILTERS = ("all", "error", "warning", "info")


def _per_source_count_summary(group_issues: list[Any]) -> str:
    """Inline count summary line for a per-source issue group.

    Reads "Reviewers (2 errors, 1 warning)" — but only the severities
    that are non-zero in the group; the leading source-name is added
    by the template (we return just the parenthetical body)."""
    error = sum(1 for i in group_issues if i.severity.value == "error")
    warning = sum(1 for i in group_issues if i.severity.value == "warning")
    info = sum(1 for i in group_issues if i.severity.value == "info")
    parts: list[str] = []
    if error:
        parts.append(f"{error} error{'' if error == 1 else 's'}")
    if warning:
        parts.append(f"{warning} warning{'' if warning == 1 else 's'}")
    if info:
        parts.append(f"{info} info")
    return ", ".join(parts) if parts else "no issues"


def build_validate_context(
    db: Session,
    review_session: ReviewSession,
    issues: list[Any],
    *,
    severity_filter: str = "all",
) -> ValidateContext:
    """Builds the page's view-shape context. ``issues`` is the
    ``list[ValidationIssue]`` returned by
    ``validation.validate_session_setup``.

    ``severity_filter`` (PR C) is one of ``"all"`` / ``"error"`` /
    ``"warning"`` / ``"info"``; anything else falls through to
    ``"all"``. The severity-counts row + chip totals always reflect
    the unfiltered issue counts so the operator can see what they
    *would* see at a different filter."""
    if severity_filter not in _VALID_SEVERITY_FILTERS:
        severity_filter = "all"

    error_count = sum(1 for i in issues if i.severity.value == "error")
    warning_count = sum(1 for i in issues if i.severity.value == "warning")
    info_count = sum(1 for i in issues if i.severity.value == "info")

    issue_counts_by_source: dict[str, tuple[int, int]] = {}
    for issue in issues:
        e, w = issue_counts_by_source.get(issue.source, (0, 0))
        if issue.severity.value == "error":
            issue_counts_by_source[issue.source] = (e + 1, w)
        elif issue.severity.value == "warning":
            issue_counts_by_source[issue.source] = (e, w + 1)

    verdict_line, verdict_class = _verdict(error_count, warning_count)
    setup_coverage = _setup_coverage_rows(
        db, review_session, issue_counts_by_source
    )
    lifecycle_copy = validate_lifecycle_copy(
        review_session.status,
        has_errors=error_count > 0,
        has_warnings=warning_count > 0,
    )

    severity_chips = [
        SeverityChip(
            key="all",
            label="All issues",
            count=len(issues),
            is_active=severity_filter == "all",
        ),
        SeverityChip(
            key="error",
            label="Errors only",
            count=error_count,
            is_active=severity_filter == "error",
        ),
        SeverityChip(
            key="warning",
            label="Warnings only",
            count=warning_count,
            is_active=severity_filter == "warning",
        ),
        SeverityChip(
            key="info",
            label="Info",
            count=info_count,
            is_active=severity_filter == "info",
        ),
    ]

    if severity_filter == "all":
        filtered_issues = list(issues)
    else:
        filtered_issues = [
            i for i in issues if i.severity.value == severity_filter
        ]

    grouped: dict[str, list[Any]] = {}
    for issue in filtered_issues:
        grouped.setdefault(issue.source, []).append(issue)
    issue_groups = [
        IssueSourceGroup(
            source=source,
            count_summary=_per_source_count_summary(group_issues),
            issues=group_issues,
        )
        for source, group_issues in grouped.items()
    ]

    return ValidateContext(
        verdict_line=verdict_line,
        verdict_class=verdict_class,
        error_count=error_count,
        warning_count=warning_count,
        info_count=info_count,
        last_validated_text="Validated just now",
        lifecycle_copy=lifecycle_copy,
        setup_coverage=setup_coverage,
        severity_filter=severity_filter,
        severity_chips=severity_chips,
        issue_groups=issue_groups,
        filtered_issue_count=len(filtered_issues),
    )


def session_status_pills(
    db: Session, review_session: ReviewSession
) -> SessionStatusPills:
    sid = review_session.id
    return SessionStatusPills(
        reviewer_count=csv_imports.existing_reviewer_count(db, sid),
        reviewee_count=csv_imports.existing_reviewee_count(db, sid),
        assignment_count=assignments.existing_count(db, sid),
        instrument_count=len(
            list(
                db.execute(
                    select(Instrument).where(Instrument.session_id == sid)
                ).scalars()
            )
        ),
        # The Email Invites editor lands in Segment 15 — for now no
        # session is "set up" yet. When the editor ships, swap this
        # for a real check (e.g. a non-empty email template row).
        email_invites_set_up=False,
    )


# ---------------------------------------------------------------------------
# Segment 11H — Quick Setup card scaffold
# ---------------------------------------------------------------------------
#
# The Quick Setup card on Session Home renders four slots; each slot has
# the same outer shape (file input + Submit + count indicator + dormant
# banner container) but the controls are inert until Segment 11J wires
# them up. The scaffold pins the visual + DOM contract here so 11J's
# wiring PRs are thin diffs that flip ``is_wired=True`` and supply
# ``wire_url=…`` per slot.


@dataclass(frozen=True)
class QuickSetupSlot:
    """One slot inside the Quick Setup card on Session Home.

    11J's PRs flip ``is_wired`` and supply ``wire_url`` per slot;
    11H ships every slot with ``is_wired=False`` and the controls
    rendered ``disabled``.
    """

    key: str
    """Stable slot identifier — ``reviewers`` / ``reviewees`` /
    ``assignments`` / ``settings``. Used as the DOM-id suffix
    (``#quick-setup-{key}``) so URL fragments scroll directly to a
    slot, and as the ``data-wire-target`` value so 11J's wiring
    can locate the slot without a CSS-selector contract."""

    label: str
    """Human-readable slot label, used in the H3 heading."""

    count: int
    """Current population — count of reviewers / reviewees /
    assignments. ``0`` for the configuration-import slot."""

    count_summary: str
    """Pre-rendered count copy, e.g. ``"8 currently"`` /
    ``"none yet"`` / ``"104 currently, full-matrix"``."""

    mode: str
    """``"file_upload"`` for slots 1, 2, 4; ``"rule_or_csv"`` for
    slot 3 (Assignments). Slot mode controls which inputs render
    inside the slot body."""

    is_wired: bool
    """``True`` once 11J / 12A wires the slot. While ``False`` the
    slot's controls render ``disabled`` and a ``coming_in`` tooltip
    surfaces the wiring PR's name."""

    wire_url: str | None
    """POST URL once ``is_wired=True``. ``None`` while inert."""

    coming_in: str | None
    """``"Wired in Segment 11J PR A"``-style tooltip while
    ``is_wired=False``. ``None`` once wired."""


@dataclass(frozen=True)
class QuickSetupContext:
    """Page-shape adapter output for the Quick Setup card.

    ``slots`` renders top-to-bottom in the order given; the card
    iterates and the ``quick_setup_slot`` macro renders each one.

    Two greying triggers, mutually exclusive:

    - ``is_disabled`` — session is Activated (``ready``). Whole
      card carries ``.card.disabled`` plain-greying per
      ``spec/session_home.md``; the Lock / Unlock button is not
      rendered (the operator's path forward is Pause, not unlock).
    - ``is_locked`` — session is editable (``draft`` / ``validated``)
      but the card body is greyed pending an explicit Unlock click.
      The body wrapper gets ``.locked``; the Lock / Unlock button
      sits outside the wrapper so it stays vivid. Defaults ``True``
      whenever the card is editable so the operator must
      deliberately unlock before any setup change. The button is a
      placeholder in 11H — Segment 11J wires the toggle.

    ``title`` overrides the H2 text. Session Home uses the default
    ``"Quick Setup"``; the new-session preview variant uses
    ``"Quick setup (optional)"`` to convey that the card surfaces
    early as a hint about post-creation setup paths.

    ``show_lock_toggle`` gates the Lock / Unlock footer button.
    Session Home renders it whenever the card is editable; the
    new-session preview variant suppresses it (the card is always
    unlocked there because there's nothing yet to lock).
    """

    slots: list[QuickSetupSlot]
    is_disabled: bool
    is_locked: bool
    description: str
    title: str = "Quick Setup"
    show_lock_toggle: bool = True


def build_quick_setup_context(
    db: Session, review_session: ReviewSession
) -> QuickSetupContext:
    sid = review_session.id
    # Per spec/session_home.md, Quick Setup disables when the session is
    # Activated (``ready``); ``closed`` is a reserved future state that
    # would also disable, but the predicate doesn't exist yet — when
    # ``closed`` ships, extend this check.
    is_disabled = lifecycle.is_ready(review_session)

    reviewer_count = csv_imports.existing_reviewer_count(db, sid)
    reviewee_count = csv_imports.existing_reviewee_count(db, sid)
    assignment_count = assignments.existing_count(db, sid)
    # ``assignment_mode`` is a stored string today (e.g. "FullMatrix"
    # / "Manual"); the column is plain Text, not a SQLAlchemy enum.
    assignment_mode: str | None = review_session.assignment_mode

    slots = [
        QuickSetupSlot(
            key="reviewers",
            label="Reviewers",
            count=reviewer_count,
            count_summary=(
                f"{reviewer_count} currently"
                if reviewer_count
                else "none yet"
            ),
            mode="file_upload",
            is_wired=False,
            wire_url=None,
            coming_in="Wired in Segment 11J PR A",
        ),
        QuickSetupSlot(
            key="reviewees",
            label="Reviewees",
            count=reviewee_count,
            count_summary=(
                f"{reviewee_count} currently"
                if reviewee_count
                else "none yet"
            ),
            mode="file_upload",
            is_wired=False,
            wire_url=None,
            coming_in="Wired in Segment 11J PR A",
        ),
        QuickSetupSlot(
            key="assignments",
            label="Assignments",
            count=assignment_count,
            count_summary=_assignment_summary(assignment_count, assignment_mode),
            mode="rule_or_csv",
            is_wired=False,
            wire_url=None,
            coming_in="Wired in Segment 11J PR B",
        ),
        QuickSetupSlot(
            key="settings",
            label="Session settings",
            count=0,
            count_summary="upload a session-settings CSV",
            mode="file_upload",
            is_wired=False,
            wire_url=None,
            coming_in="Wired in Segment 12A PR 6",
        ),
    ]

    description = (
        "Setup edits are paused while the session is Activated. "
        "Pause the session to re-enable bulk setup."
        if is_disabled
        else "Bulk-populate reviewers, reviewees, and assignments "
        "from files or rules in one place."
    )

    # Lock the card by default whenever it's editable. The toggle
    # itself is wired in 11J; 11H ships the lock state at fresh-page-
    # load default (locked) without state persistence.
    is_locked = not is_disabled

    return QuickSetupContext(
        slots=slots,
        is_disabled=is_disabled,
        is_locked=is_locked,
        description=description,
        # Title stays the default "Quick Setup" on Session Home.
        # Lock toggle renders whenever the card is editable; on
        # Activated sessions the operator's path forward is Pause,
        # not Unlock, so the toggle is suppressed.
        show_lock_toggle=not is_disabled,
    )


def build_new_session_quick_setup_context() -> QuickSetupContext:
    """Quick Setup placeholder for the ``/operator/sessions/new`` page.

    There is no session row yet, so all four slots show zero counts
    and no wire URLs. The card is always unlocked (``is_locked=False``)
    and the Lock / Unlock toggle is suppressed (the lock concept has
    nothing to lock here). Heading reads ``"Quick setup (optional)"``
    to convey this is a forward-looking hint, not a working surface.
    """

    slots = [
        QuickSetupSlot(
            key="reviewers",
            label="Reviewers",
            count=0,
            count_summary="none yet",
            mode="file_upload",
            is_wired=False,
            wire_url=None,
            coming_in="Wired in Segment 11J PR A",
        ),
        QuickSetupSlot(
            key="reviewees",
            label="Reviewees",
            count=0,
            count_summary="none yet",
            mode="file_upload",
            is_wired=False,
            wire_url=None,
            coming_in="Wired in Segment 11J PR A",
        ),
        QuickSetupSlot(
            key="assignments",
            label="Assignments",
            count=0,
            count_summary="none yet",
            mode="rule_or_csv",
            is_wired=False,
            wire_url=None,
            coming_in="Wired in Segment 11J PR B",
        ),
        QuickSetupSlot(
            key="settings",
            label="Session settings",
            count=0,
            count_summary="upload a session-settings CSV",
            mode="file_upload",
            is_wired=False,
            wire_url=None,
            coming_in="Wired in Segment 12A PR 6",
        ),
    ]

    return QuickSetupContext(
        slots=slots,
        is_disabled=False,
        is_locked=False,
        description=(
            "Bulk-populate reviewers, reviewees, and assignments "
            "from files or rules in one place — available on "
            "Session Home after the session is created."
        ),
        title="Quick setup (optional)",
        show_lock_toggle=False,
    )


def _assignment_summary(count: int, mode: str | None) -> str:
    if not count:
        return "none yet"
    if mode:
        return f"{count} currently, {mode}"
    return f"{count} currently"


# ---------------------------------------------------------------------------
# Segment 11H — Extract Data card scaffold
# ---------------------------------------------------------------------------
#
# The Extract Data card on Session Home renders five per-entity rows + a
# "Download all" zip-bundle footer. Read-only by nature: Segment 12A's
# PRs wire each row's Download button live; the card stays interactive
# in every lifecycle state (no lock-card wrap).


@dataclass(frozen=True)
class ExtractDataRow:
    """One row inside the Extract Data card on Session Home.

    12A's PRs flip ``is_wired`` and supply ``download_url`` per row;
    11H ships every row inert.
    """

    key: str
    """Stable identifier — ``settings`` / ``reviewers`` / ``reviewees``
    / ``assignments`` / ``responses`` / ``bundle``. DOM id is
    ``#extract-data-{key}``."""

    label: str

    filename: str
    """Final filename the download will carry, e.g.
    ``session-CS101-reviewers.csv``. Surfaced to the operator as a
    secondary line so they know what to expect."""

    count: int
    count_summary: str

    is_wired: bool
    download_url: str | None
    coming_in: str | None

    @property
    def show_count(self) -> bool:
        """True for the four entity rows whose count is operator-
        meaningful inline alongside the title (Reviewers / Reviewees /
        Assignments / Responses). Session settings + the zip-bundle row
        keep the title-only treatment."""
        return self.key in ("reviewers", "reviewees", "assignments", "responses")


@dataclass(frozen=True)
class ExtractDataContext:
    rows: list[ExtractDataRow]
    bundle: ExtractDataRow


def build_extract_data_context(
    db: Session, review_session: ReviewSession
) -> ExtractDataContext:
    sid = review_session.id
    code = review_session.code or "session"

    reviewer_count = csv_imports.existing_reviewer_count(db, sid)
    reviewee_count = csv_imports.existing_reviewee_count(db, sid)
    assignment_count = assignments.existing_count(db, sid)
    response_count = responses_service.session_response_count(db, sid)
    instrument_count = len(
        list(
            db.execute(
                select(Instrument).where(Instrument.session_id == sid)
            ).scalars()
        )
    )

    rows = [
        ExtractDataRow(
            key="reviewers",
            label="Reviewers",
            filename=f"session-{code}-reviewers.csv",
            count=reviewer_count,
            count_summary=_extract_summary("reviewer", reviewer_count),
            is_wired=False,
            download_url=None,
            coming_in="Wired in Segment 12A PR 3",
        ),
        ExtractDataRow(
            key="assignments",
            label="Assignments",
            filename=f"session-{code}-assignments.csv",
            count=assignment_count,
            count_summary=_extract_summary("assignment", assignment_count),
            is_wired=False,
            download_url=None,
            coming_in="Wired in Segment 12A PR 4",
        ),
        ExtractDataRow(
            key="reviewees",
            label="Reviewees",
            filename=f"session-{code}-reviewees.csv",
            count=reviewee_count,
            count_summary=_extract_summary("reviewee", reviewee_count),
            is_wired=False,
            download_url=None,
            coming_in="Wired in Segment 12A PR 3",
        ),
        ExtractDataRow(
            key="responses",
            label="Responses",
            filename=f"session-{code}-responses.csv",
            count=response_count,
            count_summary=_extract_summary("response", response_count),
            is_wired=False,
            download_url=None,
            coming_in="Wired in Segment 12A PR 5",
        ),
        ExtractDataRow(
            key="settings",
            label="Session settings",
            filename=f"session-{code}-settings.csv",
            count=instrument_count,
            count_summary=_extract_summary("instrument", instrument_count),
            is_wired=False,
            download_url=None,
            coming_in="Wired in Segment 12A PR 1",
        ),
    ]

    bundle = ExtractDataRow(
        key="bundle",
        label="Zip all",
        filename=f"session-{code}-export.zip",
        count=sum(r.count for r in rows),
        count_summary="zip of all five CSVs above",
        is_wired=False,
        download_url=None,
        coming_in="Wired in Segment 12A PR 6",
    )

    return ExtractDataContext(rows=rows, bundle=bundle)


def _extract_summary(noun: str, count: int) -> str:
    if count == 0:
        return f"0 {noun}s"
    if count == 1:
        return f"1 {noun}"
    return f"{count} {noun}s"


# ---------------------------------------------------------------------------
# Segment 11C Part 1 — Manage Invitations consolidated row spec
# ---------------------------------------------------------------------------
#
# The rebuilt Manage Invitations page renders one row per assigned active
# reviewer with seven columns (per the segment plan): Reviewer / Email
# Status / Email Sent / Review Progress / Required Fields / Last reminder /
# Action. ``InvitationsRow`` carries all the per-row data the template
# needs; ``build_invitations_rows`` joins:
#   - the per-reviewer progress + required-field aggregates from
#     ``monitoring.per_reviewer_progress`` (which already joins
#     reviewers ⨯ invitations ⨯ assignments ⨯ responses);
#   - the latest invitation outbox row's status + sent_at (the
#     "Email Status" + "Email Sent" columns);
# in a single batched outbox query rather than firing N queries per row.


@dataclass(frozen=True)
class InvitationsRow:
    reviewer: Reviewer
    invitation: Invitation | None
    email_status: str
    """The latest invitation outbox row's status, or ``"not sent"`` when
    no outbox row exists for this reviewer's invitation. Today the value
    set is ``{"not sent", "queued", "sent"}``; Segment 11C Part 2 widens
    it to include ``"sending"`` and ``"failed"``."""
    email_sent_at: datetime | None
    review_progress_state: str
    """``"not started"`` / ``"in progress"`` / ``"submitted"`` —
    pill_state from ``monitoring.ReviewerProgress``."""
    review_progress_done: int
    review_progress_total: int
    required_fields_done: int
    required_fields_total: int
    last_reminder_at: datetime | None

    @property
    def is_incomplete(self) -> bool:
        return self.review_progress_state != "submitted"

    @property
    def summary_state(self) -> str:
        """Single derived state for the Manage Invitations status filter.

        Collapses the otherwise-orthogonal Email Status + Review
        Progress columns into one bucket the operator filters on.
        Mirrors `spec/operations_renew.md` "Status filter values"
        (Manage Invitations) modulo the deferred "stale" bucket.
        """
        if self.email_status == "not sent":
            return "not_sent"
        if self.review_progress_state == "submitted":
            return "submitted"
        if self.review_progress_state == "in progress":
            return "in_progress"
        return "not_started"


def _latest_invitation_outbox_by_reviewer(
    db: Session, session_id: int
) -> dict[int, EmailOutbox]:
    """One latest ``kind="invitation"`` outbox row per reviewer.

    Used by ``build_invitations_rows`` to populate the Email Status +
    Email Sent columns. Sorted descending by created_at then id, then
    the first row per reviewer wins.
    """
    rows = list(
        db.execute(
            select(EmailOutbox)
            .where(
                EmailOutbox.session_id == session_id,
                EmailOutbox.kind == invitations_service.INVITATION_KIND,
                EmailOutbox.reviewer_id.is_not(None),
            )
            .order_by(
                EmailOutbox.created_at.desc(), EmailOutbox.id.desc()
            )
        ).scalars()
    )
    out: dict[int, EmailOutbox] = {}
    for row in rows:
        rid = row.reviewer_id
        if rid is not None and rid not in out:
            out[rid] = row
    return out


def build_invitations_rows(
    db: Session, review_session: ReviewSession
) -> list[InvitationsRow]:
    progress_rows = monitoring.per_reviewer_progress(db, review_session)
    latest_outbox = _latest_invitation_outbox_by_reviewer(db, review_session.id)
    out: list[InvitationsRow] = []
    for p in progress_rows:
        outbox_row = latest_outbox.get(p.reviewer.id)
        if outbox_row is None:
            email_status = "not sent"
            email_sent_at: datetime | None = None
        else:
            email_status = outbox_row.status
            email_sent_at = outbox_row.sent_at
        out.append(
            InvitationsRow(
                reviewer=p.reviewer,
                invitation=p.invitation,
                email_status=email_status,
                email_sent_at=email_sent_at,
                review_progress_state=p.pill_state,
                review_progress_done=p.completed_count,
                review_progress_total=p.assignment_count,
                required_fields_done=p.required_done,
                required_fields_total=p.required_total,
                last_reminder_at=p.last_reminder_at,
            )
        )
    return out


# ---------------------------------------------------------------------------
# Segment 11C Part 1 — Responses page (reviewee-centric coverage)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResponsesRow:
    reviewee: Reviewee
    coverage_state: str
    """``"complete"`` / ``"adequate"`` / ``"at risk"`` / ``"no responses"``"""
    reviewers_done: int
    reviewers_total: int
    last_response_at: datetime | None

    @property
    def is_at_risk(self) -> bool:
        return self.coverage_state in ("at risk", "no responses")


def build_responses_rows(
    db: Session, review_session: ReviewSession
) -> list[ResponsesRow]:
    coverage = monitoring.per_reviewee_coverage(db, review_session)
    return [
        ResponsesRow(
            reviewee=c.reviewee,
            coverage_state=c.pill_state,
            reviewers_done=c.completed_count,
            reviewers_total=c.reviewer_count,
            last_response_at=c.last_response_at,
        )
        for c in coverage
    ]


# ---------------------------------------------------------------------------
# Filter helpers — Segment 11C Part 1 follow-up
# ---------------------------------------------------------------------------
#
# Both Manage Invitations and Responses ship the list-with-bulk-actions
# pattern's filter strip (status dropdown + name/email search) per
# `spec/operations_renew.md` "Filtering". Filters compose: status + search
# narrows to rows matching both. Filter state is page-local — query params
# only, nothing persisted across navigations.


# Status filter options for Manage Invitations. Order matters: it's the
# dropdown order operators see. ``"all"`` (no filter) is implicit.
INVITATIONS_STATUS_OPTIONS: tuple[tuple[str, str], ...] = (
    ("not_sent", "Not yet sent"),
    ("not_started", "Sent, not started"),
    ("in_progress", "In progress"),
    ("submitted", "Submitted"),
)


# Status filter options for Responses. Order matters; ``"all"`` is implicit.
RESPONSES_STATUS_OPTIONS: tuple[tuple[str, str], ...] = (
    ("complete", "Complete"),
    ("adequate", "Adequate"),
    ("at_risk", "At risk"),
    ("no_responses", "No responses"),
)


def _matches_search(haystack: str, needle: str) -> bool:
    return needle.casefold() in haystack.casefold()


def filter_invitations_rows(
    rows: list[InvitationsRow], *, status: str, search: str
) -> list[InvitationsRow]:
    """Apply status + search filters to invitations rows.

    ``status`` is one of ``INVITATIONS_STATUS_OPTIONS`` keys or
    ``"all"`` (anything else falls through to "all"). ``search`` is
    matched case-insensitively against the reviewer's name or email.
    Empty ``search`` is a no-op."""
    out = list(rows)
    valid_status = {key for key, _ in INVITATIONS_STATUS_OPTIONS}
    if status in valid_status:
        out = [r for r in out if r.summary_state == status]
    needle = search.strip()
    if needle:
        out = [
            r
            for r in out
            if _matches_search(r.reviewer.name, needle)
            or _matches_search(r.reviewer.email, needle)
        ]
    return out


def filter_responses_rows(
    rows: list[ResponsesRow], *, status: str, search: str
) -> list[ResponsesRow]:
    """Apply status + search filters to responses rows.

    ``status`` is one of ``RESPONSES_STATUS_OPTIONS`` keys or
    ``"all"``. The four status keys are slugged
    (``"at_risk"`` / ``"no_responses"``) for URL-friendliness; this
    helper maps back to the row's ``coverage_state`` (``"at risk"`` /
    ``"no responses"``)."""
    out = list(rows)
    status_to_state = {
        "complete": "complete",
        "adequate": "adequate",
        "at_risk": "at risk",
        "no_responses": "no responses",
    }
    target_state = status_to_state.get(status)
    if target_state is not None:
        out = [r for r in out if r.coverage_state == target_state]
    needle = search.strip()
    if needle:
        out = [
            r
            for r in out
            if _matches_search(r.reviewee.name, needle)
            or _matches_search(r.reviewee.email_or_identifier, needle)
        ]
    return out
