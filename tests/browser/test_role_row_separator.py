"""The participant row's `|` (segment 19X Item 12): it separates the
role pills from the instrument status pills while both share a line, and
goes when the status pills wrap below; widening the window brings it
back.
"""

from __future__ import annotations

from playwright.sync_api import Page

from ._builder import REVIEWER_EMAIL, activate, seed_rosters
from .conftest import app_url


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
    session_id = new_session()
    seed_rosters(api, session_id)
    activate(api, live_server.database_url, session_id)
    reviewer = page_as(REVIEWER_EMAIL)
    reviewer.set_viewport_size({"width": 1400, "height": 900})
    reviewer.goto(app_url(f"/me/sessions/{session_id}"))
    assert _row(reviewer) == {"sepShown": True, "ownLine": False}

    reviewer.set_viewport_size({"width": 480, "height": 900})
    reviewer.wait_for_function(
        "() => document.querySelector('.rs-role-nav-statuses-wrapped') !== null"
    )
    assert _row(reviewer) == {"sepShown": False, "ownLine": True}

    reviewer.set_viewport_size({"width": 1400, "height": 900})
    reviewer.wait_for_function(
        "() => document.querySelector('.rs-role-nav-statuses-wrapped') === null"
    )
    assert _row(reviewer) == {"sepShown": True, "ownLine": False}
