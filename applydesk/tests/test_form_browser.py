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


# --- Rung 3: moves, the last-card rule, reordering, Preview ---


def _labels(page: Page) -> list[str]:
    # textContent: an open card hides its summary, which inner_text reads as "".
    return page.eval_on_selector_all(
        '#fb-cards > .fc [data-sum="label"]', "els => els.map(e => e.textContent)"
    )


def _kinds(page: Page) -> list[str]:
    return page.eval_on_selector_all(
        "#fb-cards > [data-kind]", "els => els.map(e => e.dataset.kind)"
    )


def test_new_adds_an_open_string_card_after_this_one(page: Page) -> None:
    page.goto(FORM)
    card = _card(page, "Project title")
    card.locator("[data-fc-toggle]").click()
    card.locator('[data-fc-act="new"]').click()
    labels = _labels(page)
    added = page.locator("#fb-cards > .fc").nth(labels.index("Project title") + 1)
    assert added.get_attribute("data-type") == "string"
    assert added.get_attribute("data-open") is not None
    assert added.locator('[data-f="label"]').evaluate("e => e === document.activeElement")
    assert added.locator('[data-sum="shown"]').text_content() == "Not shown"  # the safer side
    added.locator('[data-f="label"]').fill("Supervisor's name")
    assert "Supervisor's name" in page.locator("[data-fb-outline]").inner_text()
    assert "10 questions" in page.locator("[data-fb-counts]").inner_text()


def test_replicate_copies_the_card(page: Page) -> None:
    page.goto(FORM)
    card = _card(page, "Months the project will run")
    card.locator("[data-fc-toggle]").click()
    card.locator('[data-fc-act="replicate"]').click()
    copies = _card(page, "Months the project will run")
    assert copies.count() == 2
    copy = copies.nth(1)
    assert copy.get_attribute("data-type") == "integer"
    assert copy.locator('[data-f="max"][data-g="number"]').input_value() == "6"
    assert copy.locator('[data-sum="type"]').text_content() == "Integer · 1 to 6, step 1"


def test_section_and_page_break_are_added_after_the_card(page: Page) -> None:
    page.goto(FORM)
    card = _card(page, "Summary")
    card.locator("[data-fc-toggle]").click()
    card.locator('[data-fc-act="pagebreak"]').click()
    card.locator('[data-fc-act="section"]').click()
    kinds = _kinds(page)
    at = page.eval_on_selector_all(
        "#fb-cards > [data-kind]",
        "els => els.findIndex(e =>"
        " (e.querySelector('[data-sum=label]') || {}).textContent === 'Summary')",
    )
    assert kinds[at + 1 : at + 3] == ["section", "pagebreak"]
    section = page.locator("#fb-cards > [data-kind]").nth(at + 1)
    section.locator('[data-f="label"]').fill("Plans")
    outline = page.locator("[data-fb-outline]").inner_text()
    assert "Plans" in outline and "Page 3" in outline
    assert page.locator("[data-fb-counts]").inner_text().startswith("3 pages · 3 sections")


def test_delete_removes_a_card_and_the_last_card_stays(page: Page) -> None:
    page.goto(FORM)
    card = _card(page, "Methods")
    card.locator("[data-fc-toggle]").click()
    card.locator('[data-fc-act="delete"]').click()
    assert "Methods" not in _labels(page)
    page.locator(".fc-break [data-fc-act=delete]").click()  # a page break's Remove
    assert "pagebreak" not in _kinds(page)
    page.goto(BLANK)
    only = page.locator('#fb-cards > .fc[data-kind="field"]')
    assert only.locator('[data-fc-act="delete"]').is_disabled()
    assert only.locator('[data-fc-act="delete"]').get_attribute("title") == (
        "A form keeps at least one card"
    )
    only.locator('[data-fc-act="new"]').click()
    dels = page.locator('#fb-cards > .fc[data-kind="field"] [data-fc-act="delete"]')
    assert dels.nth(0).is_enabled() and dels.nth(1).is_enabled()
    dels.nth(1).click()
    assert page.locator('#fb-cards > .fc[data-kind="field"] [data-fc-act="delete"]').is_disabled()


def test_a_card_is_dragged_by_its_handle(page: Page) -> None:
    page.goto(FORM)
    before = _labels(page)
    grip = _card(page, "Field of study").locator("[data-fc-grip]")
    target = _card(page, "Project title")
    page.set_viewport_size({"width": 1280, "height": 1400})  # both on screen
    g = grip.bounding_box()
    t = target.bounding_box()
    assert g is not None and t is not None
    page.mouse.move(g["x"] + g["width"] / 2, g["y"] + g["height"] / 2)
    page.mouse.down()
    page.mouse.move(g["x"] + 5, t["y"] + 4, steps=12)  # into the top half of Project title
    page.mouse.up()
    after = _labels(page)
    assert after.index("Field of study") == after.index("Project title") - 1
    assert sorted(after) == sorted(before)
    outline = page.locator("[data-fb-outline] .fb-o-item").all_inner_texts()
    assert outline.index("Field of study") < outline.index("Project title")


def test_a_card_moves_with_the_arrow_keys(page: Page) -> None:
    page.goto(FORM)
    grip = _card(page, "Summary").locator("[data-fc-grip]")
    grip.focus()
    page.keyboard.press("ArrowUp")
    labels = _labels(page)
    assert labels.index("Summary") == labels.index("Project title") - 1
    assert grip.evaluate("e => e === document.activeElement")
    page.keyboard.press("ArrowDown")
    labels = _labels(page)
    assert labels.index("Summary") == labels.index("Project title") + 1
    page.keyboard.press("ArrowDown")
    labels = _labels(page)
    assert labels.index("Summary") == labels.index("Methods") + 1


def test_preview_shows_the_form_as_an_applicant_sees_it(page: Page) -> None:
    page.goto(FORM)
    page.locator("[data-fb-preview]").click()
    assert page.locator("#fb-preview").is_visible()
    assert not page.locator("#fb-cards").is_visible()
    body = page.locator("[data-fb-preview-body]")
    assert body.locator("h3.fb-pv-form").inner_text() == "Application form"
    assert body.locator(".fb-pv-page").all_inner_texts() == ["PAGE 1", "PAGE 2"]
    assert body.get_by_label("Months the project will run").get_attribute("type") == "number"
    assert body.get_by_label("Months the project will run").get_attribute("max") == "6"
    assert body.get_by_role("radio", name="Engineering").count() == 1
    assert body.locator(".fb-pv-frame").count() == 1
    assert "Reviewers see your answer." in body.inner_text()
    page.locator("[data-fb-preview-close]").click()
    assert page.locator("#fb-cards").is_visible() and not page.locator("#fb-preview").is_visible()
