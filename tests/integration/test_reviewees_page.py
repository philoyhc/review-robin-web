"""Reviewees Setup page — search/filter + selection-driven Edit +
Add new row + bulk inactivate / reactivate — Segment 15F PR 4.

Reviewee-side mirror of test_reviewers_page_filter +
test_reviewers_page_mutate, condensed into one file since PR 4 is
a single clone PR.
"""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Reviewee, ReviewSession


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
    if status != "draft":
        review_session.status = status
        db.commit()
    return review_session


def _seed(db: Session, session_id: int, names: list[str]) -> list[Reviewee]:
    rows = [
        Reviewee(
            session_id=session_id,
            name=name,
            email_or_identifier=f"{name.lower()}@example.edu",
        )
        for name in names
    ]
    db.add_all(rows)
    db.commit()
    return rows


# --------------------------------------------------------------------------- #
# Filter + cap.
# --------------------------------------------------------------------------- #


def test_plain_render_has_checkbox_column_and_buttons(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rve-plain")
    _seed(db, review_session.id, ["Alice", "Bob"])

    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewees"
    ).text
    assert 'class="reviewee-select"' in body
    assert 'id="reviewees-select-all"' in body
    assert 'id="reviewees-edit-btn"' in body
    assert "?add=1" in body
    assert "reviewee-edit-row" not in body


def test_status_filter_narrows_to_inactive(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rve-filter")
    rows = _seed(db, review_session.id, ["Alice", "Bob", "Carol"])
    rows[1].status = "inactive"
    db.commit()

    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewees?status=inactive"
    ).text
    table = body[body.find('id="reviewees-table"') :]
    assert "Bob" in table
    assert "Alice" not in table


def test_search_filter_substring_match(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rve-search")
    _seed(db, review_session.id, ["Alpha", "Beta"])

    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewees?q=alph"
    ).text
    table = body[body.find('id="reviewees-table"') :]
    assert "Alpha" in table
    assert "Beta" not in table


def test_unfiltered_cap_is_200(db: Session, client: TestClient) -> None:
    review_session = _make_session(client, db, code="rve-cap")
    for i in range(250):
        db.add(
            Reviewee(
                session_id=review_session.id,
                name=f"E{i:04d}",
                email_or_identifier=f"e{i:04d}@example.edu",
            )
        )
    db.commit()

    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewees"
    ).text
    table = body[body.find('id="reviewees-table"') :]
    assert "E0199" in table
    assert "E0200" not in table
    assert "Showing 200 of 250" in body


# --------------------------------------------------------------------------- #
# Edit / Add / bulk.
# --------------------------------------------------------------------------- #


def test_edit_id_renders_target_row_as_inputs(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rve-editget")
    rows = _seed(db, review_session.id, ["Alice", "Bob"])

    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewees"
        f"?edit_id={rows[0].id}"
    ).text
    assert "reviewee-edit-row" in body
    assert 'id="reviewee-edit-form"' in body
    assert ">Edit reviewee</h2>" in body
    assert 'name="email_or_identifier"' in body
    assert 'name="profile_link"' in body  # edit mode always shows it
    assert "operator-actions-main is-locked" in body


def test_edit_post_updates_row_and_redirects(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rve-editpost")
    rows = _seed(db, review_session.id, ["Alice"])

    response = client.post(
        f"/operator/sessions/{review_session.id}/reviewees/{rows[0].id}/update",
        data={
            "name": "Alice Renamed",
            "email_or_identifier": "alice@example.edu",
            "profile_link": "https://example.edu/a",
            "tag_1": "",
            "tag_2": "",
            "tag_3": "",
            "status": "inactive",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    db.expire_all()
    reviewee = db.execute(
        select(Reviewee).where(Reviewee.id == rows[0].id)
    ).scalar_one()
    assert reviewee.name == "Alice Renamed"
    assert reviewee.profile_link == "https://example.edu/a"
    assert reviewee.status == "inactive"


def test_edit_post_validation_error_rerenders(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rve-editerr")
    rows = _seed(db, review_session.id, ["Alice", "Bob"])

    response = client.post(
        f"/operator/sessions/{review_session.id}/reviewees/{rows[1].id}/update",
        data={
            "name": "Bob",
            "email_or_identifier": "alice@example.edu",
            "profile_link": "",
            "tag_1": "",
            "tag_2": "",
            "tag_3": "",
            "status": "active",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "reviewee-edit-row" in response.text
    assert "banner-error" in response.text


def test_add_renders_blank_edit_row(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rve-addget")
    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewees?add=1"
    ).text
    assert "reviewee-edit-row" in body
    assert ">Add new reviewee</h2>" in body


def test_add_post_creates_row(db: Session, client: TestClient) -> None:
    review_session = _make_session(client, db, code="rve-addpost")
    response = client.post(
        f"/operator/sessions/{review_session.id}/reviewees/create",
        data={
            "name": "Newbie",
            "email_or_identifier": "newbie-2026",
            "profile_link": "",
            "tag_1": "",
            "tag_2": "",
            "tag_3": "",
            "status": "active",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    reviewee = db.execute(
        select(Reviewee).where(Reviewee.session_id == review_session.id)
    ).scalar_one()
    assert reviewee.name == "Newbie"
    assert reviewee.email_or_identifier == "newbie-2026"


def test_add_post_validation_error_rerenders(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rve-adderr")
    response = client.post(
        f"/operator/sessions/{review_session.id}/reviewees/create",
        data={
            "name": "Bad",
            "email_or_identifier": "bad@",  # @ present → must be email
            "profile_link": "",
            "tag_1": "",
            "tag_2": "",
            "tag_3": "",
            "status": "active",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert ">Add new reviewee</h2>" in response.text
    assert "banner-error" in response.text
    assert (
        db.execute(
            select(Reviewee).where(
                Reviewee.session_id == review_session.id
            )
        ).first()
        is None
    )


def test_bulk_inactivate_flips_selected(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rve-bulk")
    rows = _seed(db, review_session.id, ["Alice", "Bob", "Carol"])

    response = client.post(
        f"/operator/sessions/{review_session.id}/reviewees/bulk-inactivate",
        data={"reviewee_ids": [rows[0].id, rows[2].id]},
        follow_redirects=False,
    )
    assert response.status_code == 303
    db.expire_all()
    statuses = {
        r.name: r.status
        for r in db.execute(
            select(Reviewee).where(
                Reviewee.session_id == review_session.id
            )
        ).scalars()
    }
    assert statuses == {
        "Alice": "inactive",
        "Bob": "active",
        "Carol": "inactive",
    }


def test_bulk_action_keeps_filter(
    db: Session, client: TestClient
) -> None:
    """The active search / status filter rides through a bulk
    action so the operator lands back on the same filtered view."""
    review_session = _make_session(client, db, code="rve-keepfilter")
    rows = _seed(db, review_session.id, ["Alice", "Bob"])

    response = client.post(
        f"/operator/sessions/{review_session.id}/reviewees/bulk-inactivate",
        data={
            "reviewee_ids": [rows[0].id],
            "filter_status": "active",
            "filter_q": "Ali",
        },
        follow_redirects=False,
    )
    loc = response.headers["location"]
    assert "status=active" in loc
    assert "q=Ali" in loc


def test_bulk_reactivate_flips_selected(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rve-bulk-react")
    rows = _seed(db, review_session.id, ["Alice"])
    rows[0].status = "inactive"
    db.commit()

    response = client.post(
        f"/operator/sessions/{review_session.id}/reviewees/bulk-reactivate",
        data={"reviewee_ids": [rows[0].id]},
        follow_redirects=False,
    )
    assert response.status_code == 303
    db.expire_all()
    assert (
        db.execute(
            select(Reviewee).where(Reviewee.id == rows[0].id)
        ).scalar_one().status
        == "active"
    )


# --------------------------------------------------------------------------- #
# Lifecycle gate.
# --------------------------------------------------------------------------- #


def test_edit_mode_suppressed_on_ready_session(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(
        client, db, code="rve-ready", status="ready"
    )
    rows = _seed(db, review_session.id, ["Alice"])

    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewees"
        f"?edit_id={rows[0].id}"
    ).text
    assert "reviewee-edit-row" not in body
    assert "card lock" in body


def test_create_on_ready_session_is_409(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(
        client, db, code="rve-ready-create", status="ready"
    )
    response = client.post(
        f"/operator/sessions/{review_session.id}/reviewees/create",
        data={
            "name": "X",
            "email_or_identifier": "x@example.edu",
            "status": "active",
        },
        follow_redirects=False,
    )
    assert response.status_code == 409
