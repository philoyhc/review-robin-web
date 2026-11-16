"""The instrument description's edit box fits its text (author,
2026-11-16), as the answer boxes do: no drag handle, two lines empty,
and it grows with what is typed."""

from __future__ import annotations

from collections.abc import Callable

from playwright.sync_api import Locator, Page

from ._builder import open_unlocked, session_pk
from .conftest import LiveServer

_BOX = "[data-intro-description-input]"
_LONG = "Score each teammate on what they contributed this term. " * 12


def _fit(box: Locator) -> dict[str, float | str]:
    return box.evaluate(
        """el => ({height: el.getBoundingClientRect().height,
                   hidden: el.scrollHeight - el.clientHeight,
                   resize: getComputedStyle(el).resize})"""
    )


def test_the_description_box_grows_with_its_text(
    page: Page, live_server: LiveServer, new_session: Callable[[], str]
) -> None:
    session_id = new_session()
    page.set_viewport_size({"width": 1400, "height": 1000})
    card = open_unlocked(page, session_id)
    box = card.locator(_BOX)
    box.fill("")
    empty = _fit(box)
    assert empty["resize"] == "none", empty
    assert float(empty["height"]) < 70, empty  # two lines, not the old 6.5em

    box.fill(_LONG)
    full = _fit(box)
    assert float(full["height"]) > float(empty["height"]) + 40, full
    assert float(full["hidden"]) <= 1, full


def _describe(database_url: str, session_id: str, text: str) -> None:
    """The session's instrument's description, written directly."""
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.db.models import Instrument

    engine = create_engine(database_url)
    try:
        with Session(engine) as db:
            instrument = db.scalars(
                select(Instrument).where(
                    Instrument.session_id == session_pk(database_url, session_id)
                )
            ).first()
            assert instrument is not None
            instrument.description = text
            db.commit()
    finally:
        engine.dispose()


def test_a_saved_long_description_shows_whole_on_unlock(
    page: Page, live_server: LiveServer, new_session: Callable[[], str]
) -> None:
    """The box is hidden until the card unlocks; it fits then, with
    nothing typed (the cold read)."""
    session_id = new_session()
    _describe(live_server.database_url, session_id, _LONG)
    page.set_viewport_size({"width": 1400, "height": 1000})
    card = open_unlocked(page, session_id)
    box = card.locator(_BOX)
    page.wait_for_function(
        "el => el.scrollHeight - el.clientHeight <= 1 && el.getBoundingClientRect().height > 100",
        arg=box.element_handle(),
    )
    fit = _fit(box)
    assert float(fit["height"]) > 100 and float(fit["hidden"]) <= 1, fit
