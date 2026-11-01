"""The Cordware host: alone, with RRW mounted at `/reviewrobin`, and its contracts.

Segment 21A rung A1 (`guide/archive/segment_21A_cordware_foundations.md`).
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient

from cordware.main import REGISTRY, AppEntry, PublicOrigin, create_app, parse_apps, parse_public_origin

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


def test_host_alone_serves_no_application_path() -> None:
    client = TestClient(create_app(apps=()))
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/operator", follow_redirects=False).status_code == 404


def test_host_with_rrw_mounts_it_at_reviewrobin() -> None:
    client = TestClient(create_app(apps=("reviewrobin",)))
    assert client.get("/health").json() == {"status": "ok"}
    # RRW's own unguarded redirect, under the mount.
    response = client.get("/reviewrobin/operator", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/reviewrobin/operator/sessions"
    # The old root path is gone: no redirects from it (v0.8 non-goal).
    assert client.get("/operator", follow_redirects=False).status_code == 404


def test_host_shadows_nothing_of_rrw() -> None:
    client = TestClient(create_app(apps=("reviewrobin",)))
    openapi = client.get("/reviewrobin/openapi.json").json()
    assert openapi["info"]["title"] == "Review Robin Web"
    assert client.get("/reviewrobin/docs").status_code == 200
    assert client.get("/reviewrobin/health").json() == {"status": "ok"}


def test_registry_mounts_rrw_at_reviewrobin() -> None:
    assert REGISTRY["reviewrobin"] == AppEntry(
        path="/reviewrobin",
        factory="app.main:create_app",
        logger="app",
        title="Review Robin",
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


# --- `CORDWARE_PUBLIC_ORIGIN` (segment 21E) ---

ORIGIN = "https://apps.example.edu"


def stub_urls() -> FastAPI:
    stub = FastAPI()

    @stub.get("/where", name="where")
    def where(request: Request) -> dict[str, str]:
        return {"url": str(request.url), "built": str(request.url_for("where"))}

    @stub.get("/folder/")
    def folder() -> dict[str, str]:
        return {"ok": "yes"}

    return stub


URL_STUB = {"u": AppEntry(path="/u", factory=f"{__name__}:stub_urls", logger="stub_u")}


def _origin_host(monkeypatch: pytest.MonkeyPatch, origin: str | None) -> TestClient:
    if origin is None:
        monkeypatch.delenv("CORDWARE_PUBLIC_ORIGIN", raising=False)
    else:
        monkeypatch.setenv("CORDWARE_PUBLIC_ORIGIN", origin)
    return TestClient(create_app(apps=("u",), registry=URL_STUB), base_url="http://backend.internal")


def test_unset_urls_follow_the_request(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _origin_host(monkeypatch, None)
    assert client.get("/u/where").json() == {
        "url": "http://backend.internal/u/where",
        "built": "http://backend.internal/u/where",
    }
    slash = client.get("/u/folder", follow_redirects=False)
    assert slash.headers["location"] == "http://backend.internal/u/folder/"


def test_set_urls_and_slash_redirects_name_the_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _origin_host(monkeypatch, ORIGIN + "/")
    assert client.get("/u/where").json() == {
        "url": f"{ORIGIN}/u/where",
        "built": f"{ORIGIN}/u/where",
    }
    slash = client.get("/u/folder", follow_redirects=False)
    assert slash.status_code == 307
    assert slash.headers["location"] == f"{ORIGIN}/u/folder/"
    # The host's own routes still answer; they build no absolute URL.
    assert client.get("/health").json() == {"status": "ok"}


def test_no_request_header_moves_the_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _origin_host(monkeypatch, ORIGIN)
    forged = {
        "host": "evil.example",
        "x-original-host": "evil.example",
        "x-forwarded-host": "evil.example",
        "x-forwarded-proto": "http",
    }
    assert client.get("/u/where", headers=forged).json()["built"] == f"{ORIGIN}/u/where"


def test_a_utilities_slash_redirect_names_the_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORDWARE_PUBLIC_ORIGIN", ORIGIN)
    client = TestClient(create_app(apps=("utilities",)), base_url="http://backend.internal")
    slash = client.get("/utilities/email-check", follow_redirects=False)
    assert slash.headers["location"] == f"{ORIGIN}/utilities/email-check/"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, None),
        ("", None),
        ("  ", None),
        ("https://Apps.Example.edu", PublicOrigin("https", "apps.example.edu", 443, "apps.example.edu")),
        ("https://apps.example.edu/", PublicOrigin("https", "apps.example.edu", 443, "apps.example.edu")),
        (
            "https://apps.example.edu:8443",
            PublicOrigin("https", "apps.example.edu", 8443, "apps.example.edu:8443"),
        ),
        ("https://apps.example.edu:443", PublicOrigin("https", "apps.example.edu", 443, "apps.example.edu")),
        ("https://[::1]:8443", PublicOrigin("https", "::1", 8443, "[::1]:8443")),
    ],
)
def test_parse_public_origin(raw: str | None, expected: PublicOrigin | None) -> None:
    assert parse_public_origin(raw, local=False) == expected


def test_http_is_allowed_only_locally() -> None:
    assert parse_public_origin("http://127.0.0.1:8000", local=True) == PublicOrigin(
        "http", "127.0.0.1", 8000, "127.0.0.1:8000"
    )
    with pytest.raises(ValueError, match="http is allowed only at APP_ENV=local"):
        parse_public_origin("http://apps.example.edu", local=False)


@pytest.mark.parametrize(
    "raw",
    [
        "apps.example.edu",
        "ftp://apps.example.edu",
        "https://",
        "https://apps.example.edu/reviewrobin",
        "https://apps.example.edu?x=1",
        "https://apps.example.edu/?",
        "https://apps.example.edu#top",
        "https://user@apps.example.edu",
        "https://apps.example.edu:notaport",
        "https://apps.example.edu:0",
        "https://a b.edu",
        "https://apps.example.edu\\evil",
        "https://ex\u4e2d.edu",
        "https://ex\u00e4mple.edu",
        "https://-apps.example.edu",
    ],
)
def test_an_invalid_origin_refuses_to_start(monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
    with pytest.raises(ValueError, match="CORDWARE_PUBLIC_ORIGIN"):
        parse_public_origin(raw, local=True)
    monkeypatch.setenv("CORDWARE_PUBLIC_ORIGIN", raw)
    with pytest.raises(ValueError, match="CORDWARE_PUBLIC_ORIGIN"):
        create_app(apps=("u",), registry=URL_STUB)


# --- Compression ---------------------------------------------------------

BIG_PAGE = "<p>" + "Review Robin " * 500 + "</p>"


def stub_bodies() -> FastAPI:
    stub = FastAPI()

    @stub.get("/page")
    def page() -> Response:
        return Response(BIG_PAGE, media_type="text/html")

    @stub.get("/archive")
    def archive() -> Response:
        return Response(b"PK" + b"\0" * 5000, media_type="application/zip")

    return stub


GZIP_STUB = {"g": AppEntry(path="/g", factory=f"{__name__}:stub_bodies", logger="stub_g")}


def _gzip_host() -> TestClient:
    return TestClient(create_app(apps=("g",), registry=GZIP_STUB))


def test_a_large_page_is_gzipped_when_the_client_accepts_it() -> None:
    reply = _gzip_host().get("/g/page", headers={"accept-encoding": "gzip"})
    assert reply.headers["content-encoding"] == "gzip"
    assert reply.headers["vary"].lower() == "accept-encoding"
    assert int(reply.headers["content-length"]) < len(BIG_PAGE) // 5
    assert reply.text == BIG_PAGE  # the client decodes it to the same page


def test_a_client_that_does_not_accept_gzip_gets_the_page_as_is() -> None:
    reply = _gzip_host().get("/g/page", headers={"accept-encoding": "identity"})
    assert "content-encoding" not in reply.headers
    assert reply.text == BIG_PAGE


def test_small_bodies_and_archives_are_not_compressed() -> None:
    client = _gzip_host()
    health = client.get("/health", headers={"accept-encoding": "gzip"})
    assert "content-encoding" not in health.headers
    archive = client.get("/g/archive", headers={"accept-encoding": "gzip"})
    assert "content-encoding" not in archive.headers
    assert archive.content.startswith(b"PK")
