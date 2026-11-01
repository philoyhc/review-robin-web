"""Accounts › Invite takes several addresses, comma-separated (19X Item
14): each is invited as one would be on its own, one refusal stops none of
the rest, and the summary names what was refused. A new row is not
selected."""

from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import User
from app.services.users import INVITE_LIST_MAX, split_invite_list
from app.web.routes_operator import _sys_admin

from .test_sys_admin_users import _bootstrap_sys_admin


@pytest.mark.parametrize(
    ("text", "entries"),
    [
        ("a@x.edu, b@x.edu", ["a@x.edu", "b@x.edu"]),
        ("Jane Tan <jane@x.edu>,Bob <bob@x.edu>", ["Jane Tan <jane@x.edu>", "Bob <bob@x.edu>"]),
        ("Tan, Jane <jane@x.edu>, b@x.edu", ["Tan, Jane <jane@x.edu>", "b@x.edu"]),
        ("a@x.edu, , b@x.edu,", ["a@x.edu", "b@x.edu"]),
        ("a@x.edu, trailing name", ["a@x.edu", "trailing name"]),
        # A stray word stays its own entry; it never sinks the address after it.
        ("alice@x.edu, Arun, carol@x.edu", ["alice@x.edu", "Arun", "carol@x.edu"]),
        ("Bob, Tan, Jane <j@x.edu>", ["Bob", "Tan, Jane <j@x.edu>"]),
        ("", [""]),
    ],
)
def test_the_list_splits_at_commas_keeping_a_comma_in_a_name(text: str, entries: list[str]) -> None:
    assert split_invite_list(text) == entries


def _invite(client: TestClient, text: str):
    return client.post("/operator/sys-admin/users/invite", data={"email": text}, follow_redirects=False)


def _emails(db: Session) -> set[str]:
    db.expire_all()
    return set(db.execute(select(User.email)).scalars())


def test_several_are_invited_and_the_refused_are_named(
    db: Session, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    response = _invite(client, "one@example.edu, Two Person <two@example.edu>, alice@example.edu, not-an-address")
    query = parse_qs(urlsplit(response.headers["location"]).query)
    assert query["invited"] == ["2"] and query["invite_unchecked"] == ["2"]
    assert query["invite_refused"] == ["duplicate:alice@example.edu", "invalid_email:not-an-address"]
    assert "selected" not in query
    assert {"one@example.edu", "two@example.edu"} <= _emails(db)
    db.expire_all()
    assert db.execute(select(User).where(User.email == "two@example.edu")).scalar_one().display_name == "Two Person"

    page = client.get(response.headers["location"]).text
    assert "Invited 2 people." in page
    assert "<code>alice@example.edu</code> already has an account here." in page
    assert "<code>not-an-address</code> isn&#39;t one whole email address." in page


def test_each_address_is_checked_against_the_directory(
    db: Session, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cordware.graph import FakeDirectory

    monkeypatch.setattr(_sys_admin, "directory_or_none", lambda request: FakeDirectory())
    monkeypatch.setattr(_sys_admin, "is_local", lambda: False)
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    response = _invite(client, "Jane Tan <jane.tan@example.edu>, nobody@example.edu, arun.kumar@example.edu")
    query = parse_qs(urlsplit(response.headers["location"]).query)
    assert query["invited"] == ["2"] and "invite_unchecked" not in query
    assert query["invite_refused"] == ["not_in_directory:nobody@example.edu"]
    db.expire_all()
    jane = db.execute(select(User).where(User.email == "jane.tan@example.edu")).scalar_one()
    assert jane.external_principal_id and jane.display_name == "Jane Tan"


def test_too_many_invites_none(db: Session, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    text = ", ".join(f"p{i}@example.edu" for i in range(INVITE_LIST_MAX + 1))
    response = _invite(client, text)
    assert response.headers["location"].endswith("invite_error=too_many")
    assert not any(e.startswith("p") for e in _emails(db))


def test_a_refusal_code_from_the_url_is_never_shown(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    page = client.get("/operator/sys-admin/users?invited=0&invite_refused=%3Cb%3Ebold%3C%2Fb%3E:x%40y.edu").text
    assert "couldn&#39;t be invited" in page and "<b>bold</b>" not in page


def test_a_duplicate_inside_the_list_is_refused_the_second_time(
    db: Session, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    response = _invite(client, "dup@example.edu, Dup@Example.edu")
    query = parse_qs(urlsplit(response.headers["location"]).query)
    assert query["invited"] == ["1"] and query["invite_refused"] == ["duplicate:Dup@Example.edu"]


def test_the_directory_is_asked_about_the_whole_list_at_once(
    db: Session, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One budget for the request, not one per address (diff-reviewer)."""
    from app.services import directory_accounts
    from cordware.graph import FakeDirectory

    calls: list[list[str]] = []
    real = directory_accounts.look_up_all

    def counting(directory, keys, *, budget):
        calls.append(list(keys))
        return real(directory, keys, budget=budget)

    monkeypatch.setattr(directory_accounts, "look_up_all", counting)
    monkeypatch.setattr(_sys_admin, "directory_or_none", lambda request: FakeDirectory())
    monkeypatch.setattr(_sys_admin, "is_local", lambda: False)
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    _invite(client, "jane.tan@example.edu, arun.kumar@example.edu")
    assert calls == [["jane.tan@example.edu", "arun.kumar@example.edu"]]


def test_a_plain_admin_s_sys_admin_list_asks_the_directory_nothing(
    db: Session, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every entry is refused `requires_super_admin` before any lookup."""
    from cordware.graph import FakeDirectory
    from cordware.settings import identity_settings

    from app.services import directory_accounts

    asked: list[str] = []
    monkeypatch.setattr(directory_accounts, "look_up_all", lambda d, keys, *, budget: asked.extend(keys) or {})
    monkeypatch.setattr(_sys_admin, "directory_or_none", lambda request: FakeDirectory())
    monkeypatch.setattr(_sys_admin, "is_local", lambda: False)
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    monkeypatch.setattr(identity_settings, "super_admin_emails", ["boss@example.edu"])
    response = client.post(
        "/operator/sys-admin/users/invite",
        data={"email": "jane.tan@example.edu, arun.kumar@example.edu", "invite_as_sys_admin": "true"},
        follow_redirects=False,
    )
    query = parse_qs(urlsplit(response.headers["location"]).query)
    assert query["invited"] == ["0"] and asked == []
    assert all(r.startswith("requires_super_admin:") for r in query["invite_refused"])
