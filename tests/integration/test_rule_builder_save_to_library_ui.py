"""UI render tests for the Rule Builder's Save-to-library button +
in-library pill (PR 2 of the post-15C parity polish).

The Save-to-library route shipped in 15C Slice 4a but never grew a
button on the editor card. This PR wires the button + the
in-library pill near the Name input. Pinned shape:

- Seeded SessionRuleSet (workspace-locked) → no button, no pill.
- Authored SessionRuleSet, ``library_origin_id IS NULL`` →
  ``To library`` button visible; no pill.
- SessionRuleSet with ``library_origin_id IS NOT NULL`` →
  ``in library`` pill visible; ``To library`` button hidden.
- Unsaved draft / blank-draft branch → neither (no DB row yet).
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, SessionRuleSet


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "RBS2L", "code": code, "description": "d"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _builder_url(session_id: int) -> str:
    return (
        f"/operator/sessions/{session_id}"
        "/assignments/rule-based-editor"
    )


def _seed_id(db: Session, *, session_id: int, name: str) -> int:
    return db.execute(
        select(SessionRuleSet.id).where(
            SessionRuleSet.session_id == session_id,
            SessionRuleSet.name == name,
        )
    ).scalar_one()


def _save_as(
    client: TestClient, *, session_id: int, source_id: int, name: str
) -> int:
    """Save-As from a seed → returns the new SessionRuleSet id."""
    response = client.post(
        f"{_builder_url(session_id)}/save",
        data={
            "source_rule_set_id": source_id,
            "name": name,
            "combinator": "ALL_OF",
            "rules_json": json.dumps([]),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    # Location carries ``?rule_set_id={new_id}&saved=1``.
    return int(
        response.headers["location"]
        .rsplit("rule_set_id=", 1)[1]
        .split("&", 1)[0]
    )


# --- pill / button visibility ----------------------------------------------


def test_seeded_row_renders_neither_button_nor_pill(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rbs2l-seed")
    body = client.get(_builder_url(review_session.id)).text
    # Seeded rows render the read-only seed banner, no editable
    # form, no Save-to-library button, no in-library pill.
    assert 'id="rule-builder-seed-banner"' in body
    assert 'id="rule-builder-save-to-library-button"' not in body
    assert "in library" not in body


def test_authored_row_without_library_origin_shows_button(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rbs2l-auth")
    intra_id = _seed_id(
        db, session_id=review_session.id, name="Intra-group peer review"
    )
    new_id = _save_as(
        client,
        session_id=review_session.id,
        source_id=intra_id,
        name="My Authored Rule",
    )
    body = client.get(
        f"{_builder_url(review_session.id)}?rule_set_id={new_id}"
    ).text
    assert 'id="rule-builder-save-to-library-button"' in body
    # No in-library pill yet — operator hasn't pressed To library.
    assert "in library" not in body


def test_linked_row_shows_pill_hides_button(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rbs2l-linked")
    intra_id = _seed_id(
        db, session_id=review_session.id, name="Intra-group peer review"
    )
    new_id = _save_as(
        client,
        session_id=review_session.id,
        source_id=intra_id,
        name="Promote Me",
    )
    # Hit Save-to-library so the session row's library_origin_id
    # becomes non-NULL.
    response = client.post(
        f"{_builder_url(review_session.id)}/save-to-library",
        data={"rule_set_id": new_id},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text

    body = client.get(
        f"{_builder_url(review_session.id)}?rule_set_id={new_id}"
    ).text
    assert "in library" in body
    assert 'id="rule-builder-save-to-library-button"' not in body


def test_blank_draft_renders_neither(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rbs2l-blank")
    body = client.get(
        f"{_builder_url(review_session.id)}?new=1"
    ).text
    assert 'id="rule-builder-save-to-library-button"' not in body
    assert "in library" not in body


def test_copy_draft_renders_neither(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rbs2l-draft")
    intra_id = _seed_id(
        db, session_id=review_session.id, name="Intra-group peer review"
    )
    body = client.get(
        f"{_builder_url(review_session.id)}?draft_from={intra_id}"
    ).text
    assert 'id="rule-builder-save-to-library-button"' not in body
    assert "in library" not in body
