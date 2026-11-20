"""Segment AD1Q, rung 2: the layouts ruling 65 approved from mockups,
measured in a real Chromium. Without a Chromium build the tests skip,
saying why; ``RRW_REQUIRE_BROWSER=1`` (set by CI) turns that skip into a
failure."""

from __future__ import annotations

from playwright.sync_api import FloatRect, Locator, Page, expect

from applydesk.tests.test_form_browser import page as page

ORIGIN = "http://applydesk.test"
EX = f"{ORIGIN}/applydesk/operator/exercises/wa9juxbc2t"


def _box(loc: Locator) -> FloatRect:
    box = loc.bounding_box()
    assert box is not None
    return box


def test_the_review_robin_card_is_two_columns_tiles_and_a_progress_panel(page: Page) -> None:
    page.set_viewport_size({"width": 1300, "height": 900})
    page.goto(f"{EX}/evaluations/gate_1")
    card = page.locator("#ev-rr")
    names, facts = _box(card.locator(".rr-names")), _box(card.locator(".rr-top > .facts"))
    assert facts["x"] > names["x"] + names["width"] - 1  # side by side
    tiles = [_box(t) for t in card.locator(".rr-file").all()]
    assert len(tiles) == 4
    assert round(tiles[0]["y"]) == round(tiles[1]["y"]) and tiles[2]["y"] > tiles[0]["y"]
    assert round(tiles[0]["x"]) == round(tiles[2]["x"])  # 2 x 2
    panel = card.locator(".rr-progress")
    assert _box(panel)["y"] > tiles[3]["y"]
    acts, table = _box(panel.locator(".rr-acts").first), _box(panel.locator("[data-rr-status]"))
    assert acts["y"] < table["y"]  # the actions above the table
    # A phone: one column each.
    page.set_viewport_size({"width": 390, "height": 900})
    tiles = [_box(t) for t in card.locator(".rr-file").all()]
    assert tiles[1]["y"] > tiles[0]["y"]


def test_a_button_beside_a_field_is_its_height(page: Page) -> None:
    page.goto(f"{EX}/emails")
    row = page.locator(".em-insert-row").first
    sel, btn = _box(row.locator("select")), _box(row.locator("button"))
    assert abs(sel["y"] - btn["y"]) < 1 and abs(sel["height"] - btn["height"]) < 1, (sel, btn)


def test_evaluations_buttons_sit_flush_right(page: Page) -> None:
    page.set_viewport_size({"width": 1300, "height": 900})
    page.goto(f"{EX}/evaluations")
    for row in page.locator("tr[data-gate]").all():
        cell, btn = _box(row.locator("td").last), _box(row.locator("td").last.locator(".btn"))
        assert cell["x"] + cell["width"] - (btn["x"] + btn["width"]) < 16, (cell, btn)


def test_panels_toolbar_is_two_columns(page: Page) -> None:
    page.set_viewport_size({"width": 1300, "height": 900})
    page.goto(f"{EX}/panels")
    chips, search = _box(page.locator(".pn-showcols")), _box(page.locator(".pn-search"))
    add = _box(page.locator('[data-pn-act="add"]'))
    assert search["x"] > chips["x"] + chips["width"]  # Filter right of the chips
    assert add["y"] >= search["y"] + search["height"] - 1  # Add new under Filter
    assert abs((add["x"] + add["width"]) - (search["x"] + search["width"])) < 1  # right edges


def test_process_opens_the_card_a_link_names(page: Page) -> None:
    """Ruling 65: #gate-<key> (the gate page's Set on Process →) and
    #outcome-<key> (an email's) open a card shut on a plain load, its stage
    with it, and bring it into view; an unknown name opens the page as
    usual. (#form is the first card, open already.)"""
    page.set_viewport_size({"width": 1300, "height": 900})
    page.goto(f"{EX}/process")

    def last(kind: str) -> str:
        keys = page.locator(f'.pc-item[data-item="{kind}"]').evaluate_all(
            "els => els.map(e => e.dataset.key)"
        )
        return keys[-1]

    for kind in ("gate", "outcome"):
        key = last(kind)
        item = page.locator(f'.pc-item[data-key="{key}"]')
        page.goto(f"{EX}/panels")
        page.goto(f"{EX}/process")
        assert item.get_attribute("data-open") is None, kind  # shut on a plain load
        page.goto(f"{EX}/panels")
        page.goto(f"{EX}/process#{kind}-{key}")  # as the gate page's and Emails' links
        expect(item).to_have_attribute("data-open", "")
        expect(item).to_be_in_viewport()
    # A name Process does not know opens the page as usual, nothing opened.
    page.goto(f"{EX}/panels")
    page.goto(f"{EX}/process")
    plain = page.locator(".pc-item[data-open]").count()
    page.goto(f"{EX}/panels")
    page.goto(f"{EX}/process#gate-nosuch")
    expect(page.locator(".pc-item[data-open]")).to_have_count(plain)
