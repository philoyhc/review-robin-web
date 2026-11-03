"""The Upload card's recheck button (segment 20I Item 1, rung 1, the
scaffold): left of Upload, named with the count of active rows that have
an address and no directory account, absent when there are none. Inert
until rung 2 wires it.

The directory is `cordware.graph.FakeDirectory`: `e0123456@` is Jane
Tan's sign-in name, `office@` is ambiguous, `nobody@` is not found.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from cordware.graph import FakeDirectory
from app.web.routes_operator import _setup_observers, _shared

from ._invitation_states import _create_session


@pytest.fixture
def directory(monkeypatch: pytest.MonkeyPatch) -> FakeDirectory:
    fake = FakeDirectory()
    monkeypatch.setattr(_shared, "directory_or_none", lambda request: fake)
    monkeypatch.setattr(_setup_observers, "directory_or_none", lambda request: fake)
    return fake


def _upload(client: TestClient, public_id: str, kind: str, csv: str) -> None:
    response = client.post(
        f"/operator/sessions/{public_id}/{kind}/import",
        files={"file": ("f.csv", csv.encode(), "text/csv")},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text


def _card(client: TestClient, public_id: str, kind: str) -> str:
    text = client.get(f"/operator/sessions/{public_id}/{kind}?unlocked=1").text
    start = text.index('id="upload-csv"')
    return text[start : text.index("</section>", start)]


def test_the_button_names_the_active_unmatched_rows_left_of_upload(
    client: TestClient, db: Session, directory: FakeDirectory
) -> None:
    session = _create_session(client, db, "recheck-reviewers")
    _upload(
        client,
        session.public_id,
        "reviewers",
        "ReviewerName,ReviewerEmail,Status\n"
        "Jane,e0123456@example.edu,active\n"
        "Office,office@example.edu,active\n"
        "Nobody,nobody@example.edu,active\n"
        "Gone,gone@example.edu,inactive\n",
    )
    card = _card(client, session.public_id, "reviewers")
    button = card.index("data-directory-recheck")
    assert "Recheck 2 unmatched</button>" in card  # bound and inactive rows left out
    assert 'type="button" data-directory-recheck' in card  # not a submit: ignores the file
    actions = card.index('class="unlock-col-actions"')
    assert actions < button < card.index(">Upload</button>")
    # The directory line sits below the actions, the countdown under it.
    line = card.index("data-directory-check")
    assert card.index("</form>") < line < card.index("data-directory-countdown")


def test_anonymous_reviewee_identifiers_are_not_counted(
    client: TestClient, db: Session, directory: FakeDirectory
) -> None:
    session = _create_session(client, db, "recheck-reviewees")
    _upload(
        client,
        session.public_id,
        "reviewees",
        "RevieweeName,RevieweeEmail\nAnon,STU-0001\nNobody,nobody@example.edu\n",
    )
    assert "Recheck 1 unmatched</button>" in _card(client, session.public_id, "reviewees")


def test_no_button_when_every_row_is_matched(
    client: TestClient, db: Session, directory: FakeDirectory
) -> None:
    session = _create_session(client, db, "recheck-observers")
    session.observers_enabled = True
    db.flush()
    _upload(
        client, session.public_id, "observers", "ObserverName,ObserverEmail\nJane,e0123456@example.edu\n"
    )
    card = _card(client, session.public_id, "observers")
    assert "data-directory-recheck" not in card
    assert "data-directory-check" in card
