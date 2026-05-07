"""Integration tests for the live preview surface — Segment 13A
PR 7.

The new single-card Rule Builder (Segment 13A-1) explicitly drops
the preview slot. PR 4a rewires the operator's link target away
from the legacy editor; the preview surface is unreachable
through any UI link. This file is scheduled for deletion in PR 4b
alongside the legacy template + the ``/preview`` POST route.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, ReviewSession, RuleSet

pytestmark = pytest.mark.skip(
    reason=(
        "Segment 13A-1 PR 4a: legacy editor preview surface "
        "unreachable from the new Rule Builder. File retired in PR 4b."
    )
)


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "PreviewSession", "code": code, "description": "d"},
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


def _seed_population(
    client: TestClient, review_session: ReviewSession
) -> None:
    client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                (
                    b"ReviewerName,ReviewerEmail,ReviewerTag1\n"
                    b"Alice,alice@example.edu,A\n"
                    b"Bob,bob@example.edu,B\n"
                ),
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
                (
                    b"RevieweeName,RevieweeEmail,RevieweeTag1\n"
                    b"Carol,carol@example.edu,A\n"
                    b"Dan,dan@example.edu,B\n"
                ),
                "text/csv",
            )
        },
        follow_redirects=False,
    )


# ---------------------------------------------------------------------------
# Initial render
# ---------------------------------------------------------------------------


def test_editor_initial_render_includes_preview_pane(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="prev-init")
    _seed_population(client, review_session)
    intra_id = _seed_id(db, "Intra-group peer review")

    body = client.get(
        f"/operator/sessions/{review_session.id}"
        f"/assignments/rule-based/edit/{intra_id}"
    ).text

    # The preview container is in place.
    assert 'id="rule-based-editor-preview-container"' in body
    # And the body of the preview partial — Intra-group on this
    # 2-reviewer × 2-reviewee population yields exactly two same-
    # tag1 pairs (Alice → Carol, Bob → Dan).
    assert "2 unique pairs" in body
    assert 'id="rule-based-preview-body"' in body


def test_initial_preview_renders_empty_population_hint(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="prev-empty")
    intra_id = _seed_id(db, "Intra-group peer review")

    body = client.get(
        f"/operator/sessions/{review_session.id}"
        f"/assignments/rule-based/edit/{intra_id}"
    ).text

    rb_section = body.split('id="rule-based-editor-preview-container"', 1)[1]
    assert "Reviewers" in rb_section
    assert "Reviewees" in rb_section


# ---------------------------------------------------------------------------
# POST /preview
# ---------------------------------------------------------------------------


def test_preview_endpoint_returns_partial_html_with_pair_count(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="prev-post")
    _seed_population(client, review_session)
    intra_id = _seed_id(db, "Intra-group peer review")

    rules = [
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
        }
    ]
    response = client.post(
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based/preview",
        data={
            "rule_set_id": intra_id,
            "combinator": "ALL_OF",
            "exclude_self_reviews": "true",
            "rules_json": json.dumps(rules),
            "seed": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 200
    body = response.text
    # The response is the partial fragment, not the full editor page.
    assert "<!doctype html>" not in body.lower()
    assert 'id="rule-based-preview-body"' in body
    assert "2 unique pairs" in body


def test_preview_endpoint_emits_no_audit_writes(
    client: TestClient, db: Session
) -> None:
    """Running the preview twice produces no ``rule_set.*`` or
    ``assignments.generated`` audit rows. Read-only by design."""

    review_session = _make_session(client, db, code="prev-audit")
    _seed_population(client, review_session)
    intra_id = _seed_id(db, "Intra-group peer review")

    before_count = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type.in_(
                [
                    "rule_set.created",
                    "rule_set.updated",
                    "rule_set.deleted",
                    "assignments.generated",
                ]
            )
        )
    ).scalars().all()

    rules = [
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
        }
    ]
    for _ in range(2):
        client.post(
            f"/operator/sessions/{review_session.id}"
            "/assignments/rule-based/preview",
            data={
                "rule_set_id": intra_id,
                "combinator": "ALL_OF",
                "exclude_self_reviews": "true",
                "rules_json": json.dumps(rules),
                "seed": "",
            },
            follow_redirects=False,
        )

    after_count = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type.in_(
                [
                    "rule_set.created",
                    "rule_set.updated",
                    "rule_set.deleted",
                    "assignments.generated",
                ]
            )
        )
    ).scalars().all()
    assert len(before_count) == len(after_count)


def test_preview_with_invalid_rules_renders_warning_partial(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="prev-bad")
    _seed_population(client, review_session)
    intra_id = _seed_id(db, "Intra-group peer review")

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
        "/assignments/rule-based/preview",
        data={
            "rule_set_id": intra_id,
            "combinator": "ALL_OF",
            "exclude_self_reviews": "true",
            "rules_json": json.dumps(bad_rules),
            "seed": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 200
    # The error placeholder warns but doesn't 500.
    assert "invalid" in response.text.lower()


def test_preview_reflects_in_progress_combinator_change(
    client: TestClient, db: Session
) -> None:
    """Switching from intra-group ALL_OF to ANY_OF in the in-progress
    payload bumps the pair count (more pairs survive under ANY_OF)."""

    review_session = _make_session(client, db, code="prev-combo")
    _seed_population(client, review_session)
    intra_id = _seed_id(db, "Intra-group peer review")

    rules = [
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
            "id": "cross",
            "kind": "MATCH",
            "enabled": True,
            "predicate": {
                "field": "reviewer.tag1",
                "operator": "different_from",
                "operand": "reviewee.tag1",
                "case_sensitive": False,
            },
        },
    ]
    # Under ALL_OF: 0 pairs (a pair can't both share and not share tag1).
    body_all = client.post(
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based/preview",
        data={
            "rule_set_id": intra_id,
            "combinator": "ALL_OF",
            "exclude_self_reviews": "true",
            "rules_json": json.dumps(rules),
            "seed": "",
        },
        follow_redirects=False,
    ).text
    # Under ANY_OF: 4 pairs (every reviewer × reviewee covered, no
    # self-pair overlap because emails differ).
    body_any = client.post(
        f"/operator/sessions/{review_session.id}"
        "/assignments/rule-based/preview",
        data={
            "rule_set_id": intra_id,
            "combinator": "ANY_OF",
            "exclude_self_reviews": "true",
            "rules_json": json.dumps(rules),
            "seed": "",
        },
        follow_redirects=False,
    ).text

    assert "0 unique pair" in body_all
    assert "4 unique pairs" in body_any
