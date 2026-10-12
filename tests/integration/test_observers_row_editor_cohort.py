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
    # And nowhere else: selecting rows shows no builder (rung 4).
    body = client.get(f"/operator/sessions/{rs.id}/observers").text
    assert "Choose a field" not in body


# ── Rung 4: `Edit` on several rows edits their rule alone ─────────────


def _second(db: Session, rs: ReviewSession, rule: object) -> Observer:
    other = Observer(
        session_id=rs.id, email="p@example.org", display_name="P",
        status="active", cohort_rule=rule,
    )
    db.add(other)
    db.commit()
    db.refresh(other)
    return other


def test_several_rows_open_their_shared_rule_alone(
    client: TestClient, db: Session
) -> None:
    rs, first = _session(client, db, "orc-multi")
    second = _second(db, rs, RULE)
    body = client.get(
        f"/operator/sessions/{rs.id}/observers"
        f"?rule_id={first.id}&rule_id={second.id}"
    ).text
    bar = _bar(body)
    assert "The 2 selected observers are able to see responses where" in bar
    assert _rule_attr(bar) == RULE
    assert "different cohort rules" not in bar
    # The rows stay read-only, both highlighted; the form posts the rule
    # alone, for both ids.
    assert '<input type="email" name="email"' not in body
    for oid in (first.id, second.id):
        assert re.search(
            rf'<tr id="observer-row-{oid}"\s+class="row-action-target session-row-selected"',
            body,
        ), f"row {oid} does not read as selected"
        assert f'<input type="hidden" name="observer_ids" value="{oid}">' in body
    form = re.search(r'<form id="observer-edit-form"[^>]*>', body)
    assert form and '/observers/cohort-rule"' in form.group(0)
    # The bar hangs under the last of them.
    assert body.index(f'id="observer-row-{second.id}"') < body.index("row-editor-bar")


def test_differing_rules_load_nothing_and_say_so(
    client: TestClient, db: Session
) -> None:
    rs, first = _session(client, db, "orc-mixed")
    second = _second(db, rs, None)
    bar = _bar(client.get(
        f"/operator/sessions/{rs.id}/observers"
        f"?rule_id={first.id}&rule_id={second.id}"
    ).text)
    assert _rule_attr(bar) is None
    assert "currently have different cohort rules" in bar


def test_one_rule_id_opens_no_rule_editor(
    client: TestClient, db: Session
) -> None:
    """One row is the row editor's (`?edit_id=`); a lone `rule_id` is
    ignored rather than opening a second surface for the same job."""
    rs, first = _session(client, db, "orc-one")
    body = client.get(
        f"/operator/sessions/{rs.id}/observers?rule_id={first.id}"
    ).text
    assert "row-editor-bar" not in body


def test_a_half_filled_rule_for_several_re_renders_their_editor(
    client: TestClient, db: Session
) -> None:
    rs, first = _session(client, db, "orc-multi-half")
    second = _second(db, rs, None)
    response = client.post(
        f"/operator/sessions/{rs.id}/observers/cohort-rule",
        data={
            "observer_ids": [first.id, second.id],
            "cohort_combinator": "AND",
            "cohort_rule_field": ["reviewee.tag1"],
            "cohort_rule_op": ["IS"],
            "cohort_rule_operand_tag": [""],
            "cohort_rule_operand_value": [""],
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    bar = _bar(response.text)
    assert "The 2 selected observers" in bar
    assert "Finish or clear each rule cell" in bar
    assert _rule_attr(bar)["rules"][0]["field"] == "reviewee.tag1"
    # Their stored rules still differ, so the note stays (Codex on #2990).
    assert "currently have different cohort rules" in bar
    db.refresh(first)
    db.refresh(second)
    assert first.cohort_rule == RULE and second.cohort_rule is None


def test_an_explicit_empty_rule_counts_as_no_rule(
    client: TestClient, db: Session
) -> None:
    """An imported observer can hold `rules: []`; saving its name from an
    untouched builder must not rewrite that as NULL with an event."""
    rs, observer = _session(client, db, "orc-empty-set")
    observer.cohort_rule = {"combinator": "AND", "rules": []}
    db.commit()
    before = len(_events(db, rs.id))
    response = _post(
        client, f"/operator/sessions/{rs.id}/observers/{observer.id}/update",
        [BLANK_CELL], name="Renamed",
    )
    assert response.status_code == 303, response.text
    assert [e for e, _ in _events(db, rs.id)[before:]] == ["observer.updated"]
    db.refresh(observer)
    assert observer.cohort_rule == {"combinator": "AND", "rules": []}


def test_null_and_an_empty_set_are_not_different_rules(
    client: TestClient, db: Session
) -> None:
    """Both mean "no rule"; the several-row editor must not call them
    different (`observers.same_cohort_rule`)."""
    rs, first = _session(client, db, "orc-null-empty")
    first.cohort_rule = None
    db.commit()
    second = _second(db, rs, {"combinator": "AND", "rules": []})
    bar = _bar(client.get(
        f"/operator/sessions/{rs.id}/observers"
        f"?rule_id={first.id}&rule_id={second.id}"
    ).text)
    assert "different cohort rules" not in bar


def test_edit_keeps_the_filter_and_page(client: TestClient, db: Session) -> None:
    """The several-row editor drops ids not on the rendered window, so
    `Edit` carries the view it was taken from — and a filtered view opens
    over the selected rows with its filter still applied."""
    rs, first = _session(client, db, "orc-view")
    second = _second(db, rs, RULE)
    hidden = Observer(session_id=rs.id, email="z@example.org",
                      display_name="Z", status="inactive")
    db.add(hidden)
    db.commit()
    page = client.get(f"/operator/sessions/{rs.id}/observers").text
    assert "window.location = OBS_BASE + query + VIEW +" in page
    body = client.get(
        f"/operator/sessions/{rs.id}/observers"
        f"?rule_id={first.id}&rule_id={second.id}"
        f"&status=active&q=&offset=0"
    ).text
    assert "The 2 selected observers" in _bar(body)
    assert f'id="observer-row-{hidden.id}"' not in body, (
        "the status filter was dropped"
    )


def test_a_rejected_save_arrives_as_unsaved(
    client: TestClient, db: Session
) -> None:
    """The leave guard and the several-row Save treat a page re-rendered
    by a rejected save as changed from arrival: what it holds was posted,
    not stored."""
    rs, first = _session(client, db, "orc-unsaved")
    second = _second(db, rs, None)
    ok = client.get(
        f"/operator/sessions/{rs.id}/observers"
        f"?rule_id={first.id}&rule_id={second.id}"
    ).text
    assert "var arrivedUnsaved = false;" in ok
    rejected = client.post(
        f"/operator/sessions/{rs.id}/observers/cohort-rule",
        data={
            "observer_ids": [first.id, second.id],
            "cohort_combinator": "AND",
            "cohort_rule_field": ["reviewee.tag1"],
            "cohort_rule_op": ["IS"],
            "cohort_rule_operand_tag": [""],
            "cohort_rule_operand_value": [""],
        },
        follow_redirects=False,
    )
    assert rejected.status_code == 400
    assert "var arrivedUnsaved = true;" in rejected.text
