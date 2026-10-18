"""Sys Admin → Sessions Diagnostics in a browser: the filter hides rows
by name, code or owner and Clear brings them back; a header sorts; and
each row's three actions stay on one line (author, 2026-10-14)."""

from __future__ import annotations

import uuid
from collections.abc import Callable

import httpx
from playwright.sync_api import Page, expect

PAGE = "/operator/sys-admin/sessions"


def _invite(page: Page, email: str) -> None:
    page.goto("/operator/sys-admin/users")
    page.fill("#invite-email", email)
    with page.expect_navigation():
        page.click("[data-invite-submit]")


def _visible_rows(page: Page):
    return page.locator("#diagnostics-sessions tbody tr:not([hidden])")


def test_the_filter_matches_an_owner_and_clear_empties_it(
    page: Page, api: httpx.Client, new_session: Callable[[], str]
) -> None:
    owner = f"diag-{uuid.uuid4().hex[:8]}@example.edu"
    _invite(page, owner)
    owned, other = new_session(), new_session()
    response = api.post(
        f"/operator/sessions/{owned}/owners/add",
        data={"target_email": owner},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text

    page.goto(PAGE)
    total = _visible_rows(page).count()
    assert total >= 2
    box = page.locator("[data-diagnostics-filter]")
    box.fill(owner.upper())  # case doesn't matter
    expect(_visible_rows(page)).to_have_count(1)
    expect(_visible_rows(page).first.locator("a").first).to_have_attribute(
        "href", f"/operator/sessions/{owned}"
    )
    box.fill("no-such-session-anywhere")
    expect(_visible_rows(page)).to_have_count(0)
    expect(page.locator("[data-diagnostics-no-match]")).to_be_visible()

    page.click("[data-diagnostics-filter-clear]")
    expect(box).to_have_value("")
    expect(_visible_rows(page)).to_have_count(total)
    expect(page.locator("[data-diagnostics-no-match]")).to_be_hidden()
    assert other  # both sessions exist; only the co-owned one matched


def test_a_header_sorts_and_the_actions_stay_on_one_line(
    page: Page, new_session: Callable[[], str]
) -> None:
    new_session()
    new_session()
    page.set_viewport_size({"width": 1280, "height": 900})
    page.goto(PAGE)
    page.context.clear_cookies(name="rrw-sort-sys-admin-sessions")
    page.reload()
    codes = page.locator("#diagnostics-sessions tbody tr td:nth-child(2) code")
    page.click('#diagnostics-sessions th[data-sort-key="code"] .rrw-sort-btn')
    ascending = codes.all_inner_texts()
    # The primitive's own collation: locale-aware, numeric runs as numbers.
    assert ascending == page.evaluate(
        "xs => xs.slice().sort((a, b) => a.localeCompare(b, undefined, {numeric: true}))",
        ascending,
    )
    page.click('#diagnostics-sessions th[data-sort-key="code"] .rrw-sort-btn')
    assert codes.all_inner_texts() == list(reversed(ascending))
    # Status has no sort button.
    expect(page.locator("#diagnostics-sessions thead th", has_text="Status").locator(".rrw-sort-btn")).to_have_count(0)

    actions = page.locator("#diagnostics-sessions tbody tr").first.locator(".btn-pair .btn")
    expect(actions).to_have_count(3)
    tops = {round(box["y"]) for box in (a.bounding_box() for a in actions.all()) if box}
    assert len(tops) == 1, tops
