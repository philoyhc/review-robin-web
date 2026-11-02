"""The shared top bar's two menus, driven by keyboard, and its narrow
layout (segment 20D, `docs/header_chrome.md` §2, §5, §7)."""

from __future__ import annotations

from collections.abc import Callable

from playwright.sync_api import Page, expect

from .conftest import app_url


def _switcher(page: Page):
    return page.locator("details.tb-switch")


def _account(page: Page):
    return page.locator("details.tb-acct")


def test_both_menus_open_by_keyboard_and_close_on_escape(page: Page) -> None:
    page.set_viewport_size({"width": 1280, "height": 900})
    page.goto(app_url("/operator/sessions"))
    switcher, account = _switcher(page), _account(page)

    switcher.locator("summary").focus()
    page.keyboard.press("Enter")
    expect(switcher).to_have_attribute("open", "")
    expect(switcher.get_by_role("link", name="All applications")).to_be_visible()
    page.keyboard.press("Escape")
    expect(switcher).not_to_have_attribute("open", "")
    expect(switcher.locator("summary")).to_be_focused()

    account.locator("summary").focus()
    page.keyboard.press("Space")
    expect(account).to_have_attribute("open", "")
    expect(account.get_by_role("link", name="Sign out")).to_be_visible()
    page.keyboard.press("Escape")
    expect(account).not_to_have_attribute("open", "")
    expect(account.locator("summary")).to_be_focused()


def test_one_menu_open_at_a_time_and_an_outside_click_closes_it(
    page: Page,
) -> None:
    page.set_viewport_size({"width": 1280, "height": 900})
    page.goto(app_url("/operator/sessions"))
    switcher, account = _switcher(page), _account(page)

    switcher.locator("summary").click()
    expect(switcher).to_have_attribute("open", "")
    account.locator("summary").click()
    expect(account).to_have_attribute("open", "")
    expect(switcher).not_to_have_attribute("open", "")

    page.locator("h1").first.click()
    expect(account).not_to_have_attribute("open", "")


def test_under_640px_the_toggle_moves_into_the_account_menu(
    page: Page, new_session: Callable[[], str]
) -> None:
    session_id = new_session()
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(app_url(f"/operator/sessions/{session_id}/reviewers"))
    account = _account(page)

    expect(page.locator(".tb-right > .theme-toggle")).to_be_hidden()
    expect(page.locator(".tb-right > .tb-name")).to_be_hidden()
    account.locator("summary").click()
    narrow = account.locator(".tb-narrow .theme-toggle")
    expect(narrow).to_be_visible()
    narrow.get_by_role("button", name="Dark").click()
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")

    # The breadcrumb's middle collapses to "…".
    crumbs = page.locator(".chrome .breadcrumb")
    expect(crumbs.locator(".bc-mid").first).to_be_hidden()
    expect(crumbs.locator(".bc-ellipsis").first).to_be_visible()
    expect(crumbs.get_by_role("link", name="Sessions")).to_be_visible()


def test_at_desktop_width_the_bar_keeps_the_toggle_and_full_breadcrumb(
    page: Page, new_session: Callable[[], str]
) -> None:
    session_id = new_session()
    page.set_viewport_size({"width": 1280, "height": 900})
    page.goto(app_url(f"/operator/sessions/{session_id}/reviewers"))
    expect(page.locator(".tb-right > .theme-toggle")).to_be_visible()
    expect(page.locator(".tb-right > .tb-name")).to_be_visible()
    crumbs = page.locator(".chrome .breadcrumb")
    expect(crumbs.locator(".bc-mid").first).to_be_visible()
    expect(crumbs.locator(".bc-ellipsis").first).to_be_hidden()
