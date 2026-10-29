"""Log encounter's script in a real Chromium (segment 1D rung 2): Save waits
for the three required choices, Clear unsets an optional one, "Who started
it?" hides and drops its choice when the type already says, and the note
counts its characters. Served as the sort tests are; without a Chromium
build the test skips, saying why, and `RRW_REQUIRE_BROWSER=1` fails it."""

from __future__ import annotations

import os
from collections.abc import Iterator
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Error, Page, Route, sync_playwright

from residentialapps.supportlogs.main import create_app

ORIGIN = "http://supportlogs.test"


@pytest.fixture
def page() -> Iterator[Page]:
    client = TestClient(create_app())

    def serve(route: Route) -> None:
        response = client.get(route.request.url.removeprefix(ORIGIN), follow_redirects=False)
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
        tab = browser.new_page(viewport={"width": 390, "height": 844})
        errors: list[str] = []
        tab.on("pageerror", lambda exc: errors.append(str(exc)))
        tab.route(f"{ORIGIN}/**", serve)
        yield tab
        browser.close()
        assert errors == [], f"page errors: {errors}"


def choose(page: Page, legend: str, label: str) -> None:
    page.locator("fieldset", has=page.locator(f"legend:text-is('{legend}')")).locator(
        "label.choice", has_text=label).first.click()


def test_save_waits_for_student_duration_and_type(page: Page) -> None:
    page.goto(f"{ORIGIN}/log")
    save = page.locator("#save")
    assert save.is_disabled()
    choose(page, "Student", "Bao Nguyen")
    choose(page, "Duration", "10 min")
    assert save.is_disabled()
    choose(page, "Type", "Practical support")
    assert save.is_enabled()
    save.click()
    page.wait_for_url("**/log/saved?**")
    sent = parse_qs(urlparse(page.url).query)
    assert sent["student"] == ["S-02"] and sent["duration"] == ["10 min"] and sent["type"] == ["Practical support"]
    assert "note" not in sent


def test_who_started_it_hides_and_drops_its_choice(page: Page) -> None:
    page.goto(f"{ORIGIN}/log?student=S-02")
    page.locator("details.more > summary", has_text="Add details").click()
    choose(page, "Duration", "5 min")
    choose(page, "Type", "Check-in")
    choose(page, "Who started it?", "Staff")
    assert page.locator("#who").is_visible()
    choose(page, "Type", "Student-initiated conversation")
    assert page.locator("#who").is_hidden()
    page.locator("#save").click()
    page.wait_for_url("**/log/saved?**")
    assert "started" not in parse_qs(urlparse(page.url).query)


def test_clear_and_the_note_count(page: Page) -> None:
    page.goto(f"{ORIGIN}/log")
    page.locator("details.more > summary", has_text="Add details").click()
    choose(page, "How", "Phone")
    assert page.locator('input[name="mode"]:checked').count() == 1
    page.locator('[data-clear="mode"]').click()
    assert page.locator('input[name="mode"]:checked').count() == 0
    page.locator("#note").fill("Caught up after dinner.")
    assert page.locator("#note-count").text_content() == "23 / 300"


def test_add_details_is_a_finger_sized_target(page: Page) -> None:
    page.goto(f"{ORIGIN}/log")
    box = page.locator("details.more > summary", has_text="Add details").bounding_box()
    assert box and box["height"] >= 44
