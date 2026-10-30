"""Log encounter's script in a real Chromium (segment 1D rung 2): Save waits
for the three required choices, Clear unsets an optional one, "Who started
it?" hides and drops its choice when the type already says, and the note
counts its characters; and a staff or student filter's box of people turns
a match into a pill and blocks an unmatched name (rung 8). Served as the
sort tests are; without a Chromium
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


def test_the_follow_ups_follow_the_student_chosen(page: Page) -> None:
    """Codex review, 2026-10-29: choosing a student on the form shows the
    plan they are on, as opening the form for them does."""
    page.goto(f"{ORIGIN}/log")
    page.locator("details.more > summary", has_text="Add details").click()
    assert page.locator("#add-follow").is_visible() and page.locator("#on-plan").is_hidden()
    choose(page, "Student", "Aiden Chen")
    assert page.locator("#on-plan").text_content() == "On your follow-ups: weekly."
    assert page.locator("#add-follow").is_hidden()
    assert page.locator("#cadence").input_value() == "Weekly"
    choose(page, "Student", "Clara Tan")
    assert page.locator("#on-plan").text_content() == "On your plans: weekly, set by Sam Lee."
    assert page.locator("#cadence-field").is_hidden()
    choose(page, "Student", "Bao Nguyen")
    assert page.locator("#on-plan").is_hidden() and page.locator("#add-follow").is_visible()
    assert page.locator("#cadence-field").is_visible() and page.locator("#cadence").input_value() == "No fixed cadence"


def test_marking_a_safety_concern_carries_the_choices(page: Page) -> None:
    page.goto(f"{ORIGIN}/log")
    choose(page, "Student", "Bao Nguyen")
    choose(page, "Duration", "10 min")
    page.get_by_role("button", name="Mark a safety concern").click()
    page.wait_for_url("**/log/safety?**")
    raise_ = page.locator("#raise")
    assert raise_.is_disabled()
    page.select_option("#ctx-type", "Check-in")
    assert raise_.is_disabled()
    choose(page, "Escalation step taken", "Duty senior staff contacted")
    assert raise_.is_enabled()
    raise_.click()
    page.wait_for_url("**/log/safety/raised?**")
    assert "A safety flag is raised for Bao Nguyen" in page.content()


OPEN = "records=open&understood=yes"


def download(page: Page):
    return page.locator("#dl-h").locator("xpath=..").locator("button[type=submit]")


def staff_box(page: Page):
    return page.locator(".tokens[aria-label='Staff']")


def test_a_filter_turns_a_matched_name_or_email_into_a_pill(page: Page) -> None:
    """Records across staff's filters (rung 8), Assignments' box of people
    made live: a match becomes a pill carrying the value, its remove button
    takes the label's id, removing it brings the typeahead back, and case
    and spaces do not matter."""
    page.goto(f"{ORIGIN}/overview/records?as=Sam%20Lee&{OPEN}")
    page.locator("#dl-staff").fill("  GRACE.HO@EXAMPLE.EDU ")
    page.locator("#dl-staff").press("Enter")
    pill = staff_box(page).locator(".token")
    assert pill.inner_text().startswith("Grace Ho")
    assert pill.locator("input[type=hidden]").get_attribute("value") == "Grace Ho"
    assert page.locator("#dl-staff").get_attribute("aria-label") == "Remove Grace Ho from Staff"  # the label names it
    assert staff_box(page).locator(".token-input").is_hidden()
    page.locator("#dl-staff").click()
    assert staff_box(page).locator(".token").count() == 0
    assert page.locator("#dl-staff").evaluate("el => el.classList.contains('token-input') && document.activeElement === el")


def test_typing_a_name_then_enter_keeps_the_pill(page: Page) -> None:
    """Key by key, then Enter twice: the pill stays, and the download goes
    out for that staff member, never for everyone."""
    page.goto(f"{ORIGIN}/overview/records?as=Sam%20Lee&{OPEN}")
    page.locator("#dl-staff").press_sequentially("Grace Ho")
    assert staff_box(page).locator(".token").count() == 0  # never taken mid-typing
    page.keyboard.press("Enter")
    assert staff_box(page).locator(".token input[type=hidden]").get_attribute("value") == "Grace Ho"
    page.keyboard.press("Enter")  # focus stayed on the box, not the pill's remove button
    assert staff_box(page).locator(".token").count() == 1
    with page.expect_request(lambda r: "records.csv" in r.url) as sent:
        download(page).click()
    assert parse_qs(urlparse(sent.value.url).query)["staff"] == ["Grace Ho"]


def test_an_unmatched_name_blocks_the_download(page: Page) -> None:
    page.goto(f"{ORIGIN}/overview/records?as=Sam%20Lee&{OPEN}")
    requests: list[str] = []
    page.on("request", lambda r: requests.append(r.url))
    page.locator("#dl-staff").press_sequentially("Daniel Kho")
    page.keyboard.press("Enter")
    assert page.locator("#dl-staff").evaluate("el => el.validationMessage").startswith("Choose a name")
    download(page).click()
    page.wait_for_timeout(300)
    assert not [u for u in requests if "records.csv" in u]


def test_a_chosen_pill_from_the_server_can_be_removed(page: Page) -> None:
    page.goto(f"{ORIGIN}/overview/records?as=Sam%20Lee&{OPEN}&staff=Grace%20Ho")
    box = page.locator(".tokens[aria-label='Purged records: Staff']")
    assert box.locator(".token-input").is_hidden()
    page.locator("#p-staff").click()  # the remove button holds the field's id
    assert box.locator(".token").count() == 0 and page.locator("#p-staff").is_visible()


def test_your_records_student_box_is_live(page: Page) -> None:
    page.goto(f"{ORIGIN}/students/?{OPEN}")
    page.locator("#dl-student").fill("Clara Tan")
    page.locator("#dl-student").press("Enter")
    box = page.locator(".tokens[aria-label='Student']")
    assert box.locator("input[type=hidden]").get_attribute("value") == "S-03"
    assert page.locator("#purge-student").is_disabled()


def test_a_chosen_filter_downloads_for_that_person(page: Page) -> None:
    page.goto(f"{ORIGIN}/overview/records?as=Sam%20Lee&{OPEN}")
    page.locator("#dl-staff").fill("Priya Raman")
    page.locator("#dl-staff").press("Enter")
    page.locator("#dl-student").fill("hana.rahim@u.example.edu")
    page.locator("#dl-student").press("Enter")
    with page.expect_request(lambda r: "records.csv" in r.url) as sent:
        page.locator("#dl-h").locator("xpath=..").locator("button[type=submit]").click()
    query = parse_qs(urlparse(sent.value.url).query)
    assert query["staff"] == ["Priya Raman"] and query["student"] == ["S-08"]
