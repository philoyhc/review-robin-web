"""Which name the top bar's top line shows (segment 20D,
`docs/header_chrome.md` §6, "Which name a page shows").

Read from the page's template context, so no route has to pass it:

- a session's pages, operator or participant (a ``session`` in context):
  the Unit of the operator who **created** the session, else the default;
- a participant's Your reviews (the route passes ``top_line_sessions``):
  the default, unless every session listed resolves to the same Unit;
- any other page: the viewer's own Unit if they are an operator, else the
  default.

The keys are the ones every session page already passes (``session``, the
`ReviewSession`); a page that names it otherwise falls through to the
viewer's Unit, which is why `tests/integration/test_user_unit.py` checks a
session page of each kind.

The default is ``CORDWARE_INSTITUTION_NAME``; empty means no top line.
The creator's Unit is read as the page renders, so a change shows on
their existing sessions at once.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from jinja2 import pass_context
from jinja2.runtime import Context

from app.db.models import ReviewSession
from cordware.identity import institution_name


def session_unit(review_session: ReviewSession) -> str | None:
    """The Unit a session's pages show: its creator's, or None."""
    creator = review_session.created_by_user
    return creator.unit if creator is not None else None


def dashboard_top_line(sessions: Iterable[ReviewSession], default: str) -> str:
    """Your reviews: one Unit when every listed session resolves to it,
    else the default (an empty list shows the default)."""
    resolved = {session_unit(s) or default for s in sessions}
    return resolved.pop() if len(resolved) == 1 else default


def resolve_top_line(
    *,
    default: str,
    review_session: Any = None,
    dashboard_sessions: Iterable[ReviewSession] | None = None,
    viewer: Any = None,
) -> str:
    if isinstance(review_session, ReviewSession):
        return session_unit(review_session) or default
    if dashboard_sessions is not None:
        return dashboard_top_line(dashboard_sessions, default)
    is_operator = getattr(viewer, "is_operator", False) or getattr(
        viewer, "is_sys_admin", False
    )
    if is_operator:
        return getattr(viewer, "unit", None) or default
    return default


@pass_context
def top_line(context: Context, viewer: Any = None) -> str:
    """The template global the top bar calls, with the viewer it shows
    (``user``, or a page's ``bar_user``)."""
    return resolve_top_line(
        default=institution_name(),
        review_session=context.get("session"),
        dashboard_sessions=context.get("top_line_sessions"),
        viewer=viewer,
    )
