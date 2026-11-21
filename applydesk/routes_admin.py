"""The platform super-admin's pages, `/admin/…` (segment AD2A, ruling 75):
the operator list, who may operate an exercise. Scaffold first (rung 5):
the page's copy and layout, its controls inert; rung 6 wires the search,
*Admit* and *Revoke*."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from starlette.responses import Response

from applydesk import gate
from applydesk.web import OPERATOR_LIST, render

router = APIRouter(prefix="/admin", dependencies=[Depends(gate.require_super_admin)])


@router.get("/operators", name="applydesk_admin_operators")
def operators_page(request: Request) -> Response:
    return render(request, "applydesk/admin/operators.html", area=OPERATOR_LIST)
