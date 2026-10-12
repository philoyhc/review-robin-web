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

    from app.db.models import Observer, Reviewee, ReviewSession

    engine = create_engine(database_url)
    try:
        with Session(engine) as db:
            db.get(ReviewSession, session_id).observers_enabled = True
            # A populated tag, so the builder offers a field to pick.
            db.add(Reviewee(
                session_id=session_id, name="E",
                email_or_identifier="e@example.org", tag_1="Blue",
            ))
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


def _stored_rule(database_url: str, email: str) -> object:
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.db.models import Observer

    engine = create_engine(database_url)
    try:
        with Session(engine) as db:
            return db.execute(
                select(Observer.cohort_rule).where(Observer.email == email)
            ).scalar_one()
    finally:
        engine.dispose()


def test_save_waits_for_an_email_and_a_finished_rule(
    page: Page, live_server: LiveServer, new_session: Callable[[], int]
) -> None:
    """Rung 3: Save is live only when the row and its rule are savable,
    and one click stores both."""
    session_id = new_session()
    _seed_observer(live_server.database_url, session_id)
    page.goto(f"/operator/sessions/{session_id}/observers?add=1")
    save = page.locator("[data-observer-edit-save]")
    builder = page.locator(
        "[data-observer-edit-cohort] [data-observer-cohort-builder]"
    )
    cell = builder.locator("[data-observer-rule-cell]").first
    field = cell.locator('select[name="cohort_rule_field"]')
    # An untouched builder is "no rule": blank field, nothing to finish.
    assert field.input_value() == ""
    assert save.is_disabled(), "no email yet"
    page.locator('input[name="email"][form="observer-edit-form"]').fill(
        "gate@example.org")
    assert save.is_enabled()
    # A field with a typed operator and no value is half-filled.
    field.select_option("reviewee.tag1")
    op = cell.locator("[data-observer-op-cycle]")
    while op.inner_text() != "IS":
        op.click()
    assert save.is_disabled()
    cell.locator("[data-observer-operand-value]").fill("Red")
    assert save.is_enabled()
    save.click()
    page.wait_for_load_state("load")
    rule = _stored_rule(live_server.database_url, "gate@example.org")
    assert rule["rules"][0]["op"] == "IS"
    assert rule["rules"][0]["operand_value"] == "Red"


def test_a_rule_the_dropdown_lacks_survives_a_rename(
    page: Page, live_server: LiveServer, new_session: Callable[[], int]
) -> None:
    """Codex on #2989: a stale key loaded into a disabled
    option, which the browser leaves out of the submission — so a rename
    saved from the row editor cleared or scrambled the rule. The option
    is selectable now, and the rule round-trips unchanged."""
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.db.models import Observer

    session_id = new_session()
    observer_id = _seed_observer(live_server.database_url, session_id)
    stale = {
        "combinator": "AND",
        "rules": [{
            # The pair-level join is not in the dropdown at all.
            "field": "pair_context.tag1", "op": "IS THE SAME AS",
            "operand_tag": "reviewer.tag2", "operand_value": "",
        }],
    }
    engine = create_engine(live_server.database_url)
    try:
        with Session(engine) as db:
            db.get(Observer, observer_id).cohort_rule = stale
            db.commit()
    finally:
        engine.dispose()

    page.goto(f"/operator/sessions/{session_id}/observers?edit_id={observer_id}")
    builder = page.locator(
        "[data-observer-edit-cohort] [data-observer-cohort-builder]"
    )
    # `+` clones the first cell, but not its stale option: a key the
    # dropdown omits is not offered in a new cell.
    builder.locator("[data-observer-rule-add]").click()
    new_cell = builder.locator("[data-observer-rule-cell]").nth(1)
    assert new_cell.locator("option[data-observer-stale]").count() == 0
    new_cell.locator("[data-observer-rule-remove]").click()
    page.locator('input[name="display_name"][form="observer-edit-form"]').fill(
        "Renamed")
    with page.expect_navigation():
        page.locator("[data-observer-edit-save]").click()

    engine = create_engine(live_server.database_url)
    try:
        with Session(engine) as db:
            name, rule = db.execute(
                select(Observer.display_name, Observer.cohort_rule)
                .where(Observer.id == observer_id)
            ).one()
    finally:
        engine.dispose()
    assert name == "Renamed"
    assert rule == stale


def _rules(database_url: str, session_id: int) -> list[object]:
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.db.models import Observer

    engine = create_engine(database_url)
    try:
        with Session(engine) as db:
            return list(db.execute(
                select(Observer.cohort_rule)
                .where(Observer.session_id == session_id)
                .order_by(Observer.id)
            ).scalars())
    finally:
        engine.dispose()


def test_edit_on_several_rows_saves_one_rule_to_each(
    page: Page, live_server: LiveServer, new_session: Callable[[], int]
) -> None:
    """Rung 4: the expander shows no builder; `Edit` on two rows opens
    their rule alone, and its Save writes it to both."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.db.models import Observer

    session_id = new_session()
    _seed_observer(live_server.database_url, session_id)
    engine = create_engine(live_server.database_url)
    try:
        with Session(engine) as db:
            db.add(Observer(session_id=session_id, email="p@example.org",
                            display_name="P", status="active"))
            db.commit()
    finally:
        engine.dispose()

    page.goto(f"/operator/sessions/{session_id}/observers")
    boxes = page.locator("input.observer-select")
    boxes.nth(0).check()
    boxes.nth(1).check()
    expander = page.locator("#observers-row-expander")
    assert expander.locator("[data-observer-cohort-builder]").count() == 0
    expander.locator(".exp-edit").click()
    page.wait_for_load_state("load")
    assert page.url.count("rule_id=") == 2

    builder = page.locator(
        "[data-observer-edit-cohort] [data-observer-cohort-builder]"
    )
    # The two differ (a rule and none), so the builder starts empty.
    assert page.get_by_text("currently have different cohort rules").is_visible()
    cell = builder.locator("[data-observer-rule-cell]").first
    cell.locator('select[name="cohort_rule_field"]').select_option("reviewee.tag1")
    op = cell.locator("[data-observer-op-cycle]")
    while op.inner_text() != "IS":
        op.click()
    cell.locator("[data-observer-operand-value]").fill("Green")
    with page.expect_navigation():
        page.locator("[data-observer-edit-save]").click()

    rules = _rules(live_server.database_url, session_id)
    assert len(rules) == 2
    for rule in rules:
        (cell,) = rule["rules"]
        # Both operands ride along in storage (the schema's idiom); the
        # operator picks which one counts.
        assert (cell["field"], cell["op"], cell["operand_value"]) == (
            "reviewee.tag1", "IS", "Green")


def test_several_rows_save_waits_for_a_change(
    page: Page, live_server: LiveServer, new_session: Callable[[], int]
) -> None:
    """Over differing rules the builder arrives empty; a live Save would
    clear them all in one click, so it waits for a change."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.db.models import Observer

    session_id = new_session()
    first = _seed_observer(live_server.database_url, session_id)
    engine = create_engine(live_server.database_url)
    try:
        with Session(engine) as db:
            second = Observer(session_id=session_id, email="p@example.org",
                              display_name="P", status="active")
            db.add(second)
            db.commit()
            second_id = second.id
    finally:
        engine.dispose()

    page.goto(f"/operator/sessions/{session_id}/observers"
              f"?rule_id={first}&rule_id={second_id}")
    save = page.locator("[data-observer-edit-save]")
    assert save.is_disabled(), "Save is live over an untouched builder"
    page.locator("[data-observer-edit-cohort] [data-observer-combinator-toggle]").click()
    assert save.is_enabled()
