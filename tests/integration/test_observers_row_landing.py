"""Row actions on Setup-Observers land on the row they acted on.

19P.2 rung 1 — the contract Reviewers got at 19P.1, carried here.
A bare 303 lands at the top of the document; two things carry the
operator's place through the POST: the pager ``offset``, and a
fragment naming the acted-on row.

Whether the browser actually scrolls is checked in Chromium — the
suite has no layout engine, so ``scroll-margin-top`` is invisible
to it. What is pinned here is the wiring on both halves: the route
reads what the page sends, and the page sends a real value.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Observer, ReviewSession


def _make_session(
    client: TestClient, db: Session, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Obs", "code": code, "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    review_session.observers_enabled = True
    db.commit()
    db.refresh(review_session)
    return review_session


def _seed(db: Session, session_id: int, names: list[str]) -> list[Observer]:
    rows = [
        Observer(
            session_id=session_id,
            email=f"{name.lower()}@example.org",
            display_name=name,
        )
        for name in names
    ]
    db.add_all(rows)
    db.commit()
    for row in rows:
        db.refresh(row)
    return rows


# Every row action, not the two that happened to get written first:
# a cold read on the Reviewers original deleted `offset=` / `anchor=`
# from the single commonest action and the whole suite stayed green.
# `cohort-rule` is on this list and is not on the Reviewers one —
# it is the row action this page has and that one does not.
_ROW_ACTIONS = [
    ("update", "{base}/{rid}/update", {
        "display_name": "Alice", "email": "alice@example.org",
        "tag_1": "", "status": "active",
    }),
    ("bulk-inactivate", "{base}/bulk-inactivate", {"observer_ids": ["{rid}"]}),
    ("bulk-reactivate", "{base}/bulk-reactivate", {"observer_ids": ["{rid}"]}),
    ("cohort-rule", "{base}/cohort-rule", {
        "observer_ids": ["{rid}"],
        "cohort_combinator": "AND",
        "cohort_rule_field": "reviewer.tag1",
        "cohort_rule_op": "IS",
        "cohort_rule_operand_tag": "observer.tag1",
        "cohort_rule_operand_value": "blue",
    }),
]


def _post_row_action(client, base, rid, template, data, **extra):
    payload = {k: ([rid] if v == ["{rid}"] else v) for k, v in data.items()}
    payload.update(extra)
    return client.post(
        template.format(base=base, rid=rid), data=payload,
        follow_redirects=False,
    )


@pytest.mark.parametrize("name,template,data", _ROW_ACTIONS)
def test_every_row_action_lands_on_the_row_it_acted_on(
    db: Session, client: TestClient, name: str, template: str, data: dict
) -> None:
    review_session = _make_session(client, db, code=f"obs-anch-{name[:6]}")
    rows = _seed(db, review_session.id, ["Alice"])
    base = f"/operator/sessions/{review_session.id}/observers"

    response = _post_row_action(client, base, rows[0].id, template, data)
    assert response.status_code == 303, f"{name}: {response.text[:400]}"
    assert response.headers["location"].endswith(
        f"#observer-row-{rows[0].id}"
    ), f"{name}: {response.headers['location']}"


@pytest.mark.parametrize("name,template,data", _ROW_ACTIONS)
def test_every_row_action_carries_the_pager_offset(
    db: Session, client: TestClient, name: str, template: str, data: dict
) -> None:
    """Without it the 303 answered with page 1 whatever page the action
    was taken from — so the operator lost their place AND the row the
    anchor names was not in the response to be found."""
    review_session = _make_session(client, db, code=f"obs-off-{name[:6]}")
    rows = _seed(db, review_session.id, ["Alice"])
    base = f"/operator/sessions/{review_session.id}/observers"

    loc = _post_row_action(
        client, base, rows[0].id, template, data, filter_offset=200
    ).headers["location"]
    assert "offset=200" in loc, f"{name}: {loc}"

    plain = _post_row_action(
        client, base, rows[0].id, template, data
    ).headers["location"]
    assert "offset=" not in plain, f"{name}: {plain}"


def test_the_page_actually_sends_the_offset_it_asks_the_route_to_read(
    db: Session, client: TestClient
) -> None:
    """The render half, which the route-level tests above cannot see.

    They POST ``filter_offset`` themselves, so they prove the route
    READS the field and never that the page SENDS one. Seeded past the
    200-row page cap so the value is a real non-zero offset: a field
    rendering ``0`` on every page would satisfy a presence check while
    carrying nothing.
    """
    review_session = _make_session(client, db, code="obs-sends-offset")
    _seed(db, review_session.id, [f"O{n}" for n in range(1, 231)])
    base = f"/operator/sessions/{review_session.id}/observers"

    bulk = re.search(
        r'<form[^>]*id="observers-bulk-form".*?</form>',
        client.get(f"{base}?offset=200").text, re.S,
    )
    assert bulk, "bulk form not rendered on page 2"
    assert 'name="filter_offset" value="200"' in bulk.group(0), (
        "the bulk form does not carry the page it was rendered on"
    )

    rid = db.execute(
        select(Observer.id).where(Observer.session_id == review_session.id)
    ).scalars().all()[210]
    edit = re.search(
        r'<form[^>]*id="observer-edit-form".*?</form>',
        client.get(f"{base}?edit_id={rid}").text, re.S,
    )
    assert edit, "edit form not rendered"
    assert 'name="filter_offset" value="200"' in edit.group(0), (
        "the edit form does not carry the page the edited row is on"
    )


def test_delete_lands_on_the_table_card_because_its_rows_are_gone(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="obs-delanchor")
    rows = _seed(db, review_session.id, ["Alice"])

    response = client.post(
        f"/operator/sessions/{review_session.id}/observers/bulk-delete",
        data={
            "observer_ids": [rows[0].id],
            "confirm": "true",
            "filter_offset": 200,
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text[:400]
    loc = response.headers["location"]
    assert loc.endswith("#observers-table-card"), loc
    assert "#observer-row-" not in loc, (
        "delete anchored a row it had just removed"
    )
    # A delete has no row to name, but it still has a page to come back
    # to: without the offset an operator deleting from page 6 of a long
    # roster was answered with page 1. The parametrized offset test
    # above cannot cover this action — deleting the row it acts on
    # leaves nothing for its anchor assertion to name — so the offset
    # half is asserted here. It was the one mutation that survived.
    assert "offset=200" in loc, loc


def test_rows_and_the_fallback_are_both_present_for_the_landing(
    db: Session, client: TestClient
) -> None:
    """The two halves the anchor needs, and that they refer to each other.

    A row the redirect can name carries the class that gives it its
    landing margin, and the fallback script exists for the case the
    fragment cannot resolve (a status change that drops the row out of
    a filtered view).
    """
    review_session = _make_session(client, db, code="obs-landing")
    rows = _seed(db, review_session.id, ["Alice"])
    body = client.get(
        f"/operator/sessions/{review_session.id}/observers"
    ).text

    row = re.search(
        rf'<tr\b[^>]*id="observer-row-{rows[0].id}"[^>]*>', body, re.S
    )
    assert row, "the row the redirect names is not rendered"
    assert "row-action-target" in row.group(0), (
        "the row carries no landing margin"
    )
    # Page-wide by nature: the rule lives in `base.html`'s inline
    # `<style>`, which every page carries. So this guards that the base
    # rule still exists, not anything Observers-specific — the scoped
    # half is the class on the row, asserted above.
    assert "tr.row-action-target" in body, "no rule gives it that margin"

    # Read the fallback's OWN text. `'"observers-table-card"' in body`
    # is satisfied by the table card's `id=` attribute, which renders
    # regardless — so deleting the operative lines of the script would
    # leave that assertion green.
    script = re.search(
        r"<script>(?:(?!</script>).)*?#observer-row-.*?</script>", body, re.S
    )
    assert script, "the fallback script is gone"
    for needle in ("getElementById", "observers-table-card", "scrollIntoView"):
        assert needle in script.group(0), f"the fallback lost {needle}"


def test_add_carries_the_active_filter_into_add_mode(
    db: Session, client: TestClient
) -> None:
    """The filter is lost at the NAVIGATION, not at the POST.

    `Add` linked to a bare `?add=1`, so the add page rendered
    unfiltered and its hidden `filter_*` fields held defaults — which
    the create route then faithfully honored all the way back to an
    unfiltered list.
    """
    review_session = _make_session(client, db, code="obs-addfilter")
    _seed(db, review_session.id, ["Alice", "Bob"])
    base = f"/operator/sessions/{review_session.id}/observers"

    body = client.get(f"{base}?status=inactive&q=ali").text
    link = re.search(r'<a[^>]*>\s*Add\s*</a>', body)
    assert link, "no Add link"
    assert "status=inactive" in link.group(0), link.group(0)
    assert "q=ali" in link.group(0), link.group(0)

    # An unfiltered view carries neither — `status=all` is the default
    # and an empty search is nothing, so spelling them out would be
    # noise in the URL.
    plain = re.search(
        r'<a[^>]*>\s*Add\s*</a>', client.get(base).text
    ).group(0)
    assert "status=" not in plain and "q=" not in plain, plain


def test_creating_a_row_pages_to_where_the_new_row_actually_is(
    db: Session, client: TestClient
) -> None:
    """Rows list by id, so a create appends past the end.

    On a roster over one page the new row is not on the page the add
    form was submitted from, so the redirect's `#observer-row-<id>`
    named a row the response did not render and the landing fell back
    to the table card. `focus` moves the window to the row instead.
    """
    review_session = _make_session(client, db, code="obs-createpage")
    _seed(db, review_session.id, [f"O{n}" for n in range(1, 231)])
    base = f"/operator/sessions/{review_session.id}/observers"

    response = client.post(
        f"{base}/create",
        data={
            "display_name": "Zed", "email": "zed@example.org",
            "tag_1": "", "status": "active", "filter_offset": 0,
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text[:400]
    loc = response.headers["location"]
    created = db.execute(
        select(Observer).where(Observer.email == "zed@example.org")
    ).scalar_one()
    assert f"focus={created.id}" in loc, loc
    assert loc.endswith(f"#observer-row-{created.id}"), loc

    # The row the fragment names is actually in the response it lands on.
    landed = client.get(loc.split("#")[0]).text
    assert f'id="observer-row-{created.id}"' in landed, (
        "the redirect lands on a page that does not render the new row"
    )
    assert ">Zed<" in landed


def test_a_create_carries_the_pager_offset_too(
    db: Session, client: TestClient
) -> None:
    """`_ROW_ACTIONS` structurally cannot cover a create — there is no
    row id to act on until the POST returns — so the offset half is
    asserted here.

    Today the value can only be `0` through the UI, because `Add`
    carries the filter but not the page. The wiring is still real: it
    is what a future `Add` that keeps the page would ride on, and
    without this the parameter could be deleted with the whole suite
    green. It was one of two mutations that survived the first pass.
    """
    review_session = _make_session(client, db, code="obs-create-off")
    base = f"/operator/sessions/{review_session.id}/observers"

    loc = client.post(
        f"{base}/create",
        data={
            "display_name": "Ada", "email": "ada@example.org",
            "tag_1": "", "status": "active", "filter_offset": 200,
        },
        follow_redirects=False,
    ).headers["location"]
    assert "offset=200" in loc, loc


def test_entering_edit_mode_lands_on_the_row_being_edited(
    db: Session, client: TestClient
) -> None:
    """Entering edit mode is a navigation like any other.

    The `Edit` button is client-side — it builds a URL from the checked
    row — so what is pinned here is that the script builds a fragment at
    all. Without it, `Edit` on a mid-table row threw the operator to the
    top of the document while the row it named sat off screen; the
    `row-action-target` on the edit row had nothing navigating to it.
    """
    review_session = _make_session(client, db, code="obs-editnav")
    body = client.get(
        f"/operator/sessions/{review_session.id}/observers"
    ).text

    script = re.search(
        r'<script>(?:(?!</script>).)*?"\?edit_id="(?:(?!</script>).)*?</script>',
        body, re.S,
    )
    assert script, "the Edit navigation script is gone"
    assert '"#observer-row-"' in script.group(0), (
        "Edit navigates without a fragment, so it lands at the top"
    )

    # And the row that fragment resolves onto carries the margin. The
    # edit row is a different `<tr>` from the display row, so the class
    # has to be on both; without this the edit row's copy could be
    # deleted with the suite green.
    row = _seed(db, review_session.id, ["Alice"])[0]
    edit_page = client.get(
        f"/operator/sessions/{review_session.id}/observers?edit_id={row.id}"
    ).text
    edit_row = re.search(
        rf'<tr\b[^>]*id="observer-row-{row.id}"[^>]*>', edit_page, re.S
    )
    assert edit_row, "the edit row is not rendered with the id Edit names"
    assert "observer-edit-row" in edit_row.group(0), edit_row.group(0)
    assert "row-action-target" in edit_row.group(0), (
        "the edit row carries no landing margin"
    )


def test_add_lands_on_the_row_it_opens(
    db: Session, client: TestClient
) -> None:
    """The other half of the `Add` fix.

    Carrying the filter stopped the add page rendering unfiltered; it
    did nothing about where the page arrives. `Add` from mid-roster
    still landed at the top of the document until the link named the
    add row, which is the editor on this page.
    """
    review_session = _make_session(client, db, code="obs-addanchor")
    _seed(db, review_session.id, ["Alice", "Bob"])
    base = f"/operator/sessions/{review_session.id}/observers"

    link = re.search(r'<a[^>]*>\s*Add\s*</a>', client.get(base).text)
    assert link, "no Add link"
    assert "#observers-row-editor" in link.group(0), link.group(0)

    # And the row that fragment names is actually rendered in add mode.
    add_page = client.get(f"{base}?add=1").text
    row = re.search(r'<tr\b[^>]*id="observers-row-editor"[^>]*>', add_page)
    assert row, "the add row does not carry the id the link names"
    assert "row-action-target" in row.group(0), (
        "the add row carries no landing margin"
    )
