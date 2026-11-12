"""The URL map as placeholders (segment AD1, item 2): every page answers
locally, IDs are shape-checked, the gate holds deployed, every link stays
in the mount, and a blind profile names nobody."""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from applydesk import gate, sample_data
from applydesk.ids import PUBLIC_ID_ALPHABET, PUBLIC_ID_LENGTH, generate_public_id, is_public_id
from applydesk.main import create_app
from applydesk.tests._host import host_with
from cordware.identity import Identity

EX = "wa9juxbc2t"  # open, not blind, Application stage
BLIND = "k7mfr3pq8z"  # blind, Review stage
DRAFT = "c4xh2ndv6s"  # not published

PAGES = (
    "/applydesk/",
    "/applydesk/operator/exercises",
    f"/applydesk/operator/exercises/{EX}",
    *(
        f"/applydesk/operator/exercises/{EX}/{section}"
        for section in (
            "settings",
            "form",
            "applications",
            "assessors",
            "review",
            "timeline",
            "export",
        )
    ),
    f"/applydesk/operator/exercises/{BLIND}",  # Review stage: "Go to Review"
    f"/applydesk/operator/exercises/{BLIND}/settings",  # blind review on
    f"/applydesk/operator/exercises/{DRAFT}",  # the Publish step
    f"/applydesk/operator/exercises/{DRAFT}/applications",  # none yet
    "/applydesk/me",
    f"/applydesk/me/exercises/{EX}",
    f"/applydesk/me/exercises/{BLIND}",  # applications have closed
    f"/applydesk/me/exercises/{EX}/applications/m3qx8vkt2n",
    f"/applydesk/me/exercises/{EX}/profiles/p3bd7kq2wx",
    f"/applydesk/me/exercises/{BLIND}/profiles/t8nv4hzm2c",
)


@pytest.fixture
def client() -> TestClient:
    return TestClient(host_with(("applydesk",))[0])


@pytest.mark.parametrize("path", PAGES)
def test_every_page_of_the_map_answers_locally(client: TestClient, path: str) -> None:
    response = client.get(path)
    assert response.status_code == 200, path
    assert "Placeholder." in response.text


@pytest.mark.parametrize(
    "path",
    [
        "/applydesk/operator/exercises/WA9JUXBC2T",  # uppercase is not the alphabet
        "/applydesk/operator/exercises/wa9juxbc2",  # nine characters
        "/applydesk/operator/exercises/wa9juxbc2t0",  # eleven
        "/applydesk/operator/exercises/wa9juxbc1t",  # a look-alike
        "/applydesk/operator/exercises/zzzzzzzzzz",  # well formed, unknown
        f"/applydesk/operator/exercises/{EX}/bogus",
        "/applydesk/me/exercises/c4xh2ndv6s",  # a draft is not open to applicants
        f"/applydesk/me/exercises/{EX}/applications/zzzzzzzzzz",
        f"/applydesk/me/exercises/{EX}/applications/M3QX8VKT2N",  # an application ID's shape
        f"/applydesk/me/exercises/{EX}/applications/m3qx8vkt2",
        f"/applydesk/me/exercises/{EX}/profiles/P3BD7KQ2WX",  # a profile ID's shape
        f"/applydesk/me/exercises/{EX}/profiles/p3bd7kq2wx0",
        f"/applydesk/me/exercises/{EX}/profiles/m3qx8vkt2n",  # an application ID is no profile ID
        f"/applydesk/me/exercises/{BLIND}/profiles/p3bd7kq2wx",  # another exercise's profile
    ],
)
def test_a_malformed_or_unknown_id_is_a_404(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 404, path


def test_public_ids_have_rrw_s_shape() -> None:
    assert PUBLIC_ID_ALPHABET == "23456789abcdefghjkmnpqrstuvwxyz" and PUBLIC_ID_LENGTH == 10
    for _ in range(50):
        assert is_public_id(generate_public_id())
    samples = [e.public_id for e in sample_data.EXERCISES]
    samples += [a.public_id for a in sample_data.APPLICATIONS]
    samples += [a.profile_id for a in sample_data.APPLICATIONS]
    assert all(is_public_id(s) for s in samples)
    assert len(set(samples)) == len(samples)


def test_deployed_only_the_super_admin_reaches_a_placeholder(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gate, "is_local", lambda: False)
    someone = Identity(principal_id="1", email="someone@example.edu", name="Someone")
    monkeypatch.setattr(gate, "current_identity", lambda request: someone)
    for path in PAGES:
        assert client.get(path).status_code == 404, path
    assert client.get("/applydesk/health").status_code == 200
    monkeypatch.setattr(gate, "current_identity", lambda request: None)
    assert client.get("/applydesk/me").status_code == 404


def test_deployed_the_super_admin_reaches_them(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gate, "is_local", lambda: False)
    client = TestClient(host_with(("applydesk",))[0])
    assert client.get("/applydesk/me").status_code == 200  # the conftest's fake super-admin


_LINK = re.compile(r'\b(?:href|action|src)="([^"]*)"')


@pytest.mark.parametrize("path", PAGES)
def test_every_link_stays_in_the_mount(client: TestClient, path: str) -> None:
    """Every link sits under the mount; only the host's landing and Easy
    Auth's sign-out leave it. (That templates write them through `url()`
    is held by rendering under another prefix, below.)"""
    for link in _LINK.findall(client.get(path).text):
        if link.startswith("data:") or link.startswith("#"):
            continue
        assert link.startswith("/applydesk/") or link in ("/", "/.auth/logout"), (path, link)


def test_the_tabs_mark_the_current_page(client: TestClient) -> None:
    page = client.get(f"/applydesk/operator/exercises/{EX}/form").text
    assert f'<a href="/applydesk/operator/exercises/{EX}/form" aria-current="page">Form</a>' in page
    assert page.count('aria-current="page"') == 2  # the tab, and Exercises in the switcher


def test_a_blind_profile_names_nobody(client: TestClient) -> None:
    app = sample_data.by_profile(BLIND, "t8nv4hzm2c")
    assert app is not None
    page = client.get(f"/applydesk/me/exercises/{BLIND}/profiles/t8nv4hzm2c").text
    for identifying in (app.applicant, app.email, app.public_id):
        assert identifying not in page, identifying
    assert "Redacted" in page


def test_an_open_profile_names_the_applicant(client: TestClient) -> None:
    page = client.get(f"/applydesk/me/exercises/{EX}/profiles/p3bd7kq2wx").text
    assert "Aisha Bello" in page


@pytest.mark.parametrize("profile", ["p3bd7kq2wx", "t8nv4hzm2c"])
def test_a_profile_shows_only_the_part_shown_to_reviewers(client: TestClient, profile: str) -> None:
    exercise = EX if profile == "p3bd7kq2wx" else BLIND
    page = client.get(f"/applydesk/me/exercises/{exercise}/profiles/{profile}").text
    assert "Shown to reviewers" in page and "Not shown to reviewers" not in page
    for hidden in sample_data.NOT_SHOWN_TO_REVIEWERS:
        assert hidden not in page, hidden


def test_the_bar_s_icon_is_the_favicon(client: TestClient) -> None:
    page = client.get("/applydesk/me").text
    (favicon,) = re.findall(r'<link rel="icon" type="image/svg\+xml"\s+href="([^"]+)"', page)
    assert f'url("{favicon}")' in page


def test_no_inline_style_attributes(client: TestClient) -> None:
    """New visual primitives are classes in `base.html`, never `style=`."""
    for path in PAGES:
        assert " style=" not in client.get(path).text, path


def _gated_routes(routes: Any, gates: tuple[object, ...] = ()) -> Iterator[tuple[Any, set[object]]]:
    """Every route under ``routes`` with the dependencies that guard it,
    an enclosing include's too (FastAPI nests an included router behind
    its include context), as Residential's gate test walks them."""
    for route in routes:
        context = getattr(route, "include_context", None)
        if context is not None:
            outer = tuple(d.dependency for d in context.dependencies or ())
            yield from _gated_routes(context.included_router.routes, gates + outer)
            continue
        calls: set[object] = set(gates)
        pending = list(route.dependant.dependencies if hasattr(route, "dependant") else ())
        while pending:
            dependant = pending.pop()
            calls.add(dependant.call)
            pending.extend(dependant.dependencies)
        yield route, calls


def test_every_route_but_health_carries_the_gate() -> None:
    """A router that forgot `Depends(placeholders_only)` would pass the
    path checks above; this walks every route the factory builds."""
    routes = list(_gated_routes(create_app().routes))
    assert len(routes) > 1
    missing = [
        r.path for r, calls in routes if r.path != "/health" and gate.placeholders_only not in calls
    ]
    assert missing == []


def test_links_follow_the_mount_s_prefix() -> None:
    """Mounted elsewhere, every link moves with it: none is written with
    `/applydesk` spelled out, so each went through `url()`."""
    from fastapi import FastAPI

    from applydesk.main import create_app as factory

    host = FastAPI()
    host.mount("/elsewhere", factory())
    client = TestClient(host)
    for path in PAGES:
        page = client.get(path.replace("/applydesk/", "/elsewhere/", 1)).text
        for link in _LINK.findall(page):
            assert not link.startswith("/applydesk"), (path, link)


def test_health_answers_with_no_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    """No sign-in at all, fake auth off and deployed: health still answers,
    and nothing else does."""
    from cordware.settings import identity_settings

    monkeypatch.setattr(identity_settings, "allow_fake_auth", False)
    monkeypatch.setattr(identity_settings, "app_env", "production")
    monkeypatch.setattr(gate, "is_local", lambda: False)
    client = TestClient(host_with(("applydesk",))[0])
    assert client.get("/applydesk/health").json() == {"status": "ok"}
    assert client.get("/applydesk/me").status_code == 404


def test_the_lobby_names_exercises_by_code_not_id(client: TestClient) -> None:
    """Iteration rung 4 (author, 2026-11-12): an Exercise Code column, as
    RRW's Session Code; the public ID is only in each row's link."""
    page = client.get("/applydesk/operator/exercises").text
    assert "<th>Exercise Code</th>" in page and ">ID<" not in page
    for e in sample_data.EXERCISES:
        assert f"<code>{e.code}</code>" in page
        assert f"<code>{e.public_id}</code>" not in page
    codes = [e.code for e in sample_data.EXERCISES]
    assert len(set(codes)) == len(codes)


def test_withdraw_is_destructive(client: TestClient) -> None:
    """The applicant cannot undo a withdrawal (author, 2026-11-12)."""
    page = client.get(f"/applydesk/me/exercises/{EX}/applications/h6zr2tdw9p").text
    assert '<button class="btn btn-destructive" type="button" disabled>Withdraw</button>' in page
