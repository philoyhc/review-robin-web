"""Segment 19W rung 3 — a Setup upload card's ask holds its file.

An upload refused with a question (the replace tick missing, a
relationships replace that would clear group answers) holds the file, so
the operator answers with a tick and Upload, no file chosen; a save, a
plain refusal or Dismiss ends the hold.
"""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    HeldUpload,
    Observer,
    Relationship,
    Reviewee,
    Reviewer,
    ReviewSession,
)

from .test_relationship_group_clear_asks_first import _base, _relationship, _seed

REVIEWERS_1 = b"ReviewerName,ReviewerEmail\nAnn,ann@example.edu\n"
REVIEWERS_2 = b"ReviewerName,ReviewerEmail\nBea,bea@example.edu\n"
REVIEWERS_3 = b"ReviewerName,ReviewerEmail\nCal,cal@example.edu\n"


def _session(client: TestClient, db: Session, *, code: str) -> ReviewSession:
    r = client.post(
        "/operator/sessions", data={"name": "S", "code": code},
        follow_redirects=False,
    )
    assert r.status_code == 303, r.text
    s = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    s.observers_enabled = True
    db.commit()
    return s


def _held(db: Session) -> int:
    db.expire_all()
    return db.execute(select(func.count()).select_from(HeldUpload)).scalar_one()


def _token(body: str) -> str:
    match = re.search(r'name="held_token" value="([^"]+)"', body)
    assert match is not None, "no held token on the card"
    return match.group(1)


def _upload(client: TestClient, url: str, content: bytes | None, **data: str):
    files = {"file": ("roster.csv", content, "text/csv")} if content else None
    return client.post(url, files=files, data=data, follow_redirects=False)


def _reviewers(db: Session, s: ReviewSession) -> list[str]:
    db.expire_all()
    return [
        r.name
        for r in db.execute(
            select(Reviewer).where(Reviewer.session_id == s.id)
        ).scalars()
    ]


def test_a_missing_replace_tick_holds_the_file_for_the_next_submit(
    db: Session, client: TestClient
) -> None:
    s = _session(client, db, code="held-rev")
    url = f"/operator/sessions/{s.public_id}/reviewers/import"
    assert _upload(client, url, REVIEWERS_1).status_code == 303

    asked = _upload(client, url, REVIEWERS_2)
    assert asked.status_code == 400
    assert "Tick the replacement-confirmation box" in asked.text
    assert "Holding <strong>roster.csv</strong>" in asked.text
    # A missing-replace ask leaves the replace tick for the operator.
    assert re.search(r'name="confirm_replace"[^>]*\bchecked\b', asked.text) is None
    # The file input is no longer required: the hold stands in for it.
    assert re.search(r'name="file"[^>]*\brequired\b', asked.text) is None
    assert _held(db) == 1

    answered = _upload(
        client, url, None, confirm_replace="true", held_token=_token(asked.text)
    )
    assert answered.status_code == 303, answered.text[:300]
    assert _reviewers(db, s) == ["Bea"]
    assert _held(db) == 0


def test_a_newly_chosen_file_wins_over_the_held_one(
    db: Session, client: TestClient
) -> None:
    s = _session(client, db, code="held-new")
    url = f"/operator/sessions/{s.public_id}/reviewers/import"
    _upload(client, url, REVIEWERS_1)
    asked = _upload(client, url, REVIEWERS_2)

    answered = _upload(
        client, url, REVIEWERS_3,
        confirm_replace="true", held_token=_token(asked.text),
    )
    assert answered.status_code == 303
    assert _reviewers(db, s) == ["Cal"]
    assert _held(db) == 0


def test_a_plain_refusal_ends_the_hold(db: Session, client: TestClient) -> None:
    s = _session(client, db, code="held-bad")
    url = f"/operator/sessions/{s.public_id}/reviewers/import"
    _upload(client, url, REVIEWERS_1)
    asked = _upload(client, url, REVIEWERS_2)

    refused = _upload(
        client, url, b"Nothing,Useful\n1,2\n",
        confirm_replace="true", held_token=_token(asked.text),
    )
    assert refused.status_code == 400
    assert 'name="held_token"' not in refused.text
    assert _held(db) == 0


def test_dismiss_ends_the_hold_and_reopens_the_card(
    db: Session, client: TestClient
) -> None:
    s = _session(client, db, code="held-obs")
    url = f"/operator/sessions/{s.public_id}/observers/import"
    first = b"ObserverEmail,ObserverName\no1@example.edu,O1\n"
    assert _upload(client, url, first).status_code == 303
    asked = _upload(client, url, b"ObserverEmail,ObserverName\no2@example.edu,O2\n")
    assert asked.status_code == 400
    assert f'formaction="{url}/dismiss"' in asked.text

    dismissed = client.post(
        f"{url}/dismiss", data={"held_token": _token(asked.text)},
        follow_redirects=False,
    )
    assert dismissed.status_code == 303
    assert dismissed.headers["location"] == (
        f"/operator/sessions/{s.public_id}/observers?unlocked=1#upload-csv"
    )
    assert _held(db) == 0
    db.expire_all()
    assert [o.email for o in db.execute(select(Observer)).scalars()] == [
        "o1@example.edu"
    ]


def test_another_sessions_token_holds_nothing_here(
    db: Session, client: TestClient
) -> None:
    """A hold belongs to one session: presented on another, it reads as
    lapsed, and the hold itself is left alone. (Another operator's
    token is the service's test, ``test_held_uploads``.)"""
    first = _session(client, db, code="held-one")
    second = _session(client, db, code="held-two")
    url_one = f"/operator/sessions/{first.public_id}/reviewers/import"
    url_two = f"/operator/sessions/{second.public_id}/reviewers/import"
    _upload(client, url_one, REVIEWERS_1)
    _upload(client, url_two, REVIEWERS_1)
    asked = _upload(client, url_one, REVIEWERS_2)

    tried = _upload(
        client, url_two, None, confirm_replace="true",
        held_token=_token(asked.text),
    )
    assert tried.status_code == 400
    assert "The file held from your last upload has expired" in tried.text
    assert _reviewers(db, second) == ["Ann"]
    assert _held(db) == 1


def test_a_group_clear_ask_holds_the_file_and_keeps_the_replace_tick(
    db: Session, client: TestClient
) -> None:
    session = _seed(db, client, "held-rgc")
    csv = (
        b"ReviewerEmail,RevieweeEmail,PairContextTag1\n"
        b"rae@example.edu,ann@example.edu,y\n"
        b"rae@example.edu,bo@example.edu,x\n"
        b"rae@example.edu,cy@example.edu,y\n"
        b"rae@example.edu,di@example.edu,y\n"
    )
    url = f"{_base(session)}/import"
    asked = _upload(client, url, csv, confirm_replace="true")
    assert asked.status_code == 400
    assert re.search(r'name="confirm_replace"[^>]*\bchecked\b', asked.text)
    assert f'formaction="{url}/dismiss"' in asked.text
    assert _relationship(db, session.id, "Ann").tag_1 == "x"

    answered = _upload(
        client, url, None,
        confirm_replace="true", acknowledge_response_loss="3",
        held_token=_token(asked.text),
    )
    assert answered.status_code == 303, answered.text[:300]
    assert _relationship(db, session.id, "Ann").tag_1 == "y"
    assert _held(db) == 0


def test_each_setup_cards_dismiss_route_ends_the_hold(
    db: Session, client: TestClient
) -> None:
    s = _session(client, db, code="held-dismiss-all")
    url = f"/operator/sessions/{s.public_id}/reviewers/import"
    _upload(client, url, REVIEWERS_1)
    asked = _upload(client, url, REVIEWERS_2)
    dismissed = client.post(
        f"{url}/dismiss", data={"held_token": _token(asked.text)},
        follow_redirects=False,
    )
    assert dismissed.status_code == 303
    assert dismissed.headers["location"].endswith("/reviewers?unlocked=1#upload-csv")
    assert _held(db) == 0
    for page in ("reviewees", "relationships"):
        response = client.post(
            f"/operator/sessions/{s.public_id}/{page}/import/dismiss",
            data={"held_token": "not-a-token"},
            follow_redirects=False,
        )
        # An unknown token deletes nothing and lands on the card.
        assert response.status_code in (303, 404), (page, response.status_code)


_EMPTY_FILE_CARDS = {
    "reviewers": (Reviewer, REVIEWERS_1, REVIEWERS_2),
    "reviewees": (
        Reviewee,
        b"RevieweeName,RevieweeEmail\nAnn,ann@example.edu\n",
        b"RevieweeName,RevieweeEmail\nBea,bea@example.edu\n",
    ),
    "observers": (
        Observer,
        b"ObserverEmail,ObserverName\no1@example.edu,O1\n",
        b"ObserverEmail,ObserverName\no2@example.edu,O2\n",
    ),
    "relationships": (
        Relationship,
        None,
        b"ReviewerEmail,RevieweeEmail\nrae@example.edu,ed@example.edu\n",
    ),
}


def _row_ids(db: Session, model, s: ReviewSession) -> list[int]:
    db.expire_all()
    return sorted(
        db.execute(select(model.id).where(model.session_id == s.id)).scalars()
    )


@pytest.mark.parametrize("page", list(_EMPTY_FILE_CARDS))
def test_an_empty_file_chosen_is_read_not_swapped_for_the_held_one(
    db: Session, client: TestClient, page: str
) -> None:
    """Findings S2: a file chosen with nothing in it is the operator's
    upload, refused as an empty one is, not a cue to send the held file.
    A filename is what marks a file chosen, as Quick Setup's
    ``_attached`` reads it; an untouched input posts an empty name."""
    model, first, held = _EMPTY_FILE_CARDS[page]
    if first is None:
        s = _seed(db, client, f"held-empty-{page}")
        url = f"{_base(s)}/import"
    else:
        s = _session(client, db, code=f"held-empty-{page}")
        url = f"/operator/sessions/{s.public_id}/{page}/import"
        assert _upload(client, url, first).status_code == 303
    before = _row_ids(db, model, s)
    asked = _upload(client, url, held)
    assert asked.status_code == 400
    assert _held(db) == 1

    sent = client.post(
        url,
        files={"file": ("empty.csv", b"", "text/csv")},
        data={"confirm_replace": "true", "held_token": _token(asked.text)},
        follow_redirects=False,
    )
    assert sent.status_code == 400, sent.text[:300]
    assert "Holding <strong>" not in sent.text
    assert _row_ids(db, model, s) == before
    # A plain refusal, so the hold ends with it.
    assert _held(db) == 0


def test_an_untouched_file_input_still_sends_the_held_file(
    db: Session, client: TestClient
) -> None:
    """The other side of S2: a browser posts an untouched file input as
    an empty part with ``filename=""``, and that is no file chosen.
    Written by hand because httpx drops an empty filename."""
    s = _session(client, db, code="held-untouched")
    url = f"/operator/sessions/{s.public_id}/reviewers/import"
    _upload(client, url, REVIEWERS_1)
    asked = _upload(client, url, REVIEWERS_2)

    fields = {"confirm_replace": "true", "held_token": _token(asked.text)}
    body = b"".join(
        f'--BB\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'
        f"{value}\r\n".encode()
        for name, value in fields.items()
    ) + (
        b'--BB\r\nContent-Disposition: form-data; name="file"; filename=""\r\n'
        b"Content-Type: application/octet-stream\r\n\r\n\r\n--BB--\r\n"
    )
    answered = client.post(
        url,
        content=body,
        headers={"content-type": "multipart/form-data; boundary=BB"},
        follow_redirects=False,
    )
    assert answered.status_code == 303, answered.text[:300]
    assert _reviewers(db, s) == ["Bea"]
    assert _held(db) == 0
