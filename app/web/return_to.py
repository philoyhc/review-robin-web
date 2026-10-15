"""Return-to-origin helper for the chrome's detour pages (Operator
Settings, About, the Guide, the Sys Admin pages, /auth/me/debug).

Per `spec/visual_style_rrw.md` "Return-to-origin behavior", these pages
render a "← Back to {context}" affordance whose target is captured via
the ``?return_to=<path>`` query param. The path is validated against an
allowlist (`spec/settings_inventory.md` § *URL state*); anything outside
falls back to ``/operator/sessions`` (the operator's natural lobby).

A session path is named only for a viewer who could see that session
anyway (``permissions.may_name_session``). Anyone else gets the default target, so the
label never confirms that a session exists or says what it is called
(participant audit P1, `guide/participant_surface_check.md`).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import unquote

from sqlalchemy.orm import Session
from starlette.routing import Match

from app.db.models import ReviewSession, User
from app.services import permissions


@dataclass(frozen=True)
class ReturnTarget:
    url: str
    label: str


DEFAULT_TARGET = ReturnTarget(url="/operator/sessions", label="Sessions")

# ``\Z``, not ``$``: ``$`` also matches before a trailing newline. And
# ``[0-9]``, not ``\d``: ``\d`` matches any Unicode digit, which ``int()``
# accepts. Either would pass a character a ``Location`` or a cookie
# refuses.
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
_OPERATOR_SESSION = re.compile(r"^/operator/sessions/([0-9]+)(?:/[A-Za-z0-9_\-]+)*/?\Z")
_REVIEWER_ROOT = re.compile(r"^/me/?\Z")
_REVIEWER_SESSION = re.compile(r"^/me/sessions/([0-9]+)/?\Z")


def _is_get_page(path: str) -> bool:
    """Whether a GET route serves ``path``. The chrome builds
    ``return_to`` from the request path, which on a page a POST rendered
    (an import's error page) is the POST's, and going back there with a
    GET would 405."""
    from app.main import app  # here, not at the top: app.main imports this module

    scope = {"type": "http", "path": path, "method": "GET"}
    return any(route.matches(scope)[0] is Match.FULL for route in app.router.routes)


Viewer = User | None | Callable[[], User | None]


def _may_name(db: Session, viewer: Viewer, session: ReviewSession) -> bool:
    # A callable is resolved only here, so a caller whose viewer costs a
    # query (``/auth/me/debug``) pays it only for a session path.
    resolved = viewer() if callable(viewer) else viewer
    return permissions.may_name_session(db, resolved, session)


def resolve_return_to(
    raw: str | None, db: Session, *, viewer: Viewer
) -> ReturnTarget:
    """Validate a ``return_to`` path and resolve a human-readable label.

    Anything outside the allowlist (including absolute URLs, paths with
    ``..`` segments, or unknown shapes) falls back to the default
    target. Session paths resolve their label from the session name
    when the row exists and ``viewer`` may see it; otherwise they fall
    back to the default, the same answer for a session that does not
    exist. ``viewer`` may be a callable returning the user, called only
    when a session path needs naming.
    """
    if not raw:
        return DEFAULT_TARGET

    # Reject anything that isn't a same-origin path.
    if not raw.startswith("/") or raw.startswith("//"):
        return DEFAULT_TARGET

    path = unquote(raw).split("?", 1)[0].split("#", 1)[0]
    if ".." in path.split("/"):
        return DEFAULT_TARGET

    if _OPERATOR_SESSIONS.match(path):
        return ReturnTarget(url=path, label="Sessions")

    page = _OPERATOR_PAGES.get(path.removesuffix("/"))
    if page is not None:
        return ReturnTarget(url=path, label=page)

    m = _OPERATOR_SESSION.match(path)
    if m and _is_get_page(path):
        session = db.get(ReviewSession, int(m.group(1)))
        if session is None or not _may_name(db, viewer, session):
            return DEFAULT_TARGET
        return ReturnTarget(url=path, label=session.name)

    if _REVIEWER_ROOT.match(path):
        return ReturnTarget(url=path, label="your reviews")

    m = _REVIEWER_SESSION.match(path)
    if m:
        session = db.get(ReviewSession, int(m.group(1)))
        if session is None or not _may_name(db, viewer, session):
            return DEFAULT_TARGET
        return ReturnTarget(url=path, label=session.name)

    return DEFAULT_TARGET
