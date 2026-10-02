"""The Extract data page's shape buttons, shown and hidden (post_assessment_1oct E6).

A saved shape's card shows Edit and hides Save until Edit is pressed;
Cancel puts them back. The hidden button used to be hidden by an inline
``style="display: none;"``, which ``spec/ui_elements.md`` §6 calls a
defect on a button, and is now the ``hidden`` attribute, so the card's
script flips ``hidden`` rather than ``style.display``. This drives that
script in a browser, since the template test cannot run it.

E36 added a confirm tick that gates each card's Delete; the second test
drives that gate and the page's clearing of it on Cancel or a change of
shape.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
from playwright.sync_api import Page, expect


def test_edit_and_cancel_swap_the_saved_shapes_buttons(
    page: Page, api: httpx.Client, new_session: Callable[[], int]
) -> None:
    session_id = new_session()
    response = api.post(
        f"/operator/sessions/{session_id}/extract-data/shapes",
        json={
            "name": "By reviewer",
            "axis": "reviewer",
            "instrument_id": None,
            "response_field_id": None,
            "column_chip_slots": ["reviewer:name", "reviewer:email"],
        },
    )
    assert response.status_code == 201, response.text
    shape_id = response.json()["id"]

    page.goto(f"/operator/sessions/{session_id}/extract-data")
    # By id, not by mode: Edit flips ``data-shape-mode`` to "edit".
    card = page.locator(f'[data-shape][data-shape-id="{shape_id}"]')
    expect(card).to_have_attribute("data-shape-mode", "saved")
    edit = card.locator("[data-shape-edit]")
    save = card.locator("[data-shape-save]")
    expect(edit).to_be_visible()
    expect(save).to_be_hidden()

    edit.click()
    expect(save).to_be_visible()
    expect(edit).to_be_hidden()

    card.locator("[data-shape-cancel]").click()
    expect(edit).to_be_visible()
    expect(save).to_be_hidden()


def _save_shape(api: httpx.Client, session_id: int, name: str) -> int:
    response = api.post(
        f"/operator/sessions/{session_id}/extract-data/shapes",
        json={
            "name": name,
            "axis": "reviewer",
            "instrument_id": None,
            "response_field_id": None,
            "column_chip_slots": ["reviewer:name", "reviewer:email"],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_delete_waits_for_its_confirm_tick_and_the_tick_resets(
    page: Page, api: httpx.Client, new_session: Callable[[], int]
) -> None:
    """E36: each shape's Delete stays disabled until its own confirm
    box is ticked, and Cancel or a switch of shape clears the tick
    (and with it, Delete) again. The pairing is the app-wide one in
    ``base.html``; what this pins is the page clearing the tick and
    each card keying its own pair."""
    session_id = new_session()
    first_id = _save_shape(api, session_id, "First")
    second_id = _save_shape(api, session_id, "Second")

    page.goto(f"/operator/sessions/{session_id}/extract-data")
    first = page.locator(f'[data-shape][data-shape-id="{first_id}"]')
    second = page.locator(f'[data-shape][data-shape-id="{second_id}"]')
    first_delete = first.locator("[data-shape-delete]")
    second_delete = second.locator("[data-shape-delete]")
    first_tick = first.locator("[data-delete-confirm]")
    second_tick = second.locator("[data-delete-confirm]")

    expect(first_delete).to_be_disabled()
    expect(second_delete).to_be_disabled()

    # A tick opens only its own card's Delete.
    first_tick.check()
    expect(first_delete).to_be_enabled()
    expect(first_delete).not_to_have_attribute("aria-disabled", "true")
    expect(second_delete).to_be_disabled()

    # Switching shape (Edit makes First the active one) clears it.
    first.locator("[data-shape-edit]").click()
    expect(first_tick).not_to_be_checked()
    expect(first_delete).to_be_disabled()
    expect(first_delete).to_have_attribute("aria-disabled", "true")

    # A tick on the active card survives a click inside that card...
    first_tick.check()
    first.locator("[data-shape-name]").click()
    expect(first_tick).to_be_checked()
    expect(first_delete).to_be_enabled()
    # ...and Cancel clears it.
    first.locator("[data-shape-cancel]").click()
    expect(first_tick).not_to_be_checked()
    expect(first_delete).to_be_disabled()

    # Editing another shape clears a tick left on the previous one.
    first.locator("[data-shape-edit]").click()
    first_tick.check()
    second.locator("[data-shape-edit]").click()
    expect(first_tick).not_to_be_checked()
    expect(first_delete).to_be_disabled()

    # A spawned card keys its own pair and ships Delete disabled; its
    # tick opens its own Delete and no other.
    second.locator("[data-shape-add]").click()
    spawned = page.locator("[data-shape]:not([data-shape-id])")
    expect(spawned).to_have_count(1)
    spawned_delete = spawned.locator("[data-shape-delete]")
    spawned_tick = spawned.locator("[data-delete-confirm]")
    expect(spawned_delete).to_be_disabled()
    expect(spawned_tick).to_have_attribute("data-delete-confirm", "shape-new-1")
    spawned_tick.check()
    expect(spawned_delete).to_be_enabled()
    expect(first_delete).to_be_disabled()
    expect(second_delete).to_be_disabled()

    # Ticked, Delete does what it did before: the shape goes, and stays
    # gone after a reload. The page fires its DELETE and forgets it, so
    # wait for the response before reloading or the reload can win.
    spawned_delete.click()
    expect(spawned).to_have_count(0)
    second_tick.check()
    with page.expect_response(
        lambda r: r.request.method == "DELETE"
        and r.url.endswith(f"/extract-data/shapes/{second_id}")
    ) as deleted:
        second_delete.click()
    assert deleted.value.status == 204
    expect(second).to_have_count(0)
    page.reload()
    expect(
        page.locator(f'[data-shape][data-shape-id="{second_id}"]')
    ).to_have_count(0)
    expect(
        page.locator(f'[data-shape][data-shape-id="{first_id}"]')
    ).to_have_count(1)

