"""Relationships Setup page — per-row Edit + bulk inactivate /
reactivate — Segment 15F PR 5 stage 2.

Pins the service mutators (`update_relationship` /
`bulk_inactivate` / `bulk_reactivate`), the routes, the
server-rendered edit state + reviewer / reviewee search-box
pickers, and the name-display table reshape. Add a new row is
stage 3.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AuditEvent,
    Relationship,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from app.services import relationships as relationships_service
from app.services.relationships import RelationshipOperationError


def _make_session(
    client: TestClient, db: Session, *, code: str, status: str = "draft"
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Spring", "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    review_session.relationships_enabled = True
    db.commit()
    if status != "draft":
        review_session.status = status
        db.commit()
    return review_session


def _seed(
    db: Session,
    session_id: int,
    *,
    reviewers: list[str],
    reviewees: list[str],
    pairs: list[tuple[int, int]],
) -> tuple[list[Reviewer], list[Reviewee], list[Relationship]]:
    rv = [
        Reviewer(
            session_id=session_id,
            name=name,
            email=f"{name.lower()}@example.edu",
        )
        for name in reviewers
    ]
    re_ = [
        Reviewee(
            session_id=session_id,
            name=name,
            email_or_identifier=f"{name.lower()}@example.edu",
        )
        for name in reviewees
    ]
    db.add_all(rv + re_)
    db.flush()
    rels = [
        Relationship(
            session_id=session_id,
            reviewer_id=rv[i].id,
            reviewee_id=re_[j].id,
        )
        for i, j in pairs
    ]
    db.add_all(rels)
    db.commit()
    return rv, re_, rels


def _operator(db: Session) -> User:
    return db.execute(select(User)).scalars().first()


# --------------------------------------------------------------------------- #
# Service — update_relationship.
# --------------------------------------------------------------------------- #


def test_update_repoints_reviewer_and_emits_changes(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rel-m-svc-upd")
    rv, re_, rels = _seed(
        db,
        review_session.id,
        reviewers=["Ali", "Peter"],
        reviewees=["Jane"],
        pairs=[(1, 0)],  # Jane ↔ Peter
    )
    changes = relationships_service.update_relationship(
        db,
        relationship=rels[0],
        reviewer_id=rv[0].id,  # re-point to Ali
        user=_operator(db),
    )
    assert changes == {"reviewer_id": [rv[1].id, rv[0].id]}
    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "relationship.updated"
        )
    ).scalar_one()
    assert event.detail["refs"]["relationship_id"] == rels[0].id


def test_update_rejects_duplicate_pair(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rel-m-svc-dup")
    rv, re_, rels = _seed(
        db,
        review_session.id,
        reviewers=["Ali", "Peter"],
        reviewees=["Jane"],
        pairs=[(0, 0), (1, 0)],  # Jane↔Ali, Jane↔Peter
    )
    # Re-point the Jane↔Peter row to Ali → collides with Jane↔Ali.
    with pytest.raises(RelationshipOperationError) as exc_info:
        relationships_service.update_relationship(
            db,
            relationship=rels[1],
            reviewer_id=rv[0].id,
            user=_operator(db),
        )
    assert exc_info.value.code == "duplicate_pair"


def test_update_rejects_reviewer_outside_session(
    db: Session, client: TestClient
) -> None:
    session_a = _make_session(client, db, code="rel-m-svc-xs-a")
    rv_a, re_a, rels_a = _seed(
        db,
        session_a.id,
        reviewers=["Ali"],
        reviewees=["Jane"],
        pairs=[(0, 0)],
    )
    session_b = _make_session(client, db, code="rel-m-svc-xs-b")
    rv_b, _, _ = _seed(
        db,
        session_b.id,
        reviewers=["Outsider"],
        reviewees=["Bob"],
        pairs=[(0, 0)],
    )
    with pytest.raises(RelationshipOperationError) as exc_info:
        relationships_service.update_relationship(
            db,
            relationship=rels_a[0],
            reviewer_id=rv_b[0].id,
            user=_operator(db),
        )
    assert exc_info.value.code == "not_in_session"


def test_bulk_inactivate_and_reactivate(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rel-m-svc-bulk")
    _rv, _re, rels = _seed(
        db,
        review_session.id,
        reviewers=["Ali"],
        reviewees=["Jane", "Bob", "Carol"],
        pairs=[(0, 0), (0, 1), (0, 2)],
    )
    user = _operator(db)
    flipped = relationships_service.bulk_inactivate(
        db,
        review_session=review_session,
        relationship_ids=[rels[0].id, rels[2].id],
        user=user,
    )
    assert sorted(flipped) == sorted([rels[0].id, rels[2].id])
    db.expire_all()
    assert {r.id: r.status for r in rels} == {
        rels[0].id: "inactive",
        rels[1].id: "active",
        rels[2].id: "inactive",
    }

    relationships_service.bulk_reactivate(
        db,
        review_session=review_session,
        relationship_ids=[rels[0].id],
        user=user,
    )
    db.expire_all()
    assert db.execute(
        select(Relationship).where(Relationship.id == rels[0].id)
    ).scalar_one().status == "active"


# --------------------------------------------------------------------------- #
# Page — render shape.
# --------------------------------------------------------------------------- #


def test_plain_render_has_checkbox_column_and_name_display(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rel-m-plain")
    _seed(
        db,
        review_session.id,
        reviewers=["Ali Khan"],
        reviewees=["Jane Doe"],
        pairs=[(0, 0)],
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/relationships"
    ).text
    table = body[body.find('id="relationships-table"') :]
    # Checkbox column + selection-driven Edit button.
    assert 'class="relationship-select"' in table
    assert 'id="relationships-edit-btn"' in body
    # Name shown stacked above the email.
    assert "Ali Khan" in table
    assert "<code>ali khan@example.edu</code>" in table
    assert "Jane Doe" in table
    assert "reviewer-edit-row" not in table


def test_edit_id_renders_pickers(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rel-m-editget")
    _rv, _re, rels = _seed(
        db,
        review_session.id,
        reviewers=["Ali", "Peter"],
        reviewees=["Jane"],
        pairs=[(0, 0)],
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/relationships"
        f"?edit_id={rels[0].id}"
    ).text
    assert "relationship-edit-row" in body
    assert 'id="relationship-edit-form"' in body
    assert ">Edit relationship</h2>" in body
    # Reviewer / reviewee search-box pickers backed by a datalist,
    # both roster members listed as datalist options.
    assert 'name="reviewer_pick"' in body
    assert 'name="reviewee_pick"' in body
    assert 'id="relationship-reviewer-options"' in body
    assert "Ali (ali@example.edu)" in body
    assert "Peter (peter@example.edu)" in body
    assert "operator-actions-main is-locked" in body


def test_picker_marks_inactive_members(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rel-m-inactopt")
    rv, _re, rels = _seed(
        db,
        review_session.id,
        reviewers=["Ali", "Peter"],
        reviewees=["Jane"],
        pairs=[(0, 0)],
    )
    rv[1].status = "inactive"
    db.commit()

    body = client.get(
        f"/operator/sessions/{review_session.id}/relationships"
        f"?edit_id={rels[0].id}"
    ).text
    assert "Peter (peter@example.edu) — inactive" in body
    assert "Ali (ali@example.edu) — inactive" not in body


def test_edit_post_updates_and_redirects(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rel-m-editpost")
    rv, _re, rels = _seed(
        db,
        review_session.id,
        reviewers=["Ali", "Peter"],
        reviewees=["Jane"],
        pairs=[(1, 0)],
    )
    response = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/relationships/{rels[0].id}/update",
        data={
            "reviewer_pick": "Ali (ali@example.edu)",
            "reviewee_pick": "Jane (jane@example.edu)",
            "tag_1": "Supervisor",
            "tag_2": "",
            "tag_3": "",
            "status": "inactive",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    db.expire_all()
    row = db.execute(
        select(Relationship).where(Relationship.id == rels[0].id)
    ).scalar_one()
    assert row.reviewer_id == rv[0].id
    assert row.tag_1 == "Supervisor"
    assert row.status == "inactive"


def test_edit_post_duplicate_pair_rerenders_400(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rel-m-editdup")
    _rv, _re, rels = _seed(
        db,
        review_session.id,
        reviewers=["Ali", "Peter"],
        reviewees=["Jane"],
        pairs=[(0, 0), (1, 0)],
    )
    response = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/relationships/{rels[1].id}/update",
        data={
            # Ali (ali@example.edu) collides with rels[0].
            "reviewer_pick": "Ali (ali@example.edu)",
            "reviewee_pick": "Jane (jane@example.edu)",
            "tag_1": "",
            "tag_2": "",
            "tag_3": "",
            "status": "active",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "relationship-edit-row" in response.text
    assert "banner-error" in response.text


def test_edit_post_unresolvable_pick_rerenders_400(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rel-m-editbadpick")
    _rv, _re, rels = _seed(
        db,
        review_session.id,
        reviewers=["Ali"],
        reviewees=["Jane"],
        pairs=[(0, 0)],
    )
    response = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/relationships/{rels[0].id}/update",
        data={
            "reviewer_pick": "Nobody In Particular",
            "reviewee_pick": "Jane (jane@example.edu)",
            "status": "active",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "relationship-edit-row" in response.text
    assert "banner-error" in response.text
    # The operator's typed text survives the re-render.
    assert "Nobody In Particular" in response.text


def test_bulk_inactivate_route(db: Session, client: TestClient) -> None:
    review_session = _make_session(client, db, code="rel-m-bulkroute")
    _rv, _re, rels = _seed(
        db,
        review_session.id,
        reviewers=["Ali"],
        reviewees=["Jane", "Bob"],
        pairs=[(0, 0), (0, 1)],
    )
    response = client.post(
        f"/operator/sessions/{review_session.id}"
        "/relationships/bulk-inactivate",
        data={"relationship_ids": [rels[0].id]},
        follow_redirects=False,
    )
    assert response.status_code == 303
    db.expire_all()
    assert db.execute(
        select(Relationship).where(Relationship.id == rels[0].id)
    ).scalar_one().status == "inactive"


def test_bulk_action_keeps_filter(
    db: Session, client: TestClient
) -> None:
    """The active search filter rides through a bulk action so the
    operator lands back on the same filtered view."""
    review_session = _make_session(client, db, code="rel-m-keepfilter")
    _rv, _re, rels = _seed(
        db,
        review_session.id,
        reviewers=["Ali"],
        reviewees=["Jane", "Bob"],
        pairs=[(0, 0), (0, 1)],
    )
    response = client.post(
        f"/operator/sessions/{review_session.id}"
        "/relationships/bulk-inactivate",
        data={
            "relationship_ids": [rels[0].id],
            "filter_search_by": "reviewee",
            "filter_q": "Jane",
        },
        follow_redirects=False,
    )
    loc = response.headers["location"]
    assert "search_by=reviewee" in loc
    assert "q=Jane" in loc


def test_edit_mode_suppressed_on_ready_session(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(
        client, db, code="rel-m-ready", status="ready"
    )
    _rv, _re, rels = _seed(
        db,
        review_session.id,
        reviewers=["Ali"],
        reviewees=["Jane"],
        pairs=[(0, 0)],
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/relationships"
        f"?edit_id={rels[0].id}"
    ).text
    assert "relationship-edit-row" not in body
    assert "card lock" in body


def test_update_on_ready_session_is_409(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(
        client, db, code="rel-m-ready-upd", status="ready"
    )
    _rv, _re, rels = _seed(
        db,
        review_session.id,
        reviewers=["Ali"],
        reviewees=["Jane"],
        pairs=[(0, 0)],
    )
    response = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/relationships/{rels[0].id}/update",
        data={
            "reviewer_pick": "Ali (ali@example.edu)",
            "reviewee_pick": "Jane (jane@example.edu)",
            "status": "active",
        },
        follow_redirects=False,
    )
    assert response.status_code == 409


# --------------------------------------------------------------------------- #
# Add a new row — Segment 15F PR 5 stage 3.
# --------------------------------------------------------------------------- #


def test_create_relationship_service(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rel-m-svc-create")
    rv, re_, _rels = _seed(
        db,
        review_session.id,
        reviewers=["Ali"],
        reviewees=["Jane"],
        pairs=[],
    )
    rel = relationships_service.create_relationship(
        db,
        review_session=review_session,
        reviewer_id=rv[0].id,
        reviewee_id=re_[0].id,
        tag_1="Supervisor",
        user=_operator(db),
    )
    assert rel.id is not None
    assert rel.tag_1 == "Supervisor"
    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "relationship.created"
        )
    ).scalar_one()
    assert event.detail["snapshot"]["reviewer_id"] == rv[0].id


def test_create_service_rejects_duplicate_pair(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rel-m-svc-cdup")
    rv, re_, _rels = _seed(
        db,
        review_session.id,
        reviewers=["Ali"],
        reviewees=["Jane"],
        pairs=[(0, 0)],
    )
    with pytest.raises(RelationshipOperationError) as exc_info:
        relationships_service.create_relationship(
            db,
            review_session=review_session,
            reviewer_id=rv[0].id,
            reviewee_id=re_[0].id,
            user=_operator(db),
        )
    assert exc_info.value.code == "duplicate_pair"


def test_add_renders_blank_picker_row(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rel-m-addget")
    _seed(
        db,
        review_session.id,
        reviewers=["Ali"],
        reviewees=["Jane"],
        pairs=[],
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/relationships?add=1"
    ).text
    assert "relationship-edit-row" in body
    assert ">Add new relationship</h2>" in body
    assert 'name="reviewer_pick"' in body
    assert 'name="reviewee_pick"' in body
    assert 'id="relationship-reviewer-options"' in body
    assert "operator-actions-main is-locked" in body


def test_add_post_creates_and_redirects(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rel-m-addpost")
    _seed(
        db,
        review_session.id,
        reviewers=["Ali"],
        reviewees=["Jane"],
        pairs=[],
    )
    response = client.post(
        f"/operator/sessions/{review_session.id}/relationships/create",
        data={
            "reviewer_pick": "Ali (ali@example.edu)",
            "reviewee_pick": "Jane (jane@example.edu)",
            "tag_1": "Supervisor",
            "tag_2": "",
            "tag_3": "",
            "status": "active",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    row = db.execute(
        select(Relationship).where(
            Relationship.session_id == review_session.id
        )
    ).scalar_one()
    assert row.tag_1 == "Supervisor"


def test_add_post_duplicate_pair_rerenders_400(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rel-m-adddup")
    _seed(
        db,
        review_session.id,
        reviewers=["Ali"],
        reviewees=["Jane"],
        pairs=[(0, 0)],
    )
    response = client.post(
        f"/operator/sessions/{review_session.id}/relationships/create",
        data={
            "reviewer_pick": "Ali (ali@example.edu)",
            "reviewee_pick": "Jane (jane@example.edu)",
            "status": "active",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "relationship-edit-row" in response.text
    assert "banner-error" in response.text
    assert ">Add new relationship</h2>" in response.text


def test_add_post_unresolvable_pick_rerenders_400(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rel-m-addbadpick")
    _seed(
        db,
        review_session.id,
        reviewers=["Ali"],
        reviewees=["Jane"],
        pairs=[],
    )
    response = client.post(
        f"/operator/sessions/{review_session.id}/relationships/create",
        data={
            "reviewer_pick": "Ali (ali@example.edu)",
            "reviewee_pick": "Nobody In Particular",
            "status": "active",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "banner-error" in response.text
    assert "Nobody In Particular" in response.text


def test_add_disabled_when_a_roster_is_empty(
    db: Session, client: TestClient
) -> None:
    """A relationship needs both sides — Add is disabled with a hint
    when either roster is empty."""
    review_session = _make_session(client, db, code="rel-m-addempty")
    _seed(
        db,
        review_session.id,
        reviewers=["Ali"],
        reviewees=[],
        pairs=[],
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/relationships"
    ).text
    assert "Add a reviewer and a reviewee first" in body


def test_create_on_ready_session_is_409(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(
        client, db, code="rel-m-ready-create", status="ready"
    )
    _seed(
        db,
        review_session.id,
        reviewers=["Ali"],
        reviewees=["Jane"],
        pairs=[],
    )
    response = client.post(
        f"/operator/sessions/{review_session.id}/relationships/create",
        data={
            "reviewer_pick": "Ali (ali@example.edu)",
            "reviewee_pick": "Jane (jane@example.edu)",
            "status": "active",
        },
        follow_redirects=False,
    )
    assert response.status_code == 409
