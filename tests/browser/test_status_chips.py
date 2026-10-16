"""On/off chips in a status color (spec/ui_elements.md §9): the audit
log's Severity chips and the Guide's sample. Off wears the status's pale
tint, on its solid fill (info: the blue chip's own), in both themes, and
the chip is a real control: a click, Space and the form all go through
its hidden box.
"""

from __future__ import annotations

from collections.abc import Callable

from playwright.sync_api import Locator, Page, expect


def _bg(locator: Locator) -> str:
    return locator.evaluate("el => getComputedStyle(el).backgroundColor")


def _token(page: Page, name: str) -> str:
    """A token's background as the browser resolves it, via a probe."""
    return page.evaluate(
        """(name) => {
          const probe = document.createElement('span');
          probe.style.background = `var(${name})`;
          document.body.appendChild(probe);
          const value = getComputedStyle(probe).backgroundColor;
          probe.remove();
          return value;
        }""",
        name,
    )


_OFF = {"info": "--status-info-bg", "warning": "--status-warning-bg", "error": "--status-error-bg"}
_ON = {"info": "--selected-bg", "warning": "--status-warning-solid-bg", "error": "--status-error-solid-bg"}


def _check_fills(page: Page) -> None:
    for value in ("info", "warning", "error"):
        chip = page.locator(f"label.status-chip-{value}")
        box = chip.locator("input")
        expect(box).not_to_be_checked()
        assert _bg(chip) == _token(page, _OFF[value]), value
        chip.click()
        expect(box).to_be_checked()
        assert _bg(chip) == _token(page, _ON[value]), value
        assert _token(page, _ON[value]) != _token(page, _OFF[value])
        chip.click()
        expect(box).not_to_be_checked()


_TRANSPARENT = "rgba(0, 0, 0, 0)"


def test_severity_chips_fill_by_state_in_both_themes(
    page: Page, new_session: Callable[[], int]
) -> None:
    session_id = new_session()
    page.goto(f"/operator/sys-admin/sessions/{session_id}/audit-log")
    light = {v: _token(page, t) for v, t in _ON.items()}
    _check_fills(page)
    page.evaluate("document.documentElement.setAttribute('data-theme', 'dark')")
    dark = {v: _token(page, t) for v, t in _ON.items()}
    _check_fills(page)
    # The tokens exist, and the dark theme flips each on-fill, as the
    # blue chip's --selected-bg does.
    for value in _ON:
        assert _TRANSPARENT not in (light[value], dark[value]), value
        assert light[value] != dark[value], value


def test_a_severity_chip_filters_and_stays_on(
    page: Page, new_session: Callable[[], int]
) -> None:
    session_id = new_session()
    page.goto(f"/operator/sys-admin/sessions/{session_id}/audit-log")
    warning = page.locator("label.status-chip-warning")
    warning.locator("input").focus()
    page.keyboard.press("Space")
    expect(warning.locator("input")).to_be_checked()
    page.get_by_role("button", name="Apply filters").click()
    assert "severity=warning" in page.url
    expect(page.locator("label.status-chip-warning input")).to_be_checked()
    expect(page.locator("label.status-chip-info input")).not_to_be_checked()


def test_the_guide_sample_answers_a_click(page: Page) -> None:
    page.goto("/guide")
    card = page.locator("#guide-controls")
    warning = card.locator("label.status-chip-warning")
    error = card.locator("label.status-chip-error")
    expect(warning.locator("input")).to_be_checked()
    expect(error.locator("input")).not_to_be_checked()
    assert _bg(warning) == _token(page, "--status-warning-solid-bg")
    assert _bg(error) == _token(page, "--status-error-bg")
    error.click()
    assert _bg(error) == _token(page, "--status-error-solid-bg")
    warning.click()
    assert _bg(warning) == _token(page, "--status-warning-bg")
