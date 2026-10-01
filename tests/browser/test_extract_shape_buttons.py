"""The Extract data page's shape buttons, shown and hidden (post_assessment_1oct E6).

A saved shape's card shows Edit and hides Save until Edit is pressed;
Cancel puts them back. The hidden button used to be hidden by an inline
``style="display: none;"``, which ``spec/ui_elements.md`` §6 calls a
defect on a button, and is now the ``hidden`` attribute, so the card's
script flips ``hidden`` rather than ``style.display``. This drives that
script in a browser, since the template test cannot run it.
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

