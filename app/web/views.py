"""View-shape adapters for operator templates.

Translate domain objects into row tuples / dataclasses that templates
iterate over. Service modules stay business-logic-only; templates stay
markup-only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from datetime import datetime

from app.db.models import (
    Assignment,
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
    email_templates,
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

    error_message: str | None = None
    """Populated when the operator's last submit for this slot was
    rejected (parse / validation failure, or a lifecycle rejection
    on ``ready``). Rendered as a ``banner-error`` inside the slot.
    The cancel link in the banner returns the operator to the slot
    fragment with a clean URL."""

    cancel_url: str | None = None
    """Clean Home URL with this slot's fragment anchor. Used as the
    Cancel target for the error banner. Stable across renders."""


@dataclass(frozen=True)
class QuickSetupContext:
    """Page-shape adapter output for the Quick Setup card.

    ``slots`` renders top-to-bottom in the order given; the card
    iterates and the ``quick_setup_slot`` macro renders each one.

    Two status signals — ``is_locked`` (visual greying) and
    ``show_lock_toggle`` (whether the operator can unlock) —
    together capture the card's availability:

    - **Available** (``draft`` AND no persisted responses):
      ``show_lock_toggle=True``. ``is_locked`` is ``True`` by
      default on every fresh page load; the cookie-driven
      ``is_unlocked`` flips it off. The operator must explicitly
      Unlock before any submit.
    - **Unavailable** (``validated`` / ``ready`` / ``closed``, or
      any state with persisted responses): ``show_lock_toggle=False``
      and ``is_locked=True`` permanently. The body greys; the
      operator can't unlock. Defense-in-depth route gates
      (``_require_editable`` + ``_require_response_loss_ack``)
      stay in place but never fire from this surface because the
      submit forms aren't reachable when the body's locked.

    ``is_disabled`` mirrors ``not is_available`` for templates
    that want a single boolean to drive label-only signals; it's
    not a separate visual lock primitive.

    ``title`` overrides the H2 text. Session Home uses the default
    ``"Quick Setup"``; the new-session preview variant uses
    ``"Quick setup (optional)"`` to convey that the card surfaces
    early as a hint about post-creation setup paths.

    ``show_lock_toggle`` gates the Lock / Unlock footer button.
    Session Home renders it only while the card is available
    (``draft`` AND no responses); the new-session preview variant
    also suppresses it (no session row → nothing to lock).
    """

    slots: list[QuickSetupSlot]
    is_disabled: bool
    is_locked: bool
    description: str
    title: str = "Quick Setup"
    show_lock_toggle: bool = True


def build_quick_setup_context(
    db: Session,
    review_session: ReviewSession,
    *,
    is_unlocked: bool = False,
    error_kind: str | None = None,
    error_reason: str | None = None,
) -> QuickSetupContext:
    """Build the Quick Setup card context for Session Home.

    ``is_unlocked`` reflects the operator's lock-toggle cookie
    (``qsu_{session_id}=1``). Default is ``False`` ⇒ ``is_locked=True``
    on every fresh page load.

    ``error_kind`` + ``error_reason`` come from the
    ``?quick_setup_error=...&quick_setup_reason=...`` redirect flag set
    by the slot's POST handler on rejection. The pair drives the
    inline ``banner-error`` rendered inside the offending slot. Other
    slots are unaffected.
    """

    sid = review_session.id
    # Card is functional only on ``draft`` AND when no reviewer
    # responses exist yet. Outside that window — ``validated`` /
    # ``ready`` / ``closed``, or any state with persisted responses
    # from a prior activation cycle — the card stays permanently
    # locked (body greyed, Lock / Unlock toggle hidden, submits
    # rejected at the service layer via ``_require_editable`` +
    # ``_require_response_loss_ack``). The single description copy
    # names both conditions.
    has_responses = responses_service.session_response_count(db, sid) > 0
    is_available = lifecycle.is_draft(review_session) and not has_responses
    is_disabled = not is_available

    reviewer_count = csv_imports.existing_reviewer_count(db, sid)
    reviewee_count = csv_imports.existing_reviewee_count(db, sid)
    assignment_count = assignments.existing_count(db, sid)
    assignment_mode: str | None = review_session.assignment_mode

    cancel_url_for = lambda key: (  # noqa: E731
        f"/operator/sessions/{sid}#quick-setup-{key}"
    )

    def _error_for(slot_key: str) -> str | None:
        if error_kind != slot_key:
            return None
        return _quick_setup_error_message(slot_key, error_reason)

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
            is_wired=True,
            wire_url=f"/operator/sessions/{sid}/quick-setup/reviewers",
            coming_in=None,
            error_message=_error_for("reviewers"),
            cancel_url=cancel_url_for("reviewers"),
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
            is_wired=True,
            wire_url=f"/operator/sessions/{sid}/quick-setup/reviewees",
            coming_in=None,
            error_message=_error_for("reviewees"),
            cancel_url=cancel_url_for("reviewees"),
        ),
        QuickSetupSlot(
            key="assignments",
            label="Assignments",
            count=assignment_count,
            count_summary=_assignment_summary(assignment_count, assignment_mode),
            mode="rule_or_csv",
            is_wired=True,
            wire_url=f"/operator/sessions/{sid}/quick-setup/assignments",
            coming_in=None,
            error_message=_error_for("assignments"),
            cancel_url=cancel_url_for("assignments"),
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
            error_message=None,
            cancel_url=cancel_url_for("settings"),
        ),
    ]

    description = (
        "Bulk-populate reviewers, reviewees, and assignments from "
        "files or rules in one place. Available only when session "
        "is in draft mode and does not have any responses."
    )

    # Default-locked on every fresh page load when the card is
    # available; the cookie-driven ``is_unlocked`` flips it off
    # until the operator locks again or the cookie is cleared.
    # When the card isn't available (validated / ready / closed
    # / or any state with persisted responses), force-lock and
    # hide the toggle entirely so the operator can't visually
    # unlock something the route layer would reject anyway.
    is_locked = True if not is_available else not is_unlocked

    return QuickSetupContext(
        slots=slots,
        is_disabled=is_disabled,
        is_locked=is_locked,
        description=description,
        show_lock_toggle=is_available,
    )


def _quick_setup_error_message(slot_key: str, reason: str | None) -> str:
    """Render the banner-error copy for a slot's last failed submit.

    ``reason`` is a stable token from the route handler:

    - ``"parse"`` — the upload couldn't be parsed / validated. The
      message points the operator at the per-entity Setup page where
      the per-row error feedback lives.
    - ``"lifecycle"`` — the submit hit ``_require_editable`` on a
      ``ready`` session. The message names the next move (Pause).
    - ``"needs_confirm"`` — the form was submitted without ticking
      the card-level replacement-confirmation checkbox at the top
      of Quick Setup.
    """

    label_for = {
        "reviewers": "Reviewers",
        "reviewees": "Reviewees",
        "assignments": "Assignments",
        "settings": "Session settings",
    }
    label = label_for.get(slot_key, slot_key)
    if reason == "lifecycle":
        return (
            "Setup edits are paused while the session is Activated. "
            "Pause the session before applying setup changes."
        )
    if reason == "needs_confirm":
        return (
            "Tick the replacement-confirmation box at the top of "
            "Quick Setup before submitting."
        )
    # Default / parse-error path. Keep the message short — the
    # per-entity Setup page is the authoritative error surface.
    per_entity_path = {
        "reviewers": "reviewers",
        "reviewees": "reviewees",
        "assignments": "assignments",
    }.get(slot_key)
    if per_entity_path:
        return (
            f"Could not import {label.lower()}. "
            f"Open the {label} Setup page for per-row error details."
        )
    return f"Could not import {label.lower()}."


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


_FILTER_LABEL_TAIL_RE = re.compile(r"\(([^()]+)\)\s*$")


def _extract_filter_label_tail(value: str) -> str | None:
    """Return the last parens-enclosed segment of a typeahead label.

    Manage Invitations and Manage Responses use a `<datalist>`
    typeahead whose options have the form ``"Name (email)"`` or
    ``"Name (identifier)"``. When the operator picks from the
    typeahead, the form submits the whole label string, which would
    miss a substring match against just the name or email. Extracting
    the parenthetical lets the filter do an exact email/identifier
    match in the picked-from-typeahead case while still falling back to
    substring search when the operator types free text. ``None`` when
    no parens-enclosed tail is present."""
    match = _FILTER_LABEL_TAIL_RE.search(value)
    if match is None:
        return None
    return match.group(1).strip()


def filter_invitations_rows(
    rows: list[InvitationsRow], *, status: str, search: str
) -> list[InvitationsRow]:
    """Apply status + search filters to invitations rows.

    ``status`` is one of ``INVITATIONS_STATUS_OPTIONS`` keys or
    ``"all"`` (anything else falls through to "all"). ``search`` is
    matched case-insensitively against the reviewer's name or email;
    when the value looks like a ``"Name (email)"`` typeahead pick, the
    bracketed email is used for an exact match instead. Empty
    ``search`` is a no-op."""
    out = list(rows)
    valid_status = {key for key, _ in INVITATIONS_STATUS_OPTIONS}
    if status in valid_status:
        out = [r for r in out if r.summary_state == status]
    needle = search.strip()
    if needle:
        tail = _extract_filter_label_tail(needle)
        if tail is not None and "@" in tail:
            picked = tail.casefold()
            out = [r for r in out if r.reviewer.email.casefold() == picked]
        else:
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
    ``"no responses"``).

    ``search`` is matched case-insensitively against the reviewee's
    name or ``email_or_identifier``; when the value looks like a
    ``"Name (identifier)"`` typeahead pick, the bracketed identifier
    is used for an exact match instead."""
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
        tail = _extract_filter_label_tail(needle)
        if tail is not None:
            picked = tail.casefold()
            out = [
                r
                for r in out
                if r.reviewee.email_or_identifier.casefold() == picked
            ]
        else:
            out = [
                r
                for r in out
                if _matches_search(r.reviewee.name, needle)
                or _matches_search(r.reviewee.email_or_identifier, needle)
            ]
    return out


def invitations_search_options(rows: list[InvitationsRow]) -> list[str]:
    """``"Name (email)"`` labels for the Manage Invitations typeahead.

    Sorted alphabetically (case-insensitive) so the `<datalist>` reads
    consistently regardless of the row order the page renders in. One
    entry per row; deduplication isn't needed because invitations rows
    are already one-per-reviewer."""
    labels = [
        f"{r.reviewer.name} ({r.reviewer.email})" for r in rows
    ]
    return sorted(labels, key=str.casefold)


def responses_search_options(rows: list[ResponsesRow]) -> list[str]:
    """``"Name (identifier)"`` labels for the Manage Responses typeahead.

    Same shape as ``invitations_search_options`` but keyed on the
    reviewee's ``email_or_identifier`` (which is the operator-visible
    handle for a reviewee even when there's no email on file)."""
    labels = [
        f"{r.reviewee.name} ({r.reviewee.email_or_identifier})"
        for r in rows
    ]
    return sorted(labels, key=str.casefold)


# How many reviewee names the picker context strip shows before
# collapsing the rest into the `<details>` disclosure tail.
PREVIEW_PICKER_REVIEWEE_PEEK_COUNT = 3


@dataclass(frozen=True)
class PreviewPickerOption:
    """One row backing the picker `<datalist>` and the prev/next math.

    ``label`` is the display string (``"Name (email)"``); ``value`` is
    the bare email the form submits. Sort order across all options is
    alphabetical by email (case-insensitive), matching the order
    `app/services/monitoring._assigned_active_reviewers` uses elsewhere.
    """

    reviewer_id: int
    name: str
    email: str
    label: str


@dataclass(frozen=True)
class PreviewPickerContext:
    options: list[PreviewPickerOption]
    """Every reviewer in the session, alphabetical by email. Backs both
    the `<datalist>` and the prev/next math."""

    raw_query: str
    """The operator's typed value (post-strip), forwarded to the input
    so refresh/back doesn't blank it."""

    current: PreviewPickerOption | None
    """The resolved selection, or ``None`` when nothing is selected
    (no param, empty param, or unmatched param)."""

    current_index: int | None
    """0-based index of ``current`` within ``options``; ``None`` when
    no current selection."""

    prev_email: str | None
    """Email to step to on Previous; wraps. ``None`` when no current."""

    next_email: str | None
    """Email to step to on Next; wraps. ``None`` when no current."""

    reviewee_count: int
    """How many distinct reviewees ``current`` is assigned to (counting
    only ``include=True`` assignments). 0 when no current."""

    reviewee_peek: list[str] = field(default_factory=list)
    """First ``PREVIEW_PICKER_REVIEWEE_PEEK_COUNT`` reviewee names for
    the context strip."""

    reviewee_tail: list[str] = field(default_factory=list)
    """Remaining reviewee names that go inside the `<details>`
    disclosure. Empty when ``reviewee_count`` is at or below the peek
    count."""

    no_match_query: str | None = None
    """When the operator submitted a value that didn't resolve, the
    typed value (post-strip). The template renders the "No reviewer
    matched 'foo'." note. ``None`` when the input was empty or
    resolved cleanly."""


_PICKER_LABEL_EMAIL_RE = re.compile(r"\(([^()]+@[^()]+)\)\s*$")


def _extract_email_from_picker_value(value: str) -> str:
    """Parse the picker's submitted value into an email.

    Accepts a bare email (``"alice@x.edu"``) or a datalist label
    (``"Alice Smith (alice@x.edu)"``). Returns the trimmed lower-case
    email, or the trimmed lower-case input unchanged when no parens-
    enclosed email is found (the caller treats unmatched values as a
    no-match).
    """
    stripped = value.strip()
    if not stripped:
        return ""
    match = _PICKER_LABEL_EMAIL_RE.search(stripped)
    if match is not None:
        return match.group(1).strip().casefold()
    return stripped.casefold()


def build_preview_picker_context(
    db: Session, review_session: ReviewSession, reviewer_query: str
) -> PreviewPickerContext:
    """Hydrate the Previews-page reviewer picker.

    ``reviewer_query`` comes from ``?reviewer_email=`` and may be
    blank, an email, or the datalist label format
    (``"Name (email)"``). Resolution is case-insensitive on email.
    Unmatched non-empty values surface as ``no_match_query`` so the
    template renders the inline "No reviewer matched" note rather than
    silently falling back.
    """

    reviewer_rows = list(
        db.execute(
            select(Reviewer)
            .where(Reviewer.session_id == review_session.id)
            .order_by(Reviewer.email)
        ).scalars()
    )

    options = [
        PreviewPickerOption(
            reviewer_id=r.id,
            name=r.name,
            email=r.email,
            label=f"{r.name} ({r.email})",
        )
        for r in reviewer_rows
    ]

    raw = reviewer_query.strip()
    parsed_email = _extract_email_from_picker_value(reviewer_query)

    current: PreviewPickerOption | None = None
    current_index: int | None = None
    if parsed_email:
        for idx, opt in enumerate(options):
            if opt.email.casefold() == parsed_email:
                current = opt
                current_index = idx
                break

    prev_email: str | None = None
    next_email: str | None = None
    if current is not None and len(options) > 0 and current_index is not None:
        n = len(options)
        prev_email = options[(current_index - 1) % n].email
        next_email = options[(current_index + 1) % n].email

    no_match: str | None = None
    if raw and current is None:
        no_match = raw

    reviewee_count = 0
    reviewee_peek: list[str] = []
    reviewee_tail: list[str] = []
    if current is not None:
        names = _picker_assigned_reviewee_names(
            db, review_session.id, current.reviewer_id
        )
        reviewee_count = len(names)
        reviewee_peek = names[:PREVIEW_PICKER_REVIEWEE_PEEK_COUNT]
        reviewee_tail = names[PREVIEW_PICKER_REVIEWEE_PEEK_COUNT:]

    return PreviewPickerContext(
        options=options,
        raw_query=raw,
        current=current,
        current_index=current_index,
        prev_email=prev_email,
        next_email=next_email,
        reviewee_count=reviewee_count,
        reviewee_peek=reviewee_peek,
        reviewee_tail=reviewee_tail,
        no_match_query=no_match,
    )


def _picker_assigned_reviewee_names(
    db: Session, session_id: int, reviewer_id: int
) -> list[str]:
    """Distinct reviewee names this reviewer is assigned to, sorted.

    Only counts ``include=True`` assignments (matching how the rest of
    the app treats included assignments as the live set). Sort by name
    so the context strip is stable across reloads.
    """
    rows = db.execute(
        select(Reviewee.name)
        .join(Assignment, Assignment.reviewee_id == Reviewee.id)
        .where(
            Assignment.session_id == session_id,
            Assignment.reviewer_id == reviewer_id,
            Assignment.include.is_(True),
        )
        .distinct()
        .order_by(Reviewee.name)
    ).all()
    return [row[0] for row in rows]


# --- Email previews region (segment 11F PR B) ----------------------------- #
#
# The previews page renders three reviewer-facing emails through a single
# tabbed card. The `EMAIL_PREVIEW_TABS` registry pins the tab order
# (chronological: invitation → reminder → responses-received) and tells the
# template which tabs are shipped vs. coming. The route's render dispatch
# lives in `build_email_preview_body` below. All three are live as of
# Segment 11F PR D (reminder) + Segment 11E PR 6 (responses-received);
# the ``is_shipped`` field stays for any future tab additions that need
# to land registry-first and dispatch-second.

# A placeholder URL the operator-facing preview substitutes for `$invite_url`.
# Real invitation tokens are one-time-use and would be wasted (and audit-
# muddying) if minted just to power a preview render.
PREVIEW_INVITE_URL_PLACEHOLDER = "(preview link — real invitation URL is generated when the operator sends)"


@dataclass(frozen=True)
class EmailBody:
    """Rendered email body for the previews page.

    `subject`, `body` come from `email_templates.render_*`. `from_display`
    + `to_display` are envelope strings the operator sees in the preview
    header — they're not part of the rendered template, just the chrome
    around it.
    """

    subject: str
    from_display: str
    to_display: str
    body: str


@dataclass(frozen=True)
class EmailPreviewTab:
    """One entry in the previews page's email tab strip."""

    key: str
    """URL slug — what `?email=` resolves to."""

    label: str
    """Human-readable tab label."""

    template_setup_param: str
    """Value to thread into the deep-link to the Email Template Setup
    page (`/setupinvite?template=...`). Same as `key` for now; kept
    separate so the URL slug can diverge from the Setup-page slug
    without ripple."""

    is_shipped: bool
    """`True` once the matching render adapter is wired in. All three
    tabs are shipped as of Segment 11F PR D (reminder) + Segment 11E
    PR 6 (responses-received); the field stays for any future tab
    additions that land registry-first and dispatch-second."""

    description: str
    """One-line description rendered below the tab strip when this tab
    is active. Grounds the operator in when this email gets sent."""


EMAIL_PREVIEW_TABS: tuple[EmailPreviewTab, ...] = (
    EmailPreviewTab(
        key="invitation",
        label="Invitation",
        template_setup_param="invitation",
        is_shipped=True,
        description="Sent when the operator activates the session.",
    ),
    EmailPreviewTab(
        key="reminder",
        label="Reminder",
        template_setup_param="reminder",
        is_shipped=True,
        description=(
            "Sent against an active session past the configured "
            "reminder threshold. Operators trigger reminders from "
            "Manage Invitations."
        ),
    ),
    EmailPreviewTab(
        key="responses_received",
        label="Responses received",
        template_setup_param="responses_received",
        is_shipped=True,
        description="Sent the moment the reviewer submits their review.",
    ),
)


def resolve_email_preview_tab(key: str) -> EmailPreviewTab:
    """Return the registry entry for ``key``, falling back to
    ``"invitation"`` when ``key`` is unknown or not yet shipped.

    The fallback keeps `?email=foo` from 404'ing or rendering a blank
    region — the operator gets the canonical first tab instead. PRs
    D / E lift this once the matching tab ships.
    """
    for tab in EMAIL_PREVIEW_TABS:
        if tab.key == key and tab.is_shipped:
            return tab
    # Unknown or unshipped — fall back to the first shipped tab.
    for tab in EMAIL_PREVIEW_TABS:
        if tab.is_shipped:
            return tab
    raise RuntimeError(  # pragma: no cover — invariant: invitation always ships
        "EMAIL_PREVIEW_TABS has no shipped entries"
    )


def email_preview_from_display(user: User) -> str:
    """Format the From-header string the preview shows, given the
    operator's SMTP credentials.

    Reads ``smtp_username`` / ``smtp_from_display_name`` directly off
    the User row (no decryption — the displayed header doesn't need
    the password). When the credentials aren't configured, returns a
    placeholder pointing at Settings so the preview surfaces the
    missing config rather than rendering an empty header.
    """
    username = (user.smtp_username or "").strip()
    if not username:
        return "(SMTP From not configured — see Settings)"
    display_name = (user.smtp_from_display_name or "").strip()
    if display_name:
        return f"{display_name} <{username}>"
    return username


def build_email_preview_body(
    *,
    tab: EmailPreviewTab,
    review_session: ReviewSession,
    reviewer: Reviewer,
    from_display: str,
) -> EmailBody | None:
    """Render the active tab's email for the picker-selected reviewer.

    All three tabs ship live render adapters as of Segment 11F PR D
    (reminder) + Segment 11E PR 6 (responses-received); a ``None``
    return only happens if a caller passes a future-unshipped tab
    directly."""
    if tab.key == "invitation":
        subject, body = email_templates.render_invitation(
            review_session, reviewer, PREVIEW_INVITE_URL_PLACEHOLDER
        )
        return EmailBody(
            subject=subject,
            from_display=from_display,
            to_display=reviewer.email,
            body=body,
        )
    if tab.key == "reminder":
        subject, body = email_templates.render_reminder(
            review_session, reviewer, PREVIEW_INVITE_URL_PLACEHOLDER
        )
        return EmailBody(
            subject=subject,
            from_display=from_display,
            to_display=reviewer.email,
            body=body,
        )
    if tab.key == "responses_received":
        subject, body = email_templates.render_responses_received(
            review_session, reviewer
        )
        return EmailBody(
            subject=subject,
            from_display=from_display,
            to_display=reviewer.email,
            body=body,
        )
    return None


# Per-template merge-tag list surfaced by the email-template editor's
# right card. Invitation / reminder share the canonical five tags;
# responses-received drops ``$invite_url`` (moot post-submit) and adds
# ``$submitted_at``. Kept here (not in ``email_templates``) because the
# tag *descriptions* are operator-facing copy — view-shape rather than
# render-time data.
_MERGE_TAG_DESCRIPTIONS = {
    "$reviewer_name": "Reviewer's name from the roster.",
    "$session_name": "Session name.",
    "$deadline": "Session deadline (YYYY-MM-DD), blank when unset.",
    "$help_contact": "Per-session help contact.",
    "$invite_url": "Reviewer-specific invitation URL.",
    "$submitted_at": (
        "When the reviewer submitted, formatted YYYY-MM-DD HH:MM TZ. "
        "Renders \"(not yet submitted)\" in previews before the "
        "reviewer has submitted anything."
    ),
}

_MERGE_TAGS_BY_TEMPLATE: dict[str, tuple[str, ...]] = {
    "invitation": (
        "$reviewer_name",
        "$session_name",
        "$deadline",
        "$help_contact",
        "$invite_url",
    ),
    "reminder": (
        "$reviewer_name",
        "$session_name",
        "$deadline",
        "$help_contact",
        "$invite_url",
    ),
    "responses_received": (
        "$reviewer_name",
        "$session_name",
        "$deadline",
        "$help_contact",
        "$submitted_at",
    ),
}


def merge_tags_for_template(template: str) -> list[dict[str, str]]:
    """Returns the editor's right-card merge-tag list for ``template``.
    Unknown ``template`` values raise ``KeyError`` — the route already
    validates against ``_VALID_TEMPLATES`` before dispatching here."""
    return [
        {"tag": tag, "description": _MERGE_TAG_DESCRIPTIONS[tag]}
        for tag in _MERGE_TAGS_BY_TEMPLATE[template]
    ]


# ─────────────────────────────────────────────────────────────────
# Reviewer-surface preview card (Segment 11F PR C). The previews hub
# renders the picker-selected reviewer's would-be surface inside an
# iframe srcdoc so the reviewer's own CSS scope (`body.ui-v2 reviewer`)
# can't leak into the operator chrome.
#
# The adapter returns a `SurfacePreviewContext` with one of two
# branches populated: ``preview`` carries the rendered context dict
# the template engine uses to produce the iframe srcdoc, OR
# ``missing`` describes a scoped missing-data error (no instruments
# configured / reviewer has no assignments) so the card surfaces a
# scoped error rather than a blank surface. Errors are scoped to this
# card only — the email region above the `<hr>` keeps rendering.
# ─────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SurfacePreviewMissing:
    """Scoped missing-data error for the surface card."""

    message: str
    setup_label: str
    setup_url: str


@dataclass(frozen=True)
class SurfacePreviewContext:
    """Result of building the surface preview card.

    Exactly one of ``preview`` / ``missing`` is non-None.
    """

    preview: dict | None
    missing: SurfacePreviewMissing | None


def build_surface_preview_context(
    *,
    db: Session,
    user: User,
    review_session: ReviewSession,
    reviewer: Reviewer,
) -> SurfacePreviewContext:
    """Build the surface preview card's context.

    Wraps :func:`routes_reviewer.build_preview_context` with the
    picker-selected reviewer threaded through, then surfaces missing-
    data errors scoped to this card. The route renders the returned
    ``preview`` dict against ``reviewer/review_surface.html`` to
    produce the iframe srcdoc.
    """
    # Local import: ``routes_reviewer`` imports from ``views`` for
    # ``placeholder_for_field`` etc., so a top-level import here would
    # cycle.
    from app.web.routes_reviewer import build_preview_context

    instrument_count = (
        db.execute(
            select(Instrument).where(Instrument.session_id == review_session.id)
        )
        .scalars()
        .first()
    )
    if instrument_count is None:
        return SurfacePreviewContext(
            preview=None,
            missing=SurfacePreviewMissing(
                message=(
                    "No instruments configured for this session. "
                    "Configure on the Instruments Setup page."
                ),
                setup_label="Instruments (Setup)",
                setup_url=(
                    f"/operator/sessions/{review_session.id}/instruments"
                ),
            ),
        )

    assigned_count = (
        db.execute(
            select(Assignment).where(
                Assignment.session_id == review_session.id,
                Assignment.reviewer_id == reviewer.id,
                Assignment.include.is_(True),
            )
        )
        .scalars()
        .first()
    )
    if assigned_count is None:
        return SurfacePreviewContext(
            preview=None,
            missing=SurfacePreviewMissing(
                message=(
                    "This reviewer has no reviewees assigned. "
                    "Configure assignments on the Assignments Setup "
                    "page."
                ),
                setup_label="Assignments (Setup)",
                setup_url=(
                    f"/operator/sessions/{review_session.id}/assignments"
                ),
            ),
        )

    preview = build_preview_context(
        db=db,
        user=user,
        review_session=review_session,
        target_reviewer=reviewer,
    )
    return SurfacePreviewContext(preview=preview, missing=None)


# Segment 13A PR 0 — Rule Based card scaffold on Setup → Assignments.
# Mirrors the 11H pattern: ship the visual shape first behind a single
# ``is_wired`` flag, then PRs 4 and 5 flip it live and supply real
# selector options + handlers without re-laying-out the partial.
# PR 4 flipped the card live with seed-only library entries; PR 5
# extends the selector to include Personal RuleSets owned by the
# operator and adds the Build / Edit rules button.


@dataclass(frozen=True)
class RuleBasedSelectorOption:
    id: int
    label: str
    description: str
    exclude_self_reviews: bool
    is_seed: bool


@dataclass(frozen=True)
class RuleBasedLastGenerated:
    """One-line summary of the most recent rule-based generation.

    Reads from ``assignments.generated`` audit rows where
    ``context.mode == 'rule_based'``. Empty when no rule-based
    generation has happened yet on this session.

    ``rule_set_name`` is the name of the RuleSet at the time of the
    generation if the row is still resolvable (including
    soft-deleted Personal RuleSets — ``library.load_rule_set`` does
    not filter on ``deleted_at``). Falls back to ``None`` if the
    audit row predates the refs slot or the RuleSet has been hard-
    deleted in the past."""

    pair_count: int
    when: datetime
    rule_set_name: str | None = None
    assignment_count: int | None = None
    """Total Assignment rows written by the run (= pair_count
    × instrument count). Surfaced alongside the unique-pair count so
    operators on multi-instrument sessions can read both numbers
    inline. ``None`` for older audit rows that wrote ``new`` under a
    different key."""


@dataclass(frozen=True)
class RuleBasedCardContext:
    is_wired: bool
    assignment_count: int
    edit_url: str
    coming_in: str
    options: list[RuleBasedSelectorOption]
    selected_option_id: int | None
    selected_description: str
    selected_exclude_self_reviews: bool
    needs_confirm_replace: bool
    error_kind: str | None
    last_generated: RuleBasedLastGenerated | None


def build_rule_based_card_context(
    db: Session,
    review_session: ReviewSession,
    *,
    user: User | None = None,
    assignment_count: int,
    error_kind: str | None = None,
) -> RuleBasedCardContext:
    """Build the live context for the Rule Based card.

    PR 4 ships the seed-only library; ``user`` is accepted now so PR 5
    can extend the query to include the operator's Personal RuleSets
    without further surgery here.
    """

    from app.db.models import AuditEvent
    from app.services.rules import library

    options: list[RuleBasedSelectorOption] = []
    selected_option_id: int | None = None
    if user is not None:
        rule_sets = library.list_visible_rule_sets(db, user=user)
        for rs in rule_sets:
            revision = rs.current_revision
            exclude_self = (
                revision.exclude_self_reviews if revision is not None else True
            )
            options.append(
                RuleBasedSelectorOption(
                    id=rs.id,
                    label=rs.name,
                    description=rs.description or "",
                    exclude_self_reviews=exclude_self,
                    is_seed=rs.is_seed,
                )
            )
        # Default selection: the first seed in install order (Full
        # Matrix). The list is short enough that the operator scrolls
        # the dropdown either way; pinning the default to the
        # install-order-first row keeps the rendered UI free of any
        # special-casing on seed name.
        seed_options = [opt for opt in options if opt.is_seed]
        if seed_options:
            selected_option_id = seed_options[0].id
        elif options:
            selected_option_id = options[0].id

    # Resolve the selected option's description and exclude-self-
    # reviews default in Python, not Jinja. ``{% set %}`` inside a
    # ``{% for %}`` is loop-scoped in Jinja and resets when the loop
    # exits, which left ``selected_description`` blank on first
    # render and only populated after a JS-driven change event.
    selected_description = ""
    selected_exclude_self_reviews = True
    for option in options:
        if option.id == selected_option_id:
            selected_description = option.description
            selected_exclude_self_reviews = option.exclude_self_reviews
            break

    last_generated: RuleBasedLastGenerated | None = None
    last_event = db.execute(
        select(AuditEvent)
        .where(
            AuditEvent.session_id == review_session.id,
            AuditEvent.event_type == "assignments.generated",
        )
        .order_by(AuditEvent.created_at.desc())
    ).scalars().first()
    if last_event is not None and last_event.detail is not None:
        ctx = last_event.detail.get("context") or {}
        if ctx.get("mode") == "rule_based":
            counts = last_event.detail.get("counts") or {}
            pair_count = counts.get("pairs")
            if isinstance(pair_count, int):
                rule_set_name: str | None = None
                refs = last_event.detail.get("refs") or {}
                rule_set_id = refs.get("rule_set_id")
                if isinstance(rule_set_id, int):
                    loaded = library.load_rule_set(db, rule_set_id)
                    if loaded is not None:
                        rule_set_name = loaded[0].name
                new_count = counts.get("new")
                last_generated = RuleBasedLastGenerated(
                    pair_count=pair_count,
                    when=last_event.created_at,
                    rule_set_name=rule_set_name,
                    assignment_count=(
                        new_count if isinstance(new_count, int) else None
                    ),
                )

    if selected_option_id is not None:
        edit_url = (
            f"/operator/sessions/{review_session.id}"
            f"/assignments/rule-based/edit/{selected_option_id}"
        )
    else:
        # Inert-branch placeholder; PR 5 ships the editor and any
        # session with at least one seed always has a selected option.
        edit_url = (
            f"/operator/sessions/{review_session.id}"
            "/assignments/rule-based/edit/0"
        )

    return RuleBasedCardContext(
        is_wired=user is not None,
        assignment_count=assignment_count,
        edit_url=edit_url,
        coming_in="The Rule Based editor child page ships in Segment 13A PR 5.",
        options=options,
        selected_option_id=selected_option_id,
        selected_description=selected_description,
        selected_exclude_self_reviews=selected_exclude_self_reviews,
        needs_confirm_replace=assignment_count > 0,
        error_kind=error_kind,
        last_generated=last_generated,
    )


# Segment 13A PR 5a — RuleSet editor child page (read-only scaffold).
# Renders the loaded RuleSet's metadata + rule tree as the locked
# sentence-shaped surface form (segment plan §"Rule semantics surface
# form"). PR 5a only ships the read-only view + a Copy action that
# duplicates the loaded RuleSet into a new Personal-scope RuleSet.
# PR 5b adds the inline-JS predicate / quota editors that mutate
# the rule list before Save / Save As.


_COMBINATOR_LABELS: dict[str, str] = {
    "ALL_OF": "All of",
    "ANY_OF": "Any of",
    "PIPELINE": "In sequence",
}

_OPERATOR_PHRASES: dict[str, str] = {
    "equals": "is",
    "not_equals": "is not",
    "in": "is one of",
    "not_in": "is not one of",
    "matches": "matches the pattern",
    "not_matches": "does not match the pattern",
    "is_empty": "is empty",
    "is_not_empty": "is set",
    "same_as": "is the same as",
    "different_from": "is different from",
}

_COMPOSITE_PREFIXES: dict[str, str] = {
    "AND": "All of:",
    "OR": "Any of:",
    "NOT": "None of:",
}


# Segment 13A PR 5b — Picker option lists for the editor surface.
# Field picker: tag1/2/3 on each side only, per the locked editor
# concept (segment plan §"Editor concept" — "No operand picker for
# non-tag fields"). The schema's full ALLOWED_PREDICATE_FIELDS
# includes email; the editor's picker omits it because operator-
# authored rules don't reach for email comparisons (the engine's
# excludeSelfReviews desugar handles that case implicitly).
_FIELD_PICKER_VALUES: list[str] = [
    "reviewer.tag1",
    "reviewer.tag2",
    "reviewer.tag3",
    "reviewee.tag1",
    "reviewee.tag2",
    "reviewee.tag3",
]

# Operator picker labels match the locked sentence-form vocabulary
# (segment plan §"Rule semantics surface form").
_OPERATOR_PICKER_OPTIONS: list[tuple[str, str]] = [
    ("equals", "is"),
    ("not_equals", "is not"),
    ("in", "is one of"),
    ("not_in", "is not one of"),
    ("matches", "matches the pattern"),
    ("not_matches", "does not match the pattern"),
    ("is_empty", "is empty"),
    ("is_not_empty", "is set"),
    ("same_as", "is the same as"),
    ("different_from", "is different from"),
]

_KIND_PICKER_OPTIONS: list[tuple[str, str]] = [
    ("MATCH", "Include pairs where"),
    ("FILTER", "Exclude pairs where"),
    ("QUOTA", "Cap the number of"),
]

_COMBINATOR_PICKER_OPTIONS: list[tuple[str, str]] = [
    ("ALL_OF", "All of"),
    ("ANY_OF", "Any of"),
    ("PIPELINE", "In sequence"),
]

_QUOTA_SCOPE_OPTIONS: list[tuple[str, str]] = [
    ("PER_REVIEWEE", "reviewers per reviewee"),
    ("PER_REVIEWER", "reviewees per reviewer"),
]

_QUOTA_STRATEGY_OPTIONS: list[tuple[str, str]] = [
    ("RANDOM", "chosen randomly"),
    ("ROUND_ROBIN", "round-robin"),
]

_COMPOSITE_OP_OPTIONS: list[tuple[str, str]] = [
    ("AND", "All of:"),
    ("OR", "Any of:"),
    ("NOT", "None of:"),
]


@dataclass(frozen=True)
class RuleLine:
    """One rendered line on the read-only rule list.

    ``indent`` drives the left guideline / padding for nested
    composite children. ``text`` is the sentence-shaped rule body.
    ``kind`` lets the template apply per-kind classes (e.g. a
    different colour for FILTER vs MATCH if needed)."""

    indent: int
    text: str
    rule_id: str
    kind: str
    enabled: bool


@dataclass(frozen=True)
class EditableRule:
    """A rule rendered for in-place editing on Personal RuleSets.

    Carries the structured shape so the template can populate the
    field/operator/operand pickers and the quota-editor inputs.
    Composite rules render their op picker + an "Add child rule"
    button; their children render as full edit rows immediately
    after the parent with ``indent`` bumped (Segment 13A PR 5c).
    The JS serialiser walks the rendered DOM order and reconstructs
    the nested tree from each row's ``data-indent`` attribute.
    """

    rule_id: str
    kind: str  # MATCH / FILTER / QUOTA / COMPOSITE
    enabled: bool
    indent: int
    # MATCH / FILTER:
    field: str | None = None
    operator: str | None = None
    operand_text: str | None = None  # rendered as form-input value
    # QUOTA:
    quota_scope: str | None = None
    quota_min: int | None = None
    quota_max: int | None = None
    quota_strategy: str | None = None
    quota_seed: int | None = None
    # COMPOSITE:
    composite_op: str | None = None


@dataclass(frozen=True)
class LibraryEntry:
    """One row in the editor's Library panel (Segment 13A PR 10).

    Seed entries are read-only and have ``delete_url=None``;
    Personal entries owned by the caller carry a ``delete_url``
    that submits to ``POST /assignments/rule-based/delete``."""

    id: int
    name: str
    description: str
    is_seed: bool
    is_active: bool
    edit_url: str
    delete_url: str | None


@dataclass(frozen=True)
class RuleBasedEditorContext:
    rule_set_id: int
    rule_set_name: str
    rule_set_description: str
    is_seed: bool
    is_owner: bool
    """True when the loaded RuleSet is a Personal RuleSet owned by
    the current user. Drives ``editable`` below — seeds render
    read-only with a Copy form; Personal renders editable with a
    Save As form (and PR 6's Save in-place)."""
    editable: bool
    """Editor controls render live when True. False on seeds and on
    any non-owner view."""
    combinator: str
    combinator_label: str
    exclude_self_reviews: bool
    seed_value: int | None
    # Read-only sentence-shaped rule lines (used in non-editable mode).
    rule_lines: list[RuleLine]
    # Edit-mode rule list (one entry per top-level rule, plus child
    # rules for composites flattened with indent for visual nesting).
    editable_rules: list[EditableRule]
    copy_url: str
    save_as_url: str
    save_url: str
    rename_url: str
    delete_url: str
    back_url: str
    revision_no: int
    saved_flash: bool
    renamed_flash: bool
    preview: object | None  # ``RulePreview`` from app.services.rules.preview
    """Read-only live preview rendered server-side on initial load.
    The editor's right column renders this synchronously; a JS hook
    refetches on form-element edits via POST /preview."""
    error_kind: str | None
    error_message: str | None
    # Picker option lists exposed to the template.
    field_options: list[str]
    operator_options: list[tuple[str, str]]
    kind_options: list[tuple[str, str]]
    combinator_options: list[tuple[str, str]]
    quota_scope_options: list[tuple[str, str]]
    quota_strategy_options: list[tuple[str, str]]
    composite_op_options: list[tuple[str, str]]
    # Segment 13A PR 9 — source picker on the Copy form.
    source_options: list[RuleBasedSelectorOption]
    """Visible RuleSets (seeds + caller-owned Personal) the
    operator can pick as the *source* for a Copy without leaving
    the editor. Same dataclass as the Rule Based card's selector;
    the template's source-picker JS reuses the
    ``data-description`` / ``data-name`` attributes for inline
    description + name-suggestion updates on selector change."""
    # Segment 13A PR 10 — Library panel inside the editor.
    library_seeds: list["LibraryEntry"]
    library_personal: list["LibraryEntry"]
    """Two lists drive the Library panel above the main editor
    card. Seeds render in install order; Personal renders the
    caller-owned RuleSets only. Each entry has ``is_active=True``
    on the currently-loaded RuleSet so the panel can highlight it.
    Personal entries carry a delete URL so the panel can render
    inline soft-delete forms reusing PR 6's
    ``POST /assignments/rule-based/delete``."""


def _render_field_reference(dotted: str) -> str:
    """``reviewer.tag1`` → ``reviewer tag1``. The dotted operator-
    facing form lives in the schema; the editor surface renders the
    side and attr space-separated so the sentence reads cleanly
    without an apostrophe (which Jinja's auto-escape would render as
    ``&#39;``)."""

    side, attr = dotted.split(".", 1)
    return f"{side} {attr}"


def _render_predicate_sentence(predicate: dict[str, Any]) -> str:
    field = predicate.get("field", "")
    op = predicate.get("operator", "")
    operand = predicate.get("operand")
    field_label = _render_field_reference(field) if field else "?"
    op_phrase = _OPERATOR_PHRASES.get(op, op)

    if op in ("is_empty", "is_not_empty"):
        return f"{field_label} {op_phrase}"

    if op in ("same_as", "different_from"):
        if isinstance(operand, str) and "." in operand:
            return f"{field_label} {op_phrase} {_render_field_reference(operand)}"
        return f"{field_label} {op_phrase} {operand!r}"

    if op in ("in", "not_in"):
        if isinstance(operand, list):
            items = ", ".join(repr(item) for item in operand)
            return f"{field_label} {op_phrase} [{items}]"
        return f"{field_label} {op_phrase} {operand!r}"

    if op in ("matches", "not_matches"):
        return f"{field_label} {op_phrase} /{operand}/"

    # equals / not_equals — literal scalar.
    return f"{field_label} {op_phrase} {operand!r}"


def _render_quota_sentence(rule: dict[str, Any]) -> str:
    scope = rule.get("scope", "")
    axis_target = "reviewee" if scope == "PER_REVIEWEE" else "reviewer"
    axis_obligor = "reviewer" if scope == "PER_REVIEWEE" else "reviewee"
    min_v = rule.get("min")
    max_v = rule.get("max")
    selection = rule.get("selection") or {}
    strategy = selection.get("strategy", "ROUND_ROBIN")
    seed = selection.get("seed")

    bound: str
    if min_v is not None and max_v is not None:
        bound = f"{min_v} to {max_v}" if min_v != max_v else f"{min_v}"
    elif max_v is not None:
        bound = f"up to {max_v}"
    elif min_v is not None:
        bound = f"at least {min_v}"
    else:
        bound = "any number of"

    strategy_phrase = (
        "chosen randomly" if strategy == "RANDOM" else "round-robin"
    )
    if strategy == "RANDOM" and seed is not None:
        strategy_phrase = f"{strategy_phrase} (seed={seed})"

    return (
        f"Cap at {bound} {axis_obligor}{'s' if bound not in ('1', 'at least 1') else ''} "
        f"per {axis_target}, {strategy_phrase}"
    )


def _flatten_rule_lines(
    rules: list[dict[str, Any]], *, indent: int = 0
) -> list[RuleLine]:
    lines: list[RuleLine] = []
    for rule in rules:
        kind = rule.get("kind", "")
        rule_id = str(rule.get("id", ""))
        enabled = bool(rule.get("enabled", True))

        if kind in ("MATCH", "FILTER"):
            verb = (
                "Include pairs where"
                if kind == "MATCH"
                else "Exclude pairs where"
            )
            sentence = f"{verb} {_render_predicate_sentence(rule.get('predicate', {}))}."
            lines.append(
                RuleLine(
                    indent=indent,
                    text=sentence,
                    rule_id=rule_id,
                    kind=kind,
                    enabled=enabled,
                )
            )
        elif kind == "QUOTA":
            lines.append(
                RuleLine(
                    indent=indent,
                    text=_render_quota_sentence(rule) + ".",
                    rule_id=rule_id,
                    kind=kind,
                    enabled=enabled,
                )
            )
        elif kind == "COMPOSITE":
            op = rule.get("op", "AND")
            prefix = _COMPOSITE_PREFIXES.get(op, "All of:")
            lines.append(
                RuleLine(
                    indent=indent,
                    text=prefix,
                    rule_id=rule_id,
                    kind=kind,
                    enabled=enabled,
                )
            )
            lines.extend(
                _flatten_rule_lines(
                    rule.get("rules") or [], indent=indent + 1
                )
            )
        else:
            lines.append(
                RuleLine(
                    indent=indent,
                    text=f"(unknown rule kind {kind!r})",
                    rule_id=rule_id,
                    kind=kind,
                    enabled=enabled,
                )
            )
    return lines


def _operand_to_text(rule: dict[str, Any]) -> str | None:
    """Render the operand value for a form input.

    ``in`` / ``not_in`` operands are stored as ``list[str]`` and
    presented as a comma-separated text field that the JS serialiser
    splits back on submit. Other operators carry the operand as a
    string (or None for nullary operators)."""

    predicate = rule.get("predicate") or {}
    operator = predicate.get("operator")
    operand = predicate.get("operand")
    if operator in ("is_empty", "is_not_empty"):
        return None
    if operator in ("in", "not_in"):
        if isinstance(operand, list):
            return ", ".join(str(item) for item in operand)
        return ""
    if operand is None:
        return ""
    return str(operand)


def _flatten_editable_rules(
    rules: list[dict[str, Any]], *, indent: int = 0
) -> list[EditableRule]:
    """Walk the rule tree and emit per-rule edit-form rows.

    Composite rules emit one parent row + one full edit row per
    composite child (Segment 13A PR 5c). The JS serialiser walks
    rendered DOM order and reconstructs the nested tree from each
    row's ``data-indent`` attribute — children are the consecutive
    rows with strictly greater indent following a composite.
    """

    out: list[EditableRule] = []
    for rule in rules:
        kind = str(rule.get("kind", ""))
        rule_id = str(rule.get("id", ""))
        enabled = bool(rule.get("enabled", True))
        if kind in ("MATCH", "FILTER"):
            predicate = rule.get("predicate") or {}
            out.append(
                EditableRule(
                    rule_id=rule_id,
                    kind=kind,
                    enabled=enabled,
                    indent=indent,
                    field=predicate.get("field"),
                    operator=predicate.get("operator"),
                    operand_text=_operand_to_text(rule),
                )
            )
        elif kind == "QUOTA":
            selection = rule.get("selection") or {}
            out.append(
                EditableRule(
                    rule_id=rule_id,
                    kind=kind,
                    enabled=enabled,
                    indent=indent,
                    quota_scope=rule.get("scope"),
                    quota_min=rule.get("min"),
                    quota_max=rule.get("max"),
                    quota_strategy=selection.get("strategy"),
                    quota_seed=selection.get("seed"),
                )
            )
        elif kind == "COMPOSITE":
            children = rule.get("rules") or []
            out.append(
                EditableRule(
                    rule_id=rule_id,
                    kind=kind,
                    enabled=enabled,
                    indent=indent,
                    composite_op=rule.get("op"),
                )
            )
            out.extend(
                _flatten_editable_rules(children, indent=indent + 1)
            )
    return out


def build_rule_based_editor_context(
    review_session: ReviewSession,
    *,
    db: Session,
    rule_set,  # RuleSet (avoid forward ref noise)
    revision,  # RuleSetRevision
    user: User,
    error_kind: str | None = None,
    error_message: str | None = None,
    saved_flash: bool = False,
    renamed_flash: bool = False,
    preview: object | None = None,
) -> RuleBasedEditorContext:
    """Build the editor child page's render context.

    Editable mode renders form-element rule rows + a hidden
    ``rules_json`` field that the inline JS keeps in sync with the
    visible controls; submitting the Save As form POSTs the
    serialised tree (segment 13A PR 5b). Read-only mode (seeds
    or non-owner views) keeps PR 5a's sentence-shaped rule lines.
    """

    is_seed = bool(rule_set.is_seed)
    is_owner = not is_seed and rule_set.owner_user_id == user.id
    editable = is_owner

    rules_json = revision.rules_json or []
    rule_lines = _flatten_rule_lines(rules_json)
    editable_rules = (
        _flatten_editable_rules(rules_json) if editable else []
    )

    # Segment 13A PR 9 — source picker. List every visible RuleSet
    # so the operator can pick a source for the Copy form without
    # leaving the editor.
    # Segment 13A PR 10 — Library panel. Build the per-row entries
    # for the Library card from the same query.
    from app.services.rules import library

    source_options: list[RuleBasedSelectorOption] = []
    library_seeds: list[LibraryEntry] = []
    library_personal: list[LibraryEntry] = []
    for rs in library.list_visible_rule_sets(db, user=user):
        rev = rs.current_revision
        exclude_self = (
            rev.exclude_self_reviews if rev is not None else True
        )
        source_options.append(
            RuleBasedSelectorOption(
                id=rs.id,
                label=rs.name,
                description=rs.description or "",
                exclude_self_reviews=exclude_self,
                is_seed=rs.is_seed,
            )
        )
        edit_url = (
            f"/operator/sessions/{review_session.id}"
            f"/assignments/rule-based/edit/{rs.id}"
        )
        delete_url: str | None = None
        if not rs.is_seed and rs.owner_user_id == user.id:
            delete_url = (
                f"/operator/sessions/{review_session.id}"
                "/assignments/rule-based/delete"
            )
        entry = LibraryEntry(
            id=rs.id,
            name=rs.name,
            description=rs.description or "",
            is_seed=rs.is_seed,
            is_active=(rs.id == rule_set.id),
            edit_url=edit_url,
            delete_url=delete_url,
        )
        if rs.is_seed:
            library_seeds.append(entry)
        else:
            library_personal.append(entry)
    return RuleBasedEditorContext(
        rule_set_id=rule_set.id,
        rule_set_name=rule_set.name,
        rule_set_description=rule_set.description or "",
        is_seed=is_seed,
        is_owner=is_owner,
        editable=editable,
        combinator=revision.combinator,
        combinator_label=_COMBINATOR_LABELS.get(
            revision.combinator, revision.combinator
        ),
        exclude_self_reviews=bool(revision.exclude_self_reviews),
        seed_value=revision.seed,
        rule_lines=rule_lines,
        editable_rules=editable_rules,
        copy_url=(
            f"/operator/sessions/{review_session.id}"
            "/assignments/rule-based/copy"
        ),
        save_as_url=(
            f"/operator/sessions/{review_session.id}"
            "/assignments/rule-based/save-as"
        ),
        save_url=(
            f"/operator/sessions/{review_session.id}"
            "/assignments/rule-based/save"
        ),
        rename_url=(
            f"/operator/sessions/{review_session.id}"
            "/assignments/rule-based/rename"
        ),
        delete_url=(
            f"/operator/sessions/{review_session.id}"
            "/assignments/rule-based/delete"
        ),
        revision_no=revision.revision_no,
        saved_flash=saved_flash,
        renamed_flash=renamed_flash,
        preview=preview,
        back_url=f"/operator/sessions/{review_session.id}/assignments",
        error_kind=error_kind,
        error_message=error_message,
        field_options=list(_FIELD_PICKER_VALUES),
        operator_options=list(_OPERATOR_PICKER_OPTIONS),
        kind_options=list(_KIND_PICKER_OPTIONS),
        combinator_options=list(_COMBINATOR_PICKER_OPTIONS),
        quota_scope_options=list(_QUOTA_SCOPE_OPTIONS),
        quota_strategy_options=list(_QUOTA_STRATEGY_OPTIONS),
        composite_op_options=list(_COMPOSITE_OP_OPTIONS),
        source_options=source_options,
        library_seeds=library_seeds,
        library_personal=library_personal,
    )


# Segment 13A-1 — single-card Rule Builder page.
#
# PR 1 shipped the read-only scaffold. PR 2 extends the same context
# with editable form state for Personal RuleSets and "draft from
# source" state for Copy. PR 3 wires the blank-draft sentinel for
# real. The dataclass keeps both surfaces — read-only seed view + the
# editable Personal form — branchable from a single template.

# Sentinel id used in dropdown / query params to mean "+ New blank
# RuleSet". An int doesn't collide with any real RuleSet primary key
# and round-trips through ``int`` query params unchanged.
RULE_BUILDER_BLANK_SENTINEL_ID = -1


@dataclass(frozen=True)
class RuleBuilderOption:
    """One entry in the Rule Builder dropdown.

    ``id`` is the RuleSet primary key for real entries, or
    ``RULE_BUILDER_BLANK_SENTINEL_ID`` for the "+ New blank RuleSet"
    sentinel that PR 3 wires up. ``is_blank_sentinel`` lets the
    template branch on the sentinel without comparing magic numbers.
    """

    id: int
    label: str
    is_seed: bool
    is_personal: bool
    is_blank_sentinel: bool


# Default description seeded into the textarea on a fresh Copy /
# blank draft. Operators are expected to overwrite this with a
# friendlier explanation; saved-Personal selections preserve their
# stored description across reloads.
RULE_BUILDER_DRAFT_DEFAULT_DESCRIPTION = "User created ruleset"


@dataclass(frozen=True)
class AvailableRuleSetEntry:
    """One row in the sibling "Available rulesets" card.

    Carries the description so the card can show the operator-facing
    helper sentence next to the name. ``is_active`` lets the
    template highlight the row matching the current Rule Builder
    selection."""

    id: int
    name: str
    description: str
    is_seed: bool
    is_personal: bool
    is_active: bool


@dataclass(frozen=True)
class RuleBuilderContext:
    """Render context for the Rule Builder single-card page.

    Three render branches:

    - **Seeded RuleSet (read-only):** ``rule_lines`` carry the
      sentence-shaped predicates; only the Copy action is exposed.
    - **Saved Personal RuleSet (editable):** ``editable_rules`` +
      ``rules_json_initial`` populate PR 5b/5c's inline form; full
      Copy + Save + Cancel + Delete action row.
    - **Unsaved draft from a source (Copy):** rules / combinator /
      seed are loaded from the source RuleSet but the row isn't
      persisted yet — Save creates it (Save-As semantics). No Delete
      (nothing to delete).

    PR 3 ships the blank-sentinel branch (``selected_is_blank=True``
    with empty rules) on the same context.
    """

    options: list[RuleBuilderOption]
    selected_id: int  # RuleSet pk, RULE_BUILDER_BLANK_SENTINEL_ID, or 0 for draft
    selected_is_blank: bool
    selected_is_seed: bool
    selected_is_personal: bool
    selected_is_draft: bool
    """True when the current selection is an unsaved draft (Copy
    from a source). The form has no ``rule_set_id`` and Save creates
    the row from scratch."""
    editable: bool
    """True for saved-Personal and unsaved-draft branches; drives
    the editable rule-form vs. read-only sentence rendering."""
    name: str
    description: str
    combinator: str  # e.g., "ALL_OF" — form select value
    combinator_label: str  # e.g., "All of" — read-only display
    exclude_self_reviews: bool
    seed_value: int | None
    rule_lines: list[RuleLine]
    editable_rules: list[EditableRule]
    rules_json_initial: str
    """JSON-serialised initial value for the form's hidden
    ``rules_json`` field. The PR 5b/5c JS keeps it in sync with the
    visible controls before submit."""
    draft_source_id: int | None
    """For a draft branch: the source RuleSet id that Save-As pins
    in the audit's ``refs.source_rule_set_id`` slot."""
    draft_auto_name: bool
    """True iff the draft name still equals the literal "Copy of …"
    default. The Save route uses this to decide whether to apply
    the auto-suffix on collision (``" (n)"``) — operator-edited
    names get a 422 instead so a duplicate isn't created silently."""
    previous_id: int | None
    """For a draft branch: the dropdown selection the operator was
    on before clicking Copy. Cancel reverts to this id."""
    can_save: bool
    can_cancel: bool
    can_delete: bool
    can_copy: bool
    copy_url: str
    save_url: str
    delete_url: str
    cancel_url: str
    page_url: str
    error_kind: str | None
    error_message: str | None
    saved_flash: bool
    # Picker option lists for the editable form. Lifted from the
    # PR 5b/5c module-level tuples so the new card reuses the same
    # vocabulary (and the JS serialiser sees the same field/operator
    # values).
    field_options: list[str]
    operator_options: list[tuple[str, str]]
    kind_options: list[tuple[str, str]]
    combinator_options: list[tuple[str, str]]
    quota_scope_options: list[tuple[str, str]]
    quota_strategy_options: list[tuple[str, str]]
    composite_op_options: list[tuple[str, str]]
    available_rulesets: list[AvailableRuleSetEntry]
    """Rows for the sibling "Available rulesets" card. Same ordering
    as the dropdown — seeds first in install order, then caller-
    owned Personal."""


_RULE_BUILDER_ERROR_MESSAGES: dict[str, str] = {
    "empty_name": "Pick a name for the new RuleSet before clicking Save.",
    "malformed_json": "The edited rule list could not be parsed.",
    "validation": (
        "One or more rules failed validation. Check operator-"
        "operand pairings, regexes, and quota bounds."
    ),
    "bad_combinator": "Pick a combinator (All / Any / In sequence).",
    "bad_seed": "RuleSet seed must be an integer.",
    "name_collision": (
        "A RuleSet with that name already exists in your library. "
        "Pick a different name and try again."
    ),
    "needs_delete_confirm": (
        "Delete not confirmed. Tick the confirm checkbox before "
        "clicking Delete."
    ),
    "empty_rules": (
        "Add at least one rule before saving the new RuleSet."
    ),
}


def _rule_builder_blank_draft(
    review_session: ReviewSession,
    options: list[RuleBuilderOption],
    *,
    error_kind: str | None,
    saved_flash: bool,
    name_override: str | None = None,
    description_override: str | None = None,
    available_rulesets: list[AvailableRuleSetEntry] | None = None,
) -> RuleBuilderContext:
    """Live blank-draft context (Segment 13A-1 PR 3).

    Replaces the PR 1/PR 2 placeholder branch — selecting
    ``+ New blank RuleSet`` from the dropdown now renders an
    editable form with zero rules, default combinator ``ALL_OF``,
    and the auto-generated name ``"New RuleSet"``. Save is gated
    server-side until at least one rule exists; the Save button is
    also gated client-side via the inline JS in
    ``_rule_builder_card.html``."""

    return RuleBuilderContext(
        options=options,
        selected_id=RULE_BUILDER_BLANK_SENTINEL_ID,
        selected_is_blank=True,
        selected_is_seed=False,
        selected_is_personal=False,
        selected_is_draft=True,
        editable=True,
        name=name_override or "New RuleSet",
        description=(
            description_override
            if description_override is not None
            else RULE_BUILDER_DRAFT_DEFAULT_DESCRIPTION
        ),
        combinator="ALL_OF",
        combinator_label=_COMBINATOR_LABELS.get("ALL_OF", "All of"),
        exclude_self_reviews=True,
        seed_value=None,
        rule_lines=[],
        editable_rules=[],
        rules_json_initial="[]",
        draft_source_id=None,
        draft_auto_name=False,
        previous_id=None,
        can_save=True,
        can_cancel=True,
        can_delete=False,
        can_copy=False,
        copy_url=_rule_builder_url(review_session, "copy"),
        save_url=_rule_builder_url(review_session, "save"),
        delete_url=_rule_builder_url(review_session, "delete"),
        cancel_url=_rule_builder_url(review_session, ""),
        page_url=_rule_builder_url(review_session, ""),
        error_kind=error_kind,
        error_message=_RULE_BUILDER_ERROR_MESSAGES.get(error_kind or ""),
        saved_flash=saved_flash,
        field_options=list(_FIELD_PICKER_VALUES),
        operator_options=list(_OPERATOR_PICKER_OPTIONS),
        kind_options=list(_KIND_PICKER_OPTIONS),
        combinator_options=list(_COMBINATOR_PICKER_OPTIONS),
        quota_scope_options=list(_QUOTA_SCOPE_OPTIONS),
        quota_strategy_options=list(_QUOTA_STRATEGY_OPTIONS),
        composite_op_options=list(_COMPOSITE_OP_OPTIONS),
        available_rulesets=available_rulesets or [],
    )


# Back-compat alias: the PR 1/PR 2 default-blank fallback is now the
# same shape as the live blank-draft branch. Defensive fallbacks
# (no visible RuleSets, stale id) reuse it.
_rule_builder_default_blank = _rule_builder_blank_draft


def _rule_builder_url(review_session: ReviewSession, suffix: str) -> str:
    """Build a path under ``/assignments/rule-based-editor``.

    Empty ``suffix`` yields the bare page URL; otherwise returns
    ``/<suffix>``. Centralised so the route module and the context
    builder stay in lockstep."""

    base = (
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based-editor"
    )
    return f"{base}/{suffix}" if suffix else base


def _build_rule_builder_options(
    db: Session, *, user: User
) -> tuple[list[RuleBuilderOption], list, list, dict[int, object]]:
    """Pull the visible RuleSets once and shape them into the
    dropdown options + the seed/personal lists used for fallback
    selection. Returns ``(options, seeds, personal, by_id)``."""

    from app.services.rules import library

    visible = list(library.list_visible_rule_sets(db, user=user))
    seeds = [rs for rs in visible if rs.is_seed]
    personal = [rs for rs in visible if not rs.is_seed]

    options: list[RuleBuilderOption] = []
    for rs in seeds:
        options.append(
            RuleBuilderOption(
                id=rs.id,
                label=rs.name,
                is_seed=True,
                is_personal=False,
                is_blank_sentinel=False,
            )
        )
    for rs in personal:
        options.append(
            RuleBuilderOption(
                id=rs.id,
                label=rs.name,
                is_seed=False,
                is_personal=True,
                is_blank_sentinel=False,
            )
        )
    options.append(
        RuleBuilderOption(
            id=RULE_BUILDER_BLANK_SENTINEL_ID,
            label="+ New blank RuleSet",
            is_seed=False,
            is_personal=False,
            is_blank_sentinel=True,
        )
    )
    by_id = {rs.id: rs for rs in visible}
    return options, seeds, personal, by_id


def _build_available_rulesets(
    seeds: list, personal: list, *, active_id: int | None
) -> list[AvailableRuleSetEntry]:
    """Shape the visible RuleSet list for the sibling
    "Available rulesets" card. Same ordering as the dropdown:
    seeds first in install order, then caller-owned Personal.
    ``active_id`` is the currently-selected RuleSet id (or None
    when the operator is on a draft / blank); the matching row
    renders highlighted."""

    rows: list[AvailableRuleSetEntry] = []
    for rs in seeds:
        rows.append(
            AvailableRuleSetEntry(
                id=rs.id,
                name=rs.name,
                description=rs.description or "",
                is_seed=True,
                is_personal=False,
                is_active=(active_id == rs.id),
            )
        )
    for rs in personal:
        rows.append(
            AvailableRuleSetEntry(
                id=rs.id,
                name=rs.name,
                description=rs.description or "",
                is_seed=False,
                is_personal=True,
                is_active=(active_id == rs.id),
            )
        )
    return rows


def build_rule_builder_context(
    review_session: ReviewSession,
    *,
    db: Session,
    user: User,
    selected_id: int | None = None,
    as_draft_from: int | None = None,
    previous_id: int | None = None,
    error_kind: str | None = None,
    saved_flash: bool = False,
    draft_name_override: str | None = None,
) -> RuleBuilderContext:
    """Build the Rule Builder card context.

    ``selected_id`` resolves a real RuleSet (or the blank sentinel
    when equal to ``RULE_BUILDER_BLANK_SENTINEL_ID``). When
    ``as_draft_from`` is set, the page renders an *unsaved draft*
    cloning the source RuleSet's rules + combinator + seed, with the
    name auto-generated as ``"Copy of <source>"`` (locked decision
    #5). ``previous_id`` is the dropdown selection the operator was
    on before clicking Copy; the Cancel button reverts to it.

    Stale or non-visible ids fall back to the first seed — refresh
    must always render rather than 404, since the URL bar is
    intentionally clean of selection state.
    """

    from app.services.rules import library

    options, seeds, _personal, by_id = _build_rule_builder_options(db, user=user)

    if as_draft_from is not None:
        return _build_draft_context(
            review_session,
            db=db,
            options=options,
            source_id=as_draft_from,
            previous_id=previous_id,
            user=user,
            error_kind=error_kind,
            saved_flash=saved_flash,
            draft_name_override=draft_name_override,
            seeds=seeds,
            personal=_personal,
        )

    if selected_id == RULE_BUILDER_BLANK_SENTINEL_ID:
        return _rule_builder_blank_draft(
            review_session,
            options,
            error_kind=error_kind,
            saved_flash=saved_flash,
            available_rulesets=_build_available_rulesets(
                seeds, _personal, active_id=None
            ),
        )

    if selected_id is None or selected_id not in by_id:
        if seeds:
            selected_id = seeds[0].id
        else:
            return _rule_builder_blank_draft(
                review_session,
                options,
                error_kind=error_kind,
                saved_flash=saved_flash,
                available_rulesets=_build_available_rulesets(
                    seeds, _personal, active_id=None
                ),
            )

    loaded = library.load_rule_set(db, selected_id)
    if loaded is None:
        if seeds:
            selected_id = seeds[0].id
            loaded = library.load_rule_set(db, selected_id)
        if loaded is None:
            return _rule_builder_blank_draft(
                review_session,
                options,
                error_kind=error_kind,
                saved_flash=saved_flash,
                available_rulesets=_build_available_rulesets(
                    seeds, _personal, active_id=None
                ),
            )
    rule_set, revision = loaded

    rules = revision.rules_json or []
    is_seed = bool(rule_set.is_seed)
    is_personal = (
        not is_seed
        and rule_set.owner_user_id == user.id
        and rule_set.deleted_at is None
    )
    editable = is_personal

    return RuleBuilderContext(
        options=options,
        selected_id=rule_set.id,
        selected_is_blank=False,
        selected_is_seed=is_seed,
        selected_is_personal=is_personal,
        selected_is_draft=False,
        editable=editable,
        name=rule_set.name,
        description=rule_set.description or "",
        combinator=revision.combinator,
        combinator_label=_COMBINATOR_LABELS.get(
            revision.combinator, revision.combinator
        ),
        exclude_self_reviews=bool(revision.exclude_self_reviews),
        seed_value=revision.seed,
        rule_lines=_flatten_rule_lines(rules),
        editable_rules=_flatten_editable_rules(rules) if editable else [],
        rules_json_initial=_dump_rules_json(rules) if editable else "[]",
        draft_source_id=None,
        draft_auto_name=False,
        previous_id=None,
        can_save=editable,
        can_cancel=editable,
        can_delete=editable,
        can_copy=True,
        copy_url=_rule_builder_url(review_session, "copy"),
        save_url=_rule_builder_url(review_session, "save"),
        delete_url=_rule_builder_url(review_session, "delete"),
        cancel_url=_rule_builder_url(review_session, "")
        + f"?rule_set_id={rule_set.id}",
        page_url=_rule_builder_url(review_session, ""),
        error_kind=error_kind,
        error_message=_RULE_BUILDER_ERROR_MESSAGES.get(error_kind or ""),
        saved_flash=saved_flash,
        field_options=list(_FIELD_PICKER_VALUES),
        operator_options=list(_OPERATOR_PICKER_OPTIONS),
        kind_options=list(_KIND_PICKER_OPTIONS),
        combinator_options=list(_COMBINATOR_PICKER_OPTIONS),
        quota_scope_options=list(_QUOTA_SCOPE_OPTIONS),
        quota_strategy_options=list(_QUOTA_STRATEGY_OPTIONS),
        composite_op_options=list(_COMPOSITE_OP_OPTIONS),
        available_rulesets=_build_available_rulesets(
            seeds, _personal, active_id=rule_set.id
        ),
    )


def _build_draft_context(
    review_session: ReviewSession,
    *,
    db: Session,
    options: list[RuleBuilderOption],
    source_id: int,
    previous_id: int | None,
    user: User,
    error_kind: str | None,
    saved_flash: bool,
    draft_name_override: str | None,
    draft_description_override: str | None = None,
    seeds: list,
    personal: list,
) -> RuleBuilderContext:
    """Render the page as an unsaved draft cloning ``source_id``'s
    rules + combinator + seed (Copy from seed/Personal). Falls back
    to the default selection when the source can't be resolved or
    isn't visible to the caller — same posture as a stale
    ``rule_set_id`` query param."""

    from app.services.rules import library

    loaded = library.load_rule_set(db, source_id)
    if loaded is None:
        if seeds:
            return build_rule_builder_context(
                review_session,
                db=db,
                user=user,
                selected_id=seeds[0].id,
                error_kind=error_kind,
                saved_flash=saved_flash,
            )
        return _rule_builder_blank_draft(
            review_session,
            options,
            error_kind=error_kind,
            saved_flash=saved_flash,
            available_rulesets=_build_available_rulesets(
                seeds, personal, active_id=None
            ),
        )
    source_rule_set, source_revision = loaded
    if (
        not source_rule_set.is_seed
        and source_rule_set.owner_user_id != user.id
    ):
        # Non-visible Personal RuleSet — redirect to default rather
        # than expose its existence via 403. Matches the
        # ``rule_set_id`` fallback posture.
        if seeds:
            return build_rule_builder_context(
                review_session,
                db=db,
                user=user,
                selected_id=seeds[0].id,
                error_kind=error_kind,
                saved_flash=saved_flash,
            )
        return _rule_builder_blank_draft(
            review_session,
            options,
            error_kind=error_kind,
            saved_flash=saved_flash,
            available_rulesets=_build_available_rulesets(
                seeds, personal, active_id=None
            ),
        )

    rules = source_revision.rules_json or []
    auto_name = f"Copy of {source_rule_set.name}"
    rendered_name = draft_name_override or auto_name
    rendered_description = (
        draft_description_override
        if draft_description_override is not None
        else RULE_BUILDER_DRAFT_DEFAULT_DESCRIPTION
    )
    cancel_url = _rule_builder_url(review_session, "")
    if previous_id is not None and previous_id > 0:
        cancel_url = f"{cancel_url}?rule_set_id={previous_id}"

    return RuleBuilderContext(
        options=options,
        # Drafts have no row in the DB yet; the dropdown stays on
        # the source's id so the operator can see what they cloned.
        selected_id=source_rule_set.id,
        selected_is_blank=False,
        selected_is_seed=False,
        selected_is_personal=False,
        selected_is_draft=True,
        editable=True,
        name=rendered_name,
        description=rendered_description,
        combinator=source_revision.combinator,
        combinator_label=_COMBINATOR_LABELS.get(
            source_revision.combinator, source_revision.combinator
        ),
        exclude_self_reviews=bool(source_revision.exclude_self_reviews),
        seed_value=source_revision.seed,
        rule_lines=_flatten_rule_lines(rules),
        editable_rules=_flatten_editable_rules(rules),
        rules_json_initial=_dump_rules_json(rules),
        draft_source_id=source_rule_set.id,
        draft_auto_name=(rendered_name == auto_name),
        previous_id=previous_id,
        can_save=True,
        can_cancel=True,
        can_delete=False,
        can_copy=False,
        copy_url=_rule_builder_url(review_session, "copy"),
        save_url=_rule_builder_url(review_session, "save"),
        delete_url=_rule_builder_url(review_session, "delete"),
        cancel_url=cancel_url,
        page_url=_rule_builder_url(review_session, ""),
        error_kind=error_kind,
        error_message=_RULE_BUILDER_ERROR_MESSAGES.get(error_kind or ""),
        saved_flash=saved_flash,
        field_options=list(_FIELD_PICKER_VALUES),
        operator_options=list(_OPERATOR_PICKER_OPTIONS),
        kind_options=list(_KIND_PICKER_OPTIONS),
        combinator_options=list(_COMBINATOR_PICKER_OPTIONS),
        quota_scope_options=list(_QUOTA_SCOPE_OPTIONS),
        quota_strategy_options=list(_QUOTA_STRATEGY_OPTIONS),
        composite_op_options=list(_COMPOSITE_OP_OPTIONS),
        available_rulesets=_build_available_rulesets(
            seeds, personal, active_id=source_rule_set.id
        ),
    )


def _dump_rules_json(rules: list[dict[str, Any]]) -> str:
    """Serialise the rule tree for the form's hidden ``rules_json``
    field. The PR 5b/5c JS reads this on first paint and keeps it
    in sync with the visible controls."""

    import json as _json

    return _json.dumps(rules, separators=(",", ":"))

