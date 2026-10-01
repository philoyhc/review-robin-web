"""Band 3's response-field rows, driven as an operator drives them.

Each test names the row of ``guide/post_azure_todo_checklist.md`` item 6
it repeats (``guide/archive/browser_test.md`` rung 3). A new session's instrument
starts with two response fields, "Rating" (Integer 1-5, required) and
"Comments".
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from playwright.sync_api import Page, expect

from ._builder import (
    names,
    open_unlocked,
    preview_headers,
    preview_input,
    rows,
    save,
    save_button,
)


def test_plus_inserts_a_default_named_row_below(
    page: Page, new_session: Callable[[], int]
) -> None:
    """Item 6, '"+" inserts below'."""
    card = open_unlocked(page, new_session())
    assert names(card) == ["Rating", "Comments"]

    rows(card).first.locator("[data-new-model-rf-add]").click()

    new_name = rows(card).nth(1).locator("[data-new-model-rf-name]")
    expect(rows(card)).to_have_count(3)
    expect(new_name).to_have_value("")
    expect(new_name).to_have_attribute("placeholder", "Field 1")
    expect(new_name).to_be_focused()
    assert preview_headers(card) == ["Rating", "Field 1", "Comments"]


def test_a_default_name_is_taken_with_arrow_and_kept_through_a_reload(
    page: Page, new_session: Callable[[], int]
) -> None:
    """Item 6, 'Default names'."""
    session_id = new_session()
    card = open_unlocked(page, session_id)
    rows(card).first.locator("[data-new-model-rf-add]").click()
    new_name = rows(card).nth(1).locator("[data-new-model-rf-name]")

    new_name.press("ArrowRight")
    expect(new_name).to_have_value("Field 1")
    new_name.fill("")
    expect(new_name).to_have_value("")
    expect(new_name).to_have_attribute("placeholder", "Field 1")
    new_name.press("ArrowRight")
    save(page, card)

    card = open_unlocked(page, session_id)
    assert names(card) == ["Rating", "Field 1", "Comments"]


def test_the_preview_follows_a_row_and_keeps_its_last_valid_shape(
    page: Page, new_session: Callable[[], int]
) -> None:
    """Item 6, 'The preview follows the row'."""
    card = open_unlocked(page, new_session())
    first = rows(card).first

    first.locator("[data-new-model-rf-name]").fill("Score")
    assert preview_headers(card) == ["Score", "Comments"]
    first.locator("[data-new-model-rf-bound=max]").fill("3")
    expect(preview_input(card, 0)).to_have_attribute("max", "3")

    first.locator("[data-new-model-rf-bound=max]").fill("0")
    expect(first).to_have_attribute(
        "title", "Max must be at least Min. The preview keeps the last valid shape."
    )
    expect(preview_input(card, 0)).to_have_attribute("max", "3")
    assert preview_headers(card) == ["Score", "Comments"]


def test_moving_a_row_up_reorders_the_preview_and_save_keeps_it(
    page: Page, new_session: Callable[[], int]
) -> None:
    """Item 6, 'Active and ▲ ▼' (the ▲ half; the hide-confirm needs saved
    responses and stays a hand check)."""
    session_id = new_session()
    card = open_unlocked(page, session_id)

    rows(card).nth(1).locator("[data-new-model-rf-move=up]").click()
    assert names(card) == ["Comments", "Rating"]
    assert preview_headers(card) == ["Comments", "Rating"]
    save(page, card)

    card = open_unlocked(page, session_id)
    assert names(card) == ["Comments", "Rating"]


def test_unticking_active_drops_the_column_and_save_keeps_it(
    page: Page, new_session: Callable[[], int]
) -> None:
    """Item 6, 'Active and ▲ ▼' (Active on a field with no responses)."""
    session_id = new_session()
    card = open_unlocked(page, session_id)

    rows(card).nth(1).locator("[data-new-model-rf-active]").uncheck()
    assert preview_headers(card) == ["Rating"]
    save(page, card)

    card = open_unlocked(page, session_id)
    expect(rows(card).nth(1).locator("[data-new-model-rf-active]")).not_to_be_checked()


@pytest.mark.parametrize(
    ("toggle", "state"),
    [
        ("data-new-model-rf-required", "data-required"),
        ("data-new-model-rf-help-visible", "data-help-visible"),
    ],
    ids=["R", "help"],
)
def test_one_toggle_alone_enables_save_and_persists(
    page: Page, new_session: Callable[[], int], toggle: str, state: str
) -> None:
    """Item 6, 'R and ≡ alone'."""
    session_id = new_session()
    card = open_unlocked(page, session_id)
    button = rows(card).first.locator(f"[{toggle}]")
    expect(button).to_have_attribute(state, "true")
    expect(save_button(card)).to_be_disabled()

    button.click()
    expect(button).to_have_attribute(state, "false")
    save(page, card)

    card = open_unlocked(page, session_id)
    expect(rows(card).first.locator(f"[{toggle}]")).to_have_attribute(state, "false")


def test_a_new_field_saved_twice_is_still_one_field_in_its_place(
    page: Page, new_session: Callable[[], int]
) -> None:
    """Item 6, 'A new field saves twice' and 'Order persists'."""
    session_id = new_session()
    card = open_unlocked(page, session_id)
    rows(card).first.locator("[data-new-model-rf-add]").click()
    rows(card).nth(1).locator("[data-new-model-rf-name]").fill("Effort")
    save(page, card)

    rows(card).nth(1).locator("[data-new-model-rf-name]").fill("Effort level")
    save(page, card)

    card = open_unlocked(page, session_id)
    assert names(card) == ["Rating", "Effort level", "Comments"]


def test_the_last_row_cannot_be_deleted(
    page: Page, new_session: Callable[[], int]
) -> None:
    """Item 6, 'The last row stays'."""
    card = open_unlocked(page, new_session())
    rows(card).nth(1).locator("[data-new-model-rf-delete]").click()

    expect(rows(card)).to_have_count(1)
    expect(rows(card).first.locator("[data-new-model-rf-delete]")).to_be_disabled()


def test_an_integer_rows_blank_step_saves_as_one(
    page: Page, new_session: Callable[[], int]
) -> None:
    """Item 6, 'Integer Step defaults to 1'."""
    session_id = new_session()
    card = open_unlocked(page, session_id)
    rows(card).first.locator("[data-new-model-rf-add]").click()
    row = rows(card).nth(1)
    row.locator("[data-new-model-rf-name]").fill("Count")
    row.locator("[data-new-model-rf-data-type]").select_option("integer")
    step = row.locator("[data-new-model-rf-bound=step]")
    expect(step).to_be_visible()
    expect(step).to_have_value("")
    expect(step).to_have_attribute("placeholder", "Step")

    save(page, card)
    expect(step).to_have_value("1")

    card = open_unlocked(page, session_id)
    expect(rows(card).nth(1).locator("[data-new-model-rf-bound=step]")).to_have_value("1")
