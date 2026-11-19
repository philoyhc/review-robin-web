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
    card.locator("[data-em-subject]").fill("$exercise_name: your interview outcome")
    assert card.locator("[data-em-unsaved]").is_visible() and save.is_enabled()
    save.click()
    # A subject alone is not written.
    assert card.locator("[data-em-chip]").text_content() == "Owed"
    assert "still owed" in card.locator("[data-em-said]").inner_text()
    card.locator("[data-em-body]").fill("Dear $applicant_name, …")
    save.click()
    assert card.locator("[data-em-chip]").text_content() == "Written"
    assert card.locator("[data-em-unsaved]").is_hidden()
    page.reload()  # kept in the tab
    card = _card(page, OWED)
    assert card.locator("[data-em-chip]").text_content() == "Written"
    assert card.locator("[data-em-body]").input_value() == "Dear $applicant_name, …"


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
    card.locator("[data-em-insert]").select_option("exercise_name")
    assert subject.input_value() == "Your outcome"  # choosing inserts nothing
    card.locator('[data-em-act="insert"]').click()
    assert subject.input_value() == "${exercise_name}Your outcome"  # braced before a letter
    # The menu holds this kind's tags only, each with what it stands for.
    values = card.locator("[data-em-insert] option").evaluate_all("os => os.map(o => o.value)")
    assert values == list(workflow.EMAIL_FIELDS["outcome-applicants"])
    label = card.locator("[data-em-insert] option").first.inner_text()
    assert label == "$applicant_name — the applicant's name"
    # A body never used takes the field at its end.
    other = _card(page, "Interviews: Outcome · Evaluators")
    other.locator("[data-em-body]").evaluate("b => { b.value = 'Dear'; }")
    other.locator("[data-em-insert]").select_option("evaluator_name")
    other.locator('[data-em-act="insert"]').click()
    assert other.locator("[data-em-body]").input_value() == "Dear$evaluator_name"


def test_save_refuses_another_kind_s_field_and_says_which(page: Page) -> None:
    page.goto(EMAILS)
    card = _card(page, OWED)  # an outcome to applicants: no $evaluator_name
    card.locator("[data-em-subject]").fill("Outcome")
    card.locator("[data-em-body]").fill("Dear $evaluator_name, $not_a_tag and $$5 stay text.")
    card.locator('[data-em-act="save"]').click()
    said = card.locator("[data-em-said]").inner_text()
    assert said == "Not saved: $evaluator_name is not a tag of this email. Use Insert field."
    assert card.locator("[data-em-body]").get_attribute("aria-invalid") == "true"
    assert card.locator("[data-em-chip]").text_content() == "Owed"
    card.locator("[data-em-body]").fill("Dear ${applicant_name}, $not_a_tag and $$5 stay text.")
    card.locator('[data-em-act="save"]').click()  # ${tag} as $tag
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
    card.locator("[data-em-body]").fill("Dear $evaluator_name")
    assert preview.locator("mark").inner_text() == "$evaluator_name"
    button.click()
    assert preview.is_hidden() and button.inner_text() == "Preview"


def test_preview_shows_text_as_text_and_a_field_with_no_sample_dimmed(page: Page) -> None:
    """The cold read on AD1L: $constructor is text, markup is text, and a
    draft's receipt (no application yet) shows its fields' names."""
    page.goto(EMAILS)
    card = _card(page, OWED)
    card.locator("[data-em-body]").fill("$constructor <b>bold</b> $applicant_name, $$5")
    card.locator('[data-em-act="preview"]').click()
    body = card.locator("[data-em-preview-body]")
    assert body.inner_text() == "$constructor <b>bold</b> Aisha Bello, $5"
    assert body.locator("b").count() == 0
    page.goto(f"{ORIGIN}/applydesk/operator/exercises/c4xh2ndv6s/emails")
    draft = page.locator("[data-email]").first
    # Its default drops each line whose tag is empty, as Review Robin's.
    draft.locator('[data-em-act="reset"]').click()
    draft.locator('[data-em-act="preview"]').click()
    shown = draft.locator("[data-em-preview-body]").inner_text()
    assert "Dear" not in shown and "Thank you" not in shown and "Questions?" in shown
    # A body of one's own keeps the line, the empty tag dimmed.
    draft.locator("[data-em-body]").fill("Dear $applicant_name,")
    none = draft.locator("[data-em-preview-body] .em-none")
    assert none.first.inner_text() == "$applicant_name"
    assert none.first.get_attribute("title") == "No value in the sample"


def test_each_card_keeps_its_own_insertion_point(page: Page) -> None:
    """Codex on #4012: a cursor left in one card's subject survives an
    edit in another card."""
    page.goto(EMAILS)
    a = _card(page, OWED)
    a.locator("[data-em-subject]").fill("Outcome")
    a.locator("[data-em-subject]").evaluate("s => s.setSelectionRange(0, 0)")
    _card(page, WRITTEN).locator("[data-em-body]").click()
    a.locator("[data-em-insert]").select_option("exercise_name")
    a.locator('[data-em-act="insert"]').click()
    assert a.locator("[data-em-subject]").input_value() == "${exercise_name}Outcome"


def test_preview_shows_paragraphs_with_a_small_gap(page: Page) -> None:
    """Ruling 53: a blank line separates paragraphs; a single line break
    stays a line break."""
    page.goto(EMAILS)
    card = _card(page, OWED)
    # Blank lines with spaces on them, several or one, are one break.
    body = "\n\nDear $applicant_name,\n  \n \nFirst line\nsecond line\n\n\nLast.\n  "
    card.locator("[data-em-body]").fill(body)
    card.locator('[data-em-act="preview"]').click()
    paras = card.locator("[data-em-preview-body] p.em-para")
    assert paras.all_inner_texts() == ["Dear Aisha Bello,", "First line\nsecond line", "Last."]
    # The gap is the rule's own 0.6em, under a line, and none after the last.
    size = paras.first.evaluate("p => parseFloat(getComputedStyle(p).fontSize)")
    gap = paras.first.evaluate("p => parseFloat(getComputedStyle(p).marginBottom)")
    assert abs(gap - 0.6 * size) < 0.5 and gap < size
    assert paras.last.evaluate("p => parseFloat(getComputedStyle(p).marginBottom)") == 0
    card.locator("[data-em-body]").fill("\n \n\n")
    assert card.locator("[data-em-preview-body] p").count() == 0


def test_the_body_grows_with_its_text_and_has_no_handle(page: Page) -> None:
    page.goto(EMAILS)
    body = _card(page, OWED).locator("[data-em-body]")
    assert body.evaluate("t => getComputedStyle(t).resize") == "none"
    before = body.evaluate("t => t.offsetHeight")
    body.fill("\n\n".join(f"Paragraph {i}." for i in range(8)))
    after = body.evaluate("t => t.offsetHeight")
    assert after > before and body.evaluate("t => t.scrollHeight <= t.clientHeight + 2")


def test_tags_are_case_as_written_and_a_braced_foreign_one_is_refused(page: Page) -> None:
    """Ruling 54, as Review Robin's: $Applicant_name is not a tag; another
    kind's tag is refused braced or not; Insert after a lone $ adds a space."""
    page.goto(EMAILS)
    card = _card(page, OWED)
    card.locator("[data-em-subject]").fill("Outcome")
    card.locator("[data-em-body]").fill("Hi ${evaluator_name}")
    card.locator('[data-em-act="save"]').click()
    assert "$evaluator_name is not a tag" in card.locator("[data-em-said]").inner_text()
    card.locator("[data-em-body]").fill("Hi $Applicant_name")
    card.locator('[data-em-act="preview"]').click()
    assert card.locator("[data-em-preview-body]").inner_text() == "Hi $Applicant_name"
    card.locator("[data-em-body]").fill("Fee: $")
    card.locator("[data-em-insert]").select_option("outcome")
    card.locator('[data-em-act="insert"]').click()
    assert card.locator("[data-em-body]").input_value() == "Fee: $ $outcome"


def test_the_side_card_s_outline_and_tags(page: Page) -> None:
    """Laid out as Form and Process (author, 2026-11-19): the Outline
    links every email and follows its chip; a tag clicked goes where the
    operator was last typing, refused on an email whose kind lacks it."""
    page.goto(EMAILS)
    side = page.locator(".fb-side")
    tag_said = side.locator("[data-em-tag-said]")
    side.locator('[data-em-tag="applicant_name"]').click()
    assert tag_said.inner_text() == "Click in an email's subject or body first."
    card = _card(page, OWED)
    card.locator("[data-em-body]").fill("Dear ")
    side.locator('[data-em-tag="applicant_name"]').click()
    assert card.locator("[data-em-body]").input_value() == "Dear $applicant_name"
    side.locator('[data-em-tag="evaluator_name"]').click()
    assert tag_said.inner_text() == f"$evaluator_name is not a tag of {OWED}."
    card.locator("[data-em-subject]").fill("Your outcome")
    card.locator('[data-em-act="save"]').click()
    chip = side.locator(f'[data-em-o-chip="{OWED}"]')
    assert chip.text_content() == "Written"  # CSS uppercases the chip
    assert side.locator("[data-em-counts]").inner_text() == "5 emails · 4 written · 1 owed"
    link = side.locator(".fb-o-item", has_text=OWED)
    assert link.get_attribute("href") == f"#{card.get_attribute('id')}"
