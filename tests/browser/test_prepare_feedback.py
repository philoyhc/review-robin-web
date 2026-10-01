"""Prepare's button while the request runs (post_assessment_1oct E4).

Prepare takes about 14 s at a 200 x 200 full matrix, so the clicked
button says "Preparing session…", in two lines like its idle label, and
a second click is refused until the page
changes. A submit listener the test adds after the card's own stops the
form leaving the page, so the button can be read mid-"request"; it
records whether the card's listener, which runs first, had already
refused the submit.
"""

from __future__ import annotations

import re
from collections.abc import Callable

import httpx
from playwright.sync_api import Page, expect

from ._builder import pin_full_matrix, seed_rosters
from .conftest import LiveServer


def test_prepare_says_so_and_takes_one_click(
    page: Page,
    api: httpx.Client,
    live_server: LiveServer,
    new_session: Callable[[], int],
) -> None:
    session_id = new_session()
    seed_rosters(api, session_id)
    pin_full_matrix(live_server.database_url, session_id)
    page.goto(f"/operator/sessions/{session_id}")
    button = page.locator("button[form='next-action-prepare-form']")
    expect(button).to_have_text("Prepare session", use_inner_text=True)
    # A draft session's Prepare is the primary button; validated, secondary.
    expect(button).not_to_have_class(re.compile(r"\bsecondary\b"))
    page.evaluate(
        """() => {
            window.refusedByCard = [];
            document.getElementById('next-action-prepare-form')
              .addEventListener('submit', (event) => {
                window.refusedByCard.push(event.defaultPrevented);
                event.preventDefault();
              });
        }"""
    )

    idle_height = button.bounding_box()["height"]
    button.click()
    # Two lines, like the idle label, so the button keeps its height.
    expect(button).to_have_text("Preparing session…", use_inner_text=True)
    assert button.evaluate("b => b.querySelectorAll('br').length") == 1
    assert button.bounding_box()["height"] == idle_height
    expect(button).to_have_attribute("aria-busy", "true")
    # Busy is aria-busy, never disabled (base.html's busy indicator, rule 2).
    expect(button).to_be_enabled()
    button.click()
    assert page.evaluate("window.refusedByCard") == [False, True]

    # Without the test's listener the guard lets the first submit through,
    # and Prepare runs: the session is validated, so Prepare is secondary.
    page.reload()
    button = page.locator("button[form='next-action-prepare-form']")
    with page.expect_navigation():
        button.click()
    expect(button).to_have_class(re.compile(r"\bsecondary\b"))
    expect(button).to_have_text("Prepare session", use_inner_text=True)
