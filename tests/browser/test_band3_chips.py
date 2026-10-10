"""Band 3's fields are on/off chips around their Active checkbox.

``guide/ux_refinements.md`` Item 1; ``spec/instruments.md`` "Display-field
table". A display field's chip wraps its hidden checkbox, so a click on
the chip ticks the box and the preview follows. Name and Email, whose box
is disabled, read as fixed switches, and so does a field a group row can't
show once the instrument is grouped.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
from playwright.sync_api import Locator, Page, expect

from ._builder import REVIEWERS_CSV, open_unlocked, preview_headers


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
