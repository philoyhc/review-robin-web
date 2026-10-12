"""The Observers row editor's cohort builder, in Chromium — operator pages
Item 4 rung 2 (`guide/operator_pages_enhancements.md`).

The rule rides to the page as JSON on the builder's pane; loading it into
cells is JS, which `tests/integration/test_observers_row_editor_cohort.py`
cannot run. This drives it: `Edit` shows the observer's rule cell by cell,
`Add` a single default cell, and the builder's buttons work in either.
"""

from __future__ import annotations

from collections.abc import Callable

from playwright.sync_api import Page

from .conftest import LiveServer

RULE = {
    "combinator": "OR",
    "rules": [
        {
            "field": "reviewer.tag1",
            "op": "IS THE SAME AS",
            "operand_tag": "observer.email",
            "operand_value": "",
        },
        {
            "field": "reviewee.tag1",
            "op": "IS",
            "operand_tag": "",
            "operand_value": "Blue",
        },
    ],
}


def _seed_observer(database_url: str, session_id: int) -> int:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.db.models import Observer, ReviewSession

    engine = create_engine(database_url)
    try:
        with Session(engine) as db:
            db.get(ReviewSession, session_id).observers_enabled = True
            observer = Observer(
                session_id=session_id, email="o@example.org",
                display_name="O", status="active", cohort_rule=RULE,
            )
            db.add(observer)
            db.commit()
            return observer.id
    finally:
        engine.dispose()


def test_edit_loads_the_observers_rule_into_the_builder(
    page: Page, live_server: LiveServer, new_session: Callable[[], int]
) -> None:
    session_id = new_session()
    observer_id = _seed_observer(live_server.database_url, session_id)
    page.goto(f"/operator/sessions/{session_id}/observers?edit_id={observer_id}")
    builder = page.locator(
        "[data-observer-edit-cohort] [data-observer-cohort-builder]"
    )
    assert builder.locator("[data-observer-combinator-toggle]").inner_text() == "OR"
    cells = builder.locator("[data-observer-rule-cell]")
    assert cells.count() == 2
    first, second = cells.nth(0), cells.nth(1)
    assert first.locator('select[name="cohort_rule_field"]').input_value() == "reviewer.tag1"
    assert first.locator("[data-observer-op-cycle]").inner_text() == "IS THE SAME AS"
    assert first.locator("[data-observer-operand-tag]").input_value() == "observer.email"
    assert second.locator("[data-observer-op-cycle]").inner_text() == "IS"
    assert second.locator("[data-observer-operand-value]").input_value() == "Blue"
    assert second.locator("[data-observer-operand-value]").is_visible()


def test_add_starts_from_one_default_cell_and_the_buttons_work(
    page: Page, live_server: LiveServer, new_session: Callable[[], int]
) -> None:
    session_id = new_session()
    _seed_observer(live_server.database_url, session_id)
    page.goto(f"/operator/sessions/{session_id}/observers?add=1")
    builder = page.locator(
        "[data-observer-edit-cohort] [data-observer-cohort-builder]"
    )
    cells = builder.locator("[data-observer-rule-cell]")
    assert cells.count() == 1
    builder.locator("[data-observer-rule-add]").click()
    assert cells.count() == 2
    toggle = builder.locator("[data-observer-combinator-toggle]")
    toggle.click()
    assert toggle.inner_text() == "OR"
    assert builder.locator("[data-observer-combinator-input]").input_value() == "OR"
    cells.nth(1).locator("[data-observer-rule-remove]").click()
    assert cells.count() == 1
