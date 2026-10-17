"""Dates at the edge of the calendar are refused or tolerated, never a
500 (findings L2 and O3, 2026-10-16).

L2: a far-future or far-past wall-clock moment on Create, Session Home's
details save (``/config``) or the lobby edit is refused as a malformed
one is; a year-9999 instant already stored renders, unconverted where
the display zone would carry it past ``datetime``'s range.

O3: the audit log's From / To at the first or last day of the calendar
filter sensibly, in the viewer and the CSV.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import AuditEvent, ReviewSession, User
from app.services import audit, date_formatting
from app.services.session_config_io._apply_shared import _parse_datetime, _ParseError

# Each datetime box on the details form, with the refusal it gives a
# malformed value today.
_BOXES = [
    ("deadline", "deadline must be ISO-8601"),
    ("scheduled_activate_at", "Start must be a valid datetime"),
    ("responses_release_at", "Release responses from must be a valid datetime"),
    ("responses_release_until", "Release responses until must be a valid datetime"),
]

# (wall-clock value, zone): each lands outside ``datetime``'s range when
# converted to UTC, or within a day of its edge.
_EDGE_MOMENTS = [
    ("9999-12-31T23:59", "America/New_York"),
    ("0001-01-01T00:00", "Asia/Tokyo"),
    ("9999-12-31T12:00", "UTC"),
]


def _create(client: TestClient, code: str, **extra: str):
    data = {"name": "S", "code": code, "description": ""}
    data.update(extra)
    return client.post("/operator/sessions", data=data, follow_redirects=False)


def _session(db: Session, code: str) -> ReviewSession:
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


# ── L2: entry refuses ────────────────────────────────────────────────


@pytest.mark.parametrize(("value", "zone"), _EDGE_MOMENTS)
@pytest.mark.parametrize(("box", "message"), _BOXES)
def test_create_refuses_an_edge_moment(
    client: TestClient, db: Session, box: str, message: str, value: str, zone: str
) -> None:
    response = _create(client, "EDGE-NEW", display_timezone=zone, **{box: value})
    assert response.status_code == 422
    assert message in response.text
    assert db.execute(
        select(ReviewSession).where(ReviewSession.code == "EDGE-NEW")
    ).scalar_one_or_none() is None


@pytest.mark.parametrize(("value", "zone"), _EDGE_MOMENTS)
@pytest.mark.parametrize(("box", "message"), _BOXES)
def test_config_save_refuses_an_edge_moment(
    client: TestClient, db: Session, box: str, message: str, value: str, zone: str
) -> None:
    assert _create(client, "EDGE-CFG", display_timezone=zone).status_code == 303
    review_session = _session(db, "EDGE-CFG")
    response = client.post(
        f"/operator/sessions/{review_session.id}/config",
        data={"name": "S", "code": "EDGE-CFG", "description": "", box: value},
        follow_redirects=False,
    )
    assert response.status_code == 422
    assert message in response.text
    db.refresh(review_session)
    assert getattr(review_session, box) is None


@pytest.mark.parametrize(("value", "zone"), _EDGE_MOMENTS)
def test_lobby_edit_refuses_an_edge_deadline(
    client: TestClient, db: Session, value: str, zone: str
) -> None:
    assert _create(client, "EDGE-LOB", display_timezone=zone).status_code == 303
    review_session = _session(db, "EDGE-LOB")
    response = client.post(
        f"/operator/sessions/{review_session.id}/lobby-edit",
        data={"name": "S", "code": "EDGE-LOB", "deadline": value},
        follow_redirects=False,
    )
    assert response.status_code == 422
    assert "deadline must be ISO-8601" in response.text
    db.refresh(review_session)
    assert review_session.deadline is None


def test_a_far_but_safe_moment_still_saves(client: TestClient, db: Session) -> None:
    response = _create(
        client, "EDGE-OK", display_timezone="Asia/Tokyo", deadline="9998-12-31T23:59"
    )
    assert response.status_code == 303
    assert _session(db, "EDGE-OK").deadline.replace(tzinfo=None) == datetime(
        9998, 12, 31, 14, 59
    )


def test_parse_refuses_within_a_day_of_the_edge() -> None:
    for value, zone in _EDGE_MOMENTS:
        with pytest.raises(ValueError):
            date_formatting.parse_local_datetime(value, zone)
    assert date_formatting.parse_local_datetime(
        "9999-12-30T00:00", "UTC"
    ) == datetime(9999, 12, 30)


# ── L2: display tolerates ────────────────────────────────────────────


@pytest.mark.parametrize(
    ("stored", "zone", "shown"),
    [
        # East of UTC, a year-9999 instant would convert past year 9999.
        (datetime(9999, 12, 31, 23, 0), "Asia/Tokyo", "9999-12-31 23:00"),
        # West of UTC, a year-1 instant would convert before year 1.
        # (``strftime`` pads year 1 or not by platform.)
        (datetime(1, 1, 1, 0, 30), "America/New_York", "1-01-01 00:30"),
    ],
)
def test_a_stored_edge_instant_renders(
    client: TestClient, db: Session, stored: datetime, zone: str, shown: str
) -> None:
    assert _create(client, "EDGE-SHOW", display_timezone=zone).status_code == 303
    review_session = _session(db, "EDGE-SHOW")
    owner = db.execute(
        select(User).where(func.lower(User.email) == "alice@example.edu")
    ).scalar_one()
    owner.preferences = {"display_timezone": zone}
    review_session.deadline = stored
    review_session.responses_release_at = stored
    db.commit()
    for url in (
        "/operator/sessions",
        f"/operator/sessions/{review_session.id}",
        f"/operator/sessions/{review_session.id}?editing=1",
    ):
        response = client.get(url)
        assert response.status_code == 200, url
        assert shown in response.text, url


def test_display_helpers_leave_an_edge_instant_unconverted() -> None:
    edge = datetime.max.replace(tzinfo=timezone.utc)
    assert date_formatting.format_datetime(edge, "Asia/Tokyo") == "9999-12-31 23:59"
    assert date_formatting.format_date(edge, "Asia/Tokyo") == "9999-12-31"
    assert date_formatting.format_datetime_local(edge, "Asia/Tokyo") == "9999-12-31T23:59"
    assert date_formatting.iso_in_zone(edge, "Asia/Tokyo").endswith("+00:00")
    # Shown in UTC, so labelled UTC rather than with the session's zone.
    assert date_formatting.gmt_offset_label("Asia/Tokyo", edge) == "UTC"
    assert date_formatting.gmt_offset_zone_label("Asia/Tokyo", edge) == "UTC"
    safe = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert date_formatting.gmt_offset_zone_label("Asia/Tokyo", safe) == "GMT+9 Asia/Tokyo"


@pytest.mark.parametrize(
    "submitted_zone", ["America/New_York", "Asia/Tokyo"], ids=["same", "changed"]
)
@pytest.mark.parametrize(("box", "_message"), _BOXES)
def test_config_save_keeps_an_untouched_stored_edge_value(
    client: TestClient, db: Session, box: str, _message: str, submitted_zone: str
) -> None:
    """A value an older import stored nearer the edge than a box accepts
    does not stop the card saving when the box is left alone (the read
    of #3109), with the zone unchanged or changed (findings L8)."""
    zone = "America/New_York"
    assert _create(client, "EDGE-KEEP", display_timezone=zone).status_code == 303
    review_session = _session(db, "EDGE-KEEP")
    stored = datetime(9999, 12, 31)
    setattr(review_session, box, stored)
    db.commit()
    response = client.post(
        f"/operator/sessions/{review_session.id}/config",
        data={
            "name": "S",
            "code": "EDGE-KEEP",
            "description": "Renamed",
            "display_timezone": submitted_zone,
            box: date_formatting.format_datetime_local(stored, zone),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    db.refresh(review_session)
    assert getattr(review_session, box).replace(tzinfo=None) == stored
    assert review_session.display_timezone == submitted_zone


@pytest.mark.parametrize(
    "value",
    ["9999-12-31T23:59:00", "9999-12-31T23:00:00-05:00", "0001-01-01T00:00:00"],
)
def test_settings_import_refuses_an_edge_datetime(value: str) -> None:
    """The Settings CSV import holds its dates to the boxes' range."""
    with pytest.raises(_ParseError, match="out of range"):
        _parse_datetime(value)
    assert _parse_datetime("9998-12-31T23:59:00") is not None


# ── O3: the audit log's date filter ──────────────────────────────────


_EVENT_AT = datetime(2026, 3, 1, 20, 30, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    ("query", "zone", "shown"),
    [
        # The first day starts before any instant: no lower bound.
        ("from=0001-01-01", "Asia/Tokyo", True),
        ("from=0001-01-01", "America/New_York", True),
        # The last day ends after any instant: no upper bound.
        ("to=9999-12-31", "Asia/Tokyo", True),
        ("to=9999-12-31", "America/New_York", True),
        ("to=9999-12-31&tz=utc", "Asia/Tokyo", True),
        # From the last day, or to the first, holds nothing.
        ("from=9999-12-31", "America/New_York", False),
        ("from=9999-12-31", "Asia/Tokyo", False),
        ("to=0001-01-01", "Asia/Tokyo", False),
        ("from=0001-01-01&to=9999-12-31", "Asia/Tokyo", True),
    ],
)
def test_audit_log_dates_at_the_calendar_edges(
    client: TestClient,
    db: Session,
    make_client,
    bob,
    monkeypatch: pytest.MonkeyPatch,
    query: str,
    zone: str,
    shown: bool,
) -> None:
    monkeypatch.setattr(settings, "sys_admin_emails", ["bob@example.edu"])
    assert _create(client, "EDGE-AUD").status_code == 303
    review_session = _session(db, "EDGE-AUD")
    audit.write_event(
        db,
        event_type="session.activated",
        summary="the dated one",
        session=review_session,
        payload=audit.counts(n=1),
    )
    event = db.execute(
        select(AuditEvent).where(AuditEvent.summary == "the dated one")
    ).scalar_one()
    event.created_at = _EVENT_AT
    db.commit()
    bob_client = make_client(bob)
    bob_client.get("/operator/sys-admin/sessions")  # creates Bob's row
    user = db.execute(
        select(User).where(func.lower(User.email) == "bob@example.edu")
    ).scalar_one()
    user.preferences = {"display_timezone": zone}
    db.commit()

    page = bob_client.get(
        f"/operator/sys-admin/sessions/{review_session.id}/audit-log?{query}"
    )
    assert page.status_code == 200
    assert ("the dated one" in page.text) is shown
    extract = bob_client.get(
        f"/operator/sessions/{review_session.id}/export/audit_log.csv?{query}"
    )
    assert extract.status_code == 200
    summaries = [row[2] for row in csv.reader(io.StringIO(extract.text))][1:]
    assert ("the dated one" in summaries) is shown
