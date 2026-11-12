"""The Form page in a real Chromium (segment AD1B, rung 2): cards open
and close, the type menu swaps a card's fields, the toggles flip, and a
card's summary and the Outline follow every edit. Without a Chromium
build the test skips, saying why; ``RRW_REQUIRE_BROWSER=1`` (set by CI)
turns that skip into a failure."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Error, Locator, Page, Route, sync_playwright

from applydesk.tests._host import host_with

ORIGIN = "http://applydesk.test"
FORM = f"{ORIGIN}/applydesk/operator/exercises/wa9juxbc2t/form"
BLANK = f"{ORIGIN}/applydesk/operator/exercises/n5wg8tjr3e/form"


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
        tab.route(f"{ORIGIN}/**", serve)
        yield tab
        browser.close()
        assert errors == [], f"page errors: {errors}"


def _card(page: Page, label: str) -> Locator:
    return page.locator(".fc", has=page.locator(f'[data-sum="label"]:text-is("{label}")'))


def test_a_card_opens_and_closes(page: Page) -> None:
    page.goto(FORM)
    card = _card(page, "Months the project will run")
    toggle = card.locator("[data-fc-toggle]")
    assert toggle.get_attribute("aria-expanded") == "false"
    assert not card.locator('[data-f="label"]').is_visible()
    toggle.click()
    assert toggle.get_attribute("aria-expanded") == "true"
    assert card.locator('[data-f="label"]').is_visible()
    assert card.locator('[data-f="step"]').is_visible()  # an Integer's fields
    assert not card.locator('[data-f="options"]').is_visible()
    toggle.click()
    assert not card.locator('[data-f="label"]').is_visible()


def test_editing_a_card_updates_its_summary_and_the_outline(page: Page) -> None:
    page.goto(FORM)
    # By position: the label it is found by is about to change.
    card = page.locator('.fc[data-kind="field"]').nth(4)
    assert card.locator('[data-sum="label"]').inner_text() == "Months the project will run"
    card.locator("[data-fc-toggle]").click()
    card.locator('[data-f="max"][data-g="number"]').fill("12")
    card.locator('[data-f="label"]').fill("Months the project will take")
    card.locator("[data-fc-toggle]").click()
    assert card.locator('[data-sum="type"]').inner_text() == "Integer · 1 to 12, step 1"
    assert card.locator('[data-sum="label"]').inner_text() == "Months the project will take"
    assert "Months the project will take" in page.locator("[data-fb-outline]").inner_text()


def test_the_type_menu_swaps_a_card_s_fields(page: Page) -> None:
    page.goto(FORM)
    card = _card(page, "Months the project will run")
    card.locator("[data-fc-toggle]").click()
    card.locator('[data-f="type"]').select_option("list")
    assert card.get_attribute("data-type") == "list"
    assert card.locator('[data-f="options"]').is_visible()
    assert not card.locator('[data-f="step"]').is_visible()
    # The question, help text, visibility and Required are kept.
    assert card.locator('[data-f="label"]').input_value() == "Months the project will run"
    card.locator('[data-f="options"]').fill("One, Two")
    card.locator('[data-f="exclusive"][data-v="false"]').click()
    assert card.locator('[data-sum="type"]').text_content() == "List · choose any · One, Two"
    card.locator('[data-f="type"]').select_option("text")
    assert card.locator(".l-t", has_text="Title").first.is_visible()
    assert not card.locator('[data-f="required"]').is_visible()
    assert (
        card.locator('[data-sum="type"]').text_content() == "Title and Description · display only"
    )


def test_required_and_visibility_toggle(page: Page) -> None:
    page.goto(FORM)
    card = _card(page, "Matriculation number")
    card.locator("[data-fc-toggle]").click()
    required = card.locator('[data-f="required"]')
    assert required.get_attribute("aria-pressed") == "true"
    required.click()
    assert required.get_attribute("aria-pressed") == "false"
    assert card.locator('[data-sum="required"]').text_content() == "Optional"
    card.locator('[data-f="shown"][data-v="true"]').click()
    assert card.locator('[data-sum="shown"]').text_content() == "Shown to reviewers"
    assert "Matriculation number" in page.locator("[data-fb-outline]").inner_text()


def test_the_photo_ratio_sets_the_kept_size(page: Page) -> None:
    page.goto(FORM)
    card = _card(page, "Photo")
    card.locator("[data-fc-toggle]").click()
    card.locator('[data-f="ratio_w"]').fill("1")
    card.locator('[data-f="ratio_h"]').fill("1")
    assert card.locator('[data-sum="kept"]').text_content() == (
        "Kept as a 600 × 600 JPEG: 600 px on its longer side."
    )
    assert card.locator('[data-sum="type"]').text_content() == "Photo · 1:1, kept 600 × 600"


def test_the_outline_counts_the_form(page: Page) -> None:
    page.goto(FORM)
    assert page.locator("[data-fb-counts]").inner_text() == (
        "2 pages · 2 sections · 9 questions · 6 required"  # a text block is no question
    )
    page.goto(BLANK)
    assert page.locator("[data-fb-counts]").inner_text() == (
        "1 page · 0 sections · 1 question · 0 required"
    )
    assert page.locator('.fc[data-kind="field"] [data-f="label"]').is_visible()  # opened
