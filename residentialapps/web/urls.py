"""Mount-aware URLs for Residential's pages, after RRW's `app/web/urls.py`.

Each application is mounted under its own prefix (`/residentialops`,
`/supportlogs`), the ``root_path`` in the ASGI scope. Routes and templates
build app-relative paths such as ``/rosters/``; the prefix is added once,
where a URL leaves the application:

- templates call ``url()`` on every link, form action and source inside
  the application;
- ``host_url()`` marks a path that is the host's, not the application's
  (the landing page, ``/``), and emits it unchanged;
- comparisons read ``app_path()`` (templates: ``is_here()``).

Residential may not import RRW's ``app`` (`residentialapps/spec/architecture.md`
"Import boundaries"), so this is its own helper. `residentialapps/tests/test_pages.py`
fails on a template link that skips it and on a page that emits a path
outside its mount.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from fastapi.templating import Jinja2Templates
from jinja2 import pass_context
from starlette.requests import HTTPConnection

WEB_TEMPLATES = Path(__file__).resolve().parent / "templates"


def root_path(request: HTTPConnection) -> str:
    """The mount's prefix for this request: ``""`` unmounted, else e.g.
    ``/residentialops``, with no trailing slash."""
    return request.scope.get("root_path", "").rstrip("/")


def url_path(request: HTTPConnection, path: str | None) -> str:
    """``path`` as emitted: an app-relative path (one leading ``/``) gains
    the mount's prefix; anything else (``#…``, ``?…``, a scheme, Easy
    Auth's ``/.auth/…``) passes through, and an empty value renders empty."""
    if not path:
        return ""
    if path.startswith("/.auth/"):
        return path
    if path.startswith("/") and not path.startswith("//"):
        return root_path(request) + path
    return path


def app_path(request: HTTPConnection) -> str:
    """The request path relative to the mount, for comparisons."""
    path = request.url.path
    prefix = root_path(request)
    if prefix and (path == prefix or path.startswith(prefix + "/")):
        return path[len(prefix) :] or "/"
    return path


def templates(directories: Sequence[Path]) -> Jinja2Templates:
    """A template environment over an application's own directories and
    the shared one, with the URL helpers as globals."""
    env = Jinja2Templates(directory=[*directories, WEB_TEMPLATES])

    @pass_context
    def url(context, path: str | None) -> str:
        return url_path(context["request"], path)

    @pass_context
    def is_here(context, path: str) -> bool:
        return app_path(context["request"]) == path

    def host_url(path: str) -> str:
        return path

    env.env.globals.update(url=url, is_here=is_here, host_url=host_url)
    return env
