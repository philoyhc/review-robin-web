"""Sys Admin → Accounts: several rows can be ticked and the selection
drives a row expander (guide/admin_pages_refine.md Item 2, rung 1, the
scaffold). Its controls follow the selected rows' chips and are inert;
the toolbar above stays live for one selected row.
"""

from __future__ import annotations

import uuid

import httpx
from playwright.sync_api import Page, expect

ACCOUNTS = "/operator/sys-admin/users"


def _invite(page: Page, email: str) -> None:
    page.goto(ACCOUNTS)
    page.fill("#invite-email", email)
    with page.expect_navigation():
        page.click("[data-invite-submit]")


def _sign_in(api: httpx.Client, email: str) -> None:
    """A first sign-in, which makes an Unused account."""
    response = api.get(
        "/me",
        headers={
            "X-MS-CLIENT-PRINCIPAL-NAME": email,
            "X-MS-CLIENT-PRINCIPAL-ID": f"browser-{email}",
        },
    )
    assert response.status_code == 200, response.text


def _tick(page: Page, email: str) -> None:
    page.locator(f'tr[data-user-id]:has(code:text-is("{email}")) .user-row-select').check()


def _expander_actions(page: Page) -> list[str]:
    return page.locator("#users-row-expander [data-expander-action]").all_inner_texts()


def _setup(page: Page, api: httpx.Client) -> tuple[str, str, str]:
    token = uuid.uuid4().hex[:8]
    first = f"exp-{token}-a@example.edu"
    second = f"exp-{token}-b@example.edu"
    unused = f"exp-{token}-c@example.edu"
    _invite(page, first)
    _invite(page, second)
    _sign_in(api, unused)
    page.goto(f"{ACCOUNTS}?show=operators&show=unused&q=exp-{token}")
    expect(page.locator("tr[data-user-id]")).to_have_count(3)
    return first, second, unused


def test_two_operators_open_an_inert_expander_and_disable_the_toolbar(
    page: Page, api: httpx.Client
) -> None:
    first, second, _ = _setup(page, api)
    _tick(page, first)
    _tick(page, second)

    expander = page.locator("#users-row-expander")
    expect(expander).to_have_count(1)
    expect(expander).to_contain_text("2 of 3 selected")
    # Grouped as the toolbar is, so each button says which role it changes.
    assert _expander_actions(page) == [
        "Revoke", "Remove from all sessions", "Promote", "Delete",
    ]
    assert expander.locator(".row-expander-actions > .muted").all_inner_texts() == [
        "Operator:", "Admin:", "|",
    ]
    for button in expander.locator("[data-expander-action]").all():
        expect(button).to_be_disabled()
    expect(expander.locator(".exp-confirm-label input")).to_be_disabled()
    # Anchored after the most recently ticked row.
    anchor = page.locator(f'tr[data-user-id]:has(code:text-is("{second}"))')
    expect(anchor.locator("xpath=following-sibling::tr[1]")).to_have_id(
        "users-row-expander"
    )
    # The toolbar acts on one row only.
    expect(page.locator('[data-action-btn="operator-toggle"]')).to_be_disabled()
    expect(page.locator('[data-action-btn="delete"]')).to_be_disabled()


def test_a_mixed_selection_shows_only_what_applies_to_every_row(
    page: Page, api: httpx.Client
) -> None:
    first, _, unused = _setup(page, api)
    _tick(page, first)
    _tick(page, unused)
    assert _expander_actions(page) == ["Remove from all sessions", "Delete"]
    # No Admin control fits, so no "Admin:" label.
    assert page.locator(
        "#users-row-expander .row-expander-actions > .muted"
    ).all_inner_texts() == ["Operator:", "|"]


def test_one_row_keeps_the_toolbar_live(page: Page, api: httpx.Client) -> None:
    _, _, unused = _setup(page, api)
    _tick(page, unused)
    expect(page.locator("#users-row-expander")).to_contain_text("1 of 3 selected")
    assert _expander_actions(page) == ["Admit", "Remove from all sessions", "Delete"]
    toggle = page.locator('[data-action-btn="operator-toggle"]')
    expect(toggle).to_be_enabled()
    expect(toggle).to_have_text("Admit")


def test_select_all_is_tri_state_and_clearing_removes_the_expander(
    page: Page, api: httpx.Client
) -> None:
    first, _, _ = _setup(page, api)
    select_all = page.locator("#users-select-all")
    # From one row ticked, the toolbar is live; select-all must leave it
    # disabled, which needs the toolbar to read the rows after the
    # select-all has ticked them.
    _tick(page, first)
    expect(page.locator('[data-action-btn="operator-toggle"]')).to_be_enabled()
    select_all.check()
    expect(page.locator(".user-row-select:checked")).to_have_count(3)
    expect(page.locator("#users-row-expander")).to_contain_text("3 of 3 selected")
    expect(page.locator('[data-action-btn="operator-toggle"]')).to_be_disabled()

    page.locator(
        f'tr[data-user-id]:has(code:text-is("{first}")) .user-row-select'
    ).uncheck()
    assert select_all.evaluate("box => box.indeterminate") is True
    expect(page.locator("#users-row-expander")).to_contain_text("2 of 3 selected")

    select_all.check()
    select_all.uncheck()
    expect(page.locator(".user-row-select:checked")).to_have_count(0)
    expect(page.locator("#users-row-expander")).to_have_count(0)
