"""Retirement behavior for the former Operations Previews hub."""

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession


def _create_session(client: TestClient, db: Session) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Retired previews", "code": "retired-previews"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return db.execute(
        select(ReviewSession).where(
            ReviewSession.code == "retired-previews"
        )
    ).scalar_one()


def test_previews_get_permanently_redirects_to_invitations(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db)

    response = client.get(
        f"/operator/sessions/{session.id}/previews",
        follow_redirects=False,
    )

    assert response.status_code == 308
    assert response.headers["location"] == (
        f"/operator/sessions/{session.id}/invitations"
    )


def test_previews_random_post_is_retired(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db)

    response = client.post(
        f"/operator/sessions/{session.id}/previews/random",
        follow_redirects=False,
    )

    assert response.status_code == 404
