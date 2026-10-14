"""Sys Admin → Sessions Diagnostics: the lobby's columns and sort, and a
filter on name, code and owner (author, 2026-10-14)."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import ReviewSession, SessionOperator, User
from app.services import session_owners
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
    # Cancel clears the filter; it is a button, not a submit.
    assert re.search(
        r'<button type="button" class="btn secondary"\s+data-diagnostics-filter-cancel>Cancel</button>',
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


def test_status_is_the_one_lobby_column_that_does_not_sort() -> None:
    assert views.LOBBY_SORT_KEYS - views.DIAGNOSTICS_SORT_KEYS == {"status"}
