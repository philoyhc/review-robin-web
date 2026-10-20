"""The lobby's Created, Deadline and Timezone, and the archive's Created,
Archived and Timezone, sort on a click as a reload sorts them (author,
2026-10-14 and -15). The browser sorted the cell text ("No deadline",
"GMT+8", a date to the minute), the route the stored values (None last,
the IANA name, the instant to the microsecond); the cells now carry the
route's value, as Sessions Diagnostics' do."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from urllib.parse import quote

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, User
from app.services import operator_settings, sessions
from app.web import views


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


def test_the_lobby_dates_and_timezone_carry_the_routes_values(
    client: TestClient, db: Session
) -> None:
    no_zone = _session(client, db, "zz-open", display_timezone=None)
    _session(
        client, db, "zz-due",
        created_at=datetime(2026, 10, 1, 9, 30, 15, 250000, tzinfo=timezone.utc),
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
    assert _sort_values(body, "zz-open")[1] == ""  # empty sorts last, either way
    # A session with no zone of its own sorts by the zone it falls back
    # to, as the route does, not by an empty or "None" value.
    assert _sort_values(body, "zz-open")[2] == sessions.resolve_session_timezone(no_zone)
    assert _sort_values(body, "zz-due") == [
        "2026-10-01T09:30:15.250000+00:00",
        "2026-11-01T12:00:00.000000+00:00",
        "Asia/Singapore",
        "0",  # Status, a draft's lifecycle place
    ]


def test_the_archive_dates_and_timezone_carry_the_routes_values(
    client: TestClient, db: Session
) -> None:
    _session(
        client, db, "zz-gone", status="archived", display_timezone="Europe/Paris",
        created_at=datetime(2026, 9, 1, 8, 0, 0, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 10, 2, 17, 45, 0, 999999, tzinfo=timezone.utc),
    )
    body = client.get("/operator/sessions/archived").text
    assert _sort_values(body, "zz-gone") == [
        "2026-09-01T08:00:00.000001+00:00",
        "2026-10-02T17:45:00.999999+00:00",
        "Europe/Paris",
        "4",  # Status, archived
    ]


def test_status_sorts_in_lifecycle_order_on_a_reload_and_a_click(
    client: TestClient, db: Session
) -> None:
    """Status sorts Draft → Validated → Activated → Closed (author,
    2026-10-15), on a reload by `session_sort_value` and on a click by
    the cell's matching number, not by the enum string or the label."""
    # Ages chosen so the default order (newest first) is neither the
    # lifecycle order nor its reverse: closed, draft, active, valid.
    for code, status, day in (
        ("zz-closed", "expired", 4), ("zz-draft", "draft", 3),
        ("zz-active", "ready", 2), ("zz-valid", "validated", 1),
    ):
        _session(
            client, db, code, status=status,
            created_at=datetime(2026, 10, day, tzinfo=timezone.utc),
        )
    lifecycle = ["zz-draft", "zz-valid", "zz-active", "zz-closed"]

    def order(direction: str) -> list[str]:
        client.cookies.set(
            "rrw-sort-lobby", quote(json.dumps([{"key": "status", "dir": direction}]))
        )
        body = client.get("/operator/sessions").text
        client.cookies.clear()
        return sorted(lifecycle, key=lambda c: body.index(f"<code>{c}</code>"))

    assert order("asc") == lifecycle
    assert order("desc") == lifecycle[::-1]
    body = client.get("/operator/sessions").text
    assert [_sort_values(body, c)[-1] for c in lifecycle] == ["0", "1", "2", "3"]


def test_an_unknown_status_has_no_lifecycle_place() -> None:
    assert views.status_sort_value("archived") == 4
    assert views.status_sort_value("retired") is None
    assert views.status_sort_cell("retired") == ""


def test_name_and_code_sort_as_a_click_does(
    client: TestClient, db: Session
) -> None:
    """A reload sorts text as a click does (author, 2026-10-15): case
    aside, and digit runs as numbers. Python's `<` alone put "Beta"
    before "alpha", and "Session 10" before "session 2", where the
    browser's `localeCompare(…, {numeric: true})` doesn't."""
    for name, code in (
        ("Session 10", "S-10"), ("beta", "b-two"), ("session 2", "s-2"), ("Alpha", "A-one"),
    ):
        client.post("/operator/sessions", data={"name": name, "code": code})
    expected = ["A-one", "b-two", "s-2", "S-10"]

    def order(key: str) -> list[str]:
        client.cookies.set("rrw-sort-lobby", quote(json.dumps([{"key": key, "dir": "asc"}])))
        body = client.get("/operator/sessions").text
        client.cookies.clear()
        return sorted(expected, key=lambda c: body.index(f"<code>{c}</code>"))

    assert order("name") == expected
    assert order("code") == expected


def test_the_text_keys_fold_case_trim_and_read_numbers() -> None:
    row = ReviewSession(name="  Session 10 ", code="ZZ-1")
    row.created_by_user = User(email="ann@example.edu", display_name="Ann Lee")
    assert views.session_sort_value(row, "name") == ("session 0", 10, "")
    assert views.session_sort_value(row, "code") == ("zz-0", 1, "")
    assert views.session_sort_value(row, "created_by") == ("ann lee",)
    # Leading digits keep text at the even places, so keys always
    # compare like with like; digits come before letters, as in the
    # browser.
    assert views.text_sort_value("2nd") == ("0", 2, "nd") < views.text_sort_value("abc")


def test_text_keys_order_as_the_browser_does() -> None:
    """Pairs a read checked against `localeCompare(…, {numeric: true})`:
    a space or hyphen before a digit sorts before the digit itself."""
    browser_order = [
        "a-1", "a1", "alpha", "Beta", "CS 101", "CS-101", "CS101", "cs102",
        "Session 2", "Session 10", "Session1", "Spring 2024", "Spring2024",
        "x 10", "x9",
    ]
    # Reversed first: `sorted` is stable, so in-order input would let a
    # key that ties two of these pass.
    assert sorted(reversed(browser_order), key=views.text_sort_value) == browser_order
    assert views.text_sort_value("") is None
    assert views.text_sort_value("   ") is None


def test_the_lobby_count_pills_come_from_the_shared_helper(
    client: TestClient, db: Session
) -> None:
    """The lobby's Sessions card and Sessions Diagnostics' Sessions
    Overview read `views.session_status_counts` (2026-10-15). Validated
    counts as draft; Closed counts only in the total; archived counts in
    its own pill only, not in the lobby's total (19X Item 9), though
    Diagnostics' total still holds it (test_sys_admin_sessions_table)."""
    for code, status in (
        ("zz-a", "draft"), ("zz-b", "validated"), ("zz-c", "ready"),
        ("zz-d", "expired"), ("zz-e", "archived"),
    ):
        _session(client, db, code, status=status)
    body = client.get("/operator/sessions").text
    pills = body.split('<div class="sessions-lobby-pills">', 1)[1].split("</div>", 1)[0]
    for pill in (
        '<span class="pill pill-count">4 sessions</span>',
        '<span class="pill pill-lifecycle-draft">2 draft</span>',
        '<span class="pill pill-lifecycle-ready">1 activated</span>',
        '<span class="pill pill-lifecycle-archived">1 archived</span>',
    ):
        assert pill in pills
