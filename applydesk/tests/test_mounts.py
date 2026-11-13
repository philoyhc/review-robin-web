"""ApplyDesk under the Cordware host: the registry entry, running alone and
beside the others, health, route names, log stamps and the favicon
(`applydesk/spec/applications.md`; segment AD1, item 1)."""

from __future__ import annotations

import logging
import re

import pytest
from fastapi.testclient import TestClient

from applydesk.tests._host import host_with
from cordware.main import REGISTRY, AppEntry

HEALTH = "/applydesk/health"


def test_registry_entry() -> None:
    assert REGISTRY["applydesk"] == AppEntry(
        path="/applydesk",
        factory="applydesk.main:create_app",
        logger="applydesk",
        title="Apply Desk",
    )
    # The landing page's order (author, 2026-11-13).
    assert list(REGISTRY) == [
        "reviewrobin",
        "applydesk",
        "residentialops",
        "supportlogs",
        "utilities",
    ]


def test_runs_alone() -> None:
    client = TestClient(host_with(("applydesk",))[0])
    assert client.get(HEALTH).json() == {"status": "ok"}
    landing = client.get("/", follow_redirects=False)
    assert landing.status_code == 200
    assert re.search(r'<a href="/applydesk/"><img [^>]*>Apply Desk</a>', landing.text)
    assert client.get("/reviewrobin/health").status_code == 404
    assert client.get("/utilities/health").status_code == 404


def test_runs_beside_every_other_application() -> None:
    client = TestClient(host_with(None)[0])
    for entry in REGISTRY.values():
        assert client.get(f"{entry.path}/health").status_code == 200, entry.path


def test_health_needs_no_sign_in_or_settings() -> None:
    """No identity, no database: the probe answers whatever the request
    carries, so Easy Auth can exclude it."""
    client = TestClient(host_with(("applydesk",))[0])
    response = client.get(HEALTH, headers={})
    assert response.status_code == 200 and response.json() == {"status": "ok"}


def test_no_schema_pages() -> None:
    client = TestClient(host_with(("applydesk",))[0])
    for path in ("/applydesk/docs", "/applydesk/redoc", "/applydesk/openapi.json"):
        assert client.get(path).status_code == 404, path


def test_route_names_resolve_into_the_mount() -> None:
    """`url_for` resolves through the host's router, first mount first;
    with every application mounted, the name still lands here."""
    host, _ = host_with(None)
    assert host.url_path_for("applydesk_health") == HEALTH


def test_log_records_are_stamped_applydesk() -> None:
    _, handler = host_with(("applydesk",))
    record = logging.LogRecord("applydesk.main", logging.INFO, __file__, 1, "x", None, None)
    assert handler.filter(record)
    assert record.__dict__["application"] == "applydesk"


def test_favicon_is_the_rose_sheet_with_a_tick() -> None:
    """The landing page draws the favicon the app's own base template
    carries (`cordware/tests/test_landing.py` holds the copy to it)."""
    icon = REGISTRY["applydesk"].icon
    for part in ("viewBox='0 0 32 32'", "rx='7'", "fill='%23be123c'", "clip-path='url(%23t)'"):
        assert part in icon, part


def test_the_name_is_two_words_on_its_pages() -> None:
    """Ruling 17: the name is Apply Desk; the URL stays /applydesk."""
    client = TestClient(host_with(("applydesk",))[0])
    lobby = client.get("/applydesk/operator/exercises").text
    assert "<title>Operator Lobby · Apply Desk</title>" in lobby
    me = client.get("/applydesk/me").text
    assert "<title>User Lobby · Apply Desk</title>" in me
    assert "ApplyDesk" not in lobby + me


def test_the_entry_points_land_by_role(monkeypatch: pytest.MonkeyPatch) -> None:
    """`/` and `/operator` land an operator on the Operator Lobby and anyone
    else on the User Lobby, as Review Robin's do (author, 2026-11-13)."""
    from applydesk import routes_home

    client = TestClient(host_with(("applydesk",))[0])
    for path in ("/applydesk/", "/applydesk/operator", "/applydesk/operator/"):
        got = client.get(path, follow_redirects=False)
        assert (got.status_code, got.headers["location"]) == (
            302,
            "/applydesk/operator/exercises",
        ), path
    monkeypatch.setattr(routes_home, "is_operator", lambda request: False)
    for path in ("/applydesk/", "/applydesk/operator"):
        got = client.get(path, follow_redirects=False)
        assert got.headers["location"] == "/applydesk/me", path


def test_the_switcher_names_the_lobbies(monkeypatch: pytest.MonkeyPatch) -> None:
    from applydesk import web

    client = TestClient(host_with(("applydesk",))[0])
    lobby = client.get("/applydesk/operator/exercises").text
    assert "<h1>Operator Lobby</h1>" in lobby
    assert 'aria-current="page">Operator Lobby <span aria-hidden="true">✓</span>' in lobby
    assert ">User Lobby</a>" in lobby
    monkeypatch.setattr(web, "is_operator", lambda request: False)
    me = client.get("/applydesk/me").text
    assert "<h1>User Lobby</h1>" in me
    assert "Operator Lobby" not in me  # a non-operator's switcher offers only theirs


def test_the_bar_names_the_application() -> None:
    """The name beside the icon is Apply Desk on every page, as Review
    Robin's bar reads Review Robin (author, 2026-11-13)."""
    client = TestClient(host_with(("applydesk",))[0])
    for path in ("/applydesk/operator/exercises", "/applydesk/me"):
        page = client.get(path).text
        assert '<span class="sw-app">Apply Desk <span' in page, path
        assert 'aria-label="Switch area: Apply Desk"' in page, path


def test_operator_pages_take_review_robin_s_layout() -> None:
    """Operator pages: Review Robin's left-aligned wide layout; /me keeps
    the centred column (author, 2026-11-13)."""
    client = TestClient(host_with(("applydesk",))[0])
    assert '<body class="op">' in client.get("/applydesk/operator/exercises").text
    assert (
        '<body class="op">' in client.get("/applydesk/operator/exercises/wa9juxbc2t/process").text
    )
    assert "<body>" in client.get("/applydesk/me").text
