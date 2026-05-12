"""Integration coverage for Segment 15D PR 4 — end-to-end
``pair_context.tag_N`` rules through the rule-based generate route.

Seeds a session with rosters and a Relationships table; saves a
Personal RuleSet whose rule consumes a pair_context tag; runs
``POST /assignments/rule-based/generate``; asserts the resulting
``Assignment`` rows match the expected pairs.
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    ReviewSession,
    Reviewee,
    Reviewer,
    RuleSet,
)


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "PCE2E", "code": code, "description": "d"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _seed_rosters(client: TestClient, session_id: int) -> None:
    client.post(
        f"/operator/sessions/{session_id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                (
                    b"ReviewerName,ReviewerEmail\n"
                    b"Alice,alice@example.edu\n"
                    b"Bob,bob@example.edu\n"
                ),
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{session_id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                (
                    b"RevieweeName,RevieweeEmail\n"
                    b"Carol,carol@example.edu\n"
                    b"Dan,dan@example.edu\n"
                ),
                "text/csv",
            )
        },
        follow_redirects=False,
    )


def _upload_relationships(
    client: TestClient, session_id: int, csv_body: bytes
) -> None:
    response = client.post(
        f"/operator/sessions/{session_id}/relationships/import",
        files={"file": ("rel.csv", csv_body, "text/csv")},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text


def _intra_seed_id(db: Session, session_id: int) -> int:
    """Post-15C-Slice-4b seeded RuleSets live in ``session_rule_sets``
    (the per-session copy table); the workspace seed materialises on
    session-create via 15C Slice 1."""
    from app.db.models import SessionRuleSet

    return db.execute(
        select(SessionRuleSet.id).where(
            SessionRuleSet.session_id == session_id,
            SessionRuleSet.name == "Intra-group peer review",
        )
    ).scalar_one()


def _save_pair_context_match_rule(
    client: TestClient,
    db: Session,
    session_id: int,
    *,
    name: str,
    tag_value: str,
) -> int:
    """Save-As a SessionRuleSet with one MATCH rule on
    ``pair_context.tag1 == tag_value``, then promote it to the
    operator library so the legacy ``/rule-based/generate`` endpoint
    (which still resolves rule ids against the library tier) can
    find it. Returns the **library** RuleSet id."""

    response = client.post(
        f"/operator/sessions/{session_id}/assignments/rule-based-editor/save",
        data={
            "source_rule_set_id": str(_intra_seed_id(db, session_id)),
            "name": name,
            "combinator": "ALL_OF",
            "rules_json": json.dumps([
                {
                    "id": "r1",
                    "kind": "MATCH",
                    "enabled": True,
                    "predicate": {
                        "field": "pair_context.tag1",
                        "operator": "equals",
                        "operand": tag_value,
                        "case_sensitive": False,
                    },
                }
            ]),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    from app.db.models import SessionRuleSet

    session_rule_set_id = db.execute(
        select(SessionRuleSet.id).where(
            SessionRuleSet.session_id == session_id,
            SessionRuleSet.name == name,
        )
    ).scalar_one()
    # Promote to operator library so /rule-based/generate finds it.
    promote_response = client.post(
        f"/operator/sessions/{session_id}/assignments/rule-based-editor/save-to-library",
        data={"rule_set_id": session_rule_set_id},
        follow_redirects=False,
    )
    assert promote_response.status_code == 303, promote_response.text
    library_row = db.execute(
        select(RuleSet).where(RuleSet.name == name)
    ).scalar_one()
    return library_row.id


def _pair_emails(db: Session, session_id: int) -> set[tuple[str, str]]:
    rows = db.execute(
        select(Assignment, Reviewer, Reviewee)
        .join(Reviewer, Assignment.reviewer_id == Reviewer.id)
        .join(Reviewee, Assignment.reviewee_id == Reviewee.id)
        .where(Assignment.session_id == session_id)
    ).all()
    # Multiple Assignment rows per (reviewer, reviewee) pair (one per
    # instrument) — collapse by pair.
    return {(r.email, e.email_or_identifier) for _a, r, e in rows}


def test_match_rule_on_pair_context_keeps_only_tagged_pairs(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="pc-match")
    _seed_rosters(client, review_session.id)
    _upload_relationships(
        client,
        review_session.id,
        (
            b"ReviewerEmail,RevieweeEmail,PairContextTag1\n"
            b"alice@example.edu,carol@example.edu,Mentor\n"
            b"bob@example.edu,dan@example.edu,COI\n"
        ),
    )
    rule_set_id = _save_pair_context_match_rule(
        client, db, review_session.id, name="match-mentor", tag_value="Mentor"
    )

    response = client.post(
        f"/operator/sessions/{review_session.id}/assignments/rule-based/generate",
        data={"rule_set_id": rule_set_id, "exclude_self_review": "false"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text

    pairs = _pair_emails(db, review_session.id)
    assert pairs == {("alice@example.edu", "carol@example.edu")}


def test_inactive_relationship_invisible_to_pair_context_rule(
    client: TestClient, db: Session
) -> None:
    """Skip-at-lookup: inactive rows hide their tag values from
    pair_context predicates. The pair stays in the candidate set
    but the predicate evaluates False."""

    review_session = _make_session(client, db, code="pc-inactive")
    _seed_rosters(client, review_session.id)
    _upload_relationships(
        client,
        review_session.id,
        (
            b"ReviewerEmail,RevieweeEmail,PairContextTag1,Status\n"
            b"alice@example.edu,carol@example.edu,Mentor,inactive\n"
        ),
    )
    rule_set_id = _save_pair_context_match_rule(
        client,
        db,
        review_session.id,
        name="inactive-mentor",
        tag_value="Mentor",
    )

    response = client.post(
        f"/operator/sessions/{review_session.id}/assignments/rule-based/generate",
        data={"rule_set_id": rule_set_id, "exclude_self_review": "false"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text

    # No assignments — the only pair with a Mentor tag had its
    # relationship row marked inactive.
    pairs = _pair_emails(db, review_session.id)
    assert pairs == set()


def test_no_relationship_row_means_no_tag_match(
    client: TestClient, db: Session
) -> None:
    """Pairs without a relationships row have no pair_context value;
    a MATCH on pair_context.tag1 leaves them out."""

    review_session = _make_session(client, db, code="pc-empty")
    _seed_rosters(client, review_session.id)
    # Note: no relationships uploaded.

    rule_set_id = _save_pair_context_match_rule(
        client, db, review_session.id, name="empty-rel", tag_value="Mentor"
    )

    response = client.post(
        f"/operator/sessions/{review_session.id}/assignments/rule-based/generate",
        data={"rule_set_id": rule_set_id, "exclude_self_review": "false"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    pairs = _pair_emails(db, review_session.id)
    assert pairs == set()


def test_filter_rule_drops_only_matching_pairs(
    client: TestClient, db: Session
) -> None:
    """A FILTER rule on pair_context.tag1 == 'COI' drops the
    tagged pair; non-tagged pairs survive."""

    review_session = _make_session(client, db, code="pc-filter")
    _seed_rosters(client, review_session.id)
    _upload_relationships(
        client,
        review_session.id,
        (
            b"ReviewerEmail,RevieweeEmail,PairContextTag1\n"
            b"alice@example.edu,carol@example.edu,COI\n"
        ),
    )

    from app.db.models import SessionRuleSet

    response = client.post(
        f"/operator/sessions/{review_session.id}/assignments/rule-based-editor/save",
        data={
            "source_rule_set_id": str(_intra_seed_id(db, review_session.id)),
            "name": "filter-coi",
            "combinator": "ALL_OF",
            "rules_json": json.dumps([
                {
                    "id": "r1",
                    "kind": "FILTER",
                    "enabled": True,
                    "predicate": {
                        "field": "pair_context.tag1",
                        "operator": "equals",
                        "operand": "COI",
                        "case_sensitive": False,
                    },
                }
            ]),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    # Promote the session-tier row to the library so /rule-based/generate
    # (still library-tier) can resolve it.
    session_rule_set_id = db.execute(
        select(SessionRuleSet.id).where(
            SessionRuleSet.session_id == review_session.id,
            SessionRuleSet.name == "filter-coi",
        )
    ).scalar_one()
    promote_response = client.post(
        f"/operator/sessions/{review_session.id}/assignments/rule-based-editor/save-to-library",
        data={"rule_set_id": session_rule_set_id},
        follow_redirects=False,
    )
    assert promote_response.status_code == 303, promote_response.text
    rule_set_id = db.execute(
        select(RuleSet.id).where(RuleSet.name == "filter-coi")
    ).scalar_one()

    response = client.post(
        f"/operator/sessions/{review_session.id}/assignments/rule-based/generate",
        data={"rule_set_id": rule_set_id, "exclude_self_review": "false"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    pairs = _pair_emails(db, review_session.id)
    # The COI pair is dropped; the other three remain.
    assert ("alice@example.edu", "carol@example.edu") not in pairs
    assert pairs == {
        ("alice@example.edu", "dan@example.edu"),
        ("bob@example.edu", "carol@example.edu"),
        ("bob@example.edu", "dan@example.edu"),
    }
