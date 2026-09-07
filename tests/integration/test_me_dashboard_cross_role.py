"""Coverage for the ``/me`` dashboard's cross-role union — the
page lists every session the signed-in user touches in any
participant role (reviewer / reviewee / observer) and renders
all matching role pills.

Pins the regression where reviewee / observer matches didn't
surface on ``/me`` because the route queried reviewers only.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Observer,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)


def _make_session_and_activate(
    client: TestClient,
    db: Session,
    *,
    code: str,
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "S", "code": code, "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _alice(db: Session) -> User:
    return db.execute(
        select(User).where(User.email == "alice@example.edu")
    ).scalar_one()


def test_me_shows_reviewer_pill_when_user_is_reviewer(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session_and_activate(client, db, code="me-rv")
    db.add(
        Reviewer(
            session_id=review_session.id,
            name="Alice",
            email="alice@example.edu",
        )
    )
    db.commit()
    body = client.get("/me").text
    assert 'class="pill pill-role-reviewer"' in body
    assert "Reviewer" in body


def test_me_shows_reviewee_pill_when_user_only_reviewee(
    client: TestClient, db: Session, grant_reviewee_visibility
) -> None:
    """Reviewee-only row used to be missing entirely because the
    route queried reviewers only. Now it surfaces with a
    Reviewee pill, no reviewer-status pill, and the Session
    name as plain text.

    Since 19F PR 2 the row is also conditional on a grant that
    resolves right now — hence `grant_reviewee_visibility`. The
    no-grant case is its own test below."""
    review_session = _make_session_and_activate(client, db, code="me-re")
    db.add(
        Reviewee(
            session_id=review_session.id,
            name="Alice",
            email_or_identifier="alice@example.edu",
        )
    )
    db.commit()
    grant_reviewee_visibility(review_session)
    body = client.get("/me").text
    assert 'class="pill pill-role-reviewee"' in body
    assert "Reviewee" in body
    # No reviewer-status pills on a reviewee-only row.
    assert "submitted" not in body
    assert "in progress" not in body


def test_me_shows_observer_pill_when_user_only_observer(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session_and_activate(client, db, code="me-ob")
    db.add(
        Observer(
            session_id=review_session.id,
            email="alice@example.edu",
            display_name="Alice",
        )
    )
    db.commit()
    body = client.get("/me").text
    assert 'class="pill pill-role-observer"' in body
    assert "Observer" in body


def test_me_unions_all_three_roles_on_one_row(
    client: TestClient, db: Session, grant_reviewee_visibility
) -> None:
    """A session where the user holds all three roles renders one
    row carrying all three pills."""
    review_session = _make_session_and_activate(client, db, code="me-all")
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
    grant_reviewee_visibility(review_session)
    body = client.get("/me").text
    assert body.count('class="pill pill-role-reviewer"') == 1
    assert body.count('class="pill pill-role-reviewee"') == 1
    assert body.count('class="pill pill-role-observer"') == 1


def test_me_matches_case_insensitively(
    client: TestClient, db: Session, grant_reviewee_visibility
) -> None:
    review_session = _make_session_and_activate(client, db, code="me-case")
    db.add(
        Reviewee(
            session_id=review_session.id,
            name="Alice",
            email_or_identifier="ALICE@EXAMPLE.EDU",
        )
    )
    db.commit()
    grant_reviewee_visibility(review_session)
    body = client.get("/me").text
    assert 'class="pill pill-role-reviewee"' in body


def test_me_skips_inactive_roster_rows(
    client: TestClient, db: Session
) -> None:
    """Soft-removed roster rows (``status=inactive``) don't put
    the user back on the dashboard — matches the existing
    reviewer behaviour and reflects that inactivation is the
    operator's soft-remove."""
    review_session = _make_session_and_activate(client, db, code="me-inact")
    db.add(
        Observer(
            session_id=review_session.id,
            email="alice@example.edu",
            display_name="Alice",
            status="inactive",
        )
    )
    db.commit()
    body = client.get("/me").text
    assert 'class="pill pill-role-observer"' not in body


def test_me_skips_other_users_roster_rows(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session_and_activate(client, db, code="me-other")
    db.add(
        Reviewer(
            session_id=review_session.id,
            name="Bob",
            email="bob@example.edu",
        )
    )
    db.commit()
    body = client.get("/me").text
    # No role pills should render — alice is in no roster.
    assert 'class="pill pill-role-reviewer"' not in body
    assert 'class="pill pill-role-reviewee"' not in body
    assert 'class="pill pill-role-observer"' not in body


# ── 19F PR 2 — the reviewee role is gated on a current grant ─────────


def test_reviewee_with_no_current_grant_gets_no_row_at_all(
    client: TestClient, db: Session
) -> None:
    """Decision 3: a reviewee with nothing currently granted is
    treated exactly as someone holding no role at all. Not a bespoke
    outcome, not a disabled link — no row.

    This is the whole point of the segment. Until PR 2 the row
    appeared the moment an operator uploaded the roster, disclosing
    that someone is the subject of a review before anyone had decided
    they may see anything about it."""
    review_session = _make_session_and_activate(client, db, code="me-nogrant")
    db.add(
        Reviewee(
            session_id=review_session.id,
            name="Alice",
            email_or_identifier="alice@example.edu",
        )
    )
    db.commit()
    body = client.get("/me").text
    assert 'class="pill pill-role-reviewee"' not in body
    # Id-qualified: a bare "/results" also matches a CSS comment, since
    # base.html inlines the whole stylesheet into every page.
    assert f"/me/sessions/{review_session.id}/results" not in body
    # Indistinguishable from the empty dashboard a stranger sees.
    assert "You have no pending reviews" in body


def test_a_grant_that_exists_but_has_not_opened_does_not_count(
    client: TestClient, db: Session, grant_reviewee_visibility
) -> None:
    """Decision 1: *currently* resolving, not ever-configured.

    The policy row is set exactly as `grant_reviewee_visibility` sets
    it, but the release anchor sits in the future — so an operator
    configuring visibility in advance does not thereby announce the
    review to its subject."""
    review_session = _make_session_and_activate(client, db, code="me-future")
    db.add(
        Reviewee(
            session_id=review_session.id,
            name="Alice",
            email_or_identifier="alice@example.edu",
        )
    )
    db.commit()
    grant_reviewee_visibility(review_session)
    review_session.responses_release_at = datetime.now(
        timezone.utc
    ) + timedelta(days=7)
    db.commit()

    body = client.get("/me").text
    assert 'class="pill pill-role-reviewee"' not in body


def test_the_row_survives_on_another_role_when_the_grant_is_absent(
    client: TestClient, db: Session
) -> None:
    """Decision 2: gate the role, not the row. Hiding the whole row
    would break two working surfaces to protect a third.

    Alice is a reviewer *and* an ungranted reviewee here: she keeps her
    row and her reviewer pill, and only the Reviewee pill is missing."""
    review_session = _make_session_and_activate(client, db, code="me-both")
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
        ]
    )
    db.commit()
    body = client.get("/me").text
    assert 'class="pill pill-role-reviewer"' in body
    assert 'class="pill pill-role-reviewee"' not in body


def test_an_archived_session_closes_the_reviewee_row(
    client: TestClient, db: Session, grant_reviewee_visibility
) -> None:
    """The archive override forces every non-operator grant off
    (`spec/visibility_policy.md`), so the row leaves when the session
    is archived — it falls out of decision 1 rather than needing a rule
    of its own.

    Note the asymmetry this creates on purpose, recorded in the plan:
    reviewers and observers keep seeing an archived session on `/me` as
    "not opened", because their rows are not grant-conditioned."""
    review_session = _make_session_and_activate(client, db, code="me-arch")
    db.add(
        Reviewee(
            session_id=review_session.id,
            name="Alice",
            email_or_identifier="alice@example.edu",
        )
    )
    db.commit()
    grant_reviewee_visibility(review_session)
    assert 'class="pill pill-role-reviewee"' in client.get("/me").text

    review_session.status = "archived"
    db.commit()
    assert 'class="pill pill-role-reviewee"' not in client.get("/me").text
