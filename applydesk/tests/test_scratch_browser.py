"""A scratch exercise in a real Chromium (segment AD1N rung 2): *New
exercise*, a name, the blank draft's Home; Details saved into it, kept
across a reload; Discard. Skips without a Chromium build, as
`test_form_browser.py`'s."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Error, Page, Route, sync_playwright

from applydesk import scratch
from applydesk.tests._host import host_with
from applydesk.tests.test_form_browser import ORIGIN

LOBBY = f"{ORIGIN}/applydesk/operator/exercises"


@pytest.fixture
def page() -> Iterator[Page]:
    """As `test_form_browser.py`'s, but every method served, with its body
    and redirects, and the test client keeping the scratch cookie."""
    scratch.clear()
    client = TestClient(host_with(("applydesk",))[0], follow_redirects=False)

    def serve(route: Route) -> None:
        request = route.request
        headers = {
            k: v
            for k, v in request.headers.items()
            if k.lower() in ("content-type", "sec-fetch-site")
        }
        response = client.request(
            request.method,
            request.url.removeprefix(ORIGIN),
            content=request.post_data_buffer,
            headers=headers,
        )
        if response.is_redirect:
            # A fulfilled 3xx does not navigate in Chromium; a page that
            # moves on at once stands in for it.
            to = ORIGIN + response.headers["location"].removeprefix("http://testserver")
            route.fulfill(
                status=200,
                body=f"<script>location.replace({to!r})</script>",
                headers={"content-type": "text/html"},
            )
            return
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
        scratch.clear()
        assert errors == [], f"page errors: {errors}"


def test_new_exercise_to_its_home_then_details_saved_and_discarded(page: Page) -> None:
    page.goto(LOBBY)
    page.get_by_role("button", name="New exercise").click()
    page.locator("[data-nx-name]").fill("Browser Bursary 2027")
    page.get_by_role("button", name="Create").click()
    page.wait_for_url(f"{LOBBY}/*")
    assert page.locator("h1").inner_text().startswith("Browser Bursary 2027")
    assert page.locator("[data-scratch-note]").is_visible()
    card = page.locator("[data-details]")
    card.locator("[data-dt-lock]").click()
    card.locator('[data-dt="code"]').fill("BB-27")
    card.locator('[data-dt="description"]').fill("A bursary set up in the browser.")
    card.locator('[data-dt-act="lock"]').click()
    said = card.locator("[data-dt-said]")
    said.filter(has_text="Saved to this scratch exercise.").wait_for()
    page.reload()
    card = page.locator("[data-details]")
    assert card.locator('[data-dt-show="code"]').inner_text() == "BB-27"
    assert (
        card.locator('[data-dt-show="description"]').inner_text()
        == "A bursary set up in the browser."
    )
    # A clashing code is refused by the server too, its reason shown.
    card.locator("[data-dt-lock]").click()
    card.locator('[data-dt="code"]').fill("RA-2027")
    card.locator('[data-dt-act="lock"]').click()
    card.locator("[data-dt-why]").filter(has_text="already").wait_for()
    card.locator('[data-dt-act="discard"]').click()
    page.goto(LOBBY)
    row = page.locator("tr", has_text="Browser Bursary 2027")
    assert row.locator("[data-scratch-chip]").inner_text().lower() == "scratch"
    page.once("dialog", lambda d: d.accept())
    row.get_by_role("button", name="Discard").click()
    page.wait_for_url(f"{LOBBY}?said=*")
    assert "Browser Bursary 2027 discarded." in page.locator("[data-nx-said]").inner_text()
    assert page.locator("tr", has_text="Browser Bursary 2027").count() == 0
