"""Sys Admin → Accounts: several rows can be ticked and the selection
drives a row expander (guide/admin_pages_refine.md Item 2). Its controls
follow the selected rows' chips and act on every selected row, all or
nothing; the single-row toolbar is retired.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

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


def test_two_operators_open_the_expander(
    page: Page, api: httpx.Client
) -> None:
    first, second, _ = _setup(page, api)
    _tick(page, first)
    _tick(page, second)

    expander = page.locator("#users-row-expander")
    expect(expander).to_have_count(1)
    expect(expander).to_contain_text("2 of 3 selected")
    # Grouped as the toolbar is, so each button says which role it changes.
    # Neither owns a session, so Revoke shows and Remove from all
    # sessions doesn't.
    assert _expander_actions(page) == ["Revoke", "Promote", "Delete"]
    assert expander.locator(".row-expander-group > .muted").all_inner_texts() == [
        "Operator:", "Admin:", "|",
    ]
    for name in ("Revoke", "Promote"):
        expect(expander.locator(f'[data-expander-action="{name}"]')).to_be_enabled()
    # Delete waits for its confirm.
    delete = expander.locator('[data-expander-action="Delete"]')
    expect(delete).to_be_disabled()
    expander.locator(".exp-confirm-label input").check()
    expect(delete).to_be_enabled()
    # Anchored after the most recently ticked row.
    anchor = page.locator(f'tr[data-user-id]:has(code:text-is("{second}"))')
    expect(anchor.locator("xpath=following-sibling::tr[1]")).to_have_id(
        "users-row-expander"
    )
    # The toolbar is gone.
    expect(page.locator("#user-actions")).to_have_count(0)


def test_a_mixed_selection_shows_only_what_applies_to_every_row(
    page: Page, api: httpx.Client
) -> None:
    first, _, unused = _setup(page, api)
    _tick(page, first)
    _tick(page, unused)
    assert _expander_actions(page) == ["Delete"]
    # No Operator or Admin control fits, so neither label renders.
    assert page.locator(
        "#users-row-expander .row-expander-group > .muted"
    ).all_inner_texts() == ["|"]


def test_one_unused_row_offers_admit(page: Page, api: httpx.Client) -> None:
    _, _, unused = _setup(page, api)
    _tick(page, unused)
    expect(page.locator("#users-row-expander")).to_contain_text("1 of 3 selected")
    assert _expander_actions(page) == ["Admit", "Delete"]


def test_select_all_is_tri_state_and_clearing_removes_the_expander(
    page: Page, api: httpx.Client
) -> None:
    first, _, _ = _setup(page, api)
    select_all = page.locator("#users-select-all")
    _tick(page, first)
    select_all.check()
    expect(page.locator(".user-row-select:checked")).to_have_count(3)
    expect(page.locator("#users-row-expander")).to_contain_text("3 of 3 selected")

    page.locator(
        f'tr[data-user-id]:has(code:text-is("{first}")) .user-row-select'
    ).uncheck()
    assert select_all.evaluate("box => box.indeterminate") is True
    expect(page.locator("#users-row-expander")).to_contain_text("2 of 3 selected")

    select_all.check()
    select_all.uncheck()
    expect(page.locator(".user-row-select:checked")).to_have_count(0)
    expect(page.locator("#users-row-expander")).to_have_count(0)


def test_the_count_the_confirm_and_the_buttons_share_one_line(
    page: Page, api: httpx.Client
) -> None:
    """The author's note on the scaffold: the confirm hung below the
    count, from `.confirm-label`'s top margin."""
    _, _, unused = _setup(page, api)
    _tick(page, unused)
    expander = page.locator("#users-row-expander")

    def middle(locator) -> float:
        box = locator.bounding_box()
        assert box is not None
        return box["y"] + box["height"] / 2

    count = middle(expander.locator(".row-expander-count"))
    confirm = middle(expander.locator(".exp-confirm-label"))
    button = middle(expander.locator('[data-expander-action="Delete"]'))
    assert abs(count - confirm) <= 2, (count, confirm)
    assert abs(count - button) <= 2, (count, button)


def test_a_narrow_row_wraps_between_groups_not_inside_one(
    page: Page, api: httpx.Client
) -> None:
    """Codex on #3036: each label and its buttons are one group, so a
    label never ends a line with its buttons on the next."""
    first, second, _ = _setup(page, api)
    page.set_viewport_size({"width": 420, "height": 900})
    _tick(page, first)
    _tick(page, second)
    groups = page.locator("#users-row-expander .row-expander-group")
    expect(groups).to_have_count(3)
    for group in groups.all():
        tops = group.evaluate(
            "g => Array.from(g.children).map(c => Math.round(c.getBoundingClientRect().top + c.getBoundingClientRect().height / 2))"
        )
        assert max(tops) - min(tops) <= 2, tops


def test_a_wrapping_confirm_keeps_its_tick_by_the_first_line(page: Page) -> None:
    """Codex on #3036: the margin reset must not center the tick on a
    long confirm that wraps (the roster pages' longer sentences)."""
    page.goto(ACCOUNTS)
    top = page.evaluate(
        """() => {
          const label = document.createElement("label");
          label.className = "confirm-label exp-confirm-label";
          label.style.width = "140px";
          label.innerHTML = '<input type="checkbox"> Yes, delete these and their associated assignments and reviewer responses';
          document.body.appendChild(label);
          const box = label.querySelector("input").getBoundingClientRect();
          const whole = label.getBoundingClientRect();
          return [box.top - whole.top, whole.height];
        }"""
    )
    offset, height = top
    assert height > 40, height  # it wrapped
    assert offset < 10, offset  # the tick stays by the first line


def _operator_cell(page: Page, email: str):
    return page.locator(f'tr[data-user-id]:has(code:text-is("{email}")) td').nth(4)


def test_revoking_two_operators_is_one_click(page: Page, api: httpx.Client) -> None:
    first, second, _ = _setup(page, api)
    _tick(page, first)
    _tick(page, second)
    with page.expect_navigation():
        page.locator('#users-row-expander [data-expander-action="Revoke"]').click()
    # Both lost the flag, so both now sit under Unused, which is on.
    expect(_operator_cell(page, first)).to_have_text("no")
    expect(_operator_cell(page, second)).to_have_text("no")
    expect(page.locator('[role="alert"]')).to_have_count(0)
    # The view came back: the chips and the search.
    assert "show=unused" in page.url and "q=exp-" in page.url


def test_a_mixed_delete_is_refused_whole_and_says_why(
    page: Page, api: httpx.Client, new_session: Callable[[], int]
) -> None:
    """The DoD's refused mixed Delete: an unused account and an operator
    who co-owns a session. The owner refuses the batch, so the unused
    account stays too, and the banner names the owner."""
    first, _, unused = _setup(page, api)
    session_id = new_session()
    response = api.post(
        f"/operator/sessions/{session_id}/owners/add",
        data={"target_email": first},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    page.reload()

    _tick(page, first)
    _tick(page, unused)
    page.locator("#users-row-expander .exp-confirm-label input").check()
    with page.expect_navigation():
        page.locator('#users-row-expander [data-expander-action="Delete"]').click()
    expect(page.locator('[role="alert"]')).to_contain_text(
        f"Nothing changed: {first} owns sessions"
    )
    expect(page.locator(f'tr[data-user-id]:has(code:text-is("{unused}"))')).to_have_count(1)
    expect(page.locator(f'tr[data-user-id]:has(code:text-is("{first}"))')).to_have_count(1)


def test_an_owner_offers_remove_from_all_sessions_not_revoke(
    page: Page, api: httpx.Client, new_session: Callable[[], int]
) -> None:
    """The toolbar's gates, kept: Revoke needs no sessions (the server's
    still_owner), Remove from all sessions needs some."""
    first, second, _ = _setup(page, api)
    session_id = new_session()
    response = api.post(
        f"/operator/sessions/{session_id}/owners/add",
        data={"target_email": first},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    page.reload()
    _tick(page, first)
    assert _expander_actions(page) == ["Remove from all sessions", "Promote", "Delete"]
    # With an operator who owns nothing, neither session control fits both.
    _tick(page, second)
    assert _expander_actions(page) == ["Promote", "Delete"]

