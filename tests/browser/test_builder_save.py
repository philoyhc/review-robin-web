"""The builder's Save, end to end: the round trip every later browser test
builds on (``guide/browser_test.md`` rung 2)."""

from __future__ import annotations

from collections.abc import Callable

import httpx
from playwright.sync_api import Page, expect


def test_a_renamed_field_survives_save_and_reload(
    page: Page, api: httpx.Client, new_session: Callable[[], int]
) -> None:
    session_id = new_session()
    page.goto(f"/operator/sessions/{session_id}/instruments")

    card = page.locator("[data-instrument-card]").first
    expect(card).to_have_attribute("data-instrument-locked", "true")
    # A card opens collapsed, as it does for a person; its summary expands it.
    card.locator("summary.instrument-card-summary").click()
    card.locator("[data-instrument-unlock-toggle]:visible").first.click()
    expect(card).to_have_attribute("data-instrument-locked", "false")

    name = card.locator("[data-new-model-rf-row] [data-new-model-rf-name]").first
    expect(name).to_have_value("Rating")
    save = card.locator("[data-new-model-save]:visible").first
    expect(save).to_be_disabled()

    name.fill("Score")
    expect(save).to_be_enabled()
    with page.expect_response(
        lambda r: r.request.method == "POST" and r.url.endswith("/save")
    ) as saved:
        save.click()
    assert saved.value.ok

    page.reload()
    expect(name).to_have_value("Score")
    assert 'value="Score"' in api.get(f"/operator/sessions/{session_id}/instruments").text
