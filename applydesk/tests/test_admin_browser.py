"""Admin → Accounts Management's *Add an operator* box in a real Chromium
(segment AD2W, rung 4): typing offers people on record, then the
directory; Add is live only for a pick and admits them; Cancel clears the
box. Without a Chromium build the tests skip, saying why;
``RRW_REQUIRE_BROWSER=1`` (set by CI) turns that skip into a failure."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Dialog, Error, Page, Route, expect, sync_playwright

from applydesk.tests._host import host_with

ORIGIN = "http://applydesk.test"


@pytest.fixture
def page() -> Iterator[Page]:
    """A Chromium tab on the app, as `test_form_browser.py`'s, forwarding
    each request's method and body: *Add* posts a form."""
    client = TestClient(host_with(("applydesk",))[0])

    def serve(route: Route) -> None:
        request = route.request
        response = client.request(
            request.method,
            request.url.removeprefix(ORIGIN),
            content=request.post_data_buffer,
            headers={"content-type": request.headers.get("content-type", "")},
        )
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


ADMIN = f"{ORIGIN}/applydesk/admin/operators"


def test_typing_offers_a_pick_and_add_admits_it(page: Page) -> None:
    page.goto(ADMIN)
    box = page.locator("[data-op-add-box]")
    add = page.locator("[data-op-add-submit]")
    cancel = page.locator("[data-op-add-cancel]")
    expect(add).to_be_disabled()
    expect(cancel).to_be_disabled()
    box.fill("jane")
    option = page.locator("[data-op-add-options] option")
    expect(option).to_have_count(1)
    label = option.first.get_attribute("value")
    assert label == "Jane Tan <jane.tan@example.edu>"
    expect(add).to_be_disabled()  # typed, not yet a pick
    expect(cancel).to_be_enabled()
    box.fill(label)
    box.dispatch_event("input")
    expect(add).to_be_enabled()
    add.click()
    expect(page.locator("[data-op-said]")).to_have_text("Added to the list.")
    expect(page.locator("[data-op-list]")).to_contain_text("jane.tan@example.edu")


def test_cancel_clears_the_box(page: Page) -> None:
    page.goto(ADMIN)
    box = page.locator("[data-op-add-box]")
    box.fill("jane")
    expect(page.locator("[data-op-add-options] option")).to_have_count(1)
    page.locator("[data-op-add-cancel]").click()
    expect(box).to_have_value("")
    expect(page.locator("[data-op-add-options] option")).to_have_count(0)
    expect(page.locator("[data-op-add-cancel]")).to_be_disabled()


def test_the_bulk_bar_wakes_on_a_tick_and_revoke_asks_first(page: Page) -> None:
    from applydesk import db, people

    session = db.new_session()
    people.pending(session, "kim@example.edu", None)
    session.commit()
    session.close()
    # Narrowed to kim: the samples' applicants are Unused too (segment AD2J).
    page.goto(f"{ADMIN}?show=unused&list_q=kim%40")
    admit = page.locator("[data-bulk-action][value='admit']")
    expect(admit).to_be_disabled()
    page.locator("[data-bulk-all]").check()
    expect(page.locator("[data-bulk-count]")).to_have_text("1")
    expect(admit).to_be_enabled()
    admit.click()
    expect(page.locator("[data-op-said]")).to_have_text("Added to the list: 1.")
    page.goto(f"{ADMIN}?show=operators")
    page.get_by_role("checkbox", name="Select kim@example.edu").check()
    asked: list[str] = []

    def answer(dialog: Dialog) -> None:
        asked.append(dialog.message)
        dialog.dismiss()  # No: nothing is revoked

    page.once("dialog", answer)
    page.locator("[data-bulk-revoke]").click()
    assert asked and "1 ticked person" in asked[0]
    expect(page.get_by_role("checkbox", name="Select kim@example.edu")).to_be_visible()
