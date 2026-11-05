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
    return db.execute(select(ReviewSession).where(ReviewSession.code == code)).scalar_one()


def test_operator_chrome_renders_the_shared_bar_and_account_menu(
    client: TestClient,
) -> None:
    """Segment 20D: the shared top bar (`docs/header_chrome.md` §2, §4).
    No version text, "Signed in as" or Sign out button in the bar; the
    account menu holds them, About carrying ?return_to= and the version
    beside it for an operator."""
    response = client.get("/operator/sessions")
    assert response.status_code == 200
    body = response.text
    assert "Review Robin Web App" not in body
    assert "Signed in as" not in body
    assert 'class="signout"' not in body
    assert 'class="tb-app">Review Robin' in body
    assert 'aria-label="Account: Alice Example"' in body
    assert 'href="/about?return_to=/operator/sessions">About <small>version dev</small></a>' in body
    assert "<strong>Alice Example</strong>" in body
    # No tier line for a regular operator.
    assert "<span>sys admin</span>" not in body
    assert 'href="/.auth/logout" data-sign-out' in body
    # Shared sort primitive (Segment 13B Part 2 PR 4) ships in
    # ``base.html`` so every page can opt into clickable sort
    # via the ``data-rrw-sortable`` annotation contract.
    # Regression guard so future template-only PRs don't
    # silently regress the primitive into per-page duplicates.
    assert "function rrwSortHeaderClick" in body
    assert "body.ui-v2 th.rrw-sortable" in body


def test_the_account_menu_names_a_sys_admins_tier(
    client: TestClient,
    monkeypatch,
) -> None:
    """A sys admin's account menu says so under their name, as the
    "(sys admin)" suffix on "Signed in as" did (`docs/header_chrome.md`
    §4)."""
    from app.config import settings

    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    response = client.get("/operator/sessions")
    assert response.status_code == 200
    assert "<span>sys admin</span>" in response.text


def test_participant_pages_render_the_same_bar_with_no_breadcrumb(
    client: TestClient,
) -> None:
    """Reviewer pages render the same bar (20D), with no breadcrumb row
    (`docs/header_chrome.md` §5). The account menu and Sign out remain."""
    response = client.get("/me")
    assert response.status_code == 200
    body = response.text
    assert "Review Robin Web App" not in body
    assert 'class="tb-app">Review Robin' in body
    assert "<strong>Alice Example</strong>" in body
    assert 'href="/.auth/logout" data-sign-out' in body
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
    response = client.get(f"/operator/sessions/{review_session.public_id}")
    body = response.text
    assert '<a href="/operator/sessions">Sessions</a>' in body
    assert f'<span aria-current="page">{review_session.name}</span>' in body


def test_breadcrumb_on_nested_operator_page_renders_three_tuple_trail(
    client: TestClient, db: Session
) -> None:
    review_session = _create_session(client, db)
    response = client.get(f"/operator/sessions/{review_session.public_id}/reviewers")
    body = response.text
    assert '<a href="/operator/sessions">Sessions</a>' in body
    assert (
        f'<a href="/operator/sessions/{review_session.public_id}" '
        f'class="bc-mid">{review_session.name}</a>' in body
    )
    assert '<span aria-current="page">Reviewers</span>' in body


def test_breadcrumb_is_suppressed_on_reviewer_root(
    client: TestClient,
) -> None:
    """Reviewer pages don't carry the operator-style breadcrumb
    (Segment 11D PR C, D2). The chrome's H1 + the user menu together
    orient the reviewer."""
    response = client.get("/me")
    body = response.text
    assert 'class="breadcrumb"' not in body
    assert '<span aria-current="page">Reviewer</span>' not in body


def test_sessions_list_row_renders_name_link_and_select_checkbox(
    client: TestClient, db: Session
) -> None:
    review_session = _create_session(client, db)
    response = client.get("/operator/sessions")
    body = response.text
    # The session name in the first column is the row's link into Home;
    # the redundant Access button was retired once the name became the
    # primary affordance.
    assert (
        f'<a href="/operator/sessions/{review_session.public_id}">{review_session.name}</a>' in body
    )
    assert ">Access</a>" not in body
    # The trailing column carries the bulk-action select-row checkbox;
    # the per-row Delete anchor that briefly lived here was retired in
    # favour of the Danger Zone card on the same page.
    assert ">Delete</a>" not in body
    assert f'aria-label="Select {review_session.name}"' in body
    assert 'name="session_ids"' in body
    assert f'value="{review_session.id}"' in body


def test_sessions_list_create_button_lives_in_header(client: TestClient, db: Session) -> None:
    _create_session(client, db)
    response = client.get("/operator/sessions")
    body = response.text
    # Old top-of-page "Create session" link no longer present.
    assert ">Create session<" not in body
    # Per Segment 18A, the "Add new" session affordance lives in the
    # half-width session-actions card above the lobby's table-in-a-card.
    assert 'href="/operator/sessions/new"' in body
    create_btn = body.find('href="/operator/sessions/new"')
    action_card = body.find('class="card sessions-action-card"')
    table_card = body.find('id="sessions-list-form"')
    assert action_card != -1 and action_card < create_btn < table_card


def test_about_page_is_reachable_without_easy_auth(client: TestClient) -> None:
    response = client.get("/about")
    assert response.status_code == 200
    body = response.text
    assert "version dev" in body


def test_back_links_are_removed_from_nested_operator_pages(client: TestClient, db: Session) -> None:
    review_session = _create_session(client, db)
    response = client.get(f"/operator/sessions/{review_session.public_id}/reviewers")
    body = response.text
    # The old back-arrow link is gone — the chrome breadcrumb replaces it.
    assert "&larr;" not in body
    assert (
        f'<a href="/operator/sessions/{review_session.public_id}">{review_session.name}</a> '
        not in body
        # Allow the breadcrumb anchor (which is the crumb to session detail);
        # the regression-guard is the absence of the standalone "← {name}"
        # back-link rendered as a paragraph.
    )


def test_session_home_has_danger_zone_anchor(client: TestClient, db: Session) -> None:
    """18R Item 4 — Danger Zone is wired on Session Home (bottom-right),
    relocated from the retired Edit page."""
    review_session = _create_session(client, db)
    home_body = client.get(f"/operator/sessions/{review_session.public_id}").text
    assert 'id="danger-zone"' in home_body


def test_chrome_user_card_shown_on_about(client: TestClient) -> None:
    # 18R Item 6: /about absorbed the /request-access role, so it now
    # renders WITH the signed-in identity (a stranger needs to see who
    # they are + a Sign out affordance). Since 20D the account menu
    # names them and holds Sign out.
    response = client.get("/about")
    body = response.text
    assert "<strong>Alice Example</strong>" in body
    assert 'href="/.auth/logout" data-sign-out' in body
