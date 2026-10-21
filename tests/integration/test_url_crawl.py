"""RRW's pages under the `/reviewrobin` mount emit no unprefixed URL.

Segment 21B (`guide/segment_21B_url_sweep.md`): the static rules in
`tests/unit/test_url_leaks.py` say every emission goes through the
helpers; this renders real pages under the mount and checks what they
emit (`tests/_mounted.py`'s `leaks()`). The page set grows as each area
is swept, and at B7 covers every fillable GET route; until then a page
whose body is not swept is checked only inside its swept regions.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from _mounted import MOUNT, leaks
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
