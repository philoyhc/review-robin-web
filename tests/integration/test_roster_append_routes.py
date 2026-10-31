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
    assert "Tick only one of replace, append or merge, then upload again." in asked.text
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
    assert asked.status_code == 400 and "only one of replace, append or merge" in asked.text

    assert _upload(client, url, new, append="true").status_code == 303
    assert _pairs(db, s.id) == 2


def test_a_relationships_append_that_redraws_an_answered_group_asks_first(
    client: TestClient, db: Session
) -> None:
    """Appending Ed into group y (Cy and Di answered) redraws y: the
    group-clear ask comes back with the append tick still ticked and the
    file held, and the count answers it."""
    import re

    from .test_relationship_group_clear_asks_first import _base, _seed

    session = _seed(db, client, "apr-rel-clear")
    url = f"{_base(session)}/import"
    csv = b"ReviewerEmail,RevieweeEmail,PairContextTag1\nrae@example.edu,ed@example.edu,y\n"

    asked = _upload(client, url, csv, append="true")
    assert asked.status_code == 400
    assert "data-group-clear-banner" in asked.text
    assert re.search(r'name="append" value="true"\s+checked', asked.text)
    assert 'name="confirm_replace" value="true" checked' not in asked.text
    assert _held(db) == 1
    count = re.search(r'name="acknowledge_response_loss"\s+value="(\d+)"', asked.text).group(1)
    assert _pairs(db, session.id) == 4

    answered = _upload(
        client, url, None, append="true", acknowledge_response_loss=count, held_token=_token(asked.text)
    )
    assert answered.status_code == 303, answered.text[:400]
    assert _pairs(db, session.id) == 5
    assert _held(db) == 0


def test_an_append_looks_up_only_the_files_addresses(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cordware.graph import FakeDirectory
    from app.web.routes_operator import _shared

    asked: list[str] = []

    class Recording(FakeDirectory):
        def find_users(self, address: str):
            asked.append(address)
            return super().find_users(address)

    s = _session(client, db, code="apr-lookup")
    url = f"/operator/sessions/{s.public_id}/reviewers/import"
    _upload(client, url, FILES["reviewers"][0])
    monkeypatch.setattr(_shared, "directory_or_none", lambda request: Recording())
    assert _upload(client, url, FILES["reviewers"][1], append="true").status_code == 303
    assert asked == ["bea@example.edu"]


def test_an_append_onto_an_empty_roster_is_just_the_roster(client: TestClient, db: Session) -> None:
    from app.db.models import AuditEvent

    s = _session(client, db, code="apr-empty")
    url = f"/operator/sessions/{s.public_id}/reviewers/import"
    assert _upload(client, url, FILES["reviewers"][0], append="true", confirm_replace="true").status_code == 303
    event = db.execute(select(AuditEvent).where(AuditEvent.event_type == "reviewers.imported")).scalar_one()
    assert "mode" not in (event.detail.get("context") or {})
    assert _addresses(db, "reviewers", s.id) == ["ann@example.edu"]


@pytest.mark.parametrize("kind", ["reviewers", "reviewees", "relationships", "observers"])
def test_the_merge_tick_shares_appends_line(client: TestClient, db: Session, kind: str) -> None:
    """The author's layout (2026-10-31): "Yes, append to, [ ] merge with
    the existing roster." Merge is live since rung 10, in the exclusive
    group and on the Upload key, and nothing is shown on an empty roster."""
    import re

    if kind == "relationships":
        s, _ = _relationships_session(client, db, f"apr-merge-{kind}")
    else:
        s = _session(client, db, code=f"apr-merge-{kind}")
    page_url = f"/operator/sessions/{s.public_id}/{kind}?unlocked=1"
    if kind != "relationships":
        assert 'name="merge"' not in client.get(page_url).text
        _upload(client, f"/operator/sessions/{s.public_id}/{kind}/import", FILES[kind][0])
    page = client.get(page_url).text
    line = re.search(r'<div class="confirm-label upload-mode-line">(.*?)</div>', page, re.S)
    assert line, "no append / merge line"
    body = line.group(1)
    assert 'name="append"' in body and "Yes, append to," in body
    merge = re.search(r'<input[^>]*name="merge"[^>]*>', body).group(0)
    assert "disabled" not in merge and 'data-exclusive-tick="upload-mode"' in merge
    assert "data-delete-confirm=" in merge
    assert "merge with the existing roster." in body
