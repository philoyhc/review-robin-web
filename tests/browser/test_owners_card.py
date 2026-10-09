"""Session Home's Owners card, driven as an operator drives it.

Each test names the row of ``guide/post_azure_todo_checklist.md`` item 5
it repeats (``guide/archive/browser_test.md`` rung 5). The fake operator creates
each session and so is its first owner; ``COLLEAGUE_EMAIL`` is a second
workspace operator, admitted through ``OPERATOR_EMAILS`` on first sign-in.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
from playwright.sync_api import Browser, Dialog, Locator, Page, expect

from ._builder import activate, seed_rosters, sign_in
from .conftest import (
    COLLEAGUE_EMAIL,
    FAKE_OPERATOR_EMAIL,
    SECOND_COLLEAGUE_EMAIL,
    LiveServer,
)


def _sign_in_colleague(api: httpx.Client) -> None:
    sign_in(api, COLLEAGUE_EMAIL)


def _card(page: Page) -> Locator:
    return page.locator("#owners-card")


def _owner_row(page: Page, email: str) -> Locator:
    return _card(page).locator("tr").filter(has=page.locator(f"code:text-is('{email}')"))


def _open_home(page: Page, session_id: int) -> None:
    page.goto(f"/operator/sessions/{session_id}")


def _add(page: Page, email: str) -> None:
    page.locator("#owners-add-email").fill(email)
    with page.expect_navigation():
        page.locator("#owners-add-submit").click()


def _two_owner_session(
    page: Page, api: httpx.Client, new_session: Callable[[], int]
) -> int:
    _sign_in_colleague(api)
    session_id = new_session()
    _open_home(page, session_id)
    _add(page, COLLEAGUE_EMAIL)
    expect(_owner_row(page, COLLEAGUE_EMAIL)).to_have_count(1)
    return session_id


def test_the_card_is_live_with_no_lock(
    page: Page, api: httpx.Client, new_session: Callable[[], int]
) -> None:
    """``guide/operator_pages_enhancements.md`` Item 1: no Lock / Unlock;
    the picker, Add owner and another owner's Remove are live on load."""
    session_id = _two_owner_session(page, api, new_session)
    sign_in(api, SECOND_COLLEAGUE_EMAIL)
    page.goto("/operator/sessions")
    _open_home(page, session_id)

    expect(page.locator("#owners-lock-toggle")).to_have_count(0)
    expect(_card(page).locator(".locked")).to_have_count(0)
    expect(page.locator("#owners-add-email")).to_be_enabled()
    expect(page.locator("#owners-add-submit")).to_be_enabled()
    remove = _owner_row(page, COLLEAGUE_EMAIL).get_by_role("button", name="Remove")
    expect(remove).to_be_enabled()


def test_add_and_remove_each_save_at_once(
    page: Page, api: httpx.Client, new_session: Callable[[], int]
) -> None:
    """Item 5, 'Add owner saves at once' and 'Remove saves at once'."""
    session_id = _two_owner_session(page, api, new_session)
    expect(page).to_have_url(f"/operator/sessions/{session_id}#owners-card")
    expect(_card(page).locator("[role=alert]")).to_have_count(0)
    expect(page.locator(f"#owners-candidates option[value='{COLLEAGUE_EMAIL}']")).to_have_count(0)

    page.once("dialog", lambda dialog: dialog.accept())
    with page.expect_navigation():
        _owner_row(page, COLLEAGUE_EMAIL).get_by_role("button", name="Remove").click()

    expect(_owner_row(page, COLLEAGUE_EMAIL)).to_have_count(0)
    expect(page.locator(f"#owners-candidates option[value='{COLLEAGUE_EMAIL}']")).to_have_count(1)


def test_removing_another_owner_asks_and_cancel_posts_nothing(
    page: Page, api: httpx.Client, new_session: Callable[[], int]
) -> None:
    """``guide/operator_pages_enhancements.md`` Item 1: the confirm that
    replaced the Owners lock, naming whom it removes."""
    _two_owner_session(page, api, new_session)
    remove = _owner_row(page, COLLEAGUE_EMAIL).get_by_role("button", name="Remove")
    asked: list[Dialog] = []
    posted: list[str] = []
    page.on("request", lambda r: posted.append(r.url) if r.method == "POST" else None)

    def dismiss(dialog: Dialog) -> None:
        asked.append(dialog)
        dialog.dismiss()

    page.once("dialog", dismiss)
    remove.click()
    expect(_owner_row(page, COLLEAGUE_EMAIL)).to_have_count(1)
    assert len(asked) == 1 and asked[0].type == "confirm"
    assert asked[0].message == (
        f"Remove {COLLEAGUE_EMAIL} as an owner of this session?"
    )
    assert posted == []
    # Declining leaves no busy indicator behind (base.html skips a
    # submit whose onsubmit cancelled it).
    page.wait_for_timeout(400)
    expect(page.locator("[data-rrw-busy-bar]")).to_be_hidden()


def test_the_last_owner_cannot_be_removed(
    page: Page, new_session: Callable[[], int]
) -> None:
    """Item 5, 'The last owner cannot go'."""
    _open_home(page, new_session())

    remove = _owner_row(page, FAKE_OPERATOR_EMAIL).get_by_role("button", name="Remove")
    expect(remove).to_be_disabled()
    expect(remove).to_have_attribute("title", "A session always keeps at least one owner.")


def test_removing_yourself_asks_and_cancel_posts_nothing(
    page: Page, api: httpx.Client, new_session: Callable[[], int]
) -> None:
    """Item 5, 'Removing yourself asks'."""
    _two_owner_session(page, api, new_session)
    remove_self = _owner_row(page, FAKE_OPERATOR_EMAIL).get_by_role("button", name="Remove")
    asked: list[Dialog] = []
    posted: list[str] = []
    page.on("request", lambda r: posted.append(r.url) if r.method == "POST" else None)

    def dismiss(dialog: Dialog) -> None:
        asked.append(dialog)
        dialog.dismiss()

    page.once("dialog", dismiss)
    remove_self.click()
    expect(_owner_row(page, FAKE_OPERATOR_EMAIL)).to_have_count(1)
    assert len(asked) == 1 and "lose access" in asked[0].message
    assert posted == []

    page.once("dialog", lambda dialog: dialog.accept())
    with page.expect_navigation():
        remove_self.click()
    expect(page).to_have_url("/operator/sessions")


def test_owners_change_in_an_activated_session(
    page: Page, api: httpx.Client, live_server: LiveServer, new_session: Callable[[], int]
) -> None:
    """Item 5, 'Any lifecycle state'."""
    _sign_in_colleague(api)
    session_id = new_session()
    seed_rosters(api, session_id)
    activate(api, live_server.database_url, session_id)
    _open_home(page, session_id)

    _add(page, COLLEAGUE_EMAIL)
    expect(_owner_row(page, COLLEAGUE_EMAIL)).to_have_count(1)


def test_add_and_self_remove_work_without_javascript(
    browser: Browser, live_server: LiveServer, api: httpx.Client, new_session: Callable[[], int]
) -> None:
    """Item 5, 'Without JavaScript'."""
    _sign_in_colleague(api)
    session_id = new_session()
    context = browser.new_context(base_url=live_server.base_url, java_script_enabled=False)
    try:
        page = context.new_page()
        _open_home(page, session_id)
        _add(page, COLLEAGUE_EMAIL)
        expect(_owner_row(page, COLLEAGUE_EMAIL)).to_have_count(1)

        # Another owner's Remove posts straight through too: no script,
        # no confirm, as self-removal.
        with page.expect_navigation():
            _owner_row(page, COLLEAGUE_EMAIL).get_by_role("button", name="Remove").click()
        expect(_owner_row(page, COLLEAGUE_EMAIL)).to_have_count(0)
        _add(page, COLLEAGUE_EMAIL)

        # Your own Remove posts straight through: with no script there is
        # no confirm to ask, and landing on the lobby shows it removed you.
        with page.expect_navigation():
            _owner_row(page, FAKE_OPERATOR_EMAIL).get_by_role("button", name="Remove").click()
        expect(page).to_have_url("/operator/sessions")
    finally:
        context.close()
