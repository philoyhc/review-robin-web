"""Rehydrate an extracted session — operator surface.

Segment 18P Group 2. Reached from the ``Rehydrate`` button in the
Sessions Lobby search-card row; rebuilds a session from a complete set
of extract CSV files (``docs/rehydrate.md``).

**PR G0 (this file) is the UI scaffold only** — the page renders with
three inert placeholder cards so the surface can be agreed before any
logic is wired (see ``CLAUDE.md`` → Working approach, "consequential UI
lands scaffold-first"). The Validate / Rehydrate actions, the pre-flight
analyzer, the stash, and the commit orchestrator land in the follow-up
PRs (F / G1 / G2 / G3 / H).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from app.db.models import User
from app.web import breadcrumbs
from app.web.deps import get_or_create_user
from app.web.routes_operator._shared import _templates

router = APIRouter()


@router.get("/sessions/rehydrate", response_class=HTMLResponse)
def rehydrate_page(
    request: Request,
    user: User = Depends(get_or_create_user),
) -> HTMLResponse:
    """The rehydrate landing page. Scaffold only (PR G0) — the cards
    are placeholders and the actions are inert."""
    return _templates.TemplateResponse(
        request,
        "operator/session_rehydrate.html",
        {
            "user": user,
            "breadcrumbs": breadcrumbs.operator_rehydrate_session(),
        },
    )
