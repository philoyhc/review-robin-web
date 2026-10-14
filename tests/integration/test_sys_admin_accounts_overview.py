"""Sys Admin → Accounts: the Overview card (``guide/archive/
admin_pages_refine.md`` Item 3, cut down by the author 2026-10-14): two
rows of count pills and nothing else, Operators · Admins · super-admins,
then No role · Unused. No links, no other lines.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import AuditEvent, User
from app.services import account_listing

ACCOUNTS = "/operator/sys-admin/users"


def _user(db: Session, email: str, **flags: bool) -> User:
    user = User(email=email, created_at=datetime.now(timezone.utc), **flags)
    db.add(user)
    db.flush()
    return user


def test_super_admins_are_config_emails_with_an_account(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A super-admin is a config email, flag or not; a sys-admin flag
    # alone isn't one, and a config email with no account counts nothing.
    monkeypatch.setattr(
        settings, "super_admin_emails", ["Boss@example.edu", "ghost@example.edu"]
    )
    _user(db, "boss@example.edu")
    _user(db, "admin@example.edu", is_operator=True, is_sys_admin=True)
    assert account_listing.count_super_admins(db) == 1


def _card(client: TestClient) -> str:
    body = client.get(ACCOUNTS).text
    return body.split('id="accounts-overview"', 1)[1].split('id="accounts-table-card"', 1)[0]


def _pill(key: str, text: str) -> str:
    return f'<span class="pill pill-count" data-overview="{key}">{text}</span>'


def test_the_card_is_two_rows_of_pills(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    monkeypatch.setattr(settings, "super_admin_emails", [])
    # A different count for every kind, so a pill can't show another's.
    for n in range(3):
        _user(db, f"op{n}@example.edu", is_operator=True)
    for n in range(2):
        acted = _user(db, f"acted{n}@example.edu")
        db.add(AuditEvent(event_type="response.submitted", summary="x", actor_user_id=acted.id, detail={}))
    for n in range(4):
        _user(db, f"unused{n}@example.edu")
    db.commit()
    card = _card(client)
    rows = card.split('<p class="overview-pills">')[1:]
    assert len(rows) == 2
    # The signed-in sys-admin is the one Admin; no super-admin configured.
    assert rows[0].split("</p>", 1)[0] == (
        _pill("operators", "3 Operators") + " · "
        + _pill("admins", "1 Admins") + " · "
        + _pill("super_admins", "0 super-admins")
    )
    assert rows[1].split("</p>", 1)[0] == (
        _pill("no_role", "2 No role") + " · " + _pill("unused", "4 Unused")
    )
    # Nothing else on the card: no links, no other lines.
    assert "<a " not in card
    assert "<dl" not in card


@pytest.mark.parametrize(
    "supers, text",
    [(["alice@example.edu"], "1 super-admin"),
     (["alice@example.edu", "boss@example.edu"], "2 super-admins")],
)
def test_the_super_admin_pill_counts_them(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch,
    supers: list[str], text: str,
) -> None:
    monkeypatch.setattr(settings, "super_admin_emails", supers)
    _user(db, "boss@example.edu", is_operator=True, is_sys_admin=True)
    db.commit()
    assert _pill("super_admins", text) in _card(client)
