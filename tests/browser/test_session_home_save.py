"""Session Home's details card: Save only saves, and keeps the seat.

19U Item 4 (author, 2026-10-08). Save used to lock the card and reload
to ``#session-config``, which scrolled the card's top edge into view —
from the Save button at its foot, a jump. Now Save comes back with the
card still unlocked, at the scroll position it left, with no fragment
in the URL; only Lock locks.
"""

from __future__ import annotations

from collections.abc import Callable

from playwright.sync_api import Page, expect


def test_save_keeps_the_card_unlocked_and_the_scroll(
    page: Page, new_session: Callable[[], int]
) -> None:
    session_id = new_session()
    # Short enough that the Save button sits below the fold.
    page.set_viewport_size({"width": 1280, "height": 500})
    page.goto(f"/operator/sessions/{session_id}?editing=1")
    card = page.locator("#session-config")
    expect(card).to_have_attribute("data-config-mode", "edit")

    page.locator("#mock-description").fill("Saved without a jump")
    save = page.locator("[data-config-save]")
    save.scroll_into_view_if_needed()
    seat = page.evaluate("window.scrollY")
    assert seat > 0, "the page did not scroll; the test proves nothing"

    with page.expect_navigation():
        save.click()
    page.wait_for_load_state("load")

    assert page.url.endswith(f"/operator/sessions/{session_id}?editing=1")
    assert "#" not in page.url
    expect(card).to_have_attribute("data-config-mode", "edit")
    expect(page.locator("#mock-description")).to_have_value("Saved without a jump")
    # A clean card after the save: nothing to save or cancel yet.
    expect(save).to_be_disabled()
    assert abs(page.evaluate("window.scrollY") - seat) <= 2

    # Lock locks, in place, and drops the param so a reload stays locked.
    page.locator("[data-config-lock-toggle]").click()
    expect(card).to_have_attribute("data-config-mode", "display")
    assert "editing" not in page.url
    page.reload()
    expect(card).to_have_attribute("data-config-mode", "display")


def test_the_seat_is_restored_before_the_first_frame(
    page: Page, new_session: Callable[[], int]
) -> None:
    """The restore runs at the foot of the parse, so the reload's first
    painted frame is already at the operator's seat (read on #2894: the
    Status claimed it and nothing checked it)."""
    session_id = new_session()
    page.set_viewport_size({"width": 1280, "height": 500})
    page.goto(f"/operator/sessions/{session_id}?editing=1")
    page.locator("#mock-description").fill("First frame")
    save = page.locator("[data-config-save]")
    save.scroll_into_view_if_needed()
    seat = page.evaluate("window.scrollY")
    # Each animation frame's scrollY, from before the parse starts.
    page.add_init_script(
        "window.__frames = []; (function f() {"
        " requestAnimationFrame(function () {"
        "  window.__frames.push(window.scrollY);"
        "  if (window.__frames.length < 4) f(); }); })();"
    )
    with page.expect_navigation():
        save.click()
    page.wait_for_load_state("load")
    page.wait_for_function("window.__frames.length >= 4")
    frames = page.evaluate("window.__frames")
    assert all(abs(y - seat) <= 2 for y in frames), frames


def _plant_seat(page: Page, session_id: int, *, y: int, age_ms: int) -> None:
    page.evaluate(
        "([key, y, age]) => sessionStorage.setItem(key,"
        " JSON.stringify({ y: y, t: Date.now() - age }))",
        [f"sessionHomeScrollY:/operator/sessions/{session_id}", y, age_ms],
    )


def test_a_seat_left_by_a_refused_save_is_not_inherited(
    page: Page, new_session: Callable[[], int]
) -> None:
    """A Save the server refuses (422) leaves the seat key behind; the next
    visit to Home — stale, or not on Save's landing URL — must not take
    its scroll or its fade (read on #2894)."""
    session_id = new_session()
    other_id = new_session()
    other_code = page.request.get(f"/operator/sessions/{other_id}").text()
    page.set_viewport_size({"width": 1280, "height": 500})
    page.goto(f"/operator/sessions/{session_id}?editing=1")
    taken = page.locator("#mock-code")
    taken.fill(
        other_code.split('id="mock-code"', 1)[1].split('value="', 1)[1].split('"', 1)[0]
    )
    page.locator("[data-config-save]").scroll_into_view_if_needed()
    page.locator("[data-config-save]").click()
    page.wait_for_load_state("load")
    assert "/config" in page.url  # the refusal page, not Home

    # Fresh key, but Home without ?editing=1: not where Save lands.
    page.goto(f"/operator/sessions/{session_id}")
    assert page.evaluate("window.scrollY") == 0
    assert page.evaluate("window.rrwSaveSeat") is None
    assert page.evaluate("document.getElementById('rrw-save-fade')") is None

    # Save's landing URL, but a stale seat.
    _plant_seat(page, session_id, y=400, age_ms=60_000)
    page.goto(f"/operator/sessions/{session_id}?editing=1")
    assert page.evaluate("window.scrollY") == 0
    assert page.evaluate("window.rrwSaveSeat") is None

    # And the key is used at most once: gone after any Home load.
    _plant_seat(page, session_id, y=400, age_ms=0)
    page.goto(f"/operator/sessions/{session_id}#owners-card")
    assert page.evaluate(
        f"sessionStorage.getItem('sessionHomeScrollY:/operator/sessions/{session_id}')"
    ) is None
