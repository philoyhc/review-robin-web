"""The lobby's Deadline and Timezone, and the archive's Timezone, sort on
a click as a reload sorts them (author, 2026-10-14). The browser sorted
the cell text ("No deadline", "GMT+8"), the route the stored values
(None last, the IANA name); the cells now carry the route's value, as
Sessions Diagnostics' do."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, User
from app.services import operator_settings, sessions


def _session(client: TestClient, db: Session, code: str, **fields: object) -> ReviewSession:
    client.post("/operator/sessions", data={"name": code.title(), "code": code})
    row = db.execute(select(ReviewSession).where(ReviewSession.code == code)).scalar_one()
    for name, value in fields.items():
        setattr(row, name, value)
    db.commit()
    return row


def _sort_values(body: str, code: str) -> list[str]:
    row = body.split(f"<code>{code}</code>", 1)[1].split("</tr>", 1)[0]
    return re.findall(r'<td[^>]*data-sort-value="([^"]*)"', row)


def test_the_lobby_deadline_and_timezone_carry_the_routes_values(
    client: TestClient, db: Session
) -> None:
    no_zone = _session(client, db, "zz-open", display_timezone=None)
    _session(
        client, db, "zz-due",
        deadline=datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc),
        display_timezone="Asia/Singapore",
    )
    # The viewer reads dates in Tokyo, so the cell shows 21:00; the sort
    # key stays the UTC instant.
    viewer = db.execute(select(User)).scalars().first()
    operator_settings.set_display_timezone(db, user=viewer, timezone_name="Asia/Tokyo")
    db.commit()
    body = client.get("/operator/sessions").text
    assert "2026-11-01 21:00" in body
    assert _sort_values(body, "zz-open")[0] == ""  # empty sorts last, either way
    # A session with no zone of its own sorts by the zone it falls back
    # to, as the route does, not by an empty or "None" value.
    assert _sort_values(body, "zz-open")[1] == sessions.resolve_session_timezone(no_zone)
    assert _sort_values(body, "zz-due") == [
        "2026-11-01T12:00:00.000000+00:00", "Asia/Singapore",
    ]


def test_the_archive_timezone_carries_the_zone_name(
    client: TestClient, db: Session
) -> None:
    _session(client, db, "zz-gone", status="archived", display_timezone="Europe/Paris")
    body = client.get("/operator/sessions/archived").text
    assert _sort_values(body, "zz-gone") == ["Europe/Paris"]
