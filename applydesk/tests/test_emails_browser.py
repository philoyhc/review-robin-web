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


def test_insert_field_puts_it_at_the_cursor_of_the_box_last_used(page: Page) -> None:
    page.goto(EMAILS)
    card = _card(page, OWED)
    subject = card.locator("[data-em-subject]")
    subject.fill("Your outcome")
    subject.evaluate("s => s.setSelectionRange(0, 0)")
    card.locator("[data-em-insert]").select_option("Exercise")
    assert subject.input_value() == "Your outcome"  # choosing inserts nothing
    card.locator('[data-em-act="insert"]').click()
    assert subject.input_value() == "[Exercise]Your outcome"
    # The menu holds this kind's fields only.
    options = card.locator("[data-em-insert] option").all_inner_texts()
    assert options == list(workflow.EMAIL_FIELDS["outcome-applicants"])
    # A body never used takes the field at its end.
    other = _card(page, "Interviews: Outcome · Evaluators")
    other.locator("[data-em-body]").evaluate("b => { b.value = 'Dear'; }")
    other.locator("[data-em-insert]").select_option("Evaluator name")
    other.locator('[data-em-act="insert"]').click()
    assert other.locator("[data-em-body]").input_value() == "Dear[Evaluator name]"


def test_save_refuses_another_kind_s_field_and_says_which(page: Page) -> None:
    page.goto(EMAILS)
    card = _card(page, OWED)  # an outcome to applicants: no [Evaluator name]
    card.locator("[data-em-subject]").fill("Outcome")
    card.locator("[data-em-body]").fill("Dear [Evaluator name], [not a field] stays text.")
    card.locator('[data-em-act="save"]').click()
    said = card.locator("[data-em-said]").inner_text()
    assert said == "Not saved: [Evaluator name] is not a field of this email. Use Insert field."
    assert card.locator("[data-em-body]").get_attribute("aria-invalid") == "true"
    assert card.locator("[data-em-chip]").text_content() == "Owed"
    card.locator("[data-em-body]").fill("Dear [applicant NAME], [not a field] stays text.")
    card.locator('[data-em-act="save"]').click()  # case does not matter
    assert card.locator("[data-em-chip]").text_content() == "Written"


def test_preview_fills_each_field_from_the_sample_and_marks_a_foreign_one(page: Page) -> None:
    page.goto(EMAILS)
    card = _card(page, OWED)
    card.locator('[data-em-act="reset"]').click()
    button = card.locator('[data-em-act="preview"]')
    button.click()
    assert button.get_attribute("aria-expanded") == "true"
    preview = card.locator("[data-em-preview]")
    subject = preview.locator("[data-em-preview-subject]").inner_text()
    assert subject == "Recruitment and Selection of Residential Assistants: Interviews outcome"
    body = preview.locator("[data-em-preview-body]").inner_text()
    assert body.startswith("Dear Aisha Bello,") and "is: Pending." in body
    assert "/applydesk/me/exercises/wa9juxbc2t" in body
    # It follows the card as typed, a foreign field marked.
    card.locator("[data-em-body]").fill("Dear [Evaluator name]")
    assert preview.locator("mark").inner_text() == "[Evaluator name]"
    button.click()
    assert preview.is_hidden() and button.inner_text() == "Preview"


def test_preview_shows_text_as_text_and_a_field_with_no_sample_dimmed(page: Page) -> None:
    """The cold read on AD1L: [constructor] is text, markup is text, and a
    draft's receipt (no application yet) shows its fields' names."""
    page.goto(EMAILS)
    card = _card(page, OWED)
    card.locator("[data-em-body]").fill("[constructor] <b>bold</b> [Applicant name]")
    card.locator('[data-em-act="preview"]').click()
    body = card.locator("[data-em-preview-body]")
    assert body.inner_text() == "[constructor] <b>bold</b> Aisha Bello"
    assert body.locator("b").count() == 0
    page.goto(f"{ORIGIN}/applydesk/operator/exercises/c4xh2ndv6s/emails")
    draft = page.locator("[data-email]").first
    draft.locator('[data-em-act="reset"]').click()
    draft.locator('[data-em-act="preview"]').click()
    none = draft.locator("[data-em-preview-body] .em-none")
    assert none.first.inner_text() == "[Applicant name]"
    assert none.first.get_attribute("title") == "No value in the sample"


def test_each_card_keeps_its_own_insertion_point(page: Page) -> None:
    """Codex on #4012: a cursor left in one card's subject survives an
    edit in another card."""
    page.goto(EMAILS)
    a = _card(page, OWED)
    a.locator("[data-em-subject]").fill("Outcome")
    a.locator("[data-em-subject]").evaluate("s => s.setSelectionRange(0, 0)")
    _card(page, WRITTEN).locator("[data-em-body]").click()
    a.locator("[data-em-insert]").select_option("Exercise")
    a.locator('[data-em-act="insert"]').click()
    assert a.locator("[data-em-subject]").input_value() == "[Exercise]Outcome"
