"""ApplyDesk's landing page, `/` (segment AD1, item 2)."""

from fastapi import APIRouter, Depends, Request
from starlette.responses import Response

from applydesk.gate import placeholders_only
from applydesk.web import render

router = APIRouter(dependencies=[Depends(placeholders_only)])


@router.get("/", name="applydesk_home")
def home(request: Request) -> Response:
    return render(request, "applydesk/landing.html", area="ApplyDesk")
