"""Reviewer dashboard — the "My Reviews" landing page listing
every session the signed-in user is an active reviewer on.

Segment 17B Phase 2 PR A widened the table to five columns —
Session / Start / End / Session Status / Reviewer Status —
adding the new two-status split (the session's open state vs
the reviewer's progress) and the Start column backed by
``sessions.activated_at``.

Carved out of the single-file ``routes_reviewer.py`` in Segment
17B PR 1.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Observer, Reviewee, Reviewer, ReviewSession, User
from app.db.session import get_db
from app.services import date_formatting
from app.services import responses as responses_service
from app.services import session_lifecycle as lifecycle
from app.services import sessions as sessions_service
from app.web import breadcrumbs
from app.web.deps import get_or_create_user
from app.web.routes_reviewer._shared import _templates

router = APIRouter(prefix="/me")


def _to_utc(value: datetime) -> datetime:
    """Promote a naive timestamp to UTC; pass aware values through.

    SQLite drops the timezone on read, so deadlines read back as
    naive datetimes even though they were written aware. Without
    this normaliser the past-deadline pill colour comparison
    raises ``TypeError`` on SQLite.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _non_reviewer_session_status(review_session: ReviewSession) -> str:
    """Session-status label for ``/me`` rows where the user is a
    reviewee / observer only — no reviewer-specific assignment
    check applies. Mirrors the reviewer flavour's
    not-opened / open / closed vocabulary so the column reads
    uniformly across role mixes."""
    if lifecycle.is_expired(review_session):
        return "closed"
    if lifecycle.is_ready(review_session):
        return "open"
    return "not opened"


@router.get("", response_class=HTMLResponse)
def reviewer_dashboard(
    request: Request,
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """The ``/me`` participant landing page — one row per session
    the signed-in user touches in any participant role
    (reviewer / reviewee / observer). The Roles column carries
    every matching label; reviewer-specific columns
    (Reviewer status, deep links, per-page sub-rows) populate
    only when the user is an active reviewer on that session.

    Cross-role union per
    ``guide/archive/participant_model_upgrade.md`` §3.2: case-insensitive
    email match against the reviewers / email-identified
    reviewees / observers rosters. Inactive rows are excluded —
    deactivation is the operator's "soft remove"."""
    user_email = (user.email or "").casefold()
    if not user_email:
        return _templates.TemplateResponse(
            request,
            "reviewer/dashboard.html",
            {
                "user": user,
                "items": [],
                "reviewer_review_count": 0,
                "breadcrumbs": breadcrumbs.reviewer_root(),
            },
        )

    reviewer_rows = list(
        db.execute(
            select(Reviewer, ReviewSession)
            .join(ReviewSession, ReviewSession.id == Reviewer.session_id)
            .where(
                Reviewer.status == "active",
                func.lower(Reviewer.email) == user_email,
            )
        ).all()
    )
    reviewee_rows = list(
        db.execute(
            select(Reviewee, ReviewSession)
            .join(ReviewSession, ReviewSession.id == Reviewee.session_id)
            .where(
                Reviewee.status == "active",
                func.lower(Reviewee.email_or_identifier) == user_email,
            )
        ).all()
    )
    observer_rows = list(
        db.execute(
            select(Observer, ReviewSession)
            .join(ReviewSession, ReviewSession.id == Observer.session_id)
            .where(
                Observer.status == "active",
                func.lower(Observer.email) == user_email,
            )
        ).all()
    )

    sessions_by_id: dict[int, ReviewSession] = {}
    reviewer_by_session: dict[int, Reviewer] = {}
    roles_by_session: dict[int, list[str]] = {}

    def _add(s: ReviewSession, role: str) -> None:
        sessions_by_id[s.id] = s
        if role not in roles_by_session.setdefault(s.id, []):
            roles_by_session[s.id].append(role)

    for reviewer, s in reviewer_rows:
        reviewer_by_session[s.id] = reviewer
        _add(s, "reviewer")
    for _reviewee, s in reviewee_rows:
        _add(s, "reviewee")
    for _observer, s in observer_rows:
        _add(s, "observer")

    ordered = sorted(
        sessions_by_id.values(),
        key=lambda s: s.updated_at,
        reverse=True,
    )

    items = []
    for review_session in ordered:
        roles = roles_by_session[review_session.id]
        reviewer = reviewer_by_session.get(review_session.id)
        session_zone = sessions_service.resolve_session_timezone(review_session)

        if reviewer is not None:
            pill = responses_service.session_pill_for_reviewer(
                db, reviewer=reviewer, session_id=review_session.id
            )
            session_status = lifecycle.session_status_for_reviewer(
                db, reviewer=reviewer, review_session=review_session
            )
        else:
            # Reviewee / observer-only row — the reviewer surface
            # doesn't apply, so the per-reviewer pill state stays
            # empty. The Session-status column still populates
            # from session lifecycle.
            pill = None
            session_status = _non_reviewer_session_status(review_session)

        # Per-role link map for both the per-pill anchor and the
        # session-name's prioritised target. The session name
        # picks the first reachable role in this priority order
        # (Reviewer → Reviewee → Observer): reviewer carries
        # active work and a deadline, the other two are
        # read-only views, so a multi-role user lands on the
        # actionable page by default. Pills give the explicit
        # escape hatch to the other surfaces.
        role_links: dict[str, dict[str, object]] = {}
        if reviewer is not None:
            role_links["reviewer"] = {
                "target": (
                    f"/me/sessions/{review_session.id}/summary"
                    if pill is not None and pill.state == "submitted"
                    else f"/me/sessions/{review_session.id}/1"
                ),
                # Same datetime gate the route used previously —
                # the reviewer surface 403s / redirects until the
                # session is at least once activated.
                "enabled": session_status != "not opened",
            }
        if "reviewee" in roles:
            role_links["reviewee"] = {
                "target": f"/me/sessions/{review_session.id}/results",
                # W16 will gate this on the
                # ``responses_release_at`` / ``responses_release_until``
                # window; today the placeholder accepts any active
                # reviewee.
                "enabled": True,
            }
        if "observer" in roles:
            role_links["observer"] = {
                "target": f"/me/sessions/{review_session.id}/collation",
                # W17 will gate this similarly to the reviewee
                # link; today the placeholder accepts any active
                # observer.
                "enabled": True,
            }

        link_target: str | None = None
        link_enabled = False
        for priority_role in ("reviewer", "reviewee", "observer"):
            candidate = role_links.get(priority_role)
            if candidate and candidate["enabled"]:
                link_target = candidate["target"]  # type: ignore[assignment]
                link_enabled = True
                break

        items.append(
            {
                "reviewer": reviewer,
                "session": review_session,
                "roles": roles,
                "role_links": role_links,
                "pill": pill,
                "session_status": session_status,
                "link_enabled": link_enabled,
                "link_target": link_target,
                "start_text": (
                    date_formatting.format_datetime(
                        review_session.activated_at, session_zone
                    )
                    if review_session.activated_at
                    else None
                ),
                "deadline_text": (
                    date_formatting.format_datetime(
                        review_session.deadline, session_zone
                    )
                    if review_session.deadline
                    else None
                ),
                "deadline_is_past": (
                    review_session.deadline is not None
                    and _to_utc(review_session.deadline)
                    <= datetime.now(timezone.utc)
                ),
                "timezone_gmt_offset": date_formatting.gmt_offset_label(
                    session_zone, at=review_session.deadline
                ),
                "timezone_iana": session_zone,
            }
        )
    return _templates.TemplateResponse(
        request,
        "reviewer/dashboard.html",
        {
            "user": user,
            "items": items,
            "reviewer_review_count": len(items),
            "breadcrumbs": breadcrumbs.reviewer_root(),
        },
    )
