"""The directory pickers' search for a session's roster rows (segment
19Z, invite from the directory, rung 20): the Reviewers, Reviewees and
Observers add and edit rows ask it as the operator types a name or an
address. Asked on the operator's own delegated token; a local run asks
the fake directory."""

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
