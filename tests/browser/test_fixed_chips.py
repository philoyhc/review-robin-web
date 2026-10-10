"""A fixed switch keeps its siblings' dark fill and wears a lock glyph.

``guide/ux_refinements.md`` Item 2; ``spec/ui_elements.md`` §9 "Fixed".
One item held at its value while the chips beside it stay live: Session
Home's optional tab once it holds data, and the Visibility card's two
cells whose mode isn't the operator's to choose. Neither has the edge or
the pointer of a live chip.
"""

from __future__ import annotations

from collections.abc import Callable

from playwright.sync_api import Locator, Page

from ._builder import open_card
from .conftest import LiveServer


def _style(chip: Locator, prop: str, pseudo: str | None = None) -> str:
    return chip.evaluate(
        "(el, [prop, pseudo]) => getComputedStyle(el, pseudo).getPropertyValue(prop)",
        [prop, pseudo],
    )


def _assert_fixed_like(fixed: Locator, live: Locator) -> None:
    assert _style(fixed, "background-color") == _style(live, "background-color")
    assert _style(fixed, "cursor") == "default"
    assert _style(fixed, "box-shadow") == "none"
    mask = _style(fixed, "-webkit-mask-image", "::before") or _style(
        fixed, "mask-image", "::before"
    )
    assert "svg" in mask, mask


def test_visibility_fixed_cells_are_fixed_switches(
    page: Page, new_session: Callable[[], int]
) -> None:
    card = open_card(page, new_session())
    editor = card.locator("[data-new-model-vp-editor]")
    fixed = editor.locator(".tag-chip.is-fixed")
    assert fixed.count() == 2
    live = editor.locator("[data-new-model-vp-cycle-audience]").first
    for i in range(2):
        _assert_fixed_like(fixed.nth(i), live)


def _seed_relationship(database_url: str, session_id: int) -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.db.models import Relationship, Reviewee, Reviewer, ReviewSession

    engine = create_engine(database_url)
    try:
        with Session(engine) as db:
            db.get(ReviewSession, session_id).relationships_enabled = True
            reviewer = Reviewer(session_id=session_id, name="R", email="r@example.org")
            reviewee = Reviewee(
                session_id=session_id, name="E", email_or_identifier="e@example.org"
            )
            db.add_all([reviewer, reviewee])
            db.flush()
            db.add(
                Relationship(
                    session_id=session_id,
                    reviewer_id=reviewer.id,
                    reviewee_id=reviewee.id,
                )
            )
            db.commit()
    finally:
        engine.dispose()


def test_session_home_tab_with_data_is_a_fixed_switch(
    page: Page, live_server: LiveServer, new_session: Callable[[], int]
) -> None:
    session_id = new_session()
    _seed_relationship(live_server.database_url, session_id)
    page.goto(f"/operator/sessions/{session_id}?editing=1")
    chips = page.locator("[data-edit-only] label.tag-chip")
    fixed = chips.filter(has=page.locator('input[name="relationships_enabled"]'))
    assert "is-fixed" in (fixed.get_attribute("class") or "")
    # A live chip that is on, to compare fills with: tick Observers.
    live = chips.filter(has=page.locator('input[name="observers_enabled"]'))
    live.click()
    _assert_fixed_like(fixed, live)
