"""v0.8 §3's behavior requirements, under the mount (segment 21D, rung D3;
`guide/archive/segment_21D_prefix_flip.md` § Semantics).

RRW answers at `/reviewrobin`. These pin what the move must keep:

- **Requirement 2, probes.** The host's `/health` and RRW's own
  `/reviewrobin/health` both answer.
- **Requirement 3, request handling.** RRW's error handlers run inside
  the mounted application: its own 404, 403 and 422 pages.
- **Requirement 4, absolute URLs.** An invitation link carries the
  request's host and the mount, never another name for the backend.

Requirement 1 (a deep link through sign-in) is Easy Auth's redirect, not
RRW's, so its check is the dev slot's. Alongside: Easy Auth's `/.auth/*`
stays host-level, and the bare mount redirects to its slash.
"""

from __future__ import annotations

import re
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from _mounted import MOUNT, mounted_rrw
from app.auth.identity import AuthenticatedUser
from app.config import settings
from app.db.models import EmailOutbox, Invitation, ReviewSession

from ._full_matrix import mark_band1_touched_on_all_instruments, pin_full_matrix_on_all_instruments


def _rae() -> AuthenticatedUser:
    return AuthenticatedUser(
        principal_id="rae-oid", email="rae@example.edu", name="Rae", provider="aad"
    )


def test_the_suites_mount_is_the_registrys() -> None:
    """These tests mount RRW through a registry override at `MOUNT`; the
    deployed path is `REGISTRY`'s. They must agree, or every test here
    would pass at a path nothing serves."""
    mounted_rrw()  # imports `cordware.main` with logging restored
    from cordware.main import REGISTRY

    assert REGISTRY["reviewrobin"].path == MOUNT


# --- Requirement 2: both probes ---


def test_the_host_probe_and_rrws_probe_both_answer() -> None:
    client = TestClient(mounted_rrw())
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get(f"{MOUNT}/health").json() == {"status": "ok"}


def test_the_bare_mount_redirects_to_its_slash() -> None:
    response = TestClient(mounted_rrw()).get(MOUNT, follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"].endswith(f"{MOUNT}/")


# --- Requirement 3: RRW's own error pages ---


def test_an_unknown_path_under_the_mount_is_rrws_404(mounted_client: TestClient) -> None:
    response = mounted_client.get(f"{MOUNT}/operator/no/such/page")
    assert response.status_code == 404
    assert "text/html" in response.headers["content-type"]
    assert "Error 404" in response.text
    assert f'href="{MOUNT}/operator/sessions" data-error-home>' in response.text


def test_a_sys_admin_page_refuses_an_operator_with_rrws_403(
    make_mounted_client: Callable[[AuthenticatedUser], TestClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "operator_emails", ["rae@example.edu"])
    response = make_mounted_client(_rae()).get(
        f"{MOUNT}/operator/sys-admin/sessions", follow_redirects=False
    )
    assert response.status_code == 403
    assert "text/html" in response.headers["content-type"]
    assert "Access denied" in response.text


def test_a_malformed_request_under_the_mount_is_rrws_422(mounted_client: TestClient) -> None:
    response = mounted_client.post(f"{MOUNT}/operator/sessions", data={}, follow_redirects=False)
    assert response.status_code == 422
    assert "text/html" in response.headers["content-type"]
    assert "Bad request" in response.text


# --- Easy Auth's paths stay the host's ---


def _nameless() -> AuthenticatedUser:
    """An identity with no email claim: RRW answers it with its 401 page."""
    return AuthenticatedUser(principal_id="anon-oid", email="", name="", provider="aad")


@pytest.mark.parametrize(
    ("who", "path", "expected"),
    [
        # base.html's chrome.
        (_rae, "/operator/sessions", 'href="/.auth/logout"'),
        # reviewer/_top_bar.html.
        (_rae, "/me", 'class="signout" href="/.auth/logout"'),
        # me_debug.html.
        (_rae, "/auth/me/debug", 'href="/.auth/logout"'),
        # error_handlers.py's 401 link, on error.html.
        (_nameless, "/me", 'href="/.auth/logout" data-error-home'),
        # error.html's check that a referrer is not the sign-in service.
        (_rae, "/operator/no/such/page", 'indexOf("/.auth/")'),
    ],
    ids=["chrome", "reviewer-bar", "me-debug", "401-page", "error-page-script"],
)
def test_easy_auths_paths_stay_the_hosts(
    make_mounted_client: Callable[[AuthenticatedUser], TestClient],
    monkeypatch: pytest.MonkeyPatch,
    who: Callable[[], AuthenticatedUser],
    path: str,
    expected: str,
) -> None:
    monkeypatch.setattr(settings, "operator_emails", ["rae@example.edu"])
    body = make_mounted_client(who()).get(f"{MOUNT}{path}", follow_redirects=False).text
    assert expected in body
    assert f"{MOUNT}/.auth/" not in body


# --- Requirement 4: absolute URLs ---


def test_an_invitation_link_carries_the_requests_host_and_the_mount(
    mounted_client: TestClient, db: Session
) -> None:
    """The gateway's public host, as the request carries it: the link is
    never built from the App Service's own name. ``mounted_client`` signs
    alice in; this client shares its overrides, on another host."""
    client = TestClient(mounted_rrw(), base_url="http://reviews.example.edu")
    base = f"{MOUNT}/operator/sessions"
    client.post(base, data={"name": "Public", "code": "public"}, follow_redirects=False)
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "public")
    ).scalar_one()
    sid = review_session.public_id
    for kind, body in (
        ("reviewers", b"ReviewerName,ReviewerEmail\nRae,rae@example.edu\n"),
        ("reviewees", b"RevieweeName,RevieweeEmail\nCarol,carol@example.edu\n"),
    ):
        client.post(
            f"{base}/{sid}/{kind}/import",
            files={"file": (f"{kind}.csv", body, "text/csv")},
            follow_redirects=False,
        )
    pin_full_matrix_on_all_instruments(db, review_session.id)
    mark_band1_touched_on_all_instruments(db, review_session.id)
    for step in ("prepare", "activate"):
        client.post(f"{base}/{sid}/workflow/{step}", follow_redirects=False)
    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == review_session.id)
    ).scalars().first()
    client.post(f"{base}/{sid}/invitations/{invitation.id}/send", follow_redirects=False)

    outbox = db.execute(
        select(EmailOutbox).where(EmailOutbox.invitation_id == invitation.id)
    ).scalar_one()
    links = re.findall(r"https?://[^\s\"'<>]+/invite/[\w-]+", outbox.body)
    assert links, outbox.body
    assert all(
        link.startswith(f"http://reviews.example.edu{MOUNT}/me/invite/") for link in links
    ), links
