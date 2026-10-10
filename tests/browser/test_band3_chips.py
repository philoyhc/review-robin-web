"""Band 3's fields are on/off chips around their Active checkbox.

A response field's chip is labeled with its name, mirrored live from the
name box, and capped; it is the row's first cell at every level.

``guide/ux_refinements.md`` Item 1; ``spec/instruments.md`` "Display-field
table". A display field's chip wraps its hidden checkbox, so a click on
the chip ticks the box and the preview follows. Name and Email, whose box
is disabled, read as fixed switches, and so does a field a group row can't
show once the instrument is grouped.
"""

from __future__ import annotations

import re
from collections.abc import Callable

import httpx
from playwright.sync_api import Dialog, Locator, Page, expect

from ._builder import REVIEWERS_CSV, open_card, open_unlocked, preview_headers, rows, unlock


def _style(chip: Locator, prop: str, pseudo: str | None = None) -> str:
    return chip.evaluate(
        "(el, [prop, pseudo]) => getComputedStyle(el, pseudo).getPropertyValue(prop)",
        [prop, pseudo],
    )


def _glyph(chip: Locator) -> str:
    return _style(chip, "-webkit-mask-image", "::before") or _style(
        chip, "mask-image", "::before"
    )


def _seed(api: httpx.Client, session_id: int) -> None:
    """A roster whose reviewees carry a tag, so Band 3 has a field
    besides Name and Email (``seed_rosters``' ``Tag1`` header isn't one)."""
    for kind, body in (
        ("reviewers", REVIEWERS_CSV),
        ("reviewees", b"RevieweeName,RevieweeEmail,RevieweeTag1\nCarol,carol@example.edu,Blue\n"),
    ):
        response = api.post(
            f"/operator/sessions/{session_id}/{kind}/import",
            files={"file": (f"{kind}.csv", body, "text/csv")},
            follow_redirects=False,
        )
        assert response.status_code in (200, 303), response.text


def _chip(card: Locator, key: str) -> Locator:
    return card.locator(f'[data-new-model-df-row][data-key="{key}"] label.tag-chip')


def _box(card: Locator, key: str) -> Locator:
    return card.locator(f'[data-new-model-df-row][data-key="{key}"] [data-new-model-df-active]')


def test_a_display_field_toggles_through_its_chip(
    page: Page, api: httpx.Client, new_session: Callable[[], int]
) -> None:
    session_id = new_session()
    _seed(api, session_id)
    card = open_unlocked(page, session_id)
    name = _chip(card, "reviewee.name")
    tag = _chip(card, "reviewee.tag_1")
    box = _box(card, "reviewee.tag_1")
    # The box is visually hidden inside its chip: a 1px clip.
    for each in card.locator("[data-new-model-df-active]").all():
        assert each.bounding_box()["width"] <= 1

    expect(box).to_be_checked()
    on_fill = _style(tag, "background-color")
    assert on_fill == _style(name, "background-color")
    assert _style(tag, "cursor") == "pointer"
    assert "svg" not in _glyph(tag)
    assert "Tag 1" in preview_headers(card)

    tag.click()
    expect(box).not_to_be_checked()
    assert _style(tag, "background-color") != on_fill
    assert "Tag 1" not in preview_headers(card)

    tag.click()
    expect(box).to_be_checked()
    assert _style(tag, "background-color") == on_fill
    assert "Tag 1" in preview_headers(card)


def test_name_and_email_chips_are_fixed_switches(
    page: Page, api: httpx.Client, new_session: Callable[[], int]
) -> None:
    session_id = new_session()
    _seed(api, session_id)
    card = open_unlocked(page, session_id)
    for key in ("reviewee.name", "reviewee.email_or_identifier"):
        chip = _chip(card, key)
        assert _style(chip, "cursor") == "default", key
        assert _style(chip, "box-shadow") == "none", key
        assert "svg" in _glyph(chip), key
        # Playwright won't click a label whose box is disabled; force it,
        # as a person's click lands anyway, and the box stays ticked.
        chip.click(force=True)
        expect(_box(card, key)).to_be_checked()


def test_a_field_a_group_row_cant_show_is_fixed_off(
    page: Page, api: httpx.Client, new_session: Callable[[], int]
) -> None:
    session_id = new_session()
    _seed(api, session_id)
    card = open_unlocked(page, session_id)
    email = _chip(card, "reviewee.email_or_identifier")
    tag = _chip(card, "reviewee.tag_1")
    tag.click()
    expect(_box(card, "reviewee.tag_1")).not_to_be_checked()
    off_fill = _style(tag, "background-color")

    mode = card.locator("[data-new-model-unit-mode]").first
    for _ in range(3):
        if mode.get_attribute("data-new-model-unit-mode") == "group":
            break
        mode.click()
    expect(mode).to_have_attribute("data-new-model-unit-mode", "group")
    # The mode switch marks Band 2; its rows re-sync on the preview's
    # refresh, which disables the box. The chip follows from CSS alone.
    card.locator("[data-new-model-band2]").first.evaluate(
        "b2 => window.newModelRefreshBand2(b2)"
    )

    box = _box(card, "reviewee.email_or_identifier")
    expect(box).not_to_be_checked()
    expect(box).to_be_disabled()
    expect(email).to_have_attribute("title", "Not shown on group rows")
    assert _style(email, "background-color") == off_fill
    assert _style(email, "cursor") == "default"
    assert "svg" in _glyph(email)


def test_a_locked_cards_chips_drop_the_edge_until_it_unlocks(
    page: Page, api: httpx.Client, new_session: Callable[[], int]
) -> None:
    """A locked card's chips read as the display pills they replaced (the
    author, 2026-10-10; Codex on #2936), read off the card's lock
    attribute, and come back live on unlock."""
    session_id = new_session()
    _seed(api, session_id)
    card = open_card(page, session_id)
    tag = _chip(card, "reviewee.tag_1")
    name = _chip(card, "reviewee.name")
    pill = card.locator("[data-new-model-vp-preview-cell]").first
    # A response field's name chip too (PR 2).
    rating = card.locator("label.rf-name-chip").first
    for chip in (tag, name, rating):
        assert _style(chip, "cursor") == "default"
        assert _style(chip, "box-shadow") == "none"
        assert _style(chip, "background-color") == _style(pill, "background-color")
        assert _style(chip, "content", "::before") == "none"

    unlock(card)
    assert _style(tag, "cursor") == "pointer"
    assert _style(tag, "box-shadow") != "none"


# ---- Response fields: name chips (ux_refinements Item 1, PR 2) ----


def _rf_chip(row: Locator) -> Locator:
    return row.locator("label.rf-name-chip")


def test_a_response_chip_follows_its_name_live(
    page: Page, new_session: Callable[[], int]
) -> None:
    card = open_unlocked(page, new_session())
    row = rows(card).first
    chip = _rf_chip(row)
    expect(chip).to_have_text("Rating")
    # The chip is the row's first cell, flush left.
    assert row.evaluate("r => r.cells[0].contains(r.querySelector('label.rf-name-chip'))")

    long = "Overall impression of the work"
    row.locator("[data-new-model-rf-name]").fill(long)
    expect(chip).to_have_text(long)
    expect(chip).to_have_attribute("title", long)
    # Capped at about a nine-letter name; the rest ends in "…".
    width = chip.evaluate("el => el.getBoundingClientRect().width")
    font = float(_style(chip, "font-size").removesuffix("px"))
    assert width <= 8 * font + 1, width
    assert _style(chip, "text-overflow") == "ellipsis"
    assert chip.evaluate("el => el.scrollWidth > el.clientWidth")

    # An empty box: the chip goes by the default the box shows muted.
    row.locator("[data-new-model-rf-name]").fill("")
    placeholder = row.locator("[data-new-model-rf-name]").get_attribute("placeholder")
    expect(chip).to_have_text(placeholder or "")

    # A row "+" adds is labeled too.
    row.locator("[data-new-model-rf-add]").click()
    added = rows(card).nth(1)
    expect(_rf_chip(added)).to_have_text(re.compile(r"^Field \d+$"))


def test_hiding_a_field_with_responses_through_its_chip_still_asks(
    page: Page, new_session: Callable[[], int]
) -> None:
    card = open_unlocked(page, new_session())
    row = rows(card).first
    box = row.locator("[data-new-model-rf-active]")
    # The confirm reads the row's saved-response count, which a field with
    # answers renders; set it here rather than seed a whole review.
    row.evaluate("r => r.setAttribute('data-response-count', '2')")
    messages: list[str] = []

    def dismiss(dialog: Dialog) -> None:
        messages.append(dialog.message)
        dialog.dismiss()

    page.once("dialog", dismiss)
    _rf_chip(row).click()
    expect(box).to_be_checked()
    assert messages and "2 saved responses" in messages[0], messages

    page.once("dialog", lambda dialog: dialog.accept())
    _rf_chip(row).click()
    expect(box).not_to_be_checked()


def test_a_hidden_parents_branch_chips_are_fixed_off(
    page: Page, new_session: Callable[[], int]
) -> None:
    card = open_unlocked(page, new_session())
    parent = rows(card).first
    parent.locator("[data-new-model-rf-fork]").click()
    governed = card.locator("[data-new-model-rf-governed]").first
    chip = _rf_chip(governed)
    on_fill = _style(chip, "background-color")
    assert _style(chip, "cursor") == "pointer"
    assert "svg" not in _glyph(chip)

    _rf_chip(parent).click()
    expect(governed.locator("[data-new-model-rf-active]")).to_be_disabled()
    assert _style(chip, "background-color") == _style(_rf_chip(parent), "background-color")
    assert _style(chip, "cursor") == "default"
    assert _style(chip, "box-shadow") == "none"
    assert "svg" in _glyph(chip)
    expect(chip).to_have_attribute("title", re.compile("parent field is hidden"))

    _rf_chip(parent).click()
    expect(governed.locator("[data-new-model-rf-active]")).to_be_enabled()
    assert _style(chip, "background-color") == on_fill
    assert _style(chip, "cursor") == "pointer"
    assert "svg" not in _glyph(chip)


def test_a_pending_rows_chip_follows_its_default_when_another_takes_it(
    page: Page, new_session: Callable[[], int]
) -> None:
    """The cold read: a name edit can move another row's default, and a
    pending row (one that can't commit) still relabels its chip."""
    card = open_unlocked(page, new_session())
    rows(card).first.locator("[data-new-model-rf-add]").click()
    added = rows(card).nth(1)
    expect(_rf_chip(added)).to_have_text(re.compile(r"^Field \d+$"))
    # The default as typed (inner_text would give the pill's uppercase).
    taken = added.locator("[data-new-model-rf-name]").get_attribute("placeholder") or ""
    expect(_rf_chip(added).locator("[data-new-model-rf-chip-label]")).to_have_text(taken)
    added.locator("[data-new-model-rf-data-type]").select_option("integer")
    added.locator('[data-new-model-rf-bound="min"]').fill("abc")
    expect(added).to_have_attribute("data-row-pending", "true")

    comments = rows(card).last
    comments.locator("[data-new-model-rf-name]").fill(taken)
    placeholder = added.locator("[data-new-model-rf-name]")
    expect(placeholder).not_to_have_attribute("placeholder", taken)
    expect(_rf_chip(added).locator("[data-new-model-rf-chip-label]")).to_have_text(
        placeholder.get_attribute("placeholder") or ""
    )
    expect(added.locator("[data-new-model-rf-active]")).to_have_attribute(
        "aria-label", "Show " + (placeholder.get_attribute("placeholder") or "")
    )


def _leading(row: Locator) -> list[str]:
    """Each leading cell's role, up to the name: chip, bar, or the
    control it holds."""
    return row.evaluate(
        """r => {
          const out = [];
          for (const td of r.cells) {
            if (td.classList.contains('rf-name')) { break; }
            if (td.querySelector('label.rf-name-chip')) { out.push('chip'); }
            else if (td.classList.contains('rf-branch-bar')) { out.push('bar'); }
            else if (td.querySelector('[data-new-model-rf-add]')) {
              out.push(td.classList.contains('rf-branch-bar-start') ? '+start' : '+');
            }
            else if (td.querySelector('[data-new-model-rf-fork]')) { out.push('fork'); }
            else if (td.querySelector('[data-new-model-rf-nest]')) { out.push('nest'); }
            else if (td.querySelector('[data-new-model-rf-join]')) { out.push('join'); }
            else { out.push('slot'); }
          }
          return out;
        }"""
    )


def test_the_row_script_keeps_the_chip_first_at_every_level(
    page: Page, new_session: Callable[[], int]
) -> None:
    """The cold read: the rows the script builds and re-levels (fork, a
    fork one level down, ending a branch) keep the chip first and start a
    parent's bar at its +."""
    card = open_unlocked(page, new_session())
    parent = rows(card).first
    parent.locator("[data-new-model-rf-fork]").click()
    governed = card.locator("[data-new-model-rf-level='1']").first
    governed.locator("[data-new-model-rf-name]").fill("Strength")
    governed.locator("[data-new-model-rf-data-type]").select_option("integer")
    governed.locator("[data-new-model-rf-fork]").click()
    inner = card.locator("[data-new-model-rf-level='2']").first

    assert _leading(parent) == ["chip", "+start", "fork", "join", "slot", "slot"]
    assert _leading(governed) == ["chip", "bar", "+start", "fork", "nest", "join"]
    assert _leading(inner) == ["chip", "bar", "bar", "+", "slot", "join"]
    for condition in card.locator("[data-new-model-rf-condition]").all():
        first = condition.evaluate("c => c.cells[0].className")
        assert "rf-active-cell" in first, first

    # Ending the inner branch (↳ on its only field) takes the bar's start
    # off the governed row's + again.
    inner.locator("[data-new-model-rf-join]").click()
    assert _leading(governed)[2] == "+"
