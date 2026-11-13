"""The Applications page in a real Chromium (segment AD1C): a gate's chip
cycles, an outcome is picked and dated, the counts follow, a release asks
to confirm, rows filter and are set in bulk. Without a Chromium build the
test skips, saying why; ``RRW_REQUIRE_BROWSER=1`` (set by CI) turns that
skip into a failure."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Dialog, Error, Locator, Page, Route, sync_playwright

from applydesk.tests._host import host_with

ORIGIN = "http://applydesk.test"
PAGE = f"{ORIGIN}/applydesk/operator/exercises/wa9juxbc2t/applications"


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


def _count(page: Page, key: str) -> str:
    return page.locator(f'[data-ap-count="{key}"]').inner_text()


def _row(page: Page, text: str) -> Locator:
    return page.locator("[data-row]", has_text=text).first


def test_a_gate_chip_cycles_and_the_count_follows(page: Page) -> None:
    page.goto(PAGE)
    before = _count(page, "g1")
    chip = _row(page, "kenji.russo").locator('[data-cell="g1"] [data-ap-adm]')
    assert chip.inner_text() == "Selected"
    chip.click()
    assert chip.inner_text() == "Not selected"
    chip.click()
    assert chip.inner_text() == "Pending"
    n = int(before.split()[0])
    assert _count(page, "g1").startswith(f"{n - 1} selected · 1 pending")
    chip.click()
    assert chip.inner_text() == "Selected" and _count(page, "g1") == before


def test_an_outcome_is_picked_and_dated(page: Page) -> None:
    page.goto(PAGE)
    row = _row(page, "aisha.rahman")
    pick = row.locator('[data-cell="o2"] select')
    assert row.locator('[data-cell="o2"] [data-ap-date]').inner_text() == "Due 24 Nov"
    pick.select_option("Finalist")
    assert row.locator('[data-cell="o2"] [data-ap-date]').inner_text() == "13 Nov"
    assert _count(page, "o2").startswith("1 finalist")
    pick.select_option("Pending")
    assert row.locator('[data-cell="o2"] [data-ap-date]').inner_text() == "Due 24 Nov"


def test_a_release_asks_first(page: Page) -> None:
    page.goto(PAGE)
    switch = page.locator('[data-ap-release="Finalists"]')
    answers: list[str] = []

    def dismiss(d: Dialog) -> None:
        answers.append(d.message)
        d.dismiss()

    page.once("dialog", dismiss)
    switch.click()
    assert "Timeline" in answers[0] and not switch.is_checked()
    page.once("dialog", lambda d: d.accept())
    switch.click()
    assert switch.is_checked()
    note = page.locator('th[data-col="o2"] [data-ap-relnote]').inner_text()
    assert note.startswith("13 Nov")


def test_search_status_and_last_applications_filter(page: Page) -> None:
    page.goto(PAGE)
    shown = page.locator("[data-ap-shown]")
    assert shown.inner_text() == "Showing 101 of 101"
    page.locator("[data-ap-search]").fill("chen.farouk")
    assert shown.inner_text() == "Showing 2 of 101"
    page.locator("[data-ap-which]").select_option("last")
    assert shown.inner_text() == "Showing 1 of 101"
    assert "Submitted" in page.locator("[data-row]:visible").inner_text()
    page.locator("[data-ap-search]").fill("")
    page.locator("[data-ap-which]").select_option("all")
    page.locator("[data-ap-status]").select_option("Draft")
    assert shown.inner_text() == "Showing 7 of 101"


def test_ticked_rows_are_set_together(page: Page) -> None:
    page.goto(PAGE)
    for who in ("aisha.bello", "kenji.russo", "wen.novak"):
        _row(page, who).locator("[data-ap-tick]").check()
    page.locator("[data-ap-set-col]").select_option("g3")
    page.locator("[data-ap-set-val]").select_option("Selected")
    page.locator("[data-ap-set]").click()
    for who in ("aisha.bello", "kenji.russo"):
        assert _row(page, who).locator('[data-cell="g3"] [data-ap-adm]').inner_text() == "Selected"
    # A draft has entered nothing: it is left alone.
    assert _row(page, "wen.novak").locator('[data-cell="g3"]').inner_text().strip() == "—"


def test_an_application_advanced_by_hand_can_be_given_later_outcomes(page: Page) -> None:
    # Codex: a submitted application outside the shortlist showed fixed
    # "—" in Finalists and Final results, so a hand change stopped there.
    page.goto(PAGE)
    row = _row(page, "aisha.bello")
    row.locator('[data-cell="o1"] select').select_option("Shortlisted")
    finalists = row.locator('[data-cell="o2"] select')
    assert finalists.input_value() == ""
    finalists.select_option("Finalist")
    assert row.locator('[data-cell="o2"] [data-ap-date]').inner_text() == "13 Nov"
    # A draft stays inert.
    assert _row(page, "wen.novak").locator('[data-cell="o2"] select').count() == 0
