"""Tests for the global page chrome and breadcrumb partial (Segment 9.4A)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession


def _create_session(client: TestClient, db: Session, *, code: str = "spring-2026") -> ReviewSession:
    client.post(
        "/operator/sessions",
        data={"name": code.title(), "code": code},
        follow_redirects=False,
    )
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def test_operator_chrome_renders_app_identity_user_card_and_signout(
    client: TestClient,
) -> None:
    response = client.get("/operator/sessions")
    assert response.status_code == 200
    body = response.text
    assert 'href="/about"' in body
    assert "Review Robin Web App (version dev)" in body
    assert "Signed in as Alice Example" in body
    assert 'href="/.auth/logout"' in body


def test_reviewer_chrome_renders_app_identity_user_card_and_signout(
    client: TestClient,
) -> None:
    response = client.get("/reviewer")
    assert response.status_code == 200
    body = response.text
    assert 'href="/about"' in body
    assert "Review Robin Web App (version dev)" in body
    assert "Signed in as Alice Example" in body
    assert 'href="/.auth/logout"' in body


def test_breadcrumb_on_operator_root_shows_single_non_link_label(
    client: TestClient,
) -> None:
    response = client.get("/operator/sessions")
    body = response.text
    # The Sessions crumb is the current page → non-link <span>, not an <a>.
    assert '<span aria-current="page">Sessions</span>' in body
    assert '<a href="/operator/sessions">Sessions</a>' not in body


def test_breadcrumb_on_session_detail_links_back_to_sessions(
    client: TestClient, db: Session
) -> None:
    review_session = _create_session(client, db)
    response = client.get(f"/operator/sessions/{review_session.id}")
    body = response.text
    assert '<a href="/operator/sessions">Sessions</a>' in body
    assert f'<span aria-current="page">{review_session.name}</span>' in body


def test_breadcrumb_on_nested_operator_page_renders_three_tuple_trail(
    client: TestClient, db: Session
) -> None:
    review_session = _create_session(client, db)
    response = client.get(f"/operator/sessions/{review_session.id}/reviewers")
    body = response.text
    assert '<a href="/operator/sessions">Sessions</a>' in body
    assert (
        f'<a href="/operator/sessions/{review_session.id}">{review_session.name}</a>'
        in body
    )
    assert '<span aria-current="page">Reviewers</span>' in body


def test_breadcrumb_on_reviewer_root_shows_single_non_link_label(
    client: TestClient,
) -> None:
    response = client.get("/reviewer")
    body = response.text
    assert '<span aria-current="page">Reviewer</span>' in body
    assert '<a href="/reviewer">Reviewer</a>' not in body


def test_sessions_list_per_row_renders_access_and_delete_buttons(
    client: TestClient, db: Session
) -> None:
    review_session = _create_session(client, db)
    response = client.get("/operator/sessions")
    body = response.text
    assert (
        f'<a class="btn secondary" href="/operator/sessions/{review_session.id}">Access</a>'
        in body
    )
    assert (
        f'<a class="btn danger-solid" href="/operator/sessions/{review_session.id}#danger-zone">Delete</a>'
        in body
    )


def test_sessions_list_create_button_lives_below_table(
    client: TestClient, db: Session
) -> None:
    _create_session(client, db)
    response = client.get("/operator/sessions")
    body = response.text
    # Old top-of-page "Create session" link no longer present.
    assert ">Create session<" not in body
    # New "Create new session" button targets the new-session form.
    assert 'href="/operator/sessions/new"' in body
    assert "Create new session" in body
    # Button appears after the closing </table>.
    table_end = body.rfind("</table>")
    create_btn = body.find("Create new session")
    assert table_end != -1 and create_btn > table_end


def test_about_page_is_reachable_without_easy_auth(client: TestClient) -> None:
    response = client.get("/about")
    assert response.status_code == 200
    body = response.text
    assert "version dev" in body


def test_back_links_are_removed_from_nested_operator_pages(
    client: TestClient, db: Session
) -> None:
    review_session = _create_session(client, db)
    response = client.get(f"/operator/sessions/{review_session.id}/reviewers")
    body = response.text
    # The old back-arrow link is gone — the chrome breadcrumb replaces it.
    assert "&larr;" not in body
    assert (
        f'<a href="/operator/sessions/{review_session.id}">{review_session.name}</a> '
        not in body
        # Allow the breadcrumb anchor (which is the crumb to session detail);
        # the regression-guard is the absence of the standalone "← {name}"
        # back-link rendered as a paragraph.
    )


def test_session_detail_has_danger_zone_anchor(
    client: TestClient, db: Session
) -> None:
    review_session = _create_session(client, db)
    response = client.get(f"/operator/sessions/{review_session.id}")
    body = response.text
    assert 'id="danger-zone"' in body


def test_chrome_user_card_hidden_when_user_unset(client: TestClient) -> None:
    # /about renders without a user — the user card should not appear.
    response = client.get("/about")
    body = response.text
    assert "Signed in as" not in body
    # But the app-identity link is still present.
    assert "Review Robin Web App (version dev)" in body
