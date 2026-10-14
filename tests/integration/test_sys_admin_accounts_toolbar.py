"""Sys Admin → Accounts: the Workspace users toolbar scaffold
(``guide/admin_pages_refine.md`` Item 1 rung 1).

Four category chips with real counts, the Session role dropdown, the
search box and the pager, all inert: nothing filters until rung 2.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import AuditEvent, User
from app.services.users import WorkspaceUserRow
from app.web import views

ACCOUNTS = "/operator/sys-admin/users"


def _row(
    *,
    is_operator: bool = False,
    is_sys_admin: bool = False,
    is_super_admin: bool = False,
    has_history: bool = False,
) -> WorkspaceUserRow:
    return WorkspaceUserRow(
        id=1,
        email="x@example.edu",
        display_name=None,
        is_operator=is_operator,
        is_sys_admin=is_sys_admin,
        is_super_admin=is_super_admin,
        created_at=datetime.now(timezone.utc),
        session_operator_count=0,
        sole_owner_count=0,
        has_history=has_history,
    )


@pytest.mark.parametrize(
    ("row", "category"),
    [
        (_row(is_operator=True), "operators"),
        # Admins win: the Operator flag doesn't put an admin under both.
        (_row(is_operator=True, is_sys_admin=True), "admins"),
        (_row(is_sys_admin=True), "admins"),
        (_row(is_super_admin=True), "admins"),
        (_row(has_history=True), "no_role"),
        (_row(), "unused"),
        # History never moves a row with a role off its role's chip.
        (_row(is_operator=True, has_history=True), "operators"),
    ],
)
def test_every_row_sits_under_exactly_one_chip(
    row: WorkspaceUserRow, category: str
) -> None:
    assert views.account_category(row) == category


def _seed(db: Session, email: str, **flags: bool) -> User:
    user = User(email=email, **flags)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _chip(body: str, key: str) -> str:
    """The markup of one chip's ``<label>``."""
    head, _, tail = body.partition(f'value="{key}"')
    assert tail, f"no {key} chip"
    return head[head.rindex("<label") :] + tail.split("</label>", 1)[0]


@pytest.fixture
def seeded(
    db: Session, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> str:
    """Alice (the signed-in admin), one operator, one more admin, one
    no-role account with history and one without. Returns the page."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    _seed(db, "bob@example.edu", is_operator=True)
    _seed(db, "carol@example.edu", is_sys_admin=True)
    dave = _seed(db, "dave@example.edu")
    db.add(
        AuditEvent(
            event_type="response.submitted", summary="Submitted",
            actor_user_id=dave.id, detail={},
        )
    )
    db.commit()
    _seed(db, "erin@example.edu")
    response = client.get(ACCOUNTS)
    assert response.status_code == 200
    return response.text


def test_chips_count_the_whole_table_with_operators_and_admins_on(
    seeded: str,
) -> None:
    body = seeded
    expected = {
        "operators": ("Operators (1)", True),
        "admins": ("Admins (2)", True),
        "no_role": ("No role (1)", False),
        "unused": ("Unused (1)", False),
    }
    for key, (label, on) in expected.items():
        chip = _chip(body, key)
        assert 'class="pill pill-count tag-chip"' in chip, key
        assert label in chip, key
        assert ("checked" in chip) is on, key
    # In toolbar order, after the row's label.
    positions = [body.index(f'value="{key}"') for key in expected]
    assert positions == sorted(positions)
    assert body.index("<span>Show:</span>") < positions[0]


def test_the_toolbar_is_the_setup_pages_two_panes(seeded: str) -> None:
    body = seeded
    assert 'class="card table-pager-anchored" id="accounts-table-card"' in body
    toolbar = body.split('<div class="table-card-toolbar is-split">', 1)[1]
    left, right = toolbar.split('<div class="toolbar-pane toolbar-right">', 1)
    assert "data-account-chips" in left
    right = right.split("{# .table-card-toolbar #}", 1)[0]
    # Session role where the roster pages put Status, then search.
    assert right.index("Session role:") < right.index("Search:")
    options = [
        option.split(">", 1)[1].split("<", 1)[0]
        for option in right.split("<option ")[1:]
    ]
    assert options == ["Any", "Reviewer", "Reviewee", "Observer", "Owner"]
    assert 'placeholder="Email or name"' in right
    # Inert: Search can't submit, and with no filter active there is
    # no Clear.
    assert '<button class="btn secondary" type="submit" disabled>Search</button>' in right
    assert ">Clear<" not in right
    # Five accounts fit one page, so no pager renders.
    assert '<div class="table-pager-cluster' not in body


def test_the_scaffold_filters_nothing(
    seeded: str, client: TestClient
) -> None:
    """Rung 1 reads no chip, role or search parameter: every account
    still renders, including the ones under chips that are off."""
    body = client.get(
        f"{ACCOUNTS}?show=unused&role=reviewer&q=bob&offset=200"
    ).text
    for name in ("alice", "bob", "carol", "dave", "erin"):
        assert f"<code>{name}@example.edu</code>" in body, name
    assert "checked" in _chip(body, "operators")
    assert "checked" not in _chip(body, "unused")


def test_past_one_page_the_pager_renders_above_and_below(
    db: Session, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    db.add_all(User(email=f"user{n}@example.edu") for n in range(200))
    db.commit()
    body = client.get(ACCOUNTS).text
    assert body.count('<div class="table-pager-cluster') == 2
    assert "<summary>1–200</summary>" in body
    assert (
        'href="/operator/sys-admin/users?offset=200#accounts-table-card"'
        in body
    )
    # Pager, then the table, then the bottom copy.
    assert (
        body.index('<div class="table-pager-cluster"')
        < body.index('id="users-table"')
        < body.index("table-pager-cluster table-pager-cluster-bottom")
    )
