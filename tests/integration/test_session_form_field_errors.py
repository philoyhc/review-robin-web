"""An over-long Name or Code is a 422, not a 500 (findings 2026-10-07 C4).

The lobby expander already turned the session payload's field errors
into a 422; Session Home's Details Save and Create built the payload
outside a ``try``, so a value past the column width (which the browser's
``maxlength`` hides) reached the server as an unhandled ``ValidationError``.
All three now share ``session_payload_error``.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession


def _make_session(client: TestClient, db: Session, code: str) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Spring", "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def test_details_save_refuses_an_over_long_name_with_a_422(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, "c4-home")
    response = client.post(
        f"/operator/sessions/{review_session.id}/config",
        data={
            "name": "N" * 256,
            "code": review_session.code,
            "display_timezone": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 422, response.text
    assert "name: " in response.text
    db.refresh(review_session)
    assert review_session.name == "Spring"


def test_create_refuses_an_over_long_name_or_code_and_creates_nothing(
    client: TestClient, db: Session
) -> None:
    before = db.execute(select(func.count(ReviewSession.id))).scalar_one()
    for data in (
        {"name": "N" * 256, "code": "c4-create"},
        {"name": "Spring", "code": "c" * 65},
    ):
        response = client.post(
            "/operator/sessions", data=data, follow_redirects=False
        )
        assert response.status_code == 422, response.text
    after = db.execute(select(func.count(ReviewSession.id))).scalar_one()
    assert after == before
