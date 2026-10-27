"""Both Residential applications under the Cordware host: the registry
entries, every `CORDWARE_APPS` combination, route-name resolution and log
stamps (`residentialapps/spec/applications.md`)."""

from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient

from cordware.main import REGISTRY, AppEntry
from residentialapps.tests._host import host_with

HEALTH = {"residentialops": "/residentialops/health", "supportlogs": "/supportlogs/health"}


def test_registry_entries() -> None:
    assert list(REGISTRY) == ["reviewrobin", "residentialops", "supportlogs"]
    assert REGISTRY["residentialops"] == AppEntry(
        path="/residentialops",
        factory="residentialapps.residentialops.main:create_app",
        logger="residentialapps.residentialops",
        title="Residential Operations",
    )
    assert REGISTRY["supportlogs"] == AppEntry(
        path="/supportlogs",
        factory="residentialapps.supportlogs.main:create_app",
        logger="residentialapps.supportlogs",
        title="Support Logs",
    )


def test_logger_prefixes_do_not_nest() -> None:
    prefixes = [entry.logger for entry in REGISTRY.values()]
    for a in prefixes:
        assert not any(b != a and b.startswith(a + ".") for b in prefixes), a


@pytest.mark.parametrize("name", ["residentialops", "supportlogs"])
def test_each_runs_alone(name: str) -> None:
    host, _ = host_with((name,))
    client = TestClient(host)
    assert client.get(HEALTH[name]).json() == {"status": "ok"}
    landing = client.get("/", follow_redirects=False)
    assert landing.status_code == 302
    assert landing.headers["location"] == f"{REGISTRY[name].path}/"
    other = next(n for n in HEALTH if n != name)
    assert client.get(HEALTH[other]).status_code == 404


def test_both_together_list_on_the_landing_page() -> None:
    host, _ = host_with(("residentialops", "supportlogs"))
    client = TestClient(host)
    for path in HEALTH.values():
        assert client.get(path).json() == {"status": "ok"}
    page = client.get("/").text
    assert "Residential Operations" in page and "Support Logs" in page
    assert page.index("Residential Operations") < page.index("Support Logs")


def test_unset_mounts_rrw_and_both() -> None:
    host, _ = host_with(None)
    client = TestClient(host)
    assert client.get("/reviewrobin/health").json() == {"status": "ok"}
    for path in HEALTH.values():
        assert client.get(path).json() == {"status": "ok"}
    page = client.get("/").text
    order = [page.index(name) for name in ("Review Robin", "Residential Operations", "Support Logs")]
    assert order == sorted(order)


@pytest.mark.parametrize("name", ["residentialops", "supportlogs"])
def test_bare_mount_has_no_page_yet(name: str) -> None:
    host, _ = host_with((name,))
    assert TestClient(host).get(f"{REGISTRY[name].path}/").status_code == 404


def test_health_names_resolve_into_their_own_mount() -> None:
    """`url_for` inside a mount resolves through the host's router, first
    mount first; with RRW mounted ahead, each name must still land home."""
    host, _ = host_with(None)
    for name, path in HEALTH.items():
        assert host.url_path_for(f"{name}_health") == path


@pytest.mark.parametrize(
    ("logger", "application"),
    [
        ("residentialapps.residentialops", "residentialops"),
        ("residentialapps.residentialops.main", "residentialops"),
        ("residentialapps.supportlogs.main", "supportlogs"),
        ("app.services", "reviewrobin"),
    ],
)
def test_log_records_are_stamped_with_their_application(logger: str, application: str) -> None:
    _, handler = host_with(("residentialops", "supportlogs"))
    record = logging.LogRecord(logger, logging.INFO, __file__, 1, "x", None, None)
    assert handler.filter(record)
    assert record.application == application
