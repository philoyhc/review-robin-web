"""The Form page in a real Chromium (segment AD1B, rung 2): cards open
and close, the type menu swaps a card's fields, the toggles flip, and a
card's summary and the Outline follow every edit. Without a Chromium
build the test skips, saying why; ``RRW_REQUIRE_BROWSER=1`` (set by CI)
turns that skip into a failure."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Error, Locator, Page, Route, sync_playwright

from applydesk.tests._host import host_with
from applydesk.tests.test_form import SUMMARY_CASES

ORIGIN = "http://applydesk.test"
FORM = f"{ORIGIN}/applydesk/operator/exercises/wa9juxbc2t/form"
BLANK = f"{ORIGIN}/applydesk/operator/exercises/n5wg8tjr3e/form"


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
        # A tab the page opens (Preview) reports its errors too.
        tab.context.on("page", lambda p: p.on("pageerror", lambda exc: errors.append(str(exc))))
        tab.context.route(f"{ORIGIN}/**", serve)
        yield tab
        browser.close()
        assert errors == [], f"page errors: {errors}"


def _card(page: Page, label: str) -> Locator:
    return page.locator(".fc", has=page.locator(f'[data-sum="label"]:text-is("{label}")'))


def test_a_card_opens_and_closes(page: Page) -> None:
    page.goto(FORM)
    card = _card(page, "Months the project will run")
    toggle = card.locator("[data-fc-toggle]")
    assert toggle.get_attribute("aria-expanded") == "false"
    assert not card.locator('[data-f="label"]').is_visible()
    toggle.click()
    assert toggle.get_attribute("aria-expanded") == "true"
    assert card.locator('[data-f="label"]').is_visible()
    assert card.locator('[data-f="step"]').is_visible()  # an Integer's fields
    assert not card.locator('[data-f="options"]').is_visible()
    toggle.click()
    assert not card.locator('[data-f="label"]').is_visible()


def test_editing_a_card_updates_its_summary_and_the_outline(page: Page) -> None:
    page.goto(FORM)
    # By position: the label it is found by is about to change.
    card = page.locator('.fc[data-kind="field"]').nth(4)
    assert card.locator('[data-sum="label"]').inner_text() == "Months the project will run"
    card.locator("[data-fc-toggle]").click()
    card.locator('[data-f="max"][data-g="number"]').fill("12")
    card.locator('[data-f="label"]').fill("Months the project will take")
    card.locator("[data-fc-toggle]").click()
    assert card.locator('[data-sum="type"]').text_content() == "Integer · 1 to 12, step 1"
    assert card.locator('[data-sum="label"]').inner_text() == "Months the project will take"
    assert "Months the project will take" in page.locator("[data-fb-outline]").inner_text()


def test_the_type_menu_swaps_a_card_s_fields(page: Page) -> None:
    page.goto(FORM)
    card = _card(page, "Months the project will run")
    card.locator("[data-fc-toggle]").click()
    card.locator('[data-f="type"]').select_option("list")
    assert card.get_attribute("data-type") == "list"
    assert card.locator('[data-f="options"]').is_visible()
    assert not card.locator('[data-f="step"]').is_visible()
    # The question, help text, visibility and Required are kept.
    assert card.locator('[data-f="label"]').input_value() == "Months the project will run"
    card.locator('[data-f="options"]').fill("One, Two")
    card.locator('[data-f="exclusive"][data-v="false"]').click()
    assert card.locator('[data-sum="type"]').text_content() == "List · choose any · One, Two"
    card.locator('[data-f="type"]').select_option("text")
    assert card.locator(".l-t", has_text="Title").first.is_visible()
    assert not card.locator('[data-f="required"]').is_visible()
    assert (
        card.locator('[data-sum="type"]').text_content() == "Title and Description · display only"
    )


def test_required_and_visibility_toggle(page: Page) -> None:
    page.goto(FORM)
    card = _card(page, "Matriculation number")
    card.locator("[data-fc-toggle]").click()
    required = card.locator('[data-f="required"]')
    assert required.get_attribute("aria-pressed") == "true"
    required.click()
    assert required.get_attribute("aria-pressed") == "false"
    assert card.locator('[data-sum="required"]').text_content() == "Optional"
    card.locator('[data-f="shown"][data-v="true"]').click()
    assert card.locator('[data-sum="shown"]').text_content() == "Shown to reviewers"
    assert "Matriculation number" in page.locator("[data-fb-outline]").inner_text()


def test_the_photo_ratio_sets_the_kept_size(page: Page) -> None:
    page.goto(FORM)
    card = _card(page, "Photo")
    card.locator("[data-fc-toggle]").click()
    card.locator('[data-f="ratio_w"]').fill("1")
    card.locator('[data-f="ratio_h"]').fill("1")
    assert card.locator('[data-sum="kept"]').text_content() == (
        "Kept as a 600 × 600 JPEG: 600 px on its longer side."
    )
    assert card.locator('[data-sum="type"]').text_content() == "Photo · 1:1, kept 600 × 600"


def test_the_outline_counts_the_form(page: Page) -> None:
    page.goto(FORM)
    assert page.locator("[data-fb-counts]").inner_text() == (
        "2 pages · 2 sections · 9 questions · 6 required"  # a text block is no question
    )
    page.goto(BLANK)
    assert page.locator("[data-fb-counts]").inner_text() == (
        "1 page · 0 sections · 1 question · 0 required"
    )
    assert page.locator('.fc[data-kind="field"] [data-f="label"]').is_visible()  # opened


# --- Rung 3: moves, the last-card rule, reordering, Preview ---


def _labels(page: Page) -> list[str]:
    # textContent: an open card hides its summary, which inner_text reads as "".
    return page.eval_on_selector_all(
        '#fb-cards > .fc [data-sum="label"]', "els => els.map(e => e.textContent)"
    )


def _kinds(page: Page) -> list[str]:
    return page.eval_on_selector_all(
        "#fb-cards > [data-kind]", "els => els.map(e => e.dataset.kind)"
    )


def test_new_adds_an_open_string_card_after_this_one(page: Page) -> None:
    page.goto(FORM)
    card = _card(page, "Project title")
    card.locator("[data-fc-toggle]").click()
    card.locator('[data-fc-act="new"]').click()
    labels = _labels(page)
    added = page.locator("#fb-cards > .fc").nth(labels.index("Project title") + 1)
    assert added.get_attribute("data-type") == "string"
    assert added.get_attribute("data-open") is not None
    assert added.locator('[data-f="label"]').evaluate("e => e === document.activeElement")
    assert added.locator('[data-sum="shown"]').text_content() == "Not shown"  # the safer side
    added.locator('[data-f="label"]').fill("Supervisor's name")
    assert "Supervisor's name" in page.locator("[data-fb-outline]").inner_text()
    assert "10 questions" in page.locator("[data-fb-counts]").inner_text()


def test_replicate_copies_the_card(page: Page) -> None:
    page.goto(FORM)
    card = _card(page, "Months the project will run")
    card.locator("[data-fc-toggle]").click()
    card.locator('[data-fc-act="replicate"]').click()
    copies = _card(page, "Months the project will run")
    assert copies.count() == 2
    copy = copies.nth(1)
    assert copy.get_attribute("data-type") == "integer"
    assert copy.locator('[data-f="max"][data-g="number"]').input_value() == "6"
    assert copy.locator('[data-sum="type"]').text_content() == "Integer · 1 to 6, step 1"


def test_section_and_page_break_are_added_after_the_card(page: Page) -> None:
    page.goto(FORM)
    card = _card(page, "Summary")
    card.locator("[data-fc-toggle]").click()
    card.locator('[data-fc-act="pagebreak"]').click()
    card.locator('[data-fc-act="section"]').click()
    kinds = _kinds(page)
    at = page.eval_on_selector_all(
        "#fb-cards > [data-kind]",
        "els => els.findIndex(e =>"
        " (e.querySelector('[data-sum=label]') || {}).textContent === 'Summary')",
    )
    assert kinds[at + 1 : at + 3] == ["section", "pagebreak"]
    section = page.locator("#fb-cards > [data-kind]").nth(at + 1)
    section.locator('[data-f="label"]').fill("Plans")
    outline = page.locator("[data-fb-outline]").inner_text()
    assert "Plans" in outline and "Page 3" in outline
    assert page.locator("[data-fb-counts]").inner_text().startswith("3 pages · 3 sections")


def test_delete_removes_a_card_and_the_last_card_stays(page: Page) -> None:
    page.goto(FORM)
    card = _card(page, "Methods")
    card.locator("[data-fc-toggle]").click()
    card.locator('[data-fc-act="delete"]').click()
    assert "Methods" not in _labels(page)
    page.locator(".fc-break [data-fc-act=delete]").click()  # a page break's Remove
    assert "pagebreak" not in _kinds(page)
    page.goto(BLANK)
    only = page.locator('#fb-cards > .fc[data-kind="field"]')
    assert only.locator('[data-fc-act="delete"]').is_disabled()
    assert only.locator('[data-fc-act="delete"]').get_attribute("title") == (
        "A form keeps at least one card"
    )
    only.locator('[data-fc-act="new"]').click()
    dels = page.locator('#fb-cards > .fc[data-kind="field"] [data-fc-act="delete"]')
    assert dels.nth(0).is_enabled() and dels.nth(1).is_enabled()
    dels.nth(1).click()
    assert page.locator('#fb-cards > .fc[data-kind="field"] [data-fc-act="delete"]').is_disabled()


def test_a_card_is_dragged_by_its_handle(page: Page) -> None:
    page.goto(FORM)
    before = _labels(page)
    grip = _card(page, "Field of study").locator("[data-fc-grip]")
    target = _card(page, "Project title")
    page.set_viewport_size({"width": 1280, "height": 1400})  # both on screen
    g = grip.bounding_box()
    t = target.bounding_box()
    assert g is not None and t is not None
    page.mouse.move(g["x"] + g["width"] / 2, g["y"] + g["height"] / 2)
    page.mouse.down()
    page.mouse.move(g["x"] + 5, t["y"] + 4, steps=12)  # into the top half of Project title
    page.mouse.up()
    after = _labels(page)
    assert after.index("Field of study") == after.index("Project title") - 1
    assert sorted(after) == sorted(before)
    outline = page.locator("[data-fb-outline] .fb-o-item").all_inner_texts()
    assert outline.index("Field of study") < outline.index("Project title")


def test_a_card_moves_with_the_arrow_keys(page: Page) -> None:
    page.goto(FORM)
    grip = _card(page, "Summary").locator("[data-fc-grip]")
    grip.focus()
    page.keyboard.press("ArrowUp")
    labels = _labels(page)
    assert labels.index("Summary") == labels.index("Project title") - 1
    assert grip.evaluate("e => e === document.activeElement")
    page.keyboard.press("ArrowDown")
    labels = _labels(page)
    assert labels.index("Summary") == labels.index("Project title") + 1
    page.keyboard.press("ArrowDown")
    labels = _labels(page)
    assert labels.index("Summary") == labels.index("Methods") + 1


# Fills one card from a FormCard's fields, as an operator would: the
# type menu first (it empties the new type's fields), then each field.
_FILL = """([card, c]) => {
  const type = card.querySelector('[data-f="type"]');
  type.value = c.type;
  type.dispatchEvent(new Event("change", { bubbles: true }));
  const num = ["integer", "decimal"].includes(c.type);
  const g = c.type === "string" ? "string" : num ? "number" : c.type === "people" ? "people" : "";
  for (const f of ["min", "max", "step", "options", "ratio_w", "ratio_h"]) {
    const el = card.querySelector(`[data-f="${f}"]:not([data-g]), [data-f="${f}"][data-g="${g}"]`);
    if (el) el.value = c[f];
  }
  card.querySelector('[data-f="pool"]').value = c.pool;
  card.querySelector(`[data-f="exclusive"][data-v="${c.exclusive}"]`).click();
  card.querySelector('[data-f="min"]').dispatchEvent(new Event("input", { bubbles: true }));
  return card.querySelector('[data-sum="type"]').textContent;
}"""


def test_the_script_s_summaries_match_the_server_s(page: Page) -> None:
    page.goto(FORM)
    # Every server-rendered summary survives an edit unchanged.
    rendered = page.eval_on_selector_all(
        '#fb-cards .fc[data-kind="field"]',
        """cards => cards.map(c => {
          const before = c.querySelector('[data-sum="type"]').textContent;
          c.querySelector('[data-f="label"]').dispatchEvent(new Event("input", { bubbles: true }));
          return [before, c.querySelector('[data-sum="type"]').textContent];
        })""",
    )
    assert rendered and all(before == after for before, after in rendered)
    # And every case card_summary is held to, typed into a card.
    card = page.locator('#fb-cards .fc[data-kind="field"]').first.element_handle()
    for c, expected in SUMMARY_CASES:
        fields = {
            k: getattr(c, k)
            for k in ("type", "min", "max", "step", "options", "ratio_w", "ratio_h", "pool")
        }
        fields["exclusive"] = "true" if c.exclusive else "false"
        assert page.evaluate(_FILL, [card, fields]) == expected, c


def test_a_type_change_resets_choose_one(page: Page) -> None:
    page.goto(FORM)
    card = _card(page, "Field of study")
    card.locator("[data-fc-toggle]").click()
    card.locator('[data-f="exclusive"][data-v="false"]').click()
    card.locator('[data-f="type"]').select_option("string")
    card.locator('[data-f="type"]').select_option("list")
    assert (
        card.locator('[data-f="exclusive"][data-v="true"]').get_attribute("aria-pressed") == "true"
    )


def test_handles_name_their_card_and_moves_are_announced(page: Page) -> None:
    page.goto(FORM)
    card = _card(page, "Summary")
    grip = card.locator("[data-fc-grip]")
    assert (grip.get_attribute("aria-label") or "").startswith("Move Summary:")
    assert card.locator("[data-fc-toggle]").get_attribute("aria-label") == "Expand Summary"
    grip.focus()
    page.keyboard.press("ArrowUp")
    assert (page.locator("[data-fb-live]").text_content() or "").startswith("Moved Summary to ")


# --- Iteration: Preview in its own tab; the form's own card collapses ---
PREVIEW = f"{FORM}/preview"


def _the_applicant_form(body: Locator) -> None:
    """What both sources draw for the sample form: pages, a number with
    its bounds, a list as radios, a photo frame, the reviewers' note."""
    assert body.locator("h2.fb-pv-form").inner_text() == "Application form"
    assert body.locator("h3.fb-pv-section").all_inner_texts() == ["About the project", "About you"]
    assert body.locator(".fb-pv-page").all_inner_texts() == ["PAGE 1", "PAGE 2"]
    months = body.get_by_label("Months the project will run")
    assert months.get_attribute("type") == "number" and months.get_attribute("max") == "6"
    assert body.get_by_role("radio", name="Engineering").count() == 1
    assert body.locator(".fb-pv-frame").count() == 1
    assert "Reviewers see your answer." in body.inner_text()


def test_preview_opens_a_tab_with_the_form_as_it_stands(page: Page) -> None:
    page.goto(FORM)
    card = _card(page, "Project title")
    card.locator("[data-fc-toggle]").click()
    # A bad maximum previews as a box, and does not stop the tab drawing.
    card.locator('[data-f="max"][data-g="string"]').fill("-1")
    label = card.locator('[data-f="label"]').element_handle()
    label.fill("Working title")
    with page.context.expect_page() as opened:
        page.locator("[data-fb-preview-tab]").click()
    tab = opened.value
    tab.wait_for_load_state()
    body = tab.locator("[data-fb-preview-body]")
    _the_applicant_form(body)
    assert body.get_by_label("Working title").evaluate("e => e.tagName") == "TEXTAREA"
    assert "unsaved" in (tab.locator("[data-pv-source]").text_content() or "")
    # A reload picks up later edits.
    label.fill("Final title")
    tab.reload()
    assert tab.locator("[data-fb-preview-body]").get_by_label("Final title").count() == 1


def test_preview_on_its_own_shows_the_sample_form(page: Page) -> None:
    page.goto(PREVIEW)
    _the_applicant_form(page.locator("[data-fb-preview-body]"))
    assert "sample form" in (page.locator("[data-pv-source]").text_content() or "")


def test_preview_of_another_exercise_ignores_this_form(page: Page) -> None:
    page.goto(FORM)
    _card(page, "Project title").locator("[data-fc-toggle]").click()
    _card(page, "Project title").locator('[data-f="label"]').fill("Not for the blank form")
    with page.context.expect_page() as opened:
        page.evaluate(f"window.open('{BLANK}/preview', 'other')")
    other = opened.value
    other.wait_for_load_state()
    assert "sample form" in (other.locator("[data-pv-source]").text_content() or "")
    assert other.locator("[data-fb-preview-body]").get_by_label("Untitled question").count() == 1


def test_the_form_s_own_card_collapses(page: Page) -> None:
    page.goto(BLANK)
    assert page.locator('[data-kind="title"]').get_attribute("data-open") is not None
    page.goto(FORM)
    title = page.locator('[data-kind="title"]')
    toggle = title.locator("[data-fc-toggle]")
    assert toggle.get_attribute("aria-label") == "Expand the form's title and description"
    assert not title.locator('[data-fb="title"]').is_visible()
    assert title.locator('[data-sum="title"]').inner_text() == "Application form"
    toggle.click()
    assert toggle.get_attribute("aria-expanded") == "true"
    assert toggle.get_attribute("aria-label") == "Collapse the form's title and description"
    title.locator('[data-fb="title"]').fill("Travel grant form")
    title.locator("[data-fc-toggle]").click()
    assert title.locator('[data-sum="title"]').inner_text() == "Travel grant form"
    assert not title.locator('[data-fb="title"]').is_visible()


def test_preview_takes_the_cards_place_and_back(page: Page) -> None:
    page.goto(FORM)
    button = page.locator("[data-fb-preview]")
    # Save sits beside it.
    assert button.locator("xpath=following-sibling::button").inner_text() == "Save"
    button.click()
    assert button.inner_text() == "Back to edit"
    assert not page.locator("#fb-cards").is_visible()
    preview = page.locator("#fb-preview")
    assert preview.is_visible()
    # The form alone: no heading or note of its own.
    assert "Nothing typed here is kept" not in preview.inner_text()
    first = preview.locator(":scope > *").first
    assert first.get_attribute("data-fb-preview-body") is not None
    assert (
        preview.locator("[data-fb-preview-body] > *").first.evaluate("e => e.className")
        == "fb-pv-form"
    )
    _the_applicant_form(preview.locator("[data-fb-preview-body]"))
    button.click()
    assert button.inner_text() == "Preview"
    assert page.locator("#fb-cards").is_visible() and not preview.is_visible()
    # An Outline click while previewing goes back to the card.
    button.click()
    page.locator(".fb-o-item", has_text="Methods").click()
    assert page.locator("#fb-cards").is_visible() and button.inner_text() == "Preview"
    focused = page.evaluate(
        "document.activeElement.closest('.fc').querySelector('[data-sum=label]').textContent"
    )
    assert focused == "Methods"


def test_text_boxes_grow_to_fit_without_a_handle(page: Page) -> None:
    page.goto(FORM)
    card = _card(page, "Summary")
    card.locator("[data-fc-toggle]").click()
    help_box = card.locator('[data-f="help"]')
    assert help_box.evaluate("e => getComputedStyle(e).resize") == "none"
    before = help_box.evaluate("e => e.offsetHeight")
    help_box.fill("A line\n" * 8)
    after = help_box.evaluate("e => e.offsetHeight")
    assert after > before
    assert help_box.evaluate("e => e.scrollHeight <= e.clientHeight")
    # A box in a card that opens from collapsed is sized to its text.
    long = _card(page, "Your proposed project")
    long.locator("[data-fc-toggle]").click()
    box = long.locator('[data-f="help"]')
    page.wait_for_function(
        "e => e.style.height !== '' && e.scrollHeight <= e.clientHeight", arg=box.element_handle()
    )
    # And a new card's box, after + New.
    card.locator('[data-fc-act="new"]').click()
    fresh = page.locator('#fb-cards .fc[data-open] [data-f="help"]').nth(1)
    fresh.fill("One\nTwo\nThree\nFour")
    assert fresh.evaluate("e => e.scrollHeight <= e.clientHeight")


def test_the_form_title_is_larger_than_a_card_s(page: Page) -> None:
    page.goto(FORM)
    size = "e => parseFloat(getComputedStyle(e).fontSize)"
    title = page.locator('[data-sum="title"]').evaluate(size)
    assert title > _card(page, "Summary").locator('[data-sum="label"]').evaluate(size)


# --- Iteration: Select people ---
def _people_box(page: Page, label: str) -> Locator:
    page.goto(FORM)
    page.locator("[data-fb-preview]").click()
    return page.locator("#fb-preview").get_by_role("textbox", name=label)


def test_select_people_turns_names_into_pills(page: Page) -> None:
    page.goto(FORM)
    card = _card(page, "Preferred reviewer")
    card.locator("[data-fc-toggle]").click()
    # Open the question to anyone in the institution, up to three.
    card.locator('[data-f="max"][data-g="people"]').fill("3")
    card.locator('[data-f="pool"]').select_option("institution")
    assert (
        card.locator('[data-sum="type"]').text_content()
        == "Select people · 1 to 3 people · Institution-wide"
    )
    page.locator("[data-fb-preview]").click()
    preview = page.locator("#fb-preview")
    box = preview.get_by_role("textbox", name="Preferred reviewer")
    box.press_sequentially("Daniel Koh, PRIYA.RAMAN@example.edu, Nobody Here,")
    tokens = preview.locator(".token")
    assert [t.split("×")[0].strip() for t in tokens.all_inner_texts()] == [
        "Daniel Koh",
        "Priya Raman",
    ]
    assert box.input_value().startswith("Nobody Here")
    assert "Not found in the institution: Nobody Here." in preview.inner_text()
    box.fill("")
    box.press_sequentially("Zoe Tan")
    box.press("Enter")
    assert tokens.count() == 3
    # Three is the most: the box takes no more until one is removed.
    assert not box.is_visible()
    preview.get_by_role("button", name="Remove Daniel Koh").click()
    assert tokens.count() == 2 and box.is_visible()


def test_select_people_keeps_to_its_pool(page: Page) -> None:
    box = _people_box(page, "Preferred reviewer")
    preview = page.locator("#fb-preview")
    assert "Choose 1 person from Reviewer pool." in preview.inner_text()
    box.press_sequentially("Daniel Koh,")
    assert preview.locator(".token").count() == 0
    assert "Not found in Reviewer pool: Daniel Koh." in preview.inner_text()
    box.fill("")
    box.press_sequentially("Dr Omar Aziz,")
    assert preview.locator(".token").count() == 1 and not box.is_visible()


def test_select_people_drops_names_past_the_most_and_says_so(page: Page) -> None:
    box = _people_box(page, "Preferred reviewer")
    preview = page.locator("#fb-preview")
    box.focus()
    box.fill("Dr Omar Aziz, Dr Hana Ito,")  # pasted at once
    assert preview.locator(".token").count() == 1
    assert "At most 1 person; not added: Dr Hana Ito." in preview.inner_text()
    # Nothing is left in a hidden box; focus moved to the pill's button.
    hidden = preview.locator(".token-input")
    assert not hidden.is_visible() and hidden.input_value() == ""
    assert page.evaluate("document.activeElement.getAttribute('aria-label')") == (
        "Remove Dr Omar Aziz"
    )
    # The group keeps the question's name once the box is full.
    group = preview.get_by_role("group", name="Preferred reviewer")
    assert group.count() == 1


def test_select_people_says_already_chosen(page: Page) -> None:
    page.goto(FORM)
    card = _card(page, "Preferred reviewer")
    card.locator("[data-fc-toggle]").click()
    card.locator('[data-f="max"][data-g="people"]').fill("")
    page.locator("[data-fb-preview]").click()
    preview = page.locator("#fb-preview")
    box = preview.get_by_role("textbox", name="Preferred reviewer")
    box.press_sequentially("Dr Ruth Kahn, ruth.kahn@example.edu,")
    assert preview.locator(".token").count() == 1
    assert "Already chosen: Dr Ruth Kahn." in preview.inner_text()


def test_a_full_box_keeps_no_unfound_text(page: Page) -> None:
    # Codex: an unfound name before the one that fills the box was left
    # in the hidden input.
    box = _people_box(page, "Preferred reviewer")
    preview = page.locator("#fb-preview")
    box.focus()
    box.fill("Nobody Here, Dr Omar Aziz,")
    assert preview.locator(".token").count() == 1
    hidden = preview.locator(".token-input")
    assert not hidden.is_visible() and hidden.input_value() == ""
    assert "not added: Nobody Here." in preview.inner_text()


def test_a_card_s_buttons_sit_flush_right_in_order(page: Page) -> None:
    page.goto(FORM)
    card = _card(page, "Months the project will run")
    card.locator("[data-fc-toggle]").click()
    foot = card.locator(".fc-foot")
    buttons = foot.locator("button")
    assert buttons.all_inner_texts() == [
        "Replicate",
        "+ New",
        "+ Section",
        "+ Page break",
        "Delete",
    ]
    lefts = [b.evaluate("e => e.getBoundingClientRect().left") for b in buttons.all()]
    assert lefts == sorted(lefts)
    edge = foot.evaluate("e => e.getBoundingClientRect().right")
    last = buttons.last.evaluate("e => e.getBoundingClientRect().right")
    assert abs(edge - last) < 1
    # A gap between the buttons, not a gap at the left pushing Delete away.
    gaps = [b - a for a, b in zip(lefts, lefts[1:], strict=False)]
    assert max(gaps) < 200


# --- Segment AD1F rung 2: + New panel on a Select people card (ruling 19) ---
def _new_panel(page: Page) -> tuple[Locator, Locator]:
    page.goto(FORM)
    card = _card(page, "Preferred reviewer")
    card.locator("[data-fc-toggle]").click()
    card.locator('[data-f="pool"]').select_option("__new")
    return card, card.locator("[data-newpanel]")


def test_new_panel_opens_its_box_and_keeps_the_choice(page: Page) -> None:
    card, box = _new_panel(page)
    assert box.is_visible()
    assert card.locator('[data-f="pool"]').input_value() == "pool"
    summary = card.locator('[data-sum="type"]').text_content()
    assert summary == "Select people · exactly 1 person · Reviewer pool"
    box.get_by_role("button", name="Cancel").click()
    assert not box.is_visible()
    assert card.locator('[data-f="pool"]').input_value() == "pool"
    card.locator('[data-f="pool"]').select_option("__new")
    box.locator('[data-np="name"]').press("Escape")
    assert not box.is_visible()


def test_new_panel_refuses_what_it_cannot_make(page: Page) -> None:
    _, box = _new_panel(page)
    err = box.locator("[data-np-err]")
    box.get_by_role("button", name="Create panel").click()
    assert err.text_content() == "Name the panel. Add at least one email."
    box.locator('[data-np="name"]').fill("panel a")
    box.locator('[data-np="members"]').fill("kim@example.edu\nnot-an-email\nKIM@example.edu")
    box.get_by_role("button", name="Create panel").click()
    assert err.text_content() == (
        "A panel is already called panel a. Not an email: not-an-email."
        " Listed twice: KIM@example.edu."
    )
    assert box.is_visible()


def test_new_panel_is_made_chosen_and_offered_everywhere(page: Page) -> None:
    card, box = _new_panel(page)
    box.locator('[data-np="name"]').fill("Panel C")
    box.locator('[data-np="members"]').fill("Kim Lee <kim.lee@example.edu>, sam.ho@example.edu")
    box.get_by_role("button", name="Create panel").click()
    assert not box.is_visible()
    menu = card.locator('[data-f="pool"]')
    assert menu.evaluate("s => s.options[s.selectedIndex].textContent") == "Panel C"
    assert card.locator('[data-sum="type"]').text_content() == (
        "Select people · exactly 1 person · Panel C"
    )
    live = page.locator("[data-np-live]").text_content() or ""
    assert "Panel C made, 2 people, and chosen." in live
    # A card added after offers it too, before + New panel….
    card.locator('[data-fc-act="new"]').click()
    added = page.locator("#fb-cards .fc[data-open]").nth(1)
    added.locator('[data-f="type"]').select_option("people")
    options = added.locator('[data-f="pool"] option').all_text_contents()
    assert options[-2:] == ["Panel C", "+ New panel…"]
    # Preview looks people up in it.
    page.locator("[data-fb-preview]").click()
    preview = page.locator("#fb-preview")
    assert "Choose 1 person from Panel C." in preview.inner_text()
    box = preview.get_by_role("textbox", name="Preferred reviewer")
    box.press_sequentially("Kim Lee,")
    assert preview.locator(".token").count() == 1
    # And the snapshot hands it to the preview tab.
    snap = page.evaluate("JSON.parse(window.applydeskFormSnapshot())")
    assert snap["pools"] == {
        "new-1": {
            "name": "Panel C",
            "members": [
                ["Kim Lee", "kim.lee@example.edu"],
                ["sam.ho@example.edu", "sam.ho@example.edu"],
            ],
        }
    }
