"""`app/web/urls.py` at `/` and under the `/reviewrobin` mount.

Segment 21B rung B1 (`guide/segment_21B_url_sweep.md`). The first half
pins what Starlette does to a mounted application's scope, which the
helpers are built on; the second half pins that every helper returns its
input at `/` and adds the prefix under the mount.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.testclient import TestClient
from jinja2 import DictLoader, Environment
from starlette.responses import Response

from _mounted import MOUNT, host_with, leaks
from app.web import urls

_PAGE = """\
<a href="{{ url('/operator/sessions') }}">lobby</a>
<a href="{{ url('#top') }}">top</a>
<a href="{{ url('/.auth/logout') }}">out</a>
<span id="here">{{ here() }}</span>
<span id="is">{{ is_here('/probe/page') }}</span>
<span id="in">{{ here_in('/me', '/probe/page') }}</span>
<span id="under">{{ here_under('/probe') }}</span>
"""


def probe_app() -> FastAPI:
    """A stand-in application whose routes report the scope and call the
    helpers, so these tests don't depend on any RRW page."""
    probe = FastAPI()
    templates = urls.install(
        Jinja2Templates(env=Environment(loader=DictLoader({"page.html": _PAGE}), autoescape=True))
    )

    @probe.get("/probe/scope/{n}", name="probe_scope")
    def scope(request: Request, n: int) -> dict[str, object]:
        return {
            "url_path": request.url.path,
            "root_path": request.scope.get("root_path", ""),
            "app_path": urls.app_path(request),
            "url_path_for": str(request.app.url_path_for("probe_scope", n=n)),
            "url_for": str(request.url_for("probe_scope", n=n)),
            "emitted": urls.url_path(request, "/operator/sessions"),
            "cookie_path": urls.cookie_path(request, "/operator/sessions"),
        }

    @probe.get("/probe/redirect")
    def go(request: Request) -> Response:
        return urls.redirect(
            request,
            url="/operator/sessions?x=1",
            status_code=303,
            headers={"X-FieldKey-Error": "taken"},
        )

    @probe.get("/probe/leaky", response_class=HTMLResponse)
    def leaky(request: Request) -> HTMLResponse:
        response = HTMLResponse(
            '<a href="/operator/x">a</a><form action="/me/y"></form><img src="/static/z.png">'
            '<a href="https://example.edu/">ok</a><a href="#f">ok</a><a href="/.auth/me">ok</a>'
        )
        response.set_cookie("c", "v", path="/operator/sessions")
        return response

    @probe.get("/probe/page", response_class=HTMLResponse)
    def page(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(request, "page.html")

    return probe


@pytest.fixture(params=["/", MOUNT], ids=["root", "mounted"])
def mounted_at(request: pytest.FixtureRequest) -> tuple[str, TestClient]:
    path = request.param
    host = host_with(f"{__name__}:probe_app", path=path)
    return ("" if path == "/" else path), TestClient(host)


# --- What Starlette does under a mount (the facts the helpers rely on) ---


def test_under_a_mount_root_path_is_the_prefix_and_url_path_keeps_it() -> None:
    client = TestClient(host_with(f"{__name__}:probe_app"))
    body = client.get(f"{MOUNT}/probe/scope/3").json()
    assert body["root_path"] == MOUNT
    assert body["url_path"] == f"{MOUNT}/probe/scope/3"
    assert body["url_path_for"] == "/probe/scope/3"
    assert body["url_for"] == f"http://testserver{MOUNT}/probe/scope/3"


def test_at_root_the_scope_is_unchanged() -> None:
    client = TestClient(host_with(f"{__name__}:probe_app", path="/"))
    body = client.get("/probe/scope/3").json()
    assert body["root_path"] == ""
    assert body["url_path"] == body["url_path_for"] == "/probe/scope/3"
    assert body["url_for"] == "http://testserver/probe/scope/3"


# --- The helpers ---


def test_app_path_and_emission(mounted_at: tuple[str, TestClient]) -> None:
    prefix, client = mounted_at
    body = client.get(f"{prefix}/probe/scope/3").json()
    assert body["app_path"] == "/probe/scope/3"
    assert body["emitted"] == f"{prefix}/operator/sessions"
    assert body["cookie_path"] == f"{prefix}/operator/sessions"


def test_redirect_adds_the_prefix_and_keeps_status_query_and_headers(
    mounted_at: tuple[str, TestClient],
) -> None:
    prefix, client = mounted_at
    response = client.get(f"{prefix}/probe/redirect", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == f"{prefix}/operator/sessions?x=1"
    assert response.headers["x-fieldkey-error"] == "taken"


def test_template_globals(mounted_at: tuple[str, TestClient]) -> None:
    prefix, client = mounted_at
    html = client.get(f"{prefix}/probe/page").text
    assert f'href="{prefix}/operator/sessions"' in html
    assert 'href="#top"' in html
    assert 'href="/.auth/logout"' in html
    assert '<span id="here">/probe/page</span>' in html
    for name in ("is", "in", "under"):
        assert f'<span id="{name}">True</span>' in html


@pytest.mark.parametrize(
    "value",
    ["", None, "#a", "?q=1", "https://example.edu/x", "//cdn.example/x", "mailto:a@b", "rel/x"],
)
def test_url_path_passes_non_app_paths_through(value: str | None) -> None:
    request = Request({"type": "http", "path": "/x", "root_path": MOUNT, "headers": []})
    assert urls.url_path(request, value) == (value or "")


def test_app_path_leaves_a_path_outside_the_prefix_alone() -> None:
    request = Request(
        {"type": "http", "path": "/reviewrobinx/y", "root_path": MOUNT, "headers": []}
    )
    assert urls.app_path(request) == "/reviewrobinx/y"


# --- RRW itself under the harness ---


def test_rrw_answers_under_the_mount_and_the_host_keeps_health(
    mounted_client: TestClient,
) -> None:
    assert mounted_client.get("/health").json() == {"status": "ok"}
    assert mounted_client.get(f"{MOUNT}/health").json() == {"status": "ok"}
    assert mounted_client.get("/operator/sessions").status_code == 404


def test_every_rrw_template_environment_has_the_url_globals() -> None:
    from app.web import error_handlers, routes_about, routes_auth, routes_guide
    from app.web.routes_operator import _shared as operator_shared
    from app.web.routes_reviewer import _shared as reviewer_shared

    for module in (
        error_handlers,
        routes_about,
        routes_auth,
        routes_guide,
        operator_shared,
        reviewer_shared,
    ):
        assert set(urls.TEMPLATE_GLOBALS) <= set(module._templates.env.globals), module


# --- The crawl's checker ---


def test_the_checker_finds_every_kind_of_leak() -> None:
    client = TestClient(host_with(f"{__name__}:probe_app"))
    found = leaks(client.get(f"{MOUNT}/probe/leaky"))
    assert sorted(found) == ["/me/y", "/operator/sessions", "/operator/x", "/static/z.png"]
    assert leaks(client.get(f"{MOUNT}/probe/redirect", follow_redirects=False)) == []


def test_a_page_built_with_the_helpers_does_not_leak() -> None:
    client = TestClient(host_with(f"{__name__}:probe_app"))
    assert leaks(client.get(f"{MOUNT}/probe/page")) == []


def test_building_the_harness_leaves_root_logging_as_it_was() -> None:
    import logging

    root = logging.getLogger()
    before = (list(root.handlers), root.level)
    host_with(f"{__name__}:probe_app")
    assert (list(root.handlers), root.level) == before


def test_url_path_is_idempotent_under_the_mount() -> None:
    request = Request({"type": "http", "path": "/x", "root_path": MOUNT, "headers": []})
    once = urls.url_path(request, "/operator/sessions?x=1")
    assert urls.url_path(request, once) == once == f"{MOUNT}/operator/sessions?x=1"
    assert urls.url_path(request, MOUNT) == MOUNT
    assert urls.url_path(request, "/reviewrobinx") == f"{MOUNT}/reviewrobinx"
