"""A new exercise in a real Chromium (segment AD1N rung 2; a row since
AD2G): *New exercise*, a name, the blank draft's Home; Details saved into
it, kept across a reload. Skips without a Chromium build, as
`test_form_browser.py`'s."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Error, Page, Route, sync_playwright

from applydesk.tests._host import host_with
from applydesk.tests.test_form_browser import ORIGIN

LOBBY = f"{ORIGIN}/applydesk/operator/exercises"


@pytest.fixture
def page() -> Iterator[Page]:
    """As `test_form_browser.py`'s, but every method served, with its body
    and redirects."""
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
        assert errors == [], f"page errors: {errors}"


def test_new_exercise_to_its_home_then_details_saved(page: Page) -> None:
    page.goto(LOBBY)
    page.get_by_role("button", name="New exercise").click()
    page.locator("[data-nx-name]").fill("Browser Bursary 2027")
    page.get_by_role("button", name="Create").click()
    page.wait_for_url(f"{LOBBY}/*")
    assert page.locator("h1").inner_text().startswith("Browser Bursary 2027")
    assert page.locator("[data-scratch-note]").count() == 0
    card = page.locator("[data-details]")
    card.locator("[data-dt-lock]").click()
    card.locator('[data-dt="code"]').fill("BB-27")
    card.locator('[data-dt="description"]').fill("A bursary set up in the browser.")
    card.locator('[data-dt-act="lock"]').click()
    said = card.locator("[data-dt-said]")
    said.filter(has_text="Saved.").wait_for()
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
    assert row.count() == 1 and row.get_by_role("button", name="Discard").count() == 0


def test_form_saved_into_a_new_exercise_survives_a_reload(page: Page) -> None:
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
    # The new question is keyed on saving (segment AD2D), so the page
    # reloads to hold its key, and says it saved once back.
    with page.expect_navigation():
        page.locator("[data-fb-save]").click()
    said = page.locator("[data-fb-said]")
    said.filter(has_text="Saved").wait_for()
    assert said.inner_text() == "Saved.", said.inner_text()
    assert page.locator("[data-unsaved]").is_hidden()
    assert page.locator('#fb-cards > .fc[data-kind="field"]').get_attribute("data-key") == "q1"
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


def test_process_saved_into_a_new_exercise_survives_a_reload(page: Page) -> None:
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
    first.locator('[data-pc-act="form"]').click()  # ruling 84: the first item before gates
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
    for v in ("Awarded", "Not awarded"):
        outcome.locator('[data-pc-act="add-value"]').click()
        outcome.locator('[data-pc="value"]').last.fill(v)
    outcome.locator('[data-rel="applicants-email"]').check()
    # Gates are renumbered on saving, so the page reloads to hold the keys.
    with page.expect_navigation():
        page.locator("[data-fb-save]").click()
    said = page.locator("[data-fb-said]")
    said.filter(has_text="Saved").wait_for()
    assert said.inner_text() == "Saved.", said.inner_text()
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
    rows = outcome.locator('[data-pc="value"]')
    assert [rows.nth(i).input_value() for i in range(rows.count())] == ["Awarded", "Not awarded"]
    assert outcome.locator("li").first.get_attribute("data-value-key")
    assert outcome.locator('[data-rel="applicants-email"]').is_checked()
    page.goto(home + "/emails")
    assert "Award" in page.locator("main").inner_text()


def test_panels_saved_into_a_new_exercise_survive_a_reload(page: Page) -> None:
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
    page.locator("[data-fb-said]").filter(has_text="Saved.").wait_for()
    assert page.locator("[data-pn-kept]").is_hidden()
    assert page.locator('th[data-panel="panel-1"]').inner_text().startswith("Readers")
    # Saved again, it keeps its key.
    with page.expect_navigation():
        page.locator("[data-fb-save]").click()
    page.locator("[data-fb-said]").filter(has_text="Saved.").wait_for()
    assert page.locator('th[data-panel="panel-1"]').inner_text().startswith("Readers")
    assert page.locator("[data-pn-row]").count() == 1
    assert who[1] in page.locator("[data-pn-row]").first.inner_text()
    page.goto(home + "/process")
    pools = page.evaluate("JSON.parse(document.getElementById('pc-pools').textContent)")
    assert pools["panel-1"]["name"] == "Readers", pools


def test_an_email_saved_into_a_new_exercise_survives_a_reload(page: Page) -> None:
    """Rung 6: the receipt a new exercise owes, started from the default,
    saved, written after a reload; a tag of another kind refused."""
    page.goto(LOBBY)
    page.get_by_role("button", name="New exercise").click()
    page.locator("[data-nx-name]").fill("Emails Walkthrough")
    page.get_by_role("button", name="Create").click()
    page.wait_for_url(f"{LOBBY}/*")
    home = page.url
    # A new exercise starts blank (segment AD2K): the receipt comes with a Form.
    page.goto(home + "/process")
    page.locator('[data-pc-act="form"]').first.click()
    page.locator("[data-fb-save]").click()
    page.locator("[data-unsaved]").wait_for(state="hidden")
    page.goto(home + "/emails")
    card = page.locator('[data-em-item="receipt"]')
    assert card.locator("[data-em-chip]").text_content() == "Owed"
    card.locator('[data-em-act="reset"]').click()
    card.locator('[data-em-act="save"]').click()
    card.locator("[data-em-said]").filter(has_text="Saved.").wait_for()
    assert card.locator("[data-em-chip]").text_content() == "Written"
    page.reload()
    card = page.locator('[data-em-item="receipt"]')
    assert card.locator("[data-em-chip]").text_content() == "Written"
    assert card.locator("[data-em-subject]").input_value().startswith("$exercise_name")
    assert card.locator('[data-em-act="save"]').is_disabled()


def test_gates_and_outcomes_appear_once_a_first_item_is_added(page: Page) -> None:
    """Ruling 84: a new exercise's stage offers only +Form and +Create
    dossiers; adding either brings +Gate and +Outcome."""
    page.goto(LOBBY)
    page.get_by_role("button", name="New exercise").click()
    page.locator("[data-nx-name]").fill("First Item Walkthrough")
    page.get_by_role("button", name="Create").click()
    page.wait_for_url(f"{LOBBY}/*")
    page.goto(page.url + "/process")
    adds = page.locator("#pc-cards .pc-adds").first
    assert adds.locator('[data-pc-act="gate"]').is_hidden()
    assert adds.locator('[data-pc-act="outcome"]').is_hidden()
    adds.locator('[data-pc-act="candidates"]').click()
    assert adds.locator('[data-pc-act="gate"]').is_visible()
    assert adds.locator('[data-pc-act="outcome"]').is_visible()


def test_who_may_apply_follows_create_dossiers(page: Page) -> None:
    """Ruling 84: a Form after Create dossiers shows Dossiers, locked;
    removing Create dossiers gives the choice back, Dossiers greyed out."""
    page.goto(LOBBY)
    page.get_by_role("button", name="New exercise").click()
    page.locator("[data-nx-name]").fill("Who May Apply Walkthrough")
    page.get_by_role("button", name="Create").click()
    page.wait_for_url(f"{LOBBY}/*")
    page.goto(page.url + "/process")
    stage = page.locator("#pc-cards > .fc").first
    stage.locator('[data-pc-act="candidates"]').click()
    stage.locator('[data-pc-act="form"]').click()
    who = stage.locator('[data-rel="who-may-apply"]')
    assert who.input_value() == "dossiers" and who.is_disabled()
    stage.locator('[data-pc-act="remove-candidates"]').click()
    assert who.is_enabled() and who.input_value() == "open"
    assert who.evaluate("s => s.querySelector('option[value=dossiers]').disabled")
    who.select_option("invitation")
    assert who.input_value() == "invitation"


def test_invitees_show_with_their_choice_and_are_added(page: Page) -> None:
    """Ruling 84: choosing Invitees shows the Form's invite list. Names or
    emails typed with commas become pills when found, one not found stays
    as typed; Add invites each pill, listed under the folding count
    (author, 2026-11-27)."""
    page.set_viewport_size({"width": 1400, "height": 900})
    page.goto(LOBBY)
    page.get_by_role("button", name="New exercise").click()
    page.locator("[data-nx-name]").fill("Invitees Walkthrough")
    page.get_by_role("button", name="Create").click()
    page.wait_for_url(f"{LOBBY}/*")
    page.goto(page.url + "/process")
    stage = page.locator("#pc-cards > .fc").first
    stage.locator('[data-pc-act="form"]').click()
    # Opens, Closes, Who may apply and Max dossiers per person: one row.
    form = stage.locator('.pc-item[data-item="form"]')
    tops = [
        form.locator(sel).bounding_box()
        for sel in (
            '[data-pc="item-from"]',
            '[data-pc="item-to"]',
            '[data-rel="who-may-apply"]',
            '[data-rel="per-person"]',
        )
    ]
    assert all(t is not None for t in tops)
    assert len({round(t["y"]) for t in tops if t}) == 1, tops
    rows = stage.locator("[data-invitees-row]")
    assert rows.is_hidden()
    stage.locator('[data-rel="who-may-apply"]').select_option("invitation")
    assert rows.is_visible()
    lst = rows.locator('[data-cand-live][data-cand-kind="invitees"]')
    entry = lst.locator("[data-cand-entry]")
    entry.fill("admin@example.edu, nobody.here@nowhere.example,")
    lst.locator("[data-cand-tokens] .token").first.wait_for()
    lst.locator("[data-cand-said]").filter(has_text="Not found").wait_for()
    assert lst.locator("[data-cand-tokens] .token").count() == 1
    assert "nobody.here@nowhere.example" in entry.input_value()
    lst.locator("[data-cand-add-all]").click()
    lst.locator("[data-cand-list] tr", has_text="admin@example.edu").wait_for()
    assert lst.locator("[data-cand-fold-n]").inner_text() == "Invitees (1)"
    assert lst.locator("[data-cand-tokens] .token").count() == 0


def test_an_invite_that_fails_keeps_its_pill(page: Page) -> None:
    """Codex on #4264: of a batch, a pill whose invite fails stays to be
    tried again and the line names it; the rest are invited."""
    import json

    from applydesk import db, people

    session = db.new_session()
    try:
        people.pending(session, "zed.pill@example.edu", None)
        session.commit()
    finally:
        session.close()
    page.goto(LOBBY)
    page.get_by_role("button", name="New exercise").click()
    page.locator("[data-nx-name]").fill("Failed Invite Walkthrough")
    page.get_by_role("button", name="Create").click()
    page.wait_for_url(f"{LOBBY}/*")
    page.goto(page.url + "/process")
    stage = page.locator("#pc-cards > .fc").first
    stage.locator('[data-pc-act="form"]').click()
    stage.locator('[data-rel="who-may-apply"]').select_option("invitation")
    lst = stage.locator('[data-cand-live][data-cand-kind="invitees"]')
    lst.locator("[data-cand-entry]").fill("admin@example.edu, zed.pill@example.edu,")
    pills = lst.locator("[data-cand-tokens] .token")
    pills.nth(1).wait_for()

    adds: list[str] = []

    def refuse_one(route: Route) -> None:
        # The first invite sent is refused; every other request goes on.
        if route.request.method == "POST":
            sent = json.loads(route.request.post_data or "{}")
            if sent.get("action") == "add":
                adds.append(str(sent))
                if len(adds) == 1:
                    route.fulfill(
                        status=400,
                        body=json.dumps({"error": "Refused for the test."}),
                        headers={"content-type": "application/json"},
                    )
                    return
        route.fallback()

    page.route("**/invitees", refuse_one)
    lst.locator("[data-cand-add-all]").click()
    lst.locator("[data-cand-said]").filter(has_text="Not invited").wait_for()
    assert pills.count() == 1
    assert "Refused for the test." in lst.locator("[data-cand-said]").inner_text()
    assert lst.locator("[data-cand-list] tbody tr").count() == 1


def test_a_name_waits_when_the_directory_is_down(page: Page) -> None:
    """Codex on #4264: with the directory unreachable, a name matching one
    person on record is not taken as them; it stays as typed and the line
    says to try again. An exact address still resolves."""
    import json

    page.goto(LOBBY)
    page.get_by_role("button", name="New exercise").click()
    page.locator("[data-nx-name]").fill("Directory Down Walkthrough")
    page.get_by_role("button", name="Create").click()
    page.wait_for_url(f"{LOBBY}/*")
    page.goto(page.url + "/process")
    stage = page.locator("#pc-cards > .fc").first
    stage.locator('[data-pc-act="form"]').click()
    stage.locator('[data-rel="who-may-apply"]').select_option("invitation")

    def down(route: Route) -> None:
        found = {
            "on_record": [{"id": 1, "name": "Ada Lim", "email": "ada.lim@example.edu"}],
            "directory": [],
            "directory_failed": True,
        }
        route.fulfill(
            status=200, body=json.dumps(found), headers={"content-type": "application/json"}
        )

    page.route("**/invitees/search?*", down)
    lst = stage.locator('[data-cand-live][data-cand-kind="invitees"]')
    entry = lst.locator("[data-cand-entry]")
    entry.fill("Ada,")
    lst.locator("[data-cand-said]").filter(has_text="could not be searched").wait_for()
    assert lst.locator("[data-cand-tokens] .token").count() == 0
    assert "Ada" in entry.input_value()
    entry.fill("ada.lim@example.edu,")
    lst.locator("[data-cand-tokens] .token").first.wait_for()


def test_a_stages_items_reorder_within_the_rules(page: Page) -> None:
    """Ruling 84: a stage's gates swap by their grips and save in that
    order; a move putting a gate before Create dossiers, or the outcome
    before a gate, is put back, saying why."""
    page.goto(LOBBY)
    page.get_by_role("button", name="New exercise").click()
    page.locator("[data-nx-name]").fill("Reorder Walkthrough")
    page.get_by_role("button", name="Create").click()
    page.wait_for_url(f"{LOBBY}/*")
    page.goto(page.url + "/process")
    stage = page.locator("#pc-cards > .fc").first
    if stage.locator("[data-fc-toggle]").get_attribute("aria-expanded") == "false":
        stage.locator("[data-fc-toggle]").click()
    stage.locator('[data-pc-act="candidates"]').click()
    for name in ("Screen", "Interview"):
        stage.locator('[data-pc-act="gate"]').click()
        stage.locator('.pc-item[data-item="gate"] [data-pc="item-name"]').last.fill(name)
    stage.locator('[data-pc-act="outcome"]').click()
    stage.locator('.pc-item[data-item="outcome"] [data-pc="item-name"]').fill("Offer")
    gates = stage.locator('.pc-item[data-item="gate"] [data-pc="item-name"]')
    said = stage.locator("[data-pc-move-said]")

    def kinds() -> list[str]:
        found = stage.locator(".pc-item")
        return [found.nth(i).get_attribute("data-item") or "" for i in range(found.count())]

    assert kinds() == ["candidates", "gate", "gate", "outcome"]
    stage.locator('.pc-item[data-item="gate"] [data-pi-grip]').nth(1).press("ArrowUp")
    assert [gates.nth(i).input_value() for i in range(2)] == ["Interview", "Screen"]
    assert (
        stage.locator('.pc-item[data-item="gate"] [data-pc-kicker]').first.inner_text() == "Gate 1"
    )
    assert said.is_hidden()
    # Above Create dossiers: put back, the reason on the stage.
    stage.locator('.pc-item[data-item="gate"] [data-pi-grip]').first.press("ArrowUp")
    assert kinds() == ["candidates", "gate", "gate", "outcome"]
    assert "Create dossiers comes before the gates" in said.inner_text()
    stage.locator('.pc-item[data-item="outcome"] [data-pi-grip]').press("ArrowUp")
    assert kinds()[-1] == "outcome"
    assert "The outcome comes last" in said.inner_text()
    # Dragged by the mouse, the outcome above a gate is put back too.
    grip = stage.locator('.pc-item[data-item="outcome"] [data-pi-grip]').bounding_box()
    over = stage.locator('.pc-item[data-item="gate"]').first.bounding_box()
    assert grip and over
    said.evaluate("e => { e.textContent = ''; e.hidden = true; }")
    page.mouse.move(grip["x"] + 4, grip["y"] + 4)
    page.mouse.down()
    page.mouse.move(over["x"] + 20, over["y"] + 4, steps=5)
    page.mouse.up()
    assert kinds()[-1] == "outcome"
    assert "The outcome comes last" in said.inner_text()
    with page.expect_navigation():
        page.locator("[data-fb-save]").click()
    page.locator("[data-fb-said]").filter(has_text="Saved").wait_for()
    stage = page.locator("#pc-cards > .fc").first
    names = stage.locator('.pc-item[data-item="gate"] [data-pc="item-name"]')
    assert [names.nth(i).input_value() for i in range(2)] == ["Interview", "Screen"]
