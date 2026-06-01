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
from app.services import session_tags


def test_create_redirects_to_edit(client: TestClient, db: Session) -> None:
    """A bare Create (no Quick Setup uploads) lands on the Edit
    page — the operator's natural next step is to fill in the
    rest of the details. The back-link there returns to Session
    Home. A Create with Quick Setup uploads anchors back to the
    relevant card on Home (separate test path)."""
    response = client.post(
        "/operator/sessions",
        data={"name": "Spring Reviews", "code": "spring-2026"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "spring-2026")
    ).scalar_one()
    assert (
        response.headers["location"]
        == f"/operator/sessions/{review_session.id}/edit"
    )


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
# Bulk delete via the inline row expander on /operator/sessions
# ---------------------------------------------------------------------------


def test_sessions_list_delete_lives_in_the_expander(
    client: TestClient,
) -> None:
    """The standalone Danger Zone card is retired — delete now lives in
    the inline row expander: an Allow-delete confirm checkbox plus a
    Delete button posting the ticked session_ids to delete-selected."""

    client.post(
        "/operator/sessions",
        data={"name": "Spring Reviews", "code": "spring-2026"},
        follow_redirects=False,
    )

    body = client.get("/operator/sessions").text
    assert 'id="sessions-list-danger-zone"' not in body
    assert "data-expander-allow-delete" in body
    assert "data-expander-delete" in body
    assert 'formaction="/operator/sessions/delete-selected"' in body


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
    # Single-session expander Save is wired (no longer a placeholder).
    assert "data-expander-save" in body
    # Bulk expander hosts a Tags box + the bulk actions, Cancel, and
    # the selection-management buttons.
    assert 'data-expander-field="bulk-tags"' in body
    assert "data-expander-cancel" in body
    assert "data-expander-clear-all" in body
    assert "data-expander-clear-others" in body


def test_lobby_edit_updates_draft_session_and_tags(
    client: TestClient, db: Session
) -> None:
    """The single-session expander Save route updates a draft
    session's name / code and replaces its tag set."""
    client.post(
        "/operator/sessions",
        data={"name": "Old Name", "code": "old-1"},
        follow_redirects=False,
    )
    session_id = db.execute(
        select(ReviewSession.id).where(ReviewSession.code == "old-1")
    ).scalar_one()

    response = client.post(
        f"/operator/sessions/{session_id}/lobby-edit",
        data={
            "name": "New Name",
            "code": "new-1",
            "deadline": "",
            "tags": "Pilot, cohort-a",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    db.expire_all()
    updated = db.get(ReviewSession, session_id)
    assert updated.name == "New Name"
    assert updated.code == "new-1"
    assert session_tags.tags_for_sessions(db, [session_id])[session_id] == [
        "cohort-a",
        "pilot",
    ]


def test_lobby_edit_skips_name_code_when_not_draft(
    client: TestClient, db: Session
) -> None:
    """Off draft, the lobby-edit route ignores Name / Code (the boxes
    render read-only) but still applies the always-editable tags."""
    client.post(
        "/operator/sessions",
        data={"name": "Locked", "code": "locked-1"},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "locked-1")
    ).scalar_one()
    session_id = review_session.id
    review_session.status = "ready"
    db.commit()

    response = client.post(
        f"/operator/sessions/{session_id}/lobby-edit",
        data={
            "name": "Attempted",
            "code": "attempted-1",
            "deadline": "",
            "tags": "live-tag",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    db.expire_all()
    updated = db.get(ReviewSession, session_id)
    assert updated.name == "Locked"
    assert updated.code == "locked-1"
    assert session_tags.tags_for_sessions(db, [session_id])[session_id] == [
        "live-tag",
    ]


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


def test_lobby_sort_cookie_orders_the_table(client: TestClient) -> None:
    """The lobby opts into the shared rrw-sortable primitive — a sort
    cookie reorders the server-rendered rows."""
    client.post(
        "/operator/sessions",
        data={"name": "Aaa Session", "code": "sort-a"},
        follow_redirects=False,
    )
    client.post(
        "/operator/sessions",
        data={"name": "Zzz Session", "code": "sort-z"},
        follow_redirects=False,
    )

    client.cookies.set("rrw-sort-lobby", '[{"key": "name", "dir": "desc"}]')
    body = client.get("/operator/sessions").text
    client.cookies.delete("rrw-sort-lobby")

    # Descending by name — "Zzz Session" sorts above "Aaa Session".
    assert body.index("Zzz Session") < body.index("Aaa Session")


def test_archive_selected_archives_draft_and_excludes_from_lobby(
    client: TestClient, db: Session
) -> None:
    """Archive-selected flips draft sessions to archived; the main
    lobby table then excludes them while the stats pill still counts
    them."""
    client.post(
        "/operator/sessions",
        data={"name": "Archive Me", "code": "arch-me"},
        follow_redirects=False,
    )
    client.post(
        "/operator/sessions",
        data={"name": "Keep Me", "code": "keep-me"},
        follow_redirects=False,
    )
    session_id = db.execute(
        select(ReviewSession.id).where(ReviewSession.code == "arch-me")
    ).scalar_one()

    response = client.post(
        "/operator/sessions/archive-selected",
        data={"session_ids": [session_id]},
        follow_redirects=False,
    )
    assert response.status_code == 303

    db.expire_all()
    assert db.get(ReviewSession, session_id).status == "archived"

    body = client.get("/operator/sessions").text
    assert "Archive Me" not in body
    assert "Keep Me" in body
    assert "1 archived" in body


def test_archive_selected_skips_non_draft(
    client: TestClient, db: Session
) -> None:
    """A non-draft session ticked for archive is silently skipped —
    archiving is draft-only."""
    client.post(
        "/operator/sessions",
        data={"name": "Running", "code": "arch-running"},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "arch-running")
    ).scalar_one()
    session_id = review_session.id
    review_session.status = "ready"
    db.commit()

    client.post(
        "/operator/sessions/archive-selected",
        data={"session_ids": [session_id]},
        follow_redirects=False,
    )

    db.expire_all()
    assert db.get(ReviewSession, session_id).status == "ready"


def test_lobby_search_card_has_go_to_archive(client: TestClient) -> None:
    """The Search card carries a 'Go to Archive' link to the archived
    sessions child page."""
    client.post(
        "/operator/sessions",
        data={"name": "Anchor", "code": "goarch"},
        follow_redirects=False,
    )

    body = client.get("/operator/sessions").text
    assert 'href="/operator/sessions/archived"' in body
    assert "Go to Archive" in body


def test_archived_page_lists_archived_sessions(
    client: TestClient, db: Session
) -> None:
    """The archived-sessions child page lists the operator's archived
    sessions; a draft stays off it."""
    client.post(
        "/operator/sessions",
        data={"name": "Filed Away", "code": "arch-page"},
        follow_redirects=False,
    )
    client.post(
        "/operator/sessions",
        data={"name": "Still Active", "code": "active-page"},
        follow_redirects=False,
    )
    archived_id = db.execute(
        select(ReviewSession.id).where(ReviewSession.code == "arch-page")
    ).scalar_one()
    client.post(
        "/operator/sessions/archive-selected",
        data={"session_ids": [archived_id]},
        follow_redirects=False,
    )

    response = client.get("/operator/sessions/archived")
    assert response.status_code == 200
    body = response.text
    assert "Archived sessions" in body
    assert "Filed Away" in body
    assert "Still Active" not in body
    # The table carries sortable headers (incl. the Archived column)
    # and a select-checkbox column.
    assert 'data-sort-key="archived"' in body
    assert 'data-rrw-sortable="rrw-sort-archived"' in body
    assert 'class="archived-list-select-all"' in body
    # Search card + the bulk-only expander template.
    assert 'class="archived-search-input"' in body
    assert 'id="archived-bulk-expander"' in body


def test_unarchive_selected_restores_session_to_draft(
    client: TestClient, db: Session
) -> None:
    """The archived-page bulk expander's Unarchive flips a session
    archived → draft, returning it to the main lobby."""
    client.post(
        "/operator/sessions",
        data={"name": "Bring Back", "code": "unarch-me"},
        follow_redirects=False,
    )
    session_id = db.execute(
        select(ReviewSession.id).where(ReviewSession.code == "unarch-me")
    ).scalar_one()
    client.post(
        "/operator/sessions/archive-selected",
        data={"session_ids": [session_id]},
        follow_redirects=False,
    )

    response = client.post(
        "/operator/sessions/unarchive-selected",
        data={"session_ids": [session_id]},
        follow_redirects=False,
    )

    assert response.status_code == 303
    db.expire_all()
    assert db.get(ReviewSession, session_id).status == "draft"


def test_delete_archived_selected_removes_session(
    client: TestClient, db: Session
) -> None:
    """The archived-page bulk Delete removes an archived session; it
    requires the confirm gate."""
    client.post(
        "/operator/sessions",
        data={"name": "Purge Me", "code": "del-arch"},
        follow_redirects=False,
    )
    session_id = db.execute(
        select(ReviewSession.id).where(ReviewSession.code == "del-arch")
    ).scalar_one()
    client.post(
        "/operator/sessions/archive-selected",
        data={"session_ids": [session_id]},
        follow_redirects=False,
    )

    # Without the confirm gate the route rejects.
    no_confirm = client.post(
        "/operator/sessions/delete-archived-selected",
        data={"session_ids": [session_id]},
        follow_redirects=False,
    )
    assert no_confirm.status_code == 400

    response = client.post(
        "/operator/sessions/delete-archived-selected",
        data={"session_ids": [session_id], "confirm": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    db.expire_all()
    assert db.get(ReviewSession, session_id) is None


def _two_sessions(client: TestClient, db: Session) -> list[int]:
    for name, code in (("Bulk A", "bt-a"), ("Bulk B", "bt-b")):
        client.post(
            "/operator/sessions",
            data={"name": name, "code": code},
            follow_redirects=False,
        )
    return [
        db.execute(
            select(ReviewSession.id).where(ReviewSession.code == code)
        ).scalar_one()
        for code in ("bt-a", "bt-b")
    ]


def test_bulk_tags_add_to_all(client: TestClient, db: Session) -> None:
    """The bulk expander's 'All tags to all' adds every tag in the box
    to each selected session."""
    ids = _two_sessions(client, db)

    response = client.post(
        "/operator/sessions/bulk-tags",
        data={"session_ids": ids, "tags": "Alpha, beta", "op": "add"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    for session_id in ids:
        assert session_tags.tags_for_sessions(db, [session_id])[
            session_id
        ] == ["alpha", "beta"]


def test_bulk_tags_remove_from_all(client: TestClient, db: Session) -> None:
    """'Remove from all' strips every tag in the box from each
    selected session."""
    ids = _two_sessions(client, db)
    client.post(
        "/operator/sessions/bulk-tags",
        data={"session_ids": ids, "tags": "shared, gone", "op": "add"},
        follow_redirects=False,
    )

    response = client.post(
        "/operator/sessions/bulk-tags",
        data={"session_ids": ids, "tags": "gone", "op": "remove"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    for session_id in ids:
        assert session_tags.tags_for_sessions(db, [session_id])[
            session_id
        ] == ["shared"]


def test_bulk_tags_rejects_unknown_op(client: TestClient, db: Session) -> None:
    ids = _two_sessions(client, db)
    response = client.post(
        "/operator/sessions/bulk-tags",
        data={"session_ids": ids, "tags": "x", "op": "sideways"},
        follow_redirects=False,
    )
    assert response.status_code == 400


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


def test_lobby_status_cell_renders_closed_pill_for_expired_session(
    client: TestClient, db: Session
) -> None:
    """When a session's lifecycle enum is ``expired``, the lobby's
    Status cell renders ``<span class="pill pill-lifecycle-expired">
    Closed</span>`` — the label rename ("Closed" rather than the
    raw "Expired") plus a CSS class with a visible red treatment
    (matching the past-deadline pill in the Deadline column + the
    reviewer dashboard's ``closed`` pill).

    Earlier renders carried the same class but no
    ``body.ui-v2 .pill-lifecycle-expired`` rule existed in
    ``base.html``, so the pill fell back to plain text styling."""
    client.post(
        "/operator/sessions",
        data={"name": "Past", "code": "past-1"},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "past-1")
    ).scalar_one()
    review_session.status = "expired"
    db.commit()

    body = client.get("/operator/sessions").text
    assert (
        '<span class="pill pill-lifecycle-expired">Closed</span>' in body
    )
    # Confirm the CSS rule itself ships (regression guard against
    # the rule getting removed and the pill silently falling back
    # to the un-styled state).
    assert "body.ui-v2 .pill-lifecycle-expired" in body
