"""The Upload card's recheck (segment 20I Item 1): the button left of
Upload, named with the count of active rows that have an address and no
directory account, absent when there are none (rung 1); the POST that
looks those rows up again and binds the ones found (rung 2).

The directory is `cordware.graph.FakeDirectory`: `e0123456@` is Jane
Tan's sign-in name, `office@` is ambiguous, `nobody@` is not found.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from cordware.graph import FakeDirectory, GraphError
from app.db.models import AuditEvent, Observer, Reviewee, Reviewer, ReviewSession
from app.web.routes_operator import _directory, _setup_observers, _shared

from ._invitation_states import _create_session


class _Switch:
    """The directory every route asks, swappable mid-test: an import while
    the directory is down, then a recheck once it is back."""

    def __init__(self) -> None:
        self.current: FakeDirectory | None = FakeDirectory()


class _Failing(FakeDirectory):
    def __init__(self, kind: str) -> None:
        super().__init__()
        self._kind = kind

    def find_users(self, address: str):
        raise GraphError(self._kind, {"server": 503, "unauthorized": 401}[self._kind])


@pytest.fixture
def switch(monkeypatch: pytest.MonkeyPatch) -> _Switch:
    state = _Switch()
    for module in (_shared, _setup_observers, _directory):
        monkeypatch.setattr(module, "directory_or_none", lambda request: state.current)
    return state


@pytest.fixture
def directory(switch: _Switch) -> FakeDirectory:
    assert switch.current is not None
    return switch.current


def _recheck(client: TestClient, public_id: str, roster: str, status: int = 303):
    response = client.post(
        f"/operator/sessions/{public_id}/directory-recheck",
        data={"roster": roster},
        follow_redirects=False,
    )
    assert response.status_code == status, response.text
    return response


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
    assert 'form="directory-recheck-form"' in card  # its own form: ignores the file
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


# --- rung 2: the recheck binds what the directory now finds ---


def _rows(db: Session, model, session_id: int) -> dict[str, object]:
    db.expire_all()
    address = "email_or_identifier" if model is Reviewee else "email"
    rows = db.execute(select(model).where(model.session_id == session_id)).scalars()
    return {getattr(row, address): row for row in rows}


def _event(db: Session, session_id: int, event_type: str) -> AuditEvent:
    return db.execute(
        select(AuditEvent)
        .where(AuditEvent.session_id == session_id, AuditEvent.event_type == event_type)
        .order_by(AuditEvent.id.desc())
    ).scalars().first()


def test_a_recheck_binds_the_rows_the_directory_now_finds(
    client: TestClient, db: Session, switch: _Switch
) -> None:
    session = _create_session(client, db, "recheck-binds")
    switch.current = _Failing("server")
    _upload(
        client,
        session.public_id,
        "reviewers",
        "ReviewerName,ReviewerEmail,Status\n"
        "Jane,e0123456@example.edu,active\n"
        "Arun,arun.kumar@example.edu,active\n"
        "Nobody,nobody@example.edu,active\n"
        "Gone,lab01@example.edu,inactive\n",
    )
    assert "Recheck 3 unmatched</button>" in _card(client, session.public_id, "reviewers")

    switch.current = FakeDirectory()
    response = _recheck(client, session.public_id, "reviewers")
    assert response.headers["location"].endswith("/reviewers?unlocked=1#upload-csv")

    rows = _rows(db, Reviewer, session.id)
    assert rows["e0123456@example.edu"].directory_upn == "e0123456@example.edu"
    assert rows["arun.kumar@example.edu"].directory_object_id
    assert rows["nobody@example.edu"].directory_object_id is None
    assert rows["lab01@example.edu"].directory_object_id is None  # inactive: not rechecked

    counts = _event(db, session.id, "reviewers.directory_rechecked").detail["counts"]
    assert counts == {
        "directory_by_mail": 1,
        "directory_by_upn": 1,
        "directory_not_found": 1,
        "directory_ambiguous": 0,
        "directory_not_checked": 0,
        "directory_held": 0,
    }
    card = _card(client, session.public_id, "reviewers")
    assert "Recheck 1 unmatched</button>" in card
    line = " ".join(card[card.index("data-directory-check") :].split("</p>")[0].split())
    assert "Recheck of the unmatched addresses" in line
    assert "1 matched by mail, 1 by sign-in name, 1 not found, 0 ambiguous." in line


def test_a_row_on_an_account_another_row_holds_stays_unbound(
    client: TestClient, db: Session, switch: _Switch
) -> None:
    """20H Item 1's rule, applied to a recheck: Jane's mail and her
    sign-in name, both saved unbound while the directory was down, are
    one account, so only the first binds."""
    session = _create_session(client, db, "recheck-held")
    switch.current = _Failing("server")
    _upload(
        client,
        session.public_id,
        "reviewers",
        "ReviewerName,ReviewerEmail\nJane,jane.tan@example.edu\nJane UPN,e0123456@example.edu\n",
    )
    switch.current = FakeDirectory()
    _recheck(client, session.public_id, "reviewers")
    rows = _rows(db, Reviewer, session.id)
    assert rows["jane.tan@example.edu"].directory_object_id
    assert rows["e0123456@example.edu"].directory_object_id is None
    counts = _event(db, session.id, "reviewers.directory_rechecked").detail["counts"]
    assert counts["directory_held"] == 1 and counts["directory_by_mail"] == 1
    card = _card(client, session.public_id, "reviewers")
    assert "1 on an account another row already holds" in card


def test_a_directory_still_down_binds_nothing_and_says_why(
    client: TestClient, db: Session, switch: _Switch
) -> None:
    session = _create_session(client, db, "recheck-down")
    switch.current = _Failing("server")
    _upload(client, session.public_id, "reviewers", "ReviewerName,ReviewerEmail\nArun,arun.kumar@example.edu\n")
    _recheck(client, session.public_id, "reviewers")
    assert _rows(db, Reviewer, session.id)["arun.kumar@example.edu"].directory_object_id is None
    event = _event(db, session.id, "reviewers.directory_rechecked")
    assert event.detail["counts"]["directory_not_checked"] == 1
    assert event.detail["context"]["directory_unchecked"] == "server"
    card = _card(client, session.public_id, "reviewers")
    assert "couldn&#39;t check the" in card or "couldn't check the" in card
    assert "Recheck 1 unmatched</button>" in card


def test_an_expired_sign_in_saves_nothing_and_asks_to_renew(
    client: TestClient, db: Session, switch: _Switch
) -> None:
    session = _create_session(client, db, "recheck-expired")
    switch.current = _Failing("server")
    _upload(client, session.public_id, "reviewers", "ReviewerName,ReviewerEmail\nArun,arun.kumar@example.edu\n")
    switch.current = _Failing("unauthorized")
    response = _recheck(client, session.public_id, "reviewers")
    assert "recheck_renew=1" in response.headers["location"]
    assert _event(db, session.id, "reviewers.directory_rechecked") is None
    page = client.get(response.headers["location"].split("#")[0]).text
    banner = page[page.index("data-directory-renew") :]
    assert "Renew sign-in and recheck" in banner
    assert 'form="directory-recheck-form"' in banner


def test_reviewees_and_observers_recheck_too(
    client: TestClient, db: Session, switch: _Switch
) -> None:
    session = _create_session(client, db, "recheck-others")
    session.observers_enabled = True
    db.commit()
    switch.current = _Failing("server")
    _upload(client, session.public_id, "reviewees", "RevieweeName,RevieweeEmail\nArun,arun.kumar@example.edu\nAnon,STU-1\n")
    _upload(client, session.public_id, "observers", "ObserverName,ObserverEmail\nJane,jane.tan@example.edu\n")
    switch.current = FakeDirectory()
    _recheck(client, session.public_id, "reviewees")
    _recheck(client, session.public_id, "observers")
    assert _rows(db, Reviewee, session.id)["arun.kumar@example.edu"].directory_object_id
    assert _rows(db, Observer, session.id)["jane.tan@example.edu"].directory_object_id
    assert _event(db, session.id, "reviewees.directory_rechecked").detail["counts"]["directory_by_mail"] == 1
    assert _event(db, session.id, "observers.directory_rechecked").detail["counts"]["directory_by_mail"] == 1


def test_an_activated_session_may_recheck_and_an_archived_one_may_not(
    client: TestClient, db: Session, switch: _Switch
) -> None:
    """Any state but archived (author, 2026-11-03: binding admits by
    account what the address already admits)."""
    session = _create_session(client, db, "recheck-states")
    switch.current = _Failing("server")
    _upload(client, session.public_id, "reviewers", "ReviewerName,ReviewerEmail\nArun,arun.kumar@example.edu\n")
    switch.current = FakeDirectory()
    row = db.get(ReviewSession, session.id)
    row.status = "ready"
    db.commit()
    _recheck(client, session.public_id, "reviewers")
    assert _rows(db, Reviewer, session.id)["arun.kumar@example.edu"].directory_object_id
    row = db.get(ReviewSession, session.id)
    row.status = "archived"
    db.commit()
    _recheck(client, session.public_id, "reviewers", status=409)


def test_an_unknown_roster_or_disabled_observers_is_not_found(
    client: TestClient, db: Session, directory: FakeDirectory
) -> None:
    session = _create_session(client, db, "recheck-404")
    _recheck(client, session.public_id, "relationships", status=404)
    _recheck(client, session.public_id, "observers", status=404)


def test_under_symmetric_review_the_reviewers_recheck_reaches_the_mirror(
    client: TestClient, db: Session, switch: _Switch
) -> None:
    response = client.post(
        "/operator/sessions",
        data={"name": "Sym", "code": "recheck-sym", "description": "", "symmetric_review": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    session = db.execute(select(ReviewSession).where(ReviewSession.code == "recheck-sym")).scalar_one()
    switch.current = _Failing("server")
    _upload(
        client, session.public_id, "reviewers",
        "ReviewerName,ReviewerEmail\nArun,arun.kumar@example.edu\nNobody,nobody@example.edu\n",
    )
    switch.current = FakeDirectory()
    _recheck(client, session.public_id, "reviewers")
    mirror = _rows(db, Reviewee, session.id)["arun.kumar@example.edu"]
    assert mirror.directory_object_id == _rows(db, Reviewer, session.id)["arun.kumar@example.edu"].directory_object_id
    _recheck(client, session.public_id, "reviewees", status=409)
    # Nobody stays unmatched: the Reviewers card offers the recheck, the
    # mirrored Reviewees card does not.
    assert "Recheck 1 unmatched</button>" in _card(client, session.public_id, "reviewers")
    assert "data-directory-recheck" not in client.get(
        f"/operator/sessions/{session.public_id}/reviewees?unlocked=1"
    ).text


# --- rung 3: the countdown's keys for a recheck ---


def test_the_recheck_keys_are_every_unmatched_address_kept_or_not(
    client: TestClient, db: Session, directory: FakeDirectory
) -> None:
    """A recheck asks afresh: `directory-keys` names every unmatched
    row's key, even one whose answer the upload's countdown kept."""
    session = _create_session(client, db, "recheck-keys")
    _upload(
        client,
        session.public_id,
        "reviewers",
        "ReviewerName,ReviewerEmail\nJane,e0123456@example.edu\nNobody,Nobody@Example.edu\n"
        "Gone,gone@example.edu\n",
    )
    lookup = client.post(
        f"/operator/sessions/{session.public_id}/directory-lookup",
        json={"keys": ["nobody@example.edu"]},
    )
    assert lookup.status_code == 200  # now kept
    response = client.post(
        f"/operator/sessions/{session.public_id}/directory-keys",
        data={"roster": "reviewers", "recheck": "true"},
    )
    assert response.status_code == 200
    assert response.json() == {"keys": ["nobody@example.edu", "gone@example.edu"]}
