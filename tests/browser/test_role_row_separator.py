"""The participant row's `|` (segment 19X Item 12): it separates the
role pills from the instrument status pills while both share a line, and
goes when the status pills wrap below, taking their own line; widening
the window brings it back. Without script the `|` stays.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
from playwright.sync_api import Page

from ._builder import REVIEWER_EMAIL, activate, seed_rosters
from .conftest import LiveServer, app_url

_WRAPPED = "() => document.querySelector('.rs-role-nav-statuses-wrapped') !== null"
_UNWRAPPED = "() => document.querySelector('.rs-role-nav-statuses-wrapped') === null"
# A ResizeObserver loop reaches `window.onerror`, which Playwright's
# `pageerror` does not report: collect it on the page.
_CATCH_ERRORS = (
    "window.__errors = [];"
    "window.addEventListener('error', e => window.__errors.push(String(e.message)));"
)


def _open(
    page_as: Callable[..., Page],
    api: httpx.Client,
    live_server: LiveServer,
    new_session: Callable[[], str],
    *,
    width: int,
    javascript: bool = True,
) -> Page:
    session_id = new_session()
    seed_rosters(api, session_id)
    activate(api, live_server.database_url, session_id)
    reviewer = page_as(REVIEWER_EMAIL, javascript=javascript)
    reviewer.add_init_script(_CATCH_ERRORS)
    reviewer.set_viewport_size({"width": width, "height": 900})
    reviewer.goto(app_url(f"/me/sessions/{session_id}"))
    return reviewer


def _row(page: Page) -> dict:
    return page.evaluate(
        """() => {
             const group = document.querySelector(".rs-role-nav-statuses");
             const before = group.previousElementSibling.getBoundingClientRect();
             const sep = document.querySelector(".rs-role-nav-sep");
             return {sepShown: sep.getClientRects().length > 0,
                     ownLine: group.getBoundingClientRect().top >= before.bottom - 1};
           }"""
    )


def test_the_separator_goes_when_the_pills_wrap(page_as, api, live_server, new_session) -> None:
    reviewer = _open(page_as, api, live_server, new_session, width=1400)
    assert _row(reviewer) == {"sepShown": True, "ownLine": False}

    reviewer.set_viewport_size({"width": 480, "height": 900})
    reviewer.wait_for_function(_WRAPPED)
    assert _row(reviewer) == {"sepShown": False, "ownLine": True}

    reviewer.set_viewport_size({"width": 1400, "height": 900})
    reviewer.wait_for_function(_UNWRAPPED)
    assert _row(reviewer) == {"sepShown": True, "ownLine": False}
    assert reviewer.evaluate("window.__errors") == []


def test_pills_that_fit_only_without_the_separator_keep_their_own_line(
    page_as, api, live_server, new_session
) -> None:
    """In the band of widths where the pills would fit beside the role
    pills only once the `|` is gone, they stay on their own line: the
    reason the wrapped group takes the whole line."""
    reviewer = _open(page_as, api, live_server, new_session, width=1400)
    sizes = reviewer.evaluate(
        """() => {
             const row = document.querySelector(".rs-role-nav");
             const group = row.querySelector(".rs-role-nav-statuses");
             const sep = row.querySelector(".rs-role-nav-sep");
             const cs = getComputedStyle(sep);
             const r = row.getBoundingClientRect();
             return {inset: window.innerWidth - r.width,
                     end: group.getBoundingClientRect().right - r.left,
                     sep: sep.getBoundingClientRect().width
                          + parseFloat(cs.marginLeft) + parseFloat(cs.marginRight)};
           }"""
    )
    # A row a little narrower than the pills need with the `|`, but wider
    # than they need without it.
    width = round(sizes["inset"] + sizes["end"] - sizes["sep"] / 2)
    reviewer.set_viewport_size({"width": width, "height": 900})
    reviewer.wait_for_function(_WRAPPED)
    reviewer.wait_for_timeout(100)  # a frame for the observer to settle
    assert _row(reviewer) == {"sepShown": False, "ownLine": True}
    assert reviewer.evaluate("window.__errors") == []


def test_a_narrow_window_on_load_has_no_separator(page_as, api, live_server, new_session) -> None:
    reviewer = _open(page_as, api, live_server, new_session, width=480)
    reviewer.wait_for_function(_WRAPPED)
    assert _row(reviewer) == {"sepShown": False, "ownLine": True}


def test_without_script_the_separator_stays(page_as, api, live_server, new_session) -> None:
    reviewer = _open(page_as, api, live_server, new_session, width=480, javascript=False)
    assert reviewer.locator(".rs-role-nav-sep").is_visible()
    assert reviewer.locator(".rs-role-nav-statuses-wrapped").count() == 0
