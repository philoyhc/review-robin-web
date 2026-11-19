"""The Review Robin card's Send and Re-send in a real Chromium (segment
AD1M rung 4), simulated in the tab (ruling 55). Skips without a Chromium
build, as `test_form_browser.py`'s."""

from __future__ import annotations

from playwright.sync_api import Locator, Page

from applydesk.tests.test_form_browser import ORIGIN
from applydesk.tests.test_form_browser import page as page  # the fixture, re-exported

EX = "wa9juxbc2t"
EVALUATIONS = f"{ORIGIN}/applydesk/operator/exercises/{EX}/evaluations"
INTERVIEW = f"{EVALUATIONS}/gate_3"  # Suggested, its pairs awaiting approval


def _card(page: Page) -> Locator:
    return page.locator("#ev-rr")


def _said(page: Page) -> str:
    return _card(page).locator("[data-rr-said]").inner_text()


def _approve_all(page: Page) -> None:
    page.locator('[data-ev-act="approve-all"]').click()


def test_send_waits_for_approvals_then_keeps_the_send_in_the_tab(page: Page) -> None:
    page.on("dialog", lambda d: d.accept())
    page.goto(INTERVIEW)
    card = _card(page)
    send, resend = card.locator('[data-rr-act="send"]'), card.locator('[data-rr-act="resend"]')
    assert send.is_enabled() and resend.is_disabled()
    send.click()  # the approvals are owed
    assert _said(page) == "Not sent (invalid_setup): 40 dossiers to approve."
    _approve_all(page)
    send.click()
    assert _said(page).startswith("Sent (simulated): Review Robin would now hold a draft session")
    assert page.locator(".ev-head [data-gate-state]").text_content() == "Sent"
    assert card.locator("[data-rr-link]").inner_text() == "Linked; sent, its session not yet open"
    assert card.locator("[data-rr-last]").inner_text().endswith("in this tab")
    assert send.is_disabled() and resend.is_disabled()
    assert card.locator("[data-rr-changed]").is_hidden()
    page.reload()  # kept in the tab
    card = _card(page)
    assert page.locator(".ev-head [data-gate-state]").text_content() == "Sent"
    assert card.locator('[data-rr-act="send"]').is_disabled()
    # Evaluations' table says so too.
    page.goto(EVALUATIONS)
    row = page.locator('tr[data-gate="g3"]')
    assert row.locator("[data-gate-state]").text_content() == "Sent"
    assert "Sent in this tab" in row.inner_text()


def test_a_change_since_sent_is_re_sent(page: Page) -> None:
    page.on("dialog", lambda d: d.accept())
    page.goto(INTERVIEW)
    _approve_all(page)
    card = _card(page)
    card.locator('[data-rr-act="send"]').click()
    resend = card.locator('[data-rr-act="resend"]')
    card.locator("[data-rr-name]").fill("RA interviews 2026")
    assert card.locator("[data-rr-changed]").is_visible() and resend.is_enabled()
    resend.click()
    assert _said(page).startswith("Re-sent (simulated): the draft")
    assert card.locator("[data-rr-changed]").is_hidden() and resend.is_disabled()
    # The files changing since (a pair saved by AD2, here the kept digest)
    # marks it too.
    page.evaluate(
        f"""() => {{
          const k = "applydesk-rr:{EX}", all = JSON.parse(sessionStorage.getItem(k));
          all.g3.digest = "older"; sessionStorage.setItem(k, JSON.stringify(all));
        }}"""
    )
    page.reload()
    card = _card(page)
    assert card.locator("[data-rr-changed]").is_visible()
    assert card.locator("[data-rr-name]").input_value() == "RA interviews 2026"


def test_a_taken_code_and_an_edited_pair_are_refused(page: Page) -> None:
    page.on("dialog", lambda d: d.accept())
    page.goto(INTERVIEW)
    _approve_all(page)
    card = _card(page)
    card.locator("[data-rr-code]").fill(f"{EX.upper()}-G1")
    card.locator('[data-rr-act="send"]').click()
    assert _said(page) == (
        f"Not sent (session_code_conflict): {EX.upper()}-G1 is Gate 1's session code."
        " Choose another."
    )
    card.locator("[data-rr-code]").fill("")
    card.locator('[data-rr-act="send"]').click()
    assert "the session code must be 1 to 64 characters" in _said(page)
    card.locator("[data-rr-code]").fill(f"{EX}-g3")
    page.locator("#ev-table-card tbody tr").first.get_by_role("button", name="Remove").click()
    card.locator('[data-rr-act="send"]').click()
    assert "this tab's changes to the pairs are not saved until AD2" in _said(page)


def test_an_opened_closed_or_detached_gate_sends_nothing(page: Page) -> None:
    base = f"{ORIGIN}/applydesk/operator/exercises/k7mfr3pq8z/evaluations"
    for n, why in (
        (1, "Opened in Review Robin"),
        (2, "Opened in Review Robin"),
        (3, "Detached: unlinked in Review Robin"),
    ):
        page.goto(f"{base}/gate_{n}")
        card = _card(page)
        for sel in ('[data-rr-act="send"]', '[data-rr-act="resend"]', "[data-rr-code]"):
            el = card.locator(sel)
            assert el.is_disabled()
            assert (el.get_attribute("title") or "").startswith(why)
