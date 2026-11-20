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
    assert "was discarded." in page.locator("[data-nx-said]").inner_text()
    assert page.locator("tr", has_text="Browser Bursary 2027").count() == 0


def test_form_saved_into_a_scratch_exercise_survives_a_reload(page: Page) -> None:
    page.goto(LOBBY)
    page.get_by_role("button", name="New exercise").click()
    page.locator("[data-nx-name]").fill("Form Walkthrough")
    page.get_by_role("button", name="Create").click()
    page.wait_for_url(f"{LOBBY}/*")
    page.goto(page.url + "/form")
    # A blank form's one question opens by itself.
    card = page.locator('#fb-cards > .fc[data-kind="field"]')
    card.locator('[data-f="label"]').fill("What do you study?")
    assert page.locator("[data-unsaved]").is_visible()
    page.locator("[data-fb-save]").click()
    page.locator("[data-fb-said]").filter(has_text="Saved to this scratch exercise.").wait_for()
    assert page.locator("[data-unsaved]").is_hidden()
    # An edit made while a save is on its way keeps the page unsaved (Codex).
    page.route(
        "**/form",
        lambda route: (
            page.locator('#fb-cards > .fc[data-kind="field"] [data-f="label"]').fill(
                "What do you study, and where?"
            ),
            route.fallback(),
        ),
    )
    page.locator("[data-fb-save]").click()
    page.locator("[data-fb-said]").filter(has_text="not the changes made since").wait_for()
    assert page.locator("[data-unsaved]").is_visible()
    page.unroute("**/form")
    page.once("dialog", lambda d: d.accept())
    page.reload()
    assert (
        page.locator('#fb-cards > .fc[data-kind="field"] [data-f="label"]').input_value()
        == "What do you study?"
    )


def test_process_saved_into_a_scratch_exercise_survives_a_reload(page: Page) -> None:
    """Rung 4: a stage, a gate and an outcome added on Process, saved,
    and read back; the outcome's ticked email is owed on Emails."""
    page.goto(LOBBY)
    page.get_by_role("button", name="New exercise").click()
    page.locator("[data-nx-name]").fill("Process Walkthrough")
    page.get_by_role("button", name="Create").click()
    page.wait_for_url(f"{LOBBY}/*")
    home = page.url
    page.goto(home + "/process")
    first = page.locator("#pc-cards > .fc").first
    if first.locator("[data-fc-toggle]").get_attribute("aria-expanded") == "false":
        first.locator("[data-fc-toggle]").click()
    first.locator('[data-pc="name"]').fill("Applications")
    first.locator('[data-fc-act="new"]').click()
    second = page.locator("#pc-cards > .fc").nth(1)
    if second.locator("[data-fc-toggle]").get_attribute("aria-expanded") == "false":
        second.locator("[data-fc-toggle]").click()
    second.locator('[data-pc="name"]').fill("Review")
    second.locator('[data-pc-act="gate"]').click()
    second.locator('.pc-item[data-item="gate"] [data-pc="item-name"]').fill("Panel read")
    second.locator('[data-pc-act="outcome"]').click()
    outcome = second.locator('.pc-item[data-item="outcome"]')
    outcome.locator('[data-pc="item-name"]').fill("Award")
    outcome.locator('[data-pc="values"]').fill("Awarded, Not awarded")
    outcome.locator('[data-rel="applicants-email"]').check()
    # Gates are renumbered on saving, so the page reloads to hold the keys.
    with page.expect_navigation():
        page.locator("[data-fb-save]").click()
    said = page.locator("[data-fb-said]")
    said.filter(has_text="Saved").wait_for()
    assert said.inner_text() == "Saved to this scratch exercise.", said.inner_text()
    assert page.locator("[data-unsaved]").is_hidden()
    names = page.locator('#pc-cards > .fc [data-pc="name"]')
    assert [names.nth(i).input_value() for i in range(names.count())] == [
        "Applications",
        "Review",
    ]
    gate = page.locator('.pc-item[data-item="gate"]')
    assert gate.get_attribute("data-key") == "g1"
    assert gate.locator('[data-pc="item-name"]').input_value() == "Panel read"
    outcome = page.locator('.pc-item[data-item="outcome"]')
    assert outcome.get_attribute("data-key") == "o1"
    assert outcome.locator('[data-pc="values"]').input_value() == "Awarded, Not awarded"
    assert outcome.locator('[data-rel="applicants-email"]').is_checked()
    page.goto(home + "/emails")
    assert "Award" in page.locator("main").inner_text()


def test_panels_saved_into_a_scratch_exercise_survive_a_reload(page: Page) -> None:
    """Rung 5: a panel made in Manage panels, with a member from the
    directory, saved, read back, and offered to a gate on Process."""
    page.goto(LOBBY)
    page.get_by_role("button", name="New exercise").click()
    page.locator("[data-nx-name]").fill("Panels Walkthrough")
    page.get_by_role("button", name="Create").click()
    page.wait_for_url(f"{LOBBY}/*")
    home = page.url
    page.goto(home + "/panels")
    who = page.evaluate("JSON.parse(document.getElementById('pn-people').textContent)[0]")
    page.locator('[data-pn-act="manage"]').click()
    page.locator("[data-pn-newname]").fill("Readers")
    page.locator("[data-pn-members]").fill(who[1])
    page.locator("[data-pn-members]").press("Enter")
    page.locator('[data-pn-act="create"]').click()
    # Still open in Manage panels: Save is refused, saying why.
    page.locator("[data-fb-save]").click()
    assert "Keep or undo" in page.locator("[data-pn-said]").inner_text()
    page.locator('[data-pn-act="save-names"]').click()
    # The save keys the panel anew, so the page reloads to hold its key,
    # and says it saved once back (cold read).
    with page.expect_navigation():
        page.locator("[data-fb-save]").click()
    page.locator("[data-fb-said]").filter(has_text="Saved to this scratch exercise.").wait_for()
    assert page.locator("[data-pn-kept]").is_hidden()
    assert page.locator('th[data-panel="panel-1"]').inner_text().startswith("Readers")
    # Saved again, it keeps its key.
    with page.expect_navigation():
        page.locator("[data-fb-save]").click()
    page.locator("[data-fb-said]").filter(has_text="Saved to this scratch exercise.").wait_for()
    assert page.locator('th[data-panel="panel-1"]').inner_text().startswith("Readers")
    assert page.locator("[data-pn-row]").count() == 1
    assert who[1] in page.locator("[data-pn-row]").first.inner_text()
    page.goto(home + "/process")
    pools = page.evaluate("JSON.parse(document.getElementById('pc-pools').textContent)")
    assert pools["panel-1"]["name"] == "Readers", pools


def test_an_email_saved_into_a_scratch_exercise_survives_a_reload(page: Page) -> None:
    """Rung 6: the receipt a new exercise owes, started from the default,
    saved, written after a reload; a tag of another kind refused."""
    page.goto(LOBBY)
    page.get_by_role("button", name="New exercise").click()
    page.locator("[data-nx-name]").fill("Emails Walkthrough")
    page.get_by_role("button", name="Create").click()
    page.wait_for_url(f"{LOBBY}/*")
    home = page.url
    page.goto(home + "/emails")
    card = page.locator('[data-em-item="receipt"]')
    assert card.locator("[data-em-chip]").text_content() == "Owed"
    card.locator('[data-em-act="reset"]').click()
    card.locator('[data-em-act="save"]').click()
    card.locator("[data-em-said]").filter(has_text="Saved to this scratch exercise.").wait_for()
    assert card.locator("[data-em-chip]").text_content() == "Written"
    page.reload()
    card = page.locator('[data-em-item="receipt"]')
    assert card.locator("[data-em-chip]").text_content() == "Written"
    assert card.locator("[data-em-subject]").input_value().startswith("$exercise_name")
    assert card.locator('[data-em-act="save"]').is_disabled()
