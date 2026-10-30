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

from fastapi.templating import Jinja2Templates
from jinja2 import pass_context
from starlette.requests import HTTPConnection


def url_path(request: HTTPConnection, path: str) -> str:
    """An app-relative ``path`` with the mount's prefix; anything else
    (``#…``, ``?…``, ``//…``, Easy Auth's ``/.auth/…``) unchanged."""
    if path.startswith("/") and not path.startswith(("//", "/.auth/")):
        return request.scope.get("root_path", "").rstrip("/") + path
    return path


templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))


@pass_context
def _url(context, path: str) -> str:
    return url_path(context["request"], path)


templates.env.globals.update(url=_url, host_url=lambda path: path)
