"""Coverage for the role-navigator chip strip rendered below the
session-name header on each ``/me`` role-specific surface.

Contract:

- One chip per role the signed-in user holds on this session
  (case-insensitive email match, active rows only).
- Chips appear in priority order: Reviewer → Reviewee → Observer.
- The chip matching the current page renders as a span
  (no anchor, ``rs-role-nav-active``).
- Other roles render as anchors with ``rs-role-nav-muted`` when
  reachable; as plain spans with ``rs-role-nav-muted`` when not.
- Suppressed on the operator preview surface (``preview_mode``).
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Observer, Reviewee, Reviewer, ReviewSession


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Cohort A", "code": code, "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


# ── Results surface ───────────────────────────────────────────────────


def test_results_chip_renders_reviewee_active_no_anchor(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="chip-re-only")
    db.add(
        Reviewee(
            session_id=review_session.id,
            name="Alice",
            email_or_identifier="alice@example.edu",
        )
    )
    db.commit()
    body = client.get(
        f"/me/sessions/{review_session.id}/results"
    ).text
    # Reviewee chip is the active one — no anchor, span with the
    # ``rs-role-nav-active`` marker class.
    assert (
        '<span class="pill pill-role-reviewee rs-role-nav-active">Reviewee</span>'
        in body
    )
    # Only one chip — no anchors to the other surfaces.
    assert (
        f'href="/me/sessions/{review_session.id}/1"'
        not in body
    )
    assert (
        f'href="/me/sessions/{review_session.id}/collation"'
        not in body
    )


def test_results_chips_show_other_roles_as_muted_anchors(
    client: TestClient, db: Session
) -> None:
    """A reviewee + observer user lands on /results. The
    Reviewee chip is active; the Observer chip is a muted
    anchor to /collation."""
    review_session = _make_session(client, db, code="chip-re-ob")
    db.add_all(
        [
            Reviewee(
                session_id=review_session.id,
                name="Alice",
                email_or_identifier="alice@example.edu",
            ),
            Observer(
                session_id=review_session.id,
                email="alice@example.edu",
                display_name="Alice",
            ),
        ]
    )
    db.commit()
    body = client.get(
        f"/me/sessions/{review_session.id}/results"
    ).text
    assert (
        '<span class="pill pill-role-reviewee rs-role-nav-active">Reviewee</span>'
        in body
    )
    expected_observer = (
        f'<a class="pill pill-role-observer rs-role-nav-muted" '
        f'href="/me/sessions/{review_session.id}/collation">Observer</a>'
    )
    assert expected_observer in body


def test_results_chips_render_in_priority_order(
    client: TestClient, db: Session
) -> None:
    """Triple-role row visiting /results: chips ordered
    Reviewer → Reviewee → Observer regardless of which is
    active."""
    review_session = _make_session(client, db, code="chip-three")
    review_session.status = "ready"
    db.add_all(
        [
            Reviewer(
                session_id=review_session.id,
                name="Alice",
                email="alice@example.edu",
            ),
            Reviewee(
                session_id=review_session.id,
                name="Alice",
                email_or_identifier="alice@example.edu",
            ),
            Observer(
                session_id=review_session.id,
                email="alice@example.edu",
                display_name="Alice",
            ),
        ]
    )
    db.commit()
    body = client.get(
        f"/me/sessions/{review_session.id}/results"
    ).text
    reviewer_pos = body.find("pill-role-reviewer rs-role-nav-muted")
    reviewee_pos = body.find("pill-role-reviewee rs-role-nav-active")
    observer_pos = body.find("pill-role-observer rs-role-nav-muted")
    assert -1 < reviewer_pos < reviewee_pos < observer_pos


def test_results_reviewer_chip_disabled_when_session_not_opened(
    client: TestClient, db: Session
) -> None:
    """Reviewee on /results who is also a reviewer on a draft
    session — the reviewer chip greys out as a span (no anchor)
    since the reviewer surface is ``not opened``."""
    review_session = _make_session(client, db, code="chip-rv-draft")
    db.add_all(
        [
            Reviewee(
                session_id=review_session.id,
                name="Alice",
                email_or_identifier="alice@example.edu",
            ),
            Reviewer(
                session_id=review_session.id,
                name="Alice",
                email="alice@example.edu",
            ),
        ]
    )
    db.commit()
    body = client.get(
        f"/me/sessions/{review_session.id}/results"
    ).text
    # Disabled reviewer chip — muted span, no anchor.
    assert (
        '<span class="pill pill-role-reviewer rs-role-nav-muted">Reviewer</span>'
        in body
    )
    assert (
        f'<a class="pill pill-role-reviewer rs-role-nav-muted" '
        f'href="/me/sessions/{review_session.id}'
        not in body
    )


# ── Collation surface ────────────────────────────────────────────────


def test_collation_chip_renders_observer_active(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="chip-ob-only")
    db.add(
        Observer(
            session_id=review_session.id,
            email="alice@example.edu",
            display_name="Alice",
        )
    )
    db.commit()
    body = client.get(
        f"/me/sessions/{review_session.id}/collation"
    ).text
    assert (
        '<span class="pill pill-role-observer rs-role-nav-active">Observer</span>'
        in body
    )


def test_collation_chips_show_reviewee_when_user_holds_both(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="chip-ob-re")
    db.add_all(
        [
            Observer(
                session_id=review_session.id,
                email="alice@example.edu",
                display_name="Alice",
            ),
            Reviewee(
                session_id=review_session.id,
                name="Alice",
                email_or_identifier="alice@example.edu",
            ),
        ]
    )
    db.commit()
    body = client.get(
        f"/me/sessions/{review_session.id}/collation"
    ).text
    expected_reviewee = (
        f'<a class="pill pill-role-reviewee rs-role-nav-muted" '
        f'href="/me/sessions/{review_session.id}/results">Reviewee</a>'
    )
    assert expected_reviewee in body
    assert (
        '<span class="pill pill-role-observer rs-role-nav-active">Observer</span>'
        in body
    )
