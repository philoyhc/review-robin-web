"""Templates and mount-aware URLs for Utilities, after Residential's
`residentialapps/web/urls.py`, which it may not import
(`utilityapps/spec/utilities.md` "Import boundaries").

The application is mounted at `/utilities`, the ``root_path`` in the ASGI
scope. Templates write app-relative paths through ``url()``, which adds
the prefix once; ``host_url()`` marks a path that is the host's (the
landing page, ``/``) and emits it unchanged.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from fastapi.templating import Jinja2Templates
from jinja2 import pass_context
from jinja2.runtime import Context
from starlette.requests import HTTPConnection


def url_path(request: HTTPConnection, path: str) -> str:
    """An app-relative ``path`` with the mount's prefix; anything else
    (``#…``, ``?…``, ``//…``, Easy Auth's ``/.auth/…``) unchanged."""
    if path.startswith("/") and not path.startswith(("//", "/.auth/")):
        return request.scope.get("root_path", "").rstrip("/") + path
    return path


templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))


@pass_context
def _url(context: Context, path: str) -> str:
    return url_path(context["request"], path)


def _host_url(path: str) -> str:
    return path


class _HasGlobals(Protocol):
    globals: dict[str, object]


def _add_globals(env: _HasGlobals, **values: object) -> None:
    """Jinja infers `Environment.globals` from a literal, partly untyped:
    it is reached through this, typed once."""
    env.globals.update(values)


_add_globals(templates.env, url=_url, host_url=_host_url)
