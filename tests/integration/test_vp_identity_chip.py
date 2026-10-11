"""The Band 2 card's reviewer-identity level, as scaffolded.

ProfileLink updates Item 2 rung 1 (``guide/profilelink_updates.md``): an
inert "Name, email" pill beside the Reviewees and Observers Responses
released cells, rendered ``hidden`` unless that cell is Raw, and the
same pill after the Reviewees cell of the card's locked table. Nothing
stores a level yet, so it always reads today's Raw.
"""

from __future__ import annotations

import re

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Instrument, ReviewSession


def _session(client: TestClient, db: Session, code: str) -> tuple[int, int]:
    response = client.post(
        "/operator/sessions",
        data={"name": "S", "code": code, "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    session = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == session.id)
    ).scalars().first()
    return session.id, instrument.id


def _pill(body: str, attr: str) -> str:
    match = re.search(rf"<span [^>]*{re.escape(attr)}[^>]*>[^<]*</span>", body)
    assert match, attr
    return " ".join(match.group(0).split())


def test_identity_pills_hide_unless_the_released_cell_is_raw(
    client: TestClient, db: Session
) -> None:
    session_id, _ = _session(client, db, "vp-ident-off")
    body = client.get(f"/operator/sessions/{session_id}/instruments").text
    for attr in (
        'data-new-model-vp-identity="reviewee"',
        'data-new-model-vp-identity="observer"',
        'data-new-model-vp-identity-preview="reviewee"',
    ):
        pill = _pill(body, attr)
        assert " hidden" in pill, pill
        assert pill.endswith(">Name, email</span>"), pill
    # Reviewers see their own work; nothing identifies them to anyone.
    assert 'data-new-model-vp-identity="peer_reviewer"' not in body
    assert 'data-new-model-vp-identity-preview="peer_reviewer"' not in body


def test_identity_pills_show_beside_a_raw_released_cell(
    client: TestClient, db: Session
) -> None:
    session_id, instrument_id = _session(client, db, "vp-ident-raw")
    response = client.post(
        f"/operator/sessions/{session_id}/instruments/{instrument_id}/fields/save",
        data={
            "reviewee_after_release_mode": "raw",
            "observer_after_release_mode": "anonymized",
        },
        follow_redirects=False,
    )
    assert response.status_code in (200, 303), response.text
    body = client.get(f"/operator/sessions/{session_id}/instruments").text
    editor_reviewee = _pill(body, 'data-new-model-vp-identity="reviewee"')
    locked_reviewee = _pill(body, 'data-new-model-vp-identity-preview="reviewee"')
    observer = _pill(body, 'data-new-model-vp-identity="observer"')
    assert " hidden" not in editor_reviewee, editor_reviewee
    assert " hidden" not in locked_reviewee, locked_reviewee
    assert " hidden" in observer, observer
    # Inert until the level is stored: a display pill, not a chip.
    assert "tag-chip" not in editor_reviewee
    for attr in ("onclick", "tabindex", 'role="button"'):
        assert attr not in editor_reviewee, attr
