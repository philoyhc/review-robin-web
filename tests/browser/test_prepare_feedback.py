"""Prepare's button while the request runs (post_assessment_1oct E4).

Prepare takes about 14 s at a 200 x 200 full matrix, so its button says
"Preparing…" and refuses a second click until the page changes. A submit
listener the test adds after the card's own stops the form leaving the
page, so the button can be read mid-"request"; it records whether the
card's listener, which runs first, had already refused the submit.
"""

from __future__ import annotations

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

    button.click()
    expect(button).to_have_text("Preparing…")
    expect(button).to_be_disabled()
    expect(button).to_have_attribute("aria-busy", "true")
    # A second submit, by keyboard or script, is refused rather than queued.
    page.evaluate("document.getElementById('next-action-prepare-form').requestSubmit()")
    assert page.evaluate("window.refusedByCard") == [False, True]
