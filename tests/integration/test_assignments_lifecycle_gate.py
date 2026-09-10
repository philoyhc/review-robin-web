"""The Assignments page and its routes answer to one predicate.

Segment 19I Item 8. The template gated its whole operator-actions
card on `not is_ready` while all five mutating routes gate on
`_require_editable` (`is_editable`). The two disagreed on **three of
five** states, in both directions:

* `expired` / `archived` — the page offered row checkboxes and live
  bulk Inactivate / Activate that every route refuses. Item 3's
  dead-control shape, on the surface Item 3 did not cover.
* `ready` — it went the other way and hid the **search** along with
  the controls, removing the only way to find a row on exactly the
  state an operator checks who is assigned to whom.

The matrix asserts both halves on every state, so neither can drift
from the other silently.
"""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Assignment

from ._assignment_states import (
    ALL_STATES,
    EDITABLE,
    LOCKED,
    seed_session_with_assignment as _seed,
)

# Match rendered elements, never bare class names: `base.html` carries
# `.operator-actions-card` in its inline CSS 15 times, so a substring
# test for it is true on every page and asserts nothing. That was a
# real vacuous check caught while measuring this item.
# The card, not its exact class list: 19I Item 12 added
# ``grid-right`` when the author asked for it back at half
# width, and a whole-attribute match broke on a layout class
# that has nothing to do with what these tests check.
CARD = 'class="card operator-actions-card'
SEARCH_INPUT = '<input type="text" name="q"'
SEARCH_BY = '<select name="search_by">'
BULK_FORM = '<form id="assignments-bulk-form"'
ROW_CHECKBOX = 'name="assignment_ids"'
SELECT_ALL = 'id="assignments-select-all"'
INACTIVATE = 'id="assignments-inactivate-btn"'
ACTIVATE = 'id="assignments-activate-btn"'
SELECTED_PILL = 'id="assignments-selected-count"'


def _page(client: TestClient, s, *, q: str = "") -> str:
    url = f"/operator/sessions/{s.id}/assignments"
    if q:
        url = f"{url}?q={q}"
    return client.get(url).text


@pytest.mark.parametrize("state", ALL_STATES)
def test_the_bulk_routes_answer_by_editability(
    db: Session, client: TestClient, state: str
) -> None:
    s = _seed(client, db, code=f"alg-route-{state}")
    s.status = state
    db.commit()
    aid = db.execute(select(Assignment.id).order_by(Assignment.id)).scalars().first()

    for action in ("bulk-inactivate", "bulk-activate"):
        response = client.post(
            f"/operator/sessions/{s.id}/assignments/{action}",
            data={"assignment_ids": str(aid), "confirm": "true"},
            follow_redirects=False,
        )
        if state in EDITABLE:
            assert response.status_code == 303, (state, action, response.text[:200])
        else:
            assert response.status_code == 409, (state, action, response.status_code)


@pytest.mark.parametrize("state", ALL_STATES)
def test_the_read_only_half_renders_in_every_state(
    db: Session, client: TestClient, state: str
) -> None:
    """Item 3's rule: reading a finished session is legitimate, so the
    search survives every state. This is the half `ready` used to
    lose."""
    s = _seed(client, db, code=f"alg-read-{state}")
    s.status = state
    db.commit()

    page = _page(client, s)

    assert CARD in page, state
    assert SEARCH_INPUT in page, state
    assert SEARCH_BY in page, state


@pytest.mark.parametrize("state", ALL_STATES)
def test_clear_renders_in_every_state_when_a_filter_is_applied(
    db: Session, client: TestClient, state: str
) -> None:
    s = _seed(client, db, code=f"alg-clear-{state}")
    s.status = state
    db.commit()

    assert ">Clear</a>" in _page(client, s, q="Ana"), state


@pytest.mark.parametrize("state", ALL_STATES)
def test_the_selection_surface_renders_only_while_editable(
    db: Session, client: TestClient, state: str
) -> None:
    s = _seed(client, db, code=f"alg-sel-{state}")
    s.status = state
    db.commit()

    page = _page(client, s)
    editable = state in EDITABLE

    for marker in (
        BULK_FORM,
        ROW_CHECKBOX,
        SELECT_ALL,
        INACTIVATE,
        ACTIVATE,
        SELECTED_PILL,
    ):
        assert (marker in page) is editable, (state, marker)


@pytest.mark.parametrize("state", LOCKED)
def test_the_self_review_toggle_is_disabled_on_every_locked_state(
    db: Session, client: TestClient, state: str
) -> None:
    """The per-instrument self-review checkbox posts to a route that
    gates on `_require_editable` like the rest, so it follows the same
    predicate — it was `is_ready` alone."""
    s = _seed(client, db, code=f"alg-self-{state}")
    s.status = state
    db.commit()

    page = _page(client, s)
    boxes = re.findall(r"<input type=\"checkbox\"[^>]*data-self-review-instrument[^>]*>", page, re.S)

    assert boxes, state
    assert all("disabled" in b for b in boxes), state


@pytest.mark.parametrize("state", EDITABLE)
def test_the_self_review_toggle_is_live_while_editable(
    db: Session, client: TestClient, state: str
) -> None:
    s = _seed(client, db, code=f"alg-self-live-{state}")
    s.status = state
    db.commit()

    page = _page(client, s)
    boxes = re.findall(r"<input type=\"checkbox\"[^>]*data-self-review-instrument[^>]*>", page, re.S)

    assert boxes, state
    assert all("disabled" not in b for b in boxes), state


@pytest.mark.parametrize(
    ("state", "expected"),
    (
        ("ready", "Revert to draft"),
        ("expired", "Revert to draft"),
        ("archived", "Unarchive this session"),
    ),
)
def test_the_disabled_title_names_a_way_out_that_exists(
    db: Session, client: TestClient, state: str, expected: str
) -> None:
    """As Item 6: `revert_session_to_draft` accepts `ready` and
    `expired` only, so telling an `archived` operator to revert names
    a path the route refuses."""
    s = _seed(client, db, code=f"alg-title-{state}")
    s.status = state
    db.commit()

    page = _page(client, s)

    assert f"{expected} to change self-review inclusion." in page, state
    if state == "archived":
        assert "Revert to draft to change self-review" not in page
