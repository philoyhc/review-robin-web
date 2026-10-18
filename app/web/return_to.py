"""Return-to-origin helper for the chrome's detour pages (Operator
Settings, About, the Guide, the Sys Admin pages, /auth/me/debug).

Per `spec/visual_style_rrw.md` "Return-to-origin behavior", these pages
render a "← Back to {context}" affordance whose target is captured via
the ``?return_to=<path>`` query param. The path is validated against an
allowlist (`spec/settings_inventory.md` § *URL state*); anything outside
falls back to ``/operator/sessions`` (the operator's natural lobby), or
to ``/me`` for a viewer who is not an operator (participant audit M8):
a participant sent to the lobby is only bounced back to ``/me``.

A session path is named only for a viewer who could see that session
anyway (``permissions.may_name_session``). Anyone else gets the default target, so the
label never confirms that a session exists or says what it is called
(participant audit P1, `guide/archive/participant_surface_check.md`).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import unquote

from sqlalchemy.orm import Session
from starlette.routing import Match

from app.db.models import User
from app.services import permissions, sessions


@dataclass(frozen=True)
class ReturnTarget:
    url: str
    label: str


DEFAULT_TARGET = ReturnTarget(url="/operator/sessions", label="Sessions")
PARTICIPANT_DEFAULT = ReturnTarget(url="/me", label="your reviews")

# ``\Z``, not ``$``: ``$`` also matches before a trailing newline. And
# ASCII classes, not ``\w`` or ``\d``, which match any Unicode letter or
# digit. Either would pass a character a ``Location`` or a cookie
# refuses. A session is named by its URL public ID (19V Item 1).
_OPERATOR_SESSIONS = re.compile(r"^/operator/sessions/?\Z")
# The operator pages outside a session that carry the chrome's links.
_OPERATOR_PAGES = {
    "/operator/sessions/archived": "Archived sessions",
    "/operator/sessions/new": "New session",
    "/operator/settings": "Settings",
}
# A session page at any depth (a tab, an instrument's editor), so a
# detour returns to the page it left rather than the session's home, as
# long as a GET serves it (`_is_get_page`).
_OPERATOR_SESSION = re.compile(r"^/operator/sessions/([0-9a-z]+)(?:/[A-Za-z0-9_\-]+)*/?\Z")
_REVIEWER_ROOT = re.compile(r"^/me/?\Z")
_REVIEWER_SESSION = re.compile(r"^/me/sessions/([0-9a-z]+)/?\Z")


def _is_get_page(path: str) -> bool:
    """Whether a GET route serves ``path``. The chrome builds
    ``return_to`` from the request path, which on a page a POST rendered
    (an import's error page) is the POST's, and going back there with a
    GET would 405."""
    from app.main import app  # here, not at the top: app.main imports this module

    scope = {"type": "http", "path": path, "method": "GET"}
    return any(route.matches(scope)[0] is Match.FULL for route in app.router.routes)


Viewer = User | None | Callable[[], User | None]


def _once(viewer: Viewer) -> Callable[[], User | None]:
    """``viewer`` as a getter that resolves a callable at most once, and
    only when first asked, so a caller whose viewer costs a query pays
    it only when a label needs it. (``/auth/me/debug`` now also asks for
    its top bar, through its own per-request cache.)"""
    if not callable(viewer):
        return lambda: viewer
    cache: list[User | None] = []

    def get() -> User | None:
        if not cache:
            cache.append(viewer())
        return cache[0]

    return get


def _fallback(get_viewer: Callable[[], User | None]) -> ReturnTarget:
    """The Sessions lobby for an operator, ``/me`` for anyone else."""
    viewer = get_viewer()
    if viewer is not None and (viewer.is_operator or viewer.is_sys_admin):
        return DEFAULT_TARGET
    return PARTICIPANT_DEFAULT


def resolve_return_to(
    raw: str | None, db: Session, *, viewer: Viewer
) -> ReturnTarget:
    """Validate a ``return_to`` path and resolve a human-readable label.

    Anything outside the allowlist (including absolute URLs, paths with
    ``..`` segments, or unknown shapes) falls back to the default
    target. Session paths resolve their label from the session name
    when the row exists and ``viewer`` may see it; otherwise they fall
    back to the default, the same answer for a session that does not
    exist. The fallback is the Sessions lobby for an operator and
    ``/me`` for anyone else. ``viewer`` may be a callable returning the
    user, called at most once and only when an answer needs it.
    """
    get_viewer = _once(viewer)
    target = _resolve(raw, db, get_viewer)
    return target if target is not None else _fallback(get_viewer)


def _resolve(
    raw: str | None, db: Session, get_viewer: Callable[[], User | None]
) -> ReturnTarget | None:
    """The allowlisted target for ``raw``, or ``None`` to fall back."""
    if not raw:
        return None

    # Reject anything that isn't a same-origin path.
    if not raw.startswith("/") or raw.startswith("//"):
        return None

    path = unquote(raw).split("?", 1)[0].split("#", 1)[0]
    if ".." in path.split("/"):
        return None

    if _OPERATOR_SESSIONS.match(path):
        return ReturnTarget(url=path, label="Sessions")

    page = _OPERATOR_PAGES.get(path.removesuffix("/"))
    if page is not None:
        return ReturnTarget(url=path, label=page)

    m = _OPERATOR_SESSION.match(path)
    if m and _is_get_page(path):
        session = sessions.get_by_public_id(db, m.group(1))
        if session is None or not permissions.may_name_session(db, get_viewer(), session):
            return None
        return ReturnTarget(url=path, label=session.name)

    if _REVIEWER_ROOT.match(path):
        return ReturnTarget(url=path, label="your reviews")

    m = _REVIEWER_SESSION.match(path)
    if m:
        session = sessions.get_by_public_id(db, m.group(1))
        if session is None or not permissions.may_name_session(db, get_viewer(), session):
            return None
        return ReturnTarget(url=path, label=session.name)

    return None
