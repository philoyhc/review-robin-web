"""The Instruments page and routes answer to one lifecycle predicate.

Segment 19I Item 6 PR 1. Before this, `_can_edit_instrument` was
`not is_ready`, so the whole instrument surface was protected exactly
while the session was *collecting* and stopped being protected the
moment collection **ended**. On `expired` and `archived` the page
rendered live Delete buttons, the routes permitted the delete, and the
`Instrument -> assignments -> responses` cascade took a submitted
answer with it.

The matrix below is the measurement that found it, turned into a
gate. It asserts **both halves on every state** — what the route
answers and what the page offers — so neither can drift from the
other without a failure.
"""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Assignment, Instrument, Response

from ._instrument_states import (
    ALL_STATES,
    EDITABLE,
    LOCKED,
    seed_session_with_instruments as _seed,
)


def _live_delete_buttons(page: str) -> int:
    """Delete buttons an operator can actually submit — the confirm
    tick enables them client-side, but `type="button"` ones are dead
    markup that no tick reaches."""
    buttons = re.findall(
        r'<button class="btn destructive"[^>]*>Delete</button>', page, re.S
    )
    return len([b for b in buttons if 'type="submit"' in b])


@pytest.mark.parametrize("state", ALL_STATES)
def test_the_delete_route_answers_by_editability(
    db: Session, client: TestClient, state: str
) -> None:
    s, iid = _seed(client, db, code=f"ilg-route-{state}")
    s.status = state
    db.commit()

    response = client.post(
        f"/operator/sessions/{s.id}/instruments/{iid}/delete",
        data={"confirm": "true"},
        follow_redirects=False,
    )

    if state in EDITABLE:
        assert response.status_code == 303, (state, response.text[:200])
    else:
        assert response.status_code == 409, (state, response.status_code)


@pytest.mark.parametrize("state", LOCKED)
def test_a_locked_session_keeps_its_instrument_assignment_and_response(
    db: Session, client: TestClient, state: str
) -> None:
    """The cascade is the reason this matters: `Instrument` ->
    `assignments` -> `responses`, both `delete-orphan`. On `expired`
    and `archived` this delete used to succeed and take a submitted
    answer with it."""
    s, iid = _seed(client, db, code=f"ilg-keep-{state}")
    s.status = state
    db.commit()

    client.post(
        f"/operator/sessions/{s.id}/instruments/{iid}/delete",
        data={"confirm": "true"},
        follow_redirects=False,
    )
    db.expire_all()

    assert db.get(Instrument, iid) is not None, state
    assert len(db.execute(select(Assignment)).scalars().all()) == 1, state
    assert len(db.execute(select(Response)).scalars().all()) == 1, state


@pytest.mark.parametrize("state", EDITABLE)
def test_an_editable_session_still_deletes(
    db: Session, client: TestClient, state: str
) -> None:
    """The gate narrows `expired` / `archived` only — `validated`
    keeps every control it had."""
    s, iid = _seed(client, db, code=f"ilg-del-{state}")
    s.status = state
    db.commit()

    client.post(
        f"/operator/sessions/{s.id}/instruments/{iid}/delete",
        data={"confirm": "true"},
        follow_redirects=False,
    )
    db.expire_all()

    assert db.get(Instrument, iid) is None, state


@pytest.mark.parametrize("state", ALL_STATES)
def test_the_page_offers_delete_exactly_where_the_route_allows_it(
    db: Session, client: TestClient, state: str
) -> None:
    """The other half of the matrix. A live button on a state the
    route refuses is the dead control Item 3 removed from the roster
    pages; a live button on a state the route *permits* is what this
    item found."""
    s, _ = _seed(client, db, code=f"ilg-page-{state}")
    s.status = state
    db.commit()

    page = client.get(f"/operator/sessions/{s.id}/instruments").text

    if state in EDITABLE:
        assert _live_delete_buttons(page) > 0, state
    else:
        assert _live_delete_buttons(page) == 0, state


@pytest.mark.parametrize("state", LOCKED)
def test_the_card_lock_toggle_is_disabled_on_every_locked_state(
    db: Session, client: TestClient, state: str
) -> None:
    """Unlock is the card's entry into edit mode, so it follows the
    same predicate as the mutations it opens."""
    s, _ = _seed(client, db, code=f"ilg-lock-{state}")
    s.status = state
    db.commit()

    page = client.get(f"/operator/sessions/{s.id}/instruments").text
    unlocks = re.findall(r"<a[^>]*data-instrument-unlock-toggle[^>]*>", page, re.S)

    assert unlocks, state
    # Both gates, asserted apart. A bare `"disabled" in anchor` is
    # satisfied by `aria-disabled` alone, so it cannot tell the class
    # gate from the ARIA one — reverting the class changed nothing and
    # the test still passed. Caught by mutation, not by reading.
    for anchor in unlocks:
        assert 'class="btn secondary disabled"' in anchor, (state, anchor)
        assert 'aria-disabled="true"' in anchor, (state, anchor)


@pytest.mark.parametrize("state", ALL_STATES)
def test_editing_query_param_cannot_open_a_card_on_a_locked_session(
    db: Session, client: TestClient, state: str
) -> None:
    """`?editing=<id>` is the no-JS way into edit mode. It was already
    refused on `ready`; it follows `can_edit` now."""
    s, iid = _seed(client, db, code=f"ilg-edit-{state}")
    s.status = state
    db.commit()

    page = client.get(
        f"/operator/sessions/{s.id}/instruments?editing={iid}"
    ).text
    # Match the card element, not the bare attribute: `base.html`'s
    # inline CSS carries `[data-instrument-locked="false"]` selectors,
    # so a substring test for the attribute is true on every page and
    # asserts nothing.
    unlocked_cards = re.findall(
        r'data-instrument-card="\d+"\s+data-instrument-locked="false"', page
    )

    assert bool(unlocked_cards) is (state in EDITABLE), (state, unlocked_cards)


@pytest.mark.parametrize(
    ("state", "expected"),
    (
        ("ready", "Revert to draft to add or delete instruments."),
        ("expired", "Revert to draft to add or delete instruments."),
        ("archived", "Unarchive this session to add or delete instruments."),
    ),
)
def test_the_disabled_title_names_a_way_out_that_exists(
    db: Session, client: TestClient, state: str, expected: str
) -> None:
    """Widening the gate without this would have left the tooltips
    telling an `archived` operator to "revert to draft" — a path
    `revert_session_to_draft` refuses, since it accepts only `ready`
    and `expired`. `archived` leaves through `unarchive_session`.

    Pinned because it was not: blanking `lock_action` passed the
    whole suite.
    """
    s, _ = _seed(client, db, code=f"ilg-title-{state}")
    s.status = state
    db.commit()

    page = client.get(f"/operator/sessions/{s.id}/instruments").text

    assert f'title="{expected}"' in page, state
    if state == "archived":
        assert "Revert to draft to add or delete" not in page


@pytest.mark.parametrize("state", EDITABLE)
def test_no_lifecycle_disabled_title_while_editable(
    db: Session, client: TestClient, state: str
) -> None:
    s, _ = _seed(client, db, code=f"ilg-notitle-{state}")
    s.status = state
    db.commit()

    page = client.get(f"/operator/sessions/{s.id}/instruments").text

    assert "to add or delete instruments." not in page, state
