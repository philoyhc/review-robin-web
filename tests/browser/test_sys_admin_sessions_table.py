"""Sys Admin → Sessions Diagnostics in a browser: the filter hides rows
by name, code or owner and Clear brings them back; a header sorts; and
each row's three actions stay on one line (author, 2026-10-14)."""

from __future__ import annotations

import uuid
from collections.abc import Callable

import httpx
from playwright.sync_api import Page, expect

from .conftest import app_url

PAGE = "/operator/sys-admin/sessions"


def _invite(page: Page, email: str) -> None:
    page.goto(app_url("/operator/sys-admin/users"))
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

    page.goto(app_url(PAGE))
    total = _visible_rows(page).count()
    assert total >= 2
    box = page.locator("[data-diagnostics-filter]")
    box.fill(owner.upper())  # case doesn't matter
    expect(_visible_rows(page)).to_have_count(1)
    expect(_visible_rows(page).first.locator("a").first).to_have_attribute(
        "href", app_url(f"/operator/sessions/{owned}")
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
    page.goto(app_url(PAGE))
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


def test_a_sort_survives_a_reload(page: Page, new_session: Callable[[], str]) -> None:
    """The sort cookie is scoped to a path this page is under, so the
    browser sends it back. It was written at ``/operator/sessions/admin``
    when the table id ``rrw-sort-sys-admin-sessions`` was read as surface
    ``sys``, session ``admin``, and the order was lost on reload."""
    new_session()
    new_session()
    page.goto(app_url(PAGE))
    page.context.clear_cookies(name="rrw-sort-sys-admin-sessions")
    page.reload()
    codes = page.locator("#diagnostics-sessions tbody tr td:nth-child(2) code")
    button = '#diagnostics-sessions th[data-sort-key="code"] .rrw-sort-btn'
    page.click(button)
    page.click(button)
    descending = codes.all_inner_texts()
    [cookie] = [c for c in page.context.cookies() if c["name"] == "rrw-sort-sys-admin-sessions"]
    assert cookie["path"] == app_url("/")
    page.reload()
    assert codes.all_inner_texts() == descending


def test_each_table_id_maps_to_its_cookie_path(page: Page) -> None:
    page.goto(app_url(PAGE))
    cases = {
        "rrw-sort-lobby": "/",
        "rrw-sort-archived": "/",
        "rrw-sort-sys-admin-sessions": "/",
        "rrw-sort-reviewers-k7m2p9q4rs": "/operator/sessions/k7m2p9q4rs",
        "rrw-sort-assignments-k7m2p9q4rs": "/operator/sessions/k7m2p9q4rs",
        "rrw-sort-rs-k7m2p9q4rs-3": "/me/sessions/k7m2p9q4rs",
    }
    found = page.evaluate("ids => ids.map(id => _rrwCookiePath(id))", list(cases))
    assert dict(zip(cases, found)) == {name: app_url(path) for name, path in cases.items()}


def test_a_sort_cookie_left_at_the_root_path_is_expired(page: Page) -> None:
    """Findings C2: a copy written at ``Path=/`` before the move under the
    mount rode beside the mount's copy, and the server read it last. The
    page expires it on load, and leaves the mount's copy alone."""
    assert app_url("/") != "/", "premise: the suite serves RRW under a mount"
    name = "rrw-sort-sys-admin-sessions"
    page.goto(app_url(PAGE))
    host = page.evaluate("location.hostname")
    page.context.clear_cookies(name=name)
    stale = '%5B%7B%22key%22%3A%22code%22%2C%22dir%22%3A%22asc%22%7D%5D'
    page.context.add_cookies(
        [
            {"name": name, "value": stale, "domain": host, "path": "/"},
            {"name": name, "value": "%5B%5D", "domain": host, "path": app_url("/")},
        ]
    )
    page.reload()
    paths = sorted(c["path"] for c in page.context.cookies() if c["name"] == name)
    assert paths == [app_url("/")]


def test_the_load_that_expires_a_root_copy_sorts_by_the_mount_copy(
    page: Page, new_session: Callable[[], str]
) -> None:
    """Codex on #3235: the server sorted that load by the root copy, so the
    script that expires it puts the rows in the mount copy's order."""
    from urllib.parse import quote

    new_session()
    new_session()
    name = "rrw-sort-sys-admin-sessions"
    page.goto(app_url(PAGE))
    host = page.evaluate("location.hostname")

    def spec(direction: str) -> str:
        return quote(f'[{{"key":"code","dir":"{direction}"}}]', safe="")

    page.context.clear_cookies(name=name)
    page.context.add_cookies(
        [
            {"name": name, "value": spec("asc"), "domain": host, "path": "/"},
            {"name": name, "value": spec("desc"), "domain": host, "path": app_url("/")},
        ]
    )
    rows = page.locator("#diagnostics-sessions tbody tr td:nth-child(2) code")
    page.reload()
    first_load = rows.all_inner_texts()
    assert [c["path"] for c in page.context.cookies() if c["name"] == name] == [app_url("/")]
    # The next load sends only the mount copy, so the server sorts by it.
    page.reload()
    assert first_load == rows.all_inner_texts()
