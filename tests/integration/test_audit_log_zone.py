"""The audit log reads in the viewer's Settings timezone, or in UTC by
choice: a cycle chip switches between the two, and the zone sets the
"When" column and the From / To day boundaries (page and CSV alike).
The CSV's own timestamps stay UTC."""

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
from app.services import audit
from app.services.audit import AuditFilters

# 20:30 UTC on 1 March is 04:30 on 2 March in Singapore (GMT+8).
_EVENT_AT = datetime(2026, 3, 1, 20, 30, tzinfo=timezone.utc)


def _setup(
    client: TestClient,
    db: Session,
    make_client,
    bob,
    monkeypatch: pytest.MonkeyPatch,
    *,
    code: str,
    zone: str | None = "Asia/Singapore",
):
    """A session with one dated ``session.activated`` event, and Bob
    as a sys-admin whose Settings timezone is ``zone``."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["bob@example.edu"])
    resp = client.post(
        "/operator/sessions",
        data={"name": "Spring", "code": code},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
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
    user.preferences = {"display_timezone": zone} if zone else {}
    db.commit()
    url = f"/operator/sys-admin/sessions/{review_session.public_id}/audit-log"
    csv_url = f"/operator/sessions/{review_session.public_id}/export/audit_log.csv"
    return bob_client, url, csv_url


def test_the_page_reads_in_the_settings_zone_by_default(
    client: TestClient, db: Session, make_client, bob, monkeypatch
) -> None:
    bob_client, url, _ = _setup(client, db, make_client, bob, monkeypatch, code="tz-default")
    body = bob_client.get(url).text
    assert "When (GMT+8)" in body
    assert "From (GMT+8)" in body and "To (GMT+8)" in body
    assert "2026-03-02 04:30" in body
    # The cycle chip names the zone in use and links to the other.
    chip = body.split("data-audit-zone>", 1)[1].split("</span>", 1)[0]
    assert 'class="pill pill-count tag-chip is-selected"' in chip
    assert f'href="{url}?tz=utc"' in chip
    assert ">GMT+8 Asia/Singapore</a>" in chip
    assert "The CSV's times are always UTC." in body


def test_tz_utc_reads_the_page_in_utc_and_keeps_the_choice(
    client: TestClient, db: Session, make_client, bob, monkeypatch
) -> None:
    bob_client, url, csv_url = _setup(client, db, make_client, bob, monkeypatch, code="tz-utc")
    body = bob_client.get(f"{url}?tz=utc&severity=info").text
    assert "When (UTC)" in body and "From (UTC)" in body
    assert "2026-03-01 20:30" in body
    assert f'href="{url}?severity=info"' in body  # the chip goes back
    assert ">UTC</a>" in body
    # Apply, Clear and the CSV all carry the choice.
    assert '<input type="hidden" name="tz" value="utc">' in body
    assert f'href="{url}?tz=utc">Clear</a>' in body
    assert f'href="{csv_url}?severity=info&amp;tz=utc"' in body


def test_a_utc_settings_zone_shows_a_plain_pill(
    client: TestClient, db: Session, make_client, bob, monkeypatch
) -> None:
    bob_client, url, _ = _setup(
        client, db, make_client, bob, monkeypatch, code="tz-none", zone=None
    )
    body = bob_client.get(f"{url}?tz=utc").text
    assert '<span class="pill pill-count">UTC</span>' in body
    assert "?tz=utc" not in body
    assert '<input type="hidden" name="tz"' not in body


@pytest.mark.parametrize(
    ("query", "shown"),
    [
        # 2 March in Singapore holds the event; in UTC it is 1 March.
        ("from=2026-03-02&to=2026-03-02", True),
        ("from=2026-03-02&to=2026-03-02&tz=utc", False),
        ("from=2026-03-01&to=2026-03-01&tz=utc", True),
        ("from=2026-03-01&to=2026-03-01", False),
    ],
)
def test_from_and_to_are_days_in_the_page_zone(
    client: TestClient, db: Session, make_client, bob, monkeypatch, query, shown
) -> None:
    code = "tz-days-" + query.replace("&", "-").replace("=", "")
    bob_client, url, csv_url = _setup(
        client, db, make_client, bob, monkeypatch, code=code[:60]
    )
    assert ("the dated one" in bob_client.get(f"{url}?{query}").text) is shown
    rows = list(csv.reader(io.StringIO(bob_client.get(f"{csv_url}?{query}").text)))
    summaries = [r[2] for r in rows[1:]]
    assert ("the dated one" in summaries) is shown
    if shown:
        # The file's timestamp is UTC whichever zone chose the rows.
        row = next(r for r in rows[1:] if r[2] == "the dated one")
        assert row[5].startswith("2026-03-01T20:30:00")


def test_severity_sits_inline_after_event_type(
    client: TestClient, db: Session, make_client, bob, monkeypatch
) -> None:
    bob_client, url, _ = _setup(client, db, make_client, bob, monkeypatch, code="tz-sev")
    body = bob_client.get(url).text
    head = body.split('<div class="audit-filter-head">', 1)[1].split("</div>", 1)[0]
    assert head.index('for="filter-event-type"') < head.index(">|</span>")
    assert head.index(">|</span>") < head.index(">Severity</span>")
    for value in ("info", "warning", "error"):
        assert f'name="severity" value="{value}"' in head
    assert body.count('name="severity"') == 3


def test_the_extract_event_records_a_non_utc_date_zone() -> None:
    from datetime import date

    dated = AuditFilters(created_from=date(2026, 3, 2), date_zone="Asia/Singapore")
    assert dated.as_audit_context()["date_zone"] == "Asia/Singapore"
    assert "date_zone" not in AuditFilters(created_from=date(2026, 3, 2)).as_audit_context()
    assert AuditFilters(date_zone="Asia/Singapore").as_audit_context() == {}
    assert not AuditFilters(date_zone="Asia/Singapore").is_active


def test_the_default_zone_adds_no_tz_and_older_events_keep_utc(
    client: TestClient, db: Session, make_client, bob, monkeypatch
) -> None:
    from app.web.routes_operator import _sys_admin

    bob_client, url, csv_url = _setup(client, db, make_client, bob, monkeypatch, code="tz-pages")
    body = bob_client.get(f"{url}?severity=info").text
    assert f'href="{csv_url}?severity=info"' in body
    assert '<input type="hidden" name="tz"' not in body
    # A full page offers Older events; under UTC its link keeps the choice.
    monkeypatch.setattr(_sys_admin, "_AUDIT_LOG_PAGE_SIZE", 1)
    body = bob_client.get(f"{url}?tz=utc").text
    older = body.rsplit("Older events &rarr;", 1)[0].rsplit("href=", 1)[1]
    assert "cursor=" in older and "tz=utc" in older
    # The chip back to the Settings zone drops the cursor and the choice.
    cursor_body = bob_client.get(f"{url}?tz=utc&cursor=999999").text
    chip = cursor_body.split("data-audit-zone>", 1)[1].split("</span>", 1)[0]
    assert f'href="{url}"' in chip


@pytest.mark.parametrize(
    ("zone", "chip", "short"),
    [
        ("Etc/UTC", None, "UTC"),
        ("Europe/London", "Europe/London", "Europe/London"),
        ("America/New_York", "America/New_York", "America/New_York"),
        ("Australia/Sydney", "Australia/Sydney", "Australia/Sydney"),
        # A Ramadan shift, not daylight saving: GMT+1 most of the year.
        ("Africa/Casablanca", "Africa/Casablanca", "Africa/Casablanca"),
    ],
)
def test_zero_offset_and_daylight_saving_zones(
    client: TestClient, db: Session, make_client, bob, monkeypatch, zone, chip, short
) -> None:
    code = "tz-" + zone.replace("/", "-").lower()
    bob_client, url, _ = _setup(client, db, make_client, bob, monkeypatch, code=code, zone=zone)
    body = bob_client.get(url).text
    head = body.split("data-audit-zone>", 1)[1].split("</span>", 1)[0]
    if chip is None:
        assert '<span class="pill pill-count">UTC' in head
        assert "<a " not in head
    else:
        assert "tag-chip" in head and chip in head
    # A zone with daylight saving names itself, not today's offset.
    assert f"When ({short})" in body
