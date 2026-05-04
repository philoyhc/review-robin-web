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


def test_reviewer_chrome_renders_lighter_top_bar_with_no_breadcrumb(
    client: TestClient,
) -> None:
    """Reviewer pages render the lighter "Review Robin" chrome variant
    (Segment 11D PR C, D2): no version string, no /about link, and no
    breadcrumb. The user card and sign-out remain."""
    response = client.get("/reviewer")
    assert response.status_code == 200
    body = response.text
    assert "Review Robin Web App" not in body
    assert "version dev" not in body
    assert 'class="chrome-app-identity">Review Robin</span>' in body
    assert 'href="/about"' not in body
    assert "Signed in as Alice Example" in body
    assert 'href="/.auth/logout"' in body
    # No operator-style breadcrumb on the reviewer surface.
    assert 'class="breadcrumb"' not in body


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


def test_breadcrumb_is_suppressed_on_reviewer_root(
    client: TestClient,
) -> None:
    """Reviewer pages don't carry the operator-style breadcrumb
    (Segment 11D PR C, D2). The chrome's H1 + the user menu together
    orient the reviewer."""
    response = client.get("/reviewer")
    body = response.text
    assert 'class="breadcrumb"' not in body
    assert '<span aria-current="page">Reviewer</span>' not in body


def test_sessions_list_row_renders_name_link_and_delete_button(
    client: TestClient, db: Session
) -> None:
    review_session = _create_session(client, db)
    response = client.get("/operator/sessions")
    body = response.text
    # The session name in the first column is the row's link into Home;
    # the redundant Access button was retired once the name became the
    # primary affordance.
    assert (
        f'<a href="/operator/sessions/{review_session.id}">{review_session.name}</a>'
        in body
    )
    assert ">Access</a>" not in body
    # Delete sits in the unlabelled trailing action column.
    assert (
        f'<a class="btn danger-solid" href="/operator/sessions/{review_session.id}#danger-zone">Delete</a>'
        in body
    )


def test_sessions_list_create_button_lives_in_header(
    client: TestClient, db: Session
) -> None:
    _create_session(client, db)
    response = client.get("/operator/sessions")
    body = response.text
    # Old top-of-page "Create session" link no longer present.
    assert ">Create session<" not in body
    # Per Segment 11D PR B (D4) and the cards-vs-table revisit, the
    # Primary "Create new session" affordance sits in the header row
    # to the right of the H1, above the lobby's table-in-a-card.
    assert 'href="/operator/sessions/new"' in body
    assert "Create new session" in body
    header_close = body.find("</div>", body.find('class="sessions-list-header"'))
    create_btn = body.find("Create new session")
    assert header_close != -1 and 0 < create_btn < header_close


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
