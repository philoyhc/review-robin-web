"""The gate pages under Evaluations in a real Chromium (segment AD1H):
the table sorted as Review Robin's, click and shift-click. Without a
Chromium build the test skips, saying why; ``RRW_REQUIRE_BROWSER=1``
(set by CI) turns that skip into a failure."""

from __future__ import annotations

from playwright.sync_api import Page

from applydesk.tests.test_form_browser import page as page

ORIGIN = "http://applydesk.test"
GATE3 = f"{ORIGIN}/applydesk/operator/exercises/wa9juxbc2t/evaluations/gate_3"


def _badges(page: Page) -> list[str]:
    return page.locator("th.ev-sortable .ev-sort-badge").all_inner_texts()


def test_a_column_sorts_and_shift_adds_it_to_the_cascade(page: Page) -> None:
    """As Review Robin's tables (author, 2026-11-17): a click sorts, again
    reverses, again clears; shift-click adds a column to the cascade."""
    page.goto(GATE3)
    assert _badges(page) == ["↕", "↕", "↕", "↕"]
    page.get_by_role("link", name="Sort by Evaluator").click()
    assert page.url.endswith("?sort=evaluator#ev-table-card")
    assert _badges(page) == ["↕", "1↑", "↕", "↕"]
    page.get_by_role("link", name="Sort by Candidate").click(modifiers=["Shift"])
    assert "sort=evaluator%2Ccandidate" in page.url
    assert _badges(page) == ["2↑", "1↑", "↕", "↕"]
    rows = page.locator("tbody tr")
    first = [rows.nth(i).locator("td").nth(1).inner_text() for i in range(4)]
    assert first == sorted(first, key=str.casefold)
    page.get_by_role("link", name="Sort by Evaluator").click()  # alone, up: replaces
    assert _badges(page) == ["↕", "1↑", "↕", "↕"]
    page.get_by_role("link", name="Sort by Evaluator").click()
    assert _badges(page) == ["↕", "1↓", "↕", "↕"]
    page.get_by_role("link", name="Sort by Evaluator").click()
    assert _badges(page) == ["↕", "↕", "↕", "↕"] and "sort=" not in page.url
