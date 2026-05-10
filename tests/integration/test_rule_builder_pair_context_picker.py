"""Integration coverage for Segment 15D PR 3 — Rule Builder field
picker exposes the new ``pair_context.tag_N`` options.

The grammar work is unit-tested in
``tests/unit/test_rules_pair_context_grammar.py``; this file pins
the editor surface (the operator-visible dropdown) and round-trips
a saved rule that uses the new field through the existing save +
preview flow without crashing.
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, RuleSet, RuleSetRevision


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "RBPCTX", "code": code, "description": "d"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _intra_seed_id(db: Session) -> int:
    return db.execute(
        select(RuleSet.id).where(
            RuleSet.is_seed.is_(True),
            RuleSet.name == "Intra-group peer review",
        )
    ).scalar_one()


def _builder_url(session_id: int, *parts: str) -> str:
    base = (
        f"/operator/sessions/{session_id}"
        "/assignments/rule-based-editor"
    )
    return base if not parts else base + "/" + "/".join(parts)


def test_field_picker_includes_pair_context_options(
    client: TestClient, db: Session
) -> None:
    """The editor's <select class='rule-field'> dropdown surfaces the
    three pair_context options alongside the existing reviewer /
    reviewee tag options."""

    review_session = _make_session(client, db, code="rbpc-picker")
    intra_id = _intra_seed_id(db)
    # Save-As a Personal RuleSet so the editor renders an editable
    # form with at least one rule + the field-picker dropdown.
    response = client.post(
        _builder_url(review_session.id, "save"),
        data={
            "source_rule_set_id": str(intra_id),
            "name": "Picker-test",
            "combinator": "ALL_OF",
            "rules_json": json.dumps([
                {
                    "id": "r1",
                    "kind": "MATCH",
                    "enabled": True,
                    "predicate": {
                        "field": "reviewer.tag1",
                        "operator": "equals",
                        "operand": "x",
                        "case_sensitive": False,
                    },
                }
            ]),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    saved = db.execute(
        select(RuleSet).where(RuleSet.name == "Picker-test")
    ).scalar_one()

    body = client.get(
        _builder_url(review_session.id) + f"?rule_set_id={saved.id}"
    ).text
    # Each pair_context option appears in a <select> option; we don't
    # assert the surrounding markup beyond the value attribute.
    assert 'value="pair_context.tag1"' in body
    assert 'value="pair_context.tag2"' in body
    assert 'value="pair_context.tag3"' in body
    # Existing options survive.
    assert 'value="reviewer.tag1"' in body
    assert 'value="reviewee.tag1"' in body


def test_save_rule_using_pair_context_field_persists(
    client: TestClient, db: Session
) -> None:
    """A rule referencing ``pair_context.tag1`` saves cleanly through
    the editor's POST /save flow; the persisted revision carries the
    field in its rules_json."""

    review_session = _make_session(client, db, code="rbpc-save")
    intra_id = _intra_seed_id(db)

    rules_payload = [
        {
            "id": "r1",
            "kind": "MATCH",
            "enabled": True,
            "predicate": {
                "field": "pair_context.tag1",
                "operator": "equals",
                "operand": "Mentor",
                "case_sensitive": False,
            },
        }
    ]
    response = client.post(
        _builder_url(review_session.id, "save"),
        data={
            "source_rule_set_id": str(intra_id),
            "name": "Pair-context-save",
            "combinator": "ALL_OF",
            "rules_json": json.dumps(rules_payload),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    saved = db.execute(
        select(RuleSet).where(RuleSet.name == "Pair-context-save")
    ).scalar_one()
    revision = db.execute(
        select(RuleSetRevision).where(
            RuleSetRevision.id == saved.current_revision_id
        )
    ).scalar_one()
    persisted = revision.rules_json
    assert persisted[0]["predicate"]["field"] == "pair_context.tag1"


def test_engine_evaluation_with_pair_context_does_not_crash(
    client: TestClient, db: Session
) -> None:
    """End-to-end: a saved rule using pair_context.tag1 makes it
    through ``/assignments/rule-based/generate``. Per the PR 3 stub,
    the predicate evaluates to False (no relationships table read
    yet), so no pairs match — but the engine doesn't crash."""

    review_session = _make_session(client, db, code="rbpc-engine")
    intra_id = _intra_seed_id(db)

    # Roster the session.
    client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                b"ReviewerName,ReviewerEmail\nAlice,a@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{review_session.id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                b"RevieweeName,RevieweeEmail\nCarol,c@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )

    # Save a Personal RuleSet that filters on a pair_context tag.
    rules_payload = [
        {
            "id": "r1",
            "kind": "MATCH",
            "enabled": True,
            "predicate": {
                "field": "pair_context.tag1",
                "operator": "equals",
                "operand": "Mentor",
                "case_sensitive": False,
            },
        }
    ]
    save_response = client.post(
        _builder_url(review_session.id, "save"),
        data={
            "source_rule_set_id": str(intra_id),
            "name": "Engine-stub",
            "combinator": "ALL_OF",
            "rules_json": json.dumps(rules_payload),
        },
        follow_redirects=False,
    )
    assert save_response.status_code == 303, save_response.text
    saved = db.execute(
        select(RuleSet).where(RuleSet.name == "Engine-stub")
    ).scalar_one()

    # Generate against the saved RuleSet — the engine must not crash
    # on the pair_context field; no pairs match because the stub
    # resolver returns None.
    response = client.post(
        f"/operator/sessions/{review_session.id}/assignments/rule-based/generate",
        data={"rule_set_id": saved.id, "exclude_self_review": "false"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
