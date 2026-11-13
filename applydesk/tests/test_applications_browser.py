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
    assert chip.inner_text() == "Entered"
    chip.click()
    assert chip.inner_text() == "Not entered"
    chip.click()
    assert chip.inner_text() == "—"
    assert (chip.get_attribute("aria-label") or "").endswith(": no status yet")
    n = int(before.split()[0])
    assert _count(page, "g1").startswith(f"{n - 1} entered · 1 to decide")
    chip.click()
    assert chip.inner_text() == "Entered" and _count(page, "g1") == before


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
    page.locator("[data-ap-set-val]").select_option("Entered")
    page.locator("[data-ap-set]").click()
    for who in ("aisha.bello", "kenji.russo"):
        assert _row(page, who).locator('[data-cell="g3"] [data-ap-adm]').inner_text() == "Entered"
    # A draft has entered nothing: it is left alone.
    assert _row(page, "wen.novak").locator('[data-cell="g3"] [data-ap-adm]').count() == 0


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


# --- Rung 3: Fill by rule… and Upload CSV, proposing before they apply ---
def test_a_rule_proposes_then_applies(page: Page) -> None:
    page.goto(PAGE)
    page.locator("[data-ap-rule-open]").click()
    rule = page.locator("[data-ap-rule]")
    rule.locator("[data-ap-rule-target]").select_option("o2")
    rule.locator("[data-ap-rule-then]").select_option("Finalist")
    rule.locator("[data-ap-rule-else]").select_option("Not a finalist")
    rule.locator("[data-ap-rule-source]").select_option("g2")
    rule.locator("[data-ap-rule-at]").fill("4.5")
    before = _count(page, "o2")
    rule.locator("[data-ap-rule-go]").click()
    prop = page.locator("[data-ap-proposal]")
    assert prop.is_visible()
    n = prop.locator("[data-ap-prop-rows] tr").count()
    assert n > 0
    assert "proposed. Nothing changes until Apply." in prop.inner_text()
    # Nothing has changed yet.
    assert _count(page, "o2") == before
    prop.locator("[data-ap-prop-apply]").click()
    assert not prop.is_visible()
    finalists = page.locator('[data-cell="o2"] select[data-v="Finalist"]').count()
    others = page.locator('[data-cell="o2"] select[data-v="Not a finalist"]').count()
    assert finalists + others == n and finalists > 0 and others > 0
    assert _count(page, "o2").startswith(f"{finalists} finalist")


def test_a_rule_names_what_it_cannot_judge(page: Page) -> None:
    page.goto(PAGE)
    page.locator("[data-ap-rule-open]").click()
    rule = page.locator("[data-ap-rule]")
    rule.locator("[data-ap-rule-target]").select_option("g2")
    rule.locator("[data-ap-rule-source]").select_option("g1")
    rule.locator("[data-ap-rule-at]").fill("3.5")
    rule.locator("[data-ap-rule-go]").click()
    prop = page.locator("[data-ap-proposal]")
    # The two applications still waiting on peer reviews are pending at
    # Gate 2 and have no finished Rating: named, not guessed.
    assert "2 applications have no finished Rating at Peer Review" in prop.inner_text()
    prop.locator("[data-ap-prop-cancel]").click()
    assert not prop.is_visible()


def test_a_csv_proposes_then_applies(page: Page) -> None:
    page.goto(PAGE)
    body = (
        "Application ID,Gate 3: Interview,Finalists,Mystery\n"
        "kenji-not-an-id,Entered,,\n"
        "h6zr2tdw9p,Entered,,x\n"
        "f2ps7nyh4k,Entered,,\n"
        "m3qx8vkt2n,Maybe,,\n"
    )
    shortlisted = page.locator('[data-row]:has([data-cell="o2"] select)').first
    sid = shortlisted.locator(".ap-id code").inner_text()
    body += f'{sid},,"Finalist",\n'
    page.locator("[data-ap-csv]").set_input_files(
        files=[{"name": "decisions.csv", "mimeType": "text/csv", "buffer": body.encode()}]
    )
    prop = page.locator("[data-ap-proposal]")
    assert "Upload CSV: decisions.csv" in prop.inner_text()
    text = prop.inner_text()
    assert "Column not on this page, ignored: Mystery." in text
    assert "Not in this exercise, ignored: kenji-not-an-id." in text
    assert 'm3qx8vkt2n: "Maybe" is not a value of Interview.' in text
    assert "f2ps7nyh4k: Interview cannot be set (a draft, or never admitted)." in text
    assert prop.locator("[data-ap-prop-rows] tr").count() == 2
    prop.locator("[data-ap-prop-apply]").click()
    assert (
        _row(page, "kenji.russo").locator('[data-cell="g3"] [data-ap-adm]').inner_text()
        == "Entered"
    )
    assert shortlisted.locator('[data-cell="o2"] select').input_value() == "Finalist"


def test_the_table_downloads_as_the_csv_an_upload_reads(page: Page) -> None:
    page.goto(PAGE)
    with page.expect_download() as got:
        page.locator("[data-ap-csv-down]").click()
    raw = got.value.path().read_text(encoding="utf-8")
    # A byte-order mark, so a spreadsheet reads it as UTF-8; no status is "-".
    assert raw.startswith("\ufeff")
    text = raw.removeprefix("\ufeff")
    lines = text.splitlines()
    assert "—" not in text
    assert lines[0].startswith("Application ID,Applicant,Email,Status,Peer Review,")
    assert len(lines) == 102
    # Uploaded back, it changes nothing and leaves nothing out.
    page.locator("[data-ap-csv]").set_input_files(
        files=[{"name": "applications.csv", "mimeType": "text/csv", "buffer": text.encode()}]
    )
    prop = page.locator("[data-ap-proposal]")
    assert "Nothing would change." in prop.inner_text()
    assert prop.locator("[data-ap-prop-skip] li").count() == 0


def test_apply_keeps_a_cell_changed_by_hand_since(page: Page) -> None:
    page.goto(PAGE)
    upper = "H6ZR2TDW9P"  # IDs match whatever their case
    page.locator("[data-ap-csv]").set_input_files(
        files=[
            {
                "name": "x.csv",
                "mimeType": "text/csv",
                "buffer": f"Application ID,Interview\n{upper},Entered\n".encode(),
            }
        ]
    )
    prop = page.locator("[data-ap-proposal]")
    assert prop.locator("[data-ap-prop-rows] tr").count() == 1
    chip = _row(page, "kenji.russo").locator('[data-cell="g3"] [data-ap-adm]')
    chip.click()  # Not entered -> no status, by hand
    page.once("dialog", lambda d: d.accept())
    prop.locator("[data-ap-prop-apply]").click()
    assert chip.inner_text() == "—"
    # Focus returns to what opened the proposal.
    assert page.evaluate("document.activeElement.hasAttribute('data-ap-csv-open')")


def test_a_rule_reads_only_an_earlier_gate(page: Page) -> None:
    page.goto(PAGE)
    page.locator("[data-ap-rule-open]").click()
    rule = page.locator("[data-ap-rule]")
    rule.locator("[data-ap-rule-target]").select_option("g1")
    # Nothing comes before Peer Review: no source, no Propose.
    assert rule.locator("[data-ap-rule-go]").is_disabled()
    rule.locator("[data-ap-rule-target]").select_option("g2")
    assert rule.locator("[data-ap-rule-source] option:not([disabled])").all_inner_texts() == [
        "Rating at Peer Review"
    ]


def test_a_csv_giving_one_cell_two_values_leaves_it(page: Page) -> None:
    # Codex: two rows for one application and column were both proposed
    # against the same starting value, and Apply made only the first.
    page.goto(PAGE)
    body = (
        "Application ID,Interview\n"
        "h6zr2tdw9p,Entered\n"
        "h6zr2tdw9p,-\n"
        "m3qx8vkt2n,Entered\n"
        "m3qx8vkt2n,entered\n"
    )
    page.locator("[data-ap-csv]").set_input_files(
        files=[{"name": "twice.csv", "mimeType": "text/csv", "buffer": body.encode()}]
    )
    prop = page.locator("[data-ap-proposal]")
    assert "h6zr2tdw9p: Interview given more than one value (Entered, —), left as is." in (
        prop.inner_text()
    )
    rows = prop.locator("[data-ap-prop-rows] tr")
    assert rows.count() == 1 and "m3qx8vkt2n" in rows.inner_text()
    prop.locator("[data-ap-prop-apply]").click()
    assert (
        _row(page, "aisha.bello").locator('[data-cell="g3"] [data-ap-adm]').inner_text()
        == "Entered"
    )
    assert _row(page, "kenji.russo").locator('[data-cell="g3"] [data-ap-adm]').inner_text() == (
        "Not entered"
    )


def test_a_csv_id_like_an_object_key_is_just_unknown(page: Page) -> None:
    # Codex: "__proto__" matched an inherited property and the upload threw.
    page.goto(PAGE)
    body = "Application ID,Interview\n__proto__,Entered\nconstructor,Entered\n"
    page.locator("[data-ap-csv]").set_input_files(
        files=[{"name": "odd.csv", "mimeType": "text/csv", "buffer": body.encode()}]
    )
    prop = page.locator("[data-ap-proposal]")
    assert "Not in this exercise, ignored: __proto__, constructor." in prop.inner_text()
