"""The interop proof of concept's Clear list in a real Chromium (segment 23F,
author 2026-11-16): the button shows while the browser's list has a session,
asks, then empties the list, in this tab and in its storage. Pages go
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
        tab = browser.new_page(viewport={"width": 1000, "height": 900})
        errors: list[str] = []
        tab.on("pageerror", lambda exc: errors.append(str(exc)))
        tab.route(f"{ORIGIN}/**", serve)
        yield tab
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
