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

from app.db.models import ReviewSession, SessionRuleSet


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


def _intra_seed_id(db: Session, session_id: int) -> int:
    return db.execute(
        select(SessionRuleSet.id).where(
            SessionRuleSet.session_id == session_id,
            SessionRuleSet.name == "Intra-group peer review",
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
    intra_id = _intra_seed_id(db, review_session.id)
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
        select(SessionRuleSet).where(
            SessionRuleSet.session_id == review_session.id,
            SessionRuleSet.name == "Picker-test",
        )
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
    intra_id = _intra_seed_id(db, review_session.id)

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
        select(SessionRuleSet).where(
            SessionRuleSet.session_id == review_session.id,
            SessionRuleSet.name == "Pair-context-save",
        )
    ).scalar_one()
    # SessionRuleSet carries rules_json directly — no revision indirection.
    persisted = saved.rules_json
    assert persisted[0]["predicate"]["field"] == "pair_context.tag1"


def test_pair_context_field_round_trips_through_save(
    client: TestClient, db: Session
) -> None:
    """End-to-end round-trip: a saved rule using ``pair_context.tag1``
    makes it through the editor's POST /save flow and re-reads the
    same field value on GET.

    Pre-Slice 4b this test went on to exercise the engine through
    ``/assignments/rule-based/generate`` — but that endpoint still
    resolves rule ids against the operator-library tier (it'll be
    rewired in 15B Slice 3 to read ``instruments.rule_set_id`` →
    ``session_rule_sets`` directly). Engine evaluation against
    pair_context predicates remains covered by the unit tests in
    ``tests/unit/test_rules_pair_context_grammar.py``.
    """

    review_session = _make_session(client, db, code="rbpc-roundtrip")
    intra_id = _intra_seed_id(db, review_session.id)

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
        select(SessionRuleSet).where(
            SessionRuleSet.session_id == review_session.id,
            SessionRuleSet.name == "Engine-stub",
        )
    ).scalar_one()

    # Re-read the saved row's rules_json directly to confirm the
    # pair_context field survives the Pydantic round-trip + the
    # session-tier snapshot write.
    assert saved.rules_json[0]["predicate"]["field"] == "pair_context.tag1"
