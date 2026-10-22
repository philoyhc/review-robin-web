"""Mount-aware URLs: app-relative values travel, the prefix is added at emission.

RRW is a mounted application (`cordware/spec/host.md`). Routes, views,
services, breadcrumbs and `return_to` build app-relative strings such as
``/operator/sessions/abc/home``; the mount's prefix, ``root_path`` in the
ASGI scope, is added once, where a URL leaves RRW:

- templates call the ``url()`` global on every link, form action and
  source;
- routes answer with :func:`redirect`, the one place a
  ``RedirectResponse`` is built;
- cookies scope with :func:`cookie_path`;
- comparisons read :func:`app_path`, the request path without the
  prefix (templates: ``here()``, ``is_here()``, ``here_in()``,
  ``here_under()``).

At ``/`` ``root_path`` is empty, so every helper returns its input.
Segment 21B (`guide/archive/segment_21B_url_sweep.md`) moves RRW's call sites
onto these. `tests/unit/test_url_leaks.py` fails on an emission that
skips them, and `tests/integration/test_url_crawl.py` fails on a page
that emits one under the mount.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fastapi.templating import Jinja2Templates
from jinja2 import pass_context
from starlette.requests import HTTPConnection
from starlette.responses import RedirectResponse


def root_path(request: HTTPConnection) -> str:
    """The mount's prefix for this request: ``""`` at ``/``, else e.g.
    ``/reviewrobin``, with no trailing slash."""
    return request.scope.get("root_path", "").rstrip("/")


def url_path(request: HTTPConnection, path: str | None) -> str:
    """``path`` as emitted. An app-relative path (one leading ``/``) gains
    the mount's prefix; anything else (``//host``, a scheme, ``#…``,
    ``?…``, a relative path, Easy Auth's host-level ``/.auth/…``) passes
    through unchanged, and an empty value renders empty. Idempotent: a
    path already under the prefix is returned as it is, so a template may
    wrap a value where it is set and again where it is emitted."""
    if not path:
        return ""
    if path.startswith("/.auth/"):
        return path  # Easy Auth's, at the host level (v0.8 §3)
    if path.startswith("/") and not path.startswith("//"):
        prefix = root_path(request)
        if prefix and (path == prefix or path.startswith((prefix + "/", prefix + "?", prefix + "#"))):
            return path  # already emitted once: a value wrapped where it is set and where it is used
        return prefix + path
    return path


def app_path(request: HTTPConnection) -> str:
    """The request path relative to the mount: what a route sees as its
    own path. Starlette keeps the prefix in ``request.url.path`` under a
    mount, so comparisons read this instead."""
    path = request.url.path
    prefix = root_path(request)
    if prefix and (path == prefix or path.startswith(prefix + "/")):
        return path[len(prefix) :] or "/"
    return path


def redirect(
    request: HTTPConnection,
    url: str,
    status_code: int = 307,
    headers: Mapping[str, str] | None = None,
) -> RedirectResponse:
    """A ``RedirectResponse`` to ``url`` as emitted. The defaults are
    ``RedirectResponse``'s own, so a call site moves over unchanged."""
    return RedirectResponse(url_path(request, url), status_code=status_code, headers=headers)


def cookie_path(request: HTTPConnection, path: str = "/") -> str:
    """A cookie ``Path`` scoped under the mount: the prefix plus ``path``."""
    return url_path(request, path)


@pass_context
def _url(context: Mapping[str, Any], path: str | None) -> str:
    return url_path(context["request"], path)


@pass_context
def _here(context: Mapping[str, Any]) -> str:
    return app_path(context["request"])


@pass_context
def _is_here(context: Mapping[str, Any], path: str) -> bool:
    return app_path(context["request"]) == path


@pass_context
def _here_in(context: Mapping[str, Any], *paths: str) -> bool:
    return app_path(context["request"]) in paths


@pass_context
def _here_under(context: Mapping[str, Any], prefix: str) -> bool:
    return app_path(context["request"]).startswith(prefix)


TEMPLATE_GLOBALS = {
    "url": _url,
    "here": _here,
    "is_here": _is_here,
    "here_in": _here_in,
    "here_under": _here_under,
}


def install(templates: Jinja2Templates) -> Jinja2Templates:
    """Add the URL globals to a ``Jinja2Templates`` environment."""
    templates.env.globals.update(TEMPLATE_GLOBALS)
    return templates
