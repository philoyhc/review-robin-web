"""Cross-slice plumbing for the reviewer route package.

Owns the single ``Jinja2Templates`` instance used by every
reviewer sub-module, and the two helpers used by more than one
slice. Per the operator-package precedent, slice modules import
from this file but ``_shared`` imports nothing from the package.
"""

from __future__ import annotations

from pathlib import Path

from collections.abc import Sequence

from fastapi import HTTPException, status
from fastapi.templating import Jinja2Templates
from sqlalchemy import and_, not_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Instrument, InstrumentDisplayField, Reviewer, User
from app.web import views
from app.web.date_filters import (
    display_timezone_context_processor,
    format_date_filter,
    format_datetime_filter,
)

# ``__file__`` here is ``app/web/routes_reviewer/_shared.py``; the
# templates live two levels up at ``app/web/templates``, hence
# ``.parent.parent``. (The pre-package single-file module resolved
# with a single ``.parent``.)
_templates = Jinja2Templates(
    directory=str(Path(__file__).parent.parent / "templates"),
    context_processors=[display_timezone_context_processor],
)
_templates.env.globals["app_version"] = settings.app_version
# Segment 13C — per-numeric-column ``ch`` width for the
# fixed-layout group-scoped instrument table.
_templates.env.globals["numeric_column_ch_width"] = (
    views.numeric_column_ch_width
)
# 2026-05-28 — derives the ``rows`` attribute for String
# response-field textareas from ``max_chars`` + operator-set
# column width so reviewers see a textarea sized for the typical
# response (50% of the configured cap) at the column's current
# width, without waiting on the reviewer to drag-resize. Native
# textarea resize stays available at runtime.
_templates.env.globals["textarea_rows_for"] = views.textarea_rows_for
# Canonical date / time display formatting — Segment 18B PR 1 / PR 2.
# Context-aware: the filters resolve their display zone from the
# ``display_timezone`` context key the processor above injects.
_templates.env.filters["format_datetime"] = format_datetime_filter
_templates.env.filters["format_date"] = format_date_filter


def validate_page_n(
    page_n: int, pages: Sequence[Sequence[Instrument]]
) -> int:
    """Validate a 1-based reviewer-surface ``page_n`` against the
    session's page list, raising 404 if it's out of range.

    Segment 18N PR 1 — single source of truth for the page-validity
    check the reviewer-surface GET, the save POST, and the operator-
    side preview route all need to perform. Previously the GET +
    preview clamped ``page_count = len(pages) or 1`` (so a session
    with zero instruments would still respond on ``/1`` with an
    empty render) while the save POST hard-failed with ``len(pages)``
    (404 on empty). The asymmetry was unreachable in practice
    because session-setup validation refuses to activate an empty
    session, but the defensive shape was inconsistent and would
    have masked a real bug if upstream gating ever changed.

    Strict semantics: an empty pages list yields 404 for every
    method (rather than rendering empty content on ``/1``). Tracks
    the 28may codebase assessment §5 weakness.
    """
    if not pages or page_n < 1 or page_n > len(pages):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return page_n


def reviewer_review_count_for_user(db: Session, user: User) -> int:
    """Count active Reviewer rows whose email matches ``user``, case-insensitive.

    Drives the conditional "My Reviews" link in the reviewer chrome
    (suppressed when the user has only a single review — the dashboard
    isn't useful as a navigation hub in that case).
    """
    target = (user.email or "").casefold()
    if not target:
        return 0
    rows = db.execute(
        select(Reviewer).where(Reviewer.status == "active")
    ).scalars()
    return sum(1 for r in rows if r.email.casefold() == target)


_NOT_REVIEWEE_IDENTITY_DISPLAY_FIELD = not_(
    and_(
        InstrumentDisplayField.source_type == "reviewee",
        InstrumentDisplayField.source_field.in_(["name", "email_or_identifier"]),
    )
)
"""Filter expression: exclude display fields that duplicate the always-rendered
Reviewee identity column (name + email). The operator can still configure these
on the Instruments page; they're just not rendered as separate columns on the
reviewer surface since the Reviewee column already shows both."""
