"""ApplyDesk under the Cordware host: the registry entry, running alone and
beside the others, health, route names, log stamps and the favicon
(`applydesk/spec/applications.md`; segment AD1, item 1)."""

from __future__ import annotations

import logging
import re

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
