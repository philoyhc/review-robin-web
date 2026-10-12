"""The Observers row editor carries the cohort builder — operator pages
Item 4 (`guide/operator_pages_enhancements.md`).

Rung 2, the scaffold: in add and edit mode the builder renders under the
row it edits, loaded with the observer's rule (none on `Add`), its
controls posting with the edit form. The routes ignore those controls
until rung 3, so Save still saves the row alone. Whether the rule
actually loads into the cells is JS; `tests/browser/` drives that.
"""

from __future__ import annotations

import html as html_lib
import json
import re

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Observer, ReviewSession

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


def _session(client: TestClient, db: Session, code: str) -> tuple[ReviewSession, Observer]:
    response = client.post(
        "/operator/sessions",
        data={"name": "Obs", "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    rs = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    rs.observers_enabled = True
    observer = Observer(
        session_id=rs.id, email="o@example.org", display_name="O",
        status="active", cohort_rule=RULE,
    )
    db.add(observer)
    db.commit()
    db.refresh(observer)
    return rs, observer


def _bar(body: str) -> str:
    """The row editor's bar, by its class — `base.html` inlines markup
    from every page, so a page-wide check proves nothing."""
    m = re.search(
        r'<tr class="session-expander session-expander-bracketed row-editor-bar">'
        r".*?</tr>",
        body, re.S,
    )
    assert m, "no row editor bar"
    return m.group(0)


def _rule_attr(bar: str) -> object:
    m = re.search(r'data-observer-edit-cohort\s+data-rule="([^"]*)"', bar)
    assert m, "the builder pane carries no rule"
    return json.loads(html_lib.unescape(m.group(1)))


def _form_ids(fragment: str) -> set[str]:
    return set(re.findall(r'\bform="([^"]+)"', fragment))


def test_edit_shows_the_builder_loaded_with_the_rule(
    client: TestClient, db: Session
) -> None:
    rs, observer = _session(client, db, "orc-edit")
    body = client.get(
        f"/operator/sessions/{rs.id}/observers?edit_id={observer.id}"
    ).text
    bar = _bar(body)
    assert "This observer is able to see responses where" in bar
    assert "data-observer-cohort-builder" in bar
    assert _rule_attr(bar) == RULE
    # Every builder control posts with the edit form, Save included.
    assert _form_ids(bar) == {"observer-edit-form"}


def test_add_shows_an_empty_builder(client: TestClient, db: Session) -> None:
    rs, _ = _session(client, db, "orc-add")
    bar = _bar(client.get(f"/operator/sessions/{rs.id}/observers?add=1").text)
    assert "The new observer is able to see responses where" in bar
    assert _rule_attr(bar) is None
    assert _form_ids(bar) == {"observer-edit-form"}


def test_edit_mode_loads_the_rule_and_builds_no_selection_panel(
    client: TestClient, db: Session
) -> None:
    rs, observer = _session(client, db, "orc-script")
    body = client.get(
        f"/operator/sessions/{rs.id}/observers?edit_id={observer.id}"
    ).text
    assert "window.observerFillRule(" in body
    assert "window.observerAddRule = function" in body
    # The selection panel needs the checkboxes edit mode does not render.
    assert "observers-row-expander" not in body
    assert 'id="observers-cohort-template"' not in body


def test_the_selection_template_still_posts_with_the_bulk_form(
    client: TestClient, db: Session
) -> None:
    rs, _ = _session(client, db, "orc-bulk")
    body = client.get(f"/operator/sessions/{rs.id}/observers").text
    m = re.search(
        r'<template id="observers-cohort-template">.*?</template>', body, re.S
    )
    assert m, "no cohort template"
    assert _form_ids(m.group(0)) == {"observers-bulk-form"}
    assert "row-editor-bar" not in body


def test_save_still_saves_the_row_alone(client: TestClient, db: Session) -> None:
    """Rung 2: the builder's fields reach the route and are ignored."""
    rs, observer = _session(client, db, "orc-save")
    response = client.post(
        f"/operator/sessions/{rs.id}/observers/{observer.id}/update",
        data={
            "email": "o@example.org",
            "display_name": "Renamed",
            "tag_1": "",
            "status": "active",
            "cohort_combinator": "AND",
            "cohort_rule_field": "reviewee.tag1",
            "cohort_rule_op": "IS",
            "cohort_rule_operand_tag": "",
            "cohort_rule_operand_value": "Red",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    db.refresh(observer)
    assert observer.display_name == "Renamed"
    assert observer.cohort_rule == RULE
