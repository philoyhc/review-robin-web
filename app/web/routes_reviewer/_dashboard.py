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

from dataclasses import dataclass
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


@dataclass(frozen=True)
class DashboardPageRow:
    """One per-page sub-row on the reviewer dashboard.

    Segment 15B Slice 6 introduced per-instrument sub-rows; Segment
    18L's multi-page reviewer surface (one page per run of
    instruments between Segment 18M page breaks) repointed the deep
    link at ``/me/sessions/{id}/{page_n}`` rather than the
    per-instrument position, so the sub-rows now reflect *pages*
    rather than individual instruments.

    Suppressed entirely (empty list) for single-page sessions —
    that covers single-instrument sessions (the pre-15B byte-
    identical contract) *and* multi-instrument sessions where the
    operator hasn't added a page break (the sub-row would just
    restate the parent session row at the same ``/{id}/1`` URL).

    Fields:

    - ``label`` — ``"Page N: #n {short_label}, #m {short_label}, ..."``
      where N is the 1-based page number and #n / #m are the
      instrument positions across the whole session (the same
      ``#N`` convention the reviewer surface's per-instrument
      heading uses). Bare ``"Page N"`` falls back when an
      instrument has no ``short_label`` *or* ``name``.
    - ``page_n`` — 1-based page index. Lands in
      ``/me/sessions/{id}/{page_n}``.
    - ``state`` — ``"not started"`` / ``"in progress"`` /
      ``"submitted"`` / ``"no assignments"``. Rolled up from the
      page's instruments via :func:`_rollup_page_state` — mixed
      submitted/not-started or any in-progress collapses to
      ``"in progress"``; a page where every instrument is "no
      assignments" rolls up to ``"no assignments"``.
    - ``completed_rows`` / ``total_assignments`` — summed across
      the page's instruments; surfaced in the muted ``(N/M)``
      suffix alongside the pill, same shape as the per-session
      pill row.
    """

    label: str
    page_n: int
    state: str
    completed_rows: int
    total_assignments: int


def _rollup_page_state(per_instrument_states: list[str]) -> str:
    """Roll up per-instrument pill states to one per-page state.

    Order of evaluation mirrors :func:`_page_status_for_group` /
    ``_session_status`` on the surface: ``no assignments`` entries
    contribute nothing; any ``in progress`` wins; uniform
    ``submitted`` / ``not started`` carry through; mixed
    submitted + not started reads as ``in progress`` (some
    instruments done on this page, others not yet started).
    """
    active = [s for s in per_instrument_states if s != "no assignments"]
    if not active:
        return "no assignments"
    if any(s == "in progress" for s in active):
        return "in progress"
    if all(s == "submitted" for s in active):
        return "submitted"
    if all(s == "not started" for s in active):
        return "not started"
    return "in progress"


def _build_dashboard_page_rows(
    db: Session, reviewer: Reviewer, review_session: ReviewSession
) -> list[DashboardPageRow]:
    """Return one :class:`DashboardPageRow` per operator-defined
    reviewer page when the session has both ``N > 1`` instruments
    and ``M > 1`` pages; empty list otherwise.

    The empty-list contract keeps single-page sessions (including
    every single-instrument session — the byte-identical pre-15B
    invariant) free of redundant sub-rows.
    """
    # Defer the import to avoid a slice-level cycle: ``_surface``
    # imports nothing from ``_dashboard``, but the dashboard reads
    # the same page-grouping helper the surface route owns.
    from app.web.routes_reviewer._surface import _pages_for_session

    pages = _pages_for_session(db, review_session.id)
    instrument_count = sum(len(p) for p in pages)
    if instrument_count <= 1 or len(pages) <= 1:
        return []
    # 1-based instrument position across the whole session,
    # matching the surface's ``#N`` labelling. Pages preserve
    # ``(Instrument.order, Instrument.id)`` ordering already.
    position_by_id = {
        inst.id: idx
        for idx, inst in enumerate(
            (inst for page in pages for inst in page), start=1
        )
    }
    state_by_instrument = (
        responses_service.reviewer_session_state_per_instrument(
            db, reviewer=reviewer, session_id=review_session.id
        )
    )
    rows: list[DashboardPageRow] = []
    for page_n, page_instruments in enumerate(pages, start=1):
        label_parts: list[str] = []
        per_instrument_states: list[str] = []
        completed_total = 0
        assignment_total = 0
        for inst in page_instruments:
            pos = position_by_id[inst.id]
            short = (inst.short_label or inst.name or "").strip()
            label_parts.append(f"#{pos} {short}" if short else f"#{pos}")
            state = state_by_instrument.get(inst.id)
            if state is None:
                per_instrument_states.append("no assignments")
                continue
            per_instrument_states.append(state.pill_state)
            completed_total += state.completed_count
            assignment_total += state.total_assignments
        rows.append(
            DashboardPageRow(
                label=f"Page {page_n}: {', '.join(label_parts)}",
                page_n=page_n,
                state=_rollup_page_state(per_instrument_states),
                completed_rows=completed_total,
                total_assignments=assignment_total,
            )
        )
    return rows


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
    ``guide/participant_model_upgrade.md`` §3.2: case-insensitive
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
            link_enabled = session_status != "not opened"
            link_target = (
                f"/me/sessions/{review_session.id}/summary"
                if pill.state == "submitted"
                else f"/me/sessions/{review_session.id}/1"
            )
            page_rows = _build_dashboard_page_rows(
                db, reviewer, review_session
            )
        else:
            # Reviewee / observer-only row — the reviewer surface
            # doesn't apply, so the per-reviewer pill / page-row
            # state stays empty and the Session name renders as
            # plain text. The reviewee results surface (W16) and
            # observer collation surface (W17) will eventually
            # turn ``link_target`` into a real link for those
            # roles; today both are placeholders in the template.
            pill = None
            session_status = _non_reviewer_session_status(review_session)
            link_enabled = False
            link_target = None
            page_rows = []

        items.append(
            {
                "reviewer": reviewer,
                "session": review_session,
                "roles": roles,
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
                "page_rows": page_rows,
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
