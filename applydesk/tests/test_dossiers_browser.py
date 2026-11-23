"""The Dossiers page in a real Chromium (segment AD1C, ruling 25): a gate's chip
cycles, an outcome is picked and dated, the counts follow, a release asks
to confirm, rows filter and are set in bulk. Without a Chromium build the
test skips, saying why; ``RRW_REQUIRE_BROWSER=1`` (set by CI) turns that
skip into a failure."""

from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import replace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Dialog, Error, Locator, Page, Route, sync_playwright

from applydesk import locks, sample_data, stages
from applydesk.tests._host import host_with


@pytest.fixture(autouse=True)
def _table_open(monkeypatch: pytest.MonkeyPatch) -> None:
    """These tests work the table: an opened gate's cells and a release
    waiting on its emails (segment AD1K) are opened here; the locks have
    tests of their own (``test_locks_browser.py``)."""
    monkeypatch.setattr(locks, "cells_lock", lambda e, g: locks.OPEN)
    monkeypatch.setattr(locks, "release_lock", lambda e, o: locks.OPEN)


#: What a test sets on the server's own plan, which *Apply rules* reads
#: (ruling 78): a column's rule, a gate cell's result, every result in.
_SERVER: dict[str, Any] = {}


@pytest.fixture(autouse=True)
def _server_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    rules: dict[str, stages.Rule | None] = {}
    results: dict[tuple[str, str], str | None] = {}
    _SERVER.clear()
    _SERVER.update(rules=rules, results=results, fill=False)
    real = stages.plan_of

    def cell(app: str, key: str, c: stages.Cell) -> stages.Cell:
        if _SERVER["fill"] and key in ("g1", "g2") and c.value == "Entered" and c.result is None:
            c = replace(c, result=1.0)
        if (app, key) in results:
            x = results[(app, key)]
            c = replace(c, result=None if x is None else float(x))
        return c

    def plan_of(exercise_id: str) -> stages.Plan:
        plan = real(exercise_id)
        if exercise_id != "wa9juxbc2t":
            return plan
        staged = tuple(
            replace(
                st,
                columns=tuple(
                    replace(c, rule=rules[c.key]) if c.key in rules else c for c in st.columns
                ),
            )
            for st in plan.stages
        )
        rows = tuple(
            stages.Row(
                r.application,
                {k: cell(r.application.public_id, k, c) for k, c in r.cells.items()},
            )
            for r in plan.rows
        )
        return stages.Plan(staged, rows)

    monkeypatch.setattr(stages, "plan_of", plan_of)


def _set_result(app: str, key: str, value: str | None) -> None:
    """A gate cell's first result as the server holds it (None: not in)."""
    _SERVER["results"][(app, key)] = value


def _fill_results() -> None:
    """Every gate result in, so no ranking waits on one (the sample keeps
    two dossiers' peer reviews coming)."""
    _SERVER["fill"] = True


def _rule_of(rule: dict[str, Any] | None) -> stages.Rule | None:
    if rule is None:
        return None

    def conds(when: list[list[str]]) -> tuple[tuple[str, str, str, str], ...]:
        return tuple((c[0], c[1], c[2], c[3]) for c in when)

    return stages.Rule(
        conds(rule["when"]),
        rule["then"],
        rule["otherwise"],
        tuple((conds(m["when"]), m["then"]) for m in rule.get("more", [])),
    )


ORIGIN = "http://applydesk.test"
PAGE = f"{ORIGIN}/applydesk/operator/exercises/wa9juxbc2t/dossiers"


@pytest.fixture
def page() -> Iterator[Page]:
    client = TestClient(host_with(("applydesk",))[0])

    def serve(route: Route) -> None:
        # A post too: *Apply rules* asks the server (ruling 78).
        response = client.request(
            route.request.method,
            route.request.url.removeprefix(ORIGIN),
            content=route.request.post_data_buffer,
            headers={**route.request.headers, "origin": ORIGIN},
        )
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
    assert chip.text_content() == "Entered"
    chip.click()
    assert chip.text_content() == "Not entered"
    chip.click()
    assert chip.text_content() == "—"
    assert (chip.get_attribute("aria-label") or "").endswith(": no status yet")
    n = int(before.split()[0])
    assert _count(page, "g1").startswith(f"{n - 1} entered · 1 to decide")
    chip.click()
    assert chip.text_content() == "Entered" and _count(page, "g1") == before


def test_an_outcome_is_picked_and_dated(page: Page) -> None:
    page.goto(PAGE)
    _unlock(page)
    row = _row(page, "kenji.russo")
    pick = row.locator('[data-cell="o2"] select')
    assert row.locator('[data-cell="o2"] [data-ap-date]').inner_text() == "Due 4 Dec"
    pick.select_option("Selected")
    assert (
        row.locator('[data-cell="o2"] [data-ap-date]').inner_text() == "17 Nov"
    )  # the clock's today (AD-40)
    assert _count(page, "o2").startswith("1 selected")
    pick.select_option("Pending")
    assert row.locator('[data-cell="o2"] [data-ap-date]').inner_text() == "Due 4 Dec"


def test_a_release_asks_first(page: Page) -> None:
    page.goto(PAGE)
    _unlock(page)
    switch = page.locator('[data-ap-release="Selection"]')
    answers: list[str] = []

    def dismiss(d: Dialog) -> None:
        answers.append(d.message)
        d.dismiss()

    page.once("dialog", dismiss)
    switch.click()
    assert "set on Process" in answers[0] and not switch.is_checked()
    # Its reached cells still undecided are named first (AD-21): the 55
    # Pending, not the 45 Shortlisting stopped (Codex).
    assert answers[0].startswith(
        "55 dossiers are still undecided or Pending here. Release Selection?"
    )
    page.once("dialog", lambda d: d.accept())
    switch.click()
    assert switch.is_checked()
    note = page.locator('th[data-col="o2"] [data-ap-relnote]').inner_text()
    assert note.startswith("17 Nov")


def test_search_status_and_last_applications_filter(page: Page) -> None:
    page.goto(PAGE)
    shown = page.locator("[data-ap-shown]")
    assert shown.inner_text() == "Showing 104 of 104 dossiers"
    page.locator("[data-ap-search]").fill("chen.")
    assert shown.inner_text() == "Showing 4 of 104 dossiers"
    page.locator("[data-ap-which]").select_option("last")  # one each (ruling 30)
    assert shown.inner_text() == "Showing 4 of 104 dossiers"
    page.locator("[data-ap-search]").fill("")
    page.locator("[data-ap-which]").select_option("all")
    page.locator("[data-ap-status]").select_option("Draft")
    assert shown.inner_text() == "Showing 3 of 104 dossiers"


def test_ticked_rows_are_set_together(page: Page) -> None:
    page.goto(PAGE)
    _unlock(page)
    for who in ("aisha.bello", "kenji.russo", "wen.novak"):
        _row(page, who).locator("[data-ap-tick]").check()
    page.locator("[data-ap-set-col]").select_option("g3")
    page.locator("[data-ap-set-val]").select_option("Entered")
    page.locator("[data-ap-set]").click()
    for who in ("aisha.bello", "kenji.russo"):
        assert _row(page, who).locator('[data-cell="g3"] [data-ap-adm]').text_content() == "Entered"
    # A draft has entered nothing: it is left alone.
    assert _row(page, "wen.novak").locator('[data-cell="g3"] [data-ap-adm]').count() == 0


def test_the_header_tick_ticks_the_rows_in_view(page: Page) -> None:
    """AD-22: the header's tick for every row in view, and Set with none
    ticked says so."""
    page.goto(PAGE)
    _unlock(page)
    page.locator("[data-ap-set]").click()
    assert page.locator("[data-ap-said]").inner_text().startswith("No rows ticked")
    page.locator("[data-ap-status]").select_option("Draft")
    every = page.locator("[data-ap-tick-all]")
    every.check()
    assert page.locator("[data-row]:not([hidden]) [data-ap-tick]:checked").count() == 3
    assert page.locator("[data-row][hidden] [data-ap-tick]:checked").count() == 0
    page.locator("[data-row]:not([hidden]) [data-ap-tick]").first.uncheck()
    assert every.evaluate("e => e.indeterminate && !e.checked")
    page.locator("[data-ap-status]").select_option("")
    assert every.evaluate("e => e.indeterminate")  # 2 of 104 in view
    every.click()  # from part-ticked, as a checkbox does: every row in view
    assert page.locator("[data-row] [data-ap-tick]:checked").count() == 104
    every.click()
    assert page.locator("[data-row] [data-ap-tick]:checked").count() == 0
    # Its box sits over the rows' boxes (author, 2026-11-18).
    head_x = every.bounding_box()
    row_x = page.locator("[data-row] [data-ap-tick]").first.bounding_box()
    assert head_x and row_x and abs(head_x["x"] - row_x["x"]) < 1


def test_an_application_advanced_by_hand_can_be_given_later_outcomes(page: Page) -> None:
    # Codex: a submitted application outside the shortlist showed fixed
    # "—" in its later outcomes, so a hand change stopped there.
    page.goto(PAGE)
    _unlock(page)
    row = _row(page, "ben.sato")  # not shortlisted
    selection = row.locator('[data-cell="o2"] select')
    assert selection.input_value() == ""
    row.locator('[data-cell="o1"] select').select_option("Interview")
    selection.select_option("Selected")
    assert (
        row.locator('[data-cell="o2"] [data-ap-date]').inner_text() == "17 Nov"
    )  # the clock's today (AD-40)
    # A draft stays inert.
    assert _row(page, "wen.novak").locator('[data-cell="o2"] select').count() == 0


# --- Rung 3: Fill by rule… and Upload CSV, proposing before they apply ---
def test_a_csv_proposes_then_applies(page: Page) -> None:
    page.goto(PAGE)
    _unlock(page)
    body = (
        "Application ID,Gate 3: Staff interview,Selection,Mystery\n"
        "kenji-not-an-id,Entered,,\n"
        "nzhhny6gaa,Entered,,x\n"
        "f2ps7nyh4k,Entered,,\n"
        "m3qx8vkt2n,Maybe,,\n"
        'h6zr2tdw9p,,"Selected",\n'
    )
    page.locator("[data-ap-csv]").set_input_files(
        files=[{"name": "decisions.csv", "mimeType": "text/csv", "buffer": body.encode()}]
    )
    page.locator("[data-ap-proposal]").wait_for(state="visible")  # read async
    prop = page.locator("[data-ap-proposal]")
    assert "Upload CSV: decisions.csv" in prop.inner_text()
    text = prop.inner_text()
    assert "Column not on this page, ignored: Mystery." in text
    assert "Not in this exercise, ignored: kenji-not-an-id." in text
    assert 'm3qx8vkt2n: "Maybe" is not a value of Staff interview.' in text
    assert "f2ps7nyh4k: Staff interview cannot be set (a draft, or never admitted)." in text
    assert prop.locator("[data-ap-prop-rows] tr").count() == 2
    prop.locator("[data-ap-prop-apply]").click()
    assert (
        _row(page, "ben.sato").locator('[data-cell="g3"] [data-ap-adm]').text_content() == "Entered"
    )
    assert _row(page, "kenji.russo").locator('[data-cell="o2"] select').input_value() == "Selected"


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
    assert lines[0] == (
        "Application ID,Applicant,Email,Status,Peer review,Office checks,Shortlisting,"
        "Staff interview,Selection"
    )
    assert len(lines) == 105
    # Uploaded back, it changes nothing and leaves nothing out.
    page.locator("[data-ap-csv]").set_input_files(
        files=[{"name": "applications.csv", "mimeType": "text/csv", "buffer": text.encode()}]
    )
    page.locator("[data-ap-proposal]").wait_for(state="visible")  # read async
    prop = page.locator("[data-ap-proposal]")
    assert "Nothing would change." in prop.inner_text()
    assert prop.locator("[data-ap-prop-skip] li").count() == 0


def test_the_csv_is_the_rows_in_view_named_for_the_exercise(page: Page) -> None:
    """AD-66: the filter holds, the name does not clash with Extract's
    applications.csv, and a formula-like cell is guarded."""
    page.goto(PAGE)
    page.locator("[data-ap-search]").fill("kenji.russo")
    page.evaluate(
        """() => { var m = document.querySelector('[data-row] .ap-mail');
        m.textContent = '=HYPERLINK(1)'; }"""
    )
    with page.expect_download() as got:
        page.locator("[data-ap-csv-down]").click()
    assert got.value.suggested_filename == "ra_2027_dossiers_2026-11-17.csv"
    lines = got.value.path().read_text(encoding="utf-8").removeprefix("\ufeff").splitlines()
    assert len(lines) == 1 + page.locator("[data-row]:not([hidden])").count()
    page.locator("[data-ap-search]").fill("")
    with page.expect_download() as got:
        page.locator("[data-ap-csv-down]").click()
    text = got.value.path().read_text(encoding="utf-8").removeprefix("\ufeff")
    assert ",'=HYPERLINK(1)," in text
    # Uploaded back, the guarded value and a guarded header read as written.
    _unlock(page)
    head = "Application ID,'-Staff interview"
    page.locator("[data-ap-csv]").set_input_files(
        files=[{"name": "x.csv", "mimeType": "text/csv", "buffer": (head + "\n").encode()}]
    )
    page.locator("[data-ap-proposal]").wait_for(state="visible")
    skipped = page.locator("[data-ap-prop-skip]").inner_text()
    assert "Column not on this page, ignored: -Staff interview." in skipped


def test_apply_keeps_a_cell_changed_by_hand_since(page: Page) -> None:
    page.goto(PAGE)
    _unlock(page)
    upper = "NZHHNY6GAA"  # IDs match whatever their case
    page.locator("[data-ap-csv]").set_input_files(
        files=[
            {
                "name": "x.csv",
                "mimeType": "text/csv",
                "buffer": f"Application ID,Staff interview\n{upper},Entered\n".encode(),
            }
        ]
    )
    page.locator("[data-ap-proposal]").wait_for(state="visible")  # read async
    prop = page.locator("[data-ap-proposal]")
    assert prop.locator("[data-ap-prop-rows] tr").count() == 1
    chip = _row(page, "ben.sato").locator('[data-cell="g3"] [data-ap-adm]')
    chip.click()  # Not entered -> no status, by hand
    page.once("dialog", lambda d: d.accept())
    prop.locator("[data-ap-prop-apply]").click()
    assert chip.text_content() == "—"
    # Focus returns to what opened the proposal.
    assert page.evaluate("document.activeElement.hasAttribute('data-ap-csv-open')")


def test_a_csv_giving_one_cell_two_values_leaves_it(page: Page) -> None:
    # Codex: two rows for one application and column were both proposed
    # against the same starting value, and Apply made only the first.
    page.goto(PAGE)
    _unlock(page)
    body = (
        "Application ID,Staff interview\n"
        "nzhhny6gaa,Entered\n"
        "nzhhny6gaa,-\n"
        "m3qx8vkt2n,Entered\n"
        "m3qx8vkt2n,entered\n"
    )
    page.locator("[data-ap-csv]").set_input_files(
        files=[{"name": "twice.csv", "mimeType": "text/csv", "buffer": body.encode()}]
    )
    page.locator("[data-ap-proposal]").wait_for(state="visible")  # read async
    prop = page.locator("[data-ap-proposal]")
    assert "nzhhny6gaa: Staff interview given more than one value (Entered, —), left as is." in (
        prop.inner_text()
    )
    rows = prop.locator("[data-ap-prop-rows] tr")
    assert rows.count() == 1 and "p3bd7kq2wx" in rows.inner_text()  # the row as shown
    prop.locator("[data-ap-prop-apply]").click()
    assert (
        _row(page, "aisha.bello").locator('[data-cell="g3"] [data-ap-adm]').text_content()
        == "Entered"
    )
    assert _row(page, "ben.sato").locator('[data-cell="g3"] [data-ap-adm]').text_content() == (
        "Not entered"
    )


def test_a_csv_id_like_an_object_key_is_just_unknown(page: Page) -> None:
    # Codex: "__proto__" matched an inherited property and the upload threw.
    page.goto(PAGE)
    _unlock(page)
    body = "Application ID,Staff interview\n__proto__,Entered\nconstructor,Entered\n"
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
    proposal = page.locator("[data-ap-proposal]")
    proposal.wait_for(state="visible")  # the server answers (ruling 78)
    return proposal


def test_each_column_shows_its_rule_from_setup(page: Page) -> None:
    page.goto(PAGE)
    assert (
        "Rule: Mean score at Peer review ≥ 3.5 and Major concerns at Office checks < 1 and"
        " Currently an RA? is Yes → Re-appointment; else if"
        in page.locator('th[data-col="o1"]').inner_text()
    )
    assert (
        "Rule: Shortlisting is Interview → Entered"
        in page.locator('th[data-col="g3"]').inner_text()
    )
    # No rule is built on this page.
    assert page.locator("[data-ap-rule] select").count() == 0


def test_apply_rules_proposes_in_column_order_and_waits_on_the_undecided(page: Page) -> None:
    """Mid Stage 3 (ruling 30): the re-appointed are selected now, their
    Selection open though they skip the interview; the interviewed wait,
    their best 20 not known until the interviews are in."""
    page.goto(PAGE)
    _unlock(page)
    prop = _apply_rules(page)
    text = prop.inner_text()
    assert "Selection: 40 dossiers cannot be judged yet" in text
    rows = prop.locator("[data-ap-prop-rows] tr").all_inner_texts()
    assert len(rows) == 15 and all("\tSelection\tPending\tSelected" in r for r in rows)
    assert any(r.startswith("p3bd7kq2wx\tAisha Bello") for r in rows)  # named as shown
    prop.locator("[data-ap-prop-apply]").click()
    assert _count(page, "o2").startswith("15 selected · 40 pending")


def _set_rule(page: Page, key: str, rule: dict[str, Any] | None) -> None:
    """A rule set on a column, as Process saves it: on the server, whose
    engine *Apply rules* asks (ruling 78), and on the header, which shows
    it. None is decided by hand."""
    _SERVER["rules"][key] = _rule_of(rule)
    page.evaluate(
        '([k, r]) => { document.querySelector(`th[data-col="${k}"]`).dataset.rule ='
        " JSON.stringify(r); }",
        [key, rule],
    )


def _by_answer(question: str) -> dict[str, list[stages.Row]]:
    """The model exercise's submitted rows, grouped by their answer to a
    List question on its form."""
    groups: dict[str, list[stages.Row]] = {}
    for r in stages.plan_of("wa9juxbc2t").rows:
        if r.application.state == "Submitted":
            answer = sample_data.answers("wa9juxbc2t", r.application)[question]
            groups.setdefault(answer, []).append(r)
    return groups


def test_a_branched_rule_takes_a_form_answer_and_the_best_n(page: Page) -> None:
    """Ruling 30: a rule's branches in order, the first holding deciding;
    a form answer; the best N among those its branch reaches, ties at the
    cut all taken and said so. Set on the Shortlisting's header, as
    Process would, so that the sample's own rule is not the only case."""
    groups = _by_answer("Faculty")
    # A faculty with a tie at some cut, so the tie is shown.
    field, rows, n = next(
        (f, rs, i)
        for f, rs in sorted(groups.items())
        for xs in [sorted((r.cells["g1"].result or 0 for r in rs), reverse=True)]
        for i in range(2, len(xs))
        if xs[i - 1] == xs[i]
    )
    results = sorted((r.cells["g1"].result or 0 for r in rows), reverse=True)
    cut = results[n - 1]
    page.goto(PAGE)
    _unlock(page)
    _set_rule(
        page,
        "o1",
        {
            "when": [["form", "Faculty", "is", field], ["top", "g1.r1", "le", str(n)]],
            "then": "Re-appointment",
            "otherwise": "Not shortlisted",
            "more": [{"when": [["res", "g2.r1", "ge", "20"]], "then": "Interview"}],
        },
    )
    prop = _apply_rules(page, only_undecided=False)
    taken = sum(1 for x in results if x >= cut)
    assert taken > n and f"Shortlisting: {taken} at the cut of {n}: tied." in prop.inner_text()
    prop.locator("[data-ap-prop-apply]").click()
    best = {r.application.public_id for r in rows if (r.cells["g1"].result or 0) >= cut}
    for r in (r for rs in groups.values() for r in rs):
        if r.cells["o1"].by_hand:
            continue  # kept: the options leave a hand alone
        i = r.application.public_id
        got = _row(page, i).locator('[data-cell="o1"] select').get_attribute("data-v")
        major = r.cells["g2"].result or 0
        want = "Re-appointment" if i in best else "Interview" if major >= 20 else "Not shortlisted"
        assert got == want, i


def test_the_best_n_waits_while_one_it_could_rank_is_not_in(page: Page) -> None:
    """The cold read on rungs 2-3: a dossier whose score is still coming
    could outrank the rest, so the ranking waits for the whole branch;
    those the branch does not reach are still decided."""
    groups = _by_answer("Faculty")
    field, rows = sorted(groups.items())[0]
    page.goto(PAGE)
    _unlock(page)
    # One of them still waiting on its peer reviews: no result yet.
    _set_result(rows[0].application.public_id, "g1", None)
    _set_rule(
        page,
        "o1",
        {
            "when": [["form", "Faculty", "is", field], ["top", "g1.r1", "le", "3"]],
            "then": "Interview",
            "otherwise": "Not shortlisted",
        },
    )
    prop = _apply_rules(page, only_undecided=False, replace_hand=True)
    text = prop.inner_text()
    assert f"Shortlisting: {len(rows)} dossiers cannot be judged yet" in text
    proposed = [
        p
        for p in prop.locator("[data-ap-prop-rows] tr").all_inner_texts()
        if "\tShortlisting\t" in p
    ]
    ids = {r.application.dossier_id for r in rows}  # proposals name rows as shown
    assert not [p for p in proposed if any(i in p for i in ids)]
    # Elsewhere the rule decides: every other faculty's shortlisted turn Not.
    assert proposed and all(p.endswith("Not shortlisted") for p in proposed)


def _cell(page: Page, row_id: str, key: str) -> Locator:
    return _row(page, row_id).locator(f'[data-cell="{key}"] [data-v]')


def test_one_not_entered_at_a_ranking_goes_on_once(page: Page) -> None:
    """Codex on #3955: a dossier not entered at the first branch's gate
    went on to the next branch twice, so its best N took one dossier for
    two and left out another."""
    rows = [r for r in stages.plan_of("wa9juxbc2t").rows if r.cells["g1"].result is not None]
    a, b = rows[0].application.public_id, rows[1].application.public_id
    page.goto(PAGE)
    _unlock(page)
    _fill_results()
    for i, top in ((a, "9.9"), (b, "9.8")):
        _cell(page, i, "g2").evaluate("e => { e.dataset.v = 'Not entered'; }")
        _set_result(i, "g1", top)
    # The gates' own rules would enter them again: decided by hand here.
    for k in ("g1", "g2"):
        _set_rule(page, k, None)
    _set_rule(
        page,
        "o1",
        {
            "when": [["top", "g2.r1", "le", "3"]],
            "then": "Shortlisted",
            "otherwise": "Shortlisted",
            "more": [{"when": [["top", "g1.r1", "le", "2"]], "then": "Not shortlisted"}],
        },
    )
    prop = _apply_rules(page, only_undecided=False, replace_hand=True)
    prop.locator("[data-ap-prop-apply]").click()
    for i in (a, b):
        got = _row(page, i).locator('[data-cell="o1"] select').get_attribute("data-v")
        assert got == "Not shortlisted", i


def test_one_a_ranking_cannot_take_falls_through_though_another_condition_waits(
    page: Page,
) -> None:
    """Codex on #3955: a dossier not entered at the ranking's gate cannot
    join the branch, so it goes on to the next even while the branch's
    other condition waits on its result."""
    xa = next(
        r.application
        for r in stages.plan_of("wa9juxbc2t").rows
        if r.cells["o1"].value == "Interview" and not r.cells["o1"].by_hand
    )
    x, x_shown = xa.public_id, xa.dossier_id
    page.goto(PAGE)
    _unlock(page)
    _cell(page, x, "g1").evaluate("e => { e.dataset.v = 'Not entered'; }")
    _set_result(x, "g2", None)
    for k in ("g1", "g2"):
        _set_rule(page, k, None)
    _set_rule(
        page,
        "o1",
        {
            "when": [["res", "g2.r1", "ge", "0"], ["top", "g1.r1", "le", "3"]],
            "then": "Interview",
            "otherwise": "Not shortlisted",
        },
    )
    prop = _apply_rules(page, only_undecided=False, replace_hand=True)
    notes = prop.locator("[data-ap-prop-skip] li").all_inner_texts()
    assert not [n for n in notes if n.startswith("Shortlisting") and "judged" in n]
    got = [
        r for r in prop.locator("[data-ap-prop-rows] tr").all_inner_texts() if r.startswith(x_shown)
    ]
    assert got and got[0].endswith("\tShortlisting\tInterview\tNot shortlisted"), got


def test_a_dossier_waiting_elsewhere_holds_back_only_a_ranking_it_could_join(
    page: Page,
) -> None:
    """Codex on #3955: one an earlier branch left waiting held back every
    later best N, even one whose other conditions rule it out."""
    groups = _by_answer("Faculty")
    eng_app = groups["Engineering"][0].application
    eng, eng_dossier = eng_app.public_id, eng_app.dossier_id
    page.goto(PAGE)
    _unlock(page)
    _set_result(eng, "g2", None)  # its checks coming
    _set_rule(
        page,
        "o1",
        {
            "when": [["form", "Faculty", "is", "Engineering"], ["res", "g2.r1", "ge", "0"]],
            "then": "Interview",
            "otherwise": "Interview",
            "more": [
                {
                    "when": [["form", "Faculty", "is", "Law"], ["top", "g1.r1", "le", "3"]],
                    "then": "Not shortlisted",
                }
            ],
        },
    )
    prop = _apply_rules(page, only_undecided=False)
    text = prop.inner_text()
    assert "Shortlisting: 1 dossier cannot be judged yet" in text and eng_dossier in text
    proposed = prop.locator("[data-ap-prop-rows] tr").all_inner_texts()
    law = {r.application.dossier_id for r in groups["Law"]}  # rows named as shown
    ranked = [p for p in proposed if p.split("\t")[0] in law and p.endswith("Not shortlisted")]
    assert 1 <= len(ranked) <= 3 + 2  # the best 3 not already so, or more tied at the cut


def test_the_best_n_waits_on_another_condition_not_yet_judged(page: Page) -> None:
    """The cold read on rungs 2-3: a dossier whose other condition in the
    branch cannot be judged yet could still outrank the rest, so the
    ranking waits for it."""
    field, rows = sorted(_by_answer("Faculty").items())[0]
    page.goto(PAGE)
    _unlock(page)
    _set_result(rows[0].application.public_id, "g2", None)
    _set_rule(
        page,
        "o1",
        {
            "when": [
                ["res", "g2.r1", "lt", "100"],
                ["form", "Faculty", "is", field],
                ["top", "g1.r1", "le", "3"],
            ],
            "then": "Interview",
            "otherwise": "Not shortlisted",
        },
    )
    prop = _apply_rules(page, only_undecided=False, replace_hand=True)
    assert f"Shortlisting: {len(rows)} dossiers cannot be judged yet" in prop.inner_text()


def test_a_later_column_reads_what_an_earlier_one_proposes(page: Page) -> None:
    """Rules run in column order: a later column reads the value an
    earlier one proposes in the same run, and waits on one undecided."""
    page.goto(PAGE)
    _unlock(page)
    hand = page.locator('[data-row]:has(td[data-cell="o1"][data-hand])')
    who = hand.get_attribute("data-ap-name") or ""  # as proposals name it
    # An interviewee's Shortlisting back to Pending, its peer reviews still
    # coming: the Shortlisting cannot decide it, so its entry waits.
    kenji = _row(page, "kenji.russo")
    kenji.locator('[data-cell="o1"] select').select_option("Pending")
    _set_result("h6zr2tdw9p", "g1", None)
    prop = _apply_rules(page, only_undecided=False, replace_hand=True)
    rows = prop.locator("[data-ap-prop-rows] tr").all_inner_texts()
    # The one set by hand goes back to the rule's Not shortlisted, and so
    # the interview, in the same run, turns it away.
    assert f"{who}\t" in "".join(
        r for r in rows if r.endswith("\tShortlisting\tInterview\tNot shortlisted")
    )
    assert [
        r
        for r in rows
        if r.startswith(who) and r.endswith("\tStaff interview\tEntered\tNot entered")
    ]
    assert "Staff interview: 1 dossier cannot be judged yet" in prop.inner_text()


def test_selection_reaches_one_sent_on_by_shortlisting_alone(page: Page) -> None:
    """The cold read on AD1H 4-6: a current RA put down for re-appointment,
    by hand or by this very run, reaches Selection though they enter no
    interview; one not shortlisted does not."""
    plan = stages.plan_of("wa9juxbc2t")
    ras = {m.email for m in sample_data.CURRENT_RAS}
    out = [
        r
        for r in plan.rows
        if r.application.email in ras and r.cells["o1"].value == "Not shortlisted"
    ]
    major = next(
        r for r in out if (r.cells["g2"].result or 0) > 0 and (r.cells["g1"].result or 0) >= 3.5
    )
    low = next(r for r in out if r is not major)
    page.goto(PAGE)
    _unlock(page)
    # One by hand, one whose major concern the office withdrew (the rule
    # now re-appoints them in this run).
    _row(page, low.application.public_id).locator('[data-cell="o1"] select').select_option(
        "Re-appointment"
    )
    _set_result(major.application.public_id, "g2", "0")
    prop = _apply_rules(page, only_undecided=False)  # its decided Shortlisting too
    rows = prop.locator("[data-ap-prop-rows] tr").all_inner_texts()
    for r in (low, major):
        i = r.application.dossier_id  # proposals name rows as shown
        assert [p for p in rows if p.startswith(i) and p.endswith("\tSelection\t\tSelected")], i
    assert not [p for p in rows if p.startswith("napy2evdjp") and "\tSelection\t" in p]


def test_the_page_combines_results_as_the_server_does(page: Page) -> None:
    """The script's combined result is `stages.combined`'s, weights read by
    key and rescaled when a gate is not entered (ruling 21). The RA
    recruitment weighs nothing it shows two gates of, so the Shortlisting
    is given weights here, as Process would."""
    plan = stages.plan_of("wa9juxbc2t")
    weighed = stages.Outcome("o1", 1, "X", (), None, "", (("g1.r1", 0.3), ("g2.r2", 0.7)))
    page.goto(PAGE)
    _unlock(page)
    page.evaluate(
        """() => {
          document.querySelector('th[data-col="o1"]').dataset.weights = "g1.r1:0.3|g2.r2:0.7";
          for (const td of document.querySelectorAll('td[data-cell="o1"]')) {
            const s = document.createElement("span");
            s.setAttribute("data-ap-comb", "");
            td.appendChild(s);
          }
        }"""
    )
    # A change redraws them all.
    chip = _row(page, "ben.sato").locator('[data-cell="g3"] [data-ap-adm]')
    chip.click()
    shown = dict(
        page.evaluate(
            """() => Array.from(document.querySelectorAll('[data-row]')).map(r => [
            r.dataset.apApp,
            (r.querySelector('[data-cell="o1"] [data-ap-comb]') || {}).textContent || ""])"""
        )
    )
    for r in plan.rows:
        if r.application.state != "Submitted":
            continue
        want = stages.combined(r, weighed)
        assert shown[r.application.public_id] == ("" if want is None else f"Combined {want:.2f}")
    # Office checks not entered: Gate 1's alone.
    kenji = next(r for r in plan.rows if r.application.public_id == "h6zr2tdw9p")
    row = _row(page, "kenji.russo")
    g2 = row.locator('[data-cell="g2"] [data-ap-adm]')
    while g2.text_content() != "Not entered":
        g2.click()
    assert row.locator('[data-cell="o1"] [data-ap-comb]').inner_text() == (
        f"Combined {kenji.cells['g1'].result:.2f}"
    )


def test_a_cell_set_by_hand_is_marked_and_kept(page: Page) -> None:
    page.goto(PAGE)
    _unlock(page)
    hand = page.locator('[data-row] td[data-cell="o1"][data-hand]')
    assert hand.count() == 1 and "Set by hand: panel request" in hand.inner_text()
    who = hand.locator("xpath=ancestor::tr").get_attribute("data-ap-name") or ""
    prop = _apply_rules(page, only_undecided=False)
    rows = prop.locator("[data-ap-prop-rows] tr").all_inner_texts()
    assert not [r for r in rows if who in r and "\tShortlisting\t" in r]
    prop.locator("[data-ap-prop-cancel]").press("Escape")  # Esc is Cancel (AD-104)
    assert prop.is_hidden()
    prop = _apply_rules(page, only_undecided=False)
    prop.locator("[data-ap-prop-cancel]").click()  # and so is Cancel
    assert prop.is_hidden()
    prop = _apply_rules(page, only_undecided=False, replace_hand=True)
    rows = prop.locator("[data-ap-prop-rows] tr").all_inner_texts()
    # Its mean is just under the bar: the rule would not interview it.
    assert [
        r for r in rows if who in r and r.endswith("\tShortlisting\tInterview\tNot shortlisted")
    ]
    prop.locator("[data-ap-prop-apply]").click()
    cell = page.locator(f'[data-row]:has(code:text-is("{who}")) td[data-cell="o1"]')
    assert cell.get_attribute("data-hand") is None
    # A change by hand marks the cell.
    cell.locator("select").select_option("Interview")
    assert cell.get_attribute("data-hand") == ""


def test_a_gate_rule_takes_each_applicant_s_one_application(page: Page) -> None:
    """One application each (ruling 30): every submitted one is its
    applicant's last, so a gate entering the last submitted takes all."""
    page.goto(PAGE)
    assert page.locator('[data-row][data-rank="2"]').count() == 0
    assert page.locator('[data-row][data-rank="1"]').count() == 100


def test_the_page_shows_each_outcome_s_combined_result_and_weights(page: Page) -> None:
    page.goto(PAGE)
    _unlock(page)
    head = page.locator('th[data-col="o2"]').inner_text()
    # Each weight names a gate's result (ruling 21).
    assert "Interview score at Staff interview 100%" in head
    combs = page.locator('[data-cell="o2"] [data-ap-comb]')
    assert combs.count() > 0 and not "".join(combs.all_inner_texts())  # none interviewed yet
    # A result in, and the table redrawn by a change, shows it combined.
    kenji = _row(page, "kenji.russo")
    kenji.locator('[data-cell="g3"] [data-v]').evaluate("e => { e.dataset.result = '4.5'; }")
    _row(page, "ben.sato").locator('[data-cell="g3"] [data-ap-adm]').click()
    assert kenji.locator('[data-cell="o2"] [data-ap-comb]').inner_text() == "Combined 4.50"
    # Not entered at the interview, it has nothing to combine.
    chip = kenji.locator('[data-cell="g3"] [data-ap-adm]')
    while chip.text_content() != "Not entered":
        chip.click()
    assert kenji.locator('[data-cell="o2"] [data-ap-comb]').inner_text() == ""


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
    withdrawn = page.locator('[data-row][data-status="Withdrawn"]').evaluate_all(
        "rs => rs.map(r => r.dataset.apName)"
    )
    assert withdrawn and not [r for r in rows if r.split("\t")[0] in withdrawn]


def test_a_rule_proposal_is_dropped_when_the_table_changes(page: Page) -> None:
    page.goto(PAGE)
    _unlock(page)
    prop = _apply_rules(page)
    first = prop.locator("[data-ap-prop-rows] tr").first.inner_text().split("\t")
    assert first[2:] == ["Selection", "Pending", "Selected"]  # a re-appointed RA
    messages: list[str] = []

    def answer(d: Dialog) -> None:
        messages.append(d.message)
        d.accept()

    page.on("dialog", answer)
    row = _row(page, first[0])
    row.locator('[data-cell="g1"] [data-ap-adm]').click()  # the table changes
    prop.locator("[data-ap-prop-apply]").click()
    assert messages and "propose again" in messages[0]
    assert row.locator('[data-cell="o2"] select').get_attribute("data-v") == "Pending"


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
    before = chip.text_content()
    chip.click()
    assert page.locator("[data-ap-changes]").inner_text() == "1 change since unlocked"
    # Leaving with a change pending asks first.
    assert page.evaluate(
        "() => { const e = new Event('beforeunload', {cancelable: true});"
        " window.dispatchEvent(e); return e.defaultPrevented; }"
    )
    page.locator("[data-ap-undo]").click()
    assert chip.text_content() == before
    assert page.locator("[data-ap-changes]").inner_text() == "No changes yet"
    chip.click()
    after = chip.text_content()
    lock.click()
    assert chip.is_disabled() and chip.text_content() == after
    assert page.locator("[data-ap-said]").inner_text() == (
        "1 change kept on this page; the table is locked."
    )


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
    page.locator("[data-ap-proposal]").wait_for(state="visible")
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
                "buffer": b"Application ID,Shortlisting\r\n",
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


def _order(page: Page) -> list[str]:
    return page.locator("[data-row]").evaluate_all("rs => rs.map(r => r.dataset.apName)")


def test_a_column_s_name_sorts_the_rows_and_the_tab_keeps_it(page: Page) -> None:
    """Ruling 52: each column's name sorts the rows by it: ascending, then
    descending, then the page's own order; the sort is kept in the tab."""
    page.goto(PAGE)
    own = _order(page)
    name = page.locator('[data-ap-sort="applicant"]')
    name.click()
    who = page.locator("[data-row] .ap-who strong").all_inner_texts()
    assert who == sorted(who, key=str.lower)
    assert name.locator("xpath=..").get_attribute("aria-sort") == "ascending"
    name.click()
    assert page.locator("[data-row] .ap-who strong").all_inner_texts() == sorted(
        who, key=str.lower, reverse=True
    )
    page.reload()  # kept in the tab
    assert name.locator("xpath=..").get_attribute("aria-sort") == "descending"
    name.click()
    assert _order(page) == own
    # Status: Submitted, Draft, Withdrawn.
    page.locator('[data-ap-sort="status"]').click()
    states = page.locator("[data-row]").evaluate_all("rs => rs.map(r => r.dataset.status)")
    rank = {"Submitted": 0, "Draft": 1, "Withdrawn": 2}
    assert [rank[s] for s in states] == sorted(rank[s] for s in states)


def test_a_gate_sorts_by_its_chip_then_its_result_and_an_outcome_by_its_values(
    page: Page,
) -> None:
    page.goto(PAGE)
    page.locator('[data-ap-sort="g3"]').click()
    chips = page.locator('[data-row] [data-cell="g3"]').evaluate_all(
        "cs => cs.map(c => (c.querySelector('[data-v]') || {dataset: {v: ''}}).dataset.v)"
    )
    order = {"Entered": 0, "Not entered": 1, "": 2}
    assert [order[c] for c in chips] == sorted(order[c] for c in chips)
    page.locator('[data-ap-sort="g1"]').click()
    results = page.locator('[data-row] [data-cell="g1"] [data-v]').evaluate_all(
        "bs => bs.filter(b => b.dataset.v === 'Entered' && b.dataset.result)"
        ".map(b => parseFloat(b.dataset.result))"
    )
    assert results and results == sorted(results, reverse=True)
    page.locator('[data-ap-sort="o1"]').click()
    values = page.locator('[data-row] [data-cell="o1"] [data-v]').evaluate_all(
        "ss => ss.map(s => s.dataset.v)"
    )
    known = page.locator('th[data-col="o1"]').get_attribute("data-values") or ""
    rank = {v: i for i, v in enumerate(known.split("|"))}
    ranked = [rank.get(v, len(rank) + (0 if v == "Pending" else 1)) for v in values]
    assert ranked == sorted(ranked)


def test_a_sort_moves_rows_only_so_the_table_s_work_is_unchanged(page: Page) -> None:
    """The cold read on ruling 52: a sort counts as no change, before or
    after Unlock, and leaves an open proposal good to apply."""
    page.goto(PAGE)
    page.locator('[data-ap-sort="applicant"]').click()
    _unlock(page)
    changes = page.locator("[data-ap-changes]")
    assert changes.inner_text() == "No changes yet"
    page.locator('[data-ap-sort="status"]').click()
    assert changes.inner_text() == "No changes yet"
    page.locator("[data-ap-lock]").click()
    assert changes.is_hidden()
    _unlock(page)
    prop = _apply_rules(page, only_undecided=False)
    page.locator('[data-ap-sort="dossier"]').click()
    dialogs: list[str] = []
    page.on("dialog", lambda d: (dialogs.append(d.message), d.dismiss())[1])
    if prop.locator("[data-ap-prop-apply]").is_enabled():
        prop.locator("[data-ap-prop-apply]").click()
    assert not dialogs


def test_dossier_sorts_by_id_drafts_last(page: Page) -> None:
    page.goto(PAGE)
    page.locator('[data-ap-sort="dossier"]').click()
    rows = page.locator("[data-row]").evaluate_all(
        "rs => rs.map(r => [r.dataset.status === 'Draft' ? 1 : 0, r.dataset.apName])"
    )
    assert rows == sorted(rows) and rows[-1][0] == 1


def test_a_row_takes_the_muted_hover_its_sticky_cell_too(page: Page) -> None:
    """AD-77: Review Robin's row hover (spec/ui_elements.md §7). Dossiers'
    cells are filled, the first one sticky, so the hover fills each cell."""
    page.goto(PAGE)
    row = page.locator("[data-row]").first
    first = row.locator("td").first
    muted = page.evaluate(
        "() => { const d = document.createElement('div');"
        " d.style.background = 'var(--surface-muted)'; document.body.appendChild(d);"
        " const c = getComputedStyle(d).backgroundColor; d.remove(); return c; }"
    )
    assert first.evaluate("e => getComputedStyle(e).backgroundColor") != muted
    row.hover()
    assert first.evaluate("e => getComputedStyle(e).backgroundColor") == muted
    assert first.evaluate("e => getComputedStyle(e).borderBottomColor") == page.evaluate(
        "() => { const d = document.createElement('div');"
        " d.style.color = 'var(--border-default)'; document.body.appendChild(d);"
        " const c = getComputedStyle(d).color; d.remove(); return c; }"
    )
