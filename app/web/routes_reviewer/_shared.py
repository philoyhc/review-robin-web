"""Cross-slice plumbing for the reviewer route package.

Owns the single ``Jinja2Templates`` instance used by every
reviewer sub-module, and the two helpers used by more than one
slice. Per the operator-package precedent, slice modules import
from this file but ``_shared`` imports nothing from the package.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.templating import Jinja2Templates
from sqlalchemy import and_, not_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import InstrumentDisplayField, Reviewer, User
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
# Canonical date / time display formatting — Segment 18B PR 1 / PR 2.
# Context-aware: the filters resolve their display zone from the
# ``display_timezone`` context key the processor above injects.
_templates.env.filters["format_datetime"] = format_datetime_filter
_templates.env.filters["format_date"] = format_date_filter


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
