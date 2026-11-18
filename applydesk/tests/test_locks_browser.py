"""What a published stage fixes, beyond Process, in a real Chromium
(segment AD1K rung 4): the Form builder read-only (AD-03), an opened
gate's cells on Dossiers (AD-04), blind review (AD-05) and a release
waiting on its emails (AD-21). Skips without a Chromium build, as
`test_form_browser.py`'s."""

from __future__ import annotations

from playwright.sync_api import Dialog, Page

from applydesk.tests.test_form_browser import ORIGIN
from applydesk.tests.test_form_browser import page as page  # the fixture, re-exported

MODEL = f"{ORIGIN}/applydesk/operator/exercises/wa9juxbc2t"


def test_a_published_form_reads_but_does_not_change(page: Page) -> None:
    page.goto(f"{MODEL}/form")
    note = page.locator("[data-fb-fixed-note]")
    assert note.inner_text().startswith("Applications is published: revert it to draft")
    main = page.locator(".fb-main")
    editable = main.locator(
        "input:not([disabled]), select:not([disabled]), textarea:not([disabled])"
    )
    assert editable.count() == 0
    grip = main.locator("[data-fc-grip]").first
    assert grip.is_disabled()
    toggle = main.locator("#fb-cards [data-fc-toggle]").first
    toggle.click()  # its cards still open, to be read
    assert toggle.get_attribute("aria-expanded") == "true"
    assert page.locator("[data-fb-preview]").is_enabled()


def test_an_opened_gate_s_cells_stay_fixed_when_unlocked(page: Page) -> None:
    page.goto(f"{MODEL}/dossiers")
    page.locator("[data-ap-lock]").click()
    assert (
        page.locator('th[data-col="g1"]')
        .inner_text()
        .endswith("Fixed: its Review Robin session has opened")
    )
    chip = page.locator('[data-cell="g1"] [data-ap-adm]').first
    assert chip.is_disabled()
    assert (chip.get_attribute("title") or "").startswith("Its Review Robin session has opened")
    g3 = page.locator('[data-cell="g3"] [data-ap-adm]').first
    assert g3.is_enabled()  # not sent yet: its entries still move


def test_a_release_waits_on_its_emails_and_names_what_is_undecided(page: Page) -> None:
    page.goto(f"{MODEL}/dossiers")
    page.locator("[data-ap-lock]").click()
    selection = page.locator('[data-ap-release="Selection"]')
    assert selection.is_disabled()
    title = page.locator('th[data-col="o2"] .ap-rel').get_attribute("title") or ""
    assert title.startswith("Write its emails on Emails first: Interviews: Outcome - Applicants")
    shortlisting = page.locator('[data-ap-release="Shortlisting"]')
    assert shortlisting.is_enabled()  # released already: it may be withdrawn
    said: list[str] = []

    def dismiss(d: Dialog) -> None:
        said.append(d.message)
        d.dismiss()

    page.once("dialog", dismiss)
    shortlisting.click()
    assert said and said[0].startswith("Withdraw the release of Shortlisting")


def test_blind_review_is_fixed_once_a_gate_s_stage_is_published(page: Page) -> None:
    page.goto(MODEL)
    card = page.locator("[data-details]")
    card.get_by_role("button", name="Unlock").click()
    blind = card.locator('[data-dt="blind"]')
    assert blind.is_disabled()
    assert "fixed: a stage holding a gate is published" in card.locator(".dt-check").inner_text()
