"""19S Item 10 rung 2 — Session Home's Owners card stages, like Create's.

Author's direction, 2026-09-23: conform Session Home's Owners card to
Create's, reusing its logic. The edit table is ``_owners_stager_js``'s:
Add owner and Remove change the table only, each row carries a hidden
``owners`` input bound to the details card's form, and the card's Save
sends the whole set behind ``owners_present`` (rung 1 is the route).

What JavaScript does — the last-owner disable, the self-removal confirm,
Cancel restoring the rows — was driven in Chromium; the suite runs no
browser, so this file pins the markup those behaviors hang on.
"""

from __future__ import annotations

import re

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession

CREATOR = "alice@example.edu"


def _session_home(client: TestClient, db: Session, *, editing: bool = True) -> tuple[ReviewSession, str]:
    response = client.post(
        "/operator/sessions",
        data={"name": "Staged", "code": "OWN-STAGE", "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "OWN-STAGE")
    ).scalar_one()
    suffix = "?editing=1" if editing else ""
    return review_session, client.get(
        f"/operator/sessions/{review_session.id}{suffix}"
    ).text


def _stager(body: str) -> str:
    start = body.index("data-owners-stager")
    end = body.index("data-owners-add>Add owner", start)
    return body[start:end + len("data-owners-add>Add owner")]


def test_the_edit_table_is_a_stager_bound_to_the_cards_form(
    client: TestClient, db: Session
) -> None:
    review_session, body = _session_home(client, db)
    stager = _stager(body)
    form = f'form="config-save-{review_session.id}"'

    assert f'data-owners-form="config-save-{review_session.id}"' in stager
    assert f'data-owners-self="{CREATOR}"' in stager, (
        "the stager knows whose row asks before removing"
    )
    assert "data-owners-table" in stager
    assert "data-owners-add" in stager
    assert re.search(
        rf'<input type="hidden" name="owners_present" value="1"\s+{form}>', stager
    )
    assert re.search(rf'value="{CREATOR}"\s+{form}>', stager)


def test_the_stager_script_is_on_the_page(client: TestClient, db: Session) -> None:
    _, body = _session_home(client, db)

    assert "document.querySelectorAll('[data-owners-stager]')" in body
    assert "function syncRemoves()" in body
    assert "window.confirm(" in body


def test_the_marker_rides_with_the_rows_in_the_edit_block(
    client: TestClient, db: Session
) -> None:
    """The marker is rendered once, inside the stager root, which is the
    card's ``data-edit-only`` block: a card that posts the set always
    posts the marker, and nothing else on the page does. The root being
    ``data-edit-only`` is also what staging's dirty-marking hangs on —
    the card's ``onEdit`` only counts events from inside such a block."""
    _, body = _session_home(client, db)
    root = re.search(r"<div ([^>]*data-owners-stager[^>]*)>", body)

    assert root is not None
    assert "data-edit-only" in root.group(1)
    assert body.count('name="owners_present"') == 1
    assert 'name="owners_present"' in _stager(body)


def test_the_picker_box_is_not_required(client: TestClient, db: Session) -> None:
    """An empty picker must not block the card's Save."""
    _, body = _session_home(client, db)
    box = body.split('id="config-add-owner-email"', 1)[1].split(">", 1)[0]

    assert "required" not in box


def test_the_subtitle_says_owners_save_with_the_card(
    client: TestClient, db: Session
) -> None:
    _, body = _session_home(client, db, editing=False)

    assert re.search(r"changes are saved with\s+the card\.", body)
