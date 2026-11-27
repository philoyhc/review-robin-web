"""The Candidates item in a real Chromium (ruling 77, segment AD2C rung
9): the search finds someone on record, Add lists them, Remove takes them
off, a CSV adds its good rows and lists the rest back; none of it marks
Process unsaved, since each change is kept as it is made."""

from __future__ import annotations

from dataclasses import replace

from playwright.sync_api import Locator, Page, Route

from applydesk import candidates, db, people, process_store, stages
from applydesk.tests.test_process_browser import ORIGIN
from applydesk.tests.test_process_browser import page as page  # the fixture, re-exported

MODEL = "wa9juxbc2t"


def _with_candidates() -> None:
    built = stages.plan_of(MODEL).stages
    held = (replace(built[0], candidates=True), *built[1:])
    session = db.new_session()
    try:
        process_store.save(session, MODEL, held, 0, None)
        people.pending(session, "zoe.candidate@example.edu", None)
        session.commit()
    finally:
        session.close()


def _pick(item: Locator, typed: str, email: str) -> None:
    """The add box (author, 2026-11-27: as Add invitees'): type, wait for
    the suggestion naming ``email`` under the box, then click it, making
    that account's pill; Add is enabled then."""
    entry = item.locator("[data-cand-entry]")
    entry.fill(typed)
    offer = item.locator("[data-tok-options] li", has_text=email)
    offer.wait_for()
    offer.click()
    assert item.locator("[data-tok-options]").is_hidden()
    assert item.locator("[data-cand-tokens] .token").count() == 1
    assert item.locator("[data-cand-add-all]").is_enabled()


def test_the_list_is_kept_as_it_is_changed(page: Page) -> None:
    _with_candidates()
    page.goto(f"{ORIGIN}/applydesk/operator/exercises/{MODEL}/process")
    item = page.locator('#pc-cards .pc-item[data-item="candidates"]')
    stage = page.locator("#pc-cards .pc").filter(
        has=page.locator('.pc-item[data-item="candidates"]')
    )
    if not stage.locator(".fc-body").first.is_visible():
        stage.locator("[data-fc-toggle]").first.click()
    if not item.locator("[data-cand-entry]").is_visible():
        item.locator("[data-pi-toggle]").click()
    _pick(item, "zoe.cand", "zoe.candidate@example.edu")
    item.locator("[data-cand-add-all]").click()
    # On Process the list is a count line (segment AD2N).
    sum_ = item.locator("[data-cand-sum]")
    sum_.filter(has_text="1 dossier for 1 person").wait_for()
    assert item.locator("[data-cand-count]").text_content() == "1 dossier"
    item.locator("[data-cand-file]").set_input_files(
        files=[
            {
                "name": "c.csv",
                "mimeType": "text/csv",
                "buffer": b"Email,Name\nyan@example.edu,Yan\nnope\n",
            }
        ]
    )
    sum_.filter(has_text="2 dossiers for 2 people").wait_for()
    assert "is not an email address" in item.locator("[data-cand-bad]").inner_text()
    assert item.locator("[data-cand-said]").inner_text() == "1 added."
    # Kept as made: Process's own Save has nothing unsaved.
    assert page.locator("[data-unsaved]").is_hidden()


def test_candidates_moved_to_another_stage_shows_the_list_as_it_stands(page: Page) -> None:
    """Codex on #4161: +Create dossiers on another stage draws the list as it
    now is, not as the page first loaded it."""
    built = stages.plan_of(MODEL).stages
    drafts = tuple(
        replace(st, status="Draft", candidates=(i == 0), form=False) for i, st in enumerate(built)
    )
    session = db.new_session()
    try:
        process_store.save(session, MODEL, drafts, 0, None)
        people.pending(session, "zoe.candidate@example.edu", None)
        session.commit()
    finally:
        session.close()
    page.goto(f"{ORIGIN}/applydesk/operator/exercises/{MODEL}/process")
    item = page.locator('#pc-cards .pc-item[data-item="candidates"]')
    first, other = page.locator("#pc-cards .pc").nth(0), page.locator("#pc-cards .pc").nth(1)
    for card in (first, other):
        if not card.locator(".fc-body").first.is_visible():
            card.locator("[data-fc-toggle]").first.click()
    if not item.locator("[data-cand-entry]").is_visible():
        item.locator("[data-pi-toggle]").click()
    _pick(item, "zoe.cand", "zoe.candidate@example.edu")
    item.locator("[data-cand-add-all]").click()
    item.locator("[data-cand-sum]").filter(has_text="1 dossier for 1 person").wait_for()
    first.locator('[data-pc-act="remove-candidates"]').click()
    other.locator('[data-pc-act="candidates"]').click()
    moved = other.locator('.pc-item[data-item="candidates"]')
    assert moved.locator("[data-cand-sum]").inner_text() == "1 dossier for 1 person"
    assert moved.locator("[data-cand-count]").text_content() == "1 dossier"


def test_changes_are_sent_one_at_a_time(page: Page) -> None:
    """Codex on #4161: two removals in quick succession are sent in turn, so
    an older answer cannot redraw over a newer list."""
    built = stages.plan_of(MODEL).stages
    session = db.new_session()
    try:
        process_store.save(
            session, MODEL, (replace(built[0], candidates=True), *built[1:]), 0, None
        )
        for address in ("one@example.edu", "two@example.edu"):
            candidates.add(session, MODEL, people.pending(session, address, None), "csv", None)
        session.commit()
    finally:
        session.close()
    seen: list[str] = []
    held: list[Route] = []

    def hold(route: Route) -> None:
        if route.request.method != "POST":
            route.fallback()  # to the fixture's server
            return
        seen.append(route.request.post_data or "")
        held.append(route)

    page.route("**/candidates", hold)
    # Removing is the Dossiers page's (segment AD2N), through the same script.
    page.goto(f"{ORIGIN}/applydesk/operator/exercises/{MODEL}/dossiers")
    item = page.locator('.cd-card [data-cand-live][data-cand-kind="candidates"]')
    item.locator("[data-cand-remove]").first.click()
    item.locator("[data-cand-remove]").last.click()
    page.wait_for_timeout(300)
    assert len(seen) == 1  # the second waits for the first's answer
    held.pop().fallback()
    page.wait_for_timeout(300)
    assert len(seen) == 2
    held.pop().fallback()
    item.locator("[data-cand-none]").wait_for()


def _drafts_holding_candidates() -> None:
    built = stages.plan_of(MODEL).stages
    drafts = tuple(
        replace(st, status="Draft", candidates=(i == 0), form=False) for i, st in enumerate(built)
    )
    session = db.new_session()
    try:
        process_store.save(session, MODEL, drafts, 0, None)
        people.pending(session, "zoe.candidate@example.edu", None)
        session.commit()
    finally:
        session.close()


def test_a_replicated_stage_leaves_candidates_behind(page: Page) -> None:
    """Codex on #4161: a stage's copy holds no Candidates, as it holds no
    form, so Replicate does not leave Process unsaveable."""
    _drafts_holding_candidates()
    page.goto(f"{ORIGIN}/applydesk/operator/exercises/{MODEL}/process")
    first = page.locator("#pc-cards .pc").nth(0)
    if not first.locator(".fc-body").first.is_visible():
        first.locator("[data-fc-toggle]").first.click()
    first.locator('[data-fc-act="replicate"]').click()
    assert page.locator('#pc-cards .pc-item[data-item="candidates"]').count() == 1
    assert (
        page.locator("#pc-cards .pc").nth(1).locator('.pc-item[data-item="candidates"]').count()
        == 0
    )


def test_an_answer_after_a_move_redraws_the_item_on_the_page(page: Page) -> None:
    """Codex on #4161: a change answered after Candidates moved stage is
    drawn on the item now on the page, not the one taken off."""
    _drafts_holding_candidates()
    held: list[Route] = []

    def hold(route: Route) -> None:
        if route.request.method == "POST":
            held.append(route)
        else:
            route.fallback()

    page.goto(f"{ORIGIN}/applydesk/operator/exercises/{MODEL}/process")
    item = page.locator('#pc-cards .pc-item[data-item="candidates"]')
    first, other = page.locator("#pc-cards .pc").nth(0), page.locator("#pc-cards .pc").nth(1)
    for card in (first, other):
        if not card.locator(".fc-body").first.is_visible():
            card.locator("[data-fc-toggle]").first.click()
    if not item.locator("[data-cand-entry]").is_visible():
        item.locator("[data-pi-toggle]").click()
    _pick(item, "zoe.cand", "zoe.candidate@example.edu")
    page.route("**/candidates", hold)
    item.locator("[data-cand-add-all]").click()
    page.wait_for_timeout(200)
    first.locator('[data-pc-act="remove-candidates"]').click()
    other.locator('[data-pc-act="candidates"]').click()
    held.pop().fallback()
    moved = other.locator('.pc-item[data-item="candidates"]')
    moved.locator("[data-cand-sum]").filter(has_text="1 dossier for 1 person").wait_for()
    assert moved.locator("[data-cand-count]").text_content() == "1 dossier"


def _open_item(page: Page) -> Locator:
    page.goto(f"{ORIGIN}/applydesk/operator/exercises/{MODEL}/process")
    item = page.locator('#pc-cards .pc-item[data-item="candidates"]')
    stage = page.locator("#pc-cards .pc").filter(
        has=page.locator('.pc-item[data-item="candidates"]')
    )
    if not stage.locator(".fc-body").first.is_visible():
        stage.locator("[data-fc-toggle]").first.click()
    if not item.locator("[data-cand-entry]").is_visible():
        item.locator("[data-pi-toggle]").click()
    return item


def test_a_directory_match_by_sign_in_name_becomes_its_pill(page: Page) -> None:
    """Codex on #4255, kept for the pill box: typed whole by its sign-in
    name, a directory account whose address differs is that account."""
    _with_candidates()
    page.route(
        "**/candidates/search*",
        lambda route: route.fulfill(
            json={
                "on_record": [],
                "directory": [
                    {
                        "object_id": "o-9",
                        "name": "Jane Tan",
                        "address": "jane.tan@example.edu",
                        "upn": "e0123456@u.edu",
                    }
                ],
                "directory_failed": False,
            }
        ),
    )
    item = _open_item(page)
    item.locator("[data-cand-entry]").fill("e0123456@u.edu,")
    token = item.locator("[data-cand-tokens] .token")
    token.wait_for()
    assert token.inner_text().startswith("Jane Tan")
    assert item.locator("[data-cand-add-all]").is_enabled()


def test_a_picked_suggestion_adds_its_own_account_not_an_address_twin(page: Page) -> None:
    """Codex on #4255, kept for the pill box: a person on record and a
    directory account sharing one address are two suggestions; the one
    picked is the one added. Typed whole, the address names two accounts,
    so it stays in the box."""
    _with_candidates()
    page.route(
        "**/candidates/search*",
        lambda route: route.fulfill(
            json={
                "on_record": [{"id": 4242, "name": "", "email": "sam@example.edu"}],
                "directory": [
                    {
                        "object_id": "o-7",
                        "name": "Sam Ng",
                        "address": "sam@example.edu",
                        "upn": "sam@example.edu",
                    }
                ],
                "directory_failed": False,
            }
        ),
    )
    sent: list[str] = []

    def hold(route: Route) -> None:
        sent.append(route.request.post_data or "")
        route.fulfill(json={"said": "Added.", "bad": [], "candidates": []})

    page.route("**/candidates", hold)
    item = _open_item(page)
    entry = item.locator("[data-cand-entry]")
    entry.fill("sam@example.edu,")
    item.locator("[data-cand-said]").filter(has_text="more than one match").wait_for()
    assert item.locator("[data-cand-tokens] .token").count() == 0
    entry.fill("sam@")
    item.locator("[data-tok-options] li", has_text="directory").wait_for()
    item.locator("[data-tok-options] li").filter(has_not_text="directory").click()
    item.locator("[data-cand-add-all]").click()
    item.locator("[data-cand-said]").filter(has_text="Added.").wait_for()
    assert '"person_id":4242' in sent[0] and "object_id" not in sent[0]
    assert '"count":1' in sent[0]


def test_every_match_is_suggested_and_the_keyboard_picks(page: Page) -> None:
    """Codex on #4255, kept for the pill box: a directory match found by a
    field the label does not show (a surname) is still suggested, and the
    keyboard picks it."""
    _with_candidates()
    page.route(
        "**/candidates/search*",
        lambda route: route.fulfill(
            json={
                "on_record": [],
                "directory": [
                    {
                        "object_id": "o-8",
                        "name": "Jane",
                        "address": "e0123456@example.edu",
                        "upn": "e0123456@example.edu",
                    }
                ],
                "directory_failed": False,
            }
        ),
    )
    item = _open_item(page)
    entry = item.locator("[data-cand-entry]")
    entry.fill("Tan")
    item.locator("[data-tok-options] li", has_text="e0123456@example.edu").wait_for()
    entry.press("ArrowDown")
    entry.press("Enter")
    assert item.locator("[data-cand-tokens] .token").inner_text().startswith("Jane")
    assert entry.input_value() == ""


def test_a_changed_entry_drops_the_last_highlight(page: Page) -> None:
    """Codex on #4255, kept for the pill box: a suggestion highlighted, then
    the entry changed and its search failing, Enter makes no pill from the
    old suggestion; the entry stays as typed."""
    _with_candidates()
    answered: list[int] = []

    def search(route: Route) -> None:
        answered.append(1)
        if len(answered) > 1:
            route.abort()
            return
        route.fulfill(
            json={
                "on_record": [{"id": 4243, "name": "Old Match", "email": "old@example.edu"}],
                "directory": [],
                "directory_failed": False,
            }
        )

    page.route("**/candidates/search*", search)
    item = _open_item(page)
    entry = item.locator("[data-cand-entry]")
    entry.fill("old")
    item.locator("[data-tok-options] li", has_text="old@example.edu").wait_for()
    entry.press("ArrowDown")
    entry.fill("newer")
    entry.press("Enter")
    item.locator("[data-cand-said]").filter(has_text="newer").wait_for()
    assert item.locator("[data-cand-tokens] .token").count() == 0
    assert entry.input_value() == "newer"


def test_add_makes_the_count_for_each_pill(page: Page) -> None:
    """Author, 2026-11-27: Create dossiers' box takes several people at
    once, as Add invitees' does; Add makes *Dossiers per person* for each."""
    _with_candidates()
    session = db.new_session()
    try:
        people.pending(session, "yan.candidate@example.edu", None)
        session.commit()
    finally:
        session.close()
    item = _open_item(page)
    entry = item.locator("[data-cand-entry]")
    entry.fill("zoe.candidate@example.edu, yan.candidate@example.edu,")
    item.locator("[data-cand-tokens] .token").nth(1).wait_for()
    item.locator("[data-cand-n]").fill("2")
    item.locator("[data-cand-add-all]").click()
    item.locator("[data-cand-sum]").filter(has_text="4 dossiers for 2 people").wait_for()
    assert item.locator("[data-cand-tokens] .token").count() == 0


def test_a_pill_being_saved_is_not_sent_again(page: Page) -> None:
    """Codex on #4266: a dossier added twice is two dossiers, so Add while a
    pill's save is pending sends only the pills not yet sent."""
    _with_candidates()
    sent: list[str] = []
    held: list[Route] = []

    def hold(route: Route) -> None:
        if route.request.method != "POST":
            route.fallback()
            return
        sent.append(route.request.post_data or "")
        held.append(route)

    item = _open_item(page)
    _pick(item, "zoe.cand", "zoe.candidate@example.edu")
    page.route("**/candidates", hold)
    item.locator("[data-cand-add-all]").click()
    page.wait_for_timeout(200)
    assert len(sent) == 1
    item.locator("[data-cand-entry]").fill("som")  # typing again enables Add
    assert item.locator("[data-cand-add-all]").is_enabled()
    item.locator("[data-cand-add-all]").click()
    page.wait_for_timeout(300)
    assert len(sent) == 1  # the pill being saved is not sent again
    held.pop().fallback()
    item.locator("[data-cand-sum]").filter(has_text="1 dossier for 1 person").wait_for()


def test_a_pill_already_in_the_box_is_not_suggested_again(page: Page) -> None:
    """Author, 2026-11-27: the suggestions leave out whoever is already a
    pill in the box, by account or by address."""
    _with_candidates()
    page.route(
        "**/candidates/search*",
        lambda route: route.fulfill(
            json={
                "on_record": [],
                "directory": [
                    {
                        "object_id": "o-1",
                        "name": "Aisha Bello",
                        "address": "aisha.bello@example.edu",
                        "upn": "aisha.bello@example.edu",
                    },
                    {
                        "object_id": "o-2",
                        "name": "Aisha Carter",
                        "address": "aisha.carter@example.edu",
                        "upn": "aisha.carter@example.edu",
                    },
                ],
                "directory_failed": False,
            }
        ),
    )
    item = _open_item(page)
    _pick(item, "aish", "aisha.bello@example.edu")
    item.locator("[data-cand-entry]").fill("aish")
    item.locator("[data-tok-options] li", has_text="aisha.carter@example.edu").wait_for()
    assert item.locator("[data-tok-options] li", has_text="aisha.bello").count() == 0
