"""Session Home's date-time fields (segment 19X Item 6): a 24-hour text
box, a calendar button that opens the browser's picker, and a ✕ that
clears the box in one press.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

import httpx
from playwright.sync_api import Page, expect


def test_the_box_takes_text_clears_in_one_press_and_saves(
    page: Page, new_session: Callable[[], str]
) -> None:
    session_id = new_session()
    page.goto(f"/operator/sessions/{session_id}?editing=1")
    end = page.locator("#mock-end")
    field = page.locator("[data-dt-field]", has=end)
    pick = field.locator("[data-dt-pick]")
    clear = field.locator("[data-dt-clear]")
    save = page.locator("[data-config-save]")
    # The script reveals both buttons; the native picker stays out of the
    # tab order and out of sight.
    expect(pick).to_be_visible()
    expect(clear).to_be_visible()
    expect(field.locator("[data-dt-picker]")).to_have_attribute("tabindex", "-1")
    expect(end).to_have_attribute("type", "text")

    # A pasted `T` form reads as the box's own 24-hour text.
    end.fill("2027-03-01T17:05")
    end.press("Tab")
    expect(end).to_have_value("2027-03-01 17:05")
    expect(save).to_be_enabled()

    with page.expect_navigation():
        save.click()
    page.wait_for_load_state("load")
    expect(end).to_have_value("2027-03-01 17:05")
    expect(save).to_be_disabled()

    # One press empties it, and counts as an edit.
    clear.click()
    expect(end).to_have_value("")
    expect(end).to_be_focused()
    expect(save).to_be_enabled()
    with page.expect_navigation():
        save.click()
    page.wait_for_load_state("load")
    expect(end).to_have_value("")


def test_the_buttons_hide_with_the_box_when_locked(
    page: Page, new_session: Callable[[], str]
) -> None:
    session_id = new_session()
    page.goto(f"/operator/sessions/{session_id}")
    card = page.locator("#session-config")
    expect(card).to_have_attribute("data-config-mode", "display")
    expect(page.locator("#mock-end")).to_be_hidden()
    expect(page.locator("[data-dt-clear]").first).to_be_hidden()
    expect(page.locator("[data-dt-pick]").first).to_be_hidden()


def test_create_flags_an_out_of_order_box_and_saves_text(page: Page) -> None:
    """New session's four fields: the ordering chain marks the later box
    of a pair out of order, as the server words it, and blocks the
    submit; put back in order, the 24-hour text saves."""
    code = f"dt{uuid.uuid4().hex[:8]}"
    page.goto("/operator/sessions/new")
    page.locator("#name").fill(f"Fields {code}")
    page.locator("#code").fill(code)
    page.locator("#display_timezone").fill("UTC")
    for box in ("#scheduled_activate_at", "#deadline"):
        field = page.locator("[data-dt-field]", has=page.locator(box))
        expect(field.locator("[data-dt-pick]")).to_be_visible()
        expect(field.locator("[data-dt-clear]")).to_be_visible()

    start, end = page.locator("#scheduled_activate_at"), page.locator("#deadline")
    start.fill("2027-03-02 09:00")
    end.fill("2027-03-01 09:00")
    message = end.evaluate("el => el.validationMessage")
    assert message == "End must be on or after Start."
    assert start.evaluate("el => el.validity.valid")
    # The picker behind End offers nothing before Start.
    expect(
        page.locator("[data-dt-field]", has=end).locator("[data-dt-picker]")
    ).to_have_attribute("min", "2027-03-02T09:00")
    assert not page.evaluate("document.getElementById('deadline').form.checkValidity()")

    end.fill("2027-03-02T17:30")
    end.press("Tab")
    expect(end).to_have_value("2027-03-02 17:30")
    assert end.evaluate("el => el.validity.valid")
    with page.expect_navigation():
        page.locator("#create-session-submit").click()
    page.wait_for_load_state("load")
    assert "/new" not in page.url
    page.goto(page.url.split("?")[0].split("#")[0] + "?editing=1")
    expect(page.locator("#mock-start")).to_have_value("2027-03-02 09:00")
    expect(page.locator("#mock-end")).to_have_value("2027-03-02 17:30")


def test_the_lobby_expanders_end_is_the_field(
    page: Page, api: httpx.Client
) -> None:
    code = f"dl{uuid.uuid4().hex[:8]}"
    response = api.post(
        "/operator/sessions",
        data={"name": f"Lobby {code}", "code": code, "display_timezone": "UTC",
              "deadline": "2027-04-01T10:00"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    session_id = response.headers["location"].split("?")[0].rsplit("/", 1)[1]
    page.goto("/operator/sessions")
    row = page.locator(f'tr[data-session-id="{session_id}"]')
    row.locator(".sessions-list-select-row").check()
    end = page.locator('[data-expander-field="deadline"]')
    field = page.locator("[data-dt-field]", has=end)
    expect(end).to_have_value("2027-04-01 10:00")
    expect(field.locator("[data-dt-pick]")).to_be_visible()
    clear = field.locator("[data-dt-clear]")
    expect(clear).to_be_visible()

    clear.click()
    expect(end).to_have_value("")
    end.fill("2027-04-02 11:15")
    with page.expect_navigation():
        page.locator("[data-expander-save]").click()
    page.wait_for_load_state("load")
    page.locator(f'tr[data-session-id="{session_id}"] .sessions-list-select-row').check()
    expect(page.locator('[data-expander-field="deadline"]')).to_have_value(
        "2027-04-02 11:15"
    )


def _pick(page: Page, box: str, value: str) -> None:
    """What the browser's picker does on a choice: set its value and fire
    change. A headless run cannot open the pop-up itself."""
    page.locator("[data-dt-field]", has=page.locator(box)).locator(
        "[data-dt-picker]"
    ).evaluate(
        "(el, v) => { el.value = v; el.dispatchEvent(new Event('change', {bubbles: true})); }",
        value,
    )


def test_a_pick_writes_24_hour_text_and_counts_as_an_edit(
    page: Page, new_session: Callable[[], str]
) -> None:
    session_id = new_session()
    page.goto(f"/operator/sessions/{session_id}?editing=1")
    save = page.locator("[data-config-save]")
    expect(save).to_be_disabled()
    _pick(page, "#mock-end", "2027-05-06T21:45")
    expect(page.locator("#mock-end")).to_have_value("2027-05-06 21:45")
    expect(save).to_be_enabled()
    picker = page.locator("[data-dt-field]", has=page.locator("#mock-end")).locator(
        "[data-dt-picker]"
    )
    # The picker keeps nothing once its choice is written.
    expect(picker).to_have_value("")


def test_a_pick_then_a_zone_change_leaves_create_submittable(page: Page) -> None:
    """The read of this item: a picked End used to stay in its picker,
    under bounds the zone change then moved, and blocked the submit on
    an invisible control."""
    page.goto("/operator/sessions/new")
    page.locator("#name").fill("Picked")
    page.locator("#code").fill(f"pk{uuid.uuid4().hex[:8]}")
    page.locator("#display_timezone").fill("UTC")
    page.locator("#scheduled_activate_at").fill("2027-03-01 08:00")
    _pick(page, "#deadline", "2027-03-01T09:00")
    page.locator("#display_timezone").fill("Asia/Singapore")
    expect(page.locator("#scheduled_activate_at")).to_have_value("2027-03-01 16:00")
    expect(page.locator("#deadline")).to_have_value("2027-03-01 17:00")
    assert page.evaluate("document.getElementById('deadline').form.checkValidity()")


def test_a_zone_change_leaves_an_impossible_time_as_typed(page: Page) -> None:
    """Text that names no real moment is left for the server to refuse,
    not rolled by the zone conversion into another day."""
    page.goto("/operator/sessions/new")
    page.locator("#display_timezone").fill("UTC")
    for text in ("2027-02-31 10:00", "2027-13-01 10:00", "2027-01-01 10:99"):
        page.locator("#deadline").fill(text)
        page.locator("#display_timezone").fill("Asia/Singapore")
        expect(page.locator("#deadline")).to_have_value(text)
        page.locator("#display_timezone").fill("UTC")
