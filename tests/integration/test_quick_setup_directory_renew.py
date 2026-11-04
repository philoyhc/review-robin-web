"""Quick Setup when Graph refuses an expired token (segment 20G): the
submit-all saves nothing, holds every file of the submit and
re-renders the card with the renew banner above the slots, naming no
slot's fault; the renew button's resubmit then saves them."""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Observer, Reviewer
from app.web.routes_operator import _quick_setup
from cordware.graph import FakeDirectory, GraphError

from ._invitation_states import _create_session


class _Expired(FakeDirectory):
    def find_users(self, address: str):
        raise GraphError("unauthorized", 401)


def test_a_sign_in_stop_holds_the_submit_and_asks_to_renew(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = _create_session(client, db, code="qs-renew")
    url = f"/operator/sessions/{session.public_id}/quick-setup/submit-all"
    monkeypatch.setattr(_quick_setup, "directory_or_none", lambda request: _Expired())
    response = client.post(
        url,
        files={
            "reviewers_file": ("r.csv", b"ReviewerName,ReviewerEmail\nJane,e0123456@example.edu\n", "text/csv"),
            "observers_file": ("o.csv", b"ObserverName,ObserverEmail\nOli,oli@example.edu\n", "text/csv"),
        },
        follow_redirects=False,
    )
    assert response.status_code == 422
    page = response.text
    assert "data-directory-renew" in page and "Renew sign-in and submit" in page
    assert 'form="quick-setup-submit-all-form"' in page[page.index("data-directory-renew") :]
    assert "data-quick-setup-reason=\"" not in page  # no slot is at fault
    token = re.search(r'name="held_token" value="([^"]+)"', page).group(1)
    db.expire_all()
    assert db.execute(select(Reviewer).where(Reviewer.session_id == session.id)).first() is None

    monkeypatch.setattr(_quick_setup, "directory_or_none", lambda request: FakeDirectory())
    response = client.post(url, data={"held_token": token}, follow_redirects=False)
    assert response.status_code == 303
    db.expire_all()
    jane = db.execute(select(Reviewer).where(Reviewer.session_id == session.id)).scalar_one()
    assert jane.directory_object_id is not None
    assert db.execute(select(Observer).where(Observer.session_id == session.id)).scalar_one()


def test_a_per_slot_route_holds_nothing_so_its_banner_says_reload(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The per-slot routes hold no files, so a renew button would have
    nothing to send: the slot's own banner says to reload and submit."""
    session = _create_session(client, db, code="qs-renew-slot")
    monkeypatch.setattr(_quick_setup, "directory_or_none", lambda request: _Expired())
    response = client.post(
        f"/operator/sessions/{session.public_id}/quick-setup/reviewers",
        files={"file": ("r.csv", b"ReviewerName,ReviewerEmail\nJane,e0123456@example.edu\n", "text/csv")},
        follow_redirects=False,
    )
    assert response.status_code == 422
    assert "data-directory-renew" not in response.text
    assert "Reload the page, then submit again." in response.text
    db.expire_all()
    assert db.execute(select(Reviewer).where(Reviewer.session_id == session.id)).first() is None
