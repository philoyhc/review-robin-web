"""Integration tests for Segment 13A PR 4 — the live Generate path.

Login as operator, GET the assignments page, POST Generate against
each seeded RuleSet, assert assignments wrote and the audit context
reflects the actually-applied ``exclude_self_reviews`` value
(distinct from the RuleSet's stored default because the card-level
checkbox can override). Also cover the cascade-confirmation gate
(missing ``confirm_replace`` 303s back with a banner) and lifecycle
gate (locked sessions reject Generate).
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Assignment, AuditEvent, ReviewSession, RuleSet


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "RuleBased", "code": code, "description": "d"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _seed_population(
    client: TestClient, review_session: ReviewSession
) -> None:
    """Two reviewers and two reviewees, no overlap so self-reviews
    don't muddy the count."""

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


def _full_matrix_seed_id(db: Session) -> int:
    return db.execute(
        select(RuleSet.id).where(
            RuleSet.is_seed.is_(True), RuleSet.name == "Full Matrix"
        )
    ).scalar_one()


def _intra_group_seed_id(db: Session) -> int:
    return db.execute(
        select(RuleSet.id).where(
            RuleSet.is_seed.is_(True),
            RuleSet.name == "Intra-group peer review",
        )
    ).scalar_one()


def test_generate_with_full_matrix_seed_writes_assignments(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rb-fm")
    _seed_population(client, review_session)

    response = client.post(
        f"/operator/sessions/{review_session.id}/assignments/rule-based/generate",
        data={
            "rule_set_id": _full_matrix_seed_id(db),
            "exclude_self_review": "true",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    rows = db.execute(
        select(Assignment).where(Assignment.session_id == review_session.id)
    ).scalars().all()
    # 2 reviewers × 2 reviewees × 1 default instrument; no email
    # overlap so no self-reviews to drop.
    assert len(rows) == 4
    assert {row.created_by_mode for row in rows} == {"rule_based"}


def test_generate_with_intra_group_seed_filters_by_tag1(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rb-intra")
    _seed_population(client, review_session)

    response = client.post(
        f"/operator/sessions/{review_session.id}/assignments/rule-based/generate",
        data={
            "rule_set_id": _intra_group_seed_id(db),
            "exclude_self_review": "true",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    rows = db.execute(
        select(Assignment).where(Assignment.session_id == review_session.id)
    ).scalars().all()
    # Alice (A) → Carol (A); Bob (B) → Dan (B). 2 pairs.
    assert len(rows) == 2


def test_audit_context_records_actual_exclude_self_reviews_value(
    client: TestClient, db: Session
) -> None:
    """The override checkbox's value is what lands in the audit
    ``context.exclude_self_reviews``, not the RuleSet's stored
    default. The audit log is the source of truth for what ran."""

    review_session = _make_session(client, db, code="rb-audit")
    _seed_population(client, review_session)

    rule_set_id = _intra_group_seed_id(db)

    # Submit with the override OFF (unchecked).
    client.post(
        f"/operator/sessions/{review_session.id}/assignments/rule-based/generate",
        data={"rule_set_id": rule_set_id},
        follow_redirects=False,
    )
    event = db.execute(
        select(AuditEvent)
        .where(
            AuditEvent.session_id == review_session.id,
            AuditEvent.event_type == "assignments.generated",
        )
        .order_by(AuditEvent.created_at.desc())
    ).scalars().first()
    assert event is not None
    detail = event.detail or {}
    assert detail["context"]["mode"] == "rule_based"
    assert detail["context"]["exclude_self_reviews"] is False
    assert detail["refs"]["rule_set_id"] == rule_set_id


def test_audit_refs_carry_rule_set_revision_id(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rb-refs")
    _seed_population(client, review_session)

    rule_set_id = _full_matrix_seed_id(db)
    client.post(
        f"/operator/sessions/{review_session.id}/assignments/rule-based/generate",
        data={
            "rule_set_id": rule_set_id,
            "exclude_self_review": "true",
        },
        follow_redirects=False,
    )

    event = db.execute(
        select(AuditEvent)
        .where(
            AuditEvent.session_id == review_session.id,
            AuditEvent.event_type == "assignments.generated",
        )
    ).scalars().one()
    refs = (event.detail or {}).get("refs", {})
    assert refs.get("rule_set_id") == rule_set_id
    assert isinstance(refs.get("rule_set_revision_id"), int)
    assert refs["rule_set_revision_id"] > 0


def test_generate_without_confirm_replace_redirects_back_with_error(
    client: TestClient, db: Session
) -> None:
    """On a session that already has assignments, missing
    ``confirm_replace`` 303s back with
    ``?rule_based_error=needs_confirm`` and writes nothing."""

    review_session = _make_session(client, db, code="rb-confirm")
    _seed_population(client, review_session)

    rule_set_id = _full_matrix_seed_id(db)
    # First generate to populate.
    client.post(
        f"/operator/sessions/{review_session.id}/assignments/rule-based/generate",
        data={"rule_set_id": rule_set_id, "exclude_self_review": "true"},
        follow_redirects=False,
    )
    before = db.execute(
        select(Assignment).where(Assignment.session_id == review_session.id)
    ).scalars().all()
    assert len(before) == 4

    # Second generate without confirm_replace → bounce back.
    response = client.post(
        f"/operator/sessions/{review_session.id}/assignments/rule-based/generate",
        data={"rule_set_id": rule_set_id, "exclude_self_review": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].endswith(
        "/assignments?rule_based_error=needs_confirm"
    )

    after = db.execute(
        select(Assignment).where(Assignment.session_id == review_session.id)
    ).scalars().all()
    # Untouched.
    assert len(after) == len(before)


def test_generate_with_confirm_replace_replaces_existing(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rb-replace")
    _seed_population(client, review_session)

    full_matrix_id = _full_matrix_seed_id(db)
    intra_id = _intra_group_seed_id(db)

    # Populate 4 pairs via Full Matrix.
    client.post(
        f"/operator/sessions/{review_session.id}/assignments/rule-based/generate",
        data={"rule_set_id": full_matrix_id, "exclude_self_review": "true"},
        follow_redirects=False,
    )
    # Switch to Intra-group; should drop to 2 pairs.
    response = client.post(
        f"/operator/sessions/{review_session.id}/assignments/rule-based/generate",
        data={
            "rule_set_id": intra_id,
            "exclude_self_review": "true",
            "confirm_replace": "true",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    rows = db.execute(
        select(Assignment).where(Assignment.session_id == review_session.id)
    ).scalars().all()
    assert len(rows) == 2


def test_generate_rejects_unknown_rule_set_id(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rb-unknown")
    _seed_population(client, review_session)

    response = client.post(
        f"/operator/sessions/{review_session.id}/assignments/rule-based/generate",
        data={"rule_set_id": 999_999, "exclude_self_review": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].endswith(
        "/assignments?rule_based_error=missing_rule_set"
    )


def test_assignments_page_shows_last_generated_with_ruleset_name(
    client: TestClient, db: Session
) -> None:
    """After a successful Generate, the assignments page renders a
    `Last generated using <RuleSet name>: N pairs.` line that reads
    the name from ``refs.rule_set_id`` of the most recent
    ``assignments.generated`` audit row."""

    review_session = _make_session(client, db, code="rb-last")
    _seed_population(client, review_session)
    rule_set_id = _intra_group_seed_id(db)
    client.post(
        f"/operator/sessions/{review_session.id}/assignments/rule-based/generate",
        data={"rule_set_id": rule_set_id, "exclude_self_review": "true"},
        follow_redirects=False,
    )

    body = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
    ).text
    rb_section = body.split('id="rule-based-assignment"', 1)[1]
    rb_section = rb_section.split("</section>", 1)[0]
    assert "Last generated using" in rb_section
    assert "<strong>Intra-group peer review</strong>" in rb_section
    # Intra-group across the seed population (two reviewers in
    # different tag1 groups, two reviewees likewise) yields exactly
    # two intra-group pairs.
    assert "2 pairs" in rb_section
