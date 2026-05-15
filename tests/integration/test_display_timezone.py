"""Segment 18B PR 2 — operator surfaces render timestamps in the
signed-in operator's configured display timezone.

Exercises the full filter-wiring chain: ``get_or_create_user``
stamps ``request.state.display_timezone`` from the operator's
``users.preferences``; the ``date_filters`` context processor
injects it; the context-aware ``format_datetime`` filter resolves
the zone at render time.
"""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession
from app.services.date_formatting import format_datetime


def _create_session(
    client: TestClient, db: Session, *, code: str = "tz-demo"
) -> ReviewSession:
    client.post(
        "/operator/sessions",
        data={"name": code.title(), "code": code},
        follow_redirects=False,
    )
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def test_lobby_renders_in_utc_before_any_preference(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db)
    body = client.get("/operator/sessions").text
    assert format_datetime(session.created_at, "UTC") in body


def test_lobby_renders_in_operator_zone_after_save(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db)

    client.post(
        "/operator/settings/timezone",
        data={"display_timezone": "Asia/Singapore"},
        follow_redirects=False,
    )

    body = client.get("/operator/sessions").text
    # The created-at pill now renders in Singapore time (+08)...
    assert format_datetime(session.created_at, "Asia/Singapore") in body
    # ...and the UTC render (a different wall-clock time) is gone.
    assert format_datetime(session.created_at, "UTC") not in body
