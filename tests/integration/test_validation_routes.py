from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import ReviewSession


def _make_session(
    client: TestClient, db: Session, code: str = "spring-2026"
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Spring", "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def test_validate_renders_with_errors_for_empty_session(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db)

    response = client.get(f"/operator/sessions/{review_session.id}/validate")

    assert response.status_code == 200
    body = response.text
    assert "No reviewers" in body
    assert "No reviewees" in body
    assert "2 errors" in body or "2 error" in body


def test_validate_renders_clean_for_populated_session(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db)
    client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                b"ReviewerName,ReviewerEmail\nAlice,alice@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{review_session.id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                b"RevieweeName,RevieweeEmail\nCarol,carol@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )

    response = client.get(f"/operator/sessions/{review_session.id}/validate")

    assert response.status_code == 200
    assert "0 errors" in response.text
    assert "No reviewers" not in response.text
    assert "No reviewees" not in response.text


def test_non_operator_cannot_view_validate(
    db: Session,
    alice: AuthenticatedUser,
    bob: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    alice_client = make_client(alice)
    review_session = _make_session(alice_client, db, code="alice-only")

    bob_client = make_client(bob)
    response = bob_client.get(f"/operator/sessions/{review_session.id}/validate")

    assert response.status_code == 403


def test_session_detail_shows_counts_and_validate_link(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db)

    empty_response = client.get(f"/operator/sessions/{review_session.id}")
    assert empty_response.status_code == 200
    body = empty_response.text
    # Setup row labels appear as button labels
    assert ">Reviewers</a>" in body
    assert ">Reviewees</a>" in body
    assert ">Assignments</a>" in body
    # Validate Session Setup button targets the ?validated=1 query branch
    assert (
        f'href="/operator/sessions/{review_session.id}?validated=1"' in body
    )

    client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                b"ReviewerName,ReviewerEmail\n"
                b"Alice,alice@example.edu\n"
                b"Bob,bob@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )

    populated = client.get(f"/operator/sessions/{review_session.id}")
    body = populated.text
    # Reviewers count cell now shows 2
    assert "Number of reviewers: 2" in body
