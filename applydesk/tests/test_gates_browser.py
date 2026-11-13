"""The Gates page in a real Chromium (segment AD1F, rung 3): gate cards
open and close, the Outline goes to them, and a gate's panel, chosen or
made in place, redraws its chip, its members and the Outline. Skips
without a Chromium build, as `test_form_browser.py`'s."""

from __future__ import annotations

from playwright.sync_api import Page

from applydesk.tests.test_form_browser import ORIGIN
from applydesk.tests.test_form_browser import page as page  # the fixture, re-exported

GATES = f"{ORIGIN}/applydesk/operator/exercises/wa9juxbc2t/gates"
DRAFT = f"{ORIGIN}/applydesk/operator/exercises/c4xh2ndv6s/gates"


def test_a_gate_card_opens_and_closes_and_the_outline_goes_to_it(page: Page) -> None:  # noqa: F811
    page.goto(GATES)
    card = page.locator('.gc[data-gate="g2"]')
    assert card.get_attribute("data-open") is None
    card.locator("[data-fc-toggle]").click()
    assert card.get_attribute("data-open") == ""
    assert card.locator("[data-fc-toggle]").get_attribute("aria-label") == "Collapse Gate 2"
    card.locator("[data-fc-toggle]").click()
    assert card.get_attribute("data-open") is None
    page.locator('[data-go="g3"]').click()
    g3 = page.locator('.gc[data-gate="g3"]')
    assert g3.get_attribute("data-open") == ""
    assert g3.locator("[data-fc-toggle]").evaluate("b => b === document.activeElement")
    assert page.locator("[data-gc-counts]").text_content() == "3 gates · 3 panels in use"
    assert not page.locator("[data-gc-issues]").is_visible()
    # Sent gates keep their panel.
    assert g3.locator("[data-gc-panel]").is_disabled()


def test_a_gate_makes_its_panel_in_place(page: Page) -> None:  # noqa: F811
    page.goto(DRAFT)
    card = page.locator('.gc[data-gate="g1"]')
    issues = page.locator("[data-gc-issues]")
    assert issues.text_content() == "Gate 1 has no panel."
    assert page.locator("[data-gc-counts]").text_content() == "1 gate · 0 panels in use"
    menu = card.locator("[data-gc-panel]")
    menu.select_option("__new")
    assert menu.input_value() == ""
    box = card.locator("[data-newpanel]")
    box.locator('[data-np="name"]').fill("Interview panel")
    box.locator('[data-np="members"]').fill("Ann Goh <ann.goh@example.edu>\nraj.k@example.edu")
    box.get_by_role("button", name="Create panel").click()
    assert not box.is_visible()
    assert card.locator('[data-sum="panel"]').text_content() == "Interview panel · 2 people"
    members = card.locator("[data-gc-members] li").all_inner_texts()
    assert members == ["Ann Goh ann.goh@example.edu", "raj.k@example.edu"]
    assert not card.locator("[data-gc-none]").is_visible()
    assert page.locator('[data-o-panel="g1"]').text_content() == "Interview panel"
    assert page.locator("[data-gc-counts]").text_content() == "1 gate · 1 panel in use"
    assert not issues.is_visible()
    # Back to none: the gate says so again.
    menu.select_option("")
    assert card.locator('[data-sum="panel"]').text_content() == "No panel"
    assert card.locator("[data-gc-none]").is_visible()
    assert issues.text_content() == "Gate 1 has no panel."
