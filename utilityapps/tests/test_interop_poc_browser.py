"""The interop proof of concept's Clear list in a real Chromium (segment 23F,
author 2026-11-16): the button shows while the browser's list has a session,
asks, then empties the list, in this tab, in its storage and in
another open tab. Pages go
through a ``TestClient`` behind a routed origin, as the photo proof of
concept's browser test does. Without a Chromium build the test skips,
saying why; ``RRW_REQUIRE_BROWSER=1`` (set by CI) turns that skip into a
failure."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Error, Page, Route, expect, sync_playwright

from utilityapps.tests._host import host_with

ORIGIN = "http://utilities.test"
PAGE = f"{ORIGIN}/utilities/interop-poc/"
KEY = "interop-poc.sent"
SENT = [
    {
        "transfer_id": "00000000-0000-4000-8000-000000000001",
        "session_code": "POC-CLEAR-1",
        "session_url": "/reviewrobin/operator/sessions/abc",
        "sent_at": "2026-11-16T09:00:00Z",
    }
]


@pytest.fixture
def client() -> TestClient:
    return TestClient(host_with(("utilities",))[0])


@pytest.fixture
def page(client: TestClient) -> Iterator[Page]:
    def serve(route: Route) -> None:
        request = route.request
        response = client.request(
            request.method,
            request.url.removeprefix(ORIGIN),
            content=request.post_data_buffer,
            headers=request.headers,
        )
        route.fulfill(
            status=response.status_code, body=response.content, headers=dict(response.headers)
        )

    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch()
        except Error as exc:
            reason = f"Chromium could not launch: {exc.message.splitlines()[0]}"
            if os.environ.get("RRW_REQUIRE_BROWSER") == "1":
                pytest.fail(f"{reason}, and RRW_REQUIRE_BROWSER=1", pytrace=False)
            pytest.skip(reason)
        # One context, so a second tab shares this one's storage and
        # receives its ``storage`` events.
        context = browser.new_context(viewport={"width": 1000, "height": 900})
        errors: list[str] = []
        context.on("weberror", lambda error: errors.append(str(error.error)))
        context.route(f"{ORIGIN}/**", serve)
        yield context.new_page()
        browser.close()
        assert errors == [], f"page errors: {errors}"


def test_clear_list_empties_the_browsers_list(page: Page) -> None:
    page.goto(PAGE)
    clear = page.locator("#poc-sent-clear")
    expect(clear).to_be_hidden()  # nothing sent yet
    page.evaluate("([key, list]) => localStorage.setItem(key, JSON.stringify(list))", [KEY, SENT])
    page.reload()
    expect(page.locator("#poc-sent-rows")).to_contain_text("POC-CLEAR-1")
    expect(clear).to_be_visible()

    page.once("dialog", lambda dialog: dialog.dismiss())
    clear.click()
    expect(page.locator("#poc-sent-rows")).to_contain_text("POC-CLEAR-1")  # declined

    page.once("dialog", lambda dialog: dialog.accept())
    clear.click()
    expect(page.locator("#poc-sent-rows")).to_contain_text("No sessions sent")
    expect(clear).to_be_hidden()
    assert json.loads(page.evaluate(f"localStorage.getItem('{KEY}')")) == []


def test_another_tab_follows_the_clear(page: Page) -> None:
    page.goto(PAGE)
    page.evaluate("([key, list]) => localStorage.setItem(key, JSON.stringify(list))", [KEY, SENT])
    page.reload()
    other = page.context.new_page()
    other.goto(PAGE)
    expect(other.locator("#poc-sent-rows")).to_contain_text("POC-CLEAR-1")
    # A panel the other tab had open goes with the list (diff-reviewer).
    other.evaluate("document.getElementById('poc-sent-detail').textContent = 'Status: POC-CLEAR-1'")

    page.once("dialog", lambda dialog: dialog.accept())
    page.locator("#poc-sent-clear").click()
    expect(other.locator("#poc-sent-rows")).to_contain_text("No sessions sent")
    expect(other.locator("#poc-sent-clear")).to_be_hidden()
    expect(other.locator("#poc-sent-detail")).to_be_empty()
