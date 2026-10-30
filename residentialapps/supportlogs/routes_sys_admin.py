"""Support Logs' Sys admin on sample data, segment 1D item 1 rung 6: Access
over the Staff roster, the configured lists and the administrative audit
(functional spec §3.3, §11.3; roles rules 1, 6, 8, 9). Administration
sees no support content. Nothing is stored: changes wait on item 2."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from starlette.requests import Request
from starlette.responses import Response

from residentialapps.supportlogs import sample_support as sample
from residentialapps.supportlogs.pages import SYS_ADMIN_AREA, gated
from residentialapps.web.pages import placeholders_local_only

router = APIRouter(dependencies=[Depends(placeholders_local_only)])


def _page(request: Request, template: str, **context: object) -> Response:
    me = sample.viewer(request.query_params.get("as"))
    return gated(request, f"supportlogs/sys_admin/{template}", *sample.ADMINISTRATION, area=SYS_ADMIN_AREA,
                 super_admin=sample.holds(me, sample.SUPER_ADMIN), **context)


@router.get("/sys-admin/", name="supportlogs_sys_admin")
def access(request: Request) -> Response:
    """Access: every active Staff-roster member and the grants each holds,
    lapsed grants first. The Sys admin column is the super-admin's alone.
    With no one holding Senior identifiable it warns (author, 2026-10-30);
    `?preview=no-senior` shows the warning on the sample, which has one."""
    none = request.query_params.get("preview") == "no-senior"
    return _page(request, "access.html", seniors=[] if none else sample.holders(sample.SENIOR))


@router.get("/sys-admin/configuration", name="supportlogs_sys_admin_configuration")
def configuration(request: Request) -> Response:
    """The lists staff choose from (§5.5–5.10, §6.4, §7.3–7.4) and the
    consultation rules (§10.8)."""
    return _page(request, "configuration.html")


@router.get("/sys-admin/audit", name="supportlogs_sys_admin_audit")
def audit(request: Request) -> Response:
    """Administrative events only; the support-activity audit is senior
    staff's (§11.3)."""
    return _page(request, "audit.html")
