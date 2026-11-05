"""20H Item 1: the single-row Add form and an address edit refuse a
second row on one directory account, on Reviewers, Reviewees and
Observers, as an append refuses it (author, 2026-11-03). The suite's
directory (`cordware.graph.FakeDirectory`) knows Jane by mail,
``jane.tan@example.edu``, and by sign-in name, ``e0123456@example.edu``:
two addresses, one account."""

from __future__ import annotations

import html

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Observer, Reviewee, Reviewer

from ._feature_toggles import enable_observers
from ._invitation_states import _create_session

JANE_ID = "11111111-1111-4111-8111-111111111111"
FORM = {"profile_link": "", "tag_1": "", "tag_2": "", "tag_3": "", "status": "active"}
ROSTERS = [
    ("reviewers", Reviewer, "email", "name"),
    ("reviewees", Reviewee, "email_or_identifier", "name"),
    ("observers", Observer, "email", "display_name"),
]
REFUSAL = (
    "'e0123456@example.edu' is the same directory account as the {label} "
    "'jane.tan@example.edu' already on the roster. Edit that row instead."
)


def _session(client: TestClient, db: Session, code: str):
    session = _create_session(client, db, code=code)
    enable_observers(db, session)
    return session


def _count(db: Session, model, session_id: int) -> int:
    db.expire_all()
    return db.execute(
        select(func.count()).select_from(model).where(model.session_id == session_id)
    ).scalar_one()


def _add(client: TestClient, base: str, field: str, name_field: str, address: str, name: str):
    return client.post(
        f"{base}/create", data={**FORM, field: address, name_field: name}, follow_redirects=False
    )


@pytest.mark.parametrize(("roster", "model", "field", "name_field"), ROSTERS)
def test_adding_a_second_row_on_one_account_is_refused(
    client: TestClient, db: Session, roster: str, model, field: str, name_field: str
) -> None:
    session = _session(client, db, f"same-add-{roster}")
    base = f"/operator/sessions/{session.public_id}/{roster}"
    assert _add(client, base, field, name_field, "jane.tan@example.edu", "Jane").status_code == 303
    refused = _add(client, base, field, name_field, "e0123456@example.edu", "Jane")
    assert refused.status_code != 303
    assert REFUSAL.format(label=roster[:-1]) in html.unescape(refused.text)
    assert _count(db, model, session.id) == 1


@pytest.mark.parametrize(("roster", "model", "field", "name_field"), ROSTERS)
def test_an_address_edit_onto_a_held_account_is_refused(
    client: TestClient, db: Session, roster: str, model, field: str, name_field: str
) -> None:
    session = _session(client, db, f"same-edit-{roster}")
    base = f"/operator/sessions/{session.public_id}/{roster}"
    assert _add(client, base, field, name_field, "jane.tan@example.edu", "Jane").status_code == 303
    assert _add(client, base, field, name_field, "other@example.edu", "Jane").status_code == 303
    db.expire_all()
    other = db.execute(
        select(model).where(
            model.session_id == session.id, getattr(model, field) == "other@example.edu"
        )
    ).scalar_one()
    refused = client.post(
        f"{base}/{other.id}/update",
        data={**FORM, field: "e0123456@example.edu", name_field: "Jane"},
        follow_redirects=False,
    )
    assert refused.status_code != 303
    assert REFUSAL.format(label=roster[:-1]) in html.unescape(refused.text)
    db.refresh(other)
    assert getattr(other, field) == "other@example.edu" and other.directory_object_id is None


@pytest.mark.parametrize(("roster", "model", "field", "name_field"), ROSTERS)
def test_editing_the_holder_itself_and_an_unbound_lookup_are_allowed(
    client: TestClient, db: Session, roster: str, model, field: str, name_field: str
) -> None:
    """The row holding the account may move to its other address, and an
    address the directory does not know binds nothing, so it is allowed."""
    session = _session(client, db, f"same-ok-{roster}")
    base = f"/operator/sessions/{session.public_id}/{roster}"
    assert _add(client, base, field, name_field, "jane.tan@example.edu", "Jane").status_code == 303
    jane = db.execute(select(model).where(model.session_id == session.id)).scalar_one()
    moved = client.post(
        f"{base}/{jane.id}/update",
        data={**FORM, field: "e0123456@example.edu", name_field: "Jane"},
        follow_redirects=False,
    )
    assert moved.status_code == 303
    db.refresh(jane)
    assert jane.directory_object_id == JANE_ID  # the reused answer still binds
    assert _add(client, base, field, name_field, "stranger@example.edu", "Sam").status_code == 303
    assert _count(db, model, session.id) == 2


def test_an_inactive_row_still_holds_its_account(client: TestClient, db: Session) -> None:
    session = _create_session(client, db, code="same-inactive")
    base = f"/operator/sessions/{session.public_id}/reviewers"
    assert (
        client.post(
            f"{base}/create",
            data={**FORM, "email": "jane.tan@example.edu", "name": "Jane", "status": "inactive"},
            follow_redirects=False,
        ).status_code
        == 303
    )
    refused = _add(client, base, "email", "name", "e0123456@example.edu", "Jane")
    assert refused.status_code != 303
    assert _count(db, Reviewer, session.id) == 1


def test_an_add_and_an_edit_look_the_address_up_once(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The refusal's lookup is the binding's: one directory call each."""
    from app.web.routes_operator import _shared
    from cordware.graph import FakeDirectory

    calls: list[str] = []

    class _Counting(FakeDirectory):
        def find_users(self, address: str):
            calls.append(address)
            return super().find_users(address)

    monkeypatch.setattr(_shared, "directory_for", lambda request, *a, **k: _Counting())
    session = _session(client, db, "same-once")
    base = f"/operator/sessions/{session.public_id}/reviewers"
    assert _add(client, base, "email", "name", "jane.tan@example.edu", "Jane").status_code == 303
    assert len(calls) == 1
    jane = db.execute(select(Reviewer).where(Reviewer.session_id == session.id)).scalar_one()
    calls.clear()
    assert (
        client.post(
            f"{base}/{jane.id}/update",
            data={**FORM, "email": "e0123456@example.edu", "name": "Jane"},
            follow_redirects=False,
        ).status_code
        == 303
    )
    assert len(calls) == 1
