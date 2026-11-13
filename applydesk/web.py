"""Templates, mount-aware URLs and the page chrome for ApplyDesk, after
Residential's `residentialapps/web/urls.py`, which it may not import
(`applydesk/spec/architecture.md`, "Import boundaries").

The application is mounted at `/applydesk`, the ``root_path`` in the ASGI
scope. Templates write app-relative paths through ``url()``, which adds
the prefix once; ``host_url()`` marks a path that is the host's (the
landing page, ``/``, and Easy Auth's ``/.auth/…``) and emits it unchanged;
comparisons read ``is_here()``.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol

from fastapi import Request
from fastapi.templating import Jinja2Templates
from jinja2 import pass_context
from jinja2.runtime import Context
from starlette.requests import HTTPConnection
from starlette.responses import Response

from applydesk.gate import is_operator
from cordware.identity import current_identity, institution_name


def root_path(request: HTTPConnection) -> str:
    return request.scope.get("root_path", "").rstrip("/")


def url_path(request: HTTPConnection, path: str | None) -> str:
    """An app-relative ``path`` with the mount's prefix; anything else
    (``#…``, ``?…``, ``//…``, ``/.auth/…``) unchanged; empty stays empty."""
    if not path:
        return ""
    if path.startswith("/") and not path.startswith(("//", "/.auth/")):
        return root_path(request) + path
    return path


def app_path(request: HTTPConnection) -> str:
    """The request path relative to the mount, for comparisons."""
    path = request.url.path
    prefix = root_path(request)
    if prefix and (path == prefix or path.startswith(prefix + "/")):
        return path[len(prefix) :] or "/"
    return path


templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))


@pass_context
def _url(context: Context, path: str | None) -> str:
    return url_path(context["request"], path)


@pass_context
def _is_here(context: Context, path: str) -> bool:
    return app_path(context["request"]) == path


def _host_url(path: str) -> str:
    return path


class _HasGlobals(Protocol):
    globals: dict[str, object]


def _add_globals(env: _HasGlobals, **values: object) -> None:
    """Jinja infers `Environment.globals` from a literal, partly untyped:
    it is reached through this, typed once (as in `utilityapps/web.py`)."""
    env.globals.update(values)


_add_globals(templates.env, url=_url, is_here=_is_here, host_url=_host_url)

APP_NAME = "Apply Desk"

OPERATOR_LOBBY, USER_LOBBY = "Operator Lobby", "User Lobby"

#: The switcher's places (`docs/header_chrome.md` §3), named as Review
#: Robin's are (author, 2026-11-13): the Operator Lobby for an operator
#: (`gate.is_operator`), the User Lobby for everyone.
PLACES: tuple[Mapping[str, Any], ...] = (
    {"label": OPERATOR_LOBBY, "path": "/operator/exercises", "operators": True},
    {"label": USER_LOBBY, "path": "/me", "operators": False},
)


#: An exercise's pages beyond Home, in the chrome's two rows (ruling 14):
#: (path segment, tab label).
SETUP_PAGES: tuple[tuple[str, str], ...] = (
    ("process", "Process"),
    ("form", "Form"),
    ("gates", "Gates"),
    ("emails", "Emails"),
)
OPERATIONS_PAGES: tuple[tuple[str, str], ...] = (
    ("applications", "Applications"),
    ("evaluations", "Evaluations"),
    ("extract", "Extract data"),
)


def exercise_nav(exercise_id: str, current: str) -> Mapping[str, Any]:
    """An exercise's chrome (ruling 14, segment AD1D): Home, then the
    Setup and Operations rows, each tab's path, and the page showing
    (``current``: "" for Home, else a path segment)."""
    base = f"/operator/exercises/{exercise_id}"

    def row(pages: tuple[tuple[str, str], ...]) -> list[Mapping[str, Any]]:
        return [
            {"label": label, "path": f"{base}/{key}", "on": key == current} for key, label in pages
        ]

    setup, operations = row(SETUP_PAGES), row(OPERATIONS_PAGES)
    return {
        "home": {"label": "Exercise Home", "path": base, "on": current == ""},
        "setup": setup,
        "operations": operations,
        "setup_on": any(t["on"] for t in setup),
        "operations_on": any(t["on"] for t in operations),
    }


def initials(label: str) -> str:
    parts = [p for p in label.replace("@", " ").split() if p[:1].isalpha()]
    return "".join(p[0] for p in parts[:2]).upper() or "?"


def render(
    request: Request,
    template: str,
    *,
    area: str,
    nav: Mapping[str, Any] | None = None,
    status_code: int = 200,
    **context: Any,
) -> Response:
    """A page in the shared bar (`docs/header_chrome.md`): the app icon,
    the workspace's top line over ``area``, the switcher and the account
    menu; on an exercise's pages, ``nav``, its chrome (ruling 14)."""
    viewer = current_identity(request)
    operator = is_operator(request)
    return templates.TemplateResponse(
        request,
        template,
        {
            "app_name": APP_NAME,
            "operator_page": app_path(request).startswith("/operator"),
            "area": area,
            "places": [p for p in PLACES if operator or not p["operators"]],
            "nav": nav,
            "top_line": institution_name(),
            "viewer": viewer,
            "initials": initials(viewer.display_label) if viewer else "?",
            **context,
        },
        status_code=status_code,
    )
