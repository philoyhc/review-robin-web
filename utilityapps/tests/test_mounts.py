"""Utilities under the Cordware host: the registry entry, running alone
and beside the others, the index, route names and log stamps
(`utilityapps/spec/utilities.md`; segment U1, rung 1)."""

from __future__ import annotations

import logging

from fastapi.testclient import TestClient

from cordware.main import REGISTRY, AppEntry
from utilityapps.tests._host import host_with

HEALTH = "/utilities/health"


def test_registry_entry() -> None:
    assert list(REGISTRY)[-1] == "utilities"
    assert REGISTRY["utilities"] == AppEntry(
        path="/utilities",
        factory="utilityapps.main:create_app",
        logger="utilityapps",
        title="Utilities",
    )


def test_runs_alone() -> None:
    client = TestClient(host_with(("utilities",))[0])
    assert client.get(HEALTH).json() == {"status": "ok"}
    landing = client.get("/", follow_redirects=False)
    assert landing.status_code == 302 and landing.headers["location"] == "/utilities/"
    assert client.get("/reviewrobin/health").status_code == 404
    assert client.get("/supportlogs/health").status_code == 404


def test_health_needs_no_sign_in_or_settings() -> None:
    """No identity and no Graph: the probe answers whatever the request
    carries, so Easy Auth can exclude it (spec §9)."""
    client = TestClient(host_with(("utilities",))[0])
    response = client.get(HEALTH, headers={})
    assert response.status_code == 200 and response.json() == {"status": "ok"}


def test_unset_mounts_it_last_on_the_landing_page() -> None:
    client = TestClient(host_with(None)[0])
    assert client.get(HEALTH).json() == {"status": "ok"}
    page = client.get("/").text
    titles = [entry.title for entry in REGISTRY.values()]
    order = [page.index(f">{title}<") for title in titles]
    assert order == sorted(order)


def test_index_links_the_checker() -> None:
    page = TestClient(host_with(("utilities",))[0]).get("/utilities/")
    assert page.status_code == 200
    assert "<h1>Cordware Utilities</h1>" in page.text
    assert 'href="/utilities/email-check/">Email Address Checker</a>' in page.text
    assert 'href="/"' in page.text  # the host's landing, not the mount's


def test_route_names_resolve_into_the_mount() -> None:
    """`url_for` resolves through the host's router, first mount first;
    with every application mounted ahead, the names still land here."""
    host, _ = host_with(None)
    assert host.url_path_for("utilities_health") == HEALTH
    assert host.url_path_for("utilities_home") == "/utilities/"


def test_log_records_are_stamped_utilities() -> None:
    _, handler = host_with(("utilities",))
    record = logging.LogRecord("utilityapps.main", logging.INFO, __file__, 1, "x", None, None)
    assert handler.filter(record)
    assert record.application == "utilities"


def test_favicon_is_the_amber_wrench_and_alerts_keep_the_status_hue() -> None:
    """Author's ruling, 2026-10-30: the favicon is a white wrench on amber
    `#b45309`, and an alert is never painted with the accent."""
    page = TestClient(host_with(("utilities",))[0]).get("/utilities/").text
    icon = page[page.index('<link rel="icon"') :]
    icon = icon[: icon.index('</svg>">') + 8]
    assert "fill='%23b45309'" in icon and "stroke='%23fff'" in icon
    assert "translate(7 7) scale(0.75)" in icon and "stroke-width='3.2'" in icon
    assert ".alert { border-color: var(--warn); }" in page
    assert ".alert strong { color: var(--warn); }" in page
