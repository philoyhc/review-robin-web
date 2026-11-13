"""Apply Desk's entry points, `/` and `/operator`: no page of their own,
they land by role, as Review Robin's do (Cordware's lobbies, author,
2026-11-13): an operator on the Operator Lobby, anyone else on the User
Lobby."""

from fastapi import APIRouter, Depends, Request
from starlette.responses import RedirectResponse

from applydesk.gate import is_operator, placeholders_only
from applydesk.web import url_path

router = APIRouter(dependencies=[Depends(placeholders_only)])


def _land(request: Request) -> RedirectResponse:
    to = "/operator/exercises" if is_operator(request) else "/me"
    return RedirectResponse(url_path(request, to), status_code=302)


@router.get("/", name="applydesk_home")
def home(request: Request) -> RedirectResponse:
    return _land(request)


@router.get("/operator", include_in_schema=False)
@router.get("/operator/", include_in_schema=False)
def operator_root(request: Request) -> RedirectResponse:
    return _land(request)
