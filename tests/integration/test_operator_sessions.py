from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import (
    AuditEvent,
    ReviewSession,
    SessionOperator,
    SessionTag,
    User,
)


def test_create_redirects_to_detail(client: TestClient, db: Session) -> None:
    response = client.post(
        "/operator/sessions",
        data={"name": "Spring Reviews", "code": "spring-2026"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "spring-2026")
    ).scalar_one()
    assert response.headers["location"] == f"/operator/sessions/{review_session.id}"


def test_create_inserts_session_operator_row(client: TestClient, db: Session) -> None:
    client.post(
        "/operator/sessions",
        data={"name": "Spring Reviews", "code": "spring-2026"},
        follow_redirects=False,
    )

    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "spring-2026")
    ).scalar_one()
    user = db.execute(
        select(User).where(User.email == "alice@example.edu")
    ).scalar_one()
    operator = db.execute(
        select(SessionOperator).where(
            SessionOperator.session_id == review_session.id,
            SessionOperator.user_id == user.id,
        )
    ).scalar_one()
    assert operator.role == "owner"


def test_create_writes_session_created_audit_event(
    client: TestClient, db: Session
) -> None:
    client.post(
        "/operator/sessions",
        data={"name": "Spring Reviews", "code": "spring-2026"},
        follow_redirects=False,
    )

    event = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "session.created")
    ).scalar_one()
    assert event.summary == "Session spring-2026 created"
    assert event.detail is not None
    assert event.detail["session_code"] == "spring-2026"
    assert event.detail["snapshot"]["code"] == "spring-2026"
    assert event.correlation_id is not None
    assert event.actor_user_id is not None


def test_list_shows_users_session(client: TestClient) -> None:
    client.post(
        "/operator/sessions",
        data={"name": "Spring Reviews", "code": "spring-2026"},
        follow_redirects=False,
    )

    response = client.get("/operator/sessions")
    assert response.status_code == 200
    body = response.text
    assert "Spring Reviews" in body
    assert "spring-2026" in body


def test_detail_renders_for_operator(client: TestClient, db: Session) -> None:
    client.post(
        "/operator/sessions",
        data={"name": "Spring Reviews", "code": "spring-2026"},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "spring-2026")
    ).scalar_one()

    response = client.get(f"/operator/sessions/{review_session.id}")
    assert response.status_code == 200
    assert "Spring Reviews" in response.text


def test_non_operator_cannot_view_other_session(
    db: Session,
    alice: AuthenticatedUser,
    bob: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    alice_client = make_client(alice)
    alice_client.post(
        "/operator/sessions",
        data={"name": "Alice's Session", "code": "alice-only"},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "alice-only")
    ).scalar_one()

    bob_client = make_client(bob)
    response = bob_client.get(f"/operator/sessions/{review_session.id}")

    assert response.status_code == 403


def test_create_missing_name_returns_422(client: TestClient) -> None:
    response = client.post(
        "/operator/sessions",
        data={"code": "spring-2026"},
        follow_redirects=False,
    )
    assert response.status_code == 422


def test_list_empty_state_renders_for_new_user(client: TestClient) -> None:
    response = client.get("/operator/sessions")
    assert response.status_code == 200
    body = response.text
    assert "don't have any sessions yet" in body or "no sessions" in body.lower()


def test_delete_session_with_email_outbox_rows_succeeds(
    client: TestClient, db: Session
) -> None:
    """Regression: deleting a session that has ``email_outbox`` rows
    pointing at its invitations must not trip a FOREIGN KEY constraint
    failure. Before the fix, ``ReviewSession.invitations`` cascade-
    deleted invitation rows but the ``email_outbox.invitation_id`` FK
    held them in place, raising ``sqlalchemy.exc.IntegrityError`` when
    the unit-of-work flushed the deletes."""

    from app.db.models import EmailOutbox, Invitation, Reviewer

    client.post(
        "/operator/sessions",
        data={"name": "DeleteMe", "code": "del-outbox"},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "del-outbox")
    ).scalar_one()

    # Seed a reviewer + invitation + outbox row tied to all three.
    reviewer = Reviewer(
        session_id=review_session.id,
        name="Reviewer One",
        email="r1@example.edu",
    )
    db.add(reviewer)
    db.flush()
    invitation = Invitation(
        session_id=review_session.id,
        reviewer_id=reviewer.id,
        token_hash="hash-del-outbox",
    )
    db.add(invitation)
    db.flush()
    outbox = EmailOutbox(
        session_id=review_session.id,
        reviewer_id=reviewer.id,
        invitation_id=invitation.id,
        kind="invitation",
        to_email="r1@example.edu",
        subject="Invite",
        body="…",
    )
    db.add(outbox)
    db.commit()

    response = client.post(
        f"/operator/sessions/{review_session.id}/delete",
        data={"confirm": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text

    # All session-scoped rows are gone.
    assert db.execute(
        select(ReviewSession).where(ReviewSession.id == review_session.id)
    ).scalar_one_or_none() is None
    assert db.execute(
        select(Invitation).where(Invitation.id == invitation.id)
    ).scalar_one_or_none() is None
    assert db.execute(
        select(EmailOutbox).where(EmailOutbox.id == outbox.id)
    ).scalar_one_or_none() is None


# ---------------------------------------------------------------------------
# Bulk delete via the Danger Zone card on /operator/sessions
# ---------------------------------------------------------------------------


def test_sessions_list_renders_danger_zone_with_delete_form(
    client: TestClient,
) -> None:
    """When at least one session exists, the sessions list renders a
    Danger Zone card in the bottom-right with a confirm checkbox and a
    submit button posting to /operator/sessions/delete-selected."""

    client.post(
        "/operator/sessions",
        data={"name": "Spring Reviews", "code": "spring-2026"},
        follow_redirects=False,
    )

    body = client.get("/operator/sessions").text
    assert 'id="sessions-list-danger-zone"' in body
    assert 'action="/operator/sessions/delete-selected"' in body
    assert 'name="session_ids"' in body
    assert 'name="confirm"' in body
    assert "Delete selected sessions" in body


def test_sessions_list_renders_select_all_header_checkbox(
    client: TestClient,
) -> None:
    """The select-row column carries a select-all checkbox in its
    header — it toggles every row checkbox client-side."""
    client.post(
        "/operator/sessions",
        data={"name": "Spring Reviews", "code": "spring-2026"},
        follow_redirects=False,
    )

    body = client.get("/operator/sessions").text
    assert 'class="sessions-list-select-all"' in body


def test_sessions_list_renders_inline_expander_fragments(
    client: TestClient,
) -> None:
    """The lobby ships the two inline row-expander <template>
    fragments — a single-session and a bulk variant — that the
    selection-aware script clones and injects below the table rows."""
    client.post(
        "/operator/sessions",
        data={"name": "Spring Reviews", "code": "spring-2026"},
        follow_redirects=False,
    )

    body = client.get("/operator/sessions").text
    assert 'id="single-session-expander"' in body
    assert 'id="bulk-expander"' in body
    # Single-session expander hosts the per-session action placeholders
    # plus the Name / Code / Deadline / Tags edit boxes.
    assert 'data-expander-field="name"' in body
    assert 'data-expander-field="code"' in body
    assert 'data-expander-field="deadline"' in body
    assert 'data-expander-field="tags"' in body
    # Bulk expander hosts a Tags box + the bulk actions, Cancel, and
    # the selection-management buttons.
    assert 'data-expander-field="bulk-tags"' in body
    assert "data-expander-cancel" in body
    assert "data-expander-clear-all" in body
    assert "data-expander-clear-others" in body


def test_lobby_renders_real_session_tags(
    client: TestClient, db: Session
) -> None:
    """The Tags column renders each session's real tags, and the
    filter strip lists the operator's tag vocabulary."""
    client.post(
        "/operator/sessions",
        data={"name": "Tagged", "code": "tagged-1"},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "tagged-1")
    ).scalar_one()
    db.add(SessionTag(session_id=review_session.id, tag="pilot"))
    db.add(SessionTag(session_id=review_session.id, tag="cohort-a"))
    db.commit()

    body = client.get("/operator/sessions").text
    assert '<span class="pill pill-count">pilot</span>' in body
    assert '<span class="pill pill-count">cohort-a</span>' in body
    assert "Show sessions tagged with:" in body
    # No placeholder literals survive.
    assert "HSH1000" not in body


def test_lobby_tag_filter_strip_is_interactive(
    client: TestClient, db: Session
) -> None:
    """The tag-filter strip ships clickable chips, an AND/OR mode
    chip, and a clear chip; each row carries its tag set for the
    client-side filter."""
    client.post(
        "/operator/sessions",
        data={"name": "Filterable", "code": "filter-1"},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "filter-1")
    ).scalar_one()
    db.add(SessionTag(session_id=review_session.id, tag="pilot"))
    db.commit()

    body = client.get("/operator/sessions").text
    assert 'data-tag-chip="pilot"' in body
    assert "data-tag-mode" in body
    assert "data-tag-clear" in body
    assert "data-tags=" in body
    assert 'class="sessions-no-match"' in body


def test_lobby_search_box_is_wired(client: TestClient) -> None:
    """The Search card ships a live search box and a Cancel hook; the
    retired Apply button is gone."""
    client.post(
        "/operator/sessions",
        data={"name": "Searchable", "code": "search-1"},
        follow_redirects=False,
    )

    body = client.get("/operator/sessions").text
    assert 'class="sessions-search-input"' in body
    assert "data-search-cancel" in body
    assert ">Apply<" not in body


def test_lobby_renders_no_tags_state(client: TestClient) -> None:
    """A session with no tags shows a muted 'No tags', and the filter
    strip is hidden when the operator has no tags at all."""
    client.post(
        "/operator/sessions",
        data={"name": "Bare", "code": "bare-1"},
        follow_redirects=False,
    )

    body = client.get("/operator/sessions").text
    assert "No tags" in body
    assert "Show sessions tagged with:" not in body


def test_delete_selected_removes_ticked_drafts(
    client: TestClient, db: Session
) -> None:
    client.post(
        "/operator/sessions",
        data={"name": "Keep", "code": "keep-1"},
        follow_redirects=False,
    )
    client.post(
        "/operator/sessions",
        data={"name": "Bin", "code": "bin-1"},
        follow_redirects=False,
    )
    keep = db.execute(
        select(ReviewSession).where(ReviewSession.code == "keep-1")
    ).scalar_one()
    bin_ = db.execute(
        select(ReviewSession).where(ReviewSession.code == "bin-1")
    ).scalar_one()

    response = client.post(
        "/operator/sessions/delete-selected",
        data={"session_ids": [bin_.id], "confirm": "true"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers.get("location") == "/operator/sessions"
    assert db.execute(
        select(ReviewSession).where(ReviewSession.id == bin_.id)
    ).scalar_one_or_none() is None
    assert db.execute(
        select(ReviewSession).where(ReviewSession.id == keep.id)
    ).scalar_one_or_none() is not None


def test_delete_selected_without_confirm_returns_400(
    client: TestClient, db: Session
) -> None:
    client.post(
        "/operator/sessions",
        data={"name": "NoConfirm", "code": "noconf-1"},
        follow_redirects=False,
    )
    target = db.execute(
        select(ReviewSession).where(ReviewSession.code == "noconf-1")
    ).scalar_one()

    response = client.post(
        "/operator/sessions/delete-selected",
        data={"session_ids": [target.id]},  # no confirm flag
        follow_redirects=False,
    )

    assert response.status_code == 400
    # Session is still in place.
    assert db.execute(
        select(ReviewSession).where(ReviewSession.id == target.id)
    ).scalar_one_or_none() is not None


def test_delete_selected_with_no_ids_is_a_clean_redirect(
    client: TestClient,
) -> None:
    """Submitting the form with zero ticked rows is a no-op redirect
    back to the list. No 4xx — the operator just gets the page back."""

    response = client.post(
        "/operator/sessions/delete-selected",
        data={"confirm": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers.get("location") == "/operator/sessions"


def test_delete_selected_skips_other_users_sessions(
    db: Session,
    alice: AuthenticatedUser,
    bob: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """A crafted POST that includes an id the caller doesn't operate
    is silently skipped — get_for_user returns None for non-operators
    and the loop continues."""

    alice_client = make_client(alice)
    alice_client.post(
        "/operator/sessions",
        data={"name": "Alice's", "code": "alice-private"},
        follow_redirects=False,
    )
    alice_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "alice-private")
    ).scalar_one()

    bob_client = make_client(bob)
    bob_client.post(
        "/operator/sessions",
        data={"name": "Bob's", "code": "bob-self"},
        follow_redirects=False,
    )
    bob_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "bob-self")
    ).scalar_one()

    # Bob crafts a POST with both his own id + Alice's id. His own
    # gets deleted; Alice's stays.
    response = bob_client.post(
        "/operator/sessions/delete-selected",
        data={
            "session_ids": [bob_session.id, alice_session.id],
            "confirm": "true",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    assert db.execute(
        select(ReviewSession).where(ReviewSession.id == bob_session.id)
    ).scalar_one_or_none() is None
    assert db.execute(
        select(ReviewSession).where(ReviewSession.id == alice_session.id)
    ).scalar_one_or_none() is not None
