"""Sys Admin → Sessions Diagnostics: the lobby's columns and sort, and a
filter on name, code and owner (author, 2026-10-14)."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import ReviewSession, SessionOperator, User
from app.services import operator_settings, session_owners
from app.web import views

PAGE = "/operator/sys-admin/sessions"


def _user(db: Session, email: str, name: str | None = None) -> User:
    user = User(email=email, display_name=name, is_operator=True)
    db.add(user)
    db.flush()
    return user


def _session(
    db: Session, name: str, code: str, *owners: User, **fields: object
) -> ReviewSession:
    review_session = ReviewSession(
        name=name, code=code, created_by_user_id=owners[0].id, **fields
    )
    db.add(review_session)
    db.flush()
    for owner in owners:
        db.add(SessionOperator(session_id=review_session.id, user_id=owner.id, role="owner"))
    db.flush()
    return review_session


@pytest.fixture
def admin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])


def test_owners_by_session_maps_each_session_in_one_go(db: Session) -> None:
    ann = _user(db, "ann@example.edu")
    ben = _user(db, "ben@example.edu")
    first = _session(db, "First", "first", ann, ben)
    second = _session(db, "Second", "second", ben)
    owners = session_owners.owners_by_session(db, [first.id, second.id])
    assert [u.email for u in owners[first.id]] == ["ann@example.edu", "ben@example.edu"]
    assert [u.email for u in owners[second.id]] == ["ben@example.edu"]
    assert session_owners.owners_by_session(db, []) == {}


def test_a_row_carries_its_name_code_and_owners_for_the_filter(
    db: Session, client: TestClient, admin: None
) -> None:
    ann = _user(db, "Ann@Example.edu", "Ann Lee")
    ben = _user(db, "ben@example.edu")
    _session(db, "Spring Review", "Spring-26", ann, ben)
    db.commit()
    body = client.get(PAGE).text
    text = body.split('data-filter-text="', 1)[1].split('"', 1)[0]
    assert text.split("\n") == [
        "spring review", "spring-26", "ann lee", "ann@example.edu", "ben@example.edu",
    ]
    # The typeahead offers names and codes, then owners by label.
    options = body.split('id="diagnostics-filter-options"', 1)[1].split("</datalist>", 1)[0]
    for value in ("Spring Review", "Spring-26", "Ann Lee", "ben@example.edu"):
        assert f'<option value="{value}">' in options
    # Clear empties the filter, as the lobby's does; a button, not a submit.
    assert re.search(
        r'<button type="button" class="btn secondary"\s+data-diagnostics-filter-clear>Clear</button>',
        body,
    )


def test_the_sort_cookie_orders_the_first_render(
    db: Session, client: TestClient, admin: None
) -> None:
    ann = _user(db, "ann@example.edu")
    # Statuses and ages differ, so a Status sort would visibly reorder:
    # newest first is Gamma, Alpha, Beta; by status it would be Beta
    # (archived), Gamma (draft), Alpha (ready).
    now = datetime.now(timezone.utc)
    _session(db, "Beta", "zz-beta", ann, status="archived", created_at=now - timedelta(days=3))
    _session(db, "Alpha", "zz-alpha", ann, status="ready", created_at=now - timedelta(days=2))
    _session(db, "Gamma", "zz-gamma", ann, status="draft", created_at=now - timedelta(days=1))
    db.commit()

    def order(cookie: list[dict[str, str]] | None) -> list[str]:
        if cookie is not None:
            client.cookies.set("rrw-sort-sys-admin-sessions", quote(json.dumps(cookie)))
        body = client.get(PAGE).text
        client.cookies.clear()
        return sorted(("Alpha", "Beta", "Gamma"), key=lambda n: body.index(f">{n}</a>"))

    assert order([{"key": "name", "dir": "asc"}]) == ["Alpha", "Beta", "Gamma"]
    assert order([{"key": "code", "dir": "desc"}]) == ["Gamma", "Beta", "Alpha"]
    # Status doesn't sort here, so a cookie naming it is ignored: the
    # default order (newest first) stands.
    assert order(None) == ["Gamma", "Alpha", "Beta"]
    assert order([{"key": "status", "dir": "asc"}]) == ["Gamma", "Alpha", "Beta"]


def test_filter_text_lower_cases_as_the_browser_does() -> None:
    """``lower()``, not ``casefold()``: the browser lower-cases the term
    with ``toLowerCase``, which keeps "ß" where ``casefold`` makes it
    "ss", so a picked "Strauß" would match nothing."""
    owner = User(email="o@example.edu", display_name="Johann Strauß")
    text = views.diagnostics_filter_text(ReviewSession(name="Walzer", code="w"), [owner])
    assert "johann strauß" in text.split("\n")


def test_created_deadline_and_timezone_sort_by_the_routes_values(
    db: Session, client: TestClient, admin: None
) -> None:
    """Codex on #3046: the browser sorted the cell text ("No deadline",
    "GMT+8"), the route the stored values (None last, the IANA name), so a
    click and a reload disagreed. The cells now carry the route's value.
    Created too (author, 2026-10-15): its text is to the minute in the
    viewer's zone, the route's key to the microsecond."""
    ann = _user(db, "ann@example.edu")
    _session(db, "Open", "zz-open", ann)
    _session(
        db, "Due", "zz-due", ann,
        created_at=datetime(2026, 10, 1, 9, 30, 15, 250000, tzinfo=timezone.utc),
        deadline=datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc),
        display_timezone="Asia/Singapore",
    )
    db.commit()
    # The viewer reads dates in Tokyo, so the cell shows 21:00; the sort
    # key stays the UTC instant.
    client.get(PAGE)
    viewer = db.execute(select(User).where(User.email == "alice@example.edu")).scalar_one()
    operator_settings.set_display_timezone(db, user=viewer, timezone_name="Asia/Tokyo")
    db.commit()
    body = client.get(PAGE).text
    assert "2026-11-01 21:00" in body

    def cells(code: str) -> list[str]:
        row = body.split(f"<code>{code}</code>", 1)[1].split("</tr>", 1)[0]
        return re.findall(r'<td[^>]*data-sort-value="([^"]*)"', row)

    assert cells("zz-open")[1] == ""  # empty sorts last, either direction
    assert cells("zz-due") == [
        "2026-10-01T09:30:15.250000+00:00",
        "2026-11-01T12:00:00.000000+00:00",
        "Asia/Singapore",
    ]


def test_the_deadline_key_is_utc_and_fixed_width() -> None:
    """An aware value at another offset comes out as UTC, and every key
    carries microseconds, so text order is time order: "12:00:00.5"
    would otherwise collate before "12:00:00" in the browser."""
    tokyo = timezone(timedelta(hours=9))
    keys = [
        views.instant_sort_value(value)
        for value in (
            datetime(2026, 11, 1, 21, 0, 0, tzinfo=tokyo),
            datetime(2026, 11, 1, 12, 0, 0, 500000),
            datetime(2026, 11, 1, 12, 0, 1),
        )
    ]
    assert keys == [
        "2026-11-01T12:00:00.000000+00:00",
        "2026-11-01T12:00:00.500000+00:00",
        "2026-11-01T12:00:01.000000+00:00",
    ]
    assert views.instant_sort_value(None) == ""


def test_status_is_the_one_lobby_column_that_does_not_sort() -> None:
    assert views.LOBBY_SORT_KEYS - views.DIAGNOSTICS_SORT_KEYS == {"status"}
