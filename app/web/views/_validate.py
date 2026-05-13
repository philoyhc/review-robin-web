"""Validate page view-shape adapter (Segment 11G PR A) — the
read-only deep-dive into setup readiness at
``/operator/sessions/{id}/validate``.

Slice 8 of the §12.B ladder (``guide/archive/major_refactor.md``).

Owns the ``SetupCoverageRow`` / ``SeverityChip`` /
``IssueSourceGroup`` / ``ValidateContext`` dataclasses, the
lifecycle-aware secondary-line copy (``validate_lifecycle_copy``),
the verdict / severity-tally / per-source-count helpers, and the
context builder ``build_validate_context`` that wires
``validation.validate_session_setup`` output into the page shape.

Source range in pre-PR-8 ``_legacy.py``: lines 33-392.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Instrument, ReviewSession
from app.services import assignments, csv_imports


# --------------------------------------------------------------------------- #
# Setup gate vs. Operations gate (Segment 15E PR 2)
# --------------------------------------------------------------------------- #
#
# Each registered ``ValidationRule`` belongs to one of two gates:
#
# - **Setup gate** — structural readiness rules an operator fixes
#   on the Setup-row pages (session metadata, rosters, instrument
#   shape, email template).
# - **Operations gate** — readiness rules about generated
#   assignments (the workflow card's Generate / Activate buttons
#   rely on these).
#
# Source axis alone isn't enough: ``instruments``-source rules
# split across both gates (``instruments.no_fields`` is structural
# Setup, while ``instruments.stale_generated`` is post-Generate
# Operations). Hence an explicit per-key mapping.
#
# Display-only split. The Validate page renders one section per
# gate; PR 3's workflow card uses the same mapping to decide
# which rules its Generate-setup-gate / operations-gate check
# considers.

Gate = Literal["setup", "operations"]


_RULE_KEY_GATE: dict[str, Gate] = {
    "session.no_name": "setup",
    "session.no_code": "setup",
    "reviewers.empty": "setup",
    "reviewers.duplicate_email": "setup",
    "reviewees.empty": "setup",
    "reviewees.duplicate_id": "setup",
    "instruments.no_fields": "setup",
    "instruments.no_display_fields": "setup",
    "email_template.no_help_contact": "setup",
    "instruments.no_rule_pinned": "operations",
    "instruments.stale_generated": "operations",
    "instruments.zero_included": "operations",
    "assignments.no_included_pairs": "operations",
    "assignments.reviewer_missing": "operations",
    "assignments.reviewer_missing_for_instrument": "operations",
    "assignments.instrument_empty": "operations",
}


def gate_for_rule_key(rule_key: str) -> Gate:
    """Return the gate a registered rule key belongs to.

    Falls back to a source-based heuristic (``assignments.*`` →
    Operations, anything else → Setup) when the key isn't in the
    explicit mapping, so a newly added rule slots into a sensible
    default until the mapping is updated.
    """
    gate = _RULE_KEY_GATE.get(rule_key)
    if gate is not None:
        return gate
    source = rule_key.split(".", 1)[0]
    return "operations" if source == "assignments" else "setup"


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
    warning") respecting the active severity filter.

    ``gate`` (Segment 15E PR 2) splits the issue list into two
    sections — Setup gate vs. Operations gate. The same source can
    appear in both gates when its rules span structural readiness
    (e.g. ``instruments.no_fields``) and post-Generate readiness
    (e.g. ``instruments.stale_generated``); the grouping is by
    ``(gate, source)`` rather than source alone.
    """

    source: str
    count_summary: str
    issues: list[Any]  # list[ValidationIssue], untyped to avoid circular import
    gate: Gate = "setup"


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

    # Group by (gate, source) so the Validate page can render two
    # gate sections (Setup / Operations) with per-source headings
    # inside each. Iteration order of ``filtered_issues`` matches
    # ``REGISTERED_RULES`` order — preserve it via insertion-ordered
    # dict, then re-emit in gate order so setup-gate groups come
    # before operations-gate groups regardless of the underlying rule
    # order.
    grouped: dict[tuple[Gate, str], list[Any]] = {}
    for issue in filtered_issues:
        key = (gate_for_rule_key(issue.rule_key or ""), issue.source)
        grouped.setdefault(key, []).append(issue)
    issue_groups = [
        IssueSourceGroup(
            source=source,
            count_summary=_per_source_count_summary(group_issues),
            issues=group_issues,
            gate=gate,
        )
        for gate_filter in ("setup", "operations")
        for (gate, source), group_issues in grouped.items()
        if gate == gate_filter
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
