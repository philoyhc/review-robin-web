"""The nine date-time boxes are one control (segment 19X Item 6): a
24-hour ``YYYY-MM-DD HH:MM`` text box, with the browser's native
``datetime-local`` kept only as the hidden picker behind it."""

from __future__ import annotations

import re
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession


def _native_boxes(body: str) -> list[str]:
    return [
        tag
        for tag in re.findall(r"<input[^>]*>", body)
        if 'type="datetime-local"' in tag and "data-dt-picker" not in tag
    ]


def _create(client: TestClient, db: Session, code: str) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Fields", "code": code, "display_timezone": "UTC",
              "deadline": "2027-04-01 10:00"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def test_no_page_renders_a_bare_native_box(client: TestClient, db: Session) -> None:
    review_session = _create(client, db, "dt-pages")
    pages = {
        "/operator/sessions/new": 4,
        f"/operator/sessions/{review_session.public_id}?editing=1": 4,
        "/operator/sessions": 1,
    }
    for url, fields in pages.items():
        body = client.get(url).text
        assert _native_boxes(body) == [], url
        assert body.count('class="dt-field" data-dt-field') == fields, url


def test_the_lobby_seeds_end_as_24_hour_text_and_keeps_it(
    client: TestClient, db: Session
) -> None:
    review_session = _create(client, db, "dt-lobby")
    assert review_session.deadline == datetime(2027, 4, 1, 10, 0)
    body = client.get("/operator/sessions").text
    assert 'data-deadline="2027-04-01 10:00"' in body

    def save(deadline: str) -> None:
        response = client.post(
            f"/operator/sessions/{review_session.public_id}/lobby-edit",
            data={"name": "Fields", "code": "dt-lobby", "deadline": deadline,
                  "tags": ""},
            follow_redirects=False,
        )
        assert response.status_code == 303, response.text
        db.refresh(review_session)

    save("2027-04-01 10:00")
    assert review_session.deadline == datetime(2027, 4, 1, 10, 0)
    save("2027-04-02 11:15")
    assert review_session.deadline == datetime(2027, 4, 2, 11, 15)
    save("")
    assert review_session.deadline is None
