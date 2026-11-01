"""The directory pickers' searches (segment 19Z, invite from the
directory): a session's roster rows ask the session's (rung 20), and the
"Help contact (optional)" boxes on New session and Session Home ask the
workspace's (rung 21), since New session has no session yet. Asked on the
operator's own delegated token; a local run asks the fake directory."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.db.models import ReviewSession
from app.web.deps import require_session_operator
from app.web.routes_operator._shared import directory_or_none, directory_search_response

router = APIRouter()


@router.get("/sessions/{session_id}/directory-search")
def roster_directory_search(
    request: Request,
    q: str = "",
    review_session: ReviewSession = Depends(require_session_operator),
) -> JSONResponse:
    """Up to ten people for a roster row's picker; the session's operators
    only (`_shared.directory_search_response`)."""
    return directory_search_response(directory_or_none(request), q)


@router.get("/directory-search")
def workspace_directory_search(request: Request, q: str = "") -> JSONResponse:
    """Up to ten people for a help-contact box's picker; any workspace
    operator (the package's `require_operator` gate)."""
    return directory_search_response(directory_or_none(request), q)
