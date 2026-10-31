"""Merging through the four roster Upload cards (segment 19Z, upsert
amendment, rung 10): the merge tick reaches the service; more than one
tick asks; two file rows on one directory account refuse the file; a
Reviewees merge that would clear saved group answers asks first with the
count, on a field of its own, and the count answers it.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Relationship, Reviewer

from .test_held_upload_setup_cards import _held, _session, _token, _upload
from .test_roster_append_routes import _relationships_session


def _names(db: Session, session_id: int) -> dict[str, str | None]:
    db.expire_all()
    return {
        r.email: r.tag_1
        for r in db.execute(select(Reviewer).where(Reviewer.session_id == session_id)).scalars()
    }


def test_the_merge_tick_updates_matched_rows_and_adds_the_rest(client: TestClient, db: Session) -> None:
    s = _session(client, db, code="mrr-basic")
    url = f"/operator/sessions/{s.public_id}/reviewers/import"
    _upload(client, url, b"ReviewerName,ReviewerEmail,ReviewerTag1\nAnn,ann@example.edu,A\nKim,kim@example.edu,K\n")

    merged = _upload(
        client, url, b"ReviewerName,ReviewerEmail,ReviewerTag1\nAnn,ann@example.edu,B\nBea,bea@example.edu,\n",
        merge="true",
    )
    assert merged.status_code == 303, merged.text[:400]
    assert _names(db, s.id) == {"ann@example.edu": "B", "kim@example.edu": "K", "bea@example.edu": None}


@pytest.mark.parametrize("ticks", [{"merge": "true", "append": "true"}, {"merge": "true", "confirm_replace": "true"}])
def test_more_than_one_tick_asks_and_holds(client: TestClient, db: Session, ticks: dict[str, str]) -> None:
    s = _session(client, db, code=f"mrr-two-{len(ticks)}-{sorted(ticks)[0]}")
    url = f"/operator/sessions/{s.public_id}/observers/import"
    _upload(client, url, b"ObserverName,ObserverEmail\nAnn,ann@example.edu\n")
    asked = _upload(client, url, b"ObserverName,ObserverEmail\nBea,bea@example.edu\n", **ticks)
    assert asked.status_code == 400
    assert "Tick only one of replace, append or merge" in asked.text
    assert _held(db) == 1
    assert 'name="merge" value="true" checked' not in asked.text


def test_two_file_rows_on_one_account_refuse_the_merge(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from cordware.graph import FakeDirectory
    from app.web.routes_operator import _shared

    monkeypatch.setattr(_shared, "directory_or_none", lambda request: FakeDirectory())
    s = _session(client, db, code="mrr-acct")
    url = f"/operator/sessions/{s.public_id}/reviewers/import"
    _upload(client, url, b"ReviewerName,ReviewerEmail\nKim,kim@example.edu\n")
    refused = _upload(
        client, url,
        b"ReviewerName,ReviewerEmail\nJane,jane.tan@example.edu\nJane,e0123456@example.edu\n",
        merge="true",
    )
    assert refused.status_code == 400
    assert "is a directory account named twice in the file" in refused.text
    assert set(_names(db, s.id)) == {"kim@example.edu"}


def test_a_reviewees_merge_that_redraws_an_answered_group_asks_first(client: TestClient, db: Session) -> None:
    """Ann moves from red into blue by a merged tag: the card asks with
    the count in its banner, on `acknowledge_group_clear` (the card's
    hidden `acknowledge_response_loss` carries `true` for a replace), the
    merge tick stays ticked and the file is held; the count answers it."""
    from .test_group_clear_asks_first import _responses, _reviewee, _seed

    session, _ = _seed(db, client, "mrr-groups")
    url = f"/operator/sessions/{session.public_id}/reviewees/import"
    csv = b"RevieweeName,RevieweeEmail,RevieweeTag1\nAnn,ann@example.edu,blue\n"

    asked = _upload(client, url, csv, merge="true")
    assert asked.status_code == 400
    assert "data-group-clear-banner" in asked.text
    assert re.search(r'name="acknowledge_group_clear"\s+value="3"', asked.text)
    assert re.search(r'name="merge" value="true" checked', asked.text)
    assert _held(db) == 1
    assert _reviewee(db, session.id, "Ann").tag_1 == "red"
    assert _responses(db) == 4

    answered = _upload(
        client, url, None, merge="true", acknowledge_group_clear="3", held_token=_token(asked.text)
    )
    assert answered.status_code == 303, answered.text[:400]
    assert _reviewee(db, session.id, "Ann").tag_1 == "blue"
    assert _responses(db) == 1
    assert _held(db) == 0


def test_relationships_merge_updates_a_held_pairs_tags(client: TestClient, db: Session) -> None:
    s, url = _relationships_session(client, db, "mrr-rel")
    merged = _upload(
        client, url,
        b"ReviewerEmail,RevieweeEmail,PairContextTag1\nal@example.edu,cy@example.edu,G\nbo@example.edu,cy@example.edu,\n",
        merge="true",
    )
    assert merged.status_code == 303, merged.text[:400]
    db.expire_all()
    tags = sorted(
        (r.tag_1 or "") for r in db.execute(select(Relationship).where(Relationship.session_id == s.id)).scalars()
    )
    assert tags == ["", "G"]
