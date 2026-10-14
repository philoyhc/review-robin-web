"""Return-to-origin helper for detour destinations (About, /auth/me/debug).

Per `spec/visual_style_rrw.md` "Return-to-origin behavior", these pages
render a "← Back to {context}" affordance whose target is captured via
the ``?return_to=<path>`` query param. The path is validated against a
tight allowlist; anything outside falls back to ``/operator/sessions``
(the operator's natural lobby).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import unquote

from sqlalchemy.orm import Session

from app.db.models import ReviewSession


@dataclass(frozen=True)
class ReturnTarget:
    url: str
    label: str


DEFAULT_TARGET = ReturnTarget(url="/operator/sessions", label="Sessions")

# ``\Z``, not ``$``: ``$`` also matches before a trailing newline, which
# would pass a control character through to a ``Location`` or a cookie.
_OPERATOR_SESSIONS = re.compile(r"^/operator/sessions/?\Z")
# The operator pages outside a session that carry the chrome's links.
_OPERATOR_PAGES = {
    "/operator/sessions/archived": "Archived sessions",
    "/operator/sessions/new": "New session",
    "/operator/settings": "Settings",
}
# A session page at any depth (a tab, an instrument's editor), so a
# detour returns to the page it left rather than the session's home.
_OPERATOR_SESSION = re.compile(r"^/operator/sessions/(\d+)(?:/[A-Za-z0-9_\-]+)*/?\Z")
_REVIEWER_ROOT = re.compile(r"^/me/?\Z")
_REVIEWER_SESSION = re.compile(r"^/me/sessions/(\d+)/?\Z")


def resolve_return_to(raw: str | None, db: Session) -> ReturnTarget:
    """Validate a ``return_to`` path and resolve a human-readable label.

    Anything outside the allowlist (including absolute URLs, paths with
    ``..`` segments, or unknown shapes) falls back to the default
    target. Session paths resolve their label from the session name
    when the row exists; otherwise they fall back to the default.
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

    page = _OPERATOR_PAGES.get(path.rstrip("/"))
    if page is not None:
        return ReturnTarget(url=path, label=page)

    m = _OPERATOR_SESSION.match(path)
    if m:
        session = db.get(ReviewSession, int(m.group(1)))
        if session is None:
            return DEFAULT_TARGET
        return ReturnTarget(url=path, label=session.name)

    if _REVIEWER_ROOT.match(path):
        return ReturnTarget(url=path, label="your reviews")

    m = _REVIEWER_SESSION.match(path)
    if m:
        session = db.get(ReviewSession, int(m.group(1)))
        if session is None:
            return DEFAULT_TARGET
        return ReturnTarget(url=path, label=session.name)

    return DEFAULT_TARGET
