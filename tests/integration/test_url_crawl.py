"""RRW's pages under the `/reviewrobin` mount emit no unprefixed URL.

Segment 21B (`guide/segment_21B_url_sweep.md`): the static rules in
`tests/unit/test_url_leaks.py` say every emission goes through the
helpers; this renders real pages under the mount and checks what they
emit (`tests/_mounted.py`'s `leaks()`). The page set grows as each area
is swept, and at B7 covers every fillable GET route; until then a page
whose body is not swept is checked only inside its swept regions.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from _mounted import MOUNT, leaks
from app.auth.identity import AuthenticatedUser
from app.config import settings
from app.db.models import ReviewSession


@pytest.fixture
def session_id(mounted_client: TestClient, db: Session) -> str:
    mounted_client.post(
        f"{MOUNT}/operator/sessions",
        data={"name": "Crawl", "code": "crawl"},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "crawl")
    ).scalar_one()
    # The optional Setup pages render only with their toggles on.
    review_session.relationships_enabled = True
    review_session.observers_enabled = True
    db.flush()
    return review_session.public_id


@pytest.fixture
def sys_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])


# --- B2: the chrome ---


@pytest.mark.parametrize("path", ["/operator/no-such-page", "/me/no-such-page"])
def test_the_error_page_emits_only_prefixed_urls(mounted_client: TestClient, path: str) -> None:
    response = mounted_client.get(f"{MOUNT}{path}")
    assert response.status_code == 404
    assert leaks(response) == []


@pytest.mark.usefixtures("sys_admin")
def test_the_operator_chrome_emits_only_prefixed_urls(mounted_client: TestClient) -> None:
    response = mounted_client.get(f"{MOUNT}/operator/sessions")
    assert response.status_code == 200
    assert leaks(response, within="chrome-user") == []
    # Settings, Admin, Guide and About each carry the page's app-relative
    # path as their return_to.
    for target in ("operator/settings", "operator/sys-admin", "guide", "about"):
        assert f'href="{MOUNT}/{target}?return_to=/operator/sessions"' in response.text


def test_the_session_nav_and_breadcrumbs_emit_only_prefixed_urls(
    mounted_client: TestClient, session_id: str
) -> None:
    response = mounted_client.get(f"{MOUNT}/operator/sessions/{session_id}/reviewers")
    assert response.status_code == 200
    for region in ("session-nav-grid", "breadcrumb"):
        assert leaks(response, within=region) == [], region


@pytest.mark.usefixtures("sys_admin")
def test_the_sys_admin_nav_emits_only_prefixed_urls(mounted_client: TestClient) -> None:
    response = mounted_client.get(f"{MOUNT}/operator/sys-admin/sessions")
    assert response.status_code == 200
    assert leaks(response, within="sys-admin-nav") == []


def test_the_participant_top_bar_emits_only_prefixed_urls(mounted_client: TestClient) -> None:
    response = mounted_client.get(f"{MOUNT}/me")
    assert response.status_code == 200
    assert leaks(response, within="chrome-user") == []


def test_the_chrome_hides_its_own_page_under_the_mount(mounted_client: TestClient) -> None:
    """``is_here`` compares the app-relative path, so the Guide link is
    hidden on the Guide page under the mount, as at ``/``."""
    response = mounted_client.get(f"{MOUNT}/guide")
    assert response.status_code == 200
    assert f'href="{MOUNT}/guide?' not in response.text
    assert f'href="{MOUNT}/about?return_to=/guide"' in response.text


# --- B3: the operator pages, whole ---

OPERATOR_PAGES = [
    "/operator/sessions",
    "/operator/sessions/new",
    "/operator/sessions/archived",
    "/operator/settings",
]
SESSION_PAGES = [
    "",
    "/reviewers",
    "/reviewees",
    "/relationships",
    "/observers",
    "/instruments",
    "/setup-invite",
    "/assignments",
    "/validate",
    "/invitations",
    "/responses",
    "/extract-data",
]
SYS_ADMIN_PAGES = ["/operator/sys-admin/sessions", "/operator/sys-admin/users"]


@pytest.mark.parametrize("path", OPERATOR_PAGES)
def test_an_operator_page_emits_only_prefixed_urls(mounted_client: TestClient, path: str) -> None:
    response = mounted_client.get(f"{MOUNT}{path}")
    assert response.status_code == 200
    assert leaks(response) == []


@pytest.mark.parametrize("page", SESSION_PAGES)
def test_a_session_page_emits_only_prefixed_urls(
    mounted_client: TestClient, session_id: str, page: str
) -> None:
    response = mounted_client.get(f"{MOUNT}/operator/sessions/{session_id}{page}")
    assert response.status_code == 200
    # Validate's severity cookie is scoped by B6.
    assert leaks(response, cookies=page != "/validate") == []


@pytest.mark.usefixtures("sys_admin")
@pytest.mark.parametrize("path", SYS_ADMIN_PAGES)
def test_a_sys_admin_page_emits_only_prefixed_urls(mounted_client: TestClient, path: str) -> None:
    response = mounted_client.get(f"{MOUNT}{path}")
    assert response.status_code == 200
    # The admin return-to cookie is scoped by B6.
    assert leaks(response, cookies=False) == []


# --- B4: the participant pages, the Guide and About ---


@pytest.fixture
def active_session_id(mounted_client: TestClient, db: Session) -> str:
    """A session alice operates and rae reviews, activated, through the mount."""
    from ._full_matrix import mark_band1_touched_on_all_instruments, pin_full_matrix_on_all_instruments

    base = f"{MOUNT}/operator/sessions"
    mounted_client.post(base, data={"name": "Live", "code": "live"}, follow_redirects=False)
    review_session = db.execute(select(ReviewSession).where(ReviewSession.code == "live")).scalar_one()
    sid = review_session.public_id
    for kind, body in (
        ("reviewers", b"ReviewerName,ReviewerEmail\nRae,rae@example.edu\n"),
        ("reviewees", b"RevieweeName,RevieweeEmail\nCarol,carol@example.edu\n"),
    ):
        mounted_client.post(
            f"{base}/{sid}/{kind}/import",
            files={"file": (f"{kind}.csv", body, "text/csv")},
            follow_redirects=False,
        )
    pin_full_matrix_on_all_instruments(db, review_session.id)
    mark_band1_touched_on_all_instruments(db, review_session.id)
    for step in ("prepare", "activate"):
        mounted_client.post(f"{base}/{sid}/workflow/{step}", follow_redirects=False)
    db.refresh(review_session)
    assert review_session.status == "ready", review_session.status  # activated: open to reviewers
    return sid


@pytest.mark.parametrize("path", ["/me", "/guide", "/about", "/auth/me/debug"])
def test_a_participant_page_emits_only_prefixed_urls(
    mounted_client: TestClient, active_session_id: str, path: str
) -> None:
    response = mounted_client.get(f"{MOUNT}{path}")
    assert response.status_code == 200
    assert leaks(response) == []


@pytest.fixture
def rae_client(make_mounted_client: Callable[[AuthenticatedUser], TestClient]) -> TestClient:
    rae = AuthenticatedUser(principal_id="rae-oid", email="rae@example.edu", name="Rae", provider="aad")
    return make_mounted_client(rae)


@pytest.mark.parametrize("path", ["/me", "/me/sessions/{sid}/1"])
def test_a_reviewer_page_emits_only_prefixed_urls(
    active_session_id: str, rae_client: TestClient, path: str
) -> None:
    response = rae_client.get(f"{MOUNT}{path.format(sid=active_session_id)}")
    assert response.status_code == 200
    assert leaks(response) == []


# --- B5: redirects ---


def test_the_root_redirects_land_under_the_mount(mounted_client: TestClient) -> None:
    for path in ("/", "/operator"):
        response = mounted_client.get(f"{MOUNT}{path}", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["location"] == f"{MOUNT}/operator/sessions"


def test_a_post_redirect_lands_under_the_mount(mounted_client: TestClient) -> None:
    response = mounted_client.post(
        f"{MOUNT}/operator/sessions", data={"name": "R", "code": "redir"}, follow_redirects=False
    )
    assert response.status_code == 303
    assert response.headers["location"].startswith(f"{MOUNT}/operator/sessions/")
    assert leaks(response) == []


@pytest.mark.parametrize("path", ["/me/sessions/{sid}", "/me/sessions/{sid}/summary"])
def test_a_reviewer_redirect_lands_under_the_mount(
    active_session_id: str, rae_client: TestClient, path: str
) -> None:
    response = rae_client.get(f"{MOUNT}{path.format(sid=active_session_id)}", follow_redirects=False)
    assert response.status_code in (302, 303, 307)
    assert response.headers["location"].startswith(f"{MOUNT}/me")
    assert leaks(response) == []
