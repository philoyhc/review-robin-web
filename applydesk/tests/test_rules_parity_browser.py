"""Dossiers' *Apply rules* against the server's engine (segment AD2C rung
6, ruling 78). Rung 6a ran this file against the page's own script, the
one parity run before it went: the two agreed cell for cell and reason for
reason. Since rung 6b the page asks the engine, so this now checks that
the page shows the engine's answer over the table as it stands, hand
changes included, under each option. Without a Chromium build the test
skips, saying why; ``RRW_REQUIRE_BROWSER=1`` (set by CI) turns that skip
into a failure."""

from __future__ import annotations

import functools
import os
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Error, Page, Route, sync_playwright

from applydesk import locks, rules, sample_data, stages
from applydesk.tests._host import host_with

ORIGIN = "http://applydesk.test"
MODEL = "wa9juxbc2t"


@pytest.fixture(autouse=True)
def _table_open(monkeypatch: pytest.MonkeyPatch) -> None:
    """The table worked by hand: no gate's session has opened."""
    monkeypatch.setattr(locks, "cells_lock", lambda e, g: locks.OPEN)
    monkeypatch.setattr(locks, "release_lock", lambda e, o: locks.OPEN)


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


_TABLE = """() => {
  const out = {};
  document.querySelectorAll("[data-row]").forEach((r) => {
    const cells = {};
    r.querySelectorAll("[data-cell]").forEach((td) => {
      const el = td.querySelector("[data-v]");
      if (el) cells[td.dataset.cell] = [el.dataset.v, td.hasAttribute("data-hand")];
    });
    out[r.dataset.apApp] = cells;
  });
  return out;
}"""

_PROPOSAL = """() => ({
  rows: Array.from(document.querySelectorAll("[data-ap-prop-rows] tr")).map(
    (tr) => Array.from(tr.children).map((td) => td.textContent)),
  skipped: Array.from(document.querySelectorAll("[data-ap-prop-skip] li")).map(
    (li) => li.textContent),
})"""


def _page_answer(page: Page, *, only_pending: bool, replace_hand: bool) -> dict[str, Any]:
    rule = page.locator("[data-ap-rule]")
    if rule.is_hidden():
        page.locator("[data-ap-rule-open]").click()
    rule.locator("[data-ap-rule-pending]").set_checked(only_pending)
    rule.locator("[data-ap-rule-hand]").set_checked(replace_hand)
    rule.locator("[data-ap-rule-go]").click()
    page.locator("[data-ap-proposal]").wait_for(state="visible")
    got = page.evaluate(_PROPOSAL)
    page.locator("[data-ap-prop-cancel]").click()
    return got


def _server_answer(
    exercise_id: str,
    table: dict[str, dict[str, list[Any]]],
    *,
    only_pending: bool,
    replace_hand: bool,
) -> dict[str, Any]:
    plan = stages.plan_of(exercise_id)
    columns = rules.columns_of(plan, lambda gate: False)
    sent = {app: {k: (v[0], bool(v[1])) for k, v in cells.items()} for app, cells in table.items()}
    rows = rules.rows_of(plan, functools.partial(sample_data.answers, exercise_id), sent)
    got = rules.propose(columns, rows, only_pending=only_pending, replace_hand=replace_hand)
    labels = {c.key: c.label for c in columns}
    names = {r.app: r.name for r in rows}
    return {
        "rows": [[names[c.app], labels[c.key], c.old, c.new] for c in got.changes],
        "skipped": list(got.skipped),
    }


def _same(page: Page, exercise_id: str, *, only_pending: bool, replace_hand: bool) -> int:
    """The page's proposal and the server's, over the table as it stands;
    the number of changes, so a scenario can show it proposes some."""
    table = page.evaluate(_TABLE)
    shown = _page_answer(page, only_pending=only_pending, replace_hand=replace_hand)
    server = _server_answer(
        exercise_id, table, only_pending=only_pending, replace_hand=replace_hand
    )
    # The page's rows are Dossier, applicant, column, from, to.
    page_rows = [[r[0], r[2], r[3], r[4]] for r in shown["rows"]]
    assert page_rows == server["rows"]
    assert shown["skipped"] == server["skipped"]
    return len(page_rows)


@pytest.mark.parametrize(
    ("only_pending", "replace_hand"), [(True, False), (False, False), (False, True)]
)
def test_the_server_proposes_what_the_page_proposed(
    page: Page, only_pending: bool, replace_hand: bool
) -> None:
    page.goto(f"{ORIGIN}/applydesk/operator/exercises/{MODEL}/dossiers")
    page.locator("[data-ap-lock]").click()
    proposed = _same(page, MODEL, only_pending=only_pending, replace_hand=replace_hand)
    assert proposed > 0


def test_parity_holds_after_hand_changes_and_an_applied_run(page: Page) -> None:
    """Hand changes on gates and outcomes, then a run applied, then the
    rules asked again: later columns read the earlier ones as they stand."""
    page.goto(f"{ORIGIN}/applydesk/operator/exercises/{MODEL}/dossiers")
    page.locator("[data-ap-lock]").click()
    chips = page.locator('[data-cell="g1"] [data-ap-adm]:not([disabled])')
    for i in range(min(4, chips.count())):
        chips.nth(i).click()
    selects = page.locator('[data-cell="o1"] select:not([disabled])')
    if selects.count():
        values = selects.first.locator("option").all_text_contents()
        selects.first.select_option(values[-1])
    for only_pending, replace_hand in ((True, False), (False, True)):
        _same(page, MODEL, only_pending=only_pending, replace_hand=replace_hand)
    # Apply one run, then ask again over the changed table.
    page.locator("[data-ap-rule-go]").click()
    page.locator("[data-ap-proposal]").wait_for(state="visible")
    page.locator("[data-ap-prop-apply]").click()
    _same(page, MODEL, only_pending=False, replace_hand=True)


def test_parity_holds_for_entry_combined_and_last_submitted(page: Page) -> None:
    """The kinds the sample's rules do not read: an entry, a combined
    result over two weights, and the applicant's last submitted, saved
    as Process saves them (rung 5) and read by both evaluators."""
    from dataclasses import replace

    from applydesk import db, process_store

    plan = stages.plan_of(MODEL)
    rule = stages.Rule(
        (("ent", "g2", "is", "Entered"), ("comb", "", "ge", "3.5")),
        "Interview",
        "Re-appointment",
        (((("last", "", "le", "1"), ("res", "g1.r1", "lt", "3")), "Not shortlisted"),),
    )
    weights = (("g1.r1", 0.7), ("g2.r2", 0.3))
    changed = tuple(
        replace(
            st,
            columns=tuple(
                replace(c, rule=rule, weights=weights) if c.key == "o1" else c for c in st.columns
            ),
        )
        for st in plan.stages
    )
    session = db.new_session()
    try:
        process_store.save(session, MODEL, changed, 0, None)
        session.commit()
    finally:
        session.close()
    page.goto(f"{ORIGIN}/applydesk/operator/exercises/{MODEL}/dossiers")
    page.locator("[data-ap-lock]").click()
    proposed = 0
    for only_pending, replace_hand in ((True, False), (False, True)):
        proposed += _same(page, MODEL, only_pending=only_pending, replace_hand=replace_hand)
    assert proposed > 0
