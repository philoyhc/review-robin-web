"""The instrument card around the rows: Cancel, Lock, Delete, display
fields and visibility, driven as an operator drives them.

Each test names the row of ``guide/post_azure_todo_checklist.md`` item 6
it repeats (``guide/archive/browser_test.md`` rung 3).
"""

from __future__ import annotations

import re
from collections.abc import Callable

import httpx
from playwright.sync_api import Dialog, Page, expect

from ._builder import (
    add_instrument,
    open_card,
    open_unlocked,
    rows,
    save,
    save_button,
    seed_rosters,
)


def test_cancel_removes_a_new_row(page: Page, new_session: Callable[[], int]) -> None:
    """Item 6, 'Cancel removes a new row'."""
    card = open_unlocked(page, new_session())
    rows(card).first.locator("[data-new-model-rf-add]").click()
    expect(rows(card)).to_have_count(3)

    page.once("dialog", lambda dialog: dialog.accept())
    card.locator("[data-new-model-cancel]:visible").first.click()

    card = page.locator("[data-instrument-card]").first
    expect(rows(card)).to_have_count(2)


def test_an_open_card_leaves_the_action_row_live_after_lock(
    page: Page, new_session: Callable[[], int]
) -> None:
    """Item 6, 'An open card doesn't lock the row'."""
    session_id = new_session()
    card = open_unlocked(page, session_id)
    rows(card).first.locator("[data-new-model-rf-name]").fill("Score")
    page.once("dialog", lambda dialog: dialog.accept())
    card.locator("[data-new-model-cancel]:visible").first.click()
    page.wait_for_url("**/instruments?editing=*")

    card = page.locator("[data-instrument-card]").first
    card.locator("[data-instrument-lock-toggle]:visible").first.click()
    expect(card).to_have_attribute("data-instrument-locked", "true")
    assert "editing" not in page.url
    for label in ("Replicate", "+Instrument"):
        expect(card.get_by_role("button", name=label, exact=True)).to_be_enabled()


def test_ticking_delete_leaves_the_card_clean(
    page: Page, api: httpx.Client, new_session: Callable[[], int]
) -> None:
    """Item 6, 'Delete's checkbox is clean'."""
    session_id = new_session()
    add_instrument(api, session_id)
    card = open_unlocked(page, session_id)
    dialogs: list[Dialog] = []
    page.on("dialog", lambda dialog: (dialogs.append(dialog), dialog.dismiss()))

    card.locator("input[name=confirm]").check()
    expect(save_button(card)).to_be_disabled()
    with page.expect_navigation():
        card.get_by_role("button", name="Delete", exact=True).click()

    expect(page.locator("[data-instrument-card]")).to_have_count(1)
    assert [d.type for d in dialogs] == []


def test_name_and_email_are_fixed_display_fields(
    page: Page, api: httpx.Client, new_session: Callable[[], int]
) -> None:
    """Item 6, 'Name and Email are fixed'."""
    session_id = new_session()
    seed_rosters(api, session_id)
    card = open_unlocked(page, session_id)
    display = card.locator("[data-new-model-df-row]")
    expect(display.nth(0)).to_have_attribute("data-key", "reviewee.name")
    expect(display.nth(1)).to_have_attribute("data-key", "reviewee.email_or_identifier")

    for fixed in (display.nth(0), display.nth(1)):
        checkbox = fixed.locator("[data-new-model-df-active]")
        expect(checkbox).to_be_checked()
        expect(checkbox).to_be_disabled()
        expect(fixed.locator("[data-new-model-df-move]")).to_have_count(0)


def _chip(card, audience: str, window: str):
    return card.locator(
        f"[data-new-model-vp-cycle-audience={audience}]"
        f"[data-new-model-vp-cycle-window={window}]"
    )


def test_visibility_is_edited_in_the_card_and_survives_lock_and_reload(
    page: Page, new_session: Callable[[], int]
) -> None:
    """Item 6, 'Visibility in the card' and 'Visibility preview repaints'."""
    session_id = new_session()
    card = open_unlocked(page, session_id)
    reviewees = _chip(card, "reviewee", "after_release")
    observers = _chip(card, "observer", "while_ongoing")
    expect(reviewees).to_have_attribute("data-new-model-vp-current-slug", "")

    reviewees.click()
    observers.click()
    expect(reviewees).to_have_attribute("data-new-model-vp-current-slug", "raw")
    expect(observers).to_have_attribute("data-new-model-vp-current-slug", "summarized")
    save(page, card)

    card.locator("[data-instrument-lock-toggle]:visible").first.click()
    locked_cell = card.locator("[data-new-model-vp-preview-cell=reviewee-after_release]")
    expect(locked_cell).to_be_visible()
    expect(locked_cell).to_have_text("Raw responses")
    expect(card.locator("[data-new-model-vp-observers-row]")).to_be_hidden()

    card = open_card(page, session_id)
    expect(
        card.locator("[data-new-model-vp-preview-cell=reviewee-after_release]")
    ).to_have_text("Raw responses")
    card.locator("[data-instrument-unlock-toggle]:visible").first.click()
    expect(_chip(card, "reviewee", "after_release")).to_have_attribute(
        "data-new-model-vp-current-slug", "raw"
    )
    expect(_chip(card, "observer", "while_ongoing")).to_have_attribute(
        "data-new-model-vp-current-slug", "summarized"
    )


def test_link3_cells_keep_their_markers_through_add_and_remove(
    page: Page, api: httpx.Client, new_session: Callable[[], int]
) -> None:
    """Ec9: adding a boundary cell turns the earlier one into a disabled
    AND and puts the X on the new last cell, keeping the cell-button
    class the template renders; removing it restores a lone, disabled X.
    """
    session_id = new_session()
    # Link 3 offers only populated reviewee / pair-context tags.
    response = api.post(
        f"/operator/sessions/{session_id}/reviewees/import",
        files={
            "file": (
                "reviewees.csv",
                b"RevieweeName,RevieweeEmail,RevieweeTag1\n"
                b"Carol,carol@example.edu,Blue\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    assert response.status_code in (200, 303), response.text
    card = open_unlocked(page, session_id)
    mode = card.locator("[data-new-model-unit-mode]").first
    for _ in range(3):
        if mode.get_attribute("data-new-model-unit-mode") == "group":
            break
        mode.click()
    expect(mode).to_have_attribute("data-new-model-unit-mode", "group")
    actions = card.locator("[data-new-model-cell-action]")
    expect(actions).to_have_count(1)
    expect(actions.first).to_be_disabled()

    card.locator("[data-new-model-unit-add]").first.click()
    expect(actions).to_have_count(2)
    expect(actions.nth(0)).to_have_text("AND")
    expect(actions.nth(0)).to_be_disabled()
    expect(actions.nth(1)).to_have_text("X")
    expect(actions.nth(1)).to_be_enabled()
    for i in range(2):
        expect(actions.nth(i)).to_have_class(re.compile(r"\bcohort-cell-btn\b"))

    # The next add clones the first cell, now an AND: the refresh must
    # still hand the new last cell a working X.
    card.locator("[data-new-model-unit-add]").first.click()
    expect(actions).to_have_count(3)
    expect(actions.nth(1)).to_have_text("AND")
    expect(actions.nth(1)).to_be_disabled()
    expect(actions.nth(2)).to_have_text("X")
    actions.nth(2).click()
    expect(actions).to_have_count(2)
    expect(actions.nth(1)).to_have_text("X")

    actions.nth(1).click()
    expect(actions).to_have_count(1)
    expect(actions.first).to_have_text("X")
    expect(actions.first).to_be_disabled()
