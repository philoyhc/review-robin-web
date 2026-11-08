"""Log encounter's script in a real Chromium (segment 1D rung 2): Save waits
for the three required choices, Clear unsets an optional one, "Who started
it?" hides and drops its choice when the type already says, and the note
counts its characters; and a staff or student filter's box of people turns
a match into a pill and blocks an unmatched name (rung 8); and Students'
filter of plans and follow-ups, kept across a reload (rung 13); and that
text boxes resize vertically only, and Overview's withheld name opens
and closes (2026-11-07). Served as the
sort tests are; without a Chromium
build the test skips, saying why, and `RRW_REQUIRE_BROWSER=1` fails it."""

from __future__ import annotations

import os
from collections.abc import Iterator
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Error, Page, Route, sync_playwright

from residentialapps.supportlogs import sample_support as sample
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
        "label.choice", has_text=label
    ).first.click()


def test_save_waits_for_student_duration_and_type(page: Page) -> None:
    page.goto(f"{ORIGIN}/log")
    save = page.locator("#save")
    assert save.is_disabled()
    choose(page, "Student", "Hana Rahim")  # a favorite, shared by Priya Raman
    choose(page, "Duration", "15 min")
    assert save.is_disabled()
    choose(page, "Type", "Practical support")
    assert save.is_enabled()
    save.click()
    page.wait_for_url("**/log/saved?**")
    sent = parse_qs(urlparse(page.url).query)
    assert (
        sent["student"] == ["S-08"]
        and sent["duration"] == ["15 min"]
        and sent["type"] == ["Practical support"]
    )
    assert "note" not in sent


def test_who_started_it_is_asked_of_every_type(page: Page) -> None:
    """Author, 2026-11-06: no type says who started it any longer, so the
    question shows whatever the type, and its answer travels."""
    page.goto(f"{ORIGIN}/log?student=S-02")
    page.locator("details.more > summary", has_text="Add details").click()
    choose(page, "Duration", "15 min")
    for kind in sample.ENCOUNTER_TYPES:
        choose(page, "Type", kind)
        assert page.locator("#who").is_visible(), kind
    choose(page, "Who started it?", "Staff")
    page.locator("#save").click()
    page.wait_for_url("**/log/saved?**")
    assert parse_qs(urlparse(page.url).query)["started"] == ["Staff"]


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
    choose(page, "Student", "Clara Tan")
    assert page.locator("#on-plan").text_content() == "On your plans: weekly, set by Sam Lee."
    assert page.locator("#cadence-field").is_hidden()
    choose(page, "Student", "Hana Rahim")  # Priya Raman's student: no plan of Daniel's
    assert page.locator("#on-plan").is_hidden() and page.locator("#add-follow").is_visible()
    assert (
        page.locator("#cadence-field").is_visible()
        and page.locator("#cadence").input_value() == "No fixed cadence"
    )


def test_marking_a_safety_concern_carries_the_choices(page: Page) -> None:
    page.goto(f"{ORIGIN}/log")
    choose(page, "Student", "Hana Rahim")
    choose(page, "Duration", "15 min")
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
    assert "A safety flag is raised for Hana Rahim" in page.content()


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
    assert (
        page.locator("#dl-staff").get_attribute("aria-label") == "Remove Grace Ho from Staff"
    )  # the label names it
    assert staff_box(page).locator(".token-input").is_hidden()
    page.locator("#dl-staff").click()
    assert staff_box(page).locator(".token").count() == 0
    assert page.locator("#dl-staff").evaluate(
        "el => el.classList.contains('token-input') && document.activeElement === el"
    )


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
    assert (
        page.locator("#dl-staff").evaluate("el => el.validationMessage").startswith("Choose a name")
    )
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


def test_a_student_on_follow_ups_shows_them_in_the_browser(page: Page) -> None:
    """The informal plan path the favorites no longer reach by a chip
    (cold read, rung 12): arriving for Aiden Chen shows his follow-ups."""
    page.goto(f"{ORIGIN}/log?student=S-01")
    page.locator("details.more > summary", has_text="Add details").click()
    assert page.locator("#on-plan").text_content() == "On your follow-ups: weekly."
    assert page.locator("#add-follow").is_hidden()
    assert page.locator("#cadence").input_value() == "Weekly"


def test_students_filter_shows_plans_or_follow_ups_and_is_kept(page: Page) -> None:
    """Students' filter (1D rung 13, author, 2026-11-07): Plans and
    Following narrow My students and its count; the choice survives a
    reload, kept in the browser."""
    page.goto(f"{ORIGIN}/students/")
    mine = page.locator("[data-students-list] > li:visible a.strong")
    count = page.locator("[data-students-count]")
    assert mine.count() == 7 and count.inner_text() == "7"
    add = page.locator("[data-students-add]")
    assert add.is_visible()
    page.get_by_role("button", name="Plans", exact=True).click()
    assert mine.all_inner_texts() == ["Clara Tan", "Dev Menon"] and count.inner_text() == "2"
    assert not add.is_visible()  # under All and Following only
    page.get_by_role("button", name="Following", exact=True).click()
    assert mine.all_inner_texts() == ["Aiden Chen", "Elena Park"]
    assert add.is_visible()
    page.reload()
    assert mine.all_inner_texts() == ["Aiden Chen", "Elena Park"]
    assert (
        page.get_by_role("button", name="Following", exact=True).get_attribute("aria-pressed")
        == "true"
    )
    page.get_by_role("button", name="All", exact=True).click()
    assert mine.count() == 7
    page.evaluate("localStorage.setItem('supportlogs-students-show', 'nonsense')")
    page.reload()
    assert mine.count() == 7  # an unknown stored choice reads as All


def test_students_filter_says_none_when_nothing_matches(page: Page) -> None:
    """Priya Raman has a follow-up and no formal plan: Plans shows None."""
    page.goto(f"{ORIGIN}/students/?as=Priya%20Raman")
    page.get_by_role("button", name="Plans", exact=True).click()
    assert page.locator("[data-students-list] > li:visible").count() == 0
    assert page.locator("[data-students-none]").is_visible()
    assert page.locator("[data-students-count]").inner_text() == "0"
    page.get_by_role("button", name="Following", exact=True).click()
    assert not page.locator("[data-students-none]").is_visible()


def test_text_boxes_resize_vertically_only(page: Page) -> None:
    """Author, 2026-11-07: every Residential text box is dragged taller,
    never wider; the rule is the shared stylesheet's, so Support Logs'
    two boxes stand for Residential Ops' six too."""
    for path, box in (("/log", "#note"), ("/consultation/?as=Hui%20Min%20Goh", "#emails")):
        page.goto(f"{ORIGIN}{path}")
        resize = page.locator(box).evaluate("el => getComputedStyle(el).resize")
        assert resize == "vertical", (path, resize)


def test_a_withheld_name_shows_and_hides_again(page: Page) -> None:
    """Overview's withheld name (author, 2026-11-07): Show name opens it in
    place, its control stays and reads Hide name, and closes it again."""
    page.goto(f"{ORIGIN}/overview/?as=Sam%20Lee")
    page.locator("#across-h").click()  # the card opens first (author, 2026-11-08)
    row = page.locator("#across-table details.reveal").first
    summary = row.locator("summary")
    name = row.locator("> .strong")
    assert not name.is_visible() and "Show name" in summary.inner_text()
    summary.click()
    first = next(
        r["student"].name
        for r in sample.students_across_staff()
        if not sample.named_on_overview(r["student"].id)
    )
    assert name.is_visible() and name.inner_text() == first
    assert summary.is_visible() and "Hide name" in summary.inner_text()
    summary.click()
    assert not name.is_visible()


def test_overview_cards_of_names_stay_folded_until_opened(page: Page) -> None:
    """Author, 2026-11-08: on a senior's Overview every card that shows
    names starts closed, its heading the control; the safety flags banner
    and the count tiles stay open."""
    page.goto(f"{ORIGIN}/overview/?as=Sam%20Lee")
    for heading, inside in (
        ("#support-h", "#support-table"),
        ("#across-h", "#across-table"),
        ("#who-h", "section:has(#who-h) dl.kv"),
        ("#refs-h", "section:has(#refs-h) ul.items"),
        ("#plans-h", "section:has(#plans-h) ul.items"),
    ):
        assert not page.locator(inside).is_visible(), heading
        page.locator(heading).click()
        assert page.locator(inside).is_visible(), heading
    assert page.locator("#flags-h").is_visible() and page.locator(".tiles").is_visible()


def test_three_columns_of_340_and_cards_span_two(page: Page) -> None:
    """Author, 2026-11-08: at most three columns of at least 340 px, 24 px
    apart. Three from 1116 px wide: a split's main column spans two and
    its side one, and a card on its own spans two. Two from 736 px (the
    page's margins are 16 px below 960): a card spans the page. One
    below."""
    measure = """() => {
      const s = document.querySelector('.split');
      const m = s.querySelector('.main').getBoundingClientRect();
      const d = s.querySelector('.side').getBoundingClientRect();
      const card = document.querySelector('section:has(#plans-h)').getBoundingClientRect();
      const pg = document.querySelector('.page'), cs = getComputedStyle(pg);
      const content = pg.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
      return [Math.round(content), Math.round(m.width), Math.round(d.width),
              m.top === d.top, Math.round(card.width)];
    }"""
    for width, expect in (
        (1280, (1184, 781, 379, True, 781)),
        (1116, (1068, 704, 340, True, 704)),
        (1115, (1067, 703, 340, True, 1067)),
        (736, (704, 340, 340, True, 704)),
        (735, (703, 703, 703, False, 703)),
    ):
        page.set_viewport_size({"width": width, "height": 900})
        page.goto(f"{ORIGIN}/overview/?as=Sam%20Lee")
        assert tuple(page.evaluate(measure)) == expect, width


def test_students_teams_filter_shows_the_team_and_hides_add(page: Page) -> None:
    """Rung 5: Teams shows the team's student alone, with no Add a student
    to follow up, and is kept across a reload."""
    page.goto(f"{ORIGIN}/students/")
    mine = page.locator("[data-students-list] > li:visible a.strong")
    add = page.locator("[data-students-add]")
    page.get_by_role("button", name="Teams", exact=True).click()
    assert mine.all_inner_texts() == ["Hana Rahim"]
    assert page.locator("[data-students-count]").inner_text() == "1"
    assert not add.is_visible()
    page.reload()
    assert mine.all_inner_texts() == ["Hana Rahim"] and not add.is_visible()
    page.get_by_role("button", name="All", exact=True).click()
