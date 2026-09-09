"""The Instruments lock card explains every state it locks.

Segment 19I Item 6 PR 2. PR 1 gated `expired` and `archived` — the
page correctly stopped offering the controls and did not say why,
which is the silence Item 3 named on the roster pages. The card that
already explained `ready` now covers all three, each with the way out
that its own state actually has:

* `ready` and `expired` -> `revert_session_to_draft` accepts both, so
  the card carries the inline revert form.
* `archived` -> `revert` answers **409**; the way out is
  `unarchive_session`, surfaced as bulk-unarchive on
  `/operator/sessions/archived`. The card names that path and offers
  no control, rather than growing a second unarchive affordance on a
  Setup page.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import ReviewSession
from tests.integration.test_instruments_lifecycle_gate import (
    EDITABLE,
    LOCKED,
    ALL_STATES,
    _seed,
)


def _page(client: TestClient, s: ReviewSession) -> str:
    return client.get(f"/operator/sessions/{s.id}/instruments").text


@pytest.mark.parametrize("state", ALL_STATES)
def test_the_lock_card_renders_exactly_where_the_page_is_locked(
    db: Session, client: TestClient, state: str
) -> None:
    s, _ = _seed(client, db, code=f"lc-render-{state}")
    s.status = state
    db.commit()

    present = '<div class="card lock">' in _page(client, s)

    assert present is (state in LOCKED), state


@pytest.mark.parametrize(
    ("state", "phrase"),
    (
        ("ready", "cannot be modified while the session is ongoing"),
        ("expired", "cannot be modified because the session is closed"),
        ("archived", "cannot be modified because the session is archived"),
    ),
)
def test_the_card_names_the_state_it_is_explaining(
    db: Session, client: TestClient, state: str, phrase: str
) -> None:
    """`expired` reads **Closed** to an operator
    (`services/lifecycle_display.py`), so the copy says closed, not
    expired."""
    s, _ = _seed(client, db, code=f"lc-copy-{state}")
    s.status = state
    db.commit()

    assert phrase in _page(client, s), state


@pytest.mark.parametrize("state", ("ready", "expired"))
def test_revertable_states_carry_the_inline_revert_form(
    db: Session, client: TestClient, state: str
) -> None:
    s, _ = _seed(client, db, code=f"lc-form-{state}")
    s.status = state
    db.commit()

    page = _page(client, s)

    assert f'action="/operator/sessions/{s.id}/revert"' in page, state
    assert 'data-delete-btn="revert"' in page, state


def test_archived_names_unarchive_instead_of_revert(
    db: Session, client: TestClient
) -> None:
    """The whole point of the archived branch: `revert` 409s from
    `archived`, so a revert form here would be a dead control — the
    shape Item 3 removed from the roster pages."""
    s, _ = _seed(client, db, code="lc-archived")
    s.status = "archived"
    db.commit()

    page = _page(client, s)

    assert 'href="/operator/sessions/archived"' in page
    assert "Unarchive" in page
    assert f'action="/operator/sessions/{s.id}/revert"' not in page
    assert 'data-delete-btn="revert"' not in page


@pytest.mark.parametrize("state", ("ready", "expired"))
def test_the_offered_revert_actually_works(
    db: Session, client: TestClient, state: str
) -> None:
    """A control the card offers has to do something. `revert` accepts
    `ready` and `expired`; this posts what the form carries."""
    s, _ = _seed(client, db, code=f"lc-works-{state}")
    s.status = state
    db.commit()

    response = client.post(
        f"/operator/sessions/{s.id}/revert",
        data={"confirm": "true", "return_to": "instruments"},
        follow_redirects=False,
    )
    db.expire_all()

    assert response.status_code == 303, (state, response.text[:200])
    assert db.get(ReviewSession, s.id).status == "draft", state


@pytest.mark.parametrize("state", EDITABLE)
def test_no_lock_copy_while_editable(
    db: Session, client: TestClient, state: str
) -> None:
    s, _ = _seed(client, db, code=f"lc-none-{state}")
    s.status = state
    db.commit()

    assert "cannot be modified" not in _page(client, s), state
