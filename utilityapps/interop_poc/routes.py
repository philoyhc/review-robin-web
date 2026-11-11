"""The proof of concept's page (segment 23A). Super-admin only, every
response `no-store`. The page carries the bundle; its script adds a
fresh transfer id and session code per click and posts it to Review
Robin's create route (`spec/handoffs.md`)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from starlette.requests import Request
from starlette.responses import Response

from cordware.identity import resolve_identity
from utilityapps.access import require_super_admin
from utilityapps.interop_poc import mock
from utilityapps.web import templates

router = APIRouter(prefix="/interop-poc", dependencies=[Depends(require_super_admin)])

_NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache"}


@router.get("/", name="utilities_interop_poc")
def page(request: Request) -> Response:
    identity = resolve_identity(request)
    email = identity.email or ""
    people = mock.reviewers(identity.name or email, email)
    return templates.TemplateResponse(
        request,
        "interop_poc/page.html",
        {
            "exercise": mock.EXERCISE,
            "reviewers": people,
            "applications": mock.APPLICATIONS,
            "reviewers_csv": mock.reviewers_csv(people),
            "reviewees_csv": mock.reviewees_csv(),
            "bundle": mock.bundle(people),
        },
        headers=_NO_STORE,
    )
