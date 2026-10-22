"""A live chip's edge is 2px as rendered, not only as declared.

``tests/integration/test_chip_edge.py`` checks the rule says it; it could
not see that ``.pill``'s later ``border: 1px solid transparent`` reset won
the cascade on every ``.pill.tag-chip``, which left only the inset
shadow's 1px (``spec/ui_elements.md`` §9, the author, 2026-10-10). This
reads the computed border and shadow: a live chip draws a 1px solid
border and an inset shadow, both in the reserved shade (``--selected-bg``),
and a fixed chip neither.
"""

from __future__ import annotations

import uuid

import httpx
from playwright.sync_api import Locator, Page, expect

from .conftest import app_url


def _edge(chip: Locator) -> tuple[str, str]:
    return tuple(
        chip.evaluate(
            "el => [getComputedStyle(el).borderTopColor,"
            " getComputedStyle(el).boxShadow]"
        )
    )


def _assert_two_pixel_edge(chip: Locator) -> None:
    """A drawn 1px border in the reserved shade, and the inset shadow in
    the same shade inside it."""
    width, style, shade = chip.evaluate(
        """el => {
            const s = getComputedStyle(el);
            const probe = document.createElement('span');
            probe.style.color = 'var(--selected-bg)';
            el.parentElement.appendChild(probe);
            const shade = getComputedStyle(probe).color;
            probe.remove();
            return [s.borderTopWidth, s.borderTopStyle, shade];
        }"""
    )
    border, shadow = _edge(chip)
    assert (width, style) == ("1px", "solid"), (width, style)
    assert border == shade, "the border is not the reserved shade"
    assert shadow.startswith(shade) and shadow.endswith("inset"), shadow


def test_lobby_chips_wear_a_two_pixel_edge(page: Page, api: httpx.Client) -> None:
    code = f"e{uuid.uuid4().hex[:8]}"
    response = api.post(
        "/operator/sessions",
        data={"name": f"Edge {code}", "code": code, "tags": "edge-alpha, edge-beta"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    page.goto(app_url("/operator/sessions"))
    strip = page.locator("#sessions-tag-filter")
    tag = strip.locator(".tag-chip").first
    expect(tag).to_be_visible()
    _assert_two_pixel_edge(tag)
    # The mode chip always had both pixels; it and a tag chip now match.
    mode = strip.locator("[data-tag-mode]")
    assert _edge(mode) == _edge(tag)


def test_guide_samples_live_and_fixed(page: Page) -> None:
    page.goto(app_url("/guide"))
    card = page.locator("#guide-controls")
    _assert_two_pixel_edge(card.locator("label.tag-chip", has_text="Tag1"))
    _assert_two_pixel_edge(card.locator("[data-guide-unset-chip]"))
    fixed = card.locator(".tag-chip.is-fixed")
    assert _edge(fixed) == ("rgba(0, 0, 0, 0)", "none")
