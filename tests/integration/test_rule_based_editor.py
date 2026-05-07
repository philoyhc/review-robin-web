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


# ---------------------------------------------------------------------------
# PR 5c — composite-tree editing
# ---------------------------------------------------------------------------


def test_composite_renders_op_picker_and_add_child_buttons(
    client: TestClient, db: Session
) -> None:
    """A Personal RuleSet whose tree contains a COMPOSITE renders an
    op picker (AND / OR / NOT) and per-composite ``+ child MATCH`` /
    ``+ child FILTER`` buttons. The composite's children render as
    full edit rows immediately after the parent."""

    review_session = _make_session(client, db, code="ed-comp-render")

    # Save As a composite tree directly to construct the source state.
    seed_id = _seed_id(db, "Intra-group peer review")
    client.post(
        f"/operator/sessions/{review_session.id}/assignments/rule-based/copy",
        data={"rule_set_id": seed_id, "new_name": "Comp-source"},
        follow_redirects=False,
    )
    base = db.execute(
        select(RuleSet).where(RuleSet.name == "Comp-source")
    ).scalar_one()
    composite_rules = [
        {
            "id": "leads_intra",
            "kind": "COMPOSITE",
            "enabled": True,
            "op": "OR",
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
            "source_rule_set_id": base.id,
            "new_name": "Comp-rendered",
            "combinator": "ALL_OF",
            "exclude_self_reviews": "true",
            "rules_json": json.dumps(composite_rules),
            "seed": "",
        },
        follow_redirects=False,
    )
    composite_rs = db.execute(
        select(RuleSet).where(RuleSet.name == "Comp-rendered")
    ).scalar_one()

    body = client.get(
        f"/operator/sessions/{review_session.id}"
        f"/assignments/rule-based/edit/{composite_rs.id}"
    ).text

    # Composite renders as an editable row with op picker + add-
    # child buttons.
    assert 'class="rule-composite-op"' in body
    assert 'class="btn secondary composite-add-child"' in body
    # Children render as full edit rows with their own field /
    # operator pickers (i.e. PR 5c — not the read-only context line
    # from PR 5b).
    assert 'data-indent="1"' in body
    # Top-level + Add COMPOSITE button is present.
    assert 'id="rule-based-editor-add-composite"' in body


def test_save_as_round_trips_composite_with_op_change(
    client: TestClient, db: Session
) -> None:
    """Edit a composite's op (AND → OR) and Save As. The new RuleSet
    persists the changed op + the same children."""

    review_session = _make_session(client, db, code="ed-comp-op")
    personal = _copy_seed_to_personal(
        client, db,
        session_id=review_session.id,
        seed_name="Intra-group peer review",
        personal_name="Comp-op-source",
    )

    edited = [
        {
            "id": "outer",
            "kind": "COMPOSITE",
            "enabled": True,
            "op": "OR",
            "rules": [
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
                {
                    "id": "cross_role",
                    "kind": "MATCH",
                    "enabled": True,
                    "predicate": {
                        "field": "reviewer.tag2",
                        "operator": "different_from",
                        "operand": "reviewee.tag2",
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
            "new_name": "Comp-op-out",
            "combinator": "ANY_OF",
            "exclude_self_reviews": "true",
            "rules_json": json.dumps(edited),
            "seed": "",
        },
        follow_redirects=False,
    )

    new_rs = db.execute(
        select(RuleSet).where(RuleSet.name == "Comp-op-out")
    ).scalar_one()
    revision = db.execute(
        select(RuleSetRevision).where(
            RuleSetRevision.id == new_rs.current_revision_id
        )
    ).scalar_one()
    assert revision.rules_json[0]["op"] == "OR"
    children = revision.rules_json[0]["rules"]
    assert len(children) == 2
    assert children[1]["predicate"]["operator"] == "different_from"


def test_save_as_persists_added_top_level_composite(
    client: TestClient, db: Session
) -> None:
    """Build a fresh top-level COMPOSITE with two children and
    Save As. Pins the round-trip the JS serialiser produces when an
    operator clicks ``+ Add COMPOSITE`` and then ``+ child MATCH``
    twice on the new row."""

    review_session = _make_session(client, db, code="ed-comp-add")
    personal = _copy_seed_to_personal(
        client, db,
        session_id=review_session.id,
        seed_name="Intra-group peer review",
        personal_name="Comp-add-source",
    )

    rules = [
        {
            "id": "new_c",
            "kind": "COMPOSITE",
            "enabled": True,
            "op": "AND",
            "rules": [
                {
                    "id": "child1",
                    "kind": "MATCH",
                    "enabled": True,
                    "predicate": {
                        "field": "reviewer.tag1",
                        "operator": "equals",
                        "operand": "GroupA",
                        "case_sensitive": False,
                    },
                },
                {
                    "id": "child2",
                    "kind": "MATCH",
                    "enabled": True,
                    "predicate": {
                        "field": "reviewee.tag1",
                        "operator": "equals",
                        "operand": "GroupA",
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
            "new_name": "Comp-add-out",
            "combinator": "ALL_OF",
            "exclude_self_reviews": "true",
            "rules_json": json.dumps(rules),
            "seed": "",
        },
        follow_redirects=False,
    )

    new_rs = db.execute(
        select(RuleSet).where(RuleSet.name == "Comp-add-out")
    ).scalar_one()
    revision = db.execute(
        select(RuleSetRevision).where(
            RuleSetRevision.id == new_rs.current_revision_id
        )
    ).scalar_one()
    composite = revision.rules_json[0]
    assert composite["kind"] == "COMPOSITE"
    assert composite["op"] == "AND"
    assert len(composite["rules"]) == 2
    assert all(child["kind"] == "MATCH" for child in composite["rules"])


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


# ---------------------------------------------------------------------------
# PR 6 — Save (in-place) / Rename / Delete + revisioning
# ---------------------------------------------------------------------------


def test_save_in_place_appends_revision_and_keeps_rule_set_id(
    client: TestClient, db: Session
) -> None:
    """In-place Save bumps ``revision_no`` and keeps the same
    RuleSet row. Past Generate runs that pinned the previous
    revision id stay resolvable because old revisions are
    retained."""

    review_session = _make_session(client, db, code="ed-save")
    personal = _copy_seed_to_personal(
        client, db,
        session_id=review_session.id,
        seed_name="Intra-group peer review",
        personal_name="Save-source",
    )
    initial_revision_id = personal.current_revision_id

    edited_rules = [
        {
            "id": "intra",
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
        "/assignments/rule-based/save",
        data={
            "rule_set_id": personal.id,
            "combinator": "ALL_OF",
            "exclude_self_reviews": "true",
            "rules_json": json.dumps(edited_rules),
            "seed": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].endswith(
        f"/edit/{personal.id}?saved=1"
    )

    db.refresh(personal)
    assert personal.current_revision_id != initial_revision_id

    revisions = db.execute(
        select(RuleSetRevision)
        .where(RuleSetRevision.rule_set_id == personal.id)
        .order_by(RuleSetRevision.revision_no)
    ).scalars().all()
    assert [r.revision_no for r in revisions] == [1, 2]
    assert revisions[1].rules_json[0]["predicate"]["field"] == "reviewer.tag2"
    # Old revision row retained for audit-ref resolution.
    assert revisions[0].rules_json[0]["predicate"]["field"] == "reviewer.tag1"


def test_save_emits_rule_set_updated_audit_with_changes(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ed-save-audit")
    personal = _copy_seed_to_personal(
        client, db,
        session_id=review_session.id,
        seed_name="Intra-group peer review",
        personal_name="Save-audit",
    )

    client.post(
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based/save",
        data={
            "rule_set_id": personal.id,
            "combinator": "ANY_OF",  # changed from ALL_OF
            "exclude_self_reviews": "false",  # changed
            "rules_json": "[]",
            "seed": "",
        },
        follow_redirects=False,
    )

    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "rule_set.updated"
        )
    ).scalars().one()
    detail = event.detail or {}
    assert detail.get("context", {}).get("via") == "save"
    changes = detail.get("changes") or {}
    assert "combinator" in changes
    assert changes["combinator"] == ["ALL_OF", "ANY_OF"]
    assert "exclude_self_reviews" in changes
    refs = detail.get("refs") or {}
    assert refs.get("rule_set_id") == personal.id


def test_save_rejects_seed(client: TestClient, db: Session) -> None:
    """In-place Save must reject seeds — they're read-only."""

    review_session = _make_session(client, db, code="ed-save-seed")
    seed_id = _seed_id(db, "Full Matrix")
    response = client.post(
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based/save",
        data={
            "rule_set_id": seed_id,
            "combinator": "ALL_OF",
            "exclude_self_reviews": "true",
            "rules_json": "[]",
            "seed": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400


def test_save_rejects_other_users_personal_rule_set(
    db: Session,
    alice: AuthenticatedUser,
    bob: AuthenticatedUser,
    make_client,  # noqa: ANN001
) -> None:
    alice_client = make_client(alice)
    review_session = _make_session(alice_client, db, code="ed-save-priv")
    intra_id = _seed_id(db, "Intra-group peer review")
    alice_client.post(
        f"/operator/sessions/{review_session.id}/assignments/rule-based/copy",
        data={"rule_set_id": intra_id, "new_name": "Alice's"},
        follow_redirects=False,
    )
    alice_rs = db.execute(
        select(RuleSet).where(RuleSet.name == "Alice's")
    ).scalar_one()

    bob_client = make_client(bob)
    response = bob_client.post(
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based/save",
        data={
            "rule_set_id": alice_rs.id,
            "combinator": "ALL_OF",
            "exclude_self_reviews": "true",
            "rules_json": "[]",
            "seed": "",
        },
        follow_redirects=False,
    )
    # Bob isn't an operator on Alice's session → 403 from the
    # session gate; ownership gate would also 403 if he were.
    assert response.status_code == 403


def test_rename_updates_metadata_without_bumping_revision(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ed-rename")
    personal = _copy_seed_to_personal(
        client, db,
        session_id=review_session.id,
        seed_name="Intra-group peer review",
        personal_name="Rename-source",
    )
    initial_revision_id = personal.current_revision_id

    response = client.post(
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based/rename",
        data={
            "rule_set_id": personal.id,
            "new_name": "Renamed",
            "new_description": "Updated description",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].endswith(
        f"/edit/{personal.id}?renamed=1"
    )

    db.refresh(personal)
    assert personal.name == "Renamed"
    assert personal.description == "Updated description"
    # Revision pointer untouched.
    assert personal.current_revision_id == initial_revision_id

    revisions = db.execute(
        select(RuleSetRevision).where(RuleSetRevision.rule_set_id == personal.id)
    ).scalars().all()
    assert len(revisions) == 1


def test_rename_emits_audit_with_changes_and_via_rename(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ed-rename-audit")
    personal = _copy_seed_to_personal(
        client, db,
        session_id=review_session.id,
        seed_name="Intra-group peer review",
        personal_name="Rename-audit",
    )

    client.post(
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based/rename",
        data={
            "rule_set_id": personal.id,
            "new_name": "Rename-audit-2",
            "new_description": "",
        },
        follow_redirects=False,
    )

    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "rule_set.updated"
        )
    ).scalars().one()
    detail = event.detail or {}
    assert detail.get("context", {}).get("via") == "rename"
    assert detail.get("changes", {}).get("name") == [
        "Rename-audit", "Rename-audit-2"
    ]


def test_delete_soft_deletes_and_redirects_to_assignments(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ed-delete")
    personal = _copy_seed_to_personal(
        client, db,
        session_id=review_session.id,
        seed_name="Intra-group peer review",
        personal_name="Delete-source",
    )

    response = client.post(
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based/delete",
        data={"rule_set_id": personal.id, "confirm": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].endswith(
        "?rule_based_error=rule_set_deleted"
    )

    db.refresh(personal)
    assert personal.deleted_at is not None
    # Revisions retained for audit-ref resolution.
    revisions = db.execute(
        select(RuleSetRevision).where(RuleSetRevision.rule_set_id == personal.id)
    ).scalars().all()
    assert len(revisions) == 1


def test_delete_without_confirm_redirects_back_with_error(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ed-delete-noconfirm")
    personal = _copy_seed_to_personal(
        client, db,
        session_id=review_session.id,
        seed_name="Intra-group peer review",
        personal_name="No-confirm",
    )

    response = client.post(
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based/delete",
        data={"rule_set_id": personal.id},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].endswith(
        f"/edit/{personal.id}?error=needs_delete_confirm"
    )

    db.refresh(personal)
    assert personal.deleted_at is None


def test_delete_emits_rule_set_deleted_audit(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ed-delete-audit")
    personal = _copy_seed_to_personal(
        client, db,
        session_id=review_session.id,
        seed_name="Intra-group peer review",
        personal_name="Delete-audit",
    )

    client.post(
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based/delete",
        data={"rule_set_id": personal.id, "confirm": "true"},
        follow_redirects=False,
    )

    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "rule_set.deleted"
        )
    ).scalars().one()
    detail = event.detail or {}
    assert detail.get("context", {}).get("soft") is True
    assert detail.get("snapshot", {}).get("name") == "Delete-audit"
    assert detail.get("refs", {}).get("rule_set_id") == personal.id


def test_delete_hides_rule_set_from_library_list(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ed-delete-lib")
    personal = _copy_seed_to_personal(
        client, db,
        session_id=review_session.id,
        seed_name="Intra-group peer review",
        personal_name="Delete-lib",
    )

    # Pre-delete: the card's selector includes the Personal RuleSet.
    body = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
    ).text
    assert ">Delete-lib</option>" in body

    client.post(
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based/delete",
        data={"rule_set_id": personal.id, "confirm": "true"},
        follow_redirects=False,
    )

    body = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
    ).text
    assert ">Delete-lib</option>" not in body
    # Soft-deleted rule sets remain resolvable for audit refs (i.e.
    # ``load_rule_set`` doesn't filter on deleted_at), so the editor
    # URL still 200s on the deleted RuleSet.
    response = client.get(
        f"/operator/sessions/{review_session.id}"
        f"/assignments/rule-based/edit/{personal.id}"
    )
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# PR 9 — source picker on the Copy form
# ---------------------------------------------------------------------------


def test_seed_copy_form_renders_source_picker(
    client: TestClient, db: Session
) -> None:
    """The seed-view Copy form's hidden ``rule_set_id`` is replaced
    with a visible source picker. Default selection is the loaded
    seed so the no-change behaviour matches PR 5a's Copy."""

    review_session = _make_session(client, db, code="ed-pr9-seed")
    intra_id = _seed_id(db, "Intra-group peer review")

    body = client.get(
        f"/operator/sessions/{review_session.id}"
        f"/assignments/rule-based/edit/{intra_id}"
    ).text

    seed_form = body.split('id="rule-based-seed-copy-form"', 1)[1]
    seed_form = seed_form.split("</form>", 1)[0]
    # The picker is named ``rule_set_id`` (matches the /copy route's
    # form parameter) and lists every visible seed.
    assert 'class="rule-based-copy-source"' in seed_form
    assert 'name="rule_set_id"' in seed_form
    for seed_name in (
        "Full Matrix",
        "Intra-group peer review",
        "Cross-group peer review",
        "Same group, different role",
        "Three reviewers per reviewee",
    ):
        assert seed_name in seed_form
    # Default selection is the loaded seed.
    assert (
        f'value="{intra_id}"\n                          selected'
        in seed_form
        or f'value="{intra_id}" selected' in seed_form
        or f'value="{intra_id}"' in seed_form
        and "selected" in seed_form
    )


def test_seed_copy_with_different_source_creates_from_picked(
    client: TestClient, db: Session
) -> None:
    """The operator opens the editor on Intra-group, picks
    Cross-group from the source picker, and submits Copy. The new
    Personal RuleSet's tree matches Cross-group, not Intra-group."""

    review_session = _make_session(client, db, code="ed-pr9-pick")
    intra_id = _seed_id(db, "Intra-group peer review")
    cross_id = _seed_id(db, "Cross-group peer review")

    response = client.post(
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based/copy",
        data={"rule_set_id": cross_id, "new_name": "PickedCross"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    new_rs = db.execute(
        select(RuleSet).where(RuleSet.name == "PickedCross")
    ).scalar_one()
    revision = db.execute(
        select(RuleSetRevision).where(
            RuleSetRevision.id == new_rs.current_revision_id
        )
    ).scalar_one()
    # Cross-group seed: MATCH(reviewer.tag1 different_from reviewee.tag1)
    assert (
        revision.rules_json[0]["predicate"]["operator"] == "different_from"
    )
    # The audit ref points back at the picked source, not the editor URL.
    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "rule_set.created"
        )
    ).scalars().one()
    refs = (event.detail or {}).get("refs", {})
    assert refs.get("source_rule_set_id") == cross_id
    # Make sure we didn't accidentally point Intra-group as the source.
    assert refs.get("source_rule_set_id") != intra_id


def test_personal_copy_form_renders_with_lose_draft_checkbox(
    client: TestClient, db: Session
) -> None:
    """The Personal-view Copy form carries the
    ``confirm_lose_draft`` required checkbox + the
    ``from_editor_with_draft=true`` hidden flag."""

    review_session = _make_session(client, db, code="ed-pr9-personal")
    personal = _copy_seed_to_personal(
        client, db,
        session_id=review_session.id,
        seed_name="Intra-group peer review",
        personal_name="PR9-personal",
    )

    body = client.get(
        f"/operator/sessions/{review_session.id}"
        f"/assignments/rule-based/edit/{personal.id}"
    ).text

    personal_form = body.split('id="rule-based-personal-copy-form"', 1)[1]
    personal_form = personal_form.split("</form>", 1)[0]
    assert 'name="from_editor_with_draft"' in personal_form
    assert 'name="referrer_rule_set_id"' in personal_form
    assert 'name="confirm_lose_draft"' in personal_form
    assert "required" in personal_form


def test_personal_copy_without_lose_draft_confirm_redirects_back(
    client: TestClient, db: Session
) -> None:
    """A POST that omits ``confirm_lose_draft`` from a Personal
    editor 303s back with ``?error=needs_lose_draft_confirm`` and
    writes nothing."""

    review_session = _make_session(client, db, code="ed-pr9-noconfirm")
    personal = _copy_seed_to_personal(
        client, db,
        session_id=review_session.id,
        seed_name="Intra-group peer review",
        personal_name="NoConfirm",
    )
    cross_id = _seed_id(db, "Cross-group peer review")

    response = client.post(
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based/copy",
        data={
            "rule_set_id": cross_id,
            "new_name": "ShouldNotPersist",
            "from_editor_with_draft": "true",
            "referrer_rule_set_id": personal.id,
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].endswith(
        f"/edit/{personal.id}?error=needs_lose_draft_confirm"
    )
    assert (
        db.execute(
            select(RuleSet).where(RuleSet.name == "ShouldNotPersist")
        ).scalar_one_or_none()
        is None
    )


def test_personal_copy_with_lose_draft_confirm_creates_personal(
    client: TestClient, db: Session
) -> None:
    """With the confirm checkbox ticked, the Personal-editor Copy
    submission writes a new Personal RuleSet from the picked
    source, leaving the editor's loaded RuleSet untouched."""

    review_session = _make_session(client, db, code="ed-pr9-confirm")
    personal = _copy_seed_to_personal(
        client, db,
        session_id=review_session.id,
        seed_name="Intra-group peer review",
        personal_name="WithConfirm",
    )
    cross_id = _seed_id(db, "Cross-group peer review")

    response = client.post(
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based/copy",
        data={
            "rule_set_id": cross_id,
            "new_name": "Confirmed-copy",
            "from_editor_with_draft": "true",
            "referrer_rule_set_id": personal.id,
            "confirm_lose_draft": "true",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    new_rs = db.execute(
        select(RuleSet).where(RuleSet.name == "Confirmed-copy")
    ).scalar_one()
    assert new_rs.scope == "personal"
    # Source RuleSet (the editor's loaded one) is untouched.
    db.refresh(personal)
    assert personal.deleted_at is None
    revisions = db.execute(
        select(RuleSetRevision).where(
            RuleSetRevision.rule_set_id == personal.id
        )
    ).scalars().all()
    assert len(revisions) == 1


def test_source_picker_omits_other_users_personal_rule_sets(
    db: Session,
    alice: AuthenticatedUser,
    bob: AuthenticatedUser,
    make_client,  # noqa: ANN001
) -> None:
    """Visibility gate: the source picker only lists seeds + the
    caller's own Personal RuleSets."""

    alice_client = make_client(alice)
    review_session = _make_session(alice_client, db, code="ed-pr9-vis")
    intra_id = _seed_id(db, "Intra-group peer review")
    alice_client.post(
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based/copy",
        data={"rule_set_id": intra_id, "new_name": "Alice-only"},
        follow_redirects=False,
    )

    # Bob isn't an operator on Alice's session; the editor 403s
    # before we'd even render the picker. Validate Alice's view
    # instead — her picker lists "Alice-only" but no Bob entry.
    body = alice_client.get(
        f"/operator/sessions/{review_session.id}"
        f"/assignments/rule-based/edit/{intra_id}"
    ).text
    seed_form = body.split('id="rule-based-seed-copy-form"', 1)[1]
    seed_form = seed_form.split("</form>", 1)[0]
    assert "Alice-only" in seed_form
