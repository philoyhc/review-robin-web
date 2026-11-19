"""The Emails page in a real Chromium (segment AD1L): each card a
template that stands alone, written, saved in the tab and reset to its
kind's default. Skips without a Chromium build, as
`test_form_browser.py`'s."""

from __future__ import annotations

from playwright.sync_api import Locator, Page

from applydesk import workflow
from applydesk.tests.test_form_browser import ORIGIN
from applydesk.tests.test_form_browser import page as page  # the fixture, re-exported

EMAILS = f"{ORIGIN}/applydesk/operator/exercises/wa9juxbc2t/emails"
OWED = "Interviews: Outcome · Applicants"
WRITTEN = "Applications: Receipt · Applicants"


def _card(page: Page, name: str) -> Locator:
    return page.locator(f'[data-email="{name}"]')


def test_an_owed_template_is_written_saved_and_kept_in_the_tab(page: Page) -> None:
    page.goto(EMAILS)
    card = _card(page, OWED)
    save = card.locator('[data-em-act="save"]')
    assert card.locator("[data-em-chip]").text_content() == "Owed" and save.is_disabled()
    card.locator("[data-em-subject]").fill("[Exercise]: your interview outcome")
    assert card.locator("[data-em-unsaved]").is_visible() and save.is_enabled()
    save.click()
    # A subject alone is not written.
    assert card.locator("[data-em-chip]").text_content() == "Owed"
    assert "still owed" in card.locator("[data-em-said]").inner_text()
    card.locator("[data-em-body]").fill("Dear [Applicant name], …")
    save.click()
    assert card.locator("[data-em-chip]").text_content() == "Written"
    assert card.locator("[data-em-unsaved]").is_hidden()
    page.reload()  # kept in the tab
    card = _card(page, OWED)
    assert card.locator("[data-em-chip]").text_content() == "Written"
    assert card.locator("[data-em-body]").input_value() == "Dear [Applicant name], …"


def test_start_from_the_default_and_reset_asks_over_text(page: Page) -> None:
    page.goto(EMAILS)
    card = _card(page, OWED)
    reset = card.locator('[data-em-act="reset"]')
    assert reset.inner_text() == "Start from the default"
    reset.click()  # an empty card: no question
    subject, body = workflow.DEFAULT_TEMPLATES["outcome-applicants"]
    assert card.locator("[data-em-subject]").input_value() == subject
    assert card.locator("[data-em-body]").input_value() == body
    assert reset.inner_text() == "Reset to default"
    assert card.locator("[data-em-unsaved]").is_visible()
    written = _card(page, WRITTEN)
    written.locator("[data-em-subject]").fill("Something else")
    asked: list[str] = []
    page.once("dialog", lambda d: (asked.append(d.message), d.dismiss())[1])
    written.locator('[data-em-act="reset"]').click()
    assert asked and written.locator("[data-em-subject]").input_value() == "Something else"


def test_leaving_with_a_card_unsaved_asks_first(page: Page) -> None:
    page.goto(EMAILS)
    _card(page, OWED).locator("[data-em-subject]").fill("Draft")
    asked: list[str] = []
    page.once("dialog", lambda d: (asked.append(d.type), d.dismiss())[1])
    page.get_by_role("link", name="Process").first.click()
    assert asked == ["beforeunload"]


def test_an_emptied_template_is_owed_again_and_a_stale_one_leaves_storage(page: Page) -> None:
    page.goto(EMAILS)
    card = _card(page, WRITTEN)
    card.locator("[data-em-subject]").fill("")
    card.locator('[data-em-act="save"]').click()
    assert card.locator("[data-em-chip]").text_content() == "Owed"
    # A template Process no longer makes owed is dropped from storage.
    page.evaluate(
        "() => { const k = 'applydesk-emails:wa9juxbc2t';"
        " const v = JSON.parse(sessionStorage.getItem(k));"
        " v['Gone: Outcome · Applicants'] = {s: 'x', b: 'y'};"
        " sessionStorage.setItem(k, JSON.stringify(v)); }"
    )
    page.reload()
    kept = page.evaluate("() => JSON.parse(sessionStorage.getItem('applydesk-emails:wa9juxbc2t'))")
    assert list(kept) == [WRITTEN]


def test_reset_on_the_default_says_so_and_asks_nothing(page: Page) -> None:
    page.goto(EMAILS)
    card = _card(page, WRITTEN)  # shows its kind's default
    card.locator('[data-em-act="reset"]').click()
    assert card.locator("[data-em-said]").inner_text() == "This is the default already."
    card.locator("[data-em-subject]").fill("Changed")
    page.once("dialog", lambda d: d.accept())
    card.locator('[data-em-act="reset"]').click()
    assert card.locator("[data-em-said]").inner_text() == "The default is in, as saved."
    assert card.locator('[data-em-act="save"]').is_disabled()
