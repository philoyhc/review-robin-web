"""The Observers row editor carries the cohort builder — operator pages
Item 4 (`guide/operator_pages_enhancements.md`).

In add and edit mode the builder renders under the row it edits, loaded
with the observer's rule (none on `Add`), its controls posting with the
edit form (rung 2); one Save writes the row and the rule, an untouched
builder meaning no rule and a half-filled cell refused (rung 3). Loading
the rule into cells and the Save gate are JS; `tests/browser/` drives
those.
"""

from __future__ import annotations

import html as html_lib
import json
import re

import pytest
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


def test_a_rejected_edit_keeps_the_rule_in_the_builder(
    client: TestClient, db: Session
) -> None:
    """Codex on #2988: a rejected save re-renders with the operator's
    values, and the builder comes back holding the rule as posted."""
    rs, observer = _session(client, db, "orc-reject")
    db.add(Observer(session_id=rs.id, email="taken@example.org", status="active"))
    db.commit()
    cells = [tuple(r[k] for k in ("field", "op", "operand_tag", "operand_value"))
             for r in RULE["rules"]]
    response = _post(
        client, f"/operator/sessions/{rs.id}/observers/{observer.id}/update",
        cells, email="taken@example.org", combinator="OR",
    )
    assert response.status_code == 400
    assert _rule_attr(_bar(response.text)) == RULE


def _post(client: TestClient, url: str, cells: list[tuple[str, str, str, str]],
          *, email: str = "o@example.org", combinator: str = "AND",
          name: str = "O") -> object:
    data: dict[str, object] = {
        "email": email, "display_name": name, "tag_1": "", "status": "active",
        "cohort_combinator": combinator,
        "cohort_rule_field": [c[0] for c in cells],
        "cohort_rule_op": [c[1] for c in cells],
        "cohort_rule_operand_tag": [c[2] for c in cells],
        "cohort_rule_operand_value": [c[3] for c in cells],
    }
    return client.post(url, data=data, follow_redirects=False)


def _events(db: Session, session_id: int) -> list[tuple[str, str | None]]:
    from app.db.models import AuditEvent

    return [
        (e.event_type, e.correlation_id)
        for e in db.execute(
            select(AuditEvent)
            .where(AuditEvent.session_id == session_id)
            .where(AuditEvent.event_type.like("observer.%"))
            .order_by(AuditEvent.id)
        ).scalars()
    ]


TAG_CELL = ("reviewer.tag1", "IS THE SAME AS", "observer.email", "")
VALUE_CELL = ("reviewee.tag1", "IS", "", "Red")
BLANK_CELL = ("", "IS THE SAME AS", "observer.name", "")


def test_add_saves_the_row_and_its_rule_in_one_post(
    client: TestClient, db: Session
) -> None:
    rs, _ = _session(client, db, "orc-add-save")
    before = len(_events(db, rs.id))
    response = _post(
        client, f"/operator/sessions/{rs.id}/observers/create",
        [TAG_CELL, VALUE_CELL], email="new@example.org", combinator="OR",
    )
    assert response.status_code == 303, response.text
    new = db.execute(
        select(Observer).where(Observer.email == "new@example.org")
    ).scalar_one()
    assert new.cohort_rule == {
        "combinator": "OR",
        "rules": [dict(zip(("field", "op", "operand_tag", "operand_value"), c))
                  for c in (TAG_CELL, VALUE_CELL)],
    }
    events = _events(db, rs.id)[before:]
    assert [e for e, _ in events] == [
        "observer.created", "observer.cohort_rule_assigned",
    ]
    assert len({c for _, c in events}) == 1, "one correlation id"


def test_an_untouched_builder_adds_an_observer_with_no_rule(
    client: TestClient, db: Session
) -> None:
    rs, _ = _session(client, db, "orc-add-blank")
    before = len(_events(db, rs.id))
    response = _post(
        client, f"/operator/sessions/{rs.id}/observers/create",
        [BLANK_CELL], email="blank@example.org",
    )
    assert response.status_code == 303, response.text
    new = db.execute(
        select(Observer).where(Observer.email == "blank@example.org")
    ).scalar_one()
    assert new.cohort_rule is None
    assert [e for e, _ in _events(db, rs.id)[before:]] == ["observer.created"]


def test_edit_changes_the_rule_alone_without_demoting_validated(
    client: TestClient, db: Session
) -> None:
    rs, observer = _session(client, db, "orc-edit-rule")
    rs.status = "validated"
    db.commit()
    before = len(_events(db, rs.id))
    response = _post(
        client, f"/operator/sessions/{rs.id}/observers/{observer.id}/update",
        [VALUE_CELL],
    )
    assert response.status_code == 303, response.text
    db.refresh(observer)
    db.refresh(rs)
    assert observer.cohort_rule == {
        "combinator": "AND",
        "rules": [dict(zip(("field", "op", "operand_tag", "operand_value"),
                           VALUE_CELL))],
    }
    assert [e for e, _ in _events(db, rs.id)[before:]] == [
        "observer.cohort_rule_assigned",
    ]
    assert rs.status == "validated"


def test_emptying_the_builder_clears_the_rule(
    client: TestClient, db: Session
) -> None:
    rs, observer = _session(client, db, "orc-clear")
    response = _post(
        client, f"/operator/sessions/{rs.id}/observers/{observer.id}/update",
        [BLANK_CELL],
    )
    assert response.status_code == 303, response.text
    db.refresh(observer)
    assert observer.cohort_rule is None


def test_an_unchanged_rule_writes_no_rule_event(
    client: TestClient, db: Session
) -> None:
    rs, observer = _session(client, db, "orc-same")
    before = len(_events(db, rs.id))
    cells = [tuple(r[k] for k in ("field", "op", "operand_tag", "operand_value"))
             for r in RULE["rules"]]
    response = _post(
        client, f"/operator/sessions/{rs.id}/observers/{observer.id}/update",
        cells, combinator="OR", name="Renamed",
    )
    assert response.status_code == 303, response.text
    assert [e for e, _ in _events(db, rs.id)[before:]] == ["observer.updated"]


@pytest.mark.parametrize(
    "cell",
    [
        ("reviewee.tag1", "IS", "", ""),     # a field, a typed operator, no value
        ("", "IS", "", "Red"),               # a value, no field
    ],
)
def test_a_half_filled_cell_is_refused_and_nothing_is_written(
    client: TestClient, db: Session, cell: tuple[str, str, str, str]
) -> None:
    rs, observer = _session(client, db, f"orc-half-{len(cell[0])}")
    response = _post(
        client, f"/operator/sessions/{rs.id}/observers/{observer.id}/update",
        [TAG_CELL, cell], name="Renamed",
    )
    assert response.status_code == 400
    assert "Finish or clear each rule cell" in response.text
    # The re-render keeps what the operator posted, both cells.
    shown = _rule_attr(_bar(response.text))
    assert len(shown["rules"]) == 2
    db.refresh(observer)
    assert observer.display_name == "O"
    assert observer.cohort_rule == RULE


def test_an_invalid_rule_is_refused_before_the_row_is_created(
    client: TestClient, db: Session
) -> None:
    rs, _ = _session(client, db, "orc-invalid")
    response = _post(
        client, f"/operator/sessions/{rs.id}/observers/create",
        [("reviewer.nope", "IS THE SAME AS", "observer.email", "")],
        email="bad@example.org",
    )
    assert response.status_code == 400
    assert "Couldn&#39;t save the cohort rule" in response.text
    assert db.execute(
        select(Observer).where(Observer.email == "bad@example.org")
    ).scalar_one_or_none() is None


def test_only_the_row_editor_offers_a_blank_field(
    client: TestClient, db: Session
) -> None:
    rs, observer = _session(client, db, "orc-blank-opt")
    bar = _bar(client.get(
        f"/operator/sessions/{rs.id}/observers?edit_id={observer.id}"
    ).text)
    assert '<option value="">Choose a field</option>' in bar
    body = client.get(f"/operator/sessions/{rs.id}/observers").text
    m = re.search(
        r'<template id="observers-cohort-template">.*?</template>', body, re.S
    )
    assert m and "Choose a field" not in m.group(0)
