"""A verified account's address reads as the roster pill (segment 19Z,
accounts item, author 2026-10-31): bound to its person in the directory,
at a checked invite or a sign-in (`users.external_principal_id`). The
Accounts table, Session Home's Owners card and the New session owners
picker show it; an unbound account stays plain code."""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import User

from .test_session_home_owners_card import CREATOR, _add_bob, _create, _home
from .test_sys_admin_users import _bootstrap_sys_admin

PILL = re.compile(r'<code class="pill pill-count pill-address" title="Matched to a directory account" data-directory-matched>([^<]+)</code>')
OBJECT_ID = "99999999-9999-4999-8999-999999999999"


def _bind(db: Session, email: str) -> None:
    db.execute(select(User).where(User.email == email)).scalar_one().external_principal_id = OBJECT_ID
    db.commit()


def test_the_accounts_table_pills_a_verified_account(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _bootstrap_sys_admin(monkeypatch, email=CREATOR)
    client.get("/operator/sys-admin/users")  # signs the admin in
    db.add_all([User(email="Bound@Example.edu", display_name="Bea Bound", is_operator=True),
                User(email="plain@example.edu", display_name="Pat Plain", is_operator=True),
                User(email="nameless@example.edu", is_operator=True)])
    db.commit()
    _bind(db, "Bound@Example.edu")
    page = client.get("/operator/sys-admin/users?show=operators&show=unused").text
    assert "Bound@Example.edu" in PILL.findall(page)  # case kept
    assert "<code>plain@example.edu</code>" in page
    # The name too (author, 2026-10-31): the pill for a verified account.
    assert '<span class="pill pill-count pill-address" title="Matched to a directory account" data-directory-matched>Bea Bound</span>' in page
    assert "<td>Pat Plain</td>" in page
    nameless = page[page.index("nameless@example.edu</code>"):]
    assert nameless.split("<td>", 2)[1].startswith("—</td>")


def test_the_owners_card_pills_a_verified_owner(client: TestClient, db: Session) -> None:
    review_session = _create(client, db, "pill-owners")
    _add_bob(db, review_session)
    _bind(db, "bob@example.edu")
    page = _home(client, review_session)
    assert "bob@example.edu" in PILL.findall(page)


def test_the_new_session_picker_marks_a_verified_candidate(client: TestClient, db: Session) -> None:
    client.get("/operator/sessions/new")  # signs the creator in
    db.add_all([User(email="bob@example.edu", is_operator=True), User(email="cy@example.edu", is_operator=True)])
    db.commit()
    _bind(db, "bob@example.edu")
    page = client.get("/operator/sessions/new").text
    assert '<option value="bob@example.edu" data-verified>' in page
    assert '<option value="cy@example.edu">' in page
