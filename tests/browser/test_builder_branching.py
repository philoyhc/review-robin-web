"""Branching in Band 3's response-field table, driven as an operator
drives it.

Each test names the row of ``guide/post_azure_todo_checklist.md`` item 6
it repeats (``guide/archive/browser_test.md`` rung 4). A new session's instrument
starts with "Rating" (Integer 1-5) above "Comments" (String).
"""

from __future__ import annotations

import re
from collections.abc import Callable

from playwright.sync_api import Locator, Page, expect

from ._builder import names, open_unlocked, rows, save


def _conditions(card: Locator) -> Locator:
    return card.locator("[data-new-model-rf-condition]")


def _governed(card: Locator) -> Locator:
    return card.locator("[data-new-model-rf-governed]")


def _levels(card: Locator) -> list[str]:
    return [
        row.get_attribute("data-new-model-rf-level") or ""
        for row in rows(card).all()
    ]


def test_fork_adds_a_pending_branch_under_a_number_field(
    page: Page, new_session: Callable[[], int]
) -> None:
    """Item 6, 'A branch with ⑂'."""
    card = open_unlocked(page, new_session())
    parent = rows(card).first

    parent.locator("[data-new-model-rf-fork]").click()

    condition = _conditions(card).first
    expect(condition).to_have_attribute("data-row-pending", "true")
    expect(condition).to_have_attribute(
        "title",
        "The branch condition needs a number. Save refuses the branch until it is fixed.",
    )
    expect(condition.locator("[data-new-model-rf-condition-mode]")).to_have_value("show")
    expect(_governed(card)).to_have_count(1)
    governed_name = _governed(card).first.locator("[data-new-model-rf-name]")
    expect(governed_name).to_have_attribute("placeholder", "Field 1")
    expect(parent.locator("[data-new-model-rf-delete]")).to_be_disabled()
    expect(
        parent.locator("[data-new-model-rf-data-type] option[value=string]")
    ).to_be_disabled()

    condition.locator("[data-new-model-rf-condition-value]").fill("4")
    expect(condition).not_to_have_attribute("data-row-pending", "true")


def test_join_and_detach_move_a_field_in_and_out_of_a_branch(
    page: Page, new_session: Callable[[], int]
) -> None:
    """Item 6, 'Join and detach'."""
    card = open_unlocked(page, new_session())
    rows(card).first.locator("[data-new-model-rf-fork]").click()
    _conditions(card).first.locator("[data-new-model-rf-condition-value]").fill("4")
    comments = rows(card).filter(has=page.locator("[data-new-model-rf-name][value=Comments]"))

    comments.locator("[data-new-model-rf-join]").click()
    expect(comments).to_have_attribute("data-new-model-rf-governed", "true")
    assert _levels(card) == ["0", "1", "1"]
    assert names(card)[2] == "Comments"

    comments.locator("[data-new-model-rf-join]").click()
    expect(comments).not_to_have_attribute("data-new-model-rf-governed", "true")
    assert _levels(card) == ["0", "1", "0"]

    # Detaching a branch's only field ends the branch, condition and all.
    _governed(card).first.locator("[data-new-model-rf-join]").click()
    expect(_governed(card)).to_have_count(0)
    expect(_conditions(card)).to_have_count(0)


def test_join_under_a_plain_field_starts_a_branch_without_a_new_row(
    page: Page, new_session: Callable[[], int]
) -> None:
    """The author, 2026-10-10, reversing guide/ux_refinements.md Item 3: ⑂
    starts a branch with a new field; ↰ under a plain number or List
    field starts one with the row itself, so no extra row appears."""
    card = open_unlocked(page, new_session())
    comments = rows(card).filter(has=page.locator("[data-new-model-rf-name][value=Comments]"))
    join = comments.locator("[data-new-model-rf-join]")
    # The field above is a plain Integer.
    expect(join).to_be_enabled()
    expect(join).to_have_attribute("title", "Start a branch on the field above with this field")
    expect(rows(card)).to_have_count(2)

    join.click()
    expect(comments).to_have_attribute("data-new-model-rf-governed", "true")
    expect(_conditions(card)).to_have_count(1)
    expect(rows(card)).to_have_count(2)
    expect(rows(card).first).to_have_attribute("data-new-model-rf-parent", "true")
    # The parent's bar starts at its + (ux_refinements Item 1), and the
    # condition's value box takes the focus.
    assert rows(card).first.evaluate(
        "r => r.querySelector('[data-new-model-rf-add]').closest('td')"
        ".classList.contains('rf-branch-bar-start')"
    )
    expect(card.locator("[data-new-model-rf-condition-value]").first).to_be_focused()

    # Detached again, it is plain under a String field: ↰ says why not.
    join.click()
    expect(_conditions(card)).to_have_count(0)
    rows(card).first.locator("[data-new-model-rf-data-type]").select_option("string")
    expect(join).to_be_disabled()
    expect(join).to_have_attribute("title", "The field above is String, so it can't have a branch")


def test_list_conditions_offer_is_and_is_not_and_name_a_missing_option(
    page: Page, new_session: Callable[[], int]
) -> None:
    """Item 6, 'List conditions'."""
    card = open_unlocked(page, new_session())
    parent = rows(card).first
    parent.locator("[data-new-model-rf-data-type]").select_option("list")
    parent.locator("[data-new-model-rf-bound=list]").fill("Red, Blue")
    parent.locator("[data-new-model-rf-fork]").click()
    condition = _conditions(card).first

    operator = condition.locator("[data-new-model-rf-condition-op]")
    expect(operator.locator("option")).to_have_text(["is", "is not"])
    operator.select_option("is_not")

    condition.locator("[data-new-model-rf-condition-value]").fill("Green")
    expect(condition).to_have_attribute("data-row-pending", "true")
    expect(condition).to_have_attribute("title", re.compile("Green"))


def test_unticking_a_parent_cascades_to_its_branch(
    page: Page, new_session: Callable[[], int]
) -> None:
    """Item 6, 'Active cascades'."""
    card = open_unlocked(page, new_session())
    parent = rows(card).first
    parent.locator("[data-new-model-rf-fork]").click()
    governed_active = _governed(card).first.locator("[data-new-model-rf-active]")
    expect(governed_active).to_be_checked()

    # The chip around the box is what a person clicks (ux_refinements
    # Item 1).
    parent.locator("label.rf-name-chip").uncheck()
    expect(governed_active).not_to_be_checked()
    expect(governed_active).to_be_disabled()

    parent.locator("label.rf-name-chip").check()
    expect(governed_active).to_be_checked()
    expect(governed_active).to_be_enabled()


def test_a_range_condition_takes_two_ends_and_says_when_it_opens(
    page: Page, new_session: Callable[[], int]
) -> None:
    """Item 6, 'Range conditions'."""
    card = open_unlocked(page, new_session())
    rows(card).first.locator("[data-new-model-rf-fork]").click()
    condition = _conditions(card).first
    high = condition.locator("[data-new-model-rf-condition-high]")
    expect(high).to_be_hidden()

    condition.locator("[data-new-model-rf-condition-op]").select_option("in_inc")
    expect(high).to_be_visible()
    condition.locator("[data-new-model-rf-condition-value]").fill("2")
    expect(condition).to_have_attribute(
        "title", "The range's high end needs a number. Save refuses the branch until it is fixed."
    )
    high.fill("4")
    expect(condition).not_to_have_attribute("data-row-pending", "true")
    expect(card.locator('[title="Opens when Rating ≥ 2 and ≤ 4"]').first).to_be_attached()

    condition.locator("[data-new-model-rf-condition-op]").select_option("out_exc")
    expect(card.locator('[title="Opens when Rating < 2 or > 4"]').first).to_be_attached()

    condition.locator("[data-new-model-rf-condition-op]").select_option("ge")
    expect(high).to_be_hidden()


def test_a_second_level_saves_and_a_third_is_not_offered(
    page: Page, new_session: Callable[[], int]
) -> None:
    """Item 6, 'Two levels of branching'."""
    session_id = new_session()
    card = open_unlocked(page, session_id)
    rows(card).first.locator("[data-new-model-rf-fork]").click()
    _conditions(card).first.locator("[data-new-model-rf-condition-value]").fill("4")
    middle = _governed(card).first
    middle.locator("[data-new-model-rf-name]").fill("Why")
    middle.locator("[data-new-model-rf-data-type]").select_option("integer")

    middle.locator("[data-new-model-rf-fork]").click()
    _conditions(card).nth(1).locator("[data-new-model-rf-condition-value]").fill("3")
    deepest = card.locator("[data-new-model-rf-level='2']").first
    deepest.locator("[data-new-model-rf-name]").fill("Detail")
    deepest.locator("[data-new-model-rf-data-type]").select_option("integer")
    # A third level is refused by not offering ⑂ at the second.
    expect(deepest.locator("[data-new-model-rf-fork]")).to_have_count(0)
    save(page, card)

    card = open_unlocked(page, session_id)
    assert names(card) == ["Rating", "Why", "Detail", "Comments"]
    assert _levels(card) == ["0", "1", "2", "0"]
