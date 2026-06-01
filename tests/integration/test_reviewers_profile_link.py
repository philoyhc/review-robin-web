"""Reviewer ``profile_link`` surface mirror — W11 closure.

Mirrors the Reviewees Setup-page treatment for the optional
``profile_link`` column:

- ``services/reviewers.create_reviewer`` + ``update_reviewer``
  accept the kwarg and normalise it (blank → ``None``, strip).
- The Setup-Reviewers form's ``profile_link`` input persists on
  create + update and re-populates after a validation error.
- The session-wide friendly label resolves to ``"Profile"`` for
  ``(reviewer, profile_link)`` — same default as the reviewee side.
- The Setup-Reviewers preview table hides the Profile-link column
  when no row has data and surfaces it when any row does.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Reviewer, ReviewSession, User
from app.services import field_labels, reviewers as reviewers_service


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "RevP", "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _operator_user(db: Session) -> User:
    return db.execute(
        select(User).where(User.email == "alice@example.edu")
    ).scalar_one()


# ---------------------------------------------------------------------------
# Service-layer normalisation
# ---------------------------------------------------------------------------


def test_create_reviewer_persists_and_normalises_profile_link(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rev-pl-create")
    reviewer = reviewers_service.create_reviewer(
        db,
        review_session=review_session,
        name="Alice",
        email="alice@example.edu",
        profile_link="  https://example.edu/alice  ",
        user=_operator_user(db),
    )
    db.refresh(reviewer)
    assert reviewer.profile_link == "https://example.edu/alice"


def test_create_reviewer_blank_profile_link_normalises_to_none(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rev-pl-blank")
    reviewer = reviewers_service.create_reviewer(
        db,
        review_session=review_session,
        name="Bob",
        email="bob@example.edu",
        profile_link="   ",
        user=_operator_user(db),
    )
    assert reviewer.profile_link is None


def test_update_reviewer_diffs_and_persists_profile_link(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rev-pl-update")
    reviewer = reviewers_service.create_reviewer(
        db,
        review_session=review_session,
        name="Cara",
        email="cara@example.edu",
        user=_operator_user(db),
    )
    changes = reviewers_service.update_reviewer(
        db,
        reviewer=reviewer,
        profile_link="https://example.edu/cara",
        user=_operator_user(db),
    )
    assert "profile_link" in changes
    assert changes["profile_link"] == [None, "https://example.edu/cara"]


# ---------------------------------------------------------------------------
# Friendly-label default
# ---------------------------------------------------------------------------


def test_reviewer_profile_link_default_label_is_profile(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rev-pl-label")
    assert (
        field_labels.resolve(review_session, "reviewer", "profile_link")
        == "Profile"
    )


# ---------------------------------------------------------------------------
# Setup-page form round-trip
# ---------------------------------------------------------------------------


def test_create_form_round_trips_profile_link(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rev-pl-form-c")

    response = client.post(
        f"/operator/sessions/{review_session.id}/reviewers/create",
        data={
            "name": "Dee",
            "email": "dee@example.edu",
            "profile_link": "https://example.edu/dee",
            "tag_1": "",
            "tag_2": "",
            "tag_3": "",
            "status": "active",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    row = db.execute(
        select(Reviewer).where(Reviewer.email == "dee@example.edu")
    ).scalar_one()
    assert row.profile_link == "https://example.edu/dee"


def test_update_form_round_trips_profile_link(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rev-pl-form-u")
    reviewer = reviewers_service.create_reviewer(
        db,
        review_session=review_session,
        name="Eli",
        email="eli@example.edu",
        user=_operator_user(db),
    )

    response = client.post(
        f"/operator/sessions/{review_session.id}/reviewers/{reviewer.id}/update",
        data={
            "name": "Eli",
            "email": "eli@example.edu",
            "profile_link": "https://example.edu/eli",
            "tag_1": "",
            "tag_2": "",
            "tag_3": "",
            "status": "active",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    db.expire_all()
    row = db.execute(
        select(Reviewer).where(Reviewer.id == reviewer.id)
    ).scalar_one()
    assert row.profile_link == "https://example.edu/eli"


# ---------------------------------------------------------------------------
# Setup-page preview column visibility
# ---------------------------------------------------------------------------


def test_reviewers_table_hides_profile_link_column_when_no_data(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rev-pl-hide")
    reviewers_service.create_reviewer(
        db,
        review_session=review_session,
        name="Fay",
        email="fay@example.edu",
        user=_operator_user(db),
    )

    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
    ).text
    # Non-edit mode + no profile_link data anywhere ⇒ column is hidden.
    assert "profile-col" not in body


def test_reviewers_table_surfaces_profile_link_column_with_data(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rev-pl-show")
    reviewers_service.create_reviewer(
        db,
        review_session=review_session,
        name="Gus",
        email="gus@example.edu",
        profile_link="https://example.edu/gus",
        user=_operator_user(db),
    )

    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
    ).text
    # One row has data ⇒ column appears with the rendered link.
    assert "profile-col" in body
    assert 'href="https://example.edu/gus"' in body
