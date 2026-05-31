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
from sqlalchemy import and_, func, not_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import (
    Instrument,
    InstrumentDisplayField,
    Observer,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from app.services import participants
from app.services import responses as responses_service
from app.services import session_lifecycle as lifecycle
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


# Ordered priority for the role-navigator chips on every
# role-specific surface (review surface / summary / results /
# collation). Reviewer carries the active work + deadline, so
# it leads; reviewee + observer follow as read-only views.
_ROLE_PRIORITY: tuple[str, ...] = ("reviewer", "reviewee", "observer")


def build_role_chips(
    db: Session,
    *,
    user: User,
    review_session: ReviewSession,
    active_role: str,
) -> list[dict[str, object]]:
    """Build the role-navigator chip list rendered below the
    session-name header on each role-specific surface.

    For every role the signed-in user holds on this session
    (case-insensitive email match against the reviewers /
    email-identified reviewees / observers rosters, ``status =
    active`` only), emit one chip carrying:

    - ``role`` — ``"reviewer"`` / ``"reviewee"`` / ``"observer"``.
    - ``target`` — the URL the chip links to (used only when
      ``active`` is ``False`` and ``enabled`` is ``True``).
    - ``active`` — ``True`` for the current surface's role —
      that chip renders in full colour and carries no link.
    - ``enabled`` — ``True`` when the role's surface is
      currently reachable. Reviewer ``not opened`` flips this
      ``False`` so the chip greys without a link; reviewee /
      observer surfaces are always reachable today (the W16 /
      W17 gates will land later).

    Chips render in :data:`_ROLE_PRIORITY` order regardless of
    which role is active, so the lineup is consistent across
    surfaces."""
    user_email = (user.email or "").casefold()
    if not user_email:
        return []

    reviewer = db.execute(
        select(Reviewer).where(
            Reviewer.session_id == review_session.id,
            Reviewer.status == "active",
            func.lower(Reviewer.email) == user_email,
        )
    ).scalar_one_or_none()

    reviewee_match = None
    for r in db.execute(
        select(Reviewee).where(
            Reviewee.session_id == review_session.id,
            Reviewee.status == "active",
        )
    ).scalars():
        if not participants.is_email_identified(r):
            continue
        if r.email_or_identifier.casefold() == user_email:
            reviewee_match = r
            break

    observer = db.execute(
        select(Observer).where(
            Observer.session_id == review_session.id,
            Observer.status == "active",
            func.lower(Observer.email) == user_email,
        )
    ).scalar_one_or_none()

    role_targets: dict[str, dict[str, object]] = {}
    if reviewer is not None:
        pill = responses_service.session_pill_for_reviewer(
            db, reviewer=reviewer, session_id=review_session.id
        )
        session_status = lifecycle.session_status_for_reviewer(
            db, reviewer=reviewer, review_session=review_session
        )
        role_targets["reviewer"] = {
            "target": (
                f"/me/sessions/{review_session.id}/summary"
                if pill.state == "submitted"
                else f"/me/sessions/{review_session.id}/1"
            ),
            "enabled": session_status != "not opened",
        }
    if reviewee_match is not None:
        role_targets["reviewee"] = {
            "target": f"/me/sessions/{review_session.id}/results",
            "enabled": True,
        }
    if observer is not None:
        role_targets["observer"] = {
            "target": f"/me/sessions/{review_session.id}/collation",
            "enabled": True,
        }

    chips: list[dict[str, object]] = []
    for role in _ROLE_PRIORITY:
        if role not in role_targets:
            continue
        chips.append(
            {
                "role": role,
                "target": role_targets[role]["target"],
                "enabled": role_targets[role]["enabled"],
                "active": role == active_role,
            }
        )
    return chips


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
