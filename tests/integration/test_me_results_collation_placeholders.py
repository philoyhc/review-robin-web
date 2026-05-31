"""Coverage for the placeholder ``/me/sessions/{id}/results`` and
``/me/sessions/{id}/collation`` surfaces — the reviewee /
observer URLs that light up behind their respective gates.

Today the body is just the chrome: session-name header, the
inline body-text caption, and an optional description card. The
real content lands with W16 / W17 per
``guide/participant_model_upgrade.md`` §3.2.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Observer, Reviewee, ReviewSession


def _make_session(
    client: TestClient,
    db: Session,
    *,
    code: str,
    description: str = "",
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Cohort A", "code": code, "description": description},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


# ── /results ──────────────────────────────────────────────────────────


def test_results_403_when_user_is_not_a_reviewee(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="res-deny")
    response = client.get(
        f"/me/sessions/{review_session.id}/results"
    )
    assert response.status_code == 403


def test_results_renders_for_email_identified_reviewee(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(
        client, db, code="res-ok", description="Mid-term peer review."
    )
    db.add(
        Reviewee(
            session_id=review_session.id,
            name="Alice",
            email_or_identifier="alice@example.edu",
        )
    )
    db.commit()
    response = client.get(
        f"/me/sessions/{review_session.id}/results"
    )
    assert response.status_code == 200
    body = response.text
    # Session name as the page header.
    assert "<h1>Cohort A</h1>" in body
    # Inline caption next to the header.
    assert "Results of the review" in body
    # Session description rendered inside the rs-status-panel card.
    assert "rs-session-description" in body
    assert "Mid-term peer review." in body


def test_results_renders_without_description_card_when_none(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="res-nodesc")
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
    assert "<h1>Cohort A</h1>" in body
    assert "Results of the review" in body
    # The class name appears in the inline ``<style>`` block in
    # base.html, so match on the actual card opening tag.
    assert '<div class="card rs-status-panel">' not in body


def test_results_403_for_inactive_reviewee(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="res-inact")
    db.add(
        Reviewee(
            session_id=review_session.id,
            name="Alice",
            email_or_identifier="alice@example.edu",
            status="inactive",
        )
    )
    db.commit()
    response = client.get(
        f"/me/sessions/{review_session.id}/results"
    )
    assert response.status_code == 403


# ── /collation ────────────────────────────────────────────────────────


def test_collation_403_when_user_is_not_an_observer(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="col-deny")
    response = client.get(
        f"/me/sessions/{review_session.id}/collation"
    )
    assert response.status_code == 403


def test_collation_renders_for_observer(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(
        client,
        db,
        code="col-ok",
        description="External committee observation.",
    )
    db.add(
        Observer(
            session_id=review_session.id,
            email="alice@example.edu",
            display_name="Alice",
        )
    )
    db.commit()
    response = client.get(
        f"/me/sessions/{review_session.id}/collation"
    )
    assert response.status_code == 200
    body = response.text
    assert "<h1>Cohort A</h1>" in body
    assert "Observer view of the session" in body
    assert "rs-session-description" in body
    assert "External committee observation." in body


def test_collation_renders_without_description_card_when_none(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="col-nodesc")
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
    assert "<h1>Cohort A</h1>" in body
    assert "Observer view of the session" in body
    assert '<div class="card rs-status-panel">' not in body


def test_collation_403_for_inactive_observer(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="col-inact")
    db.add(
        Observer(
            session_id=review_session.id,
            email="alice@example.edu",
            display_name="Alice",
            status="inactive",
        )
    )
    db.commit()
    response = client.get(
        f"/me/sessions/{review_session.id}/collation"
    )
    assert response.status_code == 403
