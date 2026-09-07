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
    client: TestClient, db: Session, grant_reviewee_visibility
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
    # 19F PR 4 — /results opens only while a grant resolves.
    grant_reviewee_visibility(review_session)
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
    client: TestClient, db: Session, grant_reviewee_visibility
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
    # 19F PR 4 — /results opens only while a grant resolves.
    grant_reviewee_visibility(review_session)
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
    client: TestClient, db: Session, grant_reviewee_visibility
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
    # 19F PR 4 — /results opens only while a grant resolves.
    grant_reviewee_visibility(review_session)
    body = client.get(
        f"/me/sessions/{review_session.id}/results"
    ).text
    reviewer_pos = body.find("pill-role-reviewer rs-role-nav-muted")
    reviewee_pos = body.find("pill-role-reviewee rs-role-nav-active")
    observer_pos = body.find("pill-role-observer rs-role-nav-muted")
    assert -1 < reviewer_pos < reviewee_pos < observer_pos


def test_results_reviewer_chip_is_always_live_now(
    client: TestClient, db: Session, grant_reviewee_visibility
) -> None:
    """**Rewritten at 19F PR 4**, because the case it tested cannot
    occur on this surface any more.

    It asserted that a reviewee on ``/results`` who is also a reviewer
    on a **draft** session sees a greyed-out reviewer chip. But
    ``/results`` now opens only while a reviewee grant resolves, and a
    reviewee grant needs the session ``expired`` — where
    ``session_status_for_reviewer`` returns ``"closed"`` and the chip is
    a live anchor. There is no reachable ``/results`` render with a
    disabled reviewer chip.

    The disabled branch is **not** dead code — it is still reachable
    from ``/collation``, where an observer can sit on a draft session,
    and the test below pins it there. Only this surface lost the case.
    """
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
    grant_reviewee_visibility(review_session)
    body = client.get(
        f"/me/sessions/{review_session.id}/results"
    ).text
    assert (
        '<span class="pill pill-role-reviewer rs-role-nav-muted">Reviewer</span>'
        not in body
    )
    assert (
        f'<a class="pill pill-role-reviewer rs-role-nav-muted" '
        f'href="/me/sessions/{review_session.id}'
    ) in body


def test_collation_reviewer_chip_disabled_when_session_not_opened(
    client: TestClient, db: Session
) -> None:
    """The disabled-reviewer-chip case, relocated from ``/results``
    to the surface where it is still reachable.

    Observers are not grant-gated (19F decision 4), so an observer can
    open ``/collation`` on a ``draft`` session — and their reviewer chip
    greys out as a span, because the reviewer surface is
    ``not opened``.
    """
    review_session = _make_session(client, db, code="chip-ob-draft")
    db.add_all(
        [
            Observer(
                session_id=review_session.id,
                email="alice@example.edu",
                display_name="Alice",
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
        f"/me/sessions/{review_session.id}/collation"
    ).text
    assert (
        '<span class="pill pill-role-reviewer rs-role-nav-muted">Reviewer</span>'
        in body
    )


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


def test_collation_omits_reviewee_chip_without_a_current_grant(
    client: TestClient, db: Session
) -> None:
    """**Rewritten at 19F PR 7**, because it asserted the defect.

    It set up an observer who is also a reviewee on a ``draft``
    session and asserted a live Reviewee anchor. After PR 4 that
    anchor pointed at a 404 — and, worse, it said *you are a reviewee
    on this session* on a surface reached by a different role, which
    is the disclosure PR 2 had just closed on ``/me``. The chip is
    omitted now, not greyed: greying it would keep making the
    statement.
    """
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
    # Scoped to the chip markup: a bare ``pill-role-reviewee`` also
    # matches the CSS rule in ``base.html``'s inlined stylesheet, which
    # is present on every page and would pass this test forever.
    assert 'class="pill pill-role-reviewee' not in body
    assert f"/me/sessions/{review_session.id}/results" not in body
    assert (
        '<span class="pill pill-role-observer rs-role-nav-active">Observer</span>'
        in body
    )


def test_collation_shows_reviewee_chip_once_a_grant_resolves(
    client: TestClient, db: Session, grant_reviewee_visibility
) -> None:
    """The positive half of the pair above — without it, deleting the
    grant check would leave a suite that passes on an always-absent
    chip."""
    review_session = _make_session(client, db, code="chip-ob-re-ok")
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
    grant_reviewee_visibility(review_session)
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
