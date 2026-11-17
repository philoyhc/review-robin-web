"""The gate pages under Evaluations in a real Chromium (segment AD1H;
AD1G rung 6b): the table sorted as Review Robin's, and each mode's
operations worked in the browser. Without a Chromium build the test
skips, saying why; ``RRW_REQUIRE_BROWSER=1`` (set by CI) turns that skip
into a failure."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Error, Page, Route, sync_playwright

from applydesk.tests._host import host_with

ORIGIN = "http://applydesk.test"
GATE3 = f"{ORIGIN}/applydesk/operator/exercises/wa9juxbc2t/evaluations/gate_3"


@pytest.fixture
def page() -> Iterator[Page]:
    client = TestClient(host_with(("applydesk",))[0])

    def serve(route: Route) -> None:
        response = client.get(route.request.url.removeprefix(ORIGIN))
        route.fulfill(
            status=response.status_code,
            body=response.content,
            headers={"content-type": response.headers.get("content-type", "text/html")},
        )

    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch()
        except Error as exc:
            reason = f"Chromium could not launch: {exc.message.splitlines()[0]}"
            if os.environ.get("RRW_REQUIRE_BROWSER") == "1":
                pytest.fail(f"{reason}, and RRW_REQUIRE_BROWSER=1", pytrace=False)
            pytest.skip(reason)
        tab = browser.new_page(viewport={"width": 1280, "height": 900})
        errors: list[str] = []
        tab.on("pageerror", lambda exc: errors.append(str(exc)))
        tab.context.route(f"{ORIGIN}/**", serve)
        yield tab
        browser.close()
        assert errors == [], f"page errors: {errors}"


def _badges(page: Page) -> list[str]:
    return page.locator("th.ev-sortable .ev-sort-badge").all_inner_texts()


def test_a_column_sorts_and_shift_adds_it_to_the_cascade(page: Page) -> None:
    """As Review Robin's tables (author, 2026-11-17): a click sorts, again
    reverses, again clears; shift-click adds a column to the cascade."""
    page.goto(GATE3)
    assert _badges(page) == ["↕", "↕", "↕", "↕"]
    page.get_by_role("link", name="Sort by Evaluator").click()
    assert page.url.endswith("?sort=evaluator#ev-table-card")
    assert _badges(page) == ["↕", "▲", "↕", "↕"]
    page.get_by_role("link", name="Sort by Candidate").click(modifiers=["Shift"])
    assert "sort=evaluator%2Ccandidate" in page.url
    assert _badges(page) == ["▲2", "▲1", "↕", "↕"]
    rows = page.locator("tbody tr")
    first = [rows.nth(i).locator("td").nth(1).inner_text() for i in range(4)]
    assert first == sorted(first, key=str.casefold)
    page.get_by_role("link", name="Sort by Evaluator").click()  # alone, up: replaces
    assert _badges(page) == ["↕", "▲", "↕", "↕"]
    page.get_by_role("link", name="Sort by Evaluator").click()
    assert _badges(page) == ["↕", "▼", "↕", "↕"]
    page.get_by_role("link", name="Sort by Evaluator").click()
    assert _badges(page) == ["↕", "↕", "↕", "↕"] and "sort=" not in page.url
