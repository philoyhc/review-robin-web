"""The Instruments card's Responses chip (segment 20K rung 3): a second
cycle chip on the "Preview review instrument" row, after the Layout chip
and before Refresh sample, reading "Responses across" / "Responses
stacked". It rides the card's Save; the preview does not follow it yet.
"""

from __future__ import annotations

from collections.abc import Callable

from playwright.sync_api import Page, expect

from ._builder import open_card, open_unlocked, save
from .conftest import LiveServer


def test_the_chip_cycles_and_saves(
    page: Page, live_server: LiveServer, new_session: Callable[[], str]
) -> None:
    session_id = new_session()
    page.set_viewport_size({"width": 1400, "height": 1000})
    card = open_unlocked(page, session_id)
    chip = card.locator("[data-response-layout-chip]")
    expect(chip).to_have_text("Responses across")
    # Heading row order: Layout chip, Responses chip, then Refresh sample.
    layout_x = card.locator("[data-intro-layout-chip]").bounding_box()
    chip_x = chip.bounding_box()
    assert layout_x is not None and chip_x is not None
    assert layout_x["x"] < chip_x["x"]

    chip.click()
    expect(chip).to_have_text("Responses stacked")
    expect(card.locator("[data-response-layout-input]")).to_have_value("stacked")
    chip.press("Enter")
    expect(chip).to_have_text("Responses across")
    chip.click()
    save(page, card)

    card = open_unlocked(page, session_id)
    expect(card.locator("[data-response-layout-chip]")).to_have_text("Responses stacked")
    expect(card.locator("[data-response-layout-input]")).to_have_value("stacked")


def test_a_locked_cards_chip_is_a_plain_pill_that_does_not_cycle(
    page: Page, live_server: LiveServer, new_session: Callable[[], str]
) -> None:
    session_id = new_session()
    card = open_card(page, session_id)
    expect(card).to_have_attribute("data-instrument-locked", "true")
    chip = card.locator("[data-response-layout-chip]")
    expect(chip).to_have_text("Responses across")
    assert chip.evaluate("el => getComputedStyle(el).cursor") == "default"
    chip.click(force=True)
    expect(chip).to_have_text("Responses across")
    expect(card.locator("[data-response-layout-input]")).to_have_value("columns")


_STACK = """card => {
  const cell = card.querySelector('[data-new-model-band2-preview] td.rs-stack');
  if (!cell) { return null; }
  const lines = [...cell.querySelectorAll('.rs-stack-field')].map(line => {
    const box = line.querySelector('.rs-stack-input > *').getBoundingClientRect();
    const label = line.querySelector('.rs-stack-label').getBoundingClientRect();
    return {
      key: line.getAttribute('data-rs-stack-field'),
      compact: line.querySelector('.rs-stack-input').classList.contains('is-compact'),
      help: (line.querySelector('.rs-stack-help') || {}).textContent || '',
      labelRight: label.right, boxLeft: box.left, boxWidth: box.width,
    };
  });
  return {
    headers: [...card.querySelectorAll('[data-new-model-band2-preview] th')]
      .map(th => th.textContent.trim()),
    summary: !!card.querySelector('[data-new-model-band2-preview] .rs-constraints'),
    lines,
  };
}"""


def test_stacked_the_preview_puts_each_field_on_a_line(
    page: Page, live_server: LiveServer, new_session: Callable[[], str]
) -> None:
    session_id = new_session()
    page.set_viewport_size({"width": 1400, "height": 1000})
    card = open_unlocked(page, session_id)
    assert card.evaluate(_STACK) is None
    card.locator("[data-response-layout-chip]").click()
    stack = card.evaluate(_STACK)
    assert stack is not None
    assert stack["headers"][-1] == "Responses"
    assert not stack["summary"]
    # The default instrument's two fields, in order.
    rating, comments = stack["lines"]
    assert rating["help"] == "1-5, steps of 1"
    assert comments["help"] == "0-2000 char"
    # Rating is compact, Comments a text box; both start at one edge,
    # right of the widest label.
    assert rating["compact"] and not comments["compact"]
    assert rating["boxWidth"] < comments["boxWidth"]
    assert abs(rating["boxLeft"] - comments["boxLeft"]) < 1
    assert rating["boxLeft"] >= max(line["labelRight"] for line in stack["lines"])

    card.locator("[data-response-layout-chip]").click()
    assert card.evaluate(_STACK) is None


def test_stacked_the_label_and_response_columns_drag_and_save(
    page: Page, live_server: LiveServer, new_session: Callable[[], str]
) -> None:
    """Two handles in the Responses header, never one per box: the label
    column's and the response column's. A drag moves every line and
    rides the card's Save as ``stack_label`` / ``stack_input``."""
    session_id = new_session()
    page.set_viewport_size({"width": 1400, "height": 1000})
    card = open_unlocked(page, session_id)
    card.locator("[data-response-layout-chip]").click()
    handles = card.locator("[data-new-model-band2-preview] th.rs-stack [data-stack-width]")
    expect(handles).to_have_count(2)
    before = card.evaluate(_STACK)
    assert before is not None
    # Unset, the header's label column lines up with the cell's.
    head_label = card.locator(".rs-stack-head-label").bounding_box()
    assert head_label is not None
    assert abs(head_label["x"] + head_label["width"] - before["lines"][0]["labelRight"]) < 2

    card.locator('[data-stack-width="label"]').scroll_into_view_if_needed()
    before = card.evaluate(_STACK)
    assert before is not None
    label_handle = card.locator('[data-stack-width="label"]').bounding_box()
    assert label_handle is not None
    x = label_handle["x"] + label_handle["width"] / 2
    y = label_handle["y"] + label_handle["height"] / 2
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + 80, y, steps=4)
    page.mouse.up()
    after = card.evaluate(_STACK)
    assert after is not None
    shift = after["lines"][0]["boxLeft"] - before["lines"][0]["boxLeft"]
    assert 70 < shift < 90
    # Every line moves together.
    assert abs(after["lines"][0]["boxLeft"] - after["lines"][1]["boxLeft"]) < 1
    snapshot = card.locator("[data-new-model-band2-widths-snapshot]").input_value()
    assert '"stack_label"' in snapshot
    save(page, card)

    card = open_unlocked(page, session_id)
    reloaded = card.evaluate(_STACK)
    assert reloaded is not None
    assert abs(reloaded["lines"][0]["boxLeft"] - after["lines"][0]["boxLeft"]) < 2
