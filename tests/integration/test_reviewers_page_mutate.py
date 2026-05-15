"""Reviewers Setup page — selection-driven Edit + Add new row +
bulk inactivate / reactivate — Segment 15F PR 3.

Pins the server-rendered edit state (``?edit_id=`` / ``?add=1``),
the create / update / bulk POST routes, validation-error
re-rendering, and the defensive ``invitations_send_one`` status
guard folded in from PR 6.
"""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Invitation, Reviewer, ReviewSession


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


def _seed(db: Session, session_id: int, names: list[str]) -> list[Reviewer]:
    rows = [
        Reviewer(
            session_id=session_id,
            name=name,
            email=f"{name.lower()}@example.edu",
        )
        for name in names
    ]
    db.add_all(rows)
    db.commit()
    return rows


# --------------------------------------------------------------------------- #
# Non-edit render — checkbox column + inert-by-default buttons.
# --------------------------------------------------------------------------- #


def test_plain_render_has_checkbox_column_and_action_buttons(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rev-m-plain")
    _seed(db, review_session.id, ["Alice", "Bob"])

    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
    ).text
    # Per-row select checkboxes + select-all.
    assert 'class="reviewer-select"' in body
    assert 'id="reviewers-select-all"' in body
    # Four action buttons; Edit/Inactivate/Reactivate start disabled.
    assert 'id="reviewers-edit-btn"' in body
    assert 'id="reviewers-inactivate-btn"' in body
    assert 'id="reviewers-reactivate-btn"' in body
    assert "?add=1" in body  # Add new row link
    # No per-row Actions column.
    assert "reviewer-edit-row" not in body


# --------------------------------------------------------------------------- #
# Edit — server-rendered edit state.
# --------------------------------------------------------------------------- #


def test_edit_id_renders_target_row_as_inputs(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rev-m-editget")
    rows = _seed(db, review_session.id, ["Alice", "Bob"])

    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
        f"?edit_id={rows[0].id}"
    ).text
    assert "reviewer-edit-row" in body
    assert 'id="reviewer-edit-form"' in body
    # Focused Edit card with Save + Cancel.
    assert ">Edit reviewer</h2>" in body
    assert ">Save</button>" in body
    assert ">Cancel</a>" in body
    # The edited row's name prefilled into an input.
    assert 'name="name"' in body
    assert 'value="Alice"' in body
    # The operator-actions card's filter + buttons grey out; the
    # Add / Edit form sits below the divider in the same card.
    assert "operator-actions-main is-locked" in body
    assert 'class="operator-actions-divider"' in body


def test_edit_post_updates_row_and_redirects(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rev-m-editpost")
    rows = _seed(db, review_session.id, ["Alice"])

    response = client.post(
        f"/operator/sessions/{review_session.id}/reviewers/{rows[0].id}/update",
        data={
            "name": "Alice Renamed",
            "email": "alice@example.edu",
            "tag_1": "Mentor",
            "tag_2": "",
            "tag_3": "",
            "status": "inactive",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    db.expire_all()
    reviewer = db.execute(
        select(Reviewer).where(Reviewer.id == rows[0].id)
    ).scalar_one()
    assert reviewer.name == "Alice Renamed"
    assert reviewer.tag_1 == "Mentor"
    assert reviewer.status == "inactive"


def test_edit_post_validation_error_rerenders_with_values(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rev-m-editerr")
    rows = _seed(db, review_session.id, ["Alice", "Bob"])

    # Rename Bob to Alice's email → duplicate-email rejection.
    response = client.post(
        f"/operator/sessions/{review_session.id}/reviewers/{rows[1].id}/update",
        data={
            "name": "Bob",
            "email": "alice@example.edu",
            "tag_1": "",
            "tag_2": "",
            "tag_3": "",
            "status": "active",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    # Re-rendered in edit mode with the error + the submitted email.
    assert "reviewer-edit-row" in response.text
    assert "banner-error" in response.text
    assert 'value="alice@example.edu"' in response.text
    # The DB row is untouched.
    db.expire_all()
    bob = db.execute(
        select(Reviewer).where(Reviewer.id == rows[1].id)
    ).scalar_one()
    assert bob.email == "bob@example.edu"


def test_edit_id_outside_cap_is_force_included(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rev-m-editcap")
    rows = _seed(
        db, review_session.id, [f"R{i:04d}" for i in range(250)]
    )
    # The 250th row is past the 200 unfiltered cap.
    target = rows[240]

    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
        f"?edit_id={target.id}"
    ).text
    assert "reviewer-edit-row" in body
    assert f'value="{target.name}"' in body


def test_edit_unknown_reviewer_id_falls_back_to_plain_list(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rev-m-editstale")
    _seed(db, review_session.id, ["Alice"])

    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers?edit_id=999999"
    ).text
    # Stale id → no edit row, plain list renders.
    assert "reviewer-edit-row" not in body
    assert 'class="reviewer-select"' in body


# --------------------------------------------------------------------------- #
# Add new row.
# --------------------------------------------------------------------------- #


def test_add_renders_blank_edit_row(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rev-m-addget")
    _seed(db, review_session.id, ["Alice"])

    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers?add=1"
    ).text
    assert "reviewer-edit-row" in body
    assert ">Add new reviewer</h2>" in body
    assert ">Save</button>" in body


def test_add_works_on_empty_roster(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rev-m-addempty")
    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers?add=1"
    ).text
    # The blank edit row renders even with zero existing reviewers.
    assert "reviewer-edit-row" in body


def test_add_post_creates_row_and_redirects(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rev-m-addpost")

    response = client.post(
        f"/operator/sessions/{review_session.id}/reviewers/create",
        data={
            "name": "Newbie",
            "email": "newbie@example.edu",
            "tag_1": "",
            "tag_2": "",
            "tag_3": "",
            "status": "active",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    reviewer = db.execute(
        select(Reviewer).where(
            Reviewer.session_id == review_session.id
        )
    ).scalar_one()
    assert reviewer.name == "Newbie"
    assert reviewer.email == "newbie@example.edu"


def test_add_post_validation_error_rerenders_in_add_mode(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rev-m-adderr")

    response = client.post(
        f"/operator/sessions/{review_session.id}/reviewers/create",
        data={
            "name": "Bad",
            "email": "not-an-email",
            "tag_1": "",
            "tag_2": "",
            "tag_3": "",
            "status": "active",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert ">Add new reviewer</h2>" in response.text
    assert "banner-error" in response.text
    # The bad value is preserved for correction.
    assert 'value="not-an-email"' in response.text
    # Nothing was persisted.
    assert (
        db.execute(
            select(Reviewer).where(
                Reviewer.session_id == review_session.id
            )
        ).first()
        is None
    )


# --------------------------------------------------------------------------- #
# Bulk inactivate / reactivate.
# --------------------------------------------------------------------------- #


def test_bulk_inactivate_flips_selected_rows(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rev-m-bulkinact")
    rows = _seed(db, review_session.id, ["Alice", "Bob", "Carol"])

    response = client.post(
        f"/operator/sessions/{review_session.id}/reviewers/bulk-inactivate",
        data={"reviewer_ids": [rows[0].id, rows[2].id]},
        follow_redirects=False,
    )
    assert response.status_code == 303
    db.expire_all()
    statuses = {
        r.name: r.status
        for r in db.execute(
            select(Reviewer).where(
                Reviewer.session_id == review_session.id
            )
        ).scalars()
    }
    assert statuses == {
        "Alice": "inactive",
        "Bob": "active",
        "Carol": "inactive",
    }


def test_bulk_action_keeps_selection(
    db: Session, client: TestClient
) -> None:
    """After a bulk action the redirect carries the acted-on ids
    so the operator clears the selection themselves."""
    review_session = _make_session(client, db, code="rev-m-keepsel")
    rows = _seed(db, review_session.id, ["Alice", "Bob", "Carol"])

    response = client.post(
        f"/operator/sessions/{review_session.id}/reviewers/bulk-inactivate",
        data={"reviewer_ids": [rows[0].id, rows[2].id]},
        follow_redirects=False,
    )
    loc = response.headers["location"]
    assert f"selected={rows[0].id}" in loc
    assert f"selected={rows[2].id}" in loc

    body = client.get(loc).text
    table = body[body.find('id="reviewers-table"') :]
    # The acted-on rows render their checkbox checked.
    for rid in (rows[0].id, rows[2].id):
        marker = f'value="{rid}"'
        cell = table[table.find(marker) - 160 : table.find(marker) + 160]
        assert "checked" in cell
    # The untouched row is not pre-checked.
    bob_marker = f'value="{rows[1].id}"'
    bob_cell = table[
        table.find(bob_marker) - 160 : table.find(bob_marker) + 160
    ]
    assert "checked" not in bob_cell


def test_bulk_reactivate_flips_selected_rows(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rev-m-bulkreact")
    rows = _seed(db, review_session.id, ["Alice", "Bob"])
    for r in rows:
        r.status = "inactive"
    db.commit()

    response = client.post(
        f"/operator/sessions/{review_session.id}/reviewers/bulk-reactivate",
        data={"reviewer_ids": [rows[0].id]},
        follow_redirects=False,
    )
    assert response.status_code == 303
    db.expire_all()
    statuses = {
        r.name: r.status
        for r in db.execute(
            select(Reviewer).where(
                Reviewer.session_id == review_session.id
            )
        ).scalars()
    }
    assert statuses == {"Alice": "active", "Bob": "inactive"}


def test_bulk_with_id_outside_session_is_rejected(
    db: Session, client: TestClient
) -> None:
    session_a = _make_session(client, db, code="rev-m-bulk-a")
    rows_a = _seed(db, session_a.id, ["Alice"])
    session_b = _make_session(client, db, code="rev-m-bulk-b")
    rows_b = _seed(db, session_b.id, ["Bob"])

    response = client.post(
        f"/operator/sessions/{session_a.id}/reviewers/bulk-inactivate",
        data={"reviewer_ids": [rows_a[0].id, rows_b[0].id]},
        follow_redirects=False,
    )
    assert response.status_code == 400


# --------------------------------------------------------------------------- #
# Lifecycle gate.
# --------------------------------------------------------------------------- #


def test_edit_mode_suppressed_on_ready_session(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(
        client, db, code="rev-m-ready", status="ready"
    )
    rows = _seed(db, review_session.id, ["Alice"])

    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
        f"?edit_id={rows[0].id}"
    ).text
    # Ready session → edit mode suppressed, lock card shown instead.
    assert "reviewer-edit-row" not in body
    assert "card lock" in body


def test_create_on_ready_session_is_409(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(
        client, db, code="rev-m-ready-create", status="ready"
    )
    response = client.post(
        f"/operator/sessions/{review_session.id}/reviewers/create",
        data={
            "name": "X",
            "email": "x@example.edu",
            "status": "active",
        },
        follow_redirects=False,
    )
    assert response.status_code == 409


# --------------------------------------------------------------------------- #
# PR 6 fold-in — defensive invitations_send_one status guard.
# --------------------------------------------------------------------------- #


def test_send_invitation_to_inactive_reviewer_is_409(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(
        client, db, code="rev-m-send-inactive", status="ready"
    )
    reviewer = Reviewer(
        session_id=review_session.id,
        name="Inactive",
        email="inactive@example.edu",
        status="inactive",
    )
    db.add(reviewer)
    db.flush()
    invitation = Invitation(
        session_id=review_session.id,
        reviewer_id=reviewer.id,
        token_hash="x" * 64,
        status="pending",
    )
    db.add(invitation)
    db.commit()

    response = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/invitations/{invitation.id}/send",
        follow_redirects=False,
    )
    assert response.status_code == 409
