"""Appending through the Reviewers, Reviewees and Observers Upload cards
(segment 19Z, rung 4): the card's append tick reaches the service; both
ticks, or neither, ask and hold the file; a row already on the roster
refuses the file as its problems; an append asks for no response-loss
acknowledgment, since it discards nothing.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Assignment, Observer, Reviewee, Reviewer
from app.services import csv_imports
from app.services import session_lifecycle as lifecycle
from app.services.instruments import ensure_default_instrument

from .test_held_upload_setup_cards import _held, _session, _token, _upload

FILES = {
    "reviewers": (b"ReviewerName,ReviewerEmail\nAnn,ann@example.edu\n", b"ReviewerName,ReviewerEmail\nBea,bea@example.edu\n"),
    "reviewees": (b"RevieweeName,RevieweeEmail\nAnn,ann@example.edu\n", b"RevieweeName,RevieweeEmail\nBea,bea@example.edu\n"),
    "observers": (b"ObserverName,ObserverEmail\nAnn,ann@example.edu\n", b"ObserverName,ObserverEmail\nBea,bea@example.edu\n"),
}
MODELS = {"reviewers": (Reviewer, Reviewer.email), "reviewees": (Reviewee, Reviewee.email_or_identifier), "observers": (Observer, Observer.email)}


def _addresses(db: Session, kind: str, session_id: int) -> list[str]:
    db.expire_all()
    model, column = MODELS[kind]
    return sorted(db.execute(select(column).where(model.session_id == session_id)).scalars())


@pytest.mark.parametrize("kind", sorted(FILES))
def test_the_append_tick_adds_the_file_and_keeps_the_roster(client: TestClient, db: Session, kind: str) -> None:
    s = _session(client, db, code=f"apr-{kind}")
    url = f"/operator/sessions/{s.public_id}/{kind}/import"
    first, second = FILES[kind]
    assert _upload(client, url, first).status_code == 303
    page = client.get(f"/operator/sessions/{s.public_id}/{kind}?unlocked=1").text
    assert 'name="append" value="true"' in page and 'name="append" value="true" disabled' not in page

    response = _upload(client, url, second, append="true")
    assert response.status_code == 303, response.text[:400]
    assert _addresses(db, kind, s.id) == ["ann@example.edu", "bea@example.edu"]


def test_an_append_keeps_the_assignments_a_replace_would_delete(client: TestClient, db: Session) -> None:
    s = _session(client, db, code="apr-keep")
    base = f"/operator/sessions/{s.public_id}"
    _upload(client, f"{base}/reviewers/import", FILES["reviewers"][0])
    _upload(client, f"{base}/reviewees/import", FILES["reviewees"][0])
    ann_r = db.execute(select(Reviewer).where(Reviewer.session_id == s.id)).scalar_one()
    ann_e = db.execute(select(Reviewee).where(Reviewee.session_id == s.id)).scalar_one()
    instrument = ensure_default_instrument(db, s)
    db.add(Assignment(session_id=s.id, reviewer_id=ann_r.id, reviewee_id=ann_e.id, instrument_id=instrument.id))
    db.commit()

    assert _upload(client, f"{base}/reviewers/import", FILES["reviewers"][1], append="true").status_code == 303
    db.expire_all()
    assert db.execute(select(Assignment).where(Assignment.session_id == s.id)).scalar_one()


@pytest.mark.parametrize("kind", ["reviewers", "observers"])
def test_both_ticks_ask_and_hold_the_file(client: TestClient, db: Session, kind: str) -> None:
    s = _session(client, db, code=f"apr-both-{kind}")
    url = f"/operator/sessions/{s.public_id}/{kind}/import"
    first, second = FILES[kind]
    _upload(client, url, first)

    asked = _upload(client, url, second, confirm_replace="true", append="true")
    assert asked.status_code == 400
    assert "Tick replace or append, not both, then upload again." in asked.text
    assert _held(db) == 1
    # Neither tick comes back checked: the ask is to choose.
    assert 'name="append" value="true" checked' not in asked.text
    assert 'name="confirm_replace" value="true" checked' not in asked.text
    assert _addresses(db, kind, s.id) == ["ann@example.edu"]

    answered = _upload(client, url, None, append="true", held_token=_token(asked.text))
    assert answered.status_code == 303
    assert _addresses(db, kind, s.id) == ["ann@example.edu", "bea@example.edu"]
    assert _held(db) == 0


@pytest.mark.parametrize("kind", ["reviewees", "observers"])
def test_a_row_already_on_the_roster_refuses_the_append(client: TestClient, db: Session, kind: str) -> None:
    s = _session(client, db, code=f"apr-dup-{kind}")
    url = f"/operator/sessions/{s.public_id}/{kind}/import"
    first, second = FILES[kind]
    _upload(client, url, first)
    both = second + first.split(b"\n", 1)[1].replace(b"ann@", b"ANN@")

    refused = _upload(client, url, both, append="true")
    assert refused.status_code == 400
    assert "is already on the roster" in refused.text
    assert _addresses(db, kind, s.id) == ["ann@example.edu"]
    assert _held(db) == 0


def test_a_conflict_arriving_after_the_routes_check_is_refused_by_the_save(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The route's check sees no conflict; the save, under the session
    lock, does (a row added between them), and the route renders it."""
    s = _session(client, db, code="apr-race")
    url = f"/operator/sessions/{s.public_id}/reviewers/import"
    _upload(client, url, FILES["reviewers"][0])
    real = csv_imports.append_conflicts
    calls: list[int] = []

    def first_sees_nothing(*args, **kwargs):
        calls.append(1)
        return [] if len(calls) == 1 else real(*args, **kwargs)

    monkeypatch.setattr(csv_imports, "append_conflicts", first_sees_nothing)
    refused = _upload(client, url, FILES["reviewers"][0], append="true")
    assert len(calls) == 2
    assert refused.status_code == 400
    assert "is already on the roster" in refused.text
    assert _addresses(db, "reviewers", s.id) == ["ann@example.edu"]


def test_an_append_needs_no_response_loss_acknowledgment(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    s = _session(client, db, code="apr-ack")
    url = f"/operator/sessions/{s.public_id}/reviewers/import"
    _upload(client, url, FILES["reviewers"][0])
    monkeypatch.setattr(lifecycle, "session_has_responses", lambda db, rs: True)

    replace = _upload(client, url, FILES["reviewers"][1], confirm_replace="true")
    assert replace.status_code == 400 and "would discard" in replace.text
    held = _token(replace.text)
    appended = _upload(client, url, None, append="true", held_token=held)
    assert appended.status_code == 303, appended.text[:400]
    assert _addresses(db, "reviewers", s.id) == ["ann@example.edu", "bea@example.edu"]


def _relationships_session(client: TestClient, db: Session, code: str):
    s = _session(client, db, code=code)
    s.relationships_enabled = True
    db.commit()
    base = f"/operator/sessions/{s.public_id}"
    _upload(client, f"{base}/reviewers/import", b"ReviewerName,ReviewerEmail\nAl,al@example.edu\nBo,bo@example.edu\n")
    _upload(client, f"{base}/reviewees/import", b"RevieweeName,RevieweeEmail\nCy,cy@example.edu\n")
    assert _upload(client, f"{base}/relationships/import", b"ReviewerEmail,RevieweeEmail\nal@example.edu,cy@example.edu\n").status_code == 303
    return s, f"{base}/relationships/import"


def _pairs(db: Session, session_id: int) -> int:
    from app.db.models import Relationship

    db.expire_all()
    return len(db.execute(select(Relationship).where(Relationship.session_id == session_id)).scalars().all())


def test_relationships_append_adds_a_pair_and_refuses_a_held_one(client: TestClient, db: Session) -> None:
    s, url = _relationships_session(client, db, "apr-rel")
    new = b"ReviewerEmail,RevieweeEmail\nbo@example.edu,cy@example.edu\n"
    held = b"ReviewerEmail,RevieweeEmail\nAL@example.edu,cy@example.edu\n"

    refused = _upload(client, url, held, append="true")
    assert refused.status_code == 400
    assert "already a relationship" in refused.text
    assert _pairs(db, s.id) == 1

    asked = _upload(client, url, new, append="true", confirm_replace="true")
    assert asked.status_code == 400 and "not both" in asked.text

    assert _upload(client, url, new, append="true").status_code == 303
    assert _pairs(db, s.id) == 2
