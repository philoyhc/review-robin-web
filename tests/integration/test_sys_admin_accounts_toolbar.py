"""Sys Admin → Accounts: the Workspace users toolbar
(``guide/admin_pages_refine.md`` Item 1).

Category chips, the Session role, the search and the pager, all filtered
on the server (``app/services/account_listing.py``) with the view held in
the URL.
"""
from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import (
    AuditEvent,
    Observer,
    Reviewee,
    Reviewer,
    ReviewSession,
    SessionOperator,
    User,
)
from app.services import account_listing
from app.web import views

ACCOUNTS = "/operator/sys-admin/users"


def _seed(db: Session, email: str, name: str | None = None, **flags: bool) -> User:
    user = User(email=email, display_name=name, **flags)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _acted(db: Session, user: User) -> None:
    db.add(
        AuditEvent(
            event_type="response.submitted", summary="Submitted",
            actor_user_id=user.id, detail={},
        )
    )
    db.commit()


def _session(db: Session, creator: User, code: str) -> ReviewSession:
    review_session = ReviewSession(
        name=f"Session {code}", code=code, created_by_user_id=creator.id
    )
    db.add(review_session)
    db.commit()
    return review_session


def _chip(body: str, key: str) -> str:
    """The markup of one chip's ``<label>``."""
    head, _, tail = body.partition(f'name="show" value="{key}"')
    assert tail, f"no {key} chip"
    return head[head.rindex("<label") :] + tail.split("</label>", 1)[0]


def _emails(body: str) -> set[str]:
    return {
        cell.split("</code>", 1)[0]
        for cell in body.split('id="users-table"', 1)[-1].split("<td><code>")[1:]
    }


@pytest.fixture
def admin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])


@pytest.fixture
def workspace(db: Session, client: TestClient, admin: None) -> dict[str, User]:
    """Alice (the signed-in admin, created on first request), plus one
    account of each kind."""
    client.get(ACCOUNTS)
    people = {
        "bob": _seed(db, "bob@example.edu", "Bob Operator", is_operator=True),
        "carol": _seed(db, "carol@example.edu", "Carol Admin", is_sys_admin=True),
        "dave": _seed(db, "dave@example.edu", "Dave Reviewer"),
        "erin": _seed(db, "Erin@Example.edu", "Erin Unused"),
    }
    _acted(db, people["dave"])
    return people


# --- The category rule ------------------------------------------------------


def test_every_account_sits_under_exactly_one_chip(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "super_admin_emails", ["Super@Example.edu"])
    operator = _seed(db, "op@example.edu", is_operator=True)
    # Admins win: the Operator flag doesn't put an admin under both.
    admin_operator = _seed(db, "ao@example.edu", is_operator=True, is_sys_admin=True)
    admin = _seed(db, "ad@example.edu", is_sys_admin=True)
    # A super-admin email whose row hasn't signed in since config named it.
    super_admin = _seed(db, "super@example.edu")
    actor = _seed(db, "actor@example.edu")
    _acted(db, actor)
    creator = _seed(db, "creator@example.edu")
    made = _session(db, creator, "made-by-creator")
    # Owning a session is history too (author, 2026-10-14): a co-owner
    # who never acted.
    owner = _seed(db, "owner@example.edu")
    db.add(SessionOperator(session_id=made.id, user_id=owner.id))
    db.commit()
    unused = _seed(db, "unused@example.edu")
    # History never moves a row with a role off its role's chip.
    busy_operator = _seed(db, "busy@example.edu", is_operator=True)
    _acted(db, busy_operator)

    expected = {
        operator: "operators",
        admin_operator: "admins",
        admin: "admins",
        super_admin: "admins",
        actor: "no_role",
        creator: "no_role",
        owner: "no_role",
        unused: "unused",
        busy_operator: "operators",
    }
    for user, category in expected.items():
        assert account_listing.category_of(db, user.id) == category, user.email
    assert account_listing.category_of(db, 999_999) is None


def test_the_view_tables_line_up_with_the_service() -> None:
    assert (
        tuple(key for key, _, _ in views.ACCOUNT_CATEGORIES)
        == account_listing.CATEGORIES
    )
    assert (
        tuple(key for key, _ in views.ACCOUNT_ROLE_OPTIONS[1:])
        == account_listing.SESSION_ROLES
    )


# --- Chips ------------------------------------------------------------------


def test_chips_count_the_whole_table_and_default_to_operators_and_admins(
    workspace: dict[str, User], client: TestClient
) -> None:
    body = client.get(ACCOUNTS).text
    expected = {
        "operators": ("Operators (1)", True),
        "admins": ("Admins (2)", True),
        "no_role": ("No role (1)", False),
        "unused": ("Unused (1)", False),
    }
    for key, (label, on) in expected.items():
        chip = _chip(body, key)
        assert label in chip, key
        assert ("checked" in chip) is on, key
        assert 'form="accounts-filter"' in chip, key
    assert _emails(body) == {
        "alice@example.edu", "bob@example.edu", "carol@example.edu"
    }


def test_a_chip_shows_only_its_rows(
    workspace: dict[str, User], client: TestClient
) -> None:
    body = client.get(f"{ACCOUNTS}?show=unused").text
    assert _emails(body) == {"Erin@Example.edu"}
    assert "checked" in _chip(body, "unused")
    assert "checked" not in _chip(body, "operators")
    body = client.get(f"{ACCOUNTS}?show=no_role&show=unused").text
    assert _emails(body) == {"dave@example.edu", "Erin@Example.edu"}


def test_every_chip_off_shows_none_and_says_so(
    workspace: dict[str, User], client: TestClient
) -> None:
    body = client.get(f"{ACCOUNTS}?show=").text
    assert _emails(body) == set()
    assert "No accounts match the chips above." in body
    # The toolbar stays, so the chips can be turned back on.
    assert 'id="accounts-filter"' in body


def test_counts_ignore_the_role_and_the_search(
    workspace: dict[str, User], client: TestClient
) -> None:
    body = client.get(f"{ACCOUNTS}?q=nobody-matches").text
    assert "Operators (1)" in _chip(body, "operators")
    assert "No accounts match the current filter." in body


# --- Search and Session role ------------------------------------------------


def test_search_matches_email_or_name_case_insensitively(
    workspace: dict[str, User], client: TestClient
) -> None:
    assert _emails(client.get(f"{ACCOUNTS}?q=BOB").text) == {"bob@example.edu"}
    assert _emails(client.get(f"{ACCOUNTS}?q=carol+adm").text) == {
        "carol@example.edu"
    }
    # A wildcard is a literal, not a pattern.
    assert _emails(client.get(f"{ACCOUNTS}?q=%25").text) == set()
    # The search spans only the chips that are on.
    assert _emails(client.get(f"{ACCOUNTS}?q=erin").text) == set()
    assert _emails(client.get(f"{ACCOUNTS}?show=unused&q=erin").text) == {
        "Erin@Example.edu"
    }


def test_session_role_matches_roster_emails_in_any_session(
    db: Session, workspace: dict[str, User], client: TestClient
) -> None:
    session = _session(db, workspace["bob"], "roles")
    db.add_all(
        [
            Reviewer(session_id=session.id, name="Bob", email="BOB@example.edu"),
            Reviewee(
                session_id=session.id, name="Carol",
                email_or_identifier="carol@EXAMPLE.edu",
            ),
            Observer(session_id=session.id, email="bob@example.edu"),
            SessionOperator(
                session_id=session.id, user_id=workspace["carol"].id, role="owner"
            ),
        ]
    )
    db.commit()
    show_all = "show=operators&show=admins&show=no_role&show=unused"

    def matching(role: str) -> set[str]:
        return _emails(client.get(f"{ACCOUNTS}?{show_all}&role={role}").text)

    assert matching("reviewer") == {"bob@example.edu"}
    assert matching("reviewee") == {"carol@example.edu"}
    assert matching("observer") == {"bob@example.edu"}
    assert matching("owner") == {"carol@example.edu"}
    assert len(matching("any")) == 5
    body = client.get(f"{ACCOUNTS}?{show_all}&role=reviewer").text
    assert '<option value="reviewer" selected>' in body


def test_clear_drops_the_role_and_search_but_keeps_the_chips(
    workspace: dict[str, User], client: TestClient
) -> None:
    assert ">Clear<" not in client.get(ACCOUNTS).text
    body = client.get(f"{ACCOUNTS}?show=unused&role=owner&q=x").text
    clear = body.split(">Clear<", 1)[0].rsplit("href=", 1)[1]
    assert clear.startswith(f'"{ACCOUNTS}?show=unused#accounts-table-card"')


def test_the_typeahead_offers_emails_and_names_under_the_chips(
    workspace: dict[str, User], client: TestClient
) -> None:
    body = client.get(ACCOUNTS).text
    options = body.split('<datalist id="accounts-search-options">', 1)[1]
    options = options.split("</datalist>", 1)[0]
    assert '<option value="bob@example.edu">' in options
    assert '<option value="Bob Operator">' in options
    assert "Erin" not in options


def test_the_typeahead_reaches_past_the_first_two_hundred(
    db: Session, client: TestClient, admin: None
) -> None:
    """The page's first list stops 200 entries in, near the start of the
    alphabet; the box asks ``search-options`` again as the operator
    types, which shows up to 200 *matches*, so a late account can still
    be suggested."""
    client.get(ACCOUNTS)
    _many(db, 250, is_operator=True)
    late = _seed(db, "zoe@example.edu", "Zoe Last", is_operator=True)
    body = client.get(ACCOUNTS).text
    assert late.email not in body.split('<datalist id="accounts-search-options">', 1)[1].split("</datalist>", 1)[0]

    # The page's own first list matches what the box already holds.
    reloaded = client.get(f"{ACCOUNTS}?q=zoe").text
    first = reloaded.split('<datalist id="accounts-search-options">', 1)[1]
    assert '<option value="zoe@example.edu">' in first.split("</datalist>", 1)[0]

    response = client.get(f"{ACCOUNTS}/search-options?q=zoe")
    assert response.status_code == 200
    assert response.json() == ["Zoe Last", "zoe@example.edu"]
    # Typing little still caps the list at 200, which typing more narrows.
    assert len(client.get(f"{ACCOUNTS}/search-options?q=user").json()) == 200
    assert len(client.get(f"{ACCOUNTS}/search-options?q=user02").json()) == 50


def test_the_typeahead_follows_the_chips(
    workspace: dict[str, User], client: TestClient
) -> None:
    assert client.get(f"{ACCOUNTS}/search-options?q=erin").json() == []
    assert client.get(
        f"{ACCOUNTS}/search-options?show=unused&q=erin"
    ).json() == ["Erin Unused", "Erin@Example.edu"]
    # A blank ``show`` is no chip at all, as on the page.
    assert client.get(f"{ACCOUNTS}/search-options?show=&q=bob").json() == []


def test_the_typeahead_needs_an_admin(client: TestClient) -> None:
    response = client.get(f"{ACCOUNTS}/search-options?q=a", follow_redirects=False)
    assert response.status_code in {303, 403, 404}


def test_unknown_values_fall_back_rather_than_fail(
    workspace: dict[str, User], client: TestClient
) -> None:
    response = client.get(f"{ACCOUNTS}?show=bogus&role=bogus&offset=-5")
    assert response.status_code == 200
    assert _emails(response.text) == set()
    assert "No accounts match the chips above." in response.text


# --- Pager ------------------------------------------------------------------


def _many(db: Session, count: int, **flags: bool) -> None:
    db.add_all(User(email=f"user{n:04d}@example.edu", **flags) for n in range(count))
    db.commit()


def test_two_hundred_rows_a_page_with_the_pager_above_and_below(
    db: Session, client: TestClient, admin: None
) -> None:
    _many(db, 250, is_operator=True)
    body = client.get(ACCOUNTS).text
    assert len(_emails(body)) == 200
    assert body.count('<div class="table-pager-cluster') == 2
    assert "<summary>1–200</summary>" in body
    assert (
        f'href="{ACCOUNTS}?show=operators&amp;show=admins&amp;offset=200'
        '#accounts-table-card"'
    ) in body
    rest = client.get(f"{ACCOUNTS}?offset=200").text
    assert len(_emails(rest)) == 51  # 250 and Alice
    assert "<summary>201–251</summary>" in rest
    # A stale offset clamps to the last page rather than failing.
    assert "<summary>201–251</summary>" in client.get(f"{ACCOUNTS}?offset=9000").text


def test_the_pager_stays_under_a_search_and_carries_it(
    db: Session, client: TestClient, admin: None
) -> None:
    _many(db, 250, is_operator=True)
    body = client.get(f"{ACCOUNTS}?q=user").text
    assert "<summary>1–200</summary>" in body
    assert f"{ACCOUNTS}?show=operators&amp;show=admins&amp;q=user&amp;offset=200" in body


def test_a_filtered_single_page_says_how_many(
    workspace: dict[str, User], client: TestClient
) -> None:
    assert "Showing 1 account." in client.get(f"{ACCOUNTS}?q=bob").text
    assert '<p class="muted table-showing-hint">' not in client.get(ACCOUNTS).text


# --- Actions keep the view --------------------------------------------------


def test_an_action_redirect_keeps_the_view(
    workspace: dict[str, User], client: TestClient
) -> None:
    erin = workspace["erin"]
    body = client.get(f"{ACCOUNTS}?show=unused&q=erin").text
    view = body.split('name="view" value="', 1)[1].split('"', 1)[0]
    assert view == "show=unused&amp;q=erin"
    response = client.post(
        f"{ACCOUNTS}/{erin.id}/admit",
        data={"view": "show=unused&q=erin"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    query = parse_qs(urlsplit(response.headers["location"]).query)
    assert query == {"show": ["unused"], "q": ["erin"], "selected": [str(erin.id)]}


def test_the_selected_rows_chip_turns_on_as_if_clicked(
    workspace: dict[str, User], client: TestClient
) -> None:
    """A ``?selected=`` row whose chip is off turns that chip on, so the
    row stays in view, and the chip stays on in the links the page
    renders: the action forms' ``view`` carries it."""
    erin = workspace["erin"]  # Unused
    body = client.get(f"{ACCOUNTS}?show=no_role&selected={erin.id}").text
    assert "checked" in _chip(body, "unused")
    assert "Erin@Example.edu" in _emails(body)
    view = body.split('name="view" value="', 1)[1].split('"', 1)[0]
    assert parse_qs(view.replace("&amp;", "&"))["show"] == ["no_role", "unused"]


def test_the_selected_row_lands_on_its_page(
    db: Session, client: TestClient, admin: None
) -> None:
    client.get(ACCOUNTS)
    oldest = _seed(db, "oldest@example.edu", is_operator=True)
    _many(db, 250, is_operator=True)
    body = client.get(f"{ACCOUNTS}?selected={oldest.id}").text
    assert "<summary>201–252</summary>" in body
    assert "oldest@example.edu" in _emails(body)


def test_a_tampered_view_is_reencoded_not_echoed(
    workspace: dict[str, User], client: TestClient
) -> None:
    response = client.post(
        f"{ACCOUNTS}/{workspace['erin'].id}/admit",
        data={"view": "show=unused&evil=1&role=bogus&offset=abc"},
        follow_redirects=False,
    )
    query = parse_qs(urlsplit(response.headers["location"]).query)
    assert query == {"show": ["unused"], "selected": [str(workspace["erin"].id)]}


@pytest.mark.parametrize("offset", ["\u00b2", "9" * 5000])
def test_an_offset_int_refuses_is_dropped_not_a_500(
    workspace: dict[str, User], client: TestClient, offset: str
) -> None:
    """``"²".isdigit()`` is true and ``int`` refuses it, as it does past
    4,300 digits: the action has committed by the redirect, so a 500
    there would report a change that happened as a failure."""
    response = client.post(
        f"{ACCOUNTS}/{workspace['erin'].id}/admit",
        data={"view": f"show=unused&offset={offset}"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    query = parse_qs(urlsplit(response.headers["location"]).query)
    assert "offset" not in query


# --- Row expander (Item 2) --------------------------------------------------


def test_each_row_carries_its_chip_for_the_expander(
    workspace: dict[str, User], client: TestClient
) -> None:
    """The expander picks its controls by the selected rows' chips, so
    each row says which chip it sits under, from the same SQL rule."""
    body = client.get(
        f"{ACCOUNTS}?show=operators&show=admins&show=no_role&show=unused"
    ).text
    for name, category in (
        ("bob", "operators"), ("carol", "admins"),
        ("dave", "no_role"), ("erin", "unused"),
    ):
        user = workspace[name]
        row = body.split(f'data-user-id="{user.id}"', 1)[1].split(">", 1)[0]
        assert f'data-category="{category}"' in row, name
    assert 'id="users-select-all"' in body
    assert 'data-can-manage-admins="true"' in body
