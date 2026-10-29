"""A table's sort survives a reload, in a real Chromium (author, 2026-10-29).

The pages are served through a ``TestClient`` behind a routed origin, so
the residential base's script runs with a real ``localStorage``. Without a
Chromium build the test skips, saying why; ``RRW_REQUIRE_BROWSER=1`` (set
by CI's residential and full lanes) turns that skip into a failure.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Error, Page, Route, sync_playwright

from residentialapps.residentialops.main import create_app

ORIGIN = "http://residential.test"


@pytest.fixture
def page() -> Iterator[Page]:
    client = TestClient(create_app())

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
        tab = browser.new_page()
        errors: list[str] = []
        tab.on("pageerror", lambda exc: errors.append(str(exc)))
        tab.route(f"{ORIGIN}/**", serve)
        yield tab
        browser.close()
        assert errors == [], f"page errors: {errors}"


def _names(page: Page, table: str) -> list[str]:
    return page.eval_on_selector_all(
        f"{table} tr[data-row]", "rows => rows.map(r => r.cells[1].textContent.trim())"
    )


def _kept(page: Page) -> list[str]:
    keys = page.evaluate("Object.keys(localStorage)")
    return [k for k in keys if k.startswith("residential-sort:/rosters/staff:")]


def test_a_sort_is_kept_across_a_reload_until_cleared(page: Page) -> None:
    page.goto(f"{ORIGIN}/rosters/staff")
    page_order = _names(page, "#staff-table")
    name = page.locator("#staff-table th.sortable").first
    name.locator(".sort-btn").click()
    name.locator(".sort-btn").click()  # descending
    descending = _names(page, "#staff-table")
    assert descending != page_order

    page.reload()
    assert name.get_attribute("aria-sort") == "descending"
    assert _names(page, "#staff-table") == descending

    page.goto(f"{ORIGIN}/rosters/staff?stage=done")  # a query string keeps it
    assert name.get_attribute("aria-sort") == "descending"
    assert _names(page, "#staff-table") == descending

    name.locator(".sort-btn").click()  # back to the page's order
    page.reload()
    assert name.get_attribute("aria-sort") is None
    assert _names(page, "#staff-table") == page_order


def test_hiding_the_sorted_column_drops_the_kept_sort(page: Page) -> None:
    page.goto(f"{ORIGIN}/rosters/staff")
    header = page.locator("#staff-table th.sortable").nth(1)
    column = header.get_attribute("data-col")
    header.locator(".sort-btn").click()
    assert header.get_attribute("aria-sort") == "ascending"
    assert _kept(page)
    page.locator(f'[data-col-toggle="{column}"]').click()
    assert page.locator("#staff-table th[aria-sort]").count() == 0  # cleared on hiding,
    assert not _kept(page)  # not only on the next load
    page.reload()
    assert page.locator("#staff-table th[aria-sort]").count() == 0
    page.locator(f'[data-col-toggle="{column}"]').click()  # shown again, still unsorted
    assert page.locator("#staff-table th[aria-sort]").count() == 0
    assert not _kept(page)


def test_each_table_on_a_page_keeps_its_own_sort(page: Page) -> None:
    url = f"{ORIGIN}/ra-leave/staff/precinct?as=Sam%20Lee"
    page.goto(url)
    tables = page.locator("table[data-sort-auto]")
    assert tables.count() > 1
    tables.nth(1).locator(".sort-btn").first.click()
    page.goto(url)
    assert [tables.nth(i).locator("th[aria-sort]").count() for i in range(tables.count())] == [
        1 if i == 1 else 0 for i in range(tables.count())
    ]
