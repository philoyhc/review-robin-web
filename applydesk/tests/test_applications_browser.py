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

from applydesk import sample_data, stages
from applydesk.tests._host import host_with

ORIGIN = "http://applydesk.test"
PAGE = f"{ORIGIN}/applydesk/operator/exercises/wa9juxbc2t/dossiers"


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


def _unlock(page: Page) -> None:
    """Ruling 23: the table is a control surface, locked until Unlock."""
    page.locator("[data-ap-lock]").click()


def _row(page: Page, text: str) -> Locator:
    return page.locator("[data-row]", has_text=text).first


def test_a_gate_chip_cycles_and_the_count_follows(page: Page) -> None:
    page.goto(PAGE)
    _unlock(page)
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
    _unlock(page)
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
    _unlock(page)
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
    assert shown.inner_text() == "Showing 102 of 102"
    page.locator("[data-ap-search]").fill("chen.farouk")
    assert shown.inner_text() == "Showing 2 of 102"
    page.locator("[data-ap-which]").select_option("last")
    assert shown.inner_text() == "Showing 1 of 102"
    assert "Submitted" in (page.locator("[data-row]:visible").text_content() or "")
    page.locator("[data-ap-search]").fill("")
    page.locator("[data-ap-which]").select_option("all")
    page.locator("[data-ap-status]").select_option("Draft")
    assert shown.inner_text() == "Showing 7 of 102"


def test_ticked_rows_are_set_together(page: Page) -> None:
    page.goto(PAGE)
    _unlock(page)
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
    _unlock(page)
    row = _row(page, "aisha.bello")
    row.locator('[data-cell="o1"] select').select_option("Shortlisted")
    finalists = row.locator('[data-cell="o2"] select')
    assert finalists.input_value() == ""
    finalists.select_option("Finalist")
    assert row.locator('[data-cell="o2"] [data-ap-date]').inner_text() == "13 Nov"
    # A draft stays inert.
    assert _row(page, "wen.novak").locator('[data-cell="o2"] select').count() == 0


# --- Rung 3: Fill by rule… and Upload CSV, proposing before they apply ---
def test_a_csv_proposes_then_applies(page: Page) -> None:
    page.goto(PAGE)
    _unlock(page)
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
    page.locator("[data-ap-proposal]").wait_for(state="visible")  # read async
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
    _unlock(page)
    with page.expect_download() as got:
        page.locator("[data-ap-csv-down]").click()
    raw = got.value.path().read_text(encoding="utf-8")
    # A byte-order mark, so a spreadsheet reads it as UTF-8; no status is "-".
    assert raw.startswith("\ufeff")
    text = raw.removeprefix("\ufeff")
    lines = text.splitlines()
    assert "—" not in text
    assert lines[0].startswith("Application ID,Applicant,Email,Status,Peer Review,")
    assert len(lines) == 103
    # Uploaded back, it changes nothing and leaves nothing out.
    page.locator("[data-ap-csv]").set_input_files(
        files=[{"name": "applications.csv", "mimeType": "text/csv", "buffer": text.encode()}]
    )
    page.locator("[data-ap-proposal]").wait_for(state="visible")  # read async
    prop = page.locator("[data-ap-proposal]")
    assert "Nothing would change." in prop.inner_text()
    assert prop.locator("[data-ap-prop-skip] li").count() == 0


def test_apply_keeps_a_cell_changed_by_hand_since(page: Page) -> None:
    page.goto(PAGE)
    _unlock(page)
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
    page.locator("[data-ap-proposal]").wait_for(state="visible")  # read async
    prop = page.locator("[data-ap-proposal]")
    assert prop.locator("[data-ap-prop-rows] tr").count() == 1
    chip = _row(page, "kenji.russo").locator('[data-cell="g3"] [data-ap-adm]')
    chip.click()  # Not entered -> no status, by hand
    page.once("dialog", lambda d: d.accept())
    prop.locator("[data-ap-prop-apply]").click()
    assert chip.inner_text() == "—"
    # Focus returns to what opened the proposal.
    assert page.evaluate("document.activeElement.hasAttribute('data-ap-csv-open')")


def test_a_csv_giving_one_cell_two_values_leaves_it(page: Page) -> None:
    # Codex: two rows for one application and column were both proposed
    # against the same starting value, and Apply made only the first.
    page.goto(PAGE)
    _unlock(page)
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
    page.locator("[data-ap-proposal]").wait_for(state="visible")  # read async
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
    _unlock(page)
    body = "Application ID,Interview\n__proto__,Entered\nconstructor,Entered\n"
    page.locator("[data-ap-csv]").set_input_files(
        files=[{"name": "odd.csv", "mimeType": "text/csv", "buffer": body.encode()}]
    )
    page.locator("[data-ap-proposal]").wait_for(state="visible")  # read async
    prop = page.locator("[data-ap-proposal]")
    assert "Not in this exercise, ignored: __proto__, constructor." in prop.inner_text()


# --- Rung 6: rules set on Setup, applied here, a hand overrides (author,
# 2026-11-13) ---
def _apply_rules(page: Page, *, only_undecided: bool = True, replace_hand: bool = False) -> Locator:
    rule = page.locator("[data-ap-rule]")
    if rule.is_hidden():
        page.locator("[data-ap-rule-open]").click()
    rule.locator("[data-ap-rule-pending]").set_checked(only_undecided)
    rule.locator("[data-ap-rule-hand]").set_checked(replace_hand)
    rule.locator("[data-ap-rule-go]").click()
    return page.locator("[data-ap-proposal]")


def test_each_column_shows_its_rule_from_setup(page: Page) -> None:
    page.goto(PAGE)
    assert (
        "Rule: Combined ≥ 4.2 → Shortlisted, else Not shortlisted"
        in page.locator('th[data-col="o1"]').inner_text()
    )
    assert (
        "Rule: Shortlist for interview is Shortlisted → Entered"
        in page.locator('th[data-col="g3"]').inner_text()
    )
    assert "Decided by hand" in page.locator('th[data-col="o3"]').inner_text()
    # No rule is built on this page.
    assert page.locator("[data-ap-rule] select").count() == 0


def test_apply_rules_proposes_in_column_order_and_waits_on_the_undecided(page: Page) -> None:
    page.goto(PAGE)
    _unlock(page)
    prop = _apply_rules(page)
    text = prop.inner_text()
    # The two still waiting on peer reviews: no combined result yet.
    assert "Shortlist for interview: 2 applications cannot be judged yet" in text
    # The interview waits on their shortlist rather than turning them away.
    assert "Interview: 2 applications cannot be judged yet" in text
    rows = prop.locator("[data-ap-prop-rows] tr").all_inner_texts()
    # Mid-stage (ruling 29): the three shortlisted still to be let in are
    # entered; no one is judged for Finalists, the interview not yet run.
    interview = [r for r in rows if "\tInterview\t" in r]
    assert len(interview) == 3 and all("Entered" in r for r in interview)
    assert not [r for r in rows if "\tFinalists\t" in r]
    prop.locator("[data-ap-prop-apply]").click()
    assert _count(page, "g3").startswith("27 entered")


def _set_rule(page: Page, key: str, rule: dict[str, object]) -> None:
    """A rule set on a column's header, as Process will: the sample has no
    branched rule until AD1H rung 6."""
    page.evaluate(
        '([k, r]) => { document.querySelector(`th[data-col="${k}"]`).dataset.rule ='
        " JSON.stringify(r); }",
        [key, rule],
    )


def _by_answer() -> dict[str, list[stages.Row]]:
    """The model exercise's reached rows (submitted, entered at Peer
    Review), grouped by their answer to *Field of study*."""
    groups: dict[str, list[stages.Row]] = {}
    for r in stages.plan_of("wa9juxbc2t").rows:
        if r.application.state == "Submitted" and r.cells["g1"].value == "Entered":
            answer = sample_data.answers("wa9juxbc2t", r.application)["Field of study"]
            groups.setdefault(answer, []).append(r)
    return groups


def test_a_branched_rule_takes_a_form_answer_and_the_best_n(page: Page) -> None:
    """Ruling 30: a rule's branches in order, the first holding deciding;
    a form answer; the best N among those its branch reaches, ties at the
    cut all taken and said so."""
    groups = _by_answer()
    # A field whose every dossier has its rating in, so its ranking runs.
    field, rows = next(
        (f, rs) for f, rs in groups.items() if all(r.cells["g1"].result is not None for r in rs)
    )
    results = sorted((r.cells["g1"].result or 0 for r in rows), reverse=True)
    n = next(i for i in range(2, len(results)) if results[i - 1] == results[i])  # a tie at the cut
    cut = results[n - 1]
    page.goto(PAGE)
    _unlock(page)
    _set_rule(
        page,
        "o1",
        {
            "when": [["form", "Field of study", "is", field], ["top", "g1.r1", "le", str(n)]],
            "then": "Shortlisted",
            "otherwise": "Not shortlisted",
            "more": [{"when": [["res", "g2.r1", "ge", "4.5"]], "then": "Shortlisted"}],
        },
    )
    prop = _apply_rules(page, only_undecided=False)
    taken = sum(1 for x in results if x >= cut)
    assert taken > n and f"Shortlist for interview: {taken} at the cut of {n}: tied." in (
        prop.inner_text()
    )
    prop.locator("[data-ap-prop-apply]").click()
    best = {r.application.public_id for r in rows if (r.cells["g1"].result or 0) >= cut}
    for r in (r for rs in groups.values() for r in rs):
        i = r.application.public_id
        if r.cells["g1"].result is None:
            continue  # its peer reviews still coming: waits
        got = _row(page, i).locator('[data-cell="o1"] select').get_attribute("data-v")
        g2 = r.cells["g2"].result or 0
        want = "Shortlisted" if i in best or g2 >= 4.5 else "Not shortlisted"
        assert got == want, i


def test_the_best_n_waits_while_one_it_could_rank_is_not_in(page: Page) -> None:
    """The cold read on rungs 2-3: a dossier whose rating is still coming
    could outrank the rest, so the ranking waits for it, not for one
    dossier but for the whole branch; the next branch still decides
    those the first does not reach."""
    groups = _by_answer()
    field, rows = next(
        (f, rs) for f, rs in groups.items() if any(r.cells["g1"].result is None for r in rs)
    )
    page.goto(PAGE)
    _unlock(page)
    _set_rule(
        page,
        "o1",
        {
            # The other condition first: a rating still coming waits there too.
            "when": [
                ["res", "g2.r1", "ge", "0"],
                ["form", "Field of study", "is", field],
                ["top", "g1.r1", "le", "3"],
            ],
            "then": "Shortlisted",
            "otherwise": "Not shortlisted",
        },
    )
    prop = _apply_rules(page, only_undecided=False)
    text = prop.inner_text()
    assert f"Shortlist for interview: {len(rows)} applications cannot be judged yet" in text
    proposed = [
        p
        for p in prop.locator("[data-ap-prop-rows] tr").all_inner_texts()
        if "\tShortlist for interview\t" in p
    ]
    ids = {r.application.public_id for r in rows}
    assert not [p for p in proposed if any(i in p for i in ids)]
    # Elsewhere the rule decides: every other field's shortlisted turn Not.
    assert proposed and all(p.endswith("Not shortlisted") for p in proposed)


def test_a_cell_set_by_hand_is_marked_and_kept(page: Page) -> None:
    page.goto(PAGE)
    _unlock(page)
    hand = page.locator('[data-row] td[data-cell="g1"][data-hand]')
    assert hand.count() == 1 and "Set by hand" in hand.inner_text()
    who = hand.locator("xpath=ancestor::tr").locator(".ap-id code").inner_text()
    prop = _apply_rules(page, only_undecided=False)
    rows = prop.locator("[data-ap-prop-rows] tr").all_inner_texts()
    assert not [r for r in rows if who in r]
    prop.locator("[data-ap-prop-cancel]").click()
    prop = _apply_rules(page, only_undecided=False, replace_hand=True)
    rows = prop.locator("[data-ap-prop-rows] tr").all_inner_texts()
    assert [r for r in rows if who in r and "Peer Review" in r]
    prop.locator("[data-ap-prop-apply]").click()
    cell = page.locator(f'[data-row]:has(code:text-is("{who}")) td[data-cell="g1"]')
    assert cell.get_attribute("data-hand") is None
    # A change by hand marks the cell.
    cell.locator("[data-ap-adm]").click()
    assert cell.get_attribute("data-hand") == ""


def test_a_gate_rule_takes_each_applicant_s_last_submitted(page: Page) -> None:
    page.goto(PAGE)
    earlier = page.locator('[data-row][data-rank="2"]')
    assert earlier.count() == 1
    assert earlier.locator('[data-cell="g1"] [data-ap-adm]').inner_text() == "Not entered"
    assert page.locator('[data-row][data-rank="1"]').count() >= 80


def test_the_page_shows_each_outcome_s_combined_result_and_weights(page: Page) -> None:
    from applydesk import stages

    page.goto(PAGE)
    _unlock(page)
    head = page.locator('th[data-col="o1"]').inner_text()
    # Each weight names a gate's result (ruling 21).
    assert "Rating at Peer Review 30% · Score at Faculty Panel Review 70%" in head
    plan = stages.plan_of("wa9juxbc2t")
    o1 = next(c for c in plan.columns if c.key == "o1")
    assert isinstance(o1, stages.Outcome)
    shown = page.evaluate(
        """() => Array.from(document.querySelectorAll('[data-row]')).map(r => [
            r.querySelector('.ap-id code').textContent,
            (r.querySelector('[data-cell="o1"] [data-ap-comb]') || {}).textContent || ""])"""
    )
    by_id = dict(shown)
    for r in plan.rows:
        if r.application.state == "Draft":
            continue
        want = stages.combined(r, o1)
        assert by_id[r.application.public_id] == ("" if want is None else f"Combined {want:.2f}"), (
            r.application.public_id
        )
    # A hand change re-weighs it: Peer Review not entered leaves the score.
    first = next(r for r in plan.rows if r.cells["g2"].result is not None)
    row = _row(page, first.application.public_id)
    chip = row.locator('[data-cell="g1"] [data-ap-adm]')
    while chip.inner_text() != "Not entered":
        chip.click()
    assert (
        row.locator('[data-cell="o1"] [data-ap-comb]').inner_text()
        == f"Combined {first.cells['g2'].result:.2f}"
    )


def test_the_sample_follows_its_rules(page: Page) -> None:
    """Every rule over every cell, decided or not, changes only what is
    still to decide; withdrawn and draft rows are never touched."""
    page.goto(PAGE)
    _unlock(page)
    prop = _apply_rules(page, only_undecided=False)
    rows = prop.locator("[data-ap-prop-rows] tr").all_inner_texts()
    assert rows
    for r in rows:
        assert r.split("\t")[3] in ("Pending", "—", ""), r
    withdrawn = page.locator('[data-row][data-status="Withdrawn"] .ap-id code').all_inner_texts()
    assert withdrawn and not [r for r in rows if r.split("\t")[0] in withdrawn]


def test_a_rule_proposal_is_dropped_when_the_table_changes(page: Page) -> None:
    page.goto(PAGE)
    _unlock(page)
    prop = _apply_rules(page)
    first = prop.locator("[data-ap-prop-rows] tr").first.inner_text().split("\t")
    messages: list[str] = []

    def answer(d: Dialog) -> None:
        messages.append(d.message)
        d.accept()

    page.on("dialog", answer)
    # The first proposal: one of the three still to be let into the Interview.
    row = _row(page, first[0])
    row.locator('[data-cell="g1"] [data-ap-adm]').click()  # the table changes
    prop.locator("[data-ap-prop-apply]").click()
    assert messages and "propose again" in messages[0]
    assert row.locator('[data-cell="g3"] [data-ap-adm]').get_attribute("data-v") == first[3]


def test_the_table_is_locked_until_unlocked_and_undo_puts_it_back(page: Page) -> None:
    """Ruling 23 (author, 2026-11-14): a control surface worked down its
    columns, so one lock for the whole table."""
    page.goto(PAGE)
    chip = _row(page, "kenji.russo").locator('[data-cell="g1"] [data-ap-adm]')
    lock = page.locator("[data-ap-lock]")
    assert chip.is_disabled() and page.locator("[data-ap-set]").is_disabled()
    assert page.locator("[data-ap-rule-open]").is_disabled()
    assert page.locator("[data-ap-release]").first.is_disabled()
    assert not page.locator("[data-ap-undo]").is_visible()
    # Ticks only choose rows: live while locked.
    tick = _row(page, "kenji.russo").locator("[data-ap-tick]")
    assert not tick.is_disabled()
    lock.click()
    assert lock.inner_text() == "Lock"
    assert page.locator("[data-ap-changes]").inner_text() == "No changes yet"
    before = chip.inner_text()
    chip.click()
    assert page.locator("[data-ap-changes]").inner_text() == "1 change since unlocked"
    # Leaving with a change pending asks first.
    assert page.evaluate(
        "() => { const e = new Event('beforeunload', {cancelable: true});"
        " window.dispatchEvent(e); return e.defaultPrevented; }"
    )
    page.locator("[data-ap-undo]").click()
    assert chip.inner_text() == before
    assert page.locator("[data-ap-changes]").inner_text() == "No changes yet"
    chip.click()
    after = chip.inner_text()
    lock.click()
    assert chip.is_disabled() and chip.inner_text() == after
    assert page.locator("[data-ap-said]").inner_text() == "1 change kept; the table is locked."


def test_the_lock_guards_rules_csv_and_open_proposals(page: Page) -> None:
    """Cold read on rung 7a: Propose and a proposal's Apply escaped the
    lock, and a CSV could reach a locked table."""
    page.goto(PAGE)
    assert page.locator("[data-ap-csv-open]").is_disabled()
    assert page.locator('[data-cell="o2"] select').first.is_disabled()
    _unlock(page)
    page.locator("[data-ap-rule-open]").click()
    assert page.locator("[data-ap-rule-go]").is_enabled()
    page.locator("[data-ap-rule-go]").click()
    assert page.locator("[data-ap-proposal]").is_visible()
    page.locator("[data-ap-lock]").click()
    assert not page.locator("[data-ap-proposal]").is_visible()
    assert not page.locator("[data-ap-rule]").is_visible()
    assert page.locator("[data-ap-rule-open]").get_attribute("aria-expanded") == "false"
    assert (
        page.locator("[data-ap-said]").inner_text() == "Locked. The open proposal was not applied."
    )
    assert page.evaluate("document.activeElement.matches('[data-ap-lock]')")
    # A CSV chosen while locked proposes nothing.
    page.locator("[data-ap-csv]").set_input_files(
        files=[
            {
                "name": "x.csv",
                "mimeType": "text/csv",
                "buffer": b"Application ID,Shortlist for interview\r\n",
            }
        ]
    )
    assert not page.locator("[data-ap-proposal]").is_visible()
    # No pending change, no leaving question.
    assert not page.evaluate(
        "() => { const e = new Event('beforeunload', {cancelable: true});"
        " window.dispatchEvent(e); return e.defaultPrevented; }"
    )


def test_a_date_alone_changed_is_still_a_change(page: Page) -> None:
    """Codex on #3892: Apply can put a value back with today's date; the
    count read only values and hand marks, so that went uncounted."""
    page.goto(PAGE)
    _unlock(page)
    page.evaluate("() => { document.querySelector('[data-ap-date]').textContent = 'Changed'; }")
    assert page.evaluate(
        "() => { const e = new Event('beforeunload', {cancelable: true});"
        " window.dispatchEvent(e); return e.defaultPrevented; }"
    )
