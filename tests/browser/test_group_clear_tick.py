"""The card's Save re-offers a refused group clear with a tick
(``guide/warnings_updates.md`` Item 1, author's ruling 2026-10-17).

The server's refusal is stubbed: what is under test is the card, which
shows the count and a ``Yes, clear them`` tick, keeps its edits, and
sends the count it showed as ``acknowledge_response_loss`` with the
next Save. The refusal itself is
``tests/integration/test_group_clear_asks_first.py``'s.
"""

from __future__ import annotations

import json
from collections.abc import Callable

from playwright.sync_api import Page, Route, expect

from . import _builder

_LINE = "This change clears 3 saved responses on groups whose members it changes."


def test_a_refused_save_offers_the_tick_and_the_next_save_sends_it(
    page: Page, new_session: Callable[[], str]
) -> None:
    session_id = new_session()
    card = _builder.open_unlocked(page, session_id)
    bodies: list[str] = []

    def refuse_once(route: Route) -> None:
        bodies.append(route.request.post_data or "")
        if len(bodies) == 1:
            route.fulfill(
                status=422,
                content_type="application/json",
                body=json.dumps(
                    {"ok": False, "errors": [_LINE], "confirm_group_clear": 3}
                ),
            )
        else:
            route.continue_()

    page.route("**/instruments/*/save", refuse_once)
    name = _builder.rows(card).locator("[data-new-model-rf-name]").first
    name.fill("Score")
    _builder.save_button(card).click()

    banner = card.locator("[data-save-error-banner]")
    expect(banner).to_be_visible()
    expect(banner).to_contain_text(_LINE)
    tick = banner.get_by_label("Yes, clear them")
    expect(tick).not_to_be_checked()
    assert 'name="acknowledge_response_loss"' not in bodies[0]
    expect(name).to_have_value("Score")

    tick.check()
    _builder.save(page, card)

    assert len(bodies) == 2
    # The tick carries the count it was shown, not ``true``.
    assert 'name="acknowledge_response_loss"\r\n\r\n3\r\n' in bodies[1]
    expect(banner).to_be_hidden()
