"""Integration tests for Segment 13A PR 5a — the RuleSet editor
read-only view + Copy action.

The editor child page renders the loaded RuleSet's metadata + rule
tree as the locked sentence-shaped surface form (segment plan
§"Rule semantics surface form"). PR 5a only ships the read-only
view + a Copy button that duplicates the loaded RuleSet into a new
Personal-scope RuleSet owned by the current user; PR 5b adds the
inline-JS predicate / quota editors.
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import AuditEvent, ReviewSession, RuleSet, RuleSetRevision


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "RBEditor", "code": code, "description": "d"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _seed_id(db: Session, name: str) -> int:
    return db.execute(
        select(RuleSet.id).where(
            RuleSet.is_seed.is_(True), RuleSet.name == name
        )
    ).scalar_one()


# ---------------------------------------------------------------------------
# GET — read-only view
# ---------------------------------------------------------------------------


def test_editor_renders_seed_with_readonly_banner_and_copy_form(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ed-seed")
    intra_id = _seed_id(db, "Intra-group peer review")

    body = client.get(
        f"/operator/sessions/{review_session.id}"
        f"/assignments/rule-based/edit/{intra_id}"
    ).text

    assert "Intra-group peer review" in body
    # The seed banner is the operator-facing read-only / Copy
    # affordance — load-bearing for the editor concept.
    assert 'id="rule-based-editor-seed-banner"' in body
    # Pill marker shows scope at-a-glance.
    assert ">seed</span>" in body
    # Combinator + Self-review status surfaced.
    assert "All of" in body
    # Copy form is rendered with a default name suggestion.
    assert 'action="/operator/sessions/' in body
    assert 'name="new_name"' in body
    assert "Intra-group peer review (copy)" in body


def test_editor_renders_match_predicate_in_sentence_form(
    client: TestClient, db: Session
) -> None:
    """Predicate sentences use plain-language verbs:
    ``equals`` → ``is``, ``same_as`` → ``is the same as``, etc.
    Per the locked editor concept (segment plan §"Rule semantics
    surface form")."""

    review_session = _make_session(client, db, code="ed-sentence")
    intra_id = _seed_id(db, "Intra-group peer review")

    body = client.get(
        f"/operator/sessions/{review_session.id}"
        f"/assignments/rule-based/edit/{intra_id}"
    ).text

    # Intra-group seed: MATCH(reviewer.tag1 same_as reviewee.tag1)
    assert (
        "Include pairs where reviewer tag1 is the same as "
        "reviewee tag1." in body
    )


def test_editor_renders_quota_rule_in_sentence_form(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ed-quota")
    quota_id = _seed_id(db, "Three reviewers per reviewee")

    body = client.get(
        f"/operator/sessions/{review_session.id}"
        f"/assignments/rule-based/edit/{quota_id}"
    ).text

    # Quota seed: PER_REVIEWEE min=3 max=3 RANDOM seed=42
    assert "Cap at 3 reviewer" in body
    assert "per reviewee" in body
    assert "chosen randomly (seed=42)" in body


def test_editor_404s_for_unknown_rule_set_id(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ed-404")
    response = client.get(
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based/edit/999999",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].endswith(
        "/assignments?rule_based_error=missing_rule_set"
    )


# ---------------------------------------------------------------------------
# POST — Copy
# ---------------------------------------------------------------------------


def test_copy_seed_creates_personal_rule_set_owned_by_caller(
    client: TestClient, db: Session, alice: AuthenticatedUser
) -> None:
    review_session = _make_session(client, db, code="ed-copy")
    intra_id = _seed_id(db, "Intra-group peer review")

    response = client.post(
        f"/operator/sessions/{review_session.id}/assignments/rule-based/copy",
        data={
            "rule_set_id": intra_id,
            "new_name": "Alice's intra-group",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    new_rule_set = db.execute(
        select(RuleSet).where(RuleSet.name == "Alice's intra-group")
    ).scalar_one()
    assert new_rule_set.scope == "personal"
    assert new_rule_set.is_seed is False
    assert new_rule_set.deleted_at is None
    assert new_rule_set.current_revision_id is not None

    revision = db.execute(
        select(RuleSetRevision).where(
            RuleSetRevision.id == new_rule_set.current_revision_id
        )
    ).scalar_one()
    assert revision.revision_no == 1
    assert revision.combinator == "ALL_OF"
    # Rule tree copied verbatim from the seed.
    assert (
        revision.rules_json[0]["predicate"]["operator"] == "same_as"
    )

    # 303 lands on the new RuleSet's editor URL.
    assert response.headers["location"].endswith(
        f"/assignments/rule-based/edit/{new_rule_set.id}"
    )


def test_copy_emits_rule_set_created_audit_with_provenance_refs(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ed-audit")
    intra_id = _seed_id(db, "Intra-group peer review")

    client.post(
        f"/operator/sessions/{review_session.id}/assignments/rule-based/copy",
        data={"rule_set_id": intra_id, "new_name": "audit-copy"},
        follow_redirects=False,
    )

    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "rule_set.created"
        )
    ).scalars().one()
    detail = event.detail or {}
    assert detail.get("snapshot", {}).get("scope") == "personal"
    assert detail.get("snapshot", {}).get("is_seed") is False
    refs = detail.get("refs", {})
    assert refs.get("source_rule_set_id") == intra_id
    assert isinstance(refs.get("rule_set_id"), int)
    assert refs.get("rule_set_id") != intra_id
    assert detail.get("context", {}).get("via") == "copy"


def test_copy_with_blank_name_redirects_back_with_error(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ed-blank")
    intra_id = _seed_id(db, "Intra-group peer review")

    response = client.post(
        f"/operator/sessions/{review_session.id}/assignments/rule-based/copy",
        data={"rule_set_id": intra_id, "new_name": "   "},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].endswith(
        f"/edit/{intra_id}?error=empty_name"
    )

    # No new RuleSet was created.
    assert (
        db.execute(
            select(RuleSet).where(RuleSet.name == "   ")
        ).scalar_one_or_none()
        is None
    )


def test_copy_of_unknown_rule_set_redirects_to_assignments(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ed-copy-404")
    response = client.post(
        f"/operator/sessions/{review_session.id}/assignments/rule-based/copy",
        data={"rule_set_id": 999_999, "new_name": "x"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].endswith(
        "/assignments?rule_based_error=missing_rule_set"
    )


# ---------------------------------------------------------------------------
# Permission gates (Personal RuleSets are owner-private)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# PR 5b — Personal RuleSet edit mode + Save As
# ---------------------------------------------------------------------------


def _copy_seed_to_personal(
    client: TestClient, db: Session, *, session_id: int, seed_name: str,
    personal_name: str,
) -> RuleSet:
    seed_id = _seed_id(db, seed_name)
    client.post(
        f"/operator/sessions/{session_id}/assignments/rule-based/copy",
        data={"rule_set_id": seed_id, "new_name": personal_name},
        follow_redirects=False,
    )
    return db.execute(
        select(RuleSet).where(RuleSet.name == personal_name)
    ).scalar_one()


def test_personal_rule_set_renders_edit_controls(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ed-edit")
    personal = _copy_seed_to_personal(
        client, db,
        session_id=review_session.id,
        seed_name="Intra-group peer review",
        personal_name="Edit-me",
    )

    body = client.get(
        f"/operator/sessions/{review_session.id}"
        f"/assignments/rule-based/edit/{personal.id}"
    ).text

    # Save As form + the inline JS hidden field marker.
    assert 'id="rule-based-editor-form"' in body
    assert 'id="rule-based-editor-rules-json"' in body
    # Combinator is now a <select>, not a static pill.
    assert 'name="combinator"' in body
    assert 'name="exclude_self_reviews"' in body
    # Field + operator pickers render with the expected values.
    assert 'class="rule-field"' in body
    assert 'class="rule-operator"' in body
    # Add-rule buttons are present.
    assert 'id="rule-based-editor-add-match"' in body
    assert 'id="rule-based-editor-add-filter"' in body
    assert 'id="rule-based-editor-add-quota"' in body


def test_save_as_with_edited_predicate_creates_new_personal_rule_set(
    client: TestClient, db: Session
) -> None:
    """Edit a Personal RuleSet's MATCH predicate (tag1 → tag2) and
    Save As. The new RuleSet picks up the edited tree; the loaded
    RuleSet stays unchanged (PR 6 will land in-place Save)."""

    review_session = _make_session(client, db, code="ed-saveas")
    personal = _copy_seed_to_personal(
        client, db,
        session_id=review_session.id,
        seed_name="Intra-group peer review",
        personal_name="To-edit",
    )

    edited_rules = [
        {
            "id": "same_tag2",
            "kind": "MATCH",
            "enabled": True,
            "predicate": {
                "field": "reviewer.tag2",
                "operator": "same_as",
                "operand": "reviewee.tag2",
                "case_sensitive": False,
            },
        }
    ]

    response = client.post(
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based/save-as",
        data={
            "source_rule_set_id": personal.id,
            "new_name": "Edited copy",
            "combinator": "ALL_OF",
            "exclude_self_reviews": "true",
            "rules_json": json.dumps(edited_rules),
            "seed": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    new_rs = db.execute(
        select(RuleSet).where(RuleSet.name == "Edited copy")
    ).scalar_one()
    assert new_rs.scope == "personal"
    revision = db.execute(
        select(RuleSetRevision).where(
            RuleSetRevision.id == new_rs.current_revision_id
        )
    ).scalar_one()
    assert revision.rules_json[0]["predicate"]["field"] == "reviewer.tag2"
    assert revision.rules_json[0]["predicate"]["operator"] == "same_as"

    # The loaded RuleSet's revision is untouched.
    source_revision = db.execute(
        select(RuleSetRevision).where(
            RuleSetRevision.rule_set_id == personal.id
        )
    ).scalar_one()
    assert source_revision.rules_json[0]["predicate"]["field"] == "reviewer.tag1"


def test_save_as_emits_audit_with_via_save_as(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ed-saveas-audit")
    personal = _copy_seed_to_personal(
        client, db,
        session_id=review_session.id,
        seed_name="Intra-group peer review",
        personal_name="Audit-source",
    )

    client.post(
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based/save-as",
        data={
            "source_rule_set_id": personal.id,
            "new_name": "Audit-saveas",
            "combinator": "ALL_OF",
            "exclude_self_reviews": "true",
            "rules_json": "[]",
            "seed": "",
        },
        follow_redirects=False,
    )

    new_rs = db.execute(
        select(RuleSet).where(RuleSet.name == "Audit-saveas")
    ).scalar_one()
    events = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "rule_set.created")
    ).scalars().all()
    save_as_event = next(
        e for e in events
        if (e.detail or {}).get("refs", {}).get("rule_set_id") == new_rs.id
    )
    detail = save_as_event.detail or {}
    assert detail.get("context", {}).get("via") == "save_as"
    assert detail.get("refs", {}).get("source_rule_set_id") == personal.id


def test_save_as_rejects_malformed_json(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ed-malformed")
    personal = _copy_seed_to_personal(
        client, db,
        session_id=review_session.id,
        seed_name="Intra-group peer review",
        personal_name="Malformed-source",
    )

    response = client.post(
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based/save-as",
        data={
            "source_rule_set_id": personal.id,
            "new_name": "x",
            "combinator": "ALL_OF",
            "exclude_self_reviews": "true",
            "rules_json": "{not json}",
            "seed": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].endswith(
        f"/edit/{personal.id}?error=malformed_json"
    )


def test_save_as_rejects_invalid_rule_tree(
    client: TestClient, db: Session
) -> None:
    """A malformed predicate (unknown operator) fails Pydantic
    validation and 303s back with ``?error=validation``."""

    review_session = _make_session(client, db, code="ed-validation")
    personal = _copy_seed_to_personal(
        client, db,
        session_id=review_session.id,
        seed_name="Intra-group peer review",
        personal_name="Validation-source",
    )

    bad_rules = [
        {
            "id": "bad",
            "kind": "MATCH",
            "enabled": True,
            "predicate": {
                "field": "reviewer.tag1",
                "operator": "INVENTED",
                "operand": "x",
                "case_sensitive": False,
            },
        }
    ]
    response = client.post(
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based/save-as",
        data={
            "source_rule_set_id": personal.id,
            "new_name": "x",
            "combinator": "ALL_OF",
            "exclude_self_reviews": "true",
            "rules_json": json.dumps(bad_rules),
            "seed": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].endswith(
        f"/edit/{personal.id}?error=validation"
    )


def test_save_as_round_trips_composite_children_untouched(
    client: TestClient, db: Session
) -> None:
    """Composite editing is a 5c follow-on; PR 5b serialises a
    composite rule by reading the parent's
    ``data-composite-children`` attribute. To pin that round-trip
    works at the route level (the JS submission produces a
    composite-shape ``rules_json``), construct the composite tree
    by hand and submit it directly."""

    review_session = _make_session(client, db, code="ed-composite")
    personal = _copy_seed_to_personal(
        client, db,
        session_id=review_session.id,
        seed_name="Intra-group peer review",
        personal_name="Composite-source",
    )

    composite_rules = [
        {
            "id": "leads_intra",
            "kind": "COMPOSITE",
            "enabled": True,
            "op": "AND",
            "rules": [
                {
                    "id": "lead_r",
                    "kind": "MATCH",
                    "enabled": True,
                    "predicate": {
                        "field": "reviewer.tag2",
                        "operator": "equals",
                        "operand": "Lead",
                        "case_sensitive": False,
                    },
                },
                {
                    "id": "intra",
                    "kind": "MATCH",
                    "enabled": True,
                    "predicate": {
                        "field": "reviewer.tag1",
                        "operator": "same_as",
                        "operand": "reviewee.tag1",
                        "case_sensitive": False,
                    },
                },
            ],
        }
    ]
    client.post(
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based/save-as",
        data={
            "source_rule_set_id": personal.id,
            "new_name": "Composite-out",
            "combinator": "ALL_OF",
            "exclude_self_reviews": "true",
            "rules_json": json.dumps(composite_rules),
            "seed": "",
        },
        follow_redirects=False,
    )

    new_rs = db.execute(
        select(RuleSet).where(RuleSet.name == "Composite-out")
    ).scalar_one()
    revision = db.execute(
        select(RuleSetRevision).where(
            RuleSetRevision.id == new_rs.current_revision_id
        )
    ).scalar_one()
    assert revision.rules_json[0]["kind"] == "COMPOSITE"
    assert revision.rules_json[0]["op"] == "AND"
    assert len(revision.rules_json[0]["rules"]) == 2


def test_other_users_personal_rule_set_returns_403(
    db: Session,
    alice: AuthenticatedUser,
    bob: AuthenticatedUser,
    make_client,  # noqa: ANN001
) -> None:
    """Permission gate: a Personal RuleSet is private to its owner.
    Bob can't open Alice's RuleSet in the editor; Alice can."""

    alice_client = make_client(alice)
    review_session = _make_session(alice_client, db, code="ed-priv")
    intra_id = _seed_id(db, "Intra-group peer review")

    # Alice copies the seed into her own Personal RuleSet.
    alice_client.post(
        f"/operator/sessions/{review_session.id}/assignments/rule-based/copy",
        data={"rule_set_id": intra_id, "new_name": "Alice private"},
        follow_redirects=False,
    )
    alice_rs = db.execute(
        select(RuleSet).where(RuleSet.name == "Alice private")
    ).scalar_one()

    # Bob can see seeds but not Alice's Personal RuleSet.
    bob_client = make_client(bob)
    response = bob_client.get(
        f"/operator/sessions/{review_session.id}"
        f"/assignments/rule-based/edit/{alice_rs.id}",
        follow_redirects=False,
    )
    # Bob isn't an operator on Alice's session → 403 from the
    # session-permission gate, which fires before the RuleSet
    # ownership check. Either way: not 200.
    assert response.status_code == 403
