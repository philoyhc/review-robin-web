"""The Cordware host: alone, with RRW mounted at `/`, and its contracts.

Segment 21A rung A1 (`guide/segment_21A_cordware_foundations.md`).
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from cordware.main import REGISTRY, AppEntry, create_app, parse_apps

# Lifespan calls recorded by the stub applications below.
EVENTS: list[str] = []


def _stub(name: str) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[dict[str, str]]:
        EVENTS.append(f"start {name}")
        yield {f"resource_{name}": f"made by {name}"}
        EVENTS.append(f"stop {name}")

    stub = FastAPI(lifespan=lifespan)

    @stub.get("/ping")
    def ping() -> dict[str, str]:
        return {"app": name}

    @stub.get("/resource")
    def resource(request: Request) -> dict[str, str]:
        return {"resource": getattr(request.state, f"resource_{name}")}

    return stub


def stub_clash() -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[dict[str, str]]:
        yield {"resource_a": "clash"}

    return FastAPI(lifespan=lifespan)


def stub_a() -> FastAPI:
    return _stub("a")


def stub_b() -> FastAPI:
    return _stub("b")


def failing_factory() -> FastAPI:
    raise RuntimeError("startup validation failed")


STUBS = {
    "a": AppEntry(path="/a", factory=f"{__name__}:stub_a", logger="stub_a"),
    "b": AppEntry(path="/b", factory=f"{__name__}:stub_b", logger="stub_b"),
}


def test_host_alone_serves_health_and_nothing_else() -> None:
    client = TestClient(create_app(apps=()))
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/operator", follow_redirects=False).status_code == 404


def test_host_with_rrw_mounts_it_at_root() -> None:
    client = TestClient(create_app(apps=("reviewrobin",)))
    assert client.get("/health").json() == {"status": "ok"}
    # RRW's own unguarded redirect, unchanged at `/`.
    response = client.get("/operator", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/operator/sessions"


def test_host_shadows_nothing_of_rrw_but_health() -> None:
    client = TestClient(create_app(apps=("reviewrobin",)))
    assert client.get("/openapi.json").json()["info"]["title"] == "Review Robin Web"
    assert client.get("/docs").status_code == 200


def test_registry_mounts_rrw_at_root() -> None:
    assert REGISTRY["reviewrobin"] == AppEntry(
        path="/", factory="app.main:create_app", logger="app"
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, ("a", "b")),
        ("", ()),
        ("  ", ()),
        ("a", ("a",)),
        (" b , a ", ("b", "a")),
    ],
)
def test_parse_apps(raw: str | None, expected: tuple[str, ...]) -> None:
    assert parse_apps(raw, STUBS) == expected


@pytest.mark.parametrize(
    ("raw", "named"),
    [("c", "unknown application(s) c"), ("a,A", "unknown application(s) A"), ("a,a", "repeats a")],
)
def test_parse_apps_refuses_unknown_or_repeated_names(raw: str, named: str) -> None:
    with pytest.raises(ValueError, match=re.escape(named)):
        parse_apps(raw, STUBS)


def test_cordware_apps_is_read_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORDWARE_APPS", "b")
    client = TestClient(create_app(registry=STUBS))
    assert client.get("/b/ping").json() == {"app": "b"}
    assert client.get("/a/ping").status_code == 404

    monkeypatch.setenv("CORDWARE_APPS", "")
    assert TestClient(create_app(registry=STUBS)).get("/b/ping").status_code == 404


def test_unknown_name_refuses_to_start(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORDWARE_APPS", "nope")
    with pytest.raises(ValueError, match="nope"):
        create_app(registry=STUBS)


def test_host_runs_mounted_lifespans_in_order() -> None:
    EVENTS.clear()
    with TestClient(create_app(apps=("a", "b"), registry=STUBS)) as client:
        assert EVENTS == ["start a", "start b"]
        assert client.get("/a/ping").json() == {"app": "a"}
    assert EVENTS == ["start a", "start b", "stop b", "stop a"]


def test_state_a_mounted_lifespan_yields_reaches_its_requests() -> None:
    with TestClient(create_app(apps=("a", "b"), registry=STUBS)) as client:
        assert client.get("/a/resource").json() == {"resource": "made by a"}
        assert client.get("/b/resource").json() == {"resource": "made by b"}


def test_a_lifespan_state_key_clash_refuses_to_start() -> None:
    registry = {**STUBS, "clash": AppEntry(path="/c", factory=f"{__name__}:stub_clash", logger="clash")}
    with pytest.raises(RuntimeError, match="'resource_a' from 'clash'"):
        with TestClient(create_app(apps=("a", "clash"), registry=registry)):
            pass


def test_a_failing_factory_fails_the_host() -> None:
    registry = {"bad": AppEntry(path="/bad", factory=f"{__name__}:failing_factory", logger="bad")}
    with pytest.raises(RuntimeError, match="startup validation failed"):
        create_app(apps=("bad",), registry=registry)


def test_rrw_startup_validation_failure_fails_the_host(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import ConfigurationError, settings
    from cordware.settings import identity_settings

    monkeypatch.setattr(identity_settings, "app_env", "production")
    # Off explicitly: a developer `.env` turns it on, and the guard would
    # refuse before RRW's validation runs.
    monkeypatch.setattr(identity_settings, "allow_fake_auth", False)
    monkeypatch.setattr(settings, "operator_emails", [])
    monkeypatch.setattr(settings, "sys_admin_emails", [])
    with pytest.raises(ConfigurationError):
        create_app(apps=("reviewrobin",))
