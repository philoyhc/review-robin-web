"""Sys Admin → Accounts: the Overview card's four lines
(``guide/admin_pages_refine.md`` Item 3 rung 2): the counts by kind,
each linking to its chip alone; accounts new in the last 30 days;
Unused accounts older than that; and sessions with one owner.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import AuditEvent, ReviewSession, SessionOperator, User
from app.services import account_listing

ACCOUNTS = "/operator/sys-admin/users"
NOW = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
OLD = NOW - timedelta(days=account_listing.OVERVIEW_DAYS + 1)
NEW = NOW - timedelta(days=account_listing.OVERVIEW_DAYS - 1)


def _user(db: Session, email: str, created_at: datetime, **flags: bool) -> User:
    user = User(email=email, created_at=created_at, **flags)
    db.add(user)
    db.flush()
    return user


def _session(db: Session, code: str, *owners: User, status: str = "draft") -> None:
    review_session = ReviewSession(
        name=code, code=code, status=status, created_by_user_id=owners[0].id
    )
    db.add(review_session)
    db.flush()
    for owner in owners:
        db.add(SessionOperator(session_id=review_session.id, user_id=owner.id, role="owner"))
    db.flush()


def test_the_counts_split_on_age_kind_and_ownership(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A super-admin is a config email, flag or not; a sys-admin flag
    # alone isn't one.
    monkeypatch.setattr(settings, "super_admin_emails", ["boss@example.edu"])
    _user(db, "boss@example.edu", OLD)
    _user(db, "admin@example.edu", OLD, is_operator=True, is_sys_admin=True)
    _user(db, "admin2@example.edu", OLD, is_operator=True, is_sys_admin=True)
    ann = _user(db, "ann@example.edu", NEW, is_operator=True)
    ben = _user(db, "ben@example.edu", OLD, is_operator=True)
    _user(db, "fresh@example.edu", NEW)  # unused, but too new to clear out
    _user(db, "stale@example.edu", OLD)  # unused and old: the one to clear
    acted = _user(db, "acted@example.edu", OLD)  # old, but has history
    db.add(AuditEvent(event_type="response.submitted", summary="x", actor_user_id=acted.id, detail={}))
    _session(db, "solo", ann)
    _session(db, "pair", ann, ben)
    _session(db, "gone", ben, status="archived")  # archived: no one manages it
    db.flush()

    overview = account_listing.overview(db, now=NOW)
    assert overview == account_listing.AccountsOverview(
        super_admins=1, new_recently=2, unused_stale=1, single_owner_sessions=1
    )


def _chip_count(body: str, key: str) -> str:
    chip = body.split(f'value="{key}"', 1)[1].split("</label>", 1)[0]
    return chip.rsplit("(", 1)[1].split(")", 1)[0]


def test_the_card_renders_the_four_lines_and_their_links(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    for n in range(3):
        _user(db, f"op{n}@example.edu", OLD, is_operator=True)
    db.commit()
    body = client.get(ACCOUNTS).text
    card = body.split('id="accounts-overview"', 1)[1].split("</dl>", 1)[0]
    # Each kind links to the table with its chip alone, and counts as
    # the chip does.
    for key, label in (
        ("operators", "Operators"), ("admins", "Admins"),
        ("no_role", "No role"), ("unused", "Unused"),
    ):
        link = (
            f'<a href="{ACCOUNTS}?show={key}#accounts-table-card" '
            f'data-overview-kind="{key}">{label} {_chip_count(body, key)}</a>'
        )
        assert link in card
    assert 'data-overview-kind="operators">Operators 3</a>' in card
    # No super-admin configured, so Admins carries no note.
    assert "super-admin" not in card
    assert "New in the last 30 days" in card
    assert "Unused for over 30 days" in card
    assert "Sessions with one owner" in card
    # Nothing to clear out on a fresh workspace, so no link to do it.
    assert "Show Unused" not in card


def test_a_stale_unused_account_offers_the_unused_view(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    _user(db, "stale@example.edu", datetime.now(timezone.utc) - timedelta(days=90))
    db.commit()
    card = client.get(ACCOUNTS).text.split('id="accounts-overview"', 1)[1]
    stale = card.split('data-overview="stale">', 1)[1].split("</dd>", 1)[0]
    assert stale.startswith("1")
    assert f'href="{ACCOUNTS}?show=unused#accounts-table-card">Show Unused</a>' in stale


@pytest.mark.parametrize(
    "supers, note",
    [(["alice@example.edu"], "(1 super-admin)"),
     (["alice@example.edu", "boss@example.edu"], "(2 super-admins)")],
)
def test_admins_counts_its_super_admins(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch,
    supers: list[str], note: str,
) -> None:
    monkeypatch.setattr(settings, "super_admin_emails", supers)
    _user(db, "boss@example.edu", OLD, is_operator=True, is_sys_admin=True)
    db.commit()
    card = client.get(ACCOUNTS).text.split('id="accounts-overview"', 1)[1]
    admins = card.split('data-overview-kind="admins">', 1)[1].split(" · ", 1)[0]
    assert admins.endswith(f"</a> {note}")
